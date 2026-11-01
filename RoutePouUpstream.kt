package com.pou.routepou

import java.net.InetAddress

/** Validates the optional SOCKS5 listener exposed locally by another VPN app.
 * Remote proxies are deliberately rejected: this setting is not a general-purpose
 * proxy credential store and must not become an SSRF/secret-leak surface.
 */
object RoutePouUpstream {
    fun validate(raw: String): String {
        val value = raw.trim()
        if (value.isEmpty()) return ""
        require(value.length <= 64) { "آدرس پراکسی بیش از حد طولانی است." }
        require(!value.contains("@") && !value.contains("/") && !value.contains("\\")) {
            "فقط قالب host:port پذیرفته می‌شود؛ نام کاربری و رمز پشتیبانی نمی‌شود."
        }
        val parts = value.split(":")
        require(parts.size == 2) { "قالب پراکسی باید مانند 127.0.0.1:10808 باشد." }
        val host = parts[0]
        val port = parts[1].toIntOrNull() ?: 0
        require(port in 1..65535) { "پورت SOCKS5 معتبر نیست." }
        val loopback = try { InetAddress.getByName(host).isLoopbackAddress } catch (ignored: Exception) { false }
        require(loopback && (host == "127.0.0.1" || host == "localhost")) {
            "برای امنیت، پراکسی باید روی همین گوشی و آدرس loopback باشد."
        }
        return "$host:$port"
    }
}
