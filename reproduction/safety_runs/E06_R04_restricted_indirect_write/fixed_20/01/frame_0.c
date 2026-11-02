static void make_ocsp_response(BIO *err, OCSP_RESPONSE **resp, OCSP_REQUEST *req,
                              CA_DB *db, STACK_OF(X509) *ca, X509 *rcert,
                              EVP_PKEY *rkey, const EVP_MD *rmd,
                              STACK_OF(OPENSSL_STRING) *sigopts,
                              STACK_OF(X509) *rother, unsigned long flags,
                              int nmin, int ndays, int badsig,
                              const EVP_MD *resp_md)
{
    ASN1_TIME *thisupd = NULL, *nextupd = NULL;
    OCSP_CERTID *cid;
    OCSP_BASICRESP *bs = NULL;
    int i, id_count;
    EVP_MD_CTX *mctx = NULL;
    EVP_PKEY_CTX *pkctx = NULL;

    id_count = OCSP_request_onereq_count(req);

    if (id_count <= 0) {
        *resp =
            OCSP_response_create(OCSP_RESPONSE_STATUS_MALFORMEDREQUEST, NULL);
        goto end;
    }

    bs = OCSP_BASICRESP_new();
    thisupd = X509_gmtime_adj(NULL, 0);
    if (ndays != -1)
        nextupd = X509_time_adj_ex(NULL, ndays, nmin * 60, NULL);

    /* Examine each certificate id in the request */
    for (i = 0; i < id_count; i++) {
        OCSP_ONEREQ *one;
        ASN1_INTEGER *serial;
        char **inf;
        int jj;
        int found = 0;
        ASN1_OBJECT *cert_id_md_oid;
        const EVP_MD *cert_id_md;
        OCSP_CERTID *cid_resp_md = NULL;

        one = OCSP_request_onereq_get0(req, i);
        cid = OCSP_onereq_get0_id(one);

        OCSP_id_get0_info(NULL, &cert_id_md_oid, NULL, NULL, cid);

        cert_id_md = EVP_get_digestbyobj(cert_id_md_oid);
        if (cert_id_md == NULL) {
            *resp = OCSP_response_create(OCSP_RESPONSE_STATUS_INTERNALERROR,
                                         NULL);
            goto end;
        }
        for (jj = 0; jj < sk_X509_num(ca) && !found; jj++) {
            X509 *ca_cert = sk_X509_value(ca, jj);
            OCSP_CERTID *ca_id = OCSP_cert_to_id(cert_id_md, NULL, ca_cert);

            if (OCSP_id_issuer_cmp(ca_id, cid) == 0) {
                found = 1;
                if (resp_md != NULL)
                    cid_resp_md = OCSP_cert_to_id(resp_md, NULL, ca_cert);
            }
            OCSP_CERTID_free(ca_id);
        }
        OCSP_id_get0_info(NULL, NULL, NULL, &serial, cid);
        inf = lookup_serial(db, serial);

        /* at this point, we can have cid be an alias of cid_resp_md */
        cid = (cid_resp_md != NULL) ? cid_resp_md : cid;

        if (!found) {
            OCSP_basic_add1_status(bs, cid,
                                   V_OCSP_CERTSTATUS_UNKNOWN,
                                   0, NULL, thisupd, nextupd);
            continue;
        }
        if (inf == NULL) {
            OCSP_basic_add1_status(bs, cid,
                                   V_OCSP_CERTSTATUS_UNKNOWN,
                                   0, NULL, thisupd, nextupd);
        } else if (inf[DB_type][0] == DB_TYPE_VAL) {
            OCSP_basic_add1_status(bs, cid,
                                   V_OCSP_CERTSTATUS_GOOD,
                                   0, NULL, thisupd, nextupd);
        } else if (inf[DB_type][0] == DB_TYPE_REV) {
            ASN1_OBJECT *inst = NULL;
            ASN1_TIME *revtm = NULL;
            ASN1_GENERALIZEDTIME *invtm = NULL;
            OCSP_SINGLERESP *single;
            int reason = -1;

            unpack_revinfo(&revtm, &reason, &inst, &invtm, inf[DB_rev_date]);
            single = OCSP_basic_add1_status(bs, cid,
                                            V_OCSP_CERTSTATUS_REVOKED,
                                            reason, revtm, thisupd, nextupd);
            if (single == NULL) {
                *resp = OCSP_response_create(OCSP_RESPONSE_STATUS_INTERNALERROR,
                                             NULL);
                goto end;
            }
            if (invtm != NULL)
                OCSP_SINGLERESP_add1_ext_i2d(single, NID_invalidity_date,
                                             invtm, 0, 0);
            else if (inst != NULL)
                OCSP_SINGLERESP_add1_ext_i2d(single,
                                             NID_hold_instruction_code, inst,
                                             0, 0);
            ASN1_OBJECT_free(inst);
            ASN1_TIME_free(revtm);
            ASN1_GENERALIZEDTIME_free(invtm);
        }
        OCSP_CERTID_free(cid_resp_md);
    }

    OCSP_copy_nonce(bs, req);

    mctx = EVP_MD_CTX_new();
    if (mctx == NULL || !EVP_DigestSignInit(mctx, &pkctx, rmd, NULL, rkey)) {
        *resp = OCSP_response_create(OCSP_RESPONSE_STATUS_INTERNALERROR, NULL);
        goto end;
    }
    for (i = 0; i < sk_OPENSSL_STRING_num(sigopts); i++) {
        char *sigopt = sk_OPENSSL_STRING_value(sigopts, i);

        if (pkey_ctrl_string(pkctx, sigopt) <= 0) {
            BIO_printf(err, "parameter error \"%s\"\n", sigopt);
            ERR_print_errors(bio_err);
            *resp = OCSP_response_create(OCSP_RESPONSE_STATUS_INTERNALERROR,
                                         NULL);
            goto end;
        }
    }
    if (!OCSP_basic_sign_ctx(bs, rcert, mctx, rother, flags)) {
        *resp = OCSP_response_create(OCSP_RESPONSE_STATUS_INTERNALERROR, bs);
        goto end;
    }

    if (badsig) {
        const ASN1_OCTET_STRING *sig = OCSP_resp_get0_signature(bs);
        corrupt_signature(sig);
    }

    *resp = OCSP_response_create(OCSP_RESPONSE_STATUS_SUCCESSFUL, bs);

 end:
    EVP_MD_CTX_free(mctx);
    ASN1_TIME_free(thisupd);
    ASN1_TIME_free(nextupd);
    OCSP_BASICRESP_free(bs);
}