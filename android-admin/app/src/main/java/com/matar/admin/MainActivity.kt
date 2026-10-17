package com.matar.admin

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp

private enum class Page(val label: String) {
    HOME("الرئيسية"), ROOM("غرفة العمليات"), USERS("المشرفون"), MESSAGES("الرسائل"), SETTINGS("الإعدادات")
}

private data class QueueItem(val id: Int, val type: String, val user: String, val amount: String, val status: String = "بانتظار التنفيذ")

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { MatarAdminApp() }
    }
}

@Composable
private fun MatarAdminApp() {
    var dark by remember { mutableStateOf<Boolean?>(null) }
    val useDark = dark ?: isSystemInDarkTheme()
    var page by remember { mutableStateOf(Page.HOME) }
    var demoMode by remember { mutableStateOf(true) }
    var connected by remember { mutableStateOf(false) }
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
                    onCodeChange = { pairingCode = it },
                    message = loginMessage,
                    onConnect = {
                        loginMessage = "تسجيل الدخول غير مفعّل بعد: يلزم ربط الخادم والتحقق من كود تيليغرام قبل منح أي صلاحية."
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
                                    Text(if (connected) "متصل بالخادم" else "وضع معاينة غير متصل", style = MaterialTheme.typography.labelSmall)
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
                            Page.values().forEach { item ->
                                val icon = when (item) {
                                    Page.HOME -> Icons.Default.Dashboard
                                    Page.ROOM -> Icons.Default.Groups
                                    Page.USERS -> Icons.Default.AdminPanelSettings
                                    Page.MESSAGES -> Icons.Default.MarkChatUnread
                                    Page.SETTINGS -> Icons.Default.Settings
                                }
                                NavigationBarItem(
                                    selected = page == item,
                                    onClick = { page = item },
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
                                    "معاينة فقط — لا يوجد اتصال بالبوت ولا تُنفّذ أي عملية حقيقية",
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
                                onNoteChange = { actionNote = it },
                                onSelect = { selectedRequest = it },
                                onTake = { id ->
                                    queue = queue.map { if (it.id == id) it.copy(status = "قيد التنفيذ — مشرف تجريبي") else it }
                                },
                                onComplete = { id ->
                                    queue = queue.map { if (it.id == id) it.copy(status = "منجز تجريبياً") else it }
                                    selectedRequest = null
                                    actionNote = ""
                                }
                            )
                            Page.USERS -> ModeratorsScreen()
                            Page.MESSAGES -> MessagesScreen()
                            Page.SETTINGS -> SettingsScreen(
                                notifications = notifications,
                                onNotificationChange = { key, value -> notifications = notifications + (key to value) },
                                onTheme = { showAppearance = true },
                                onLogin = { showLogin = true; connected = false }
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
private fun LoginScreen(code: String, onCodeChange: (String) -> Unit, message: String, onConnect: () -> Unit, onPreview: () -> Unit) {
    Column(
        Modifier.fillMaxSize().padding(24.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Icon(Icons.Default.Shield, contentDescription = null, modifier = Modifier.size(64.dp), tint = MaterialTheme.colorScheme.primary)
        Spacer(Modifier.height(12.dp))
        Text("Matar Admin", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
        Text("مركز التحكم ببوت مطر", style = MaterialTheme.typography.titleMedium)
        Spacer(Modifier.height(24.dp))
        Text("تسجيل الدخول الآمن", style = MaterialTheme.typography.titleLarge)
        Text("سيتم ربط الحساب عبر تيليغرام والتحقق من الهوية والصلاحية على الخادم.", textAlign = TextAlign.Center)
        Spacer(Modifier.height(12.dp))
        OutlinedTextField(
            value = code, onValueChange = onCodeChange,
            label = { Text("رمز الربط من بوت تيليغرام") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true
        )
        Spacer(Modifier.height(10.dp))
        Button(onClick = onConnect, modifier = Modifier.fillMaxWidth()) { Text("تحقق وتسجيل الدخول") }
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
    onNoteChange: (String) -> Unit, onSelect: (Int) -> Unit,
    onTake: (Int) -> Unit, onComplete: (Int) -> Unit
) {
    LazyColumn(Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { Text("غرفة العمليات المشتركة", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold) }
        item { Text("آلية الاستلام والتنفيذ معروضة تجريبياً. ستُقفل الطلبات على الخادم لمنع تنفيذ الطلب من مشرفين اثنين.") }
        items(queue, key = { it.id }) { item ->
            Card(Modifier.fillMaxWidth(), shape = RoundedCornerShape(16.dp)) {
                Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text("#${item.id}  ${item.type}", modifier = Modifier.weight(1f), fontWeight = FontWeight.Bold)
                        AssistChip(onClick = {}, label = { Text(item.status) })
                    }
                    Text("صاحب الطلب: ${item.user}")
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
private fun ModeratorsScreen() {
    LazyColumn(Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { Text("إدارة المشرفين", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold) }
        item { Text("في النسخة المتصلة ستُقرأ القائمة من الخادم، ولا يمكن لأي مشرف منح نفسه صلاحيات.") }
        items(listOf("مشرف الشحن — مثال", "مشرف السحب — مثال", "مشرف الرسائل — مثال")) { name ->
            Card(Modifier.fillMaxWidth()) {
                Row(Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Default.AccountCircle, contentDescription = null)
                    Spacer(Modifier.width(10.dp))
                    Text(name, modifier = Modifier.weight(1f))
                    Icon(Icons.Default.Lock, contentDescription = "صلاحيات من الخادم")
                }
            }
        }
        item { OutlinedButton(onClick = {}, enabled = false, modifier = Modifier.fillMaxWidth()) { Text("إضافة مشرف — تتطلب اتصال الخادم") } }
    }
}

@Composable
private fun MessagesScreen() {
    var target by remember { mutableStateOf("الكل") }
    var message by remember { mutableStateOf("") }
    Column(Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("الرسائل", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
        Text("إرسال الرسائل واستقبالها سيعمل عبر الخادم بعد ربط واجهات البوت.")
        Text("جهة الإرسال")
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            listOf("الكل", "مستخدم", "المشرفون").forEach { option ->
                FilterChip(selected = target == option, onClick = { target = option }, label = { Text(option) })
            }
        }
        OutlinedTextField(value = message, onValueChange = { message = it }, label = { Text("اكتب الرسالة") }, modifier = Modifier.fillMaxWidth(), minLines = 4)
        Button(onClick = {}, enabled = false, modifier = Modifier.fillMaxWidth()) { Text("إرسال — يتطلب اتصال الخادم") }
        Text("الرسائل الواردة ستظهر هنا مع سجل المحادثة وحالة التسليم.", style = MaterialTheme.typography.bodySmall)
    }
}

@Composable
private fun SettingsScreen(
    notifications: Map<String, Boolean>,
    onNotificationChange: (String, Boolean) -> Unit,
    onTheme: () -> Unit,
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
        item { Button(onClick = {}, enabled = false, modifier = Modifier.fillMaxWidth()) { Text("حفظ الإشعارات على الخادم — قريباً") } }
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
