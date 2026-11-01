package com.pou.routepou.pairing

import java.util.Base64

/** WireGuard addressing contract shared with the Go endpoint and Windows client. */
object RoutePouWgConfig {
    const val SERVER_TUNNEL_IP = "10.13.37.1"
    const val CLIENT_TUNNEL_IP = "10.13.37.2"
    const val MTU = 1420
    const val DEFAULT_PORT = 51820
    const val DEFAULT_DNS = "1.1.1.1"

    data class Keys(
        val serverPrivateKey: String,
        val serverPublicKey: String,
        val clientPrivateKey: String,
        val clientPublicKey: String,
    )

    fun serverIpc(keys: Keys, port: Int = DEFAULT_PORT): String {
        require(port in 1..65535)
        return "private_key=${toHex(keys.serverPrivateKey)}\n" +
            "listen_port=$port\n" +
            "public_key=${toHex(keys.clientPublicKey)}\n" +
            "allowed_ip=$CLIENT_TUNNEL_IP/32\n"
    }

    fun clientIpc(keys: Keys, endpoint: String, port: Int = DEFAULT_PORT): String {
        require(endpoint.matches(Regex("^[0-9.]+$"))) { "Endpoint must be an IPv4 address" }
        require(port in 1..65535)
        return "private_key=${toHex(keys.clientPrivateKey)}\n" +
            "public_key=${toHex(keys.serverPublicKey)}\n" +
            "endpoint=$endpoint:$port\n" +
            "allowed_ip=0.0.0.0/0\n" +
            "persistent_keepalive_interval=25\n"
    }

    fun toHex(base64: String): String {
        val bytes = Base64.getDecoder().decode(base64)
        require(bytes.size == 32) { "WireGuard key must be 32 bytes" }
        return bytes.joinToString("") { "%02x".format(it.toInt() and 0xff) }
    }
}
