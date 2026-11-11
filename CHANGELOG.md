# Changelog

## 0.27.0-beta — Clean rebuild
The project was rebuilt as a flat repository with a single Go module and three independent workflows.

### Changed: a shorter, faster website
- The home page shows only the essentials: headline, both downloads and four buttons (How it works, Inside the app, Security, License). Each button opens its explanation in a layer (a dialog; a bottom sheet on a phone). Without JavaScript the sections are shown on the page.
- Dark and light theme (follows the system, remembered, button in the header) and Persian/English (remembered). The app pictures switch to dark versions in the dark theme.
- Fast: the first view loads about 80 KB (HTML, CSS, JavaScript, two reduced Vazirmatn font files, a 2 KB logo). The app pictures are WebP (35 to 40 KB each), load only when their layer opens, and only the picture for the current theme loads.

### Added: language button in both apps
- The Android app and the Windows app each have a language button (فارسی / English). Persian is the default; the choice is kept for the next start. Android switches the whole screen between right-to-left and left-to-right and keeps the typed text and the running status; Windows redraws every text (`i18n.py`, saved in `%APPDATA%\\RoutePou\\settings.json`). Error messages from the helpers follow the language too.

### Fixed: the phone shows what to do when there is no shared network
- With only mobile data (no Wi-Fi, no hotspot) the Android app now says so plainly, shows **Turn on hotspot** and **Connect to Wi-Fi** buttons, and checks for a network every 3 seconds, so the QR appears as soon as one is available. The Windows app compares its own address with the phone's when a connection times out and tells you whether the two are on different networks.
- The primary button label is white on the red in both themes (it was dark on the light theme).

### Changed: the two apps look like the pictures on the website
- Both apps use the same palette as the site (red `#D01F2F` on neutral greys). The Windows buttons are in two rows (four in one row were wider than the window), the notice and footer follow the theme, and the BETA badge is gone from the header. The site pictures were redrawn from the real layout of both apps.

### Changed: tests.yml shows what failed
- A failing run lists the failed test names and their first lines on the run's Summary page.

### Changed: README
- `README.md` is in Persian now, with the earlier hero and button images, and an **English guide** button that opens `README.en.md`. The English page has a Persian-guide button back. `README.fa.md` is gone (listed in `old-files.txt`).

### Added: Remove old files
- `old-files.txt` lists the files that older versions left in the repository. The CI jobs ignore them in their own checkout, and the new manual workflow **Remove old files** (`cleanup.yml`) deletes them from the repository.

### Changed: three workflows
- The single `build.yml` is replaced by `tests.yml`, `windows.yml` and `android.yml`. They run independently, so a failure is easy to place, and a red Android build never holds back the Windows download (or the reverse). Delete the old `.github/workflows/build.yml` from the repository.
- Each of the two build workflows publishes its own file by itself after a green build (push to `main`, or **Run workflow**) with `publish-release.sh`: it moves the version tag to the built commit, attaches the file and a `.sha256`, and marks the release as the latest one. The release text comes from `release-notes.sh`.
- The EXE start test is advisory now: a runner that cannot open windows no longer blocks the download. Its result is written to the run Summary.

### Fixed (build-breaking)
- Removed `.github/workflows/build.xml`, a stale older copy of the workflow (GitHub ignores `.xml`, and it still used version-numbered file names).
- Windows: the built EXE stopped at start-up with "No module named 'tkinter.ttk'", because `routepou_windows.py` loads `tkinter.ttk` with `__import__()` and PyInstaller cannot see that. The workflow now passes `--hidden-import tkinter.ttk` and fails the build if the module is missing from the EXE. The app code is unchanged.
- Android: `RoutePouWgKeys.kt`, `RoutePouWgConfig.kt` and `RoutePouPairingPayload.kt` declared the package `com.pou.routepou.pairing`, but `MainActivity.kt` used them without importing it, so Gradle stopped with "Unresolved reference" and no APK was produced. Every Kotlin source is now in `com.pou.routepou`, and a test enforces it.
- Windows: `routepou_windows.py` now imports `tkinter.ttk` with a plain `from tkinter import ttk` instead of `__import__()`, so the EXE contains it however PyInstaller is configured. A user who downloaded the EXE from an old release still got the old build: the only release pointed at the first upload. The workflow can now publish by itself (**Actions, Run workflow**) and moves the version tag to the commit it built.
- Android: the build stopped before Gradle even started. The helper action `android-actions/setup-android@v3` failed with "Failed to find package 'tools'" on GitHub's current Ubuntu image. The workflow now calls the `sdkmanager` that is already on the runner, and the Android job runs on the fixed image `ubuntu-24.04`.
- Windows: the build now starts the finished `RoutePou.exe` once (`--selftest`: the window opens and closes by itself) and fails if a module is missing inside the EXE, so a broken EXE is caught in the build instead of on a user's PC.
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
- `README.en.md` (English guide; `README.md` is the Persian page), `PUBLISHING.md` (maintainer steps), `set-repo.py` (rewrite links for another repository).
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
