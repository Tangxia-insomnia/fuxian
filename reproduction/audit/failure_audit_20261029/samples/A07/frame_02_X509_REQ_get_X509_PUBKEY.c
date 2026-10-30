X509_PUBKEY *X509_REQ_get_X509_PUBKEY(X509_REQ *req)
{
    return req->req_info.pubkey;
}