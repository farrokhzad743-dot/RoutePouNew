from proxy_headers import rewrite_request_head

TOKEN = "a" * 64


def head(*lines):
    return b"\r\n".join(lines)


def test_plain_http_gets_token_and_connection_close():
    out = rewrite_request_head(head(b"GET http://example.com/ HTTP/1.1", b"Host: example.com",
                                    b"Proxy-Connection: keep-alive", b"Connection: keep-alive"), TOKEN)
    lines = out.split(b"\r\n")
    assert lines[0] == b"GET http://example.com/ HTTP/1.1"
    assert b"X-RoutePou-Key: " + TOKEN.encode() in lines
    assert lines.count(b"Connection: close") == 1
    assert not any(l.lower().startswith((b"proxy-connection", b"connection: keep")) for l in lines)


def test_client_supplied_token_header_is_replaced():
    out = rewrite_request_head(head(b"GET http://e.com/ HTTP/1.1", b"x-routepou-key: evil"), TOKEN)
    assert out.lower().count(b"x-routepou-key") == 1 and b"evil" not in out


def test_connect_tunnels_are_not_forced_to_close():
    out = rewrite_request_head(head(b"CONNECT example.com:443 HTTP/1.1", b"Host: example.com:443",
                                    b"Proxy-Connection: keep-alive"), TOKEN)
    assert b"Connection: close" not in out
    assert b"Proxy-Connection: keep-alive" in out and b"X-RoutePou-Key" in out
