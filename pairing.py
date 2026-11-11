"""Strict parser for RoutePou QR pairing URIs."""
from ipaddress import ip_address, IPv4Address, ip_network
from urllib.parse import urlparse, parse_qs

from i18n import t

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


def local_ip_towards(host: str):
    """The address this PC would use to reach `host` (nothing is sent), or None when the PC has no route to it."""
    import socket
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect((host, 9))
        return probe.getsockname()[0]
    except OSError:
        return None
    finally:
        probe.close()


def _same_network(a: str, b: str) -> bool:
    """Home networks and phone hotspots are /24 networks, so the first three numbers must match."""
    return a.split(".")[:3] == b.split(".")[:3]


def network_hint(host) -> str:
    """One extra line for a timeout: compares this PC's address with the phone's. Empty when nothing useful can be said."""
    import ipaddress
    try:
        if not host or not ipaddress.ip_address(host).is_private:
            return ""
    except ValueError:
        return ""
    mine = local_ip_towards(host)
    if mine is None:
        return t("این کامپیوتر الان به هیچ شبکه‌ای وصل نیست؛ آن را به وای‌فای یا هات‌اسپات گوشی وصل کنید.",
                 "This PC is not connected to any network right now. Connect it to the Wi-Fi or to the phone's hotspot.")
    if not _same_network(mine, host):
        return t(f"آدرس این کامپیوتر {mine} و آدرس گوشی {host} است؛ در یک شبکه نیستند. "
                 "ویندوز را به همان وای‌فایِ گوشی (یا به هات‌اسپات گوشی) وصل کنید.",
                 f"This PC is {mine} and the phone is {host}: they are not on the same network. "
                 "Connect the PC to the phone's Wi-Fi (or to the phone's hotspot).")
    return t(f"هر دو در یک شبکه‌اند ({mine} و {host})، پس مشکل احتمالاً AP isolation روتر یا فایروال ویندوز است.",
             f"Both are on the same network ({mine} and {host}), so the likely cause is the router's AP isolation or the Windows Firewall.")


def describe_connect_error(exc: BaseException, host=None) -> str:
    """Turn a low-level socket error into advice the user can act on (in the app's language, raw reason kept)."""
    import socket
    import ssl
    raw = str(exc).strip() or exc.__class__.__name__
    if isinstance(exc, ssl.SSLError) or "fingerprint" in raw.lower() or "certificate" in raw.lower():
        advice = t("گواهی گوشی با QR نمی‌خواند. در برنامهٔ اندروید «ساخت کلید جفت‌سازی جدید» را بزنید "
                   "و QR تازه را اسکن کنید.",
                   "The phone's certificate does not match the QR. In the Android app tap \"Create a new pairing key\" "
                   "and scan the fresh QR.")
    elif isinstance(exc, (socket.timeout, TimeoutError, ConnectionRefusedError)) or \
            getattr(exc, "winerror", None) in (10060, 10061, 10051, 10065) or getattr(exc, "errno", None) in (110, 111, 113, 101, 10060, 10061):
        advice = t("به گوشی نرسیدم. بررسی کنید: ۱) گوشی و ویندوز به یک وای‌فای وصل باشند (یا ویندوز به هات‌اسپات گوشی)؛ "
                   "۲) در برنامهٔ اندروید «شروع اشتراک‌گذاری» زده شده باشد؛ "
                   "۳) روتر «جداسازی کلاینت‌ها / AP isolation» را خاموش داشته باشد؛ "
                   "۴) فایروال ویندوز RoutePou را مسدود نکرده باشد.",
                   "Could not reach the phone. Check: 1) the phone and the PC are on the same Wi-Fi (or the PC is on the phone's hotspot); "
                   "2) \"Start sharing\" was tapped in the Android app; "
                   "3) the router's \"client isolation / AP isolation\" is off; "
                   "4) Windows Firewall is not blocking RoutePou.")
        extra = network_hint(host)
        if extra:
            advice = extra + "\n\n" + advice
    else:
        advice = t("اتصال به گوشی برقرار نشد. QR تازه بگیرید و دوباره امتحان کنید.",
                   "Could not connect to the phone. Get a fresh QR and try again.")
    return advice + "\n\n(" + raw + ")"
