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
        val token = AdminSessionStore.token(applicationContext) ?: return@withContext Result.success()
        val operations = AdminApi.loadOperations(token) ?: return@withContext Result.retry()
        val preferences = AdminApi.loadNotifications(token) ?: emptyMap()
        val currentIds = operations.map { "${it.typeKey}:${it.id}" }.toSet()
        val previousIds = AdminSessionStore.seenOperationIds(applicationContext)
        if (previousIds == null) {
            AdminSessionStore.saveSeenOperationIds(applicationContext, currentIds)
            return@withContext Result.success()
        }

        operations.filter { "${it.typeKey}:${it.id}" !in previousIds }.forEach { item ->
            val preferenceKey = if (item.typeKey == "withdraw") "withdraw_new" else "charge_new"
            if (preferences[preferenceKey] == true) notifyNewOperation(item)
        }
        AdminSessionStore.saveSeenOperationIds(applicationContext, currentIds)
        Result.success()
    }

    private fun notifyNewOperation(item: QueueItem) {
        val context = applicationContext
        val channelId = "matar_admin_operations"
        val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            manager.createNotificationChannel(
                NotificationChannel(channelId, "تنبيهات غرفة العمليات", NotificationManager.IMPORTANCE_HIGH)
            )
        }
        val intent = Intent(context, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
        }
        val pendingIntent = PendingIntent.getActivity(
            context, item.id + if (item.typeKey == "withdraw") 1_000_000 else 0, intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        val title = if (item.typeKey == "withdraw") "طلب سحب جديد" else "طلب شحن جديد"
        val notification = NotificationCompat.Builder(context, channelId)
            .setSmallIcon(R.drawable.ic_matar_admin)
            .setContentTitle(title)
            .setContentText("الطلب #${item.id} • ${item.amount} • المستخدم ${item.user}")
            .setStyle(NotificationCompat.BigTextStyle().bigText("الطلب #${item.id}\nالمبلغ: ${item.amount}\nالمستخدم: ${item.user}\nافتح تطبيق مطر للإدارة لمراجعته."))
            .setContentIntent(pendingIntent)
            .setAutoCancel(true)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .build()
        try {
            NotificationManagerCompat.from(context).notify(item.id + if (item.typeKey == "withdraw") 1_000_000 else 0, notification)
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
