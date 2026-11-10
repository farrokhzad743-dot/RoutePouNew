# Publishing RoutePou

Steps for the person who owns the GitHub repository (`farrokhzad743-dot/RoutePouNew`). Every command is run in the folder that contains `README.md` and the hidden `.github` folder.

## 1. Create the repository

On GitHub: **New repository**, owner `farrokhzad743-dot`, name `RoutePouNew`, **public** (GitHub Pages needs a public repository on a free plan), and leave "Add a README", ".gitignore" and "license" unticked.

If you ever publish under a different account or repository name, run this once before the first push. It rewrites the links in the README files, `index.html` and `site.js`:

```
python set-repo.py YourName/YourRepo
```

## 2. Upload the files

Use Git, because it keeps the hidden `.github` folder and the `res` and `winclient` folders intact:

```
git init -b main
git add .
git commit -m "RoutePou 0.27.0-beta"
git remote add origin https://github.com/farrokhzad743-dot/RoutePouNew.git
git push -u origin main
```

If you upload in the browser, remember that **the web upload never deletes files**. Files that this version removed stay in the repository. They are all listed in `old-files.txt`; the CI jobs ignore them in their own checkout (so they cannot break a build or a test), and you can remove them from the repository in one step:

1. **Actions**, choose **Remove old files** in the left list, **Run workflow**. It deletes every file listed in `old-files.txt` and commits that.
2. GitHub does not let a workflow change workflow files, so delete these two by hand (open the file, trash icon, **Commit changes**): `.github/workflows/build.yml` (the old single workflow, replaced by the new ones) and `.github/workflows/build.xml` if it is still there.

The list, for reference: `test_pwa.py`, `app.js`, `app.css`, `strings.js`, `sw.js`, `manifest.webmanifest`, `icon-512.png`, `icon-maskable-512.png`, `btn-web.png` (the old web app); `Estedad-Regular.woff2`, `Estedad-Medium.woff2`, `Estedad-Bold.woff2`, `Estedad-ExtraBold.woff2`, `Inter-Regular.woff`, `Inter-SemiBold.woff`, `Inter-Bold.woff`, `Inter-ExtraBold.woff` (old site fonts; the site uses Vazirmatn); `res/drawable-nodpi/none` (not a valid Android resource); `.github/workflows/build.yml`, `.github/workflows/build.xml`.

If you upload in the browser instead, drag the contents of the folder, not the folder itself. Afterwards the repository home page must show a `.github` folder. If it does not, choose **Add file, Create new file**, type `.github/workflows/windows.yml` as the name and paste the contents of `windows.yml`; do the same for `android.yml`, `tests.yml` and `cleanup.yml`. Without these files no build runs.

There are four workflows, one file each, so a failure is easy to place:

| File | What it does | Starts |
|---|---|---|
| `tests.yml` | Python tests, and the Go tests (advisory). Builds nothing. | every push, every pull request |
| `windows.yml` | Builds `RoutePou-windows-x64.exe` and publishes it | a push that changes the Windows app, or **Run workflow** |
| `android.yml` | Builds `RoutePou-android.apk` and publishes it | a push that changes the Android app, or **Run workflow** |
| `cleanup.yml` | **Remove old files**: deletes the leftovers listed in `old-files.txt` from the repository | only **Run workflow** |

They never wait for each other: a red Android build does not stop the Windows download, and the reverse.

## 3. Turn on the website (routepou.pouone.ir)

The download page is `index.html` in the repository root. Two things connect it to your domain.

**a) DNS, at the place where `pouone.ir` is managed.** Add one record:

| Type | Name / Host | Value / Target |
|---|---|---|
| `CNAME` | `routepou` | `farrokhzad743-dot.github.io` |

Use only the account host in the value, without `/RoutePouNew`. If the DNS service has a proxy switch (for example Cloudflare's orange cloud), turn it off for this record until GitHub has issued the certificate.

**b) GitHub, in the repository.** **Settings, Pages**:

1. Source **Deploy from a branch**, branch `main`, folder `/ (root)`, **Save**.
2. Custom domain: `routepou.pouone.ir`, **Save**. The file `CNAME` in this repository already says the same, so the setting stays after every push.
3. When GitHub shows the DNS check as successful (a few minutes to a day), tick **Enforce HTTPS**.

Until the domain works, the same page is at `https://farrokhzad743-dot.github.io/RoutePouNew/`. The file `.nojekyll` is already there.

## 4. Build and publish

Nothing else is needed: after a push, the right workflow starts by itself and, when it is green, puts its file on the **Releases** page. The website buttons take the file from the *latest release* (`releases/latest/download/...`).

To build without changing any file: **Actions**, choose **Windows EXE** or **Android APK** in the left list, **Run workflow**, keep **Publish** ticked, **Run workflow**. A run takes about 10 to 25 minutes.

- The summary of each run (top of the run page) says whether the Full Tunnel engine is inside the file. The Windows summary also says whether the finished EXE started and closed normally (the self-test; advisory).
- Untick **Publish** to only build: the file is then at the bottom of the run page (`RoutePou-Android`, `RoutePou-Windows`) and nothing is published.
- If the Android run fails, the important error lines are at the top of the run page. The Gradle reports are kept as an artifact named `android-build-reports`. Send those lines. The Go engine and the Windows worker are optional steps: if they fail, the apps are still built in proxy-only mode.
- Only a push that changes the app (or `VERSION`, the scripts or the workflow itself) starts a build. A change to the website or the README does not rebuild the apps.

## 5. Release

Publishing is automatic. Every publish moves the version tag (`v` plus the `VERSION` file) to the commit that was built, attaches the file and a `.sha256` checksum, and marks the release as the latest one. The file names do not contain the version on purpose, so the download buttons always point at the newest release.

To start a new version: change `VERSION` (and the version in `android-build.gradle.kts` and `routepou_windows.py`, which a test checks), add a section to `CHANGELOG.md`, and push. Both workflows run, and both attach their file to the same release.

If a draft or failed release with the same name exists under **Releases**, delete it before the next run.

## 6. Stable Android signing (recommended)

Without a signing key the APK is signed with a debug key, and a later build cannot be installed over it without uninstalling first.

1. Create a key with `bash make-keystore.sh` (needs a JDK).
2. In **Settings, Secrets and variables, Actions** add: `ANDROID_KEYSTORE_BASE64` (the output of `base64 -w0 routepou-release.jks`), `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS` and `ANDROID_KEY_PASSWORD`.
3. Keep the `.jks` file and the passwords somewhere safe and never commit them.

## 7. Before calling a release stable

Run the checklist in `TESTING.md` on a real phone and a real PC.
