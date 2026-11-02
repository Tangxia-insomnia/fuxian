int engine_main(int argc, char **argv)
{
    int ret = 1, i;
    int verbose = 0, list_cap = 0, test_avail = 0, test_avail_noise = 0;
    ENGINE *e;
    STACK_OF(OPENSSL_CSTRING) *engines = sk_OPENSSL_CSTRING_new_null();
    STACK_OF(OPENSSL_STRING) *pre_cmds = sk_OPENSSL_STRING_new_null();
    STACK_OF(OPENSSL_STRING) *post_cmds = sk_OPENSSL_STRING_new_null();
    BIO *out;
    const char *indent = "     ";
    OPTION_CHOICE o;
    char *prog;
    char *argv1;

    out = dup_bio_out(FORMAT_TEXT);
    if (engines == NULL || pre_cmds == NULL || post_cmds == NULL)
        goto end;

    /* Remember the original command name, parse/skip any leading engine
     * names, and then setup to parse the rest of the line as flags. */
    prog = argv[0];
    while ((argv1 = argv[1]) != NULL && *argv1 != '-') {
        sk_OPENSSL_CSTRING_push(engines, argv1);
        argc--;
        argv++;
    }
    argv[0] = prog;
    opt_init(argc, argv, engine_options);

    while ((o = opt_next()) != OPT_EOF) {
        switch (o) {
        case OPT_EOF:
        case OPT_ERR:
            BIO_printf(bio_err, "%s: Use -help for summary.\n", prog);
            goto end;
        case OPT_HELP:
            opt_help(engine_options);
            ret = 0;
            goto end;
        case OPT_VVVV:
        case OPT_VVV:
        case OPT_VV:
        case OPT_V:
            /* Convert to an integer from one to four. */
            i = (int)(o - OPT_V) + 1;
            if (verbose < i)
                verbose = i;
            break;
        case OPT_C:
            list_cap = 1;
            break;
        case OPT_TT:
            test_avail_noise++;
            /* fall through */
        case OPT_T:
            test_avail++;
            break;
        case OPT_PRE:
            sk_OPENSSL_STRING_push(pre_cmds, opt_arg());
            break;
        case OPT_POST:
            sk_OPENSSL_STRING_push(post_cmds, opt_arg());
            break;
        }
    }

    /* Any remaining arguments are engine names. */
    argc = opt_num_rest();
    argv = opt_rest();
    for ( ; *argv; argv++) {
        if (**argv == '-') {
            BIO_printf(bio_err, "%s: Cannot mix flags and engine names.\n",
                       prog);
            BIO_printf(bio_err, "%s: Use -help for summary.\n", prog);
            goto end;
        }
        sk_OPENSSL_CSTRING_push(engines, *argv);
    }

    if (sk_OPENSSL_CSTRING_num(engines) == 0) {
        for (e = ENGINE_get_first(); e != NULL; e = ENGINE_get_next(e)) {
            sk_OPENSSL_CSTRING_push(engines, ENGINE_get_id(e));
        }
    }

    ret = 0;
    for (i = 0; i < sk_OPENSSL_CSTRING_num(engines); i++) {
        const char *id = sk_OPENSSL_CSTRING_value(engines, i);
        if ((e = ENGINE_by_id(id)) != NULL) {
            const char *name = ENGINE_get_name(e);
            /*
             * Do "id" first, then "name". Easier to auto-parse.
             */
            BIO_printf(out, "(%s) %s\n", id, name);
            util_do_cmds(e, pre_cmds, out, indent);
            if (strcmp(ENGINE_get_id(e), id) != 0) {
                BIO_printf(out, "Loaded: (%s) %s\n",
                           ENGINE_get_id(e), ENGINE_get_name(e));
            }
            if (list_cap) {
                int cap_size = 256;
                char *cap_buf = NULL;
                int k, n;
                const int *nids;
                ENGINE_CIPHERS_PTR fn_c;
                ENGINE_DIGESTS_PTR fn_d;
                ENGINE_PKEY_METHS_PTR fn_pk;

                if (ENGINE_get_RSA(e) != NULL
                    && !append_buf(&cap_buf, &cap_size, "RSA"))
                    goto end;
                if (ENGINE_get_EC(e) != NULL
                    && !append_buf(&cap_buf, &cap_size, "EC"))
                    goto end;
                if (ENGINE_get_DSA(e) != NULL
                    && !append_buf(&cap_buf, &cap_size, "DSA"))
                    goto end;
                if (ENGINE_get_DH(e) != NULL
                    && !append_buf(&cap_buf, &cap_size, "DH"))
                    goto end;
                if (ENGINE_get_RAND(e) != NULL
                    && !append_buf(&cap_buf, &cap_size, "RAND"))
                    goto end;

                fn_c = ENGINE_get_ciphers(e);
                if (fn_c == NULL)
                    goto skip_ciphers;
                n = fn_c(e, NULL, &nids, 0);
                for (k = 0; k < n; ++k)
                    if (!append_buf(&cap_buf, &cap_size, OBJ_nid2sn(nids[k])))
                        goto end;

 skip_ciphers:
                fn_d = ENGINE_get_digests(e);
                if (fn_d == NULL)
                    goto skip_digests;
                n = fn_d(e, NULL, &nids, 0);
                for (k = 0; k < n; ++k)
                    if (!append_buf(&cap_buf, &cap_size, OBJ_nid2sn(nids[k])))
                        goto end;

 skip_digests:
                fn_pk = ENGINE_get_pkey_meths(e);
                if (fn_pk == NULL)
                    goto skip_pmeths;
                n = fn_pk(e, NULL, &nids, 0);
                for (k = 0; k < n; ++k)
                    if (!append_buf(&cap_buf, &cap_size, OBJ_nid2sn(nids[k])))
                        goto end;
 skip_pmeths:
                {
                    struct util_store_cap_data store_ctx;

                    store_ctx.engine = e;
                    store_ctx.cap_buf = &cap_buf;
                    store_ctx.cap_size = &cap_size;
                    store_ctx.ok = 1;

                    OSSL_STORE_do_all_loaders(util_store_cap, &store_ctx);
                    if (!store_ctx.ok)
                        goto end;
                }
                if (cap_buf != NULL && (*cap_buf != '\0'))
                    BIO_printf(out, " [%s]\n", cap_buf);

                OPENSSL_free(cap_buf);
            }
            if (test_avail) {
                BIO_printf(out, "%s", indent);
                if (ENGINE_init(e)) {
                    BIO_printf(out, "[ available ]\n");
                    util_do_cmds(e, post_cmds, out, indent);
                    ENGINE_finish(e);
                } else {
                    BIO_printf(out, "[ unavailable ]\n");
                    if (test_avail_noise)
                        ERR_print_errors_fp(stdout);
                    ERR_clear_error();
                }
            }
            if ((verbose > 0) && !util_verbose(e, verbose, out, indent))
                goto end;
            ENGINE_free(e);
        } else {
            ERR_print_errors(bio_err);
            /* because exit codes above 127 have special meaning on Unix */
            if (++ret > 127)
                ret = 127;
        }
    }

 end:

    ERR_print_errors(bio_err);
    sk_OPENSSL_CSTRING_free(engines);
    sk_OPENSSL_STRING_free(pre_cmds);
    sk_OPENSSL_STRING_free(post_cmds);
    BIO_free_all(out);
    return ret;
}