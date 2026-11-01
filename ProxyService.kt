package com.pou.routepou

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Intent
import android.os.Build
import android.os.IBinder
import android.util.Log
import java.io.BufferedInputStream
import java.io.BufferedOutputStream
import java.io.InputStream
import javax.net.ssl.SSLContext
import javax.net.ssl.SSLServerSocket
import java.net.ServerSocket
import java.net.Socket
import java.net.InetSocketAddress
import java.util.concurrent.Executors

class ProxyService : Service() {
    companion object { const val ACTION_START = "com.pou.routepou.START"; const val PORT = 8787; const val TLS_PORT = 8788; private const val CHANNEL = "routepou_proxy"
        const val EXTRA_TOKEN = "token" }
    @Volatile private var running = false
    @Volatile private var accessToken: String = ""
    private val bytesRelayedCounter = java.util.concurrent.atomic.AtomicLong()
    private val bytesRelayed: Long get() = bytesRelayedCounter.get()
    @Volatile private var connections: Int = 0
    private var server: ServerSocket? = null
    private val pool = Executors.newCachedThreadPool()

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        createChannel()
        val notification: Notification = if (Build.VERSION.SDK_INT >= 26) Notification.Builder(this, CHANNEL)
            .setContentTitle("RoutePou is active").setContentText("Encrypted TLS proxy listening on port $TLS_PORT")
            .setSmallIcon(android.R.drawable.stat_sys_upload_done).build()
        else Notification.Builder(this).setContentTitle("RoutePou is active").setContentText("Encrypted proxy on port $TLS_PORT")
            .setSmallIcon(android.R.drawable.stat_sys_upload_done).build()
        startForeground(1, notification)
        accessToken = getSharedPreferences("routepou", MODE_PRIVATE).getString("access_token", "") ?: ""
        if (!running) startServer()
        return START_STICKY
    }

    private fun createChannel() {
        if (Build.VERSION.SDK_INT >= 26) {
            val nm = getSystemService(NotificationManager::class.java)
            nm.createNotificationChannel(NotificationChannel(CHANNEL, "RoutePou proxy", NotificationManager.IMPORTANCE_LOW))
        }
    }

    private fun startServer() {
        running = true
        pool.execute {
            try {
                val context = TlsIdentity.sslContext()
                val tlsServer = context.serverSocketFactory.createServerSocket() as SSLServerSocket
                tlsServer.enabledProtocols = arrayOf("TLSv1.3", "TLSv1.2")
                tlsServer.reuseAddress = true
                tlsServer.bind(InetSocketAddress("0.0.0.0", TLS_PORT))
                server = tlsServer
                while (running) {
                    val client = server?.accept() ?: break
                    if (client is javax.net.ssl.SSLSocket) client.enabledProtocols = arrayOf("TLSv1.3", "TLSv1.2")
                    pool.execute { handle(client) }
                }
            } catch (e: Exception) { Log.e("RoutePou", "TLS proxy stopped: ${e.message}") }
            finally { running = false }
        }
    }

    private fun handle(client: Socket) {
        try {
            client.soTimeout = 30000
            client.tcpNoDelay = true
            val input = BufferedInputStream(client.getInputStream())
            val output = BufferedOutputStream(client.getOutputStream())
            val firstByte = input.read()
            if (firstByte < 0) return
            if (firstByte == 0x05) {
                handleSocks5(client, input, output)
                return
            }
            val header = readHeader(input, firstByte) ?: return
            if (accessToken.isBlank() || !authorized(header)) {
                output.write("HTTP/1.1 407 Proxy Authentication Required\r\nProxy-Authenticate: Basic realm=\"RoutePou\"\r\nConnection: close\r\nContent-Length: 0\r\n\r\n".toByteArray()); output.flush(); return
            }
            synchronized(this) { connections++ }
            if (header.startsWith("GET http://routepou.local/health ", true)) {
                val body = "{\"status\":\"ok\",\"connections\":$connections,\"bytes\":$bytesRelayed}"
                output.write("HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: ${body.toByteArray().size}\r\nConnection: close\r\n\r\n$body".toByteArray()); output.flush(); return
            }
            val requestLine = header.substringBefore("\r\n")
            val parts = requestLine.split(" ")
            if (parts.size < 3) return
            val method = parts[0].uppercase()
            val target = parts[1]
            if (method == "CONNECT") {
                val host = target.substringBeforeLast(":")
                val port = target.substringAfterLast(":", "443").toIntOrNull() ?: 443
                val remote = Socket().apply { connect(InetSocketAddress(host, port), 15000); soTimeout = 0 }
                output.write("HTTP/1.1 200 Connection Established\r\n\r\n".toByteArray()); output.flush()
                relay(client, remote, input)
            } else {
                val uri = java.net.URI(target)
                val host = uri.host ?: header.lineSequence().firstOrNull { it.startsWith("Host:", true) }?.substringAfter(":")?.trim()
                    ?: throw IllegalArgumentException("Missing host")
                val port = if (uri.port > 0) uri.port else 80
                val path = (uri.rawPath.ifBlank { "/" }) + (uri.rawQuery?.let { "?$it" } ?: "")
                val remote = Socket().apply { connect(InetSocketAddress(host, port), 15000) }
                val rewritten = header.replaceFirst(Regex("^\\S+\\s+\\S+\\s+"), "$method $path ")
                    .replace(Regex("(?im)^Proxy-Connection:.*\\r?\\n"), "")
                    .replace(Regex("(?im)^X-RoutePou-Key:.*\\r?\\n"), "")
                remote.getOutputStream().write(rewritten.toByteArray(Charsets.ISO_8859_1))
                relay(client, remote, input)
            }
        } catch (ignored: Exception) { } finally { try { client.close() } catch (ignored: Exception) { } }
    }

    private fun authorized(header: String): Boolean {
        val supplied = Regex("(?im)^X-RoutePou-Key:\\s*(.+?)\\s*$").find(header)?.groupValues?.get(1) ?: return false
        return java.security.MessageDigest.isEqual(supplied.toByteArray(), accessToken.toByteArray())
    }

    private fun handleSocks5(client: Socket, input: BufferedInputStream, output: BufferedOutputStream) {
        // SOCKS5 username/password authentication (RFC 1929). The pairing token is the password.
        val methodCount = input.read()
        if (methodCount !in 1..16) return
        val methods = ByteArray(methodCount)
        if (input.read(methods) != methodCount) return
        if (methods.none { (it.toInt() and 0xff) == 0x02 }) {
            output.write(byteArrayOf(0x05, 0xff.toByte())); output.flush(); return
        }
        output.write(byteArrayOf(0x05, 0x02)); output.flush()
        if (input.read() != 0x01) return
        val userLen = input.read(); if (userLen !in 1..255) return
        val username = ByteArray(userLen); if (input.read(username) != userLen) return
        val passLen = input.read(); if (passLen !in 1..255) return
        val password = ByteArray(passLen); if (input.read(password) != passLen) return
        val valid = String(username, Charsets.UTF_8) == "routepou" &&
            java.security.MessageDigest.isEqual(password, accessToken.toByteArray(Charsets.UTF_8))
        output.write(byteArrayOf(0x01, if (valid) 0x00 else 0x01)); output.flush()
        if (!valid) return
        val version = input.read(); val command = input.read(); val reserved = input.read(); val atyp = input.read()
        if (version != 0x05 || command != 0x01 || reserved != 0x00) {
            output.write(byteArrayOf(0x05, 0x07, 0x00, 0x01, 0, 0, 0, 0, 0, 0)); output.flush(); return
        }
        val host = when (atyp) {
            0x01 -> { val b = ByteArray(4); if (input.read(b) != 4) return; b.joinToString(".") { (it.toInt() and 255).toString() } }
            0x03 -> { val n = input.read(); if (n !in 1..255) return; val b = ByteArray(n); if (input.read(b) != n) return; String(b, Charsets.UTF_8) }
            0x04 -> { val b = ByteArray(16); if (input.read(b) != 16) return; java.net.InetAddress.getByAddress(b).hostAddress ?: return }
            else -> { output.write(byteArrayOf(0x05, 0x08, 0, 1, 0, 0, 0, 0, 0, 0)); output.flush(); return }
        }
        val portBytes = ByteArray(2); if (input.read(portBytes) != 2) return
        val port = ((portBytes[0].toInt() and 255) shl 8) or (portBytes[1].toInt() and 255)
        try {
            val remote = Socket().apply { connect(InetSocketAddress(host, port), 15000); soTimeout = 0 }
            output.write(byteArrayOf(0x05, 0x00, 0x00, 0x01, 0, 0, 0, 0, 0, 0)); output.flush()
            relay(client, remote, input)
        } catch (ignored: Exception) {
            output.write(byteArrayOf(0x05, 0x04, 0x00, 0x01, 0, 0, 0, 0, 0, 0)); output.flush()
        }
    }

    private fun readHeader(input: BufferedInputStream, firstByte: Int): String? {
        val bytes = java.io.ByteArrayOutputStream(); bytes.write(firstByte); var state = 0
        while (bytes.size() < 32768) {
            val b = input.read(); if (b < 0) return null; bytes.write(b)
            state = when { state == 0 && b == 13 -> 1; state == 1 && b == 10 -> 2; state == 2 && b == 13 -> 3; state == 3 && b == 10 -> 4; b == 13 -> 1; else -> 0 }
            if (state == 4) break
        }
        return bytes.toString("ISO-8859-1")
    }

    private fun relay(a: Socket, b: Socket, bufferedClientInput: InputStream) {
        val done = java.util.concurrent.CountDownLatch(2)
        fun copy(src: Socket, dst: Socket) { try { val buffer = ByteArray(32768); while (true) { val source = if (src === a) bufferedClientInput else src.getInputStream(); val n = source.read(buffer); if (n < 0) break; dst.getOutputStream().write(buffer, 0, n); dst.getOutputStream().flush(); bytesRelayedCounter.addAndGet(n.toLong()) }; dst.shutdownOutput() } catch (ignored: Exception) { } finally { done.countDown() } }
        pool.execute { copy(a, b) }; pool.execute { copy(b, a) }
        done.await()
        try { b.close() } catch (ignored: Exception) { }
    }

    override fun onDestroy() {
        running = false; try { server?.close() } catch (ignored: Exception) { }
        pool.shutdownNow(); stopForeground(STOP_FOREGROUND_REMOVE); super.onDestroy()
    }
    override fun onBind(intent: Intent?): IBinder? = null
}
