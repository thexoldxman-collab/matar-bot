package com.matar.admin

import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL

data class ModeratorItem(
    val userId: Long,
    val customName: String,
    val permissions: Map<String, Boolean>
)

data class BotButtonItem(val id: Int, val key: String, val text: String, val message: String, val parent: String, val active: Boolean, val requiresSubscription: Boolean)
data class AuditItem(val id: Long, val admin: String, val action: String, val details: String, val createdAt: String)

data class AdminLoginResult(
    val token: String? = null,
    val displayName: String? = null,
    val role: String? = null,
    val permissions: Map<String, Boolean> = emptyMap(),
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
            connection = (URL("${baseUrl()}/api/admin/auth/verify").openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"
                connectTimeout = 8000
                readTimeout = 8000
                doOutput = true
                setRequestProperty("Content-Type", "application/json; charset=utf-8")
                setRequestProperty("Accept", "application/json")
            }
            OutputStreamWriter(connection.outputStream, Charsets.UTF_8).use {
                it.write(JSONObject().put("code", code.trim()).toString())
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
                    token = json.optString("access_token").takeIf { it.isNotBlank() && user.optString("role") in setOf("owner", "moderator") },
                    displayName = if (user.optString("role") == "owner") "مدير البوت" else "مشرف",
                    role = user.optString("role").takeIf { it == "owner" || it == "moderator" },
                    permissions = user.optJSONObject("permissions")?.let { p ->
                        listOf("can_handle_charges", "can_handle_withdraws", "can_send_broadcast",
                            "can_manage_users", "can_view_stats", "can_manage_buttons",
                            "can_manage_moderators", "can_use_ai")
                            .associateWith { p.optBoolean(it, false) }
                    } ?: emptyMap(),
                    error = if (user.optString("role") in setOf("owner", "moderator")) null else "الخادم لم يحدد دور الحساب بشكل صحيح؛ تم رفض الدخول."
                )
            } else {
                val error = when (json.optString("error")) {
                    "invalid_or_expired_code" -> "الرمز غير صحيح أو انتهت صلاحيته. اطلب رمزاً جديداً من البوت."
                    "access_revoked" -> "هذا الحساب لم يعد مخوّلاً للدخول."
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
        request("POST", "/api/admin/auth/logout", token, null)
    }

    fun loadOperations(token: String): List<QueueItem>? {
        val (status, body) = request("GET", "/api/admin/operations", token, null)
        if (status !in 200..299) return null
        return try {
            val items = JSONObject(body).optJSONArray("items") ?: return emptyList()
            buildList {
                for (index in 0 until items.length()) {
                    val item = items.optJSONObject(index) ?: continue
                    val typeKey = item.optString("type", "charge")
                    val claim = item.optJSONObject("claim")
                    val claimOwner = if (claim != null && !claim.isNull("claimed_by")) claim.optLong("claimed_by") else null
                    val baseStatus = item.optString("status", "pending")
                    val visibleStatus = if (claimOwner != null) "مستلم بواسطة $claimOwner" else when (baseStatus) {
                        "pending" -> "بانتظار التنفيذ"
                        "processing" -> "قيد المعالجة"
                        else -> baseStatus
                    }
                    val amount = item.optDouble("amount", 0.0)
                    add(QueueItem(
                        id = item.optInt("id"),
                        type = if (typeKey == "withdraw") "طلب سحب" else "طلب شحن",
                        user = item.optString("user_id", "غير معروف"),
                        amount = String.format(java.util.Locale.ROOT, "%,.0f", amount) + " ل.س",
                        status = visibleStatus,
                        typeKey = typeKey,
                        userId = if (item.isNull("user_id")) null else item.optLong("user_id"),
                        claimOwner = claimOwner,
                        method = item.optString("method", ""),
                        reference = item.optString("reference", ""),
                        claimExpiresAt = claim?.optString("expires_at")
                    ))
                }
            }
        } catch (_: Exception) {
            null
        }
    }

    fun claimOperation(token: String, type: String, id: Int): String? {
        val (status, body) = request("POST", "/api/admin/operations/$type/$id/claim", token, JSONObject())
        if (status in 200..299) return null
        return try {
            when (JSONObject(body).optString("error")) {
                "already_claimed" -> "استلم مشرف آخر هذا الطلب. حدّث القائمة وحاول بطلب آخر."
                "permission_denied" -> "ما عندك صلاحية لتنفيذ هذا النوع من الطلبات."
                "operation_not_found" -> "الطلب لم يعد موجوداً."
                "operation_not_open" -> "الطلب لم يعد متاحاً للاستلام."
                else -> "تعذر استلام الطلب؛ تحقق من اتصال الخادم."
            }
        } catch (_: Exception) {
            "تعذر استلام الطلب؛ تحقق من اتصال الخادم."
        }
    }


    fun releaseOperation(token: String, type: String, id: Int): String? {
        val (status, body) = request("POST", "/api/admin/operations/$type/$id/release", token, JSONObject())
        return if (status in 200..299) null else apiError(body, "تعذر تحرير استلام الطلب.")
    }

    fun cancelOperation(token: String, type: String, id: Int, reason: String): String? {
        val payload = JSONObject().put("reason", reason)
        val (status, body) = request("POST", "/api/admin/operations/$type/$id/cancel", token, payload)
        return if (status in 200..299) null else apiError(body, "تعذر إلغاء الطلب؛ لم يتم تأكيد الإلغاء.")
    }

    fun completeOperation(token: String, type: String, id: Int): String {
        val (status, body) = request("POST", "/api/admin/operations/$type/$id/complete", token, JSONObject())
        return try {
            val json = JSONObject(body)
            json.optString("message").takeIf { it.isNotBlank() }
                ?: if (status in 200..299) "تمت العملية." else "لم يتم تنفيذ العملية؛ لم تتغير الأرصدة."
        } catch (_: Exception) {
            "تعذر الاتصال بالخادم؛ لم يتم تأكيد التنفيذ."
        }
    }

    fun updateModeratorPermissions(token: String, userId: Long, permissions: Map<String, Boolean>): String? {
        val permissionJson = JSONObject()
        permissions.forEach { (key, enabled) -> permissionJson.put(key, enabled) }
        val (status, body) = request("PUT", "/api/admin/moderators/$userId", token, JSONObject().put("permissions", permissionJson))
        return if (status in 200..299) null else apiError(body, "تعذر تعديل صلاحيات المشرف.")
    }

    fun loadButtons(token: String): List<BotButtonItem>? {
        val (status, body) = request("GET", "/api/admin/buttons", token, null)
        if (status !in 200..299) return null
        return try {
            val items = JSONObject(body).optJSONArray("items") ?: return emptyList()
            buildList {
                for (i in 0 until items.length()) {
                    val item = items.optJSONObject(i) ?: continue
                    add(BotButtonItem(item.optInt("id"), item.optString("button_name"),
                        item.optString("button_text"), item.optString("message_text"),
                        item.optString("parent_button"), item.optInt("is_active", 1) == 1 || item.optBoolean("is_active"),
                        item.optInt("requires_subscription", 0) == 1 || item.optBoolean("requires_subscription")))
                }
            }
        } catch (_: Exception) { null }
    }

    fun updateButton(token: String, buttonId: Int, buttonText: String, messageText: String,
                     requiresSubscription: Boolean, active: Boolean): String? {
        val payload = JSONObject().put("button_text", buttonText).put("message_text", messageText)
            .put("requires_subscription", requiresSubscription).put("is_active", active)
        val (status, body) = request("PUT", "/api/admin/buttons/$buttonId", token, payload)
        return if (status in 200..299) null else apiError(body, "تعذر حفظ الزر.")
    }

    fun loadDashboard(token: String): Map<String, Int>? {
        val (status, body) = request("GET", "/api/admin/dashboard", token, null)
        if (status !in 200..299) return null
        return try {
            val stats = JSONObject(body).optJSONObject("stats") ?: return null
            listOf("users", "pending_charges", "pending_withdraws", "moderators", "open_tickets")
                .associateWith { stats.optInt(it, 0) }
        } catch (_: Exception) { null }
    }

    fun loadAudit(token: String): List<AuditItem>? {
        val (status, body) = request("GET", "/api/admin/audit", token, null)
        if (status !in 200..299) return null
        return try {
            val items = JSONObject(body).optJSONArray("items") ?: return emptyList()
            buildList {
                for (i in 0 until items.length()) {
                    val item = items.optJSONObject(i) ?: continue
                    add(AuditItem(item.optLong("id"), item.optString("display_name"),
                        item.optString("action_type"), item.optString("details"), item.optString("created_at")))
                }
            }
        } catch (_: Exception) { null }
    }

    fun loadNotifications(token: String): Map<String, Boolean>? {
        val (status, body) = request("GET", "/api/admin/notifications", token, null)
        if (status !in 200..299) return null
        return try {
            val prefs = JSONObject(body).optJSONObject("preferences") ?: return null
            buildMap {
                for (key in listOf("charge_new", "withdraw_new", "financial_error", "moderator_actions", "referrals", "bot_offline", "ai_decisions")) {
                    put(key, prefs.optBoolean(key, false))
                }
            }
        } catch (_: Exception) {
            null
        }
    }

    fun saveNotifications(token: String, preferences: Map<String, Boolean>): Boolean {
        val prefs = JSONObject()
        preferences.forEach { (key, value) -> prefs.put(key, value) }
        val payload = JSONObject().put("preferences", prefs)
        val result = request("PUT", "/api/admin/notifications", token, payload)
        return result.first in 200..299
    }


    fun loadModerators(token: String): List<ModeratorItem>? {
        val (status, body) = request("GET", "/api/admin/moderators", token, null)
        if (status !in 200..299) return null
        return try {
            val items = JSONObject(body).optJSONArray("items") ?: return emptyList()
            buildList {
                for (index in 0 until items.length()) {
                    val item = items.optJSONObject(index) ?: continue
                    val source = item.optJSONObject("permissions") ?: JSONObject()
                    val permissions = buildMap {
                        for (key in listOf(
                            "can_handle_charges", "can_handle_withdraws", "can_send_broadcast",
                            "can_manage_users", "can_view_stats", "can_manage_buttons",
                            "can_manage_moderators", "can_use_ai"
                        )) put(key, source.optBoolean(key, false))
                    }
                    add(ModeratorItem(
                        userId = item.optLong("user_id"),
                        customName = item.optString("custom_name", ""),
                        permissions = permissions
                    ))
                }
            }
        } catch (_: Exception) {
            null
        }
    }

    fun addModerator(token: String, userId: Long, name: String, permissions: Map<String, Boolean>): String? {
        val permissionJson = JSONObject()
        permissions.forEach { (key, enabled) -> permissionJson.put(key, enabled) }
        val payload = JSONObject()
            .put("user_id", userId)
            .put("custom_name", name)
            .put("permissions", permissionJson)
        val (status, body) = request("POST", "/api/admin/moderators", token, payload)
        return if (status in 200..299) null else apiError(body, "تعذر إضافة المشرف؛ تحقق من المعرف والصلاحيات.")
    }

    fun deleteModerator(token: String, userId: Long): String? {
        val (status, body) = request("DELETE", "/api/admin/moderators/$userId", token, null)
        return if (status in 200..299) null else apiError(body, "تعذر حذف المشرف.")
    }

    fun broadcastMessage(token: String, message: String, audience: String): String? {
        val payload = JSONObject().put("message", message).put("audience", audience)
        val (status, body) = request("POST", "/api/admin/messages/broadcast", token, payload)
        if (status !in 200..299) return apiError(body, "تعذر إرسال الرسالة.")
        return try {
            val json = JSONObject(body)
            "تم الإرسال إلى ${json.optInt("sent")} حساب، وفشل ${json.optInt("failed")}."
        } catch (_: Exception) {
            "تم إرسال الطلب إلى الخادم."
        }
    }

    private fun apiError(body: String, fallback: String): String {
        return try {
            when (JSONObject(body).optString("error")) {
                "permission_denied" -> "حسابك لا يملك صلاحية تنفيذ هذا الإجراء."
                "moderator_exists" -> "هذا المستخدم مضاف كمشرف من قبل."
                "invalid_user_id" -> "معرف تيليغرام غير صالح."
                "owner_required_for_privileged_permissions" -> "منح هذه الصلاحية الحساسة متاح للمدير فقط."
                "protected_moderator" -> "لا يمكن حذف حساب المدير أو إزالة صلاحيتك كمشرف مفوّض."
                else -> JSONObject(body).optString("message").takeIf { it.isNotBlank() } ?: fallback
            }
        } catch (_: Exception) {
            fallback
        }
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
