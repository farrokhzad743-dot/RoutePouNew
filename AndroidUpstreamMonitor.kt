package com.pou.routepou

import android.content.Context
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.net.NetworkRequest
import android.os.Build
import java.util.concurrent.atomic.AtomicReference

/** Observes Android's default Internet path used by Relay's outbound sockets.
 * This is deliberately observational: it never changes routes, toggles hotspot,
 * or claims that traffic is forwarded merely because Android has Internet.
 */
class AndroidUpstreamMonitor(context: Context, private val onChanged: (Snapshot) -> Unit) {
    data class Snapshot(
        val available: Boolean,
        val validated: Boolean,
        val transport: String,
        val networkHandle: Long
    ) {
        fun userMessage(): String = when {
            !available -> Lang.t("اتصال اینترنت گوشی در دسترس نیست؛ تونل آماده عبور ترافیک نیست.", "The phone has no internet connection; the tunnel cannot carry traffic.")
            !validated -> Lang.t("شبکه پیدا شد، اما دسترسی اینترنت هنوز تأیید نشده است.", "A network was found, but internet access is not confirmed yet.")
            else -> Lang.t("اینترنت گوشی آماده است؛ عبور واقعی ترافیک باید جداگانه آزمایش شود.", "The phone's internet is ready. Real traffic still has to be tested separately.")
        }
    }

    private val manager = context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
    private val current = AtomicReference(readDefault())
    private var registered = false

    private val callback = object : ConnectivityManager.NetworkCallback() {
        override fun onAvailable(network: Network) = publish()
        override fun onLost(network: Network) = publish()
        override fun onCapabilitiesChanged(network: Network, caps: NetworkCapabilities) = publish()
    }

    fun start() {
        if (registered) return
        registered = true
        try {
            // A broad callback is required because the system default may move
            // between cellular, Wi-Fi, Ethernet, or a user VPN.
            manager.registerNetworkCallback(NetworkRequest.Builder().addCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET).build(), callback)
        } catch (e: Exception) {
            registered = false
            throw e
        }
        publish()
    }

    fun stop() {
        if (!registered) return
        try { manager.unregisterNetworkCallback(callback) } catch (ignored: Exception) { }
        registered = false
    }

    fun snapshot(): Snapshot = current.get()

    private fun publish() {
        val value = readDefault()
        current.set(value)
        onChanged(value)
    }

    private fun readDefault(): Snapshot {
        val network = manager.activeNetwork ?: return Snapshot(false, false, "none", 0L)
        val caps = manager.getNetworkCapabilities(network) ?: return Snapshot(false, false, "unknown", network.networkHandle)
        val hasInternet = caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
        val validated = caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED)
        val transport = when {
            caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) -> "wifi"
            caps.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR) -> "cellular"
            caps.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET) -> "ethernet"
            caps.hasTransport(NetworkCapabilities.TRANSPORT_VPN) -> "vpn"
            else -> "other"
        }
        return Snapshot(hasInternet, hasInternet && validated, transport, network.networkHandle)
    }
}
