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
        raise ValueError("Pairing host must be a private IPv4 hotspot address.") from exc
    if not isinstance(address, IPv4Address) or not any(address in net for net in (ip_network("10.0.0.0/8"), ip_network("172.16.0.0/12"), ip_network("192.168.0.0/16"))):
        raise ValueError("Pairing host must be a private IPv4 hotspot address.")
    if not port.isdigit() or not 1 <= int(port) <= 65535:
        raise ValueError("Invalid pairing port.")
    if len(token) != 64 or any(c not in "0123456789abcdefABCDEF" for c in token):
        raise ValueError("Invalid pairing key.")
    clean_fp = "".join(c for c in fingerprint.upper() if c in "0123456789ABCDEF")
    if len(clean_fp) != 64:
        raise ValueError("Invalid TLS certificate fingerprint.")
    return str(address), str(int(port)), token.lower(), clean_fp
