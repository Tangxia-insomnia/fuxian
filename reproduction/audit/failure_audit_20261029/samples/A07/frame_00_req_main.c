int req_main(int argc, char **argv)
{
    ASN1_INTEGER *serial = NULL;
    BIO *out = NULL;
    ENGINE *e = NULL, *gen_eng = NULL;
    EVP_PKEY *pkey = NULL, *CAkey = NULL;
    EVP_PKEY_CTX *genctx = NULL;
    STACK_OF(OPENSSL_STRING) *pkeyopts = NULL, *sigopts = NULL, *vfyopts = NULL;
    LHASH_OF(OPENSSL_STRING) *addexts = NULL;
    X509 *new_x509 = NULL, *CAcert = NULL;
    X509_REQ *req = NULL;
    const EVP_CIPHER *cipher = NULL;
    int ext_copy = EXT_COPY_UNSET;
    BIO *addext_bio = NULL;
    char *extsect = NULL;
    const char *infile = NULL, *CAfile = NULL, *CAkeyfile = NULL;
    char *outfile = NULL, *keyfile = NULL, *digest = NULL;
    char *keyalgstr = NULL, *p, *prog, *passargin = NULL, *passargout = NULL;
    char *passin = NULL, *passout = NULL;
    char *nofree_passin = NULL, *nofree_passout = NULL;
    char *subj = NULL;
    X509_NAME *fsubj = NULL;
    char *template = default_config_file, *keyout = NULL;
    const char *keyalg = NULL;
    OPTION_CHOICE o;
    char *not_before = NULL, *not_after = NULL;
    int days = UNSET_DAYS;
    int ret = 1, gen_x509 = 0, i = 0, newreq = 0, verbose = 0, progress = 1;
    int informat = FORMAT_UNDEF, outformat = FORMAT_PEM, keyform = FORMAT_UNDEF;
    int modulus = 0, multirdn = 1, verify = 0, noout = 0, text = 0;
    int noenc = 0, newhdr = 0, subject = 0, pubkey = 0, precert = 0, x509v1 = 0;
    long newkey_len = -1;
    unsigned long chtype = MBSTRING_ASC, reqflag = 0;

    cipher = (EVP_CIPHER *)EVP_aes_256_cbc();

    opt_set_unknown_name("digest");
    prog = opt_init(argc, argv, req_options);
    while ((o = opt_next()) != OPT_EOF) {
        switch (o) {
        case OPT_EOF:
        case OPT_ERR:
 opthelp:
            BIO_printf(bio_err, "%s: Use -help for summary.\n", prog);
            goto end;
        case OPT_HELP:
            opt_help(req_options);
            ret = 0;
            goto end;
        case OPT_INFORM:
            if (!opt_format(opt_arg(), OPT_FMT_PEMDER, &informat))
                goto opthelp;
            break;
        case OPT_OUTFORM:
            if (!opt_format(opt_arg(), OPT_FMT_PEMDER, &outformat))
                goto opthelp;
            break;
        case OPT_ENGINE:
            e = setup_engine(opt_arg(), 0);
            break;
        case OPT_KEYGEN_ENGINE:
#ifndef OPENSSL_NO_ENGINE
            gen_eng = setup_engine(opt_arg(), 0);
            if (gen_eng == NULL) {
                BIO_printf(bio_err, "Can't find keygen engine %s\n", *argv);
                goto opthelp;
            }
#endif
            break;
        case OPT_KEY:
            keyfile = opt_arg();
            break;
        case OPT_PUBKEY:
            pubkey = 1;
            break;
        case OPT_NEW:
            newreq = 1;
            break;
        case OPT_CONFIG:
            template = opt_arg();
            break;
        case OPT_SECTION:
            section = opt_arg();
            break;
        case OPT_KEYFORM:
            if (!opt_format(opt_arg(), OPT_FMT_ANY, &keyform))
                goto opthelp;
            break;
        case OPT_IN:
            infile = opt_arg();
            break;
        case OPT_OUT:
            outfile = opt_arg();
            break;
        case OPT_KEYOUT:
            keyout = opt_arg();
            break;
        case OPT_PASSIN:
            passargin = opt_arg();
            break;
        case OPT_PASSOUT:
            passargout = opt_arg();
            break;
        case OPT_R_CASES:
            if (!opt_rand(o))
                goto end;
            break;
        case OPT_PROV_CASES:
            if (!opt_provider(o))
                goto end;
            break;
        case OPT_NEWKEY:
            keyalg = opt_arg();
            newreq = 1;
            break;
        case OPT_PKEYOPT:
            if (pkeyopts == NULL)
                pkeyopts = sk_OPENSSL_STRING_new_null();
            if (pkeyopts == NULL
                    || !sk_OPENSSL_STRING_push(pkeyopts, opt_arg()))
                goto opthelp;
            break;
        case OPT_SIGOPT:
            if (!sigopts)
                sigopts = sk_OPENSSL_STRING_new_null();
            if (!sigopts || !sk_OPENSSL_STRING_push(sigopts, opt_arg()))
                goto opthelp;
            break;
        case OPT_VFYOPT:
            if (!vfyopts)
                vfyopts = sk_OPENSSL_STRING_new_null();
            if (!vfyopts || !sk_OPENSSL_STRING_push(vfyopts, opt_arg()))
                goto opthelp;
            break;
        case OPT_BATCH:
            batch = 1;
            break;
        case OPT_NEWHDR:
            newhdr = 1;
            break;
        case OPT_MODULUS:
            modulus = 1;
            break;
        case OPT_VERIFY:
            verify = 1;
            break;
        case OPT_NODES:
        case OPT_NOENC:
            noenc = 1;
            break;
        case OPT_NOOUT:
            noout = 1;
            break;
        case OPT_VERBOSE:
            verbose = 1;
            progress = 1;
            break;
        case OPT_QUIET:
            verbose = 0;
            progress = 0;
            break;
        case OPT_UTF8:
            chtype = MBSTRING_UTF8;
            break;
        case OPT_NAMEOPT:
            if (!set_nameopt(opt_arg()))
                goto opthelp;
            break;
        case OPT_REQOPT:
            if (!set_cert_ex(&reqflag, opt_arg()))
                goto opthelp;
            break;
        case OPT_TEXT:
            text = 1;
            break;
        case OPT_X509V1:
            x509v1 = 1;
            /* fall thru */
        case OPT_X509:
            gen_x509 = 1;
            break;
        case OPT_CA:
            CAfile = opt_arg();
            gen_x509 = 1;
            break;
        case OPT_CAKEY:
            CAkeyfile = opt_arg();
            break;
        case OPT_NOT_BEFORE:
            not_before = opt_arg();
            break;
        case OPT_NOT_AFTER:
            not_after = opt_arg();
            break;
        case OPT_DAYS:
            days = atoi(opt_arg());
            if (days <= UNSET_DAYS) {
                BIO_printf(bio_err, "%s: -days parameter arg must be >= -1\n",
                           prog);
                goto end;
            }
            break;
        case OPT_SET_SERIAL:
            if (serial != NULL) {
                BIO_printf(bio_err, "Serial number supplied twice\n");
                goto opthelp;
            }
            serial = s2i_ASN1_INTEGER(NULL, opt_arg());
            if (serial == NULL)
                goto opthelp;
            break;
        case OPT_SUBJECT:
            subject = 1;
            break;
        case OPT_SUBJ:
            subj = opt_arg();
            break;
        case OPT_MULTIVALUE_RDN:
            /* obsolete */
            break;
        case OPT_COPY_EXTENSIONS:
            if (!set_ext_copy(&ext_copy, opt_arg())) {
                BIO_printf(bio_err, "Invalid extension copy option: \"%s\"\n",
                           opt_arg());
                goto end;
            }
            break;
        case OPT_EXTENSIONS:
        case OPT_REQEXTS:
            extsect = opt_arg();
            break;
        case OPT_ADDEXT:
            p = opt_arg();
            if (addexts == NULL) {
                addexts = lh_OPENSSL_STRING_new(ext_name_hash, ext_name_cmp);
                addext_bio = BIO_new(BIO_s_mem());
                if (addexts == NULL || addext_bio == NULL)
                    goto end;
            }
            i = duplicated(addexts, p);
            if (i == 1)
                goto end;
            if (i == -1)
                BIO_printf(bio_err, "Internal error handling -addext %s\n", p);
            if (i < 0 || BIO_printf(addext_bio, "%s\n", p) < 0)
                goto end;
            break;
        case OPT_PRECERT:
            newreq = precert = 1;
            break;
        case OPT_CIPHER:
            cipher = EVP_get_cipherbyname(opt_arg());
            if (cipher == NULL) {
                BIO_printf(bio_err, "Unknown cipher: %s\n", opt_arg());
                goto opthelp;
            }
            break;
        case OPT_MD:
            digest = opt_unknown();
            break;
        }
    }

    /* No extra arguments. */
    if (!opt_check_rest_arg(NULL))
        goto opthelp;

    if (!app_RAND_load())
        goto end;

    if (!gen_x509) {
        if (days != UNSET_DAYS)
            BIO_printf(bio_err, "Warning: Ignoring -days without -x509; not generating a certificate\n");
        if (not_before != NULL)
            BIO_printf(bio_err, "Warning: Ignoring -not_before without -x509; not generating a certificate\n");
        if (not_after != NULL)
            BIO_printf(bio_err, "Warning: Ignoring -not_after without -x509; not generating a certificate\n");
        if (ext_copy == EXT_COPY_NONE)
            BIO_printf(bio_err, "Warning: Ignoring -copy_extensions 'none' when -x509 is not given\n");
    }
    if (infile == NULL) {
        if (gen_x509)
            newreq = 1;
        else if (!newreq && isatty(fileno_stdin()))
            BIO_printf(bio_err,
                       "Warning: Will read cert request from stdin since no -in option is given\n");
    }

    if (!app_passwd(passargin, passargout, &passin, &passout)) {
        BIO_printf(bio_err, "Error getting passwords\n");
        goto end;
    }

    if ((req_conf = app_load_config_verbose(template, verbose)) == NULL)
        goto end;
    if (addext_bio != NULL) {
        if (verbose)
            BIO_printf(bio_err,
                       "Using additional configuration from -addext options\n");
        if ((addext_conf = app_load_config_bio(addext_bio, NULL)) == NULL)
            goto end;
    }
    if (template != default_config_file && !app_load_modules(req_conf))
        goto end;

    if (req_conf != NULL) {
        p = app_conf_try_string(req_conf, NULL, "oid_file");
        if (p != NULL) {
            BIO *oid_bio = BIO_new_file(p, "r");

            if (oid_bio == NULL) {
                if (verbose)
                    BIO_printf(bio_err,
                               "Problems opening '%s' for extra OIDs\n", p);
            } else {
                OBJ_create_objects(oid_bio);
                BIO_free(oid_bio);
            }
        }
    }
    if (!add_oid_section(req_conf))
        goto end;

    /* Check that any specified digest is fetchable */
    if (digest != NULL) {
        if (!opt_check_md(digest))
            goto opthelp;
    } else {
        /* No digest specified, default to configuration */
        p = app_conf_try_string(req_conf, section, "default_md");
        if (p != NULL)
            digest = p;
    }

    if (extsect == NULL)
        extsect = app_conf_try_string(req_conf, section,
                                   gen_x509 ? V3_EXTENSIONS : REQ_EXTENSIONS);
    if (extsect != NULL) {
        /* Check syntax of extension section in config file */
        X509V3_CTX ctx;

        X509V3_set_ctx_test(&ctx);
        X509V3_set_nconf(&ctx, req_conf);
        if (!X509V3_EXT_add_nconf(req_conf, &ctx, extsect, NULL)) {
            BIO_printf(bio_err,
                       "Error checking %s extension section %s\n",
                       gen_x509 ? "x509" : "request", extsect);
            goto end;
        }
    }
    if (addext_conf != NULL) {
        /* Check syntax of command line extensions */
        X509V3_CTX ctx;

        X509V3_set_ctx_test(&ctx);
        X509V3_set_nconf(&ctx, req_conf);
        if (!X509V3_EXT_add_nconf(addext_conf, &ctx, "default", NULL)) {
            BIO_printf(bio_err, "Error checking extensions defined using -addext\n");
            goto end;
        }
    }

    if (passin == NULL)
        passin = nofree_passin =
            app_conf_try_string(req_conf, section, "input_password");

    if (passout == NULL)
        passout = nofree_passout =
            app_conf_try_string(req_conf, section, "output_password");

    p = app_conf_try_string(req_conf, section, STRING_MASK);
    if (p != NULL && !ASN1_STRING_set_default_mask_asc(p)) {
        BIO_printf(bio_err, "Invalid global string mask setting %s\n", p);
        goto end;
    }

    if (chtype != MBSTRING_UTF8) {
        p = app_conf_try_string(req_conf, section, UTF8_IN);
        if (p != NULL && strcmp(p, "yes") == 0)
            chtype = MBSTRING_UTF8;
    }

    if (keyfile != NULL) {
        pkey = load_key(keyfile, keyform, 0, passin, e, "private key");
        if (pkey == NULL)
            goto end;
        app_RAND_load_conf(req_conf, section);
    }
    if (keyalg != NULL && pkey != NULL) {
        BIO_printf(bio_err,
                   "Warning: Not generating key via given -newkey option since -key is given\n");
        /* Better throw an error in this case */
    }
    if (newreq && pkey == NULL) {
        app_RAND_load_conf(req_conf, section);

        if (!app_conf_try_number(req_conf, section, BITS, &newkey_len))
            newkey_len = DEFAULT_KEY_LENGTH;

        genctx = set_keygen_ctx(keyalg, &keyalgstr, &newkey_len, gen_eng);
        if (genctx == NULL)
            goto end;

        if (newkey_len < MIN_KEY_LENGTH
            && (EVP_PKEY_CTX_is_a(genctx, "RSA")
                || EVP_PKEY_CTX_is_a(genctx, "RSA-PSS")
                || EVP_PKEY_CTX_is_a(genctx, "DSA"))) {
            BIO_printf(bio_err, "Private key length too short, needs to be at least %d bits, not %ld.\n",
                       MIN_KEY_LENGTH, newkey_len);
            goto end;
        }

        if (newkey_len > OPENSSL_RSA_MAX_MODULUS_BITS
            && (EVP_PKEY_CTX_is_a(genctx, "RSA")
                || EVP_PKEY_CTX_is_a(genctx, "RSA-PSS")))
            BIO_printf(bio_err,
                       "Warning: It is not recommended to use more than %d bit for RSA keys.\n"
                       "         Your key size is %ld! Larger key size may behave not as expected.\n",
                       OPENSSL_RSA_MAX_MODULUS_BITS, newkey_len);

#ifndef OPENSSL_NO_DSA
        if (EVP_PKEY_CTX_is_a(genctx, "DSA")
                && newkey_len > OPENSSL_DSA_MAX_MODULUS_BITS)
            BIO_printf(bio_err,
                       "Warning: It is not recommended to use more than %d bit for DSA keys.\n"
                       "         Your key size is %ld! Larger key size may behave not as expected.\n",
                       OPENSSL_DSA_MAX_MODULUS_BITS, newkey_len);
#endif

        if (pkeyopts != NULL) {
            char *genopt;
            for (i = 0; i < sk_OPENSSL_STRING_num(pkeyopts); i++) {
                genopt = sk_OPENSSL_STRING_value(pkeyopts, i);
                if (pkey_ctrl_string(genctx, genopt) <= 0) {
                    BIO_printf(bio_err, "Key parameter error \"%s\"\n", genopt);
                    goto end;
                }
            }
        }

        EVP_PKEY_CTX_set_app_data(genctx, bio_err);
        if (progress)
            EVP_PKEY_CTX_set_cb(genctx, progress_cb);

        pkey = app_keygen(genctx, keyalgstr, newkey_len, verbose);
        if (pkey == NULL)
            goto end;

        EVP_PKEY_CTX_free(genctx);
        genctx = NULL;
    }
    if (keyout == NULL && keyfile == NULL)
        keyout = app_conf_try_string(req_conf, section, KEYFILE);

    if (pkey != NULL && (keyfile == NULL || keyout != NULL)) {
        if (verbose) {
            BIO_printf(bio_err, "Writing private key to ");
            if (keyout == NULL)
                BIO_printf(bio_err, "stdout\n");
            else
                BIO_printf(bio_err, "'%s'\n", keyout);
        }
        out = bio_open_owner(keyout, outformat, newreq);
        if (out == NULL)
            goto end;

        p = app_conf_try_string(req_conf, section, "encrypt_rsa_key");
        if (p == NULL)
            p = app_conf_try_string(req_conf, section, "encrypt_key");
        if (p != NULL && strcmp(p, "no") == 0)
            cipher = NULL;
        if (noenc)
            cipher = NULL;

        i = 0;
 loop:
        if (!PEM_write_bio_PrivateKey(out, pkey, cipher,
                                      NULL, 0, NULL, passout)) {
            if ((ERR_GET_REASON(ERR_peek_error()) ==
                 PEM_R_PROBLEMS_GETTING_PASSWORD) && (i < 3)) {
                ERR_clear_error();
                i++;
                goto loop;
            }
            goto end;
        }
        BIO_free_all(out);
        out = NULL;
        BIO_printf(bio_err, "-----\n");
    }

    /*
     * subj is expected to be in the format /type0=value0/type1=value1/type2=...
     * where characters may be escaped by \
     */
    if (subj != NULL
            && (fsubj = parse_name(subj, chtype, multirdn, "subject")) == NULL)
        goto end;

    if (!newreq) {
        if (keyfile != NULL)
            BIO_printf(bio_err,
                       "Warning: Not placing -key in cert or request since request is used\n");
        req = load_csr_autofmt(infile /* if NULL, reads from stdin */,
                               informat, vfyopts, "X509 request");
        if (req == NULL)
            goto end;
    } else if (infile != NULL) {
        BIO_printf(bio_err,
                   "Warning: Ignoring -in option since -new or -newkey or -precert is given\n");
        /* Better throw an error in this case, as done in the x509 app */
    }

    if (CAkeyfile == NULL)
        CAkeyfile = CAfile;
    if (CAkeyfile != NULL) {
        if (CAfile == NULL) {
            BIO_printf(bio_err,
                       "Warning: Ignoring -CAkey option since no -CA option is given\n");
        } else {
            if ((CAkey = load_key(CAkeyfile, FORMAT_UNDEF,
                                  0, passin, e,
                                  CAkeyfile != CAfile
                                  ? "issuer private key from -CAkey arg"
                                  : "issuer private key from -CA arg")) == NULL)
                goto end;
        }
    }
    if (CAfile != NULL) {
        if ((CAcert = load_cert_pass(CAfile, FORMAT_UNDEF, 1, passin,
                                     "issuer cert from -CA arg")) == NULL)
            goto end;
        if (!X509_check_private_key(CAcert, CAkey)) {
            BIO_printf(bio_err,
                       "Issuer CA certificate and key do not match\n");
            goto end;
        }
    }
    if (newreq || gen_x509) {
        if (CAcert == NULL && pkey == NULL) {
            BIO_printf(bio_err, "Must provide a signature key using -key or"
                " provide -CA / -CAkey\n");
            goto end;
        }

        if (req == NULL) {
            req = X509_REQ_new_ex(app_get0_libctx(), app_get0_propq());
            if (req == NULL) {
                goto end;
            }

            if (!make_REQ(req, pkey, fsubj, multirdn, !gen_x509, chtype)) {
                BIO_printf(bio_err, "Error making certificate request\n");
                goto end;
            }
            /* Note that -x509 can take over -key and -subj option values. */
        }
        if (gen_x509) {
            EVP_PKEY *pub_key = X509_REQ_get0_pubkey(req);
            EVP_PKEY *issuer_key = CAcert != NULL ? CAkey : pkey;
            X509V3_CTX ext_ctx;
            X509_NAME *issuer = CAcert != NULL ? X509_get_subject_name(CAcert) :
                X509_REQ_get_subject_name(req);
            X509_NAME *n_subj = fsubj != NULL ? fsubj :
                X509_REQ_get_subject_name(req);

            if (CAcert != NULL && keyfile != NULL)
                BIO_printf(bio_err,
                           "Warning: Not using -key or -newkey for signing since -CA option is given\n");

            if ((new_x509 = X509_new_ex(app_get0_libctx(),
                                        app_get0_propq())) == NULL)
                goto end;

            if (serial != NULL) {
                if (!X509_set_serialNumber(new_x509, serial))
                    goto end;
            } else {
                if (!rand_serial(NULL, X509_get_serialNumber(new_x509)))
                    goto end;
            }

            if (!X509_set_issuer_name(new_x509, issuer))
                goto end;
            if (days == UNSET_DAYS)
                days = DEFAULT_DAYS;
            else if (not_after != NULL)
                BIO_printf(bio_err,"Warning: -not_after option overriding -days option\n");
            if (!set_cert_times(new_x509, not_before, not_after, days, 1))
                goto end;
            if (!X509_set_subject_name(new_x509, n_subj))
                goto end;
            if (!pub_key || !X509_set_pubkey(new_x509, pub_key))
                goto end;
            if (ext_copy == EXT_COPY_UNSET) {
                if (infile != NULL)
                    BIO_printf(bio_err, "Warning: No -copy_extensions given; ignoring any extensions in the request\n");
            } else if (!copy_extensions(new_x509, req, ext_copy)) {
                BIO_printf(bio_err, "Error copying extensions from request\n");
                goto end;
            }

            /* Set up V3 context struct */
            X509V3_set_ctx(&ext_ctx, CAcert != NULL ? CAcert : new_x509,
                           new_x509, NULL, NULL, X509V3_CTX_REPLACE);
            /* prepare fallback for AKID, but only if issuer cert == new_x509 */
            if (CAcert == NULL) {
                if (!X509V3_set_issuer_pkey(&ext_ctx, issuer_key))
                    goto end;
                if (!cert_matches_key(new_x509, issuer_key))
                    BIO_printf(bio_err,
                               "Warning: Signature key and public key of cert do not match\n");
            }
            X509V3_set_nconf(&ext_ctx, req_conf);

            /* Add extensions */
            if (extsect != NULL
                && !X509V3_EXT_add_nconf(req_conf, &ext_ctx, extsect, new_x509)) {
                BIO_printf(bio_err, "Error adding x509 extensions from section %s\n",
                           extsect);
                goto end;
            }
            if (addext_conf != NULL
                && !X509V3_EXT_add_nconf(addext_conf, &ext_ctx, "default",
                                         new_x509)) {
                BIO_printf(bio_err, "Error adding x509 extensions defined via -addext\n");
                goto end;
            }

            /* If a pre-cert was requested, we need to add a poison extension */
            if (precert) {
                if (X509_add1_ext_i2d(new_x509, NID_ct_precert_poison,
                                      NULL, 1, 0) != 1) {
                    BIO_printf(bio_err, "Error adding poison extension\n");
                    goto end;
                }
            }

            i = do_X509_sign(new_x509, x509v1, issuer_key, digest, sigopts,
                             &ext_ctx);
            if (!i)
                goto end;
        } else {
            X509V3_CTX ext_ctx;

            if (precert) {
                BIO_printf(bio_err,
                           "Warning: Ignoring -precert flag since no cert is produced\n");
            }
            /* Set up V3 context struct */
            X509V3_set_ctx(&ext_ctx, NULL, NULL, req, NULL, X509V3_CTX_REPLACE);
            X509V3_set_nconf(&ext_ctx, req_conf);

            /* Add extensions */
            if (extsect != NULL
                && !X509V3_EXT_REQ_add_nconf(req_conf, &ext_ctx, extsect, req)) {
                BIO_printf(bio_err, "Error adding request extensions from section %s\n",
                           extsect);
                goto end;
            }
            if (addext_conf != NULL
                && !X509V3_EXT_REQ_add_nconf(addext_conf, &ext_ctx, "default",
                                             req)) {
                BIO_printf(bio_err, "Error adding request extensions defined via -addext\n");
                goto end;
            }
            i = do_X509_REQ_sign(req, pkey, digest, sigopts);
            if (!i)
                goto end;
        }
    }

    if (subj != NULL && !newreq && !gen_x509) {
        if (verbose) {
            BIO_printf(out, "Modifying subject of certificate request\n");
            print_name(out, "Old subject=", X509_REQ_get_subject_name(req));
        }

        if (!X509_REQ_set_subject_name(req, fsubj)) {
            BIO_printf(bio_err, "Error modifying subject of certificate request\n");
            goto end;
        }

        if (verbose) {
            print_name(out, "New subject=", X509_REQ_get_subject_name(req));
        }
    }

    if (verify) {
        EVP_PKEY *tpubkey = pkey;

        if (tpubkey == NULL) {
            tpubkey = X509_REQ_get0_pubkey(req);
            if (tpubkey == NULL)
                goto end;
        }

        i = do_X509_REQ_verify(req, tpubkey, vfyopts);

        if (i < 0)
            goto end;
        if (i == 0) {
            BIO_printf(bio_err, "Certificate request self-signature verify failure\n");
	    goto end;
        } else /* i > 0 */
            BIO_printf(bio_out, "Certificate request self-signature verify OK\n");
    }

    if (noout && !text && !modulus && !subject && !pubkey) {
        ret = 0;
        goto end;
    }

    out = bio_open_default(outfile,
                           keyout != NULL && outfile != NULL &&
                           strcmp(keyout, outfile) == 0 ? 'a' : 'w',
                           outformat);
    if (out == NULL)
        goto end;

    if (pubkey) {
        EVP_PKEY *tpubkey = X509_REQ_get0_pubkey(req);

        if (tpubkey == NULL) {
            BIO_printf(bio_err, "Error getting public key\n");
            goto end;
        }
        PEM_write_bio_PUBKEY(out, tpubkey);
    }

    if (text) {
        if (gen_x509)
            ret = X509_print_ex(out, new_x509, get_nameopt(), reqflag);
        else
            ret = X509_REQ_print_ex(out, req, get_nameopt(), reqflag);

        if (ret == 0) {
            if (gen_x509)
                BIO_printf(bio_err, "Error printing certificate\n");
            else
                BIO_printf(bio_err, "Error printing certificate request\n");
            goto end;
        }
    }

    if (subject) {
        print_name(out, "subject=", gen_x509
                   ? X509_get_subject_name(new_x509)
                   : X509_REQ_get_subject_name(req));
    }

    if (modulus) {
        EVP_PKEY *tpubkey;

        if (gen_x509)
            tpubkey = X509_get0_pubkey(new_x509);
        else
            tpubkey = X509_REQ_get0_pubkey(req);
        if (tpubkey == NULL) {
            BIO_puts(bio_err, "Modulus is unavailable\n");
            goto end;
        }
        BIO_puts(out, "Modulus=");
        if (EVP_PKEY_is_a(tpubkey, "RSA") || EVP_PKEY_is_a(tpubkey, "RSA-PSS")) {
            BIGNUM *n = NULL;

            if (!EVP_PKEY_get_bn_param(tpubkey, "n", &n))
                goto end;
            BN_print(out, n);
            BN_free(n);
        } else {
            BIO_puts(out, "Wrong Algorithm type");
        }
        BIO_puts(out, "\n");
    }

    if (!noout && !gen_x509) {
        if (outformat == FORMAT_ASN1)
            i = i2d_X509_REQ_bio(out, req);
        else if (newhdr)
            i = PEM_write_bio_X509_REQ_NEW(out, req);
        else
            i = PEM_write_bio_X509_REQ(out, req);
        if (!i) {
            BIO_printf(bio_err, "Unable to write certificate request\n");
            goto end;
        }
    }
    if (!noout && gen_x509 && new_x509 != NULL) {
        if (outformat == FORMAT_ASN1)
            i = i2d_X509_bio(out, new_x509);
        else
            i = PEM_write_bio_X509(out, new_x509);
        if (!i) {
            BIO_printf(bio_err, "Unable to write X509 certificate\n");
            goto end;
        }
    }
    ret = 0;
 end:
    if (ret) {
        ERR_print_errors(bio_err);
    }
    NCONF_free(req_conf);
    NCONF_free(addext_conf);
    BIO_free(addext_bio);
    BIO_free_all(out);
    EVP_PKEY_free(pkey);
    EVP_PKEY_CTX_free(genctx);
    sk_OPENSSL_STRING_free(pkeyopts);
    sk_OPENSSL_STRING_free(sigopts);
    sk_OPENSSL_STRING_free(vfyopts);
    lh_OPENSSL_STRING_doall(addexts, exts_cleanup);
    lh_OPENSSL_STRING_free(addexts);
#ifndef OPENSSL_NO_ENGINE
    release_engine(gen_eng);
#endif
    OPENSSL_free(keyalgstr);
    X509_REQ_free(req);
    X509_NAME_free(fsubj);
    X509_free(new_x509);
    X509_free(CAcert);
    EVP_PKEY_free(CAkey);
    ASN1_INTEGER_free(serial);
    release_engine(e);
    if (passin != nofree_passin)
        OPENSSL_free(passin);
    if (passout != nofree_passout)
        OPENSSL_free(passout);
    return ret;
}