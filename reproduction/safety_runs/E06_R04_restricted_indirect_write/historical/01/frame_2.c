int OCSP_BASICRESP_add_ext(OCSP_BASICRESP *x, X509_EXTENSION *ex, int loc)
{
    return (X509v3_add_ext(&(x->tbsResponseData.responseExtensions), ex, loc)
            != NULL);
}