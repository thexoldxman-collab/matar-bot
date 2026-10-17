package com.matar.admin

import android.os.Bundle
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
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp

private enum class Page(val label: String) {
    HOME("الرئيسية"), ROOM("غرفة العمليات"), USERS("المشرفون"), MESSAGES("الرسائل"), SETTINGS("الإعدادات")
}

data class QueueItem(
    val id: Int,
    val type: String,
    val user: String,
    val amount: String,
    val status: String = "بانتظار التنفيذ",
    val typeKey: String = "charge",
    val userId: Long? = null,
    val claimOwner: Long? = null
)

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
    var pairingCode by remember { mutableStateOf("") }
    var loginMessage by remember { mutableStateOf("") }
    var showLogin by remember { mutableStateOf(true) }
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
    var selectedRequest by remember { mutableStateOf<Int?>(null) }
    var actionNote by remember { mutableStateOf("") }
    var showAppearance by remember { mutableStateOf(false) }

    MaterialTheme(colorScheme = if (useDark) darkColorScheme() else lightColorScheme()) {
        CompositionLocalProvider(androidx.compose.ui.platform.LocalLayoutDirection provides androidx.compose.ui.unit.LayoutDirection.Rtl) {
            if (showLogin && !connected) {
                LoginScreen(
                    code = pairingCode,
                    onCodeChange = { pairingCode = it.filter { ch -> ch.isDigit() }.take(6) },
                    message = loginMessage,
                    connecting = connecting,
                    onConnect = {
                        val cleanCode = pairingCode.trim()
                        if (!cleanCode.matches(Regex("\\d{6}"))) {
                            loginMessage = "اكتب الرمز الرقمي المؤلف من 6 خانات الذي وصلك من البوت بعد إرسال /link."
                        } else {
                            scope.launch {
                                connecting = true
                                val result = withContext(Dispatchers.IO) { AdminApi.exchangePairingCode(cleanCode) }
                                connecting = false
                                if (result.token != null) {
                                    accessToken = result.token
                                    accountRole = result.role
                                    if (result.role == "owner") {
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
                            Page.values().filter { !connected || accountRole == "owner" || it != Page.USERS }.forEach { item ->
                                val icon = when (item) {
                                    Page.HOME -> Icons.Default.Dashboard
                                    Page.ROOM -> Icons.Default.Groups
                                    Page.USERS -> Icons.Default.AdminPanelSettings
                                    Page.MESSAGES -> Icons.Default.MarkChatUnread
                                    Page.SETTINGS -> Icons.Default.Settings
                                }
                                NavigationBarItem(
                                    selected = page == item,
                                    onClick = {
                                        page = item
                                        if (item == Page.USERS && accessToken != null) {
                                            scope.launch {
                                                moderators = withContext(Dispatchers.IO) { AdminApi.loadModerators(accessToken!!) } ?: moderators
                                            }
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
                            Page.HOME -> HomeScreen(onGoRoom = { page = Page.ROOM }, onGoSettings = { page = Page.SETTINGS })
                            Page.ROOM -> OperationsRoom(
                                queue = queue,
                                selected = selectedRequest,
                                note = actionNote,
                                message = operationMessage,
                                liveMode = connected && liveOperations,
                                onNoteChange = { actionNote = it },
                                onSelect = { id ->
                                    val token = accessToken
                                    val item = queue.firstOrNull { it.id == id }
                                    if (connected && liveOperations && token != null && item != null) {
                                        scope.launch {
                                            val error = withContext(Dispatchers.IO) { AdminApi.claimOperation(token, item.typeKey, id) }
                                            if (error == null) {
                                                selectedRequest = id
                                                queue = withContext(Dispatchers.IO) { AdminApi.loadOperations(token) } ?: queue
                                                operationMessage = "تم استلام الطلب باسم حسابك لمدة 10 دقائق."
                                            } else {
                                                operationMessage = error
                                            }
                                        }
                                    } else {
                                        selectedRequest = id
                                    }
                                },
                                onTake = { id ->
                                    if (connected && liveOperations) {
                                        operationMessage = "تم استلام الطلب. خيارات التنفيذ المالي لم تُفعّل بعد حتى لا نعلن نجاحاً وهمياً."
                                    } else {
                                        queue = queue.map { if (it.id == id) it.copy(status = "قيد التنفيذ — مشرف تجريبي") else it }
                                    }
                                },
                                onComplete = { id ->
                                    val token = accessToken
                                    val item = queue.firstOrNull { it.id == id }
                                    if (connected && liveOperations && token != null && item != null) {
                                        scope.launch {
                                            operationMessage = withContext(Dispatchers.IO) { AdminApi.completeOperation(token, item.typeKey, id) }
                                        }
                                    } else {
                                        queue = queue.map { if (it.id == id) it.copy(status = "منجز تجريبياً") else it }
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
                                            savingNotifications = false
                                            notificationMessage = if (saved) "تم حفظ تفضيلاتك على الخادم. توصيل الإشعارات الفعلية بالخلفية لم يُفعّل بعد." else "تعذر الحفظ؛ تأكد من اتصال الخادم وصلاحية الجلسة."
                                        }
                                    }
                                },
                                savingNotifications = savingNotifications,
                                notificationMessage = notificationMessage,
                                onLogin = {
                                    val oldToken = accessToken
                                    if (oldToken != null) scope.launch { withContext(Dispatchers.IO) { AdminApi.logout(oldToken) } }
                                    accessToken = null
                                    accountRole = null
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
private fun HomeScreen(onGoRoom: () -> Unit, onGoSettings: () -> Unit) {
    LazyColumn(Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { Text("أهلاً بك في مركز القيادة", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold) }
        item { Text("نظرة عامة تجريبية — الأرقام ليست بيانات حقيقية.") }
        item {
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                MetricCard("طلبات الشحن", "12", Icons.Default.South, Modifier.weight(1f))
                MetricCard("طلبات السحب", "4", Icons.Default.North, Modifier.weight(1f))
            }
        }
        item {
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                MetricCard("المشرفون", "3", Icons.Default.Groups, Modifier.weight(1f))
                MetricCard("تنبيهات", "2", Icons.Default.NotificationsActive, Modifier.weight(1f))
            }
        }
        item {
            Card(Modifier.fillMaxWidth(), shape = RoundedCornerShape(18.dp)) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("أمان التشغيل", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                    Text("وضع الاختبار مفعل. العمليات المالية الحقيقية مقفلة حتى موافقة المالك.")
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Default.Lock, contentDescription = null)
                        Spacer(Modifier.width(8.dp))
                        Text("التنفيذ الحقيقي: مقفول")
                    }
                }
            }
        }
        item { Button(onClick = onGoRoom, modifier = Modifier.fillMaxWidth()) { Text("فتح غرفة العمليات") } }
        item { OutlinedButton(onClick = onGoSettings, modifier = Modifier.fillMaxWidth()) { Text("إعدادات الإشعارات والمظهر") } }
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
    queue: List<QueueItem>, selected: Int?, note: String,
    message: String, liveMode: Boolean,
    onNoteChange: (String) -> Unit, onSelect: (Int) -> Unit,
    onTake: (Int) -> Unit, onComplete: (Int) -> Unit
) {
    LazyColumn(Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { Text("غرفة العمليات المشتركة", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold) }
        item { Text(if (liveMode) "قائمة الطلبات متصلة بالخادم. الاستلام يقفل الطلب 10 دقائق؛ إتمام المعاملة المالية محظور حتى ربط المعالجة الذرية." else "آلية الاستلام والتنفيذ معروضة تجريبياً. لن تُنفّذ أي معاملة حقيقية.") }
        if (message.isNotBlank()) item {
            Card(Modifier.fillMaxWidth()) { Text(message, modifier = Modifier.padding(12.dp), color = MaterialTheme.colorScheme.primary) }
        }
        if (queue.isEmpty()) item { Text(if (liveMode) "لا توجد طلبات مفتوحة مسموح لك بعرضها حالياً." else "هذه طلبات توضيحية للمعاينة فقط.") }
        items(queue, key = { it.id }) { item ->
            Card(Modifier.fillMaxWidth(), shape = RoundedCornerShape(16.dp)) {
                Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text("#${item.id}  ${item.type}", modifier = Modifier.weight(1f), fontWeight = FontWeight.Bold)
                        AssistChip(onClick = {}, label = { Text(item.status) })
                    }
                    Text("صاحب الطلب: ${item.user}")
                    if (item.claimOwner != null) Text("تم استلام الطلب بواسطة حساب تيليغرام: ${item.claimOwner}", style = MaterialTheme.typography.bodySmall)
                    Text("المبلغ: ${item.amount}")
                    if (selected == item.id) {
                        OutlinedTextField(value = note, onValueChange = onNoteChange, label = { Text("ملاحظات / تفاصيل الإجراء") }, modifier = Modifier.fillMaxWidth())
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            Button(onClick = { onTake(item.id) }, modifier = Modifier.weight(1f)) { Text("إجراء") }
                            OutlinedButton(onClick = { onComplete(item.id) }, modifier = Modifier.weight(1f)) { Text("تم التنفيذ") }
                        }
                    } else {
                        Button(onClick = { onSelect(item.id) }, modifier = Modifier.fillMaxWidth()) { Text("تنفيذ الطلب") }
                    }
                }
            }
        }
    }
}

@Composable
private fun ModeratorsScreen(
    moderators: List<ModeratorItem>,
    message: String,
    onRefresh: () -> Unit,
    onAdd: (Long, String, Map<String, Boolean>) -> Unit,
    onDelete: (Long) -> Unit
) {
    var userId by remember { mutableStateOf("") }
    var name by remember { mutableStateOf("") }
    var canCharges by remember { mutableStateOf(false) }
    var canWithdraws by remember { mutableStateOf(false) }
    var canBroadcast by remember { mutableStateOf(false) }
    var canViewStats by remember { mutableStateOf(false) }
    var canButtons by remember { mutableStateOf(false) }
    var canAI by remember { mutableStateOf(false) }
    LazyColumn(Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { Text("إدارة المشرفين", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold) }
        item { Text("تُقرأ الصلاحيات من الخادم. الصلاحيات الحساسة لا يمنحها إلا المدير.") }
        item { OutlinedTextField(value = userId, onValueChange = { userId = it.filter { ch -> ch.isDigit() }.take(18) }, label = { Text("معرف تيليغرام") }, modifier = Modifier.fillMaxWidth(), singleLine = true) }
        item { OutlinedTextField(value = name, onValueChange = { name = it.take(80) }, label = { Text("اسم المشرف (اختياري)") }, modifier = Modifier.fillMaxWidth(), singleLine = true) }
        item { PermissionToggle("إدارة طلبات الشحن", canCharges) { canCharges = it } }
        item { PermissionToggle("إدارة طلبات السحب", canWithdraws) { canWithdraws = it } }
        item { PermissionToggle("إرسال رسائل جماعية", canBroadcast) { canBroadcast = it } }
        item { PermissionToggle("عرض الإحصائيات", canViewStats) { canViewStats = it } }
        item { PermissionToggle("إدارة أزرار البوت", canButtons) { canButtons = it } }
        item { PermissionToggle("استخدام المساعد الذكي", canAI) { canAI = it } }
        item {
            Button(
                onClick = {
                    val parsed = userId.toLongOrNull()
                    if (parsed != null && parsed > 0) onAdd(parsed, name.trim(), mapOf(
                        "can_handle_charges" to canCharges,
                        "can_handle_withdraws" to canWithdraws,
                        "can_send_broadcast" to canBroadcast,
                        "can_view_stats" to canViewStats,
                        "can_manage_buttons" to canButtons,
                        "can_use_ai" to canAI
                    ))
                },
                enabled = userId.toLongOrNull()?.let { it > 0 } == true,
                modifier = Modifier.fillMaxWidth()
            ) { Text("إضافة مشرف") }
        }
        item { OutlinedButton(onClick = onRefresh, modifier = Modifier.fillMaxWidth()) { Text("تحديث قائمة المشرفين") } }
        if (message.isNotBlank()) item { Text(message, color = MaterialTheme.colorScheme.primary) }
        item { Text("المشرفون الحاليون", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold) }
        if (moderators.isEmpty()) item { Text("لا توجد بيانات مشرفين محمّلة. اضغط تحديث القائمة.") }
        items(moderators, key = { it.userId }) { moderator ->
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Column(Modifier.weight(1f)) {
                            Text(moderator.customName.ifBlank { "مشرف " + moderator.userId }, fontWeight = FontWeight.Bold)
                            Text("معرف تيليغرام: " + moderator.userId, style = MaterialTheme.typography.bodySmall)
                        }
                        IconButton(onClick = { onDelete(moderator.userId) }) {
                            Icon(Icons.Default.DeleteOutline, contentDescription = "حذف المشرف")
                        }
                    }
                    Text(
                        moderator.permissions.filterValues { it }.keys.joinToString(" • ") { it.removePrefix("can_").replace('_', ' ') }
                            .ifBlank { "لا توجد صلاحيات مفعّلة" },
                        style = MaterialTheme.typography.bodySmall
                    )
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
        Button(onClick = { confirm = true }, enabled = connected && !sending && message.isNotBlank(), modifier = Modifier.fillMaxWidth()) {
            Text(if (sending) "جارٍ الإرسال..." else "مراجعة وإرسال")
        }
        if (!connected) Text("يلزم تسجيل الدخول للاتصال بالخادم قبل الإرسال.", style = MaterialTheme.typography.bodySmall)
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
    onLogin: () -> Unit
) {
    LazyColumn(Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        item { Text("الإعدادات", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold) }
        item { Text("الإشعارات التي تريد استلامها بالخلفية") }
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
        item { Text("سجل التدقيق سيعرض المستخدم والإجراء والوقت والنتيجة بعد تفعيل واجهة الخادم.", style = MaterialTheme.typography.bodySmall) }
    }
}
