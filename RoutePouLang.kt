package com.pou.routepou

import android.content.Context

/**
 * The language of the app: Persian ("fa", the default) or English ("en").
 * The choice is stored in the app's preferences and read again by the screen and by the services,
 * so a message shown from a service uses the same language as the screen.
 */
object Lang {
    @Volatile var code: String = "fa"
    val isFa: Boolean get() = code != "en"

    fun load(context: Context) {
        code = if (context.getSharedPreferences("routepou", Context.MODE_PRIVATE).getString("lang", "fa") == "en") "en" else "fa"
    }

    fun save(context: Context, value: String) {
        code = if (value == "en") "en" else "fa"
        context.getSharedPreferences("routepou", Context.MODE_PRIVATE).edit().putString("lang", code).apply()
    }

    /** Persian text first, English text second. */
    fun t(fa: String, en: String): String = if (code == "en") en else fa
}
