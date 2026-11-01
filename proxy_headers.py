"""Request-head rewriting for the Windows -> phone proxy bridge (pure functions, unit-tested)."""


def rewrite_request_head(head: bytes, token: str) -> bytes:
    """Adds the phone access token and, for plain-HTTP requests, forces `Connection: close`.

    The phone connects to the origin named by the *first* request on a connection. If a browser
    reused one proxy connection for requests to different hosts, later requests would reach the
    wrong server, so plain-HTTP connections are closed after each response. CONNECT tunnels
    (HTTPS) are unaffected.
    """
    lines = head.split(b"\r\n")
    request_line, headers = lines[0], lines[1:]
    is_connect = request_line.split(b" ", 1)[0].upper() == b"CONNECT"
    drop = {b"x-routepou-key"}
    if not is_connect:
        drop |= {b"connection", b"proxy-connection"}
    kept = [h for h in headers if h.split(b":", 1)[0].strip().lower() not in drop]
    kept.append(b"X-RoutePou-Key: " + token.encode("ascii"))
    if not is_connect:
        kept.append(b"Connection: close")
    return b"\r\n".join([request_line] + kept)
