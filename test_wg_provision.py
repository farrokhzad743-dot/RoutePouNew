import base64, json, unittest, time
from wg_provision import parse_qr_to_windows_ipc, ProvisioningError

def key(byte): return base64.b64encode(bytes([byte])*32).decode()
def qr(obj): return "routepou://p/" + base64.urlsafe_b64encode(json.dumps(obj).encode()).decode().rstrip("=")

class ProvisionTests(unittest.TestCase):
    def setUp(self):
        self.obj={"v":1,"mode":"wireguard","host":"192.168.43.1","port":51820,"issuedAt":int(time.time()),
                  "wg":{"serverPublicKey":key(1),"clientPrivateKey":key(2),
                        "allowedIps":"0.0.0.0/0","endpointPort":51820,"dns":"1.1.1.1"}}
    def test_valid_payload_builds_memory_ipc(self):
        ipc, meta=parse_qr_to_windows_ipc(qr(self.obj))
        self.assertIn("private_key="+ (bytes([2])*32).hex(), ipc)
        self.assertIn("endpoint=192.168.43.1:51820", ipc)
        self.assertEqual(meta["dns"], "1.1.1.1")
    def test_reject_public_host(self):
        self.obj["host"]="8.8.8.8"
        with self.assertRaises(ProvisioningError): parse_qr_to_windows_ipc(qr(self.obj))
    def test_reject_wrong_allowed_ips(self):
        self.obj["wg"]["allowedIps"]="10.0.0.0/8"
        with self.assertRaises(ProvisioningError): parse_qr_to_windows_ipc(qr(self.obj))
    def test_reject_wrong_scheme(self):
        with self.assertRaises(ProvisioningError): parse_qr_to_windows_ipc("https://example.com")

    def test_reject_expired_qr(self):
        self.obj["issuedAt"] = int(time.time()) - 301
        with self.assertRaisesRegex(ProvisioningError, "expired"):
            parse_qr_to_windows_ipc(qr(self.obj))

    def test_reject_future_qr(self):
        self.obj["issuedAt"] = int(time.time()) + 61
        with self.assertRaisesRegex(ProvisioningError, "future"):
            parse_qr_to_windows_ipc(qr(self.obj))

    def test_reject_loopback_host(self):
        self.obj["host"] = "127.0.0.1"
        with self.assertRaises(ProvisioningError):
            parse_qr_to_windows_ipc(qr(self.obj))

    def test_reject_bad_key(self):
        self.obj["wg"]["clientPrivateKey"]="bad"
        with self.assertRaises(ProvisioningError): parse_qr_to_windows_ipc(qr(self.obj))

if __name__ == '__main__': unittest.main()
