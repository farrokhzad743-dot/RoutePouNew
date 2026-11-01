"""The phone (Kotlin) and the Go engine must agree on the WireGuard configuration dialect."""
import base64
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VECTOR = json.loads((ROOT / "test-vectors.json").read_text(encoding="utf-8"))["wgServerConfig"]


def hexkey(b64: str) -> str:
    raw = base64.b64decode(b64, validate=True)
    assert len(raw) == 32
    return raw.hex()


def kotlin_server_ipc(keys: dict, port: int) -> str:
    """Python twin of RoutePouWgConfig.serverIpc (checked against the Kotlin source below)."""
    return (f"private_key={hexkey(keys['serverPrivateKey'])}\n"
            f"listen_port={port}\n"
            f"public_key={hexkey(keys['clientPublicKey'])}\n"
            f"allowed_ip=10.13.37.2/32\n")


def test_vector_matches_what_the_phone_generates():
    assert kotlin_server_ipc(VECTOR["keys"], VECTOR["endpointPort"]) == VECTOR["ipc"]


def test_kotlin_source_still_produces_that_shape():
    src = (ROOT / "RoutePouWgConfig.kt").read_text(encoding="utf-8")
    for fragment in ('"private_key=${toHex(keys.serverPrivateKey)}\\n"', '"listen_port=$port\\n"',
                     '"public_key=${toHex(keys.clientPublicKey)}\\n"', '"allowed_ip=$CLIENT_TUNNEL_IP/32\\n"'):
        assert fragment in src, fragment
    assert 'SERVER_TUNNEL_IP = "10.13.37.1"' in src and 'CLIENT_TUNNEL_IP = "10.13.37.2"' in src
    assert "MTU = 1420" in src and "DEFAULT_PORT = 51820" in src


def test_go_engine_uses_the_same_addresses():
    go = (ROOT / "relaywg.go").read_text(encoding="utf-8")
    assert '"10.13.37.1"' in go
    assert VECTOR["serverTunnelIp"] == "10.13.37.1" and VECTOR["clientTunnelIp"] == "10.13.37.2"
    client = (ROOT / "winclient/main.go").read_text(encoding="utf-8")
    assert "1420" in client
    supervisor = (ROOT / "wg_supervisor.py").read_text(encoding="utf-8")
    assert "-address 10.13.37.2/32" in supervisor and "-routes 0.0.0.0/0" in supervisor


def test_qr_payload_contract():
    payload = (ROOT / "RoutePouPairingPayload.kt").read_text(encoding="utf-8")
    assert 'routepou://p/' in payload and "TTL_SECONDS = 300L" in payload
    provision = (ROOT / "wg_provision.py").read_text(encoding="utf-8")
    assert "PAIRING_TTL_SECONDS = 300" in provision and "routepou://p/" in provision
    assert re.search(r'"v",\s*1\)', payload) and 'root.optInt("v") == 1' in payload


def test_go_contract_test_reads_the_file_that_exists():
    go = (ROOT / "contract_test.go").read_text(encoding="utf-8")
    assert 'filepath.Join("test-vectors.json")' in go
    assert (ROOT / "test-vectors.json").is_file()
