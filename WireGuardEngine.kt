package com.pou.routepou

/** Optional bridge to the gomobile-generated Relay WireGuard engine.
 * Reflection keeps ordinary Android UI builds possible without a local NDK;
 * release CI builds and packages relaywg.aar before Gradle.
 */
object WireGuardEngine {
    private const val CLASS_NAME = "relaywg.Relaywg"

    private fun api(): Class<*>? = try { Class.forName(CLASS_NAME) } catch (ignored: Throwable) { null }

    fun isAvailable(): Boolean = api() != null

    fun start(ipcConfig: String, upstreamSocks5: String = ""): Result<Unit> = runCatching {
        validateIpc(ipcConfig)
        val bridge = api() ?: error("WireGuard engine is not packaged in this build")
        if (upstreamSocks5.isBlank()) {
            bridge.getMethod("startEndpoint", String::class.java).invoke(null, ipcConfig)
        } else {
            bridge.getMethod("startEndpointVia", String::class.java, String::class.java)
                .invoke(null, ipcConfig, upstreamSocks5)
        }
        check(isRunning()) { "WireGuard endpoint did not enter running state" }
    }

    fun setUpstream(upstreamSocks5: String): Result<Unit> = runCatching {
        val bridge = api() ?: error("WireGuard engine is not packaged in this build")
        bridge.getMethod("setEndpointUpstream", String::class.java).invoke(null, upstreamSocks5)
    }

    private fun validateIpc(config: String) {
        require(config.isNotBlank() && config.length <= 16_384) { "Invalid WireGuard IPC config size" }
        val keys = setOf("private_key", "listen_port", "public_key", "allowed_ip")
        val fields = config.lineSequence().filter { it.isNotBlank() }.map {
            val i = it.indexOf('='); require(i > 0) { "Malformed IPC line" }
            it.substring(0, i)
        }.toList()
        require(fields.containsAll(keys)) { "WireGuard IPC config is missing required fields" }
        require(fields.size == fields.toSet().size) { "Duplicate WireGuard IPC fields" }
    }

    fun stop(): Result<Unit> = runCatching {
        val api = api() ?: error("WireGuard engine is not packaged in this build")
        api.getMethod("stopEndpoint").invoke(null)
    }

    fun isRunning(): Boolean = try {
        val api = api() ?: return false
        api.getMethod("isRunning").invoke(null) as Boolean
    } catch (ignored: Throwable) { false }

    fun bytesSent(): Long = metric("bytesSent")
    fun bytesReceived(): Long = metric("bytesReceived")
    fun lastHandshakeUnix(): Long = metric("lastHandshakeUnix")

    private fun metric(method: String): Long = try {
        val api = api() ?: return 0L
        (api.getMethod(method).invoke(null) as Number).toLong()
    } catch (ignored: Throwable) { 0L }
}
