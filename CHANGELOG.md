# Changelog

## 0.27.0-beta — Clean rebuild
The project was rebuilt as a flat repository with a single Go module and a single workflow.

### Fixed (build-breaking)
- Windows CI: the worker's tests imported the engine from a GitHub path that `go.mod` never declared, so `go mod tidy` fetched foreign code or failed. The engine and the worker are now one module.
- Go engine tests read `../shared/test-vectors.json`, a path and file name that did not exist, so the contract tests always failed. The vector now sits beside the test.
- The Windows job ran the Python tests on Windows, where default text decoding (cp1252) cannot read the Persian source files. UTF-8 mode is forced and the tests run on Linux.
- Kotlin: `catch (_: Exception)` is not accepted by the pinned Kotlin 2.0; parameters are now named.
- Android dependency on `com.wireguard.android:tunnel` (an unverified version, plus a second copy of wireguard-go) replaced by BouncyCastle X25519 for key generation.
- Directory typo `wg-clinet` and three disagreeing workflows removed.

### Changed: no hotspot needed
- The phone and the PC now only need to share a network: one Wi-Fi (any router), or the phone's hotspot. Turning on the hotspot is no longer a required step.
- Fixed how the phone's address is chosen for the QR code. It used to take the first private IPv4 address on any interface, which could be the VPN's own address (tun0) or the mobile-data interface when a VPN was running, so the PC could not reach the phone. It now looks only at hotspot, Wi-Fi, USB-tethering and Ethernet interfaces and ignores VPN, point-to-point and cellular ones.
- The Windows app explains connection failures (not on the same network, client isolation on the router, firewall, certificate mismatch) instead of showing a raw socket error, and no longer pre-fills the old hotspot address.
- Connecting from a different network (phone on mobile data only) is not supported; it needs a relay server.

### Added
- Web app (installable PWA, Persian and English, dark and light) with downloads, guide, a before/after connection check and an Install button, served by GitHub Pages from the repository root. It is a guide, not a replacement for the apps.
- `README.fa.md` (Persian guide), `PUBLISHING.md` (maintainer steps), `set-repo.py` (rewrite links for another repository).
- Release files have fixed names (`RoutePou-android.apk`, `RoutePou-windows-x64.exe`) and the release is marked latest, so the README download buttons always work.

### Security
- Removed the shared TLS identity: each Android installation now creates its own EC key and certificate in the Android Keystore. Previously one PKCS#12 file (password in the source) shipped in every APK, so anyone holding the APK could impersonate any phone. "New pairing key" also rotates the certificate.
- Windows restores the system proxy on any normal interpreter exit.

### Build and release
- One workflow: tests, Android APK, Windows EXE, and on a `v*` tag a GitHub Release with SHA-256 checksums.
- The Go engine (Android) and the WireGuard worker (Windows) are optional build components: if one fails to build, the app is still produced in proxy-only mode and the release notes state it.
- Release APK is signed from repository secrets; without them it uses the debug key (installable, not updatable by a later properly signed build).
- Your logo is now the Android adaptive icon and the Windows EXE icon.

### Removed
- Dead experiments not used by the app (`packet_engine`, `wintun_manager`, `wintun_session`, `wg_telemetry`, `e2e_acceptance`, diagnostics CLIs) and per-version status notes. A real-device checklist is in `TESTING.md`.

### Not done
- Real-device pairing, data-plane and leak testing of the full tunnel are still outstanding; this remains a pre-release.

## Earlier 0.x alphas
Internal development builds (0.11–0.26): QR pairing, TLS proxy bridge, WireGuard full-tunnel path, Windows leak protection, dark/light themes.
