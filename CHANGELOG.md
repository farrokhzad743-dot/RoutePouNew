# Changelog

## 0.27.0-beta — Clean rebuild
The project was rebuilt as a flat repository with a single Go module and a single workflow.

### Fixed (build-breaking)
- Removed `.github/workflows/build.xml`, a stale older copy of the workflow (GitHub ignores `.xml`, and it still used version-numbered file names).
- Windows: the built EXE stopped at start-up with "No module named 'tkinter.ttk'", because `routepou_windows.py` loads `tkinter.ttk` with `__import__()` and PyInstaller cannot see that. The workflow now passes `--hidden-import tkinter.ttk` and fails the build if the module is missing from the EXE. The app code is unchanged.
- Android: `RoutePouWgKeys.kt`, `RoutePouWgConfig.kt` and `RoutePouPairingPayload.kt` declared the package `com.pou.routepou.pairing`, but `MainActivity.kt` used them without importing it, so Gradle stopped with "Unresolved reference" and no APK was produced. Every Kotlin source is now in `com.pou.routepou`, and a test enforces it.
- Windows: `routepou_windows.py` now imports `tkinter.ttk` with a plain `from tkinter import ttk` instead of `__import__()`, so the EXE contains it however PyInstaller is configured. A user who downloaded the EXE from an old release still got the old build: the only release pointed at the first upload. The workflow can now publish by itself (**Actions, Run workflow**) and moves the version tag to the commit it built.
- Android: `stage-android.sh` leaves out files in `res/` that Android cannot accept (no extension, `.DS_Store`, `Thumbs.db`). The placeholder `res/drawable-nodpi/none`, made in the GitHub web editor in the first upload, stops Gradle with "The file name must end with .xml or .png".
- Android: when Gradle fails, the important lines are shown at the top of the run page (Summary).
- Release: the Windows file is published even when the Python tests are red or the Android build fails; both show as warnings.
- CI: the tests and the Android job first remove files that older versions had (web app, old tests, the old workflow copy). GitHub's web upload never deletes files, so they otherwise stayed in the repository and broke the Python tests and the Android resources.
- Release job: a failed Android build no longer blocks the Windows release; the release notes say the APK is missing. Gradle reports are kept as a workflow artifact when the Android build fails.
- Android: a request URL containing `$` or `\` could break the HTTP proxy's request-line rewrite; the replacement text is now escaped.
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
- Download website for Windows and Android (`index.html`, `site.css`, `site.js`): one plain white and red page in Persian and English with both downloads together, simple pictures of the app screens, and the security and license information written on the page. One font (Vazirmatn). Published with GitHub Pages at routepou.pouone.ir. It replaces the earlier installable web app.
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
