"""Strict parser for RoutePou QR pairing URIs."""
from ipaddress import ip_address, IPv4Address, ip_network
from urllib.parse import urlparse, parse_qs

def parse_pairing_payload(payload: str):
    parsed = urlparse(payload.strip())
    if parsed.scheme != "routepou" or parsed.netloc != "pair" or parsed.fragment:
        raise ValueError("This is not a RoutePou pairing QR payload.")
    try:
        values = parse_qs(parsed.query, strict_parsing=True)
    except ValueError as exc:
        raise ValueError("Malformed pairing QR payload.") from exc
    required = {"host", "port", "key", "fp"}
    if set(values) != required or any(len(v) != 1 for v in values.values()):
        raise ValueError("Pairing QR must contain exactly one host, port, key, and fp value.")
    host, port, token, fingerprint = (values[k][0] for k in ("host", "port", "key", "fp"))
    try:
        address = ip_address(host)
    except ValueError as exc:
        raise ValueError("Pairing host must be a private IPv4 address (the phone's address on your Wi-Fi or hotspot).") from exc
    if not isinstance(address, IPv4Address) or not any(address in net for net in (ip_network("10.0.0.0/8"), ip_network("172.16.0.0/12"), ip_network("192.168.0.0/16"))):
        raise ValueError("Pairing host must be a private IPv4 address (the phone's address on your Wi-Fi or hotspot).")
    if not port.isdigit() or not 1 <= int(port) <= 65535:
        raise ValueError("Invalid pairing port.")
    if len(token) != 64 or any(c not in "0123456789abcdefABCDEF" for c in token):
        raise ValueError("Invalid pairing key.")
    clean_fp = "".join(c for c in fingerprint.upper() if c in "0123456789ABCDEF")
    if len(clean_fp) != 64:
        raise ValueError("Invalid TLS certificate fingerprint.")
    return str(address), str(int(port)), token.lower(), clean_fp


def describe_connect_error(exc: BaseException) -> str:
    """Turn a low-level socket error into advice the user can act on (Persian, with the raw reason kept)."""
    import socket
    import ssl
    raw = str(exc).strip() or exc.__class__.__name__
    if isinstance(exc, ssl.SSLError) or "fingerprint" in raw.lower() or "certificate" in raw.lower():
        advice = ("گواهی گوشی با QR نمی‌خواند. در برنامهٔ اندروید «ساخت کلید جفت‌سازی جدید» را بزنید "
                  "و QR تازه را اسکن کنید.")
    elif isinstance(exc, (socket.timeout, TimeoutError, ConnectionRefusedError)) or \
            getattr(exc, "winerror", None) in (10060, 10061, 10051, 10065) or getattr(exc, "errno", None) in (110, 111, 113, 101, 10060, 10061):
        advice = ("به گوشی نرسیدم. بررسی کنید: ۱) گوشی و ویندوز به یک وای‌فای وصل باشند (یا ویندوز به هات‌اسپات گوشی)؛ "
                  "۲) در برنامهٔ اندروید «شروع اشتراک‌گذاری» زده شده باشد؛ "
                  "۳) روتر «جداسازی کلاینت‌ها / AP isolation» را خاموش داشته باشد؛ "
                  "۴) فایروال ویندوز RoutePou را مسدود نکرده باشد.")
    else:
        advice = "اتصال به گوشی برقرار نشد. QR تازه بگیرید و دوباره امتحان کنید."
    return advice + "\n\n(" + raw + ")"
