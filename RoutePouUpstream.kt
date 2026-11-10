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
        require(value.length <= 64) { Lang.t("آدرس پراکسی بیش از حد طولانی است.", "The proxy address is too long.") }
        require(!value.contains("@") && !value.contains("/") && !value.contains("\\")) {
            Lang.t("فقط قالب host:port پذیرفته می‌شود؛ نام کاربری و رمز پشتیبانی نمی‌شود.", "Only the host:port format is accepted; a user name and password are not supported.")
        }
        val parts = value.split(":")
        require(parts.size == 2) { Lang.t("قالب پراکسی باید مانند 127.0.0.1:10808 باشد.", "The proxy format must look like 127.0.0.1:10808.") }
        val host = parts[0]
        val port = parts[1].toIntOrNull() ?: 0
        require(port in 1..65535) { Lang.t("پورت SOCKS5 معتبر نیست.", "The SOCKS5 port is not valid.") }
        val loopback = try { InetAddress.getByName(host).isLoopbackAddress } catch (ignored: Exception) { false }
        require(loopback && (host == "127.0.0.1" || host == "localhost")) {
            Lang.t("برای امنیت، پراکسی باید روی همین گوشی و آدرس loopback باشد.", "For security the proxy must run on this phone, on a loopback address.")
        }
        return "$host:$port"
    }
}
