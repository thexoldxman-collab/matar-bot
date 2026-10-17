import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;

const apiBase = 'https://matar-bot.onrender.com';
const secureStore = FlutterSecureStorage();

void main() => runApp(const MatarAdminApp());

class MatarAdminApp extends StatelessWidget {
  const MatarAdminApp({super.key});
  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'إدارة Matar Bot',
    debugShowCheckedModeBanner: false,
    theme: ThemeData(colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF176B68)), useMaterial3: true),
    home: const Directionality(textDirection: TextDirection.rtl, child: AdminHome()),
  );
}

class AdminHome extends StatefulWidget {
  const AdminHome({super.key});
  @override
  State<AdminHome> createState() => _AdminHomeState();
}

class _AdminHomeState extends State<AdminHome> {
  String? token;
  Map<String, dynamic>? data;
  String? error;
  bool busy = false;
  final code = TextEditingController();
  final prompt = TextEditingController();
  final chat = <Map<String, String>>[];

  @override
  void initState() {
    super.initState();
    secureStore.read(key: 'admin_session').then((value) async {
      if (value != null && mounted) {
        setState(() => token = value);
        await refresh();
      }
    });
  }

  @override
  void dispose() {
    code.dispose();
    prompt.dispose();
    super.dispose();
  }

  Map<String, dynamic> decode(http.Response r) {
    try {
      final v = jsonDecode(r.body);
      if (v is Map<String, dynamic>) return v;
    } catch (_) {}
    return <String, dynamic>{'ok': false, 'error': 'رد غير مفهوم من الخادم'};
  }

  String friendly(Object e) => e.toString().replaceFirst('Exception: ', '');

  Future<void> pair() async {
    setState(() { busy = true; error = null; });
    try {
      final r = await http.post(Uri.parse(apiBase + '/api/admin/v1/pair'),
        headers: {'Content-Type': 'application/json'}, body: jsonEncode({'code': code.text.trim()}))
        .timeout(const Duration(seconds: 80));
      final v = decode(r);
      if (r.statusCode != 200 || v['token'] == null) throw Exception(v['error'] ?? 'تعذر الربط');
      token = v['token'] as String;
      await secureStore.write(key: 'admin_session', value: token);
      code.clear();
      await refresh();
    } catch (e) {
      if (mounted) setState(() => error = friendly(e));
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<Map<String, dynamic>> call(String path, {Map<String, dynamic>? body}) async {
    final headers = {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + (token ?? '')};
    final r = body == null
      ? await http.get(Uri.parse(apiBase + path), headers: headers).timeout(const Duration(seconds: 80))
      : await http.post(Uri.parse(apiBase + path), headers: headers, body: jsonEncode(body)).timeout(const Duration(seconds: 130));
    final v = decode(r);
    if (r.statusCode == 401) {
      await secureStore.delete(key: 'admin_session');
      token = null;
      data = null;
      throw Exception('انتهت الجلسة. اربط التطبيق من جديد من تلغرام.');
    }
    if (r.statusCode < 200 || r.statusCode >= 300 || v['ok'] == false) {
      throw Exception(v['error'] ?? 'تعذر تنفيذ الطلب');
    }
    return v;
  }

  Future<void> refresh() async {
    if (token == null) return;
    setState(() { busy = true; error = null; });
    try { data = await call('/api/admin/v1/overview'); }
    catch (e) { error = friendly(e); }
    finally { if (mounted) setState(() => busy = false); }
  }

  Future<void> maintenance(bool enabled) async {
    setState(() { busy = true; error = null; });
    try { await call('/api/admin/v1/maintenance', body: {'enabled': enabled}); await refresh(); }
    catch (e) { if (mounted) setState(() => error = friendly(e)); }
    finally { if (mounted) setState(() => busy = false); }
  }

  Future<void> demoMode() async {
    final yes = await showDialog<bool>(context: context, builder: (c) => AlertDialog(
      title: const Text('الرجوع للوضع التجريبي'),
      content: const Text('تأكيد الرجوع إلى قاعدة الاختبار؟'),
      actions: [
        TextButton(onPressed: () => Navigator.pop(c, false), child: const Text('إلغاء')),
        FilledButton(onPressed: () => Navigator.pop(c, true), child: const Text('تأكيد')),
      ],
    ));
    if (yes != true) return;
    setState(() { busy = true; error = null; });
    try { await call('/api/admin/v1/mode', body: {'mode': 'demo'}); await refresh(); }
    catch (e) { if (mounted) setState(() => error = friendly(e)); }
    finally { if (mounted) setState(() => busy = false); }
  }

  Future<void> askAi() async {
    final text = prompt.text.trim();
    if (text.isEmpty || busy) return;
    prompt.clear();
    setState(() { chat.add({'role': 'user', 'text': text}); busy = true; error = null; });
    try {
      final v = await call('/api/admin/v1/ai', body: {'message': text});
      chat.add({'role': 'assistant', 'text': (v['answer'] ?? '').toString()});
    } catch (e) { error = friendly(e); }
    finally { if (mounted) setState(() => busy = false); }
  }

  Future<void> logout() async {
    await secureStore.delete(key: 'admin_session');
    if (mounted) setState(() { token = null; data = null; chat.clear(); error = null; });
  }

  Widget err() => Card(color: const Color(0xFFFFE9E6), child: Padding(
    padding: const EdgeInsets.all(12), child: Text(error ?? '')));

  Widget line(String label, String value) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 5),
    child: Row(children: [Expanded(child: Text(label)), Text(value, style: const TextStyle(fontWeight: FontWeight.bold))]));

  @override
  Widget build(BuildContext context) {
    if (token == null) return Scaffold(
      appBar: AppBar(title: const Text('إدارة Matar Bot')),
      body: Center(child: SingleChildScrollView(padding: const EdgeInsets.all(22), child: Card(
        child: Padding(padding: const EdgeInsets.all(20), child: Column(mainAxisSize: MainAxisSize.min, children: [
          const Icon(Icons.admin_panel_settings, size: 56),
          const Text('دخول آمن للمالك فقط', style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          const Text('أرسل الأمر /admin_app_pair للبوت في تلغرام، ثم أدخل رمز الربط هنا. الرمز صالح لخمس دقائق ولمرة واحدة.'),
          const SizedBox(height: 14),
          TextField(controller: code, textDirection: TextDirection.ltr, decoration: const InputDecoration(labelText: 'رمز الربط', border: OutlineInputBorder())),
          if (error != null) err(),
          const SizedBox(height: 12),
          SizedBox(width: double.infinity, child: FilledButton(onPressed: busy ? null : pair, child: Text(busy ? 'جارٍ الربط...' : 'ربط التطبيق'))),
        ]))))),
    );
    final counts = Map<String, dynamic>.from(data?['counts'] ?? {});
    final services = Map<String, dynamic>.from(data?['services'] ?? {});
    final maintenanceOn = data?['bot_status'] != 'active';
    return Scaffold(
      appBar: AppBar(title: const Text('إدارة Matar Bot'), actions: [
        IconButton(onPressed: busy ? null : refresh, icon: const Icon(Icons.refresh)),
        IconButton(onPressed: logout, icon: const Icon(Icons.logout)),
      ]),
      body: RefreshIndicator(onRefresh: refresh, child: ListView(padding: const EdgeInsets.all(14), children: [
        if (error != null) err(),
        if (data == null) const Center(child: Padding(padding: EdgeInsets.all(25), child: CircularProgressIndicator())),
        if (data != null) ...[
          Card(child: Padding(padding: const EdgeInsets.all(16), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            const Text('الحالة العامة', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            line('وضع التشغيل', data?['mode'] == 'demo' ? 'تجريبي' : 'حقيقي'),
            line('حالة البوت', maintenanceOn ? 'صيانة' : 'يعمل'),
            line('المساعد الذكي', data?['ai_ready'] == true ? 'جاهز' : 'غير مفعّل'),
          ]))),
          Card(child: Padding(padding: const EdgeInsets.all(16), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            const Text('ملخص البوت', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            line('المستخدمون', (counts['users'] ?? 0).toString()),
            line('المشرفون', (counts['moderators'] ?? 0).toString()),
            line('الأزرار النشطة', (counts['active_buttons'] ?? 0).toString()),
          ]))),
          Card(child: Padding(padding: const EdgeInsets.all(16), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            const Text('حالة الخدمات', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            ...services.values.map((raw) { final s = Map<String, dynamic>.from(raw as Map); return line((s['label'] ?? 'خدمة').toString(), s['active'] == true ? 'مفعّلة' : 'متوقفة'); }),
            const Text('عرض حالة فقط؛ لا يوجد تفعيل API مالي حقيقي في هذه المرحلة.', style: TextStyle(fontSize: 12)),
          ]))),
          Card(child: Padding(padding: const EdgeInsets.all(16), child: Column(children: [
            const Align(alignment: Alignment.centerRight, child: Text('التحكم الآمن', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold))),
            const SizedBox(height: 8),
            SizedBox(width: double.infinity, child: FilledButton.icon(
              onPressed: busy ? null : () => maintenance(!maintenanceOn),
              icon: Icon(maintenanceOn ? Icons.play_arrow : Icons.build),
              label: Text(maintenanceOn ? 'إنهاء الصيانة وتشغيل البوت' : 'إيقاف البوت للصيانة'))),
            SizedBox(width: double.infinity, child: OutlinedButton.icon(onPressed: busy ? null : demoMode, icon: const Icon(Icons.science), label: const Text('الرجوع للوضع التجريبي'))),
            const Text('الانتقال للوضع الحقيقي مقفول حتى اكتمال فحوصات الجاهزية.', style: TextStyle(fontSize: 12)),
          ]))),
          Card(child: Padding(padding: const EdgeInsets.all(16), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            const Text('المساعد الذكي المجاني', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            const Text('يساعدك بالفهم والتحليل. هذا الإصدار لا ينفذ تغييرات مالية أو برمجية تلقائياً.'),
            if (chat.isNotEmpty) ...chat.map((m) => Align(
              alignment: m['role'] == 'user' ? Alignment.centerRight : Alignment.centerLeft,
              child: Container(margin: const EdgeInsets.symmetric(vertical: 4), padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(color: m['role'] == 'user' ? const Color(0xFFD8ECEA) : Colors.white, borderRadius: BorderRadius.circular(10)),
                child: Text(m['text'] ?? '')))),
            Row(children: [
              Expanded(child: TextField(controller: prompt, minLines: 1, maxLines: 4, decoration: const InputDecoration(hintText: 'اكتب سؤالك...', border: OutlineInputBorder()), onSubmitted: (_) => askAi())),
              IconButton.filled(onPressed: busy ? null : askAi, icon: const Icon(Icons.send)),
            ]),
            if (busy) const LinearProgressIndicator(),
          ]))),
        ],
      ])),
    );
  }
}
