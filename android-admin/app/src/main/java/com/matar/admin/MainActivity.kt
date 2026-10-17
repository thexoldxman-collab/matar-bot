package com.matar.admin

import android.os.Bundle
import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp

private enum class Page(val label: String) {
    HOME("الرئيسية"), ROOM("غرفة العمليات"), USERS("المشرفون"),
    MESSAGES("الرسائل"), BUTTONS("أزرار البوت"), REFERRALS("الإحالات"), CONTENT("نصوص البوت"), SETTINGS("الإعدادات")
}

data class QueueItem(
    val id: Int,
    val type: String,
    val user: String,
    val amount: String,
    val status: String = "بانتظار التنفيذ",
    val typeKey: String = "charge",
    val userId: Long? = null,
    val claimOwner: Long? = null,
    val method: String = "",
    val reference: String = "",
    val claimExpiresAt: String? = null
) {
    val operationKey: String get() = "$typeKey:$id"
}

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { MatarAdminApp() }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun MatarAdminApp() {
    var dark by remember { mutableStateOf<Boolean?>(null) }
    val useDark = dark ?: isSystemInDarkTheme()
    var page by remember { mutableStateOf(Page.HOME) }
    var demoMode by remember { mutableStateOf(true) }
    var connected by remember { mutableStateOf(false) }
    var accessToken by remember { mutableStateOf<String?>(null) }
    var accountRole by remember { mutableStateOf<String?>(null) }
    var accountPermissions by remember { mutableStateOf<Map<String, Boolean>>(emptyMap()) }
    var buttons by remember { mutableStateOf<List<BotButtonItem>>(emptyList()) }
    var buttonMessage by remember { mutableStateOf("") }
    var dashboardStats by remember { mutableStateOf<Map<String, Int>?>(null) }
    var auditItems by remember { mutableStateOf<List<AuditItem>>(emptyList()) }
    var referralSummary by remember { mutableStateOf<ReferralSummary?>(null) }
    var referralMessage by remember { mutableStateOf("") }
    var contentSettings by remember { mutableStateOf<BotContentSettings?>(null) }
    var contentMessage by remember { mutableStateOf("") }
    var connecting by remember { mutableStateOf(false) }
    var savingNotifications by remember { mutableStateOf(false) }
    var liveOperations by remember { mutableStateOf(false) }
    var operationMessage by remember { mutableStateOf("") }
    var notificationMessage by remember { mutableStateOf("") }
    var moderators by remember { mutableStateOf(emptyList<ModeratorItem>()) }
    var moderatorMessage by remember { mutableStateOf("") }
    var sendingMessage by remember { mutableStateOf(false) }
    var sentMessage by remember { mutableStateOf("") }
    val scope = rememberCoroutineScope()
    val appContext = LocalContext.current
    var pairingCode by remember { mutableStateOf("") }
    var loginMessage by remember { mutableStateOf("") }
    var showLogin by remember { mutableStateOf(true) }
    var restoringSession by remember { mutableStateOf(true) }
    var notifications by remember {
        mutableStateOf(mapOf(
            "طلب شحن جديد" to true,
            "طلب سحب جديد" to true,
            "خطأ أو فشل مالي" to true,
            "إجراءات المشرفين" to true,
            "الإحالات والمستحقات" to false,
            "توقف البوت أو انقطاع الاتصال" to true,
            "قرارات المساعد الذكي" to false
        ))
    }
    var queue by remember {
        mutableStateOf(listOf(
            QueueItem(1042, "طلب شحن", "مستخدم تجريبي", "25,000 ل.س"),
            QueueItem(1041, "طلب سحب", "مستخدم تجريبي", "10,000 ل.س"),
            QueueItem(1040, "طلب شحن", "مستخدم تجريبي", "50,000 ل.س")
        ))
    }
    var selectedRequest by remember { mutableStateOf<String?>(null) }
    var actionNote by remember { mutableStateOf("") }
    var showAppearance by remember { mutableStateOf(false) }

    LaunchedEffect(Unit) {
        val savedToken = AdminSessionStore.token(appContext)
        if (!savedToken.isNullOrBlank()) {
            val restored = withContext(Dispatchers.IO) { AdminApi.restoreSession(savedToken) }
            if (restored?.token != null) {
                accessToken = restored.token
                accountRole = restored.role
                accountPermissions = restored.permissions
                dashboardStats = withContext(Dispatchers.IO) { AdminApi.loadDashboard(savedToken) }
                if (restored.role == "owner") referralSummary = withContext(Dispatchers.IO) { AdminApi.loadReferrals(savedToken) }
                buttons = withContext(Dispatchers.IO) { AdminApi.loadButtons(savedToken) } ?: emptyList()
                contentSettings = withContext(Dispatchers.IO) { AdminApi.loadContent(savedToken) }
                auditItems = withContext(Dispatchers.IO) { AdminApi.loadAudit(savedToken) } ?: emptyList()
                if (restored.role == "owner" || restored.permissions["can_manage_moderators"] == true) {
                    moderators = withContext(Dispatchers.IO) { AdminApi.loadModerators(savedToken) } ?: emptyList()
                }
                val operations = withContext(Dispatchers.IO) { AdminApi.loadOperations(savedToken) }
                if (operations != null) {
                    queue = operations
                    liveOperations = true
                }
                val savedPreferences = withContext(Dispatchers.IO) { AdminApi.loadNotifications(savedToken) }
                if (savedPreferences != null) {
                    AdminSessionStore.saveNotificationPreferences(appContext, savedPreferences)
                    val labels = mapOf(
                        "طلب شحن جديد" to "charge_new",
                        "طلب سحب جديد" to "withdraw_new",
                        "خطأ أو فشل مالي" to "financial_error",
                        "إجراءات المشرفين" to "moderator_actions",
                        "الإحالات والمستحقات" to "referrals",
                        "توقف البوت أو انقطاع الاتصال" to "bot_offline",
                        "قرارات المساعد الذكي" to "ai_decisions"
                    )
                    notifications = notifications.mapValues { (label, defaultValue) -> savedPreferences[labels[label]] ?: defaultValue }
                }
                if (restored.role == "owner" || restored.permissions["can_handle_charges"] == true || restored.permissions["can_handle_withdraws"] == true) {
                    AdminNotificationScheduler.schedule(appContext)
                }
                connected = true
                showLogin = false
                demoMode = true
            } else {
                AdminSessionStore.clear(appContext)
                AdminNotificationScheduler.cancel(appContext)
            }
        }
        restoringSession = false
    }

    MaterialTheme(colorScheme = if (useDark) darkColorScheme() else lightColorScheme()) {
        CompositionLocalProvider(androidx.compose.ui.platform.LocalLayoutDirection provides androidx.compose.ui.unit.LayoutDirection.Rtl) {
            if (restoringSession) {
                Column(
                    Modifier.fillMaxSize(),
                    verticalArrangement = Arrangement.Center,
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    CircularProgressIndicator()
                    Spacer(Modifier.height(12.dp))
                    Text("جارٍ التحقق من جلسة الإدارة...")
                }
            } else if (showLogin && !connected) {
                LoginScreen(
                    code = pairingCode,
                    onCodeChange = { pairingCode = it.uppercase().filter { ch -> ch in "ABCDEFGHJKLMNPQRSTUVWXYZ23456789" }.take(8) },
                    message = loginMessage,
                    connecting = connecting,
                    onConnect = {
                        val cleanCode = pairingCode.trim()
                        if (!cleanCode.matches(Regex("[ABCDEFGHJKLMNPQRSTUVWXYZ23456789]{8}"))) {
                            loginMessage = "اكتب رمز الربط المؤلف من 8 أحرف وأرقام الذي وصلك من البوت بعد إرسال /adminapp."
                        } else {
                            scope.launch {
                                connecting = true
                                val result = withContext(Dispatchers.IO) { AdminApi.exchangePairingCode(cleanCode) }
                                connecting = false
                                if (result.token != null) {
                                    accessToken = result.token
                                    AdminSessionStore.saveToken(appContext, result.token)
                                    if (result.role == "owner" || result.permissions["can_handle_charges"] == true || result.permissions["can_handle_withdraws"] == true) {
                                        AdminNotificationScheduler.schedule(appContext)
                                    }
                                    if (Build.VERSION.SDK_INT >= 33 && appContext is ComponentActivity &&
                                        appContext.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
                                        appContext.requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 1001)
                                    }
                                    accountRole = result.role
                                    accountPermissions = result.permissions
                                    dashboardStats = withContext(Dispatchers.IO) { AdminApi.loadDashboard(result.token) }
                                    if (result.role == "owner") referralSummary = withContext(Dispatchers.IO) { AdminApi.loadReferrals(result.token) }
                                    buttons = withContext(Dispatchers.IO) { AdminApi.loadButtons(result.token) } ?: emptyList()
                                    contentSettings = withContext(Dispatchers.IO) { AdminApi.loadContent(result.token) }
                                    auditItems = withContext(Dispatchers.IO) { AdminApi.loadAudit(result.token) } ?: emptyList()
                                    if (result.role == "owner" || result.permissions["can_manage_moderators"] == true) {
                                        moderators = withContext(Dispatchers.IO) { AdminApi.loadModerators(result.token) } ?: emptyList()
                                    }
                                    val operations = withContext(Dispatchers.IO) { AdminApi.loadOperations(result.token) }
                                    if (operations != null) {
                                        queue = operations
                                        liveOperations = true
                                    } else {
                                        liveOperations = false
                                    }
                                    val savedPreferences = withContext(Dispatchers.IO) { AdminApi.loadNotifications(result.token) }
                                    if (savedPreferences != null) {
                                        AdminSessionStore.saveNotificationPreferences(appContext, savedPreferences)
                                        val labels = mapOf(
                                            "طلب شحن جديد" to "charge_new",
                                            "طلب سحب جديد" to "withdraw_new",
                                            "خطأ أو فشل مالي" to "financial_error",
                                            "إجراءات المشرفين" to "moderator_actions",
                                            "الإحالات والمستحقات" to "referrals",
                                            "توقف البوت أو انقطاع الاتصال" to "bot_offline",
                                            "قرارات المساعد الذكي" to "ai_decisions"
                                        )
                                        notifications = notifications.mapValues { (label, defaultValue) -> savedPreferences[labels[label]] ?: defaultValue }
                                    }
                                    connected = true
                                    showLogin = false
                                    demoMode = true
                                    pairingCode = ""
                                    loginMessage = ""
                                } else {
                                    loginMessage = result.error ?: "تعذر تسجيل الدخول."
                                }
                            }
                        }
                    },
                    onPreview = { showLogin = false; demoMode = true }
                )
            } else {
                Scaffold(
                    topBar = {
                        TopAppBar(
                            title = {
                                Column {
                                    Text("Matar Admin", fontWeight = FontWeight.Bold)
                                    Text(if (connected) { if (accountRole == "owner") "مدير البوت • متصل" else "مشرف • متصل" } else "وضع معاينة غير متصل", style = MaterialTheme.typography.labelSmall)
                                }
                            },
                            actions = {
                                IconButton(onClick = { dark = when (dark) { true -> false; false -> null; null -> true } }) {
                                    Icon(if (useDark) Icons.Default.LightMode else Icons.Default.DarkMode, contentDescription = "تبديل المظهر")
                                }
                            }
                        )
                    },
                    bottomBar = {
                        NavigationBar {
                            Page.values().filter { !connected || accountRole == "owner" || when (it) {
                                Page.HOME -> accountPermissions["can_view_stats"] == true
                                Page.ROOM -> accountPermissions["can_handle_charges"] == true || accountPermissions["can_handle_withdraws"] == true
                                Page.USERS -> accountPermissions["can_manage_moderators"] == true
                                Page.MESSAGES -> accountPermissions["can_send_broadcast"] == true
                                Page.BUTTONS -> accountPermissions["can_manage_buttons"] == true
                                Page.REFERRALS -> accountRole == "owner"
                                Page.CONTENT -> accountRole == "owner" || accountPermissions["can_manage_buttons"] == true
                                Page.SETTINGS -> true
                            } }.forEach { item ->
                                val icon = when (item) {
                                    Page.HOME -> Icons.Default.Dashboard
                                    Page.ROOM -> Icons.Default.Groups
                                    Page.USERS -> Icons.Default.AdminPanelSettings
                                    Page.MESSAGES -> Icons.Default.MarkChatUnread
                                    Page.BUTTONS -> Icons.Default.EditNote
                                    Page.REFERRALS -> Icons.Default.AccountBalanceWallet
                                    Page.CONTENT -> Icons.Default.TextFields
                                    Page.SETTINGS -> Icons.Default.Settings
                                }
                                NavigationBarItem(
                                    selected = page == item,
                                    onClick = {
                                        page = item
                                        val token = accessToken
                                        if (item == Page.USERS && token != null) {
                                            scope.launch { moderators = withContext(Dispatchers.IO) { AdminApi.loadModerators(token) } ?: moderators }
                                        }
                                        if (item == Page.BUTTONS && token != null) {
                                            scope.launch { buttons = withContext(Dispatchers.IO) { AdminApi.loadButtons(token) } ?: buttons }
                                        }
                                        if (item == Page.REFERRALS && token != null && accountRole == "owner") {
                                            scope.launch { referralSummary = withContext(Dispatchers.IO) { AdminApi.loadReferrals(token) } }
                                        }
                                        if (item == Page.CONTENT && token != null) {
                                            scope.launch { contentSettings = withContext(Dispatchers.IO) { AdminApi.loadContent(token) } }
                                        }
                                        if (item == Page.HOME && token != null) {
                                            scope.launch { dashboardStats = withContext(Dispatchers.IO) { AdminApi.loadDashboard(token) } }
                                        }
                                    },
                                    icon = { Icon(icon, contentDescription = item.label) },
                                    label = { Text(item.label, maxLines = 1) }
                                )
                            }
                        }
                    }
                ) { padding ->
                    Column(Modifier.fillMaxSize().padding(padding)) {
                        if (demoMode) {
                            Surface(color = MaterialTheme.colorScheme.tertiaryContainer, modifier = Modifier.fillMaxWidth()) {
                                Text(
                                    if (connected && liveOperations) "تم التحقق — قائمة الطلبات من الخادم؛ التسوية المالية ما زالت مقفلة." else if (connected) "تم التحقق من الحساب، لكن تعذر تحميل الطلبات الحية؛ العرض تجريبي." else "معاينة فقط — لا يوجد اتصال بالبوت ولا تُنفّذ أي عملية حقيقية",
                                    modifier = Modifier.padding(10.dp),
                                    style = MaterialTheme.typography.labelMedium,
                                    textAlign = TextAlign.Center
                                )
                            }
                        }
                        when (page) {
                            Page.HOME -> HomeScreen(stats = dashboardStats, connected = connected, onRefresh = {
                                val token = accessToken
                                if (token != null) scope.launch { dashboardStats = withContext(Dispatchers.IO) { AdminApi.loadDashboard(token) } }
                            }, onGoRoom = { page = Page.ROOM }, onGoSettings = { page = Page.SETTINGS })
                            Page.ROOM -> OperationsRoom(
                                queue = queue,
                                selected = selectedRequest,
                                note = actionNote,
                                message = operationMessage,
                                liveMode = connected && liveOperations,
                                onNoteChange = { actionNote = it },
                                onSelect = { key ->
                                    val token = accessToken
                                    val item = queue.firstOrNull { it.operationKey == key }
                                    if (connected && liveOperations && token != null && item != null) {
                                        scope.launch {
                                            val error = withContext(Dispatchers.IO) { AdminApi.claimOperation(token, item.typeKey, item.id) }
                                            if (error == null) {
                                                selectedRequest = key
                                                queue = withContext(Dispatchers.IO) { AdminApi.loadOperations(token) } ?: queue
                                                operationMessage = "تم استلام الطلب لمدة 10 دقائق."
                                            } else operationMessage = error
                                        }
                                    } else selectedRequest = key
                                },
                                onRelease = { key ->
                                    val token = accessToken
                                    val item = queue.firstOrNull { it.operationKey == key }
                                    if (connected && liveOperations && token != null && item != null) scope.launch {
                                        val error = withContext(Dispatchers.IO) { AdminApi.releaseOperation(token, item.typeKey, item.id) }
                                        operationMessage = error ?: "تم تحرير الطلب وإعادته إلى قائمة الانتظار."
                                        if (error == null) {
                                            queue = withContext(Dispatchers.IO) { AdminApi.loadOperations(token) } ?: queue
                                            selectedRequest = null
                                            actionNote = ""
                                        }
                                    } else {
                                        selectedRequest = null
                                        operationMessage = "تم إلغاء الاستلام التجريبي."
                                    }
                                },
                                onCancel = { key, reason ->
                                    val token = accessToken
                                    val item = queue.firstOrNull { it.operationKey == key }
                                    if (connected && liveOperations && token != null && item != null) scope.launch {
                                        val error = withContext(Dispatchers.IO) { AdminApi.cancelOperation(token, item.typeKey, item.id, reason) }
                                        operationMessage = error ?: "تم إلغاء الطلب وإشعار المستخدم."
                                        if (error == null) {
                                            queue = withContext(Dispatchers.IO) { AdminApi.loadOperations(token) } ?: queue
                                            selectedRequest = null
                                            actionNote = ""
                                        }
                                    } else operationMessage = "الإلغاء التجريبي لا يغيّر أي بيانات مالية."
                                },
                                onComplete = { key ->
                                    val token = accessToken
                                    val item = queue.firstOrNull { it.operationKey == key }
                                    if (connected && liveOperations && token != null && item != null) scope.launch {
                                        operationMessage = withContext(Dispatchers.IO) { AdminApi.completeOperation(token, item.typeKey, item.id) }
                                        val refreshed = withContext(Dispatchers.IO) { AdminApi.loadOperations(token) }
                                        if (refreshed != null) {
                                            queue = refreshed
                                            if (refreshed.none { it.operationKey == key }) {
                                                selectedRequest = null
                                                actionNote = ""
                                            }
                                        }
                                    } else {
                                        queue = queue.map { if (it.operationKey == key) it.copy(status = "منجز تجريبياً") else it }
                                        selectedRequest = null
                                        actionNote = ""
                                    }
                                }
                            )
                            Page.USERS -> ModeratorsScreen(
                                moderators = moderators,
                                message = moderatorMessage,
                                onRefresh = {
                                    val token = accessToken
                                    if (token != null) scope.launch {
                                        moderators = withContext(Dispatchers.IO) { AdminApi.loadModerators(token) } ?: moderators
                                    }
                                },
                                onAdd = { userId, name, permissions ->
                                    val token = accessToken
                                    if (token == null) moderatorMessage = "سجّل الدخول أولاً."
                                    else scope.launch {
                                        val error = withContext(Dispatchers.IO) { AdminApi.addModerator(token, userId, name, permissions) }
                                        moderatorMessage = error ?: "تمت إضافة المشرف."
                                        if (error == null) moderators = withContext(Dispatchers.IO) { AdminApi.loadModerators(token) } ?: moderators
                                    }
                                },
                                onUpdate = { userId, permissions ->
                                    val token = accessToken
                                    if (token == null) moderatorMessage = "سجّل الدخول أولاً."
                                    else scope.launch {
                                        val error = withContext(Dispatchers.IO) { AdminApi.updateModeratorPermissions(token, userId, permissions) }
                                        moderatorMessage = error ?: "تم حفظ صلاحيات المشرف."
                                        if (error == null) moderators = withContext(Dispatchers.IO) { AdminApi.loadModerators(token) } ?: moderators
                                    }
                                },
                                onDelete = { userId ->
                                    val token = accessToken
                                    if (token == null) moderatorMessage = "سجّل الدخول أولاً."
                                    else scope.launch {
                                        val error = withContext(Dispatchers.IO) { AdminApi.deleteModerator(token, userId) }
                                        moderatorMessage = error ?: "تم حذف المشرف."
                                        if (error == null) moderators = withContext(Dispatchers.IO) { AdminApi.loadModerators(token) } ?: moderators
                                    }
                                }
                            )
                            Page.MESSAGES -> MessagesScreen(
                                connected = connected,
                                canSend = accountRole == "owner" || accountPermissions["can_send_broadcast"] == true,
                                sending = sendingMessage,
                                status = sentMessage,
                                onSend = { audience, message ->
                                    val token = accessToken
                                    if (token == null) sentMessage = "سجّل الدخول أولاً."
                                    else scope.launch {
                                        sendingMessage = true
                                        sentMessage = withContext(Dispatchers.IO) { AdminApi.broadcastMessage(token, message, audience) }
                                            ?: "تعذر الإرسال؛ قد لا يملك حسابك صلاحية البث."
                                        sendingMessage = false
                                    }
                                }
                            )
                            Page.BUTTONS -> ButtonsScreen(
                                items = buttons,
                                status = buttonMessage,
                                onSave = { id, text, message, parent, action, subscription, active ->
                                    val token = accessToken
                                    if (token == null) buttonMessage = "سجّل الدخول أولاً."
                                    else scope.launch {
                                        val error = withContext(Dispatchers.IO) { AdminApi.updateButton(token, id, text, message, parent, action, subscription, active) }
                                        buttonMessage = error ?: "تم حفظ التعديلات."
                                        buttons = withContext(Dispatchers.IO) { AdminApi.loadButtons(token) } ?: buttons
                                    }
                                }
                            )
                            Page.REFERRALS -> ReferralsScreen(
                                summary = referralSummary,
                                message = referralMessage,
                                onRefresh = {
                                    val token = accessToken
                                    if (token != null) scope.launch { referralSummary = withContext(Dispatchers.IO) { AdminApi.loadReferrals(token) } }
                                },
                                onSaveSettings = { percentage, cycleDays, nextPayout ->
                                    val token = accessToken
                                    if (token == null) referralMessage = "سجّل الدخول أولاً."
                                    else scope.launch {
                                        val error = withContext(Dispatchers.IO) { AdminApi.saveReferralSettings(token, percentage, cycleDays, nextPayout) }
                                        referralMessage = error ?: "تم حفظ إعدادات الإحالات."
                                        if (error == null) referralSummary = withContext(Dispatchers.IO) { AdminApi.loadReferrals(token) } ?: referralSummary
                                    }
                                },
                                onPayout = { userId, amount ->
                                    val token = accessToken
                                    if (token == null) referralMessage = "سجّل الدخول أولاً."
                                    else scope.launch {
                                        val error = withContext(Dispatchers.IO) { AdminApi.payReferral(token, userId, amount) }
                                        referralMessage = error ?: "تم صرف الأرباح وتحديث سجل المستحقات."
                                        if (error == null) referralSummary = withContext(Dispatchers.IO) { AdminApi.loadReferrals(token) } ?: referralSummary
                                    }
                                }
                            )
                            Page.CONTENT -> ContentScreen(
                                settings = contentSettings,
                                message = contentMessage,
                                onSave = { edited ->
                                    val token = accessToken
                                    if (token == null) contentMessage = "سجّل الدخول أولاً."
                                    else scope.launch {
                                        val error = withContext(Dispatchers.IO) { AdminApi.saveContent(token, edited) }
                                        contentMessage = error ?: "تم حفظ النصوص وإعداد الاشتراك."
                                        if (error == null) contentSettings = withContext(Dispatchers.IO) { AdminApi.loadContent(token) } ?: contentSettings
                                    }
                                }
                            )
                            Page.SETTINGS -> SettingsScreen(
                                notifications = notifications,
                                onNotificationChange = { key, value -> notifications = notifications + (key to value) },
                                onTheme = { showAppearance = true },
                                onSaveNotifications = {
                                    val token = accessToken
                                    if (token == null) {
                                        notificationMessage = "سجّل الدخول عبر تيليغرام أولاً لحفظ الإعدادات."
                                    } else {
                                        scope.launch {
                                            savingNotifications = true
                                            val keyMap = mapOf(
                                                "طلب شحن جديد" to "charge_new",
                                                "طلب سحب جديد" to "withdraw_new",
                                                "خطأ أو فشل مالي" to "financial_error",
                                                "إجراءات المشرفين" to "moderator_actions",
                                                "الإحالات والمستحقات" to "referrals",
                                                "توقف البوت أو انقطاع الاتصال" to "bot_offline",
                                                "قرارات المساعد الذكي" to "ai_decisions"
                                            )
                                            val prefs = notifications.mapNotNull { (label, enabled) -> keyMap[label]?.let { it to enabled } }.toMap()
                                            val saved = withContext(Dispatchers.IO) { AdminApi.saveNotifications(token, prefs) }
                                            if (saved) AdminSessionStore.saveNotificationPreferences(appContext, prefs)
                                            savingNotifications = false
                                            notificationMessage = if (saved) "تم حفظ تفضيلاتك على الخادم. توصيل الإشعارات الفعلية بالخلفية لم يُفعّل بعد." else "تعذر الحفظ؛ تأكد من اتصال الخادم وصلاحية الجلسة."
                                        }
                                    }
                                },
                                savingNotifications = savingNotifications,
                                notificationMessage = notificationMessage,
                                auditItems = auditItems,
                                onLogin = {
                                    val oldToken = accessToken
                                    if (oldToken != null) scope.launch { withContext(Dispatchers.IO) { AdminApi.logout(oldToken) } }
                                    accessToken = null
                                    AdminSessionStore.clear(appContext)
                                    AdminNotificationScheduler.cancel(appContext)
                                    accountRole = null
                                    accountPermissions = emptyMap()
                                    buttons = emptyList()
                                    contentSettings = null
                                    dashboardStats = null
                                    auditItems = emptyList()
                                    connected = false
                                    showLogin = true
                                    page = Page.HOME
                                }
                            )
                        }
                    }
                }
            }
            if (showAppearance) {
                AlertDialog(
                    onDismissRequest = { showAppearance = false },
                    title = { Text("المظهر") },
                    text = {
                        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            TextButton(onClick = { dark = false; showAppearance = false }) { Text("الوضع النهاري") }
                            TextButton(onClick = { dark = true; showAppearance = false }) { Text("الوضع الليلي") }
                            TextButton(onClick = { dark = null; showAppearance = false }) { Text("حسب إعدادات الهاتف") }
                        }
                    },
                    confirmButton = { TextButton(onClick = { showAppearance = false }) { Text("إغلاق") } }
                )
            }
        }
    }
}

@Composable
private fun LoginScreen(code: String, onCodeChange: (String) -> Unit, message: String, connecting: Boolean, onConnect: () -> Unit, onPreview: () -> Unit) {
    Column(
        Modifier.fillMaxSize().padding(24.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Icon(Icons.Default.WaterDrop, contentDescription = null, modifier = Modifier.size(64.dp), tint = MaterialTheme.colorScheme.primary)
        Spacer(Modifier.height(12.dp))
        Text("Matar Admin", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
        Text("مركز التحكم ببوت مطر", style = MaterialTheme.typography.titleMedium)
        Spacer(Modifier.height(24.dp))
        Text("تسجيل الدخول الآمن", style = MaterialTheme.typography.titleLarge)
        Text("أرسل /link إلى بوت مطر، ثم أدخل الرمز الرقمي. سيحدد الخادم تلقائياً إن كنت مديراً أم مشرفاً.", textAlign = TextAlign.Center)
        Spacer(Modifier.height(12.dp))
        OutlinedTextField(
            value = code, onValueChange = onCodeChange,
            label = { Text("رمز الربط من بوت تيليغرام") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true
        )
        Spacer(Modifier.height(10.dp))
        Button(onClick = onConnect, enabled = !connecting, modifier = Modifier.fillMaxWidth()) { Text(if (connecting) "جارٍ التحقق..." else "تحقق وتسجيل الدخول") }
        if (message.isNotBlank()) {
            Spacer(Modifier.height(8.dp))
            Text(message, color = MaterialTheme.colorScheme.error, textAlign = TextAlign.Center, style = MaterialTheme.typography.bodySmall)
        }
        Spacer(Modifier.height(20.dp))
        OutlinedButton(onClick = onPreview, modifier = Modifier.fillMaxWidth()) { Text("معاينة التصميم فقط") }
        Spacer(Modifier.height(8.dp))
        Text("المعاينة لا تمنح صلاحيات ولا تنفذ عمليات.", style = MaterialTheme.typography.labelSmall, textAlign = TextAlign.Center)
    }
}

@Composable
private fun HomeScreen(
    stats: Map<String, Int>?,
    connected: Boolean,
    onRefresh: () -> Unit,
    onGoRoom: () -> Unit,
    onGoSettings: () -> Unit
) {
    LazyColumn(Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { Text("أهلاً بك في مركز القيادة", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold) }
        item { Text(if (connected) "هذه الإحصائيات من خادم مطر." else "وضع معاينة — الأرقام التالية توضيحية فقط.") }
        item {
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                MetricCard("طلبات الشحن", stats?.get("pending_charges")?.toString() ?: if (connected) "—" else "12", Icons.Default.South, Modifier.weight(1f))
                MetricCard("طلبات السحب", stats?.get("pending_withdraws")?.toString() ?: if (connected) "—" else "4", Icons.Default.North, Modifier.weight(1f))
            }
        }
        item {
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                MetricCard("المشرفون", stats?.get("moderators")?.toString() ?: if (connected) "—" else "3", Icons.Default.Groups, Modifier.weight(1f))
                MetricCard("المستخدمون", stats?.get("users")?.toString() ?: "—", Icons.Default.People, Modifier.weight(1f))
            }
        }
        item {
            Card(Modifier.fillMaxWidth(), shape = RoundedCornerShape(18.dp)) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("أمان التشغيل", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                    Text("التنفيذ المالي الحقيقي يحتاج إعداداً صريحاً على الخادم؛ لا يكفي ضغط زر في التطبيق.")
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Default.Shield, contentDescription = null)
                        Spacer(Modifier.width(8.dp))
                        Text("الصلاحيات والتحقق على الخادم")
                    }
                }
            }
        }
        item { Button(onClick = onRefresh, modifier = Modifier.fillMaxWidth(), enabled = connected) { Text("تحديث الإحصائيات") } }
        item { Button(onClick = onGoRoom, modifier = Modifier.fillMaxWidth()) { Text("فتح غرفة العمليات") } }
        item { OutlinedButton(onClick = onGoSettings, modifier = Modifier.fillMaxWidth()) { Text("إعدادات الإشعارات والمظهر والسجل") } }
    }
}

@Composable
private fun MetricCard(title: String, value: String, icon: androidx.compose.ui.graphics.vector.ImageVector, modifier: Modifier = Modifier) {
    Card(modifier, shape = RoundedCornerShape(18.dp)) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Icon(icon, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
            Text(value, style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
            Text(title, style = MaterialTheme.typography.bodyMedium)
        }
    }
}

@Composable
private fun OperationsRoom(
    queue: List<QueueItem>, selected: String?, note: String,
    message: String, liveMode: Boolean,
    onNoteChange: (String) -> Unit, onSelect: (String) -> Unit,
    onRelease: (String) -> Unit, onCancel: (String, String) -> Unit, onComplete: (String) -> Unit
) {
    var confirmCancel by remember { mutableStateOf(false) }
    var cancelTarget by remember { mutableStateOf<String?>(null) }
    var confirmComplete by remember { mutableStateOf<String?>(null) }
    LazyColumn(Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { Text("غرفة العمليات المشتركة", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold) }
        item { Text(if (liveMode) "قائمة الطلبات متصلة بالخادم. الاستلام يقفل الطلب 10 دقائق؛ التنفيذ الحقيقي يخضع لإعداد الخادم." else "آلية الاستلام والتنفيذ معروضة تجريبياً. لن تُنفّذ أي معاملة حقيقية.") }
        if (message.isNotBlank()) item { Card(Modifier.fillMaxWidth()) { Text(message, modifier = Modifier.padding(12.dp), color = MaterialTheme.colorScheme.primary) } }
        if (queue.isEmpty()) item { Text(if (liveMode) "لا توجد طلبات مفتوحة مسموح لك بعرضها حالياً." else "هذه طلبات توضيحية للمعاينة فقط.") }
        items(queue, key = { it.operationKey }) { item ->
            Card(Modifier.fillMaxWidth(), shape = RoundedCornerShape(16.dp)) {
                Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text("#${item.id}  ${item.type}", modifier = Modifier.weight(1f), fontWeight = FontWeight.Bold)
                        AssistChip(onClick = {}, label = { Text(item.status) })
                    }
                    Text("صاحب الطلب: ${item.user}")
                    if (item.method.isNotBlank()) Text("طريقة الدفع: ${item.method}")
                    if (item.reference.isNotBlank()) Text("المرجع: ${item.reference}")
                    if (item.claimOwner != null) {
                        Text("تم الاستلام بواسطة حساب تيليغرام: ${item.claimOwner}", style = MaterialTheme.typography.bodySmall)
                        if (item.claimExpiresAt != null) Text("تنتهي المهلة: ${item.claimExpiresAt}", style = MaterialTheme.typography.bodySmall)
                    }
                    Text("المبلغ: ${item.amount}")
                    if (selected == item.operationKey) {
                        OutlinedTextField(value = note, onValueChange = onNoteChange, label = { Text("ملاحظات / سبب الإلغاء") }, modifier = Modifier.fillMaxWidth(), minLines = 2)
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            OutlinedButton(onClick = { onRelease(item.operationKey) }, modifier = Modifier.weight(1f)) { Text("تحرير الاستلام") }
                            Button(onClick = { confirmComplete = item.operationKey }, modifier = Modifier.weight(1f)) { Text("تم التنفيذ") }
                        }
                        OutlinedButton(onClick = { cancelTarget = item.operationKey; confirmCancel = true }, modifier = Modifier.fillMaxWidth(), colors = ButtonDefaults.outlinedButtonColors(contentColor = MaterialTheme.colorScheme.error)) { Text("إلغاء الطلب") }
                    } else {
                        Button(onClick = { onSelect(item.operationKey) }, modifier = Modifier.fillMaxWidth()) { Text("فتح الطلب واستلامه") }
                    }
                }
            }
        }
    }
    if (confirmComplete != null) {
        AlertDialog(
            onDismissRequest = { confirmComplete = null },
            title = { Text("تأكيد إتمام الطلب") },
            text = { Text("تأكد من تنفيذ الإجراء فعلياً. إذا كان التنفيذ المالي الحقيقي مغلقاً، سيرفض الخادم الطلب ولن يعلن نجاحاً وهمياً.") },
            confirmButton = { TextButton(onClick = { val key = confirmComplete; confirmComplete = null; if (key != null) onComplete(key) }) { Text("تأكيد") } },
            dismissButton = { TextButton(onClick = { confirmComplete = null }) { Text("رجوع") } }
        )
    }
    if (confirmCancel && cancelTarget != null) {
        AlertDialog(
            onDismissRequest = { confirmCancel = false; cancelTarget = null },
            title = { Text("تأكيد إلغاء الطلب") },
            text = { Text("لن يتم الإلغاء إلا إذا أكد الخادم نجاح الإجراء. السبب: " + note.ifBlank { "لم يُكتب سبب بعد" }) },
            confirmButton = {
                TextButton(onClick = {
                    val key = cancelTarget
                    if (key != null && note.isNotBlank()) onCancel(key, note.trim())
                    confirmCancel = false
                    cancelTarget = null
                }, enabled = note.isNotBlank()) { Text("تأكيد الإلغاء") }
            },
            dismissButton = { TextButton(onClick = { confirmCancel = false; cancelTarget = null }) { Text("رجوع") } }
        )
    }
}

@Composable
private fun ModeratorsScreen(
    moderators: List<ModeratorItem>,
    message: String,
    onRefresh: () -> Unit,
    onAdd: (Long, String, Map<String, Boolean>) -> Unit,
    onUpdate: (Long, Map<String, Boolean>) -> Unit,
    onDelete: (Long) -> Unit
) {
    var userId by remember { mutableStateOf("") }
    var name by remember { mutableStateOf("") }
    var canCharges by remember { mutableStateOf(false) }
    var canWithdraws by remember { mutableStateOf(false) }
    var canBroadcast by remember { mutableStateOf(false) }
    var canManageUsers by remember { mutableStateOf(false) }
    var canViewStats by remember { mutableStateOf(false) }
    var canButtons by remember { mutableStateOf(false) }
    var canManageModerators by remember { mutableStateOf(false) }
    var canAI by remember { mutableStateOf(false) }
    val labels = listOf(
        "can_handle_charges" to "إدارة طلبات الشحن",
        "can_handle_withdraws" to "إدارة طلبات السحب",
        "can_send_broadcast" to "إرسال رسائل جماعية",
        "can_manage_users" to "إدارة المستخدمين",
        "can_view_stats" to "عرض الإحصائيات والسجل",
        "can_manage_buttons" to "إدارة أزرار البوت",
        "can_manage_moderators" to "إدارة المشرفين",
        "can_use_ai" to "استخدام المساعد الذكي"
    )
    fun addPermissions() = mapOf(
        "can_handle_charges" to canCharges, "can_handle_withdraws" to canWithdraws,
        "can_send_broadcast" to canBroadcast, "can_manage_users" to canManageUsers,
        "can_view_stats" to canViewStats, "can_manage_buttons" to canButtons,
        "can_manage_moderators" to canManageModerators, "can_use_ai" to canAI
    )
    LazyColumn(Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { Text("إدارة المشرفين", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold) }
        item { Text("تُقرأ الصلاحيات من الخادم. أي تعديل يُحفظ على قاعدة البوت ويُسجّل في سجل التدقيق.") }
        item { OutlinedTextField(value = userId, onValueChange = { userId = it.filter { ch -> ch.isDigit() }.take(18) }, label = { Text("معرف تيليغرام") }, modifier = Modifier.fillMaxWidth(), singleLine = true) }
        item { OutlinedTextField(value = name, onValueChange = { name = it.take(80) }, label = { Text("اسم المشرف (اختياري)") }, modifier = Modifier.fillMaxWidth(), singleLine = true) }
        item { PermissionToggle("إدارة طلبات الشحن", canCharges) { canCharges = it } }
        item { PermissionToggle("إدارة طلبات السحب", canWithdraws) { canWithdraws = it } }
        item { PermissionToggle("إرسال رسائل جماعية", canBroadcast) { canBroadcast = it } }
        item { PermissionToggle("إدارة المستخدمين", canManageUsers) { canManageUsers = it } }
        item { PermissionToggle("عرض الإحصائيات والسجل", canViewStats) { canViewStats = it } }
        item { PermissionToggle("إدارة أزرار البوت", canButtons) { canButtons = it } }
        item { PermissionToggle("إدارة المشرفين", canManageModerators) { canManageModerators = it } }
        item { PermissionToggle("استخدام المساعد الذكي", canAI) { canAI = it } }
        item {
            Button(onClick = {
                val parsed = userId.toLongOrNull()
                if (parsed != null && parsed > 0) {
                    onAdd(parsed, name.trim(), addPermissions())
                    userId = ""
                    name = ""
                }
            }, enabled = userId.toLongOrNull()?.let { it > 0 } == true, modifier = Modifier.fillMaxWidth()) { Text("إضافة مشرف") }
        }
        item { OutlinedButton(onClick = onRefresh, modifier = Modifier.fillMaxWidth()) { Text("تحديث قائمة المشرفين") } }
        if (message.isNotBlank()) item { Text(message, color = MaterialTheme.colorScheme.primary) }
        item { Text("المشرفون الحاليون", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold) }
        if (moderators.isEmpty()) item { Text("لا توجد بيانات مشرفين محمّلة. اضغط تحديث القائمة.") }
        items(moderators, key = { it.userId }) { moderator ->
            var edits by remember(moderator.userId, moderator.permissions) { mutableStateOf(moderator.permissions) }
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Column(Modifier.weight(1f)) {
                            Text(moderator.customName.ifBlank { "مشرف " + moderator.userId }, fontWeight = FontWeight.Bold)
                            Text("معرف تيليغرام: " + moderator.userId, style = MaterialTheme.typography.bodySmall)
                        }
                        IconButton(onClick = { onDelete(moderator.userId) }) { Icon(Icons.Default.DeleteOutline, contentDescription = "حذف المشرف") }
                    }
                    labels.forEach { (key, label) ->
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(label, modifier = Modifier.weight(1f))
                            Switch(checked = edits[key] == true, onCheckedChange = { edits = edits + (key to it) })
                        }
                    }
                    Button(onClick = { onUpdate(moderator.userId, edits) }, modifier = Modifier.fillMaxWidth()) { Text("حفظ صلاحيات المشرف") }
                }
            }
        }
    }
}

@Composable
private fun PermissionToggle(label: String, checked: Boolean, onCheckedChange: (Boolean) -> Unit) {
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        Text(label, modifier = Modifier.weight(1f))
        Checkbox(checked = checked, onCheckedChange = onCheckedChange)
    }
}

@Composable
private fun MessagesScreen(
    connected: Boolean,
    canSend: Boolean,
    sending: Boolean,
    status: String,
    onSend: (String, String) -> Unit
) {
    var target by remember { mutableStateOf("all") }
    var message by remember { mutableStateOf("") }
    var confirm by remember { mutableStateOf(false) }
    Column(Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("الرسائل", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
        Text("إرسال جماعي عبر تيليغرام. راجع الجمهور والنص قبل التأكيد.")
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            FilterChip(selected = target == "all", onClick = { target = "all" }, label = { Text("كل المستخدمين") })
            FilterChip(selected = target == "moderators", onClick = { target = "moderators" }, label = { Text("المشرفون") })
        }
        OutlinedTextField(value = message, onValueChange = { message = it.take(4000) }, label = { Text("اكتب الرسالة") }, modifier = Modifier.fillMaxWidth(), minLines = 4)
        Button(onClick = { confirm = true }, enabled = connected && canSend && !sending && message.isNotBlank(), modifier = Modifier.fillMaxWidth()) {
            Text(if (sending) "جارٍ الإرسال..." else "مراجعة وإرسال")
        }
        if (!connected) Text("يلزم تسجيل الدخول للاتصال بالخادم قبل الإرسال.", style = MaterialTheme.typography.bodySmall)
        if (!canSend) Text("حسابك لا يملك صلاحية إرسال الرسائل.", style = MaterialTheme.typography.bodySmall)
        if (status.isNotBlank()) Text(status, color = MaterialTheme.colorScheme.primary, style = MaterialTheme.typography.bodySmall)
        if (confirm) {
            AlertDialog(
                onDismissRequest = { confirm = false },
                title = { Text("تأكيد الإرسال") },
                text = {
                    Text(
                        "سيتم إرسال هذه الرسالة إلى " +
                            (if (target == "all") "كل المستخدمين النشطين (حتى 5000 حساب)" else "المدير وجميع المشرفين") +
                            ". هل تريد المتابعة?\n\n" + message
                    )
                },
                confirmButton = { TextButton(onClick = { confirm = false; onSend(target, message.trim()) }) { Text("إرسال الآن") } },
                dismissButton = { TextButton(onClick = { confirm = false }) { Text("رجوع") } }
            )
        }
    }
}

@Composable
private fun SettingsScreen(
    notifications: Map<String, Boolean>,
    onNotificationChange: (String, Boolean) -> Unit,
    onTheme: () -> Unit,
    onSaveNotifications: () -> Unit,
    savingNotifications: Boolean,
    notificationMessage: String,
    auditItems: List<AuditItem>,
    onLogin: () -> Unit
) {
    LazyColumn(Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        item { Text("الإعدادات", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold) }
        item { Text("تفضيلات الإشعارات المحفوظة على الخادم. الإشعارات الفورية بالخلفية تحتاج إعداد خدمة الدفع.") }
        items(notifications.keys.toList()) { key ->
            Card(Modifier.fillMaxWidth()) {
                Row(Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                    Text(key, modifier = Modifier.weight(1f))
                    Switch(checked = notifications[key] == true, onCheckedChange = { onNotificationChange(key, it) })
                }
            }
        }
        item { Button(onClick = onSaveNotifications, enabled = !savingNotifications, modifier = Modifier.fillMaxWidth()) { Text(if (savingNotifications) "جارٍ الحفظ..." else "حفظ تفضيلات الإشعارات") } }
        if (notificationMessage.isNotBlank()) item { Text(notificationMessage, color = MaterialTheme.colorScheme.primary, style = MaterialTheme.typography.bodySmall) }
        item { HorizontalDivider() }
        item { Text("المظهر", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold) }
        item { OutlinedButton(onClick = onTheme, modifier = Modifier.fillMaxWidth()) { Icon(Icons.Default.Contrast, contentDescription = null); Spacer(Modifier.width(8.dp)); Text("الوضع الليلي / النهاري / تلقائي") } }
        item { HorizontalDivider() }
        item { Text("أمان الحساب", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold) }
        item { Text("صلاحيات المالك والمشرفين تُحسم على الخادم، وليس من واجهة التطبيق.") }
        item { OutlinedButton(onClick = onLogin, modifier = Modifier.fillMaxWidth()) { Text("العودة لشاشة تسجيل الدخول") } }
        item { HorizontalDivider() }
        item { Text("سجل التدقيق", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold) }
        if (auditItems.isEmpty()) item { Text("لا توجد سجلات متاحة أو لا تملك صلاحية عرضها.") }
        items(auditItems.take(20), key = { it.id }) { entry ->
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text(entry.action, fontWeight = FontWeight.Bold)
                    Text(entry.admin)
                    Text(entry.details)
                    Text(entry.createdAt, style = MaterialTheme.typography.labelSmall)
                }
            }
        }
    }
}

@Composable
private fun ButtonsScreen(
    items: List<BotButtonItem>,
    status: String,
    onSave: (Int, String, String, String, String, Boolean, Boolean) -> Unit
) {
    LazyColumn(Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { Text("إدارة أزرار البوت", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold) }
        item { Text("عدّل نص الزر والرسالة المرتبطة به، وحالة التفعيل واشتراط الاشتراك الإجباري. الحفظ يطبق على إعدادات البوت.") }
        if (status.isNotBlank()) item { Text(status, color = MaterialTheme.colorScheme.primary) }
        if (items.isEmpty()) item { Text("لا توجد أزرار متاحة أو لا تملك صلاحية إدارتها.") }
        items(items, key = { it.id }) { item -> ButtonEditorCard(item, onSave) }
    }
}

@Composable
private fun ButtonEditorCard(item: BotButtonItem, onSave: (Int, String, String, String, String, Boolean, Boolean) -> Unit) {
    var buttonText by remember(item.id, item.text) { mutableStateOf(item.text) }
    var messageText by remember(item.id, item.message) { mutableStateOf(item.message) }
    var parentButton by remember(item.id, item.parent) { mutableStateOf(item.parent) }
    var action by remember(item.id, item.action) { mutableStateOf(item.action) }
    var active by remember(item.id, item.active) { mutableStateOf(item.active) }
    var requiresSubscription by remember(item.id, item.requiresSubscription) { mutableStateOf(item.requiresSubscription) }
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(item.key, style = MaterialTheme.typography.labelMedium)
            OutlinedTextField(value = buttonText, onValueChange = { buttonText = it.take(150) }, label = { Text("نص الزر") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(value = messageText, onValueChange = { messageText = it.take(4000) }, label = { Text("نص الرسالة / النافذة") }, modifier = Modifier.fillMaxWidth(), minLines = 3)
            OutlinedTextField(value = parentButton, onValueChange = { parentButton = it.take(150) }, label = { Text("الفرع الأب / القائمة") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(value = action, onValueChange = { action = it.take(150) }, label = { Text("الإجراء المرتبط بالزر") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("الزر مفعّل", modifier = Modifier.weight(1f))
                Switch(checked = active, onCheckedChange = { active = it })
            }
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("اشتراك إجباري", modifier = Modifier.weight(1f))
                Switch(checked = requiresSubscription, onCheckedChange = { requiresSubscription = it })
            }
            Button(onClick = { onSave(item.id, buttonText, messageText, parentButton, action, requiresSubscription, active) }, modifier = Modifier.fillMaxWidth()) { Text("حفظ تعديلات الزر") }
        }
    }
}

@Composable
private fun ReferralsScreen(
    summary: ReferralSummary?,
    message: String,
    onRefresh: () -> Unit,
    onSaveSettings: (Double, Int, String) -> Unit,
    onPayout: (Long, Double) -> Unit
) {
    var percentage by remember(summary?.referralPercentage) { mutableStateOf(summary?.referralPercentage?.toString() ?: "10") }
    var cycleDays by remember(summary?.cycleDays) { mutableStateOf(summary?.cycleDays?.toString() ?: "10") }
    var nextPayout by remember(summary?.nextPayout) { mutableStateOf(summary?.nextPayout ?: "") }
    var targetUser by remember { mutableStateOf("") }
    var amount by remember { mutableStateOf("") }
    var confirmPayout by remember { mutableStateOf(false) }
    LazyColumn(Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { Text("نظام الإحالات", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold) }
        item { Text("صرف يدوي من الكاشيرة إلى رصيد المُحيل، مع تحديث سجل المستحقات ذرياً. الوضع الحقيقي يظل مقفلاً ما لم يُفعّل صراحةً على الخادم.") }
        item {
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                MetricCard("إجمالي الإحالات", summary?.totalReferrals?.toString() ?: "—", Icons.Default.Groups, Modifier.weight(1f))
                MetricCard("مستحق غير مدفوع", summary?.unpaidTotal?.let { String.format("%.2f", it) } ?: "—", Icons.Default.Payments, Modifier.weight(1f))
            }
        }
        item {
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                MetricCard("رصيد الكاشيرة", summary?.cashierBalance?.let { String.format("%.2f", it) } ?: "—", Icons.Default.AccountBalanceWallet, Modifier.weight(1f))
                MetricCard("النسبة الحالية", summary?.referralPercentage?.let { "${it}%" } ?: "—", Icons.Default.Percent, Modifier.weight(1f))
            }
        }
        item { OutlinedTextField(value = percentage, onValueChange = { percentage = it.take(6) }, label = { Text("نسبة الإحالات % (0–100)") }, modifier = Modifier.fillMaxWidth(), singleLine = true) }
        item { OutlinedTextField(value = cycleDays, onValueChange = { cycleDays = it.filter(Char::isDigit).take(2) }, label = { Text("مدة الدورة بالأيام (1–60)") }, modifier = Modifier.fillMaxWidth(), singleLine = true) }
        item { OutlinedTextField(value = nextPayout, onValueChange = { nextPayout = it.take(10) }, label = { Text("موعد الدفعة القادمة YYYY-MM-DD") }, modifier = Modifier.fillMaxWidth(), singleLine = true) }
        item {
            Button(onClick = {
                val pct = percentage.toDoubleOrNull()
                val days = cycleDays.toIntOrNull()
                if (pct != null && days != null) onSaveSettings(pct, days, nextPayout.trim())
            }, enabled = percentage.toDoubleOrNull()?.let { it in 0.0..100.0 } == true && cycleDays.toIntOrNull()?.let { it in 1..60 } == true, modifier = Modifier.fillMaxWidth()) { Text("حفظ إعدادات الإحالات") }
        }
        item { HorizontalDivider() }
        item { Text("صرف أرباح لمُحيل", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold) }
        item { OutlinedTextField(value = targetUser, onValueChange = { targetUser = it.filter(Char::isDigit).take(18) }, label = { Text("معرف تيليغرام للمُحيل") }, modifier = Modifier.fillMaxWidth(), singleLine = true) }
        item { OutlinedTextField(value = amount, onValueChange = { amount = it.filter { ch -> ch.isDigit() || ch == '.' }.take(14) }, label = { Text("مبلغ الصرف") }, modifier = Modifier.fillMaxWidth(), singleLine = true) }
        item { Button(onClick = { confirmPayout = true }, enabled = targetUser.toLongOrNull()?.let { it > 0 } == true && amount.toDoubleOrNull()?.let { it > 0 } == true, modifier = Modifier.fillMaxWidth()) { Text("مراجعة صرف الأرباح") } }
        item { OutlinedButton(onClick = onRefresh, modifier = Modifier.fillMaxWidth()) { Text("تحديث بيانات الإحالات") } }
        if (message.isNotBlank()) item { Text(message, color = MaterialTheme.colorScheme.primary) }
        item { Text("المُحيلون", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold) }
        if (summary?.items.isNullOrEmpty()) item { Text("لا توجد إحالات مسجلة حالياً.") }
        items(summary?.items ?: emptyList(), key = { it.userId }) { referrer ->
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text("المُحيل: ${referrer.userId}", fontWeight = FontWeight.Bold)
                    Text("عدد الإحالات: ${referrer.referrals}")
                    Text("المستحق غير المدفوع: ${String.format("%.2f", referrer.unpaidAmount)}")
                    Text("إجمالي المستحق: ${String.format("%.2f", referrer.theoreticalAmount)} • المدفوع: ${String.format("%.2f", referrer.paidAmount)}")
                }
            }
        }
    }
    if (confirmPayout) {
        AlertDialog(
            onDismissRequest = { confirmPayout = false },
            title = { Text("تأكيد صرف أرباح الإحالة") },
            text = { Text("سيتم صرف ${amount} للمُحيل ${targetUser}، وخصم المبلغ من الكاشيرة وتحديث سجل المستحقات. إذا كان التنفيذ الحقيقي مقفلاً فلن تتغير الأرصدة.") },
            confirmButton = { TextButton(onClick = { confirmPayout = false; val uid = targetUser.toLongOrNull(); val value = amount.toDoubleOrNull(); if (uid != null && value != null) onPayout(uid, value) }) { Text("تأكيد الصرف") } },
            dismissButton = { TextButton(onClick = { confirmPayout = false }) { Text("رجوع") } }
        )
    }
}

@Composable
private fun ContentScreen(
    settings: BotContentSettings?,
    message: String,
    onSave: (BotContentSettings) -> Unit
) {
    var welcome by remember(settings?.welcomeMessage) { mutableStateOf(settings?.welcomeMessage ?: "") }
    var subscriptionText by remember(settings?.subscriptionMessage) { mutableStateOf(settings?.subscriptionMessage ?: "") }
    var terms by remember(settings?.termsMessage) { mutableStateOf(settings?.termsMessage ?: "") }
    var maintenance by remember(settings?.maintenanceMessage) { mutableStateOf(settings?.maintenanceMessage ?: "") }
    var channel by remember(settings?.requiredChannel) { mutableStateOf(settings?.requiredChannel ?: "") }
    var forceSubscription by remember(settings?.forceSubscription) { mutableStateOf(settings?.forceSubscription ?: true) }
    LazyColumn(Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { Text("نصوص البوت والاشتراك", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold) }
        item { Text("هذه الإعدادات تُحفظ في قاعدة البوت. تأكد من أن حساب البوت يستطيع الوصول إلى القناة التي تحددها.") }
        item { OutlinedTextField(value = welcome, onValueChange = { welcome = it.take(4000) }, label = { Text("رسالة الترحيب") }, modifier = Modifier.fillMaxWidth(), minLines = 3) }
        item { OutlinedTextField(value = subscriptionText, onValueChange = { subscriptionText = it.take(4000) }, label = { Text("رسالة الاشتراك الإجباري") }, modifier = Modifier.fillMaxWidth(), minLines = 3) }
        item { OutlinedTextField(value = terms, onValueChange = { terms = it.take(4000) }, label = { Text("الشروط والأحكام") }, modifier = Modifier.fillMaxWidth(), minLines = 3) }
        item { OutlinedTextField(value = maintenance, onValueChange = { maintenance = it.take(4000) }, label = { Text("رسالة الصيانة") }, modifier = Modifier.fillMaxWidth(), minLines = 3) }
        item { OutlinedTextField(value = channel, onValueChange = { channel = it.take(100) }, label = { Text("معرف القناة مثل @MyChannel أو رقم يبدأ بـ -100") }, modifier = Modifier.fillMaxWidth(), singleLine = true) }
        item {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("فرض الاشتراك لكل المستخدمين", fontWeight = FontWeight.Bold)
                    Text("عند إيقافه يتجاوز البوت فحص الاشتراك الإجباري.", style = MaterialTheme.typography.bodySmall)
                }
                Switch(checked = forceSubscription, onCheckedChange = { forceSubscription = it })
            }
        }
        item {
            Button(onClick = {
                onSave(BotContentSettings(welcome, subscriptionText, terms, maintenance, channel.trim(), forceSubscription))
            }, enabled = settings != null && channel.isNotBlank(), modifier = Modifier.fillMaxWidth()) { Text("حفظ إعدادات البوت") }
        }
        if (message.isNotBlank()) item { Text(message, color = MaterialTheme.colorScheme.primary) }
    }
}
