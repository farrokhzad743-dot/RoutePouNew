"""The phone must put an address in the QR that the PC can reach (Wi-Fi or hotspot), never a VPN's or the mobile network's."""
import re
import socket
import ssl
from pathlib import Path

from pairing import describe_connect_error, parse_pairing_payload

ROOT = Path(__file__).resolve().parent
ACTIVITY = (ROOT / "MainActivity.kt").read_text(encoding="utf-8")


def function_body(name: str) -> str:
    start = ACTIVITY.index(f"private fun {name}(")
    nxt = ACTIVITY.find("\n    private fun ", start + 10)
    nxt = nxt if nxt != -1 else ACTIVITY.find("\n    override fun", start)
    return ACTIVITY[start:nxt]


def test_android_skips_vpn_cellular_and_point_to_point_interfaces():
    body = function_body("lanIpv4") + function_body("interfaceRank")
    assert "isPointToPoint" in body and "isLoopback" in body and "isUp" in body
    for virtual in ('"tun"', '"rmnet"', '"ccmni"', '"ppp"', '"dummy"'):
        assert f"startsWith({virtual})" in body, virtual
    for real in ('"wlan"', '"ap"', '"swlan"', '"rndis"', '"eth"'):
        assert f"startsWith({real})" in body, real
    assert "isSiteLocalAddress" in body
    assert "hotspotIpv4" not in ACTIVITY and "catch (_:" not in ACTIVITY


def test_every_user_facing_hint_works_without_a_hotspot():
    assert "هات‌اسپات لازم نیست" in ACTIVITY
    assert "وای‌فای" in function_body("refreshNetworkInfo")
    windows = (ROOT / "routepou_windows.py").read_text(encoding="utf-8")
    assert 'tk.StringVar(value="192.168.43.1")' not in windows
    assert "describe_connect_error" in windows


def test_qr_host_accepts_any_private_lan_address():
    for host in ("192.168.1.23", "10.0.0.5", "172.20.10.1", "192.168.43.1"):
        uri = f"routepou://pair?host={host}&port=8788&key={'a'*64}&fp={'B'*64}"
        assert parse_pairing_payload(uri)[0] == host


def test_connect_errors_explain_what_to_check():
    network = describe_connect_error(socket.timeout("timed out"))
    assert "یک وای‌فای" in network and "AP isolation" in network and "timed out" in network
    assert "وای‌فای" in describe_connect_error(ConnectionRefusedError(111, "refused"))
    refused_win = OSError(); refused_win.winerror = 10060
    assert "AP isolation" in describe_connect_error(refused_win)
    assert "کلید جفت‌سازی جدید" in describe_connect_error(ssl.SSLError("certificate verify failed"))
    assert "QR تازه" in describe_connect_error(ValueError("something else"))
