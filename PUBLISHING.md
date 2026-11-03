# Publishing RoutePou

Steps for the person who owns the GitHub repository. Every command is run in the folder that contains `README.md` and the hidden `.github` folder.

## 1. Create the repository

On GitHub: **New repository**, name it `RoutePou`, public, and leave "Add a README", ".gitignore" and "license" unticked.

If your account or the repository name is different from `Mahdi-mortazavi/RoutePou`, run this once before the first push. It rewrites the links in the README files and the web app:

```
python set-repo.py YourName/YourRepo
```

## 2. Upload the files

Use Git, because it keeps the hidden `.github` folder and the `res` and `winclient` folders intact:

```
git init -b main
git add .
git commit -m "RoutePou 0.27.0-beta"
git remote add origin https://github.com/YourName/YourRepo.git
git push -u origin main
```

If you upload in the browser instead, drag the contents of the folder, not the folder itself. Afterwards the repository home page must show a `.github` folder. If it does not, choose **Add file, Create new file**, type `.github/workflows/build.yml` as the name and paste the contents of `build.yml`. Without that file no build runs.

## 3. Turn on the web app

**Settings, Pages**: Source **Deploy from a branch**, branch `main`, folder `/ (root)`. After a minute the web app is at `https://YourName.github.io/YourRepo/`. The file `.nojekyll` is already there.

## 4. Test build

**Actions, Build and Release, Run workflow**. When it finishes, download `RoutePou-Android` and `RoutePou-Windows` from the bottom of the run page. The summary of each job says whether the Full Tunnel engine is inside the file.

If a step fails, open it, copy the red error lines and send them to whoever maintains the project. The Go engine and the Windows worker are optional steps: if they fail, the apps are still built in proxy-only mode and the release notes say so.

## 5. Release

The tag must match the `VERSION` file:

```
git tag v0.27.0-beta
git push origin v0.27.0-beta
```

The workflow builds everything and publishes a release with `RoutePou-android.apk`, `RoutePou-windows-x64.exe` and `SHA256SUMS.txt`. The file names do not contain the version on purpose, so the download buttons in the README (`releases/latest/download/...`) always point at the newest release.

## 6. Stable Android signing (recommended)

Without a signing key the APK is signed with a debug key, and a later build cannot be installed over it without uninstalling first.

1. Create a key with `bash make-keystore.sh` (needs a JDK).
2. In **Settings, Secrets and variables, Actions** add: `ANDROID_KEYSTORE_BASE64` (the output of `base64 -w0 routepou-release.jks`), `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS` and `ANDROID_KEY_PASSWORD`.
3. Keep the `.jks` file and the passwords somewhere safe and never commit them.

## 7. Before calling a release stable

Run the checklist in `TESTING.md` on a real phone and a real PC.
