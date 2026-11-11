# Third-party notices

RoutePou is distributed under the GNU GPL v3 (see `LICENSE`) because it incorporates GPL-3.0 code from the Relay project. Components and their licenses:

| Component | Used for | License |
|---|---|---|
| Relay WireGuard forwarder, the upstream project the Go sources in the repository root and `winclient/` are derived from — https://github.com/Mahdi-mortazavi/relay | Phone-side WireGuard endpoint (gomobile AAR) and Windows tunnel worker | GPL-3.0 (`LICENSE`) |
| wireguard-go (golang.zx2c4.com/wireguard) | WireGuard protocol | MIT |
| wireguard-windows (golang.zx2c4.com/wireguard/windows) | Windows adapter/route helpers | MIT |
| gVisor netstack | Userspace TCP/UDP forwarding | Apache-2.0 |
| golang.org/x/* | Go support libraries | BSD-3-Clause |
| BouncyCastle `bcprov-jdk18on` | X25519 key generation on Android | MIT (Bouncy Castle License) |
| ZXing core (com.google.zxing:core) | QR generation on Android | Apache-2.0 |
| Vazirmatn font (Persian and Latin text on the website and in the images; the website uses a reduced copy of the Regular and Bold weights containing only the characters it needs) — https://github.com/rastikerdar/vazirmatn | Typography | SIL OFL 1.1 (`FONT_LICENSES.txt`) |
| zxing-cpp, OpenCV (opencv-python), Pillow | QR decoding on Windows | Apache-2.0 / Apache-2.0 / HPND |
| PyInstaller | Packaging `RoutePou.exe` | GPL-2.0 with bootloader exception |
| Wintun (wintun.dll, downloaded from https://www.wintun.net during the build) | Windows virtual network adapter | Wintun prebuilt-binaries license (https://www.wintun.net/) |

"WireGuard" is a registered trademark of Jason A. Donenfeld. RoutePou is not affiliated with or endorsed by the WireGuard project.

Corresponding source for every released binary is this repository at the tagged commit. Do not remove upstream copyright notices.
