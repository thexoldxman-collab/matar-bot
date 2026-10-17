package com.matar.admin

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

object AdminSessionStore {
    private const val PREFS = "matar_admin_secure"
    private const val TOKEN = "session_token"
    private const val SEEN_IDS = "seen_operation_ids"
    private const val SNAPSHOT_READY = "operation_snapshot_ready"

    private fun prefs(context: Context): SharedPreferences? = try {
        val masterKey = MasterKey.Builder(context)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
            .build()
        EncryptedSharedPreferences.create(
            context,
            PREFS,
            masterKey,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
        )
    } catch (_: Exception) {
        null
    }

    fun saveToken(context: Context, token: String) {
        prefs(context)?.edit()?.putString(TOKEN, token)?.apply()
    }

    fun token(context: Context): String? = prefs(context)?.getString(TOKEN, null)

    fun clear(context: Context) {
        prefs(context)?.edit()?.clear()?.apply()
    }

    fun seenOperationIds(context: Context): Set<String>? =
        prefs(context)?.let { p ->
            if (!p.getBoolean(SNAPSHOT_READY, false)) null
            else p.getStringSet(SEEN_IDS, emptySet())?.toSet() ?: emptySet()
        }

    fun saveSeenOperationIds(context: Context, ids: Set<String>) {
        prefs(context)?.edit()
            ?.putStringSet(SEEN_IDS, ids.toSet())
            ?.putBoolean(SNAPSHOT_READY, true)
            ?.apply()
    }
}
