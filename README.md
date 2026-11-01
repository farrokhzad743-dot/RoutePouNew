<div align="center">

<img src="logo.png" width="110" alt="RoutePou" />

# RoutePou

**اینترنت و VPN گوشی اندروید را با اسکن یک QR به ویندوز وصل کنید**
*Share your Android phone's internet — and its VPN — with a Windows PC by scanning a QR code.*

`0.27.0-beta` · Android 8.0+ · Windows 10/11 (64-bit) · GPL-3.0

</div>

> ⚠️ **پیش‌انتشار.** کد کامل است و تست‌های خودکار دارد، ولی اتصال واقعی دو دستگاه هنوز روی سخت‌افزار تست نشده است. فهرست آزمایش: [`TESTING.md`](TESTING.md).

## کار برنامه

گوشی هات‌اسپات را روشن می‌کند، ویندوز به آن وصل می‌شود و با اسکن QR اینترنت گوشی — با هر VPN که روی گوشی روشن است — در ویندوز قابل استفاده می‌شود.

| حالت | توضیح | وضعیت |
|---|---|---|
| **پروکسی امن** | ویندوز پراکسی سیستم (`127.0.0.1:17878`) و SOCKS5 (`127.0.0.1:17879`) را فعال می‌کند؛ ترافیک با TLS به گوشی می‌رود | بتا |
| **تونل کامل WireGuard** | یک آداپتر مجازی می‌سازد و **همهٔ** ترافیک (TCP/UDP/DNS) را از گوشی عبور می‌دهد؛ نیاز به Administrator | آزمایشی |

## نصب

از صفحهٔ **Releases** این ریپو دو فایل را بگیرید:
- `RoutePou-…-android.apk` → روی گوشی نصب کنید (اجازهٔ «نصب از منبع ناشناس»).
- `RoutePou-…-windows-x64.exe` → اجرا کنید (اگر SmartScreen هشدار داد: *More info → Run anyway*؛ فایل امضای دیجیتال ندارد).

سپس: هات‌اسپات گوشی را روشن کنید و ویندوز را وصل کنید ← در برنامهٔ اندروید «شروع اشتراک‌گذاری» (یا تونل کامل از «تنظیمات پیشرفته») ← در برنامهٔ ویندوز «اسکن با دوربین» (یا انتخاب تصویر QR / Clipboard).

QR یک **رمز** است؛ آن را به کسی نشان ندهید. QR تونل کامل پس از ۵ دقیقه منقضی می‌شود.

## قرار دادن در GitHub و ساخت فایل‌ها

**۱. ساخت ریپوی جدید:** در GitHub، *New repository*، یک نام (مثلاً `RoutePou`) بدهید و **هیچ فایلی (README/license) را تیک نزنید**.

**۲. آپلود (روش مطمئن با Git):** زیپ را باز کنید، داخل همان پوشه PowerShell باز کنید (باید `README.md` و پوشهٔ `.github` را ببینید):
```powershell
git init -b main
git add .
git commit -m "RoutePou 0.27.0-beta"
git remote add origin https://github.com/<نام-کاربری>/RoutePou.git
git push -u origin main
```
> اگر از آپلود وب (*Add file → Upload files*) استفاده می‌کنید: **محتویات** پوشه را انتخاب و بکشید، نه خود پوشه را. بعد از آپلود باید در صفحهٔ اصلی ریپو پوشهٔ `.github` را ببینید؛ اگر نبود، *Add file → Create new file* بزنید، به‌عنوان نام `.github/workflows/build.yml` را تایپ کنید و محتوای فایل `build.yml` همین پروژه را در آن بچسبانید. بدون این فایل **هیچ بیلدی اجرا نمی‌شود**.

**۳. بیلد آزمایشی:** تب **Actions ← Build and Release ← Run workflow**. پس از پایان، از انتهای صفحهٔ اجرا، `RoutePou-Android` و `RoutePou-Windows` را دانلود کنید. در خلاصهٔ هر job نوشته شده که موتور تونل کامل داخل فایل هست یا نه.

**۴. انتشار رسمی:**
```powershell
git tag v0.27.0-beta
git push origin v0.27.0-beta
```
GitHub Actions خودش APK و EXE را می‌سازد و یک Release با checksum منتشر می‌کند (تگ باید با فایل `VERSION` یکی باشد).

**۵. (توصیه‌شده) امضای ثابت اندروید:** بدون آن APK با کلید موقت امضا می‌شود و نسخه‌های بعدی روی آن نصب نمی‌شوند مگر با حذف نسخهٔ قبل. با `./make-keystore.sh` (نیاز به JDK) کلید بسازید و چهار Secret را در *Settings → Secrets and variables → Actions* بگذارید: `ANDROID_KEYSTORE_BASE64` (خروجی `base64 -w0 routepou-release.jks`)، `ANDROID_KEYSTORE_PASSWORD`، `ANDROID_KEY_ALIAS`، `ANDROID_KEY_PASSWORD`. فایل `.jks` و رمزها را جای امن نگه دارید؛ هرگز در ریپو نگذارید.

## ساختار فایل‌ها (همه در صفحهٔ اصلی)

| فایل‌ها | کار |
|---|---|
| `*.kt`, `AndroidManifest.xml`, `res/`, `android-*.kts`, `android-gradle.properties`, `proguard-rules.pro` | برنامهٔ اندروید |
| `relaywg.go`, `netstack.go`, `upstream.go`, `mobile.go`, `*_test.go`, `go.mod`, `go.sum` | موتور WireGuard گوشی (Go → `relaywg.aar`) |
| `winclient/` | کارگر ممتاز ویندوز (`relaywg-client.exe`: Wintun + WireGuard + فیلتر نشت) |
| `routepou_windows.py`, `pairing.py`, `wg_provision.py`, `wg_supervisor.py`, `proxy_headers.py` | برنامهٔ ویندوز |
| `build-aar.sh`, `stage-android.sh`, `make-keystore.sh` | اسکریپت‌های بیلد |
| `.github/workflows/build.yml` | تست، بیلد و انتشار |
| `test_*.py`, `test-vectors.json` | تست‌ها |

فقط سه پوشه ضروری است و حذف‌شدنی نیست: `.github` (GitHub فقط از آنجا workflow می‌خواند)، `res` (اندروید منابع را فقط از پوشهٔ مخصوص می‌پذیرد) و `winclient` (Go هر پکیج را در یک پوشهٔ جدا می‌خواهد).

## بیلد محلی

**اندروید** (JDK 17، Go 1.25+، SDK 35، NDK r27؛ Gradle 8.9):
```bash
export ANDROID_HOME=~/Android/Sdk ANDROID_NDK_HOME=$ANDROID_HOME/ndk/27.2.12479018
./build-aar.sh          # اختیاری: موتور تونل کامل → build/relaywg.aar
./stage-android.sh      # پروژهٔ استاندارد اندروید در build/android
cd build/android && gradle assembleDebug     # یا این پوشه را در Android Studio باز کنید
```
**ویندوز** (Python 3.12 + Go 1.25):
```powershell
go build -trimpath -ldflags="-s -w" -o relaywg-client.exe ./winclient
# wintun.dll (amd64) را از https://www.wintun.net کنار فایل‌ها بگذارید
pip install pyinstaller zxing-cpp pillow opencv-python
pyinstaller --onefile --windowed --icon routepou.ico --collect-all zxingcpp --collect-all PIL --collect-all cv2 --add-binary "relaywg-client.exe;." --add-binary "wintun.dll;." --name RoutePou routepou_windows.py
```
**تست:** `pip install pytest pyyaml && pytest` و `go test .`

## محدودیت‌ها

- حالت پروکسی فقط برنامه‌هایی را پوشش می‌دهد که از پراکسی سیستم ویندوز پیروی کنند؛ برای کل ترافیک از تونل کامل استفاده کنید.
- اندروید ۱۵ ممکن است سرویس پیش‌زمینهٔ `dataSync` را پس از حدود ۶ ساعت متوقف کند؛ دوباره شروع کنید.
- فقط IPv4 و شبکه‌های خصوصی هات‌اسپات (`10.x`، `172.16–31.x`، `192.168.x`).
- معماری امنیتی و گزارش آسیب‌پذیری: [`SECURITY.md`](SECURITY.md). لایسنس‌های اجزا: [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

## لایسنس

GPL-3.0 (شامل کد GPL موتور Relay). متن کامل: [`LICENSE`](LICENSE).

---

### English summary
RoutePou turns an Android phone into a gateway for a Windows PC: enable the hotspot, connect the PC, scan a QR. **Proxy mode** (beta) tunnels HTTP/HTTPS/SOCKS5 over per-install, fingerprint-pinned TLS; **Full tunnel** (experimental) runs a userspace WireGuard endpoint on the phone and a Wintun client on Windows. Push this repository to GitHub as-is (keep the `.github` folder), run *Actions → Build and Release*, or push a tag like `v0.27.0-beta` to publish a Release with the APK, the EXE and checksums. Unit-tested and CI-built, **not yet validated on real devices** — see `TESTING.md`.
