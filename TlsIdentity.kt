package com.pou.routepou

import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import java.security.KeyPairGenerator
import java.security.KeyStore
import java.security.MessageDigest
import java.security.SecureRandom
import java.security.spec.ECGenParameterSpec
import java.util.Date
import javax.net.ssl.KeyManagerFactory
import javax.net.ssl.SSLContext
import javax.security.auth.x500.X500Principal

/**
 * Per-installation TLS identity for the proxy listener.
 *
 * The EC key pair and its self-signed certificate are generated inside the Android Keystore the
 * first time they are needed. The private key never leaves the keystore and is unique to this
 * installation, so the certificate fingerprint carried in the pairing QR really identifies this
 * phone. (Earlier alpha builds shipped one shared PKCS#12 file with a password in the source tree,
 * which let anyone holding the APK impersonate any phone.)
 */
object TlsIdentity {
    private const val ALIAS = "routepou_tls_v1"
    private const val PROVIDER = "AndroidKeyStore"
    private const val DAY_MS = 24L * 60 * 60 * 1000

    private fun keyStore(): KeyStore = KeyStore.getInstance(PROVIDER).apply { load(null) }

    @Synchronized
    fun ensure() {
        val ks = keyStore()
        if (ks.containsAlias(ALIAS)) return
        val now = System.currentTimeMillis()
        val spec = KeyGenParameterSpec.Builder(ALIAS, KeyProperties.PURPOSE_SIGN)
            .setAlgorithmParameterSpec(ECGenParameterSpec("secp256r1"))
            .setDigests(KeyProperties.DIGEST_SHA256, KeyProperties.DIGEST_SHA384, KeyProperties.DIGEST_SHA512)
            .setCertificateSubject(X500Principal("CN=routepou.local, O=RoutePou"))
            .setCertificateNotBefore(Date(now - DAY_MS))
            .setCertificateNotAfter(Date(now + 3650L * DAY_MS))
            .build()
        KeyPairGenerator.getInstance(KeyProperties.KEY_ALGORITHM_EC, PROVIDER)
            .apply { initialize(spec) }
            .generateKeyPair()
    }

    /** Upper-case hex SHA-256 of the DER certificate; this is the value Windows pins. */
    @Synchronized
    fun fingerprint(): String {
        ensure()
        val cert = keyStore().getCertificate(ALIAS) ?: error("TLS certificate is unavailable")
        return MessageDigest.getInstance("SHA-256").digest(cert.encoded)
            .joinToString("") { "%02X".format(it.toInt() and 0xff) }
    }

    /** Replaces the key pair; every previously paired Windows PC must scan a new QR. */
    @Synchronized
    fun regenerate() {
        val ks = keyStore()
        if (ks.containsAlias(ALIAS)) ks.deleteEntry(ALIAS)
        ensure()
    }

    @Synchronized
    fun sslContext(): SSLContext {
        ensure()
        val kmf = KeyManagerFactory.getInstance(KeyManagerFactory.getDefaultAlgorithm())
        kmf.init(keyStore(), null)
        return SSLContext.getInstance("TLS").apply { init(kmf.keyManagers, null, SecureRandom()) }
    }
}
