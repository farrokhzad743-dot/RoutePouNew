import pytest
from pairing import parse_pairing_payload

def payload(host="192.168.43.1"):
    return f"routepou://pair?host={host}&port=8788&key={'a'*64}&fp={'B'*64}"

def test_valid_pairing_uri():
    assert parse_pairing_payload(payload()) == ("192.168.43.1", "8788", "a"*64, "B"*64)

@pytest.mark.parametrize("host", ["8.8.8.8", "172.15.1.2", "172.32.1.2", "localhost", "192.168.1"])
def test_rejects_non_private_or_malformed_host(host):
    with pytest.raises(ValueError):
        parse_pairing_payload(payload(host))

def test_rejects_invalid_scheme():
    with pytest.raises(ValueError):
        parse_pairing_payload("https://pair?host=192.168.43.1")

def test_rejects_duplicate_parameters():
    with pytest.raises(ValueError):
        parse_pairing_payload(payload() + "&key=" + "b"*64)
