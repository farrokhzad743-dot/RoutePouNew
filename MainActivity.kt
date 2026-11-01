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
        val page = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(20), dp(18), dp(20), dp(28))
            setBackgroundColor(bg)
        }

        val header = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
        }
        val brand = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; layoutParams = LinearLayout.LayoutParams(0, -2, 1f) }
        brand.addView(text("RoutePou", 29f, Color.WHITE, true))
        brand.addView(text("PHONE  →  WINDOWS", 11f, muted, true).apply { letterSpacing = .16f })
        val themeButton = secondaryButton(if (darkMode) "حالت روشن" else "حالت تاریک") {
            getSharedPreferences("routepou", MODE_PRIVATE).edit().putBoolean("dark_mode", !darkMode).apply()
            applyPalette(); window.statusBarColor = bg; window.navigationBarColor = bg; buildScreen(); refreshQr()
        }
        header.addView(brand)
        header.addView(themeButton, LinearLayout.LayoutParams(-2, dp(42)).apply { marginEnd = dp(8) })
        val badge = text("BETA", 10f, Color.WHITE, true).apply {
            setPadding(dp(12), dp(7), dp(12), dp(7)); background = rounded(accent, 30)
        }
        header.addView(badge)
        page.addView(header)
        page.addView(space(22))

        val hero = cardLayout()
        hero.setPadding(dp(18), dp(18), dp(18), dp(18))
        hero.addView(text("وضعیت اتصال", 13f, muted, true))
        page.addView(hero)
        val statusRow = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL }
        val dot = View(this).apply { background = rounded(accent, 50); layoutParams = LinearLayout.LayoutParams(dp(9), dp(9)).apply { marginEnd = dp(9) } }
        statusTitle = text("آماده اتصال", 20f, Color.WHITE, true)
        statusRow.addView(dot); statusRow.addView(statusTitle)
        hero.addView(space(8)); hero.addView(statusRow)
        statusDetail = text("برای شروع، هات‌اسپات گوشی را روشن کنید.", 12f, muted)
        hero.addView(statusDetail)
        hero.addView(space(16))

        val stats = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        stats.addView(infoTile("شبکه گوشی", "Hotspot", 1f))
        stats.addView(spaceWidth(10))
        stats.addView(infoTile("پورت سرویس", "8788", 1f))
        hero.addView(stats)
        hero.addView(space(10))
        hero.addView(text("نشانی شبکه", 11f, muted, true))
        addressView = text("در حال بررسی شبکه…", 13f, Color.WHITE)
        hero.addView(addressView)
        page.addView(space(14))

        val modeCard = cardLayout().apply { setPadding(dp(18), dp(17), dp(18), dp(17)) }
        modeCard.addView(text("اتصال سریع با QR", 18f, Color.WHITE, true))
        modeCard.addView(space(5))
        modeCard.addView(text("هات‌اسپات گوشی را روشن کنید، اشتراک‌گذاری را شروع کنید و QR را با دوربین RoutePou ویندوز اسکن کنید.", 12f, muted))
        modeCard.addView(space(13))
        proxyStartButton = primaryButton("شروع اشتراک‌گذاری") { startProxy() }
        modeCard.addView(proxyStartButton, matchWrap())
        modeCard.addView(space(8))
        proxyStopButton = secondaryButton("توقف اشتراک‌گذاری") { stopProxy() }
        modeCard.addView(proxyStopButton, matchWrap())
        modeCard.addView(space(12))
        val advancedPanel = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            visibility = View.GONE
        }
        advancedPanel.addView(text("تنظیمات پیشرفته · آزمایشی", 14f, Color.WHITE, true))
        advancedPanel.addView(space(7))
        advancedPanel.addView(text("SOCKS5 محلی VPN گوشی (اختیاری)", 12f, Color.WHITE, true))
        upstreamInput = EditText(this).apply {
            hint = "127.0.0.1:10808"
            setSingleLine(true)
            textSize = 13f
            setTextColor(if (darkMode) Color.WHITE else Color.rgb(42, 25, 34))
            setHintTextColor(muted)
            setPadding(dp(12), dp(8), dp(12), dp(8))
            background = rounded(if (darkMode) Color.rgb(43, 25, 36) else Color.rgb(242, 232, 238), 12)
            inputType = android.text.InputType.TYPE_CLASS_TEXT
        }
        advancedPanel.addView(upstreamInput, matchWrap())
        advancedPanel.addView(space(8))
        tunnelStartButton = primaryButton("راه‌اندازی تونل کامل WireGuard") { startFullTunnel() }
        advancedPanel.addView(tunnelStartButton, matchWrap())
        advancedPanel.addView(space(7))
        tunnelStopButton = secondaryButton("توقف تونل کامل") { stopFullTunnel() }
        advancedPanel.addView(tunnelStopButton, matchWrap())
        modeCard.addView(advancedPanel)
        val advancedToggle = secondaryButton("نمایش تنظیمات پیشرفته") {
            val show = advancedPanel.visibility != View.VISIBLE
            advancedPanel.visibility = if (show) View.VISIBLE else View.GONE
        }
        modeCard.addView(space(9))
        modeCard.addView(advancedToggle, matchWrap())
        page.addView(modeCard)
        page.addView(space(14))

        val pairingCard = cardLayout().apply { setPadding(dp(18), dp(17), dp(18), dp(17)) }
        pairingCard.addView(text("۱ · اسکن برای اتصال ویندوز", 17f, Color.WHITE, true))
        pairingCard.addView(space(5))
        pairingCard.addView(text("پس از شروع اشتراک‌گذاری، همین QR را با دوربین ویندوز اسکن کنید. نیازی به واردکردن IP یا کلید نیست؛ QR را محرمانه نگه دارید.", 12f, muted))
        pairingCard.addView(space(13))
        qrView = ImageView(this).apply {
            setBackgroundColor(Color.WHITE)
            setPadding(dp(12), dp(12), dp(12), dp(12))
            scaleType = ImageView.ScaleType.FIT_CENTER
            contentDescription = "کد QR امن اتصال RoutePou به ویندوز"
        }
        val qrFrame = LinearLayout(this).apply { gravity = Gravity.CENTER; setPadding(0, dp(4), 0, dp(12)) }
        qrFrame.addView(qrView, LinearLayout.LayoutParams(dp(220), dp(220)))
        pairingCard.addView(qrFrame)
        tokenView = text("کلید جفت‌سازی: مخفی", 10f, muted)
        pairingCard.addView(tokenView)
        pairingCard.addView(space(10))
        val rotate = secondaryButton("ساخت کلید جفت‌سازی جدید") { rotatePairingKey() }
        pairingCard.addView(rotate, matchWrap())
        page.addView(pairingCard)
        page.addView(space(14))

        val note = cardLayout().apply { setPadding(dp(16), dp(14), dp(16), dp(14)) }
        note.addView(text("نکته امنیتی", 13f, Color.WHITE, true))
        note.addView(text("نسخه آلفا است. پروکسی فقط ترافیک برنامه‌هایی را عبور می‌دهد که دستی به آن متصل شوند؛ این حالت VPN سراسری گوشی یا ویندوز نیست. برای تونل کامل، عملکرد واقعی و Handshake باید روی دو دستگاه آزمایش شود.", 11f, muted))
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
        textDirection = View.TEXT_DIRECTION_LOCALE
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
        val host = hotspotIpv4()
        addressView.text = host ?: "هات‌اسپات پیدا نشد؛ ابتدا آن را روشن کنید."
        if (!fullTunnelRequested && !proxyStarted) {
            statusTitle.text = if (host == null) "منتظر هات‌اسپات" else "آماده اتصال"
            statusDetail.text = if (host == null) "هات‌اسپات گوشی را روشن و ویندوز را به آن متصل کنید." else "شبکه شناسایی شد؛ یکی از روش‌های اتصال را انتخاب کنید."
        }
        refreshQr()
    }

    private fun refreshQr() {
        if (!::qrView.isInitialized) return
        val host = hotspotIpv4()
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
            val host = hotspotIpv4() ?: error("هات‌اسپات پیدا نشد. آن را روشن کنید و ویندوز را متصل کنید.")
            check(WireGuardEngine.isAvailable()) { "موتور WireGuard داخل APK موجود نیست. ابتدا AAR را بسازید." }
            val keys = RoutePouWgKeys.generate()
            val ipc = RoutePouWgConfig.serverIpc(keys)
            val upstream = RoutePouUpstream.validate(upstreamInput.text.toString())
            val payload = RoutePouPairingPayload(host, RoutePouWgConfig.DEFAULT_PORT, keys.serverPublicKey, keys.clientPrivateKey, RoutePouWgConfig.DEFAULT_DNS).encode()
            val intent = Intent(this, WireGuardService::class.java).setAction(WireGuardService.ACTION_START).putExtra(WireGuardService.EXTRA_IPC, ipc).putExtra(WireGuardService.EXTRA_UPSTREAM, upstream)
            if (Build.VERSION.SDK_INT >= 26) startForegroundService(intent) else startService(intent)
            fullModePayload = payload
            fullTunnelRequested = true
            statusTitle.text = "در حال راه‌اندازی تونل"
            statusDetail.text = "سرویس WireGuard شروع شد؛ QR را در ویندوز وارد کنید. اتصال نهایی هنوز نیازمند Handshake است."
            addressView.text = "$host:${RoutePouWgConfig.DEFAULT_PORT}"
            renderQr(payload); updateButtons()
        } catch (e: Exception) {
            Toast.makeText(this, e.message ?: "راه‌اندازی تونل ناموفق بود", Toast.LENGTH_LONG).show()
            statusTitle.text = "تونل شروع نشد"
            statusDetail.text = e.message ?: "خطای نامشخص"
        }
    }

    private fun stopFullTunnel() {
        stopService(Intent(this, WireGuardService::class.java))
        fullModePayload = ""; fullTunnelRequested = false
        statusTitle.text = "تونل متوقف شد"
        statusDetail.text = "سرویس WireGuard متوقف شده است."
        updateButtons(); refreshNetworkInfo()
    }

    private fun startProxy() {
        try {
            val host = hotspotIpv4() ?: error("ابتدا هات‌اسپات گوشی را روشن کنید.")
            val intent = Intent(this, ProxyService::class.java).setAction(ProxyService.ACTION_START)
            if (Build.VERSION.SDK_INT >= 26) startForegroundService(intent) else startService(intent)
            proxyStarted = true
            statusTitle.text = "پروکسی در حال اجرا"
            statusDetail.text = "TLS روی پورت 8788 فعال می‌شود. ویندوز باید از QR برای جفت‌سازی استفاده کند."
            addressView.text = "$host:8788"
            Toast.makeText(this, "RoutePou proxy starting", Toast.LENGTH_SHORT).show()
            updateButtons(); refreshQr()
        } catch (e: Exception) {
            Toast.makeText(this, e.message ?: "شروع پروکسی ناموفق بود", Toast.LENGTH_LONG).show()
        }
    }

    private fun stopProxy() {
        stopService(Intent(this, ProxyService::class.java)); proxyStarted = false
        if (!fullTunnelRequested) { statusTitle.text = "پروکسی متوقف شد"; statusDetail.text = "برای اتصال دوباره، شروع پروکسی را بزنید." }
        updateButtons(); refreshNetworkInfo()
    }

    private fun rotatePairingKey() {
        val wasRunning = proxyStarted
        if (wasRunning) stopProxy()
        getSharedPreferences("routepou", MODE_PRIVATE).edit().remove("access_token").apply()
        pairingToken = getOrCreateToken()
        try { TlsIdentity.regenerate() } catch (ignored: Exception) { }
        fingerprint = loadFingerprint()
        tokenView.text = "کلید جفت‌سازی: مخفی · کلید جدید ساخته شد"
        refreshQr()
        if (wasRunning) startProxy()
        Toast.makeText(this, "کلید جدید ساخته شد؛ RoutePou ویندوز را دوباره جفت کنید.", Toast.LENGTH_LONG).show()
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

    private fun hotspotIpv4(): String? = try {
        NetworkInterface.getNetworkInterfaces().toList().flatMap { it.inetAddresses.toList() }
            .filterIsInstance<Inet4Address>().filter { !it.isLoopbackAddress }
            .mapNotNull { it.hostAddress }
            .firstOrNull { it.startsWith("192.168.") || it.startsWith("10.") || it.matches(Regex("""172\.(1[6-9]|2[0-9]|3[01])\..*""")) }
    } catch (ignored: Exception) { null }

    override fun onResume() { super.onResume(); if (::addressView.isInitialized) refreshNetworkInfo() }
}
