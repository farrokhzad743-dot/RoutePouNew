package com.pou.routepou

import java.security.SecureRandom
import java.util.Base64
import org.bouncycastle.crypto.params.X25519PrivateKeyParameters

/**
 * WireGuard key pairs (Curve25519).
 *
 * The cryptography is BouncyCastle's audited X25519 implementation; nothing is hand-rolled here.
 * `X25519PrivateKeyParameters(SecureRandom)` produces a correctly clamped private key, and the
 * public key is the X25519 base-point product, exactly what `wg genkey | wg pubkey` yields.
 */
object RoutePouWgKeys {
    private fun b64(bytes: ByteArray): String = Base64.getEncoder().encodeToString(bytes)

    fun generate(): RoutePouWgConfig.Keys {
        val random = SecureRandom()
        val server = X25519PrivateKeyParameters(random)
        val client = X25519PrivateKeyParameters(random)
        return RoutePouWgConfig.Keys(
            serverPrivateKey = b64(server.encoded),
            serverPublicKey = b64(server.generatePublicKey().encoded),
            clientPrivateKey = b64(client.encoded),
            clientPublicKey = b64(client.generatePublicKey().encoded),
        )
    }
}
