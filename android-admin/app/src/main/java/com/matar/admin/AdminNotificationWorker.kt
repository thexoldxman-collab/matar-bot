package com.matar.admin

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.util.concurrent.TimeUnit

class AdminNotificationWorker(context: Context, params: WorkerParameters) : CoroutineWorker(context, params) {
    override suspend fun doWork(): Result = withContext(Dispatchers.IO) {
        val context = applicationContext
        val token = AdminSessionStore.token(context) ?: return@withContext Result.success()
        val preferences = AdminApi.loadNotifications(token) ?: emptyMap()

        if (!AdminApi.isServerHealthy()) {
            if (preferences["bot_offline"] == true && !AdminSessionStore.offlineNotified(context)) {
                notifyAdminEvent("تعذر الاتصال ببوت مطر", "سيتم إعادة المحاولة تلقائياً عند عودة الاتصال.", 2_100_001)
                AdminSessionStore.setOfflineNotified(context, true)
            }
            return@withContext Result.retry()
        }
        AdminSessionStore.setOfflineNotified(context, false)

        val operations = AdminApi.loadOperations(token) ?: return@withContext Result.retry()
        val auditItems = AdminApi.loadAudit(token)
        val currentIds = operations.map { "${it.typeKey}:${it.id}" }.toSet()
        val previousIds = AdminSessionStore.seenOperationIds(context)
        if (previousIds == null) {
            AdminSessionStore.saveSeenOperationIds(context, currentIds)
            auditItems?.maxOfOrNull { it.id }?.let { AdminSessionStore.saveLastAuditId(context, it) }
            return@withContext Result.success()
        }

        operations.filter { "${it.typeKey}:${it.id}" !in previousIds }.forEach { item ->
            val preferenceKey = if (item.typeKey == "withdraw") "withdraw_new" else "charge_new"
            if (preferences[preferenceKey] == true) notifyNewOperation(item)
        }
        AdminSessionStore.saveSeenOperationIds(context, currentIds)

        if (auditItems != null && auditItems.isNotEmpty()) {
            val previousAuditId = AdminSessionStore.lastAuditId(context)
            if (previousAuditId == null) {
                AdminSessionStore.saveLastAuditId(context, auditItems.maxOf { it.id })
            } else {
                auditItems.filter { it.id > previousAuditId }.sortedBy { it.id }.take(5).forEach { entry ->
                    val action = entry.action
                    val details = entry.details
                    val category = when {
                        (action.contains("خطأ") || action.contains("فشل") || details.contains("فشل")) && preferences["financial_error"] == true ->
                            "خطأ أو فشل مالي" to ("${action}: ${details}")
                        (action.contains("مشرف") || action.contains("صلاحيات")) && preferences["moderator_actions"] == true ->
                            "إجراء إداري للمشرفين" to ("${action}: ${details}")
                        action.contains("إحالة") && preferences["referrals"] == true ->
                            "تحديث الإحالات" to ("${action}: ${details}")
                        (action.contains("مساعد") || action.contains("ذكاء") || action.contains("AI")) && preferences["ai_decisions"] == true ->
                            "قرار المساعد الذكي" to ("${action}: ${details}")
                        else -> null
                    }
                    if (category != null) notifyAdminEvent(category.first, category.second.take(500), (2_200_000 + (entry.id % 100_000)).toInt())
                }
                AdminSessionStore.saveLastAuditId(context, maxOf(previousAuditId, auditItems.maxOf { it.id }))
            }
        }
        Result.success()
    }

    private fun notifyNewOperation(item: QueueItem) {
        val title = if (item.typeKey == "withdraw") "طلب سحب جديد" else "طلب شحن جديد"
        val message = "الطلب #${item.id}\nالمبلغ: ${item.amount}\nالمستخدم: ${item.user}\nافتح تطبيق مطر للإدارة لمراجعته."
        val id = item.id + if (item.typeKey == "withdraw") 1_000_000 else 0
        notifyAdminEvent(title, message, id)
    }

    private fun notifyAdminEvent(title: String, message: String, notificationId: Int) {
        val context = applicationContext
        val channelId = "matar_admin_operations"
        val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            manager.createNotificationChannel(
                NotificationChannel(channelId, "تنبيهات إدارة مطر", NotificationManager.IMPORTANCE_HIGH)
            )
        }
        val intent = Intent(context, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
        }
        val pendingIntent = PendingIntent.getActivity(
            context, notificationId, intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        val notification = NotificationCompat.Builder(context, channelId)
            .setSmallIcon(R.drawable.ic_matar_admin)
            .setContentTitle(title)
            .setContentText(message.take(180))
            .setStyle(NotificationCompat.BigTextStyle().bigText(message))
            .setContentIntent(pendingIntent)
            .setAutoCancel(true)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .build()
        try {
            NotificationManagerCompat.from(context).notify(notificationId, notification)
        } catch (_: SecurityException) {
            // The operating system blocks notifications until the user grants permission.
        }
    }
}

object AdminNotificationScheduler {
    private const val WORK_NAME = "matar_admin_background_notifications"

    fun schedule(context: Context) {
        val constraints = Constraints.Builder()
            .setRequiredNetworkType(NetworkType.CONNECTED)
            .build()
        val request = PeriodicWorkRequestBuilder<AdminNotificationWorker>(15, TimeUnit.MINUTES)
            .setConstraints(constraints)
            .build()
        WorkManager.getInstance(context).enqueueUniquePeriodicWork(
            WORK_NAME,
            ExistingPeriodicWorkPolicy.UPDATE,
            request
        )
    }

    fun cancel(context: Context) {
        WorkManager.getInstance(context).cancelUniqueWork(WORK_NAME)
    }
}
