"""Convert a RoutePou v1 QR payload into wireguard-go IPC text in memory.

The returned string contains a private key. Callers must pass it directly to the
Windows worker's authenticated named pipe and must never log or persist it.
"""
from __future__ import annotations
import base64, binascii, ipaddress, json, re, time

_KEY = re.compile(r"^[A-Za-z0-9+/]{43}=$")
PAIRING_TTL_SECONDS = 300
CLOCK_SKEW_SECONDS = 60

class ProvisioningError(ValueError):
    pass

def _key(value: object, label: str) -> str:
    if not isinstance(value, str) or not _KEY.fullmatch(value):
        raise ProvisioningError(f"Invalid {label}")
    try:
        if len(base64.b64decode(value, validate=True)) != 32:
            raise ProvisioningError(f"Invalid {label} length")
    except (binascii.Error, ValueError) as exc:
        raise ProvisioningError(f"Invalid {label}") from exc
    return value

def parse_qr_to_windows_ipc(payload: str) -> tuple[str, dict]:
    if not isinstance(payload, str) or not payload.startswith("routepou://p/"):
        raise ProvisioningError("Unsupported RoutePou QR scheme")
    encoded = payload[len("routepou://p/"):]
    if not encoded or len(encoded) > 4096 or not re.fullmatch(r"[A-Za-z0-9_-]+", encoded):
        raise ProvisioningError("Invalid QR payload encoding")
    try:
        raw = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
        obj = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProvisioningError("Malformed QR payload") from exc
    if not isinstance(obj, dict) or obj.get("v") != 1 or obj.get("mode") != "wireguard":
        raise ProvisioningError("Unsupported RoutePou pairing version")
    try:
        host = ipaddress.ip_address(obj["host"])
        port = int(obj["port"])
        issued_at = int(obj["issuedAt"])
        wg = obj["wg"]
        server_pub = _key(wg["serverPublicKey"], "server public key")
        client_priv = _key(wg["clientPrivateKey"], "client private key")
        dns = ipaddress.ip_address(wg.get("dns", "1.1.1.1"))
    except (KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, ProvisioningError):
            raise
        raise ProvisioningError("Invalid pairing fields") from exc
    if not isinstance(host, ipaddress.IPv4Address) or not host.is_private or host.is_loopback or host.is_link_local or host.is_multicast:
        raise ProvisioningError("Pairing host must be a usable private IPv4 address")
    now = int(time.time())
    if issued_at > now + CLOCK_SKEW_SECONDS:
        raise ProvisioningError("Pairing QR was issued in the future")
    if now - issued_at > PAIRING_TTL_SECONDS:
        raise ProvisioningError("Pairing QR has expired; generate a new QR on the phone")
    if not 1 <= port <= 65535 or wg.get("endpointPort") != port:
        raise ProvisioningError("Invalid endpoint port")
    if wg.get("allowedIps") != "0.0.0.0/0":
        raise ProvisioningError("Unexpected AllowedIPs policy")
    # Windows worker reads wireguard-go IPC on its named pipe. No file is created.
    ipc = (f"private_key={_b64_to_hex(client_priv)}\n"
           f"public_key={_b64_to_hex(server_pub)}\n"
           f"endpoint={host}:{port}\n"
           "allowed_ip=0.0.0.0/0\n"
           "persistent_keepalive_interval=25\n")
    return ipc, {"host": str(host), "port": port, "dns": str(dns)}

def _b64_to_hex(value: str) -> str:
    return base64.b64decode(value, validate=True).hex()
