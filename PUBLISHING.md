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

If you upload in the browser, remember that **the web upload never deletes files**. Files that this version removed stay in the repository and can break the tests. The workflow ignores the ones listed below in its own checkout, but delete them from the repository too (open each file, then the trash icon, then **Commit changes**):

`test_pwa.py`, `app.js`, `app.css`, `strings.js`, `sw.js`, `manifest.webmanifest`, `icon-512.png`, `icon-maskable-512.png`, `btn-web.png`, `.github/workflows/build.xml`, `res/drawable-nodpi/none`

The page now uses one font, Vazirmatn. The old font files are no longer used and can be deleted the same way (optional; the workflow ignores them in its own checkout): `Estedad-Regular.woff2`, `Estedad-Medium.woff2`, `Estedad-Bold.woff2`, `Estedad-ExtraBold.woff2`, `Inter-Regular.woff`, `Inter-SemiBold.woff`, `Inter-Bold.woff`, `Inter-ExtraBold.woff`.

If you upload in the browser instead, drag the contents of the folder, not the folder itself. Afterwards the repository home page must show a `.github` folder. If it does not, choose **Add file, Create new file**, type `.github/workflows/build.yml` as the name and paste the contents of `build.yml`. Without that file no build runs.

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

## 4. Test build

**Actions, Build and Release, Run workflow**. When it finishes, download `RoutePou-Android` and `RoutePou-Windows` from the bottom of the run page. The summary of each job says whether the Full Tunnel engine is inside the file.

If the Android job fails, open its **Build APKs** step and copy the red error lines. The workflow also keeps the Gradle reports as an artifact named `android-build-reports`. The Go engine and the Windows worker are optional steps: if they fail, the apps are still built in proxy-only mode and the release notes say so.

## 5. Release

**The simple way (no Git needed):** **Actions, Build and Release, Run workflow**, keep **Publish the finished builds** ticked, press **Run workflow**. When the run is green, the Windows and Android files are on the **Releases** page and the website buttons download them. The workflow moves the version tag to the commit it built, so the release always matches the code.

The download buttons take the file from the *latest release*. If you changed the code after an earlier release, run this again; otherwise people keep getting the old file.

**With a tag:** the tag must match the `VERSION` file:

```
git tag v0.27.0-beta
git push origin v0.27.0-beta
```

If that tag already exists from an earlier attempt, delete it first and push it again:

```
git push origin :refs/tags/v0.27.0-beta
git tag -d v0.27.0-beta
git tag v0.27.0-beta
git push origin v0.27.0-beta
```

If a draft or failed release with the same name exists under **Releases**, delete it as well.

The workflow builds everything and publishes a release with `RoutePou-android.apk`, `RoutePou-windows-x64.exe` and `SHA256SUMS.txt`. The file names do not contain the version on purpose, so the download buttons (`releases/latest/download/...`) always point at the newest release. If the Android build fails, the Windows file is still published and the release notes say the APK is missing.

## 6. Stable Android signing (recommended)

Without a signing key the APK is signed with a debug key, and a later build cannot be installed over it without uninstalling first.

1. Create a key with `bash make-keystore.sh` (needs a JDK).
2. In **Settings, Secrets and variables, Actions** add: `ANDROID_KEYSTORE_BASE64` (the output of `base64 -w0 routepou-release.jks`), `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS` and `ANDROID_KEY_PASSWORD`.
3. Keep the `.jks` file and the passwords somewhere safe and never commit them.

## 7. Before calling a release stable

Run the checklist in `TESTING.md` on a real phone and a real PC.
