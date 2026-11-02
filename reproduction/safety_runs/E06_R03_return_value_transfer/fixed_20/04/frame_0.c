int ossl_quic_tls_is_cert_request(QUIC_TLS *qtls)
{
    SSL_CONNECTION *sc = SSL_CONNECTION_FROM_SSL(qtls->args.s);

    return sc->s3.tmp.message_type == SSL3_MT_CERTIFICATE_REQUEST;
}