package com.pou.routepou

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.os.Build
import android.os.Bundle
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.EditText
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import com.google.zxing.BarcodeFormat
import com.google.zxing.EncodeHintType
import com.google.zxing.qrcode.QRCodeWriter
import java.net.Inet4Address
import java.net.NetworkInterface
import java.net.URLEncoder
import java.security.SecureRandom

class MainActivity : Activity() {
    private lateinit var statusTitle: TextView
    private lateinit var statusDetail: TextView
    private lateinit var addressView: TextView
    private lateinit var qrView: ImageView
    private lateinit var tokenView: TextView
    private lateinit var proxyStartButton: Button
    private lateinit var proxyStopButton: Button
    private lateinit var tunnelStartButton: Button
    private lateinit var tunnelStopButton: Button
    private lateinit var upstreamInput: EditText
    private var proxyStarted = false
    private var fullTunnelRequested = false
    private var pairingToken = ""
    private var fingerprint = ""
    private var fullModePayload = ""

    /** What the status card says. It is a state, not a text, so it can be shown again in the other language. */
    private enum class Status { READY, NO_NETWORK, PROXY_RUNNING, TUNNEL_STARTING, TUNNEL_FAILED }
    private var status = Status.READY
    private var statusError = ""

    // Kept across a rebuild of the screen (language or theme change), so nothing the user typed or opened is lost.
    private var upstreamText = ""
    private var advancedOpen = false

    private var darkMode = true
    private var bg = Color.rgb(13, 10, 15)
    private var card = Color.rgb(31, 20, 28)
    private var muted = Color.rgb(190, 166, 180)
    private var accent = Color.rgb(150, 25, 65)
    private val green = Color.rgb(58, 205, 145)

    private fun applyPalette() {
        darkMode = getSharedPreferences("routepou", MODE_PRIVATE).getBoolean("dark_mode", true)
        if (darkMode) {
            bg = Color.rgb(13, 10, 15); card = Color.rgb(31, 20, 28)
            muted = Color.rgb(190, 166, 180); accent = Color.rgb(150, 25, 65)
        } else {
            bg = Color.rgb(248, 244, 247); card = Color.rgb(255, 255, 255)
            muted = Color.rgb(112, 83, 99); accent = Color.rgb(133, 18, 56)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        Lang.load(this)
        applyPalette()
        window.statusBarColor = bg
        window.navigationBarColor = bg
        if (Build.VERSION.SDK_INT >= 29) window.isNavigationBarContrastEnforced = false
        if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 9)
        }

        pairingToken = getOrCreateToken()
        fingerprint = loadFingerprint()
        buildScreen()
        refreshQr()
    }

    private fun buildScreen() {
        if (::upstreamInput.isInitialized) upstreamText = upstreamInput.text.toString()
        val page = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(20), dp(18), dp(20), dp(28))
            setBackgroundColor(bg)
            // Persian reads right to left, English left to right: the whole screen follows the chosen language.
            layoutDirection = if (Lang.isFa) View.LAYOUT_DIRECTION_RTL else View.LAYOUT_DIRECTION_LTR
        }

        val header = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
        }
        val brand = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; layoutParams = LinearLayout.LayoutParams(0, -2, 1f) }
        brand.addView(text("RoutePou", 29f, Color.WHITE, true))
        brand.addView(text("PHONE  →  WINDOWS", 11f, muted, true).apply { letterSpacing = .16f })
        header.addView(brand)
        val badge = text("BETA", 10f, Color.WHITE, true).apply {
            setPadding(dp(12), dp(7), dp(12), dp(7)); background = rounded(accent, 30)
        }
        header.addView(badge)
        page.addView(header)
        page.addView(space(12))

        // Language and theme sit on their own row, so the header stays readable on a narrow phone.
        val controls = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        val languageButton = secondaryButton(if (Lang.isFa) "English" else "فارسی") {
            Lang.save(this, if (Lang.isFa) "en" else "fa")
            buildScreen(); refreshQr()
        }
        val themeButton = secondaryButton(if (darkMode) Lang.t("حالت روشن", "Light mode") else Lang.t("حالت تاریک", "Dark mode")) {
            getSharedPreferences("routepou", MODE_PRIVATE).edit().putBoolean("dark_mode", !darkMode).apply()
            applyPalette(); window.statusBarColor = bg; window.navigationBarColor = bg; buildScreen(); refreshQr()
        }
        controls.addView(languageButton, LinearLayout.LayoutParams(0, dp(42), 1f).apply { marginEnd = dp(8) })
        controls.addView(themeButton, LinearLayout.LayoutParams(0, dp(42), 1f))
        page.addView(controls)
        page.addView(space(18))

        val hero = cardLayout()
        hero.setPadding(dp(18), dp(18), dp(18), dp(18))
        hero.addView(text(Lang.t("وضعیت اتصال", "Connection status"), 13f, muted, true))
        page.addView(hero)
        val statusRow = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL }
        val dot = View(this).apply { background = rounded(accent, 50); layoutParams = LinearLayout.LayoutParams(dp(9), dp(9)).apply { marginEnd = dp(9) } }
        statusTitle = text(Lang.t("آماده اتصال", "Ready to connect"), 20f, Color.WHITE, true)
        statusRow.addView(dot); statusRow.addView(statusTitle)
        hero.addView(space(8)); hero.addView(statusRow)
        statusDetail = text(Lang.t("گوشی را به همان وای‌فایِ ویندوز وصل کنید؛ اگر وای‌فای مشترک ندارید، هات‌اسپات را روشن کنید.", "Connect the phone to the same Wi-Fi as the PC. If you have no shared Wi-Fi, turn on the hotspot."), 12f, muted)
        hero.addView(statusDetail)
        hero.addView(space(16))

        val stats = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        stats.addView(infoTile(Lang.t("شبکه مشترک", "Shared network"), "Wi-Fi / Hotspot", 1f))
        stats.addView(spaceWidth(10))
        stats.addView(infoTile(Lang.t("پورت سرویس", "Service port"), "8788", 1f))
        hero.addView(stats)
        hero.addView(space(10))
        hero.addView(text(Lang.t("نشانی شبکه", "Network address"), 11f, muted, true))
        addressView = text(Lang.t("در حال بررسی شبکه…", "Checking the network…"), 13f, Color.WHITE)
        hero.addView(addressView)
        page.addView(space(14))

        val modeCard = cardLayout().apply { setPadding(dp(18), dp(17), dp(18), dp(17)) }
        modeCard.addView(text(Lang.t("اتصال سریع با QR", "Quick connect with QR"), 18f, Color.WHITE, true))
        modeCard.addView(space(5))
        modeCard.addView(text(Lang.t("هات‌اسپات لازم نیست: گوشی و ویندوز را به یک وای‌فای وصل کنید، VPN گوشی را روشن کنید، اشتراک‌گذاری را شروع کنید و QR را در RoutePou ویندوز اسکن کنید.", "No hotspot needed: connect the phone and the PC to the same Wi-Fi, turn on the phone's VPN, start sharing and scan the QR in RoutePou for Windows."), 12f, muted))
        modeCard.addView(space(13))
        proxyStartButton = primaryButton(Lang.t("شروع اشتراک‌گذاری", "Start sharing")) { startProxy() }
        modeCard.addView(proxyStartButton, matchWrap())
        modeCard.addView(space(8))
        proxyStopButton = secondaryButton(Lang.t("توقف اشتراک‌گذاری", "Stop sharing")) { stopProxy() }
        modeCard.addView(proxyStopButton, matchWrap())
        modeCard.addView(space(12))
        val advancedPanel = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            visibility = if (advancedOpen) View.VISIBLE else View.GONE
        }
        advancedPanel.addView(text(Lang.t("تنظیمات پیشرفته · آزمایشی", "Advanced settings · experimental"), 14f, Color.WHITE, true))
        advancedPanel.addView(space(7))
        advancedPanel.addView(text(Lang.t("SOCKS5 محلی VPN گوشی (اختیاری)", "Local SOCKS5 of the phone's VPN (optional)"), 12f, Color.WHITE, true))
        upstreamInput = EditText(this).apply {
            hint = "127.0.0.1:10808"
            setText(upstreamText)
            setSingleLine(true)
            textSize = 13f
            setTextColor(if (darkMode) Color.WHITE else Color.rgb(42, 25, 34))
            setHintTextColor(muted)
            setPadding(dp(12), dp(8), dp(12), dp(8))
            background = rounded(if (darkMode) Color.rgb(43, 25, 36) else Color.rgb(242, 232, 238), 12)
            inputType = android.text.InputType.TYPE_CLASS_TEXT
            textDirection = View.TEXT_DIRECTION_LTR   // an address such as 127.0.0.1:10808 is always left to right
        }
        advancedPanel.addView(upstreamInput, matchWrap())
        advancedPanel.addView(space(8))
        tunnelStartButton = primaryButton(Lang.t("راه‌اندازی تونل کامل WireGuard", "Start WireGuard full tunnel")) { startFullTunnel() }
        advancedPanel.addView(tunnelStartButton, matchWrap())
        advancedPanel.addView(space(7))
        tunnelStopButton = secondaryButton(Lang.t("توقف تونل کامل", "Stop full tunnel")) { stopFullTunnel() }
        advancedPanel.addView(tunnelStopButton, matchWrap())
        modeCard.addView(advancedPanel)
        val advancedToggle = secondaryButton(Lang.t("نمایش تنظیمات پیشرفته", "Show advanced settings")) {
            advancedOpen = advancedPanel.visibility != View.VISIBLE
            advancedPanel.visibility = if (advancedOpen) View.VISIBLE else View.GONE
        }
        modeCard.addView(space(9))
        modeCard.addView(advancedToggle, matchWrap())
        page.addView(modeCard)
        page.addView(space(14))

        val pairingCard = cardLayout().apply { setPadding(dp(18), dp(17), dp(18), dp(17)) }
        pairingCard.addView(text(Lang.t("۱ · اسکن برای اتصال ویندوز", "1 · Scan to connect Windows"), 17f, Color.WHITE, true))
        pairingCard.addView(space(5))
        pairingCard.addView(text(Lang.t("پس از شروع اشتراک‌گذاری، همین QR را با دوربین ویندوز اسکن کنید. نیازی به واردکردن IP یا کلید نیست؛ QR را محرمانه نگه دارید.", "After you start sharing, scan this QR with RoutePou on Windows. You do not need to type an IP or a key. Keep the QR private."), 12f, muted))
        pairingCard.addView(space(13))
        qrView = ImageView(this).apply {
            setBackgroundColor(Color.WHITE)
            setPadding(dp(12), dp(12), dp(12), dp(12))
            scaleType = ImageView.ScaleType.FIT_CENTER
            contentDescription = Lang.t("کد QR امن اتصال RoutePou به ویندوز", "Secure RoutePou QR code for connecting Windows")
        }
        val qrFrame = LinearLayout(this).apply { gravity = Gravity.CENTER; setPadding(0, dp(4), 0, dp(12)) }
        qrFrame.addView(qrView, LinearLayout.LayoutParams(dp(220), dp(220)))
        pairingCard.addView(qrFrame)
        tokenView = text(Lang.t("کلید جفت‌سازی: مخفی", "Pairing key: hidden"), 10f, muted)
        pairingCard.addView(tokenView)
        pairingCard.addView(space(10))
        val rotate = secondaryButton(Lang.t("ساخت کلید جفت‌سازی جدید", "Create a new pairing key")) { rotatePairingKey() }
        pairingCard.addView(rotate, matchWrap())
        page.addView(pairingCard)
        page.addView(space(14))

        val note = cardLayout().apply { setPadding(dp(16), dp(14), dp(16), dp(14)) }
        note.addView(text(Lang.t("نکته امنیتی", "Security note"), 13f, Color.WHITE, true))
        note.addView(text(Lang.t("نسخه آلفا است. پروکسی فقط ترافیک برنامه‌هایی را عبور می‌دهد که دستی به آن متصل شوند؛ این حالت VPN سراسری گوشی یا ویندوز نیست. برای تونل کامل، عملکرد واقعی و Handshake باید روی دو دستگاه آزمایش شود.", "This is an alpha version. The proxy only carries the traffic of apps that are set to use it; it is not a system-wide VPN for the phone or the PC. For the full tunnel, real-world operation and the handshake still have to be tested on two devices."), 11f, muted))
        page.addView(note)
        page.addView(space(18))
        page.addView(text("RoutePou ${BuildConfig.VERSION_NAME}  •  POU Network Tools", 10f, muted).apply { gravity = Gravity.CENTER })

        val scroll = ScrollView(this).apply {
            isFillViewport = true
            overScrollMode = View.OVER_SCROLL_NEVER
            addView(page)
        }
        setContentView(scroll)
        updateButtons()
        refreshNetworkInfo()
    }

    private fun infoTile(title: String, value: String, weight: Float): View = LinearLayout(this).apply {
        orientation = LinearLayout.VERTICAL
        setPadding(dp(12), dp(10), dp(12), dp(10))
        background = rounded(if (darkMode) Color.rgb(43, 25, 36) else Color.rgb(242, 232, 238), 14)
        addView(text(title, 10f, muted))
        addView(text(value, 14f, Color.WHITE, true))
        layoutParams = LinearLayout.LayoutParams(0, -2, weight)
    }

    private fun cardLayout() = LinearLayout(this).apply {
        orientation = LinearLayout.VERTICAL
        background = rounded(card, 20)
    }

    private fun text(value: String, size: Float, color: Int, bold: Boolean = false) = TextView(this).apply {
        text = value
        textSize = size
        setTextColor(if (color == Color.WHITE && !darkMode) Color.rgb(42, 25, 34) else color)
        if (bold) setTypeface(typeface, Typeface.BOLD)
        setPadding(0, dp(2), 0, dp(2))
        textDirection = View.TEXT_DIRECTION_FIRST_STRONG
    }

    private fun primaryButton(label: String, action: () -> Unit) = Button(this).apply {
        text = label; isAllCaps = false; textSize = 13f; setTextColor(if (darkMode) Color.WHITE else Color.rgb(42, 25, 34))
        background = rounded(accent, 13); setOnClickListener { action() }
        minHeight = dp(48); stateListAnimator = null
    }

    private fun secondaryButton(label: String, action: () -> Unit) = Button(this).apply {
        text = label; isAllCaps = false; textSize = 12f; setTextColor(if (darkMode) Color.WHITE else Color.rgb(42, 25, 34))
        background = rounded(if (darkMode) Color.rgb(61, 36, 52) else Color.rgb(238, 224, 232), 13); setOnClickListener { action() }
        minHeight = dp(46); stateListAnimator = null
    }

    private fun rounded(color: Int, radius: Int) = GradientDrawable().apply { setColor(color); cornerRadius = dp(radius).toFloat() }
    private fun space(height: Int) = View(this).apply { layoutParams = LinearLayout.LayoutParams(1, dp(height)) }
    private fun spaceWidth(width: Int) = View(this).apply { layoutParams = LinearLayout.LayoutParams(dp(width), 1) }
    private fun matchWrap() = LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(48))
    private fun dp(value: Int) = (value * resources.displayMetrics.density).toInt()

    private fun updateButtons() {
        if (!::proxyStartButton.isInitialized) return
        proxyStartButton.isEnabled = !proxyStarted
        proxyStopButton.isEnabled = proxyStarted
        tunnelStartButton.isEnabled = !fullTunnelRequested
        tunnelStopButton.isEnabled = fullTunnelRequested
        proxyStartButton.alpha = if (proxyStarted) .45f else 1f
        proxyStopButton.alpha = if (!proxyStarted) .45f else 1f
        tunnelStartButton.alpha = if (fullTunnelRequested) .45f else 1f
        tunnelStopButton.alpha = if (!fullTunnelRequested) .45f else 1f
    }

    private fun refreshNetworkInfo() {
        val host = lanIpv4()
        addressView.text = host ?: Lang.t("شبکه‌ای پیدا نشد؛ گوشی را به وای‌فای وصل کنید یا هات‌اسپات را روشن کنید.", "No network found. Connect the phone to Wi-Fi or turn on the hotspot.")
        if (!fullTunnelRequested && !proxyStarted) status = if (host == null) Status.NO_NETWORK else Status.READY
        renderStatus()
        refreshQr()
    }

    /** Writes the status card in the current language. Called again after a language or theme change. */
    private fun renderStatus() {
        if (!::statusTitle.isInitialized) return
        when (status) {
            Status.READY -> {
                statusTitle.text = Lang.t("آماده اتصال", "Ready to connect")
                statusDetail.text = Lang.t("شبکه شناسایی شد؛ یکی از روش‌های اتصال را انتخاب کنید.", "Network found. Choose a way to connect.")
            }
            Status.NO_NETWORK -> {
                statusTitle.text = Lang.t("منتظر شبکه", "Waiting for a network")
                statusDetail.text = Lang.t("گوشی را به همان وای‌فایِ ویندوز وصل کنید، یا هات‌اسپات را روشن و ویندوز را به آن وصل کنید.", "Connect the phone to the same Wi-Fi as the PC, or turn on the hotspot and connect the PC to it.")
            }
            Status.PROXY_RUNNING -> {
                statusTitle.text = Lang.t("پروکسی در حال اجرا", "Proxy is running")
                statusDetail.text = Lang.t("TLS روی پورت 8788 فعال می‌شود. ویندوز باید از QR برای جفت‌سازی استفاده کند.", "TLS is active on port 8788. Windows must pair with the QR.")
            }
            Status.TUNNEL_STARTING -> {
                statusTitle.text = Lang.t("در حال راه‌اندازی تونل", "Starting the tunnel")
                statusDetail.text = Lang.t("سرویس WireGuard شروع شد؛ QR را در ویندوز وارد کنید. اتصال نهایی هنوز نیازمند Handshake است.", "The WireGuard service has started. Scan the QR on Windows. The final connection still needs a handshake.")
            }
            Status.TUNNEL_FAILED -> {
                statusTitle.text = Lang.t("تونل شروع نشد", "The tunnel did not start")
                statusDetail.text = statusError.ifBlank { Lang.t("خطای نامشخص", "Unknown error") }
            }
        }
    }

    private fun refreshQr() {
        if (!::qrView.isInitialized) return
        val host = lanIpv4()
        if (fullModePayload.isNotBlank()) { renderQr(fullModePayload); return }
        if (host == null || fingerprint.length != 64) { qrView.setImageBitmap(null); return }
        val payload = "routepou://pair?host=${enc(host)}&port=8788&key=${enc(pairingToken)}&fp=${enc(fingerprint)}"
        renderQr(payload)
    }

    private fun renderQr(payload: String) {
        try {
            val size = 520
            val matrix = QRCodeWriter().encode(payload, BarcodeFormat.QR_CODE, size, size, mapOf(EncodeHintType.MARGIN to 1))
            val pixels = IntArray(size * size)
            for (y in 0 until size) for (x in 0 until size) pixels[y * size + x] = if (matrix[x, y]) Color.BLACK else Color.WHITE
            qrView.setImageBitmap(Bitmap.createBitmap(pixels, size, size, Bitmap.Config.ARGB_8888))
        } catch (ignored: Exception) { qrView.setImageBitmap(null) }
    }

    private fun startFullTunnel() {
        try {
            val host = lanIpv4() ?: error(Lang.t("شبکه‌ای پیدا نشد. گوشی را به وای‌فای وصل کنید یا هات‌اسپات را روشن کنید.", "No network found. Connect the phone to Wi-Fi or turn on the hotspot."))
            check(WireGuardEngine.isAvailable()) { Lang.t("موتور WireGuard داخل APK موجود نیست. ابتدا AAR را بسازید.", "The WireGuard engine is not inside this APK. Build the AAR first.") }
            val keys = RoutePouWgKeys.generate()
            val ipc = RoutePouWgConfig.serverIpc(keys)
            val upstream = RoutePouUpstream.validate(upstreamInput.text.toString())
            val payload = RoutePouPairingPayload(host, RoutePouWgConfig.DEFAULT_PORT, keys.serverPublicKey, keys.clientPrivateKey, RoutePouWgConfig.DEFAULT_DNS).encode()
            val intent = Intent(this, WireGuardService::class.java).setAction(WireGuardService.ACTION_START).putExtra(WireGuardService.EXTRA_IPC, ipc).putExtra(WireGuardService.EXTRA_UPSTREAM, upstream)
            if (Build.VERSION.SDK_INT >= 26) startForegroundService(intent) else startService(intent)
            fullModePayload = payload
            fullTunnelRequested = true
            status = Status.TUNNEL_STARTING; renderStatus()
            addressView.text = "$host:${RoutePouWgConfig.DEFAULT_PORT}"
            renderQr(payload); updateButtons()
        } catch (e: Exception) {
            Toast.makeText(this, e.message ?: Lang.t("راه‌اندازی تونل ناموفق بود", "Starting the tunnel failed"), Toast.LENGTH_LONG).show()
            status = Status.TUNNEL_FAILED; statusError = e.message ?: ""; renderStatus()
        }
    }

    private fun stopFullTunnel() {
        stopService(Intent(this, WireGuardService::class.java))
        fullModePayload = ""; fullTunnelRequested = false
        status = Status.READY
        updateButtons(); refreshNetworkInfo()
    }

    private fun startProxy() {
        try {
            val host = lanIpv4() ?: error(Lang.t("شبکه‌ای پیدا نشد. گوشی را به وای‌فای وصل کنید یا هات‌اسپات را روشن کنید.", "No network found. Connect the phone to Wi-Fi or turn on the hotspot."))
            val intent = Intent(this, ProxyService::class.java).setAction(ProxyService.ACTION_START)
            if (Build.VERSION.SDK_INT >= 26) startForegroundService(intent) else startService(intent)
            proxyStarted = true
            status = Status.PROXY_RUNNING; renderStatus()
            addressView.text = "$host:8788"
            Toast.makeText(this, Lang.t("پروکسی RoutePou در حال شروع است", "RoutePou proxy starting"), Toast.LENGTH_SHORT).show()
            updateButtons(); refreshQr()
        } catch (e: Exception) {
            Toast.makeText(this, e.message ?: Lang.t("شروع پروکسی ناموفق بود", "Starting the proxy failed"), Toast.LENGTH_LONG).show()
        }
    }

    private fun stopProxy() {
        stopService(Intent(this, ProxyService::class.java)); proxyStarted = false
        if (!fullTunnelRequested) status = Status.READY
        updateButtons(); refreshNetworkInfo()
    }

    private fun rotatePairingKey() {
        val wasRunning = proxyStarted
        if (wasRunning) stopProxy()
        getSharedPreferences("routepou", MODE_PRIVATE).edit().remove("access_token").apply()
        pairingToken = getOrCreateToken()
        try { TlsIdentity.regenerate() } catch (ignored: Exception) { }
        fingerprint = loadFingerprint()
        tokenView.text = Lang.t("کلید جفت‌سازی: مخفی · کلید جدید ساخته شد", "Pairing key: hidden · a new key was created")
        refreshQr()
        if (wasRunning) startProxy()
        Toast.makeText(this, Lang.t("کلید جدید ساخته شد؛ RoutePou ویندوز را دوباره جفت کنید.", "A new key was created. Pair RoutePou on Windows again."), Toast.LENGTH_LONG).show()
    }

    private fun enc(value: String) = URLEncoder.encode(value, "UTF-8")

    private fun loadFingerprint(): String = try {
        TlsIdentity.fingerprint()
    } catch (ignored: Exception) { "Fingerprint unavailable" }

    private fun getOrCreateToken(): String {
        val prefs = getSharedPreferences("routepou", MODE_PRIVATE)
        prefs.getString("access_token", null)?.let { return it }
        val bytes = ByteArray(32).also { SecureRandom().nextBytes(it) }
        val value = bytes.joinToString("") { "%02x".format(it) }
        prefs.edit().putString("access_token", value).apply()
        return value
    }

    /**
     * The phone's address on the network the PC can actually reach: a joined Wi-Fi network,
     * the phone's own hotspot, USB tethering or Ethernet.
     *
     * Virtual and mobile-data interfaces are skipped on purpose. A running VPN (tun0 and friends)
     * and the cellular interface also carry private addresses (10.x, 172.x), but the PC cannot
     * reach the phone through them, and the first private address found used to be one of those.
     */
    private fun lanIpv4(): String? = try {
        val candidates = ArrayList<Pair<Int, String>>()
        for (ni in NetworkInterface.getNetworkInterfaces().toList()) {
            if (!ni.isUp || ni.isLoopback || ni.isPointToPoint) continue
            val rank = interfaceRank(ni.name.lowercase())
            if (rank < 0) continue
            for (addr in ni.inetAddresses.toList()) {
                if (addr is Inet4Address && !addr.isLoopbackAddress && addr.isSiteLocalAddress) {
                    val text = addr.hostAddress
                    if (text != null) candidates.add(Pair(rank, text))
                }
            }
        }
        candidates.minByOrNull { it.first }?.second
    } catch (ignored: Exception) { null }

    /** Lower is better; -1 means never use. */
    private fun interfaceRank(name: String): Int = when {
        name.startsWith("ap") || name.startsWith("swlan") || name.startsWith("softap") -> 0
        name.startsWith("wlan") || name.startsWith("wifi") -> 1
        name.startsWith("rndis") || name.startsWith("usb") || name.startsWith("eth") -> 2
        name.startsWith("rmnet") || name.startsWith("ccmni") || name.startsWith("tun") ||
            name.startsWith("ppp") || name.startsWith("tap") || name.startsWith("dummy") ||
            name.startsWith("v4-") || name.startsWith("clat") || name.startsWith("lo") -> -1
        else -> 3
    }

    override fun onResume() { super.onResume(); if (::addressView.isInitialized) refreshNetworkInfo() }
}
