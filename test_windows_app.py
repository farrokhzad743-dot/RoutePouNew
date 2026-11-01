"""Static checks for the Windows app (it needs a display and winreg, so it is not imported)."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_all_python_sources_parse():
    for name in ("routepou_windows.py", "pairing.py", "wg_provision.py", "wg_supervisor.py", "proxy_headers.py"):
        ast.parse(read(name), filename=name)


def test_windows_app_wiring():
    source = read("routepou_windows.py")
    assert 'payload.startswith("routepou://p/")' in source       # full-tunnel QR
    assert "parse_qr_to_windows_ipc" in source
    assert "parse_pairing_payload" in source                      # proxy QR
    assert "def scan_qr_camera" in source and "def scan_qr_image" in source
    assert "connect_full_tunnel" in source and "disconnect_full_tunnel" in source
    assert 'line == "PEER-LOST"' in source and 'line == "PEER-BACK"' in source
    assert "relaywg-client.exe" in source
    assert "_restore_proxy_on_exit" in source                     # never strand the system proxy


def test_certificate_is_pinned():
    source = read("routepou_windows.py")
    assert "hashlib.sha256(wrapped.getpeercert(binary_form=True))" in source
    assert "hmac.compare_digest" in source
    assert "certificate fingerprint mismatch" in source


def test_supervisor_keeps_keys_in_memory():
    source = read("wg_supervisor.py")
    assert "CreateNamedPipeW" in source and "END-CONFIG" in source
    assert 'line == "READY"' in source and "ShellExecuteW" in source
    assert "-hold-on-loss=true" in source and "-block-leaks=true" in source
    assert "write_text" not in source and "open(" not in source


def test_worker_reports_peer_events_and_fails_closed():
    worker = read("winclient/main.go")
    assert 'peerLostLine = "PEER-LOST"' in worker and 'peerBackLine = "PEER-BACK"' in worker
    assert "refusing full tunnel because leak protection could not be installed" in worker
