package com.pou.routepou

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Intent
import android.os.Build
import android.os.IBinder

/** Owns the phone-side WireGuard endpoint for the lifetime of Full Tunnel mode. */
class WireGuardService : Service() {
    companion object {
        const val ACTION_START = "com.pou.routepou.WG_START"
        const val EXTRA_IPC = "ipc_config"
        const val EXTRA_UPSTREAM = "upstream_socks5"
        private const val CHANNEL = "routepou_wireguard"
        private const val NOTIFICATION_ID = 42
    }

    private var upstreamMonitor: AndroidUpstreamMonitor? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        createChannel()
        startForeground(NOTIFICATION_ID, notification("Starting WireGuard endpoint"))
        if (intent?.action == ACTION_START) {
            val ipc = intent.getStringExtra(EXTRA_IPC)
            if (ipc.isNullOrBlank()) {
                stopSelf()
                return START_NOT_STICKY
            }
            val upstream = intent.getStringExtra(EXTRA_UPSTREAM).orEmpty()
            WireGuardEngine.start(ipc, upstream).onSuccess {
                val monitor = AndroidUpstreamMonitor(this) { snapshot ->
                    updateNotification("WireGuard active · ${snapshot.userMessage()}")
                }
                upstreamMonitor?.stop()
                upstreamMonitor = monitor
                try {
                    monitor.start()
                    updateNotification("WireGuard endpoint active · ${monitor.snapshot().userMessage()} · ${if (upstream.isBlank()) "default route" else "SOCKS5 upstream"}")
                } catch (error: Exception) {
                    updateNotification("WireGuard active · network monitoring unavailable")
                }
            }.onFailure { error ->
                updateNotification("WireGuard failed: ${error.message ?: "unknown error"}")
                stopSelf()
            }
        }
        return START_NOT_STICKY
    }

    override fun onDestroy() {
        upstreamMonitor?.stop()
        upstreamMonitor = null
        WireGuardEngine.stop()
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun createChannel() {
        if (Build.VERSION.SDK_INT >= 26) {
            val manager = getSystemService(NotificationManager::class.java)
            manager.createNotificationChannel(NotificationChannel(CHANNEL, "RoutePou WireGuard", NotificationManager.IMPORTANCE_LOW))
        }
    }

    private fun notification(message: String): Notification =
        if (Build.VERSION.SDK_INT >= 26) Notification.Builder(this, CHANNEL)
            .setContentTitle("RoutePou Full Tunnel").setContentText(message)
            .setSmallIcon(android.R.drawable.stat_sys_upload_done).setOngoing(true).build()
        else Notification.Builder(this).setContentTitle("RoutePou Full Tunnel").setContentText(message)
            .setSmallIcon(android.R.drawable.stat_sys_upload_done).build()

    private fun updateNotification(message: String) {
        getSystemService(NotificationManager::class.java).notify(NOTIFICATION_ID, notification(message))
    }
}
