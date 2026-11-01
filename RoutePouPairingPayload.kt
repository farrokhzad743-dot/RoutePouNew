package com.pou.routepou.pairing

import android.util.Base64
import org.json.JSONObject

/** Versioned QR contract. The QR carries a per-session client private key: treat it as a secret. */
data class RoutePouPairingPayload(
    val host: String,
    val port: Int,
    val serverPublicKey: String,
    val clientPrivateKey: String,
    val dns: String = RoutePouWgConfig.DEFAULT_DNS,
    val issuedAt: Long = System.currentTimeMillis() / 1000,
) {
    fun encode(): String {
        require(host.matches(Regex("^[0-9.]+$")))
        require(port in 1..65535)
        val json = JSONObject()
            .put("v", 1).put("mode", "wireguard").put("host", host)
            .put("port", port).put("issuedAt", issuedAt)
            .put("wg", JSONObject()
                .put("serverPublicKey", serverPublicKey)
                .put("clientPrivateKey", clientPrivateKey)
                .put("allowedIps", "0.0.0.0/0")
                .put("endpointPort", port).put("dns", dns))
        val encoded = Base64.encodeToString(
            json.toString().toByteArray(Charsets.UTF_8),
            Base64.URL_SAFE or Base64.NO_WRAP or Base64.NO_PADDING,
        )
        return "routepou://p/$encoded"
    }

    companion object {
        const val TTL_SECONDS = 300L
        const val CLOCK_SKEW_SECONDS = 60L
        private val KEY_REGEX = Regex("^[A-Za-z0-9+/]{42}[AEIMQUYcgkosw480]=$")

        fun decode(value: String): RoutePouPairingPayload {
            require(value.startsWith("routepou://p/")) { "Unsupported RoutePou QR scheme" }
            val encoded = value.removePrefix("routepou://p/")
            require(encoded.isNotBlank() && encoded.length < 4096) { "Invalid pairing payload length" }
            val root = JSONObject(
                String(Base64.decode(encoded, Base64.URL_SAFE or Base64.NO_WRAP), Charsets.UTF_8),
            )
            require(root.optInt("v") == 1 && root.optString("mode") == "wireguard") {
                "Unsupported pairing version or mode"
            }
            val host = root.getString("host")
            require(host.matches(Regex("^[0-9.]+$"))) { "Invalid IPv4 address" }
            val port = root.getInt("port")
            require(port in 1..65535) { "Invalid endpoint port" }
            val issuedAt = root.getLong("issuedAt")
            val now = System.currentTimeMillis() / 1000
            require(issuedAt <= now + CLOCK_SKEW_SECONDS) { "Pairing QR issue time is in the future" }
            require(now - issuedAt <= TTL_SECONDS) { "Pairing QR expired; generate a new QR on the phone" }
            val wg = root.getJSONObject("wg")
            val server = wg.getString("serverPublicKey")
            val client = wg.getString("clientPrivateKey")
            require(server.matches(KEY_REGEX) && client.matches(KEY_REGEX)) { "Invalid WireGuard key" }
            require(wg.getInt("endpointPort") == port) { "Port mismatch" }
            return RoutePouPairingPayload(
                host, port, server, client,
                wg.optString("dns", RoutePouWgConfig.DEFAULT_DNS), issuedAt,
            )
        }
    }
}
