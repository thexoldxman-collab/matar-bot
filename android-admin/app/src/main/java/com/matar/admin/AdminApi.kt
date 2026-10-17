package com.matar.admin

import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL

data class AdminLoginResult(
    val token: String? = null,
    val displayName: String? = null,
    val role: String? = null,
    val error: String? = null
)

object AdminApi {
    private fun baseUrl(): String = BuildConfig.ADMIN_API_BASE_URL.trimEnd('/')

    fun exchangePairingCode(code: String): AdminLoginResult {
        if (baseUrl().contains("SET-ADMIN-API-URL")) {
            return AdminLoginResult(error = "عنوان خادم الإدارة غير مضبوط بعد.")
        }
        var connection: HttpURLConnection? = null
        return try {
            connection = (URL("${baseUrl()}/api/admin/pairing/exchange").openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"
                connectTimeout = 8000
                readTimeout = 8000
                doOutput = true
                setRequestProperty("Content-Type", "application/json; charset=utf-8")
                setRequestProperty("Accept", "application/json")
            }
            OutputStreamWriter(connection.outputStream, Charsets.UTF_8).use {
                it.write(JSONObject().put("code", code.trim().uppercase().replace("-", "")).toString())
            }
            val status = connection.responseCode
            val stream = if (status in 200..299) connection.inputStream else connection.errorStream
            val body = stream?.let { input ->
                BufferedReader(InputStreamReader(input, Charsets.UTF_8)).use { it.readText() }
            }.orEmpty()
            val json = if (body.isNotBlank()) JSONObject(body) else JSONObject()
            if (status in 200..299) {
                val user = json.optJSONObject("user") ?: JSONObject()
                AdminLoginResult(
                    token = json.optString("access_token").takeIf { it.isNotBlank() },
                    displayName = user.optString("display_name", "مشرف"),
                    role = user.optString("role", "moderator")
                )
            } else {
                val error = when (json.optString("error")) {
                    "invalid_or_expired_code" -> "الرمز غير صحيح أو انتهت صلاحيته. اطلب رمزاً جديداً من البوت."
                    "admin_access_revoked" -> "هذا الحساب لم يعد مخوّلاً للدخول."
                    else -> "تعذر تسجيل الدخول. تأكد من الرمز وصلاحية الحساب."
                }
                AdminLoginResult(error = error)
            }
        } catch (_: Exception) {
            AdminLoginResult(error = "تعذر الاتصال بخادم البوت. قد يحتاج تحديث الخدمة قبل تسجيل الدخول.")
        } finally {
            connection?.disconnect()
        }
    }

    fun logout(token: String) {
        request("POST", "/api/admin/logout", token, null)
    }

    fun saveNotifications(token: String, preferences: Map<String, Boolean>): Boolean {
        val prefs = JSONObject()
        preferences.forEach { (key, value) -> prefs.put(key, value) }
        val payload = JSONObject().put("preferences", prefs)
        val result = request("PUT", "/api/admin/notifications", token, payload)
        return result.first in 200..299
    }

    private fun request(method: String, path: String, token: String, payload: JSONObject?): Pair<Int, String> {
        var connection: HttpURLConnection? = null
        return try {
            connection = (URL("${baseUrl()}$path").openConnection() as HttpURLConnection).apply {
                requestMethod = method
                connectTimeout = 8000
                readTimeout = 8000
                setRequestProperty("Authorization", "Bearer $token")
                setRequestProperty("Accept", "application/json")
                if (payload != null) {
                    doOutput = true
                    setRequestProperty("Content-Type", "application/json; charset=utf-8")
                }
            }
            if (payload != null) {
                OutputStreamWriter(connection.outputStream, Charsets.UTF_8).use { it.write(payload.toString()) }
            }
            val status = connection.responseCode
            val stream = if (status in 200..299) connection.inputStream else connection.errorStream
            val body = stream?.let { input ->
                BufferedReader(InputStreamReader(input, Charsets.UTF_8)).use { it.readText() }
            }.orEmpty()
            status to body
        } catch (_: Exception) {
            -1 to ""
        } finally {
            connection?.disconnect()
        }
    }
}
