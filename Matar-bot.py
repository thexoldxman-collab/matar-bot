import telebot
from telebot import types
from flask import Flask
from threading import Thread
import os
import sqlite3
from datetime import datetime, timedelta
import random
import string
import time
import hashlib
import json

# ==========================================
# 1. إعدادات البوت والسيرفر الأساسية
# ==========================================
TOKEN = os.environ.get('TOKEN')
bot = telebot.TeleBot(TOKEN)
ADMIN_ID = 846938470  
CHANNEL_ID = "@Matar_ichancy"
CHANNEL_URL = "https://t.me/Matar_ichancy"

app = Flask('')

@app.route('/')
def home():
    return "Matar Pro System: Status Online - Anti-Lag Active"

def run_server():
    port = int(os.environ.get("PORT", 10000))
    try:
        app.run(host='0.0.0.0', port=port)
    except Exception as e:
        print(f"Server Startup Error: {e}")

def keep_alive():
    t = Thread(target=run_server)
    t.daemon = True
    t.start()

# ==========================================
# 2. نظام قاعدة البيانات المتكامل (محدث ومصلح)
# ==========================================
def setup_database():
    conn = sqlite3.connect("matar_pro_final.db", check_same_thread=False)
    cursor = conn.cursor()
    
    # جدول المستخدمين الشامل
    cursor.execute("""CREATE TABLE IF NOT EXISTS users(
        user_id INTEGER PRIMARY KEY, 
        acc_name TEXT, 
        acc_password TEXT,
        balance REAL DEFAULT 0, 
        site_balance REAL DEFAULT 0, 
        status TEXT DEFAULT 'active', 
        created_at TEXT,
        deleted INTEGER DEFAULT 0,
        first_name TEXT,
        username TEXT,
        custom_name TEXT,
        ref_code TEXT UNIQUE,
        referred_by INTEGER,
        referral_count INTEGER DEFAULT 0,
        current_earnings REAL DEFAULT 0,
        total_earnings REAL DEFAULT 0)
    """)

    cursor.execute("""CREATE TABLE IF NOT EXISTS gifts(
        code TEXT PRIMARY KEY, value REAL, limit_count INTEGER, 
        used_count INTEGER DEFAULT 0, type TEXT DEFAULT 'individual',
        created_by INTEGER, created_at TEXT)""")

    cursor.execute("""CREATE TABLE IF NOT EXISTS gift_usage(
        user_id INTEGER, code TEXT, used_at TEXT, UNIQUE(user_id, code))""")
    
    cursor.execute("""CREATE TABLE IF NOT EXISTS transactions(
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, type TEXT,
        amount REAL, commission REAL DEFAULT 0, net_amount REAL DEFAULT 0,
        method TEXT, status TEXT, transaction_date TEXT, admin_id INTEGER,
        details TEXT, receipt_number TEXT UNIQUE)""")

    cursor.execute("""CREATE TABLE IF NOT EXISTS processed_transactions(
        receipt_number TEXT PRIMARY KEY, user_id INTEGER, amount REAL, processed_at TEXT)""")
    
    cursor.execute("""CREATE TABLE IF NOT EXISTS deleted_accounts(
        user_id INTEGER PRIMARY KEY, acc_name TEXT, acc_password TEXT,
        balance REAL, site_balance REAL, deleted_at TEXT, restored_by INTEGER)""")
    
    cursor.execute("""CREATE TABLE IF NOT EXISTS cashier_balance(
        admin_id INTEGER PRIMARY KEY, balance REAL DEFAULT 0)""")
    
    cursor.execute("""CREATE TABLE IF NOT EXISTS tickets(
        ticket_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
        message TEXT, file_id TEXT, status TEXT DEFAULT 'open', created_at TEXT,
        last_reply_by INTEGER, last_reply_at TEXT, replied_count INTEGER DEFAULT 0)""")
    
    cursor.execute("""CREATE TABLE IF NOT EXISTS ticket_conversations(
        id INTEGER PRIMARY KEY AUTOINCREMENT, ticket_id INTEGER, sender_id INTEGER,
        sender_type TEXT, message TEXT, file_id TEXT, sent_at TEXT)""")
    
    cursor.execute("""CREATE TABLE IF NOT EXISTS moderators(
        user_id INTEGER PRIMARY KEY, custom_name TEXT, added_by INTEGER,
        added_at TEXT, can_reply INTEGER DEFAULT 1, can_change_codes INTEGER DEFAULT 0,
        can_view_transactions INTEGER DEFAULT 0, can_maintenance INTEGER DEFAULT 0,
        can_broadcast INTEGER DEFAULT 0, can_rename_users INTEGER DEFAULT 0,
        permissions TEXT)""")
    
    cursor.execute("""CREATE TABLE IF NOT EXISTS settings(
        key TEXT PRIMARY KEY, value TEXT, updated_at TEXT, updated_by INTEGER)""")
    
    cursor.execute("""CREATE TABLE IF NOT EXISTS referrals_log(
        id INTEGER PRIMARY KEY AUTOINCREMENT, referrer_id INTEGER, referred_id INTEGER,
        joined_at TEXT, UNIQUE(referred_id))""")
    
    cursor.execute("""CREATE TABLE IF NOT EXISTS referral_earnings(
        id INTEGER PRIMARY KEY AUTOINCREMENT, referrer_id INTEGER, amount REAL,
        from_user_id INTEGER, transaction_id INTEGER, cycle_start TEXT, cycle_end TEXT, earned_at TEXT)""")
    
    cursor.execute("""CREATE TABLE IF NOT EXISTS referral_cycles(
        id INTEGER PRIMARY KEY AUTOINCREMENT, start_date TEXT, end_date TEXT, status TEXT DEFAULT 'active')""")
    
    default_settings = [
        ('syriatel_numbers', '42483891,99706078'),
        ('sham_address', 'sham_example@sham'),
        ('usdt_status', 'متوقف'),
        ('binance_status', 'متوقف'),
        ('min_charge', '100'),
        ('min_withdraw_syria', '25000'),
        ('max_withdraw_syria', '500000'),
        ('min_withdraw_sham', '25000'),
        ('max_withdraw_sham', '5000000'),
        ('withdraw_commission', '10'),
        ('bot_status', 'active'),
        ('welcome_message', 'اهلا وسهلا بك في بوت Matar البوت الرسمي لموقع ichancy'),
        ('referral_percentage', '10'),
        ('next_referral_payout', ''),
        ('current_referral_cycle', '')
    ]
    
    # --- السطر 156 المصلح هنا ---
    for key, value in default_settings:
        try:
            cursor.execute("INSERT OR IGNORE INTO settings(key, value) VALUES (?,?)", (key, value))
        except Exception as e:
            print(f"Warning at line 156: {e}")
    
    cursor.execute("INSERT OR IGNORE INTO cashier_balance(admin_id, balance) VALUES (?,0)", (ADMIN_ID,))
    
    cursor.execute("SELECT * FROM referral_cycles WHERE status='active'")
    if not cursor.fetchone():
        start = datetime.now()
        end = start + timedelta(days=10)
        cursor.execute("INSERT INTO referral_cycles (start_date, end_date, status) VALUES (?,?,?)", 
                      (start.strftime("%Y-%m-%d %H:%M:%S"), end.strftime("%Y-%m-%d %H:%M:%S"), 'active'))
    
    conn.commit()
    return conn, cursor

conn, cursor = setup_database()
# ==========================================
# 3. الدوال المساعدة ونظام التوليد
# ==========================================

def generate_ref_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

def generate_receipt():
    return f"MT-{int(time.time())}-{random.randint(1000, 9999)}"

def is_moderator(user_id):
    if user_id == ADMIN_ID: return True
    cursor.execute("SELECT user_id FROM moderators WHERE user_id=?", (user_id,))
    return cursor.fetchone() is not None

def get_permission(user_id, perm):
    if user_id == ADMIN_ID: return True
    cursor.execute("SELECT permissions FROM moderators WHERE user_id=?", (user_id,))
    res = cursor.fetchone()
    if res:
        perms = json.loads(res[0])
        return perms.get(perm, False)
    return False

def get_setting(key):
    cursor.execute("SELECT value FROM settings WHERE key=?", (key,))
    res = cursor.fetchone()
    return res[0] if res else ""

def update_setting(key, value, admin_id):
    cursor.execute("UPDATE settings SET value=?, updated_at=?, updated_by=? WHERE key=?",
                  (value, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), admin_id, key))
    conn.commit()

# ==========================================
# 4. نظام التحقق من الاشتراك الإجباري
# ==========================================
def check_sub(user_id):
    try:
        member = bot.get_chat_member(CHANNEL_ID, user_id)
        if member.status in ['member', 'administrator', 'creator']:
            return True
        return False
    except:
        return True # في حال حدوث خطأ في التلغرام نمرر المستخدم مؤقتاً

# ==========================================
# 5. لوحات المفاتيح (Markups)
# ==========================================
def main_menu(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    # أزرار المستخدم الأساسية
    btn1 = types.KeyboardButton("👤 حسابي")
    btn2 = types.KeyboardButton("💰 شحن الرصيد")
    btn3 = types.KeyboardButton("💸 سحب الأرباح")
    btn4 = types.KeyboardButton("🤝 نظام الإحالة")
    btn5 = types.KeyboardButton("🎁 كود الهدية")
    btn6 = types.KeyboardButton("☎️ الدعم الفني")
    btn7 = types.KeyboardButton("ℹ️ معلومات البوت")
    btn8 = types.KeyboardButton("⚙️ الإعدادات")
    
    markup.add(btn1, btn2, btn3, btn4, btn5, btn6, btn7, btn8)
    
    # إذا كان المستخدم أدمن أو موظف تظهر لوحة التحكم
    if is_moderator(user_id):
        admin_btn = types.KeyboardButton("👨‍✈️ لوحة تحكم الإدارة")
        markup.add(admin_btn)
        
    return markup

def admin_panel():
    markup = types.InlineKeyboardMarkup(row_width=2)
    btns = [
        types.InlineKeyboardButton("📊 إحصائيات عامة", callback_data="admin_stats"),
        types.InlineKeyboardButton("🔍 بحث عن مستخدم", callback_data="admin_search"),
        types.InlineKeyboardButton("💳 إدارة الشحن", callback_data="admin_deposit"),
        types.InlineKeyboardButton("🏧 طلبات السحب", callback_data="admin_withdraw"),
        types.InlineKeyboardButton("🎫 التذاكر المفتوحة", callback_data="admin_tickets"),
        types.InlineKeyboardButton("📢 إذاعة (Broadcast)", callback_data="admin_broadcast"),
        types.InlineKeyboardButton("🎁 إدارة الهدايا", callback_data="admin_gifts"),
        types.InlineKeyboardButton("👥 إدارة الموظفين", callback_data="admin_staff"),
        types.InlineKeyboardButton("⚙️ إعدادات النظام", callback_data="admin_settings"),
        types.InlineKeyboardButton("🔗 نظام الإحالات", callback_data="admin_refs")
    ]
    markup.add(*btns)
    return markup

def settings_panel():
    markup = types.InlineKeyboardMarkup(row_width=2)
    btns = [
        types.InlineKeyboardButton("📝 تغيير اسم الحساب", callback_data="set_acc_name"),
        types.InlineKeyboardButton("🔑 تغيير كلمة المرور", callback_data="set_acc_pass"),
        types.InlineKeyboardButton("👤 الاسم المستعار", callback_data="set_custom_name")
    ]
    markup.add(*btns)
    return markup
# ==========================================
# 6. معالج الرسائل الأساسي (Start Handler)
# ==========================================
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    
    # التحقق من الاشتراك الإجباري
    if not check_sub(user_id):
        markup = types.InlineKeyboardMarkup()
        btn = types.InlineKeyboardButton("📢 اشترك هنا أولاً", url=CHANNEL_URL)
        btn_check = types.InlineKeyboardButton("✅ تم الاشتراك", callback_data="check_subscription")
        markup.add(btn)
        markup.add(btn_check)
        bot.send_message(user_id, f"⚠️ عذراً {first_name}، يجب عليك الاشتراك في قناة البوت الرسمية أولاً لتتمكن من استخدامه.", reply_markup=markup)
        return

    # فحص إذا كان المستخدم مسجلاً مسبقاً
    cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    user = cursor.fetchone()
    
    if not user:
        # نظام الإحالة (إذا دخل المستخدم عبر رابط إحالة)
        referrer_id = None
        if len(message.text.split()) > 1:
            ref_code = message.text.split()[1]
            cursor.execute("SELECT user_id FROM users WHERE ref_code=?", (ref_code,))
            ref_owner = cursor.fetchone()
            if ref_owner and ref_owner[0] != user_id:
                referrer_id = ref_owner[0]

        # إنشاء حساب جديد
        ref_code = generate_ref_code()
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""INSERT INTO users 
            (user_id, first_name, username, ref_code, referred_by, created_at, balance, site_balance) 
            VALUES (?, ?, ?, ?, ?, ?, 0.0, 0.0)""", 
            (user_id, first_name, username, ref_code, referrer_id, created_at))
        
        if referrer_id:
            cursor.execute("UPDATE users SET referral_count = referral_count + 1 WHERE user_id=?", (referrer_id,))
            cursor.execute("INSERT INTO referrals_log (referrer_id, referred_id, joined_at) VALUES (?, ?, ?)",
                          (referrer_id, user_id, created_at))
            
            bot.send_message(referrer_id, f"🔔 مستخدم جديد انضم عبر رابط إحالتك: {first_name}")
        
        conn.commit()
        
    # إرسال رسالة الترحيب والقائمة الرئيسية
    welcome_text = get_setting('welcome_message')
    bot.send_message(user_id, welcome_text, reply_markup=main_menu(user_id))

# ==========================================
# 7. نظام الملف الشخصي (Profile)
# ==========================================
@bot.message_handler(func=lambda message: message.text == "👤 حسابي")
def my_profile(message):
    user_id = message.from_user.id
    cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    user = cursor.fetchone()
    
    if not user:
        bot.reply_to(message, "⚠️ حدث خطأ، لم يتم العثور على حسابك. أرسل /start")
        return

    # تفريغ البيانات من الجدول (بناءً على الترتيب في setup_database)
    # user_id(0), acc_name(1), acc_password(2), balance(3), site_balance(4)...
    status = "✅ نشط" if user[5] == 'active' else "❌ محظور"
    acc_name = user[1] if user[1] else "غير مضبوط"
    acc_pass = user[2] if user[2] else "غير مضبوط"
    
    profile_msg = f"""
✨ **ملفك الشخصي في مطر برو:**
━━━━━━━━━━━━━━━━━
🆔 معرفك: `{user_id}`
👤 الاسم: {user[10] if user[10] else user[8]}
📊 الحالة: {status}

💰 رصيد البوت: {user[3]} $
🌐 رصيد الموقع: {user[4]} $

📝 بيانات الحساب في Ichancy:
👤 الاسم: `{acc_name}`
🔑 كلمة السر: `{acc_pass}`
━━━━━━━━━━━━━━━━━
📅 انضممت في: {user[6]}
"""
    bot.send_message(user_id, profile_msg, parse_mode="Markdown", reply_markup=settings_panel())
# ==========================================
# 8. نظام شحن الرصيد (Deposit System)
# ==========================================
@bot.message_handler(func=lambda message: message.text == "💰 شحن الرصيد")
def deposit_money(message):
    user_id = message.from_user.id
    if not check_sub(user_id): return
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    btns = [
        types.InlineKeyboardButton("🇸🇾 سيريتل كاش / MTN Cash", callback_data="dep_syria"),
        types.InlineKeyboardButton("🏦 شركة الهرم / الفؤاد", callback_data="dep_haram"),
        types.InlineKeyboardButton("🌐 USDT (TRC20)", callback_data="dep_usdt"),
        types.InlineKeyboardButton("🔶 Binance Pay", callback_data="dep_binance")
    ]
    markup.add(*btns)
    
    dep_msg = """
**💰 اختر وسيلة الشحن المناسبة لك:**

- يتم التأكد من الدفع خلال 5 دقائق إلى 24 ساعة.
- الحد الأدنى للشحن: حسب الوسيلة المختارة.
- تأكد من إرسال صورة الإيصال واضحة.
"""
    bot.send_message(user_id, dep_msg, parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('dep_'))
def handle_deposit_methods(call):
    user_id = call.from_user.id
    method = call.data.split('_')[1]
    
    if method == "syria":
        numbers = get_setting('syriatel_numbers')
        msg = f"**🇸🇾 الشحن عبر سيريتل كاش / MTN:**\n\nيرجى التحويل إلى أحد الأرقام التالية:\n`{numbers}`\n\nبعد التحويل، أرسل صورة الإيصال (اللقطة) هنا."
    elif method == "haram":
        address = get_setting('sham_address')
        msg = f"**🏦 الشحن عبر الهرم / الفؤاد:**\n\nيرجى التحويل إلى العنوان التالي:\n`{address}`\n\nبعد التحويل، أرسل صورة الإيصال الواضحة هنا."
    elif method == "usdt":
        status = get_setting('usdt_status')
        if status == "متوقف":
            bot.answer_callback_query(call.id, "⚠️ عذراً، الشحن عبر USDT متوقف حالياً.")
            return
        msg = "🌐 يرجى إرسال مبلغ USDT إلى العنوان التالي: (سيتم تزويدك به عبر الدعم)"
    elif method == "binance":
        status = get_setting('binance_status')
        if status == "متوقف":
            bot.answer_callback_query(call.id, "⚠️ عذراً، الشحن عبر باينانس متوقف حالياً.")
            return
        msg = "🔶 يرجى إرسال المعرف الخاص بك في باينانس للتواصل."

    bot.edit_message_text(msg, user_id, call.message.message_id, parse_mode="Markdown")
    bot.register_next_step_handler(call.message, process_deposit_step, method)

def process_deposit_step(message, method):
    user_id = message.from_user.id
    
    if message.text == "🔙 عودة" or message.text == "/start":
        bot.send_message(user_id, "تم إلغاء العملية.", reply_markup=main_menu(user_id))
        return

    if not message.photo:
        msg = bot.send_message(user_id, "❌ خطأ! يجب إرسال صورة إيصال الدفع حصراً. حاول مرة أخرى أو أرسل '🔙 عودة'")
        bot.register_next_step_handler(msg, process_deposit_step, method)
        return

    # معالجة الصورة
    file_id = message.photo[-1].file_id
    receipt = generate_receipt()
    
    # تسجيل العملية في قاعدة البيانات كـ "قيد الانتظار"
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""INSERT INTO transactions 
        (user_id, type, method, status, transaction_date, receipt_number, details) 
        VALUES (?, 'deposit', ?, 'pending', ?, ?, ?)""",
        (user_id, method, created_at, receipt, file_id))
    conn.commit()

    # إشعار المستخدم
    bot.send_message(user_id, f"✅ تم استلام طلب الشحن بنجاح.\n🎫 رقم الإيصال: `{receipt}`\nسيتم مراجعته من قبل الإدارة قريباً.", parse_mode="Markdown")

    # إشعار الإدارة (الأدمن)
    admin_msg = f"""
🆕 **طلب شحن جديد!**
━━━━━━━━━━━━━━━━━
👤 المستخدم: {message.from_user.first_name}
🆔 معرفه: `{user_id}`
💰 الوسيلة: {method}
🎫 رقم العملية: `{receipt}`
━━━━━━━━━━━━━━━━━
إضغط على الزر أدناه لمعالجة الطلب:
"""
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ قبول", callback_data=f"approve_dep_{receipt}"),
               types.InlineKeyboardButton("❌ رفض", callback_data=f"reject_dep_{receipt}"))
    
    bot.send_photo(ADMIN_ID, file_id, caption=admin_msg, parse_mode="Markdown", reply_markup=markup)
# ==========================================
# 9. نظام سحب الأرباح (Withdraw System)
# ==========================================
@bot.message_handler(func=lambda message: message.text == "💸 سحب الأرباح")
def withdraw_money(message):
    user_id = message.from_user.id
    if not check_sub(user_id): return
    
    cursor.execute("SELECT balance, site_balance FROM users WHERE user_id=?", (user_id,))
    user_data = cursor.fetchone()
    
    if not user_data:
        bot.reply_to(message, "⚠️ خطأ في العثور على بياناتك.")
        return

    bot_balance = user_data[0]
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    btns = [
        types.InlineKeyboardButton("🇸🇾 سحب عبر سيريتل كاش / MTN", callback_data="wit_syria"),
        types.InlineKeyboardButton("🏦 سحب عبر الهرم / الفؤاد", callback_data="wit_haram"),
        types.InlineKeyboardButton("🌐 سحب عبر USDT / Binance", callback_data="wit_crypto")
    ]
    markup.add(*btns)
    
    withdraw_msg = f"""
**💸 نظام سحب الأرباح:**
━━━━━━━━━━━━━━━━━
💰 رصيدك الحالي: {bot_balance} $

⚠️ ملاحظات:
- الحد الأدنى للسحب: {get_setting('min_withdraw_syria')} ل.س
- عمولة السحب: {get_setting('withdraw_commission')}%
- يتم معالجة الطلبات خلال 24 ساعة.
━━━━━━━━━━━━━━━━━
اختر وسيلة السحب:
"""
    bot.send_message(user_id, withdraw_msg, parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('wit_'))
def handle_withdraw_methods(call):
    user_id = call.from_user.id
    method = call.data.split('_')[1]
    
    cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    balance = cursor.fetchone()[0]
    
    # تحويل الرصيد من دولار لـ ليرة سورية تقريبياً للمعاينة (إذا كان النظام يعتمد ذلك)
    # هنا نطلب من المستخدم إدخال المبلغ المراد سحبه بالدولار أولاً
    
    msg = bot.edit_message_text(f"💰 رصيدك الحالي: {balance}$\n\nأدخل المبلغ الذي تريد سحبه بالدولار ($):", 
                          user_id, call.message.message_id)
    bot.register_next_step_handler(msg, process_withdraw_amount, method)

def process_withdraw_amount(message, method):
    user_id = message.from_user.id
    try:
        amount = float(message.text)
    except:
        bot.send_message(user_id, "❌ خطأ! يرجى إدخال رقم صحيح.")
        return

    cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    current_balance = cursor.fetchone()[0]
    
    if amount > current_balance:
        bot.send_message(user_id, "❌ رصيدك غير كافٍ لإتمام العملية.")
        return
        
    if amount <= 0:
        bot.send_message(user_id, "❌ المبلغ غير صالح.")
        return

    # الانتقال لطلب معلومات المستلم
    msg = bot.send_message(user_id, "📝 أدخل تفاصيل المستلم (الاسم الثلاثي + رقم الهاتف / أو عنوان المحفظة):")
    bot.register_next_step_handler(msg, finalize_withdraw, method, amount)

def finalize_withdraw(message, method, amount):
    user_id = message.from_user.id
    details = message.text
    receipt = generate_receipt()
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # خصم الرصيد فوراً وتعليقه حتى القبول أو الرفض
    cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id=?", (amount, user_id))
    
    # تسجيل العملية
    cursor.execute("""INSERT INTO transactions 
        (user_id, type, amount, method, status, transaction_date, receipt_number, details) 
        VALUES (?, 'withdraw', ?, ?, 'pending', ?, ?, ?)""",
        (user_id, amount, method, created_at, receipt, details))
    conn.commit()
    
    bot.send_message(user_id, f"✅ تم تقديم طلب السحب بنجاح.\n🎫 رقم الطلب: `{receipt}`\nسيتم إشعارك عند المعالجة.", parse_mode="Markdown")
    
    # إشعار الإدارة
    admin_msg = f"""
🚨 **طلب سحب جديد!**
━━━━━━━━━━━━━━━━━
👤 المستخدم: {message.from_user.first_name}
🆔 معرفه: `{user_id}`
💰 المبلغ: {amount} $
💰 الوسيلة: {method}
📝 التفاصيل: {details}
🎫 رقم العملية: `{receipt}`
━━━━━━━━━━━━━━━━━
"""
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ تنفيذ", callback_data=f"approve_wit_{receipt}"),
               types.InlineKeyboardButton("❌ رفض وتمرير الرصيد", callback_data=f"reject_wit_{receipt}"))
    
    bot.send_message(ADMIN_ID, admin_msg, reply_markup=markup)
# ==========================================
# 10. نظام الإحالات (Referral System)
# ==========================================
@bot.message_handler(func=lambda message: message.text == "🤝 نظام الإحالة")
def referral_system(message):
    user_id = message.from_user.id
    cursor.execute("SELECT ref_code, referral_count, total_earnings FROM users WHERE user_id=?", (user_id,))
    data = cursor.fetchone()
    
    ref_link = f"https://t.me/{bot.get_me().username}?start={data[0]}"
    
    msg = f"""
🤝 **نظام الإحالة والكسب:**
━━━━━━━━━━━━━━━━━
🔗 رابط الإحالة الخاص بك:
`{ref_link}`

👥 عدد الإحالات: {data[1]}
💰 إجمالي أرباح الإحالة: {data[2]} $

🎁 ستحصل على عمولة {get_setting('referral_percentage')}% من كل عملية شحن يقوم بها الشخص الذي سجل من خلالك!
━━━━━━━━━━━━━━━━━
شارك الرابط الآن وابدأ بالكسب!
"""
    bot.send_message(user_id, msg, parse_mode="Markdown")

# ==========================================
# 11. نظام أكواد الهدايا (Gift Codes)
# ==========================================
@bot.message_handler(func=lambda message: message.text == "🎁 كود الهدية")
def gift_code_menu(message):
    user_id = message.from_user.id
    msg = bot.send_message(user_id, "🎫 يرجى إدخال كود الهدية الآن:")
    bot.register_next_step_handler(msg, process_gift_code)

def process_gift_code(message):
    user_id = message.from_user.id
    code = message.text.strip()
    
    if code == "🔙 عودة":
        bot.send_message(user_id, "تم الرجوع.", reply_markup=main_menu(user_id))
        return

    cursor.execute("SELECT * FROM gifts WHERE code=?", (code,))
    gift = cursor.fetchone()
    
    if not gift:
        bot.send_message(user_id, "❌ الكود غير صحيح أو منتهي الصلاحية.")
        return
    
    # تحقق إذا تم استخدامه من قبل هذا المستخدم
    cursor.execute("SELECT * FROM gift_usage WHERE user_id=? AND code=?", (user_id, code))
    if cursor.fetchone():
        bot.send_message(user_id, "⚠️ لقد قمت باستخدام هذا الكود مسبقاً.")
        return
        
    # تحقق من عدد المرات المتاحة
    if gift[3] >= gift[2]:
        bot.send_message(user_id, "❌ عذراً، نفدت كمية استخدام هذا الكود.")
        return
        
    # تنفيذ إضافة الرصيد
    value = gift[1]
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (value, user_id))
    cursor.execute("UPDATE gifts SET used_count = used_count + 1 WHERE code=?", (code,))
    cursor.execute("INSERT INTO gift_usage (user_id, code, used_at) VALUES (?, ?, ?)",
                  (user_id, code, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    
    bot.send_message(user_id, f"✅ مبروك! حصلت على {value}$ رصيد مجاني.")

# ==========================================
# 12. نظام الدعم الفني (Support Tickets)
# ==========================================
@bot.message_handler(func=lambda message: message.text == "☎️ الدعم الفني")
def support_menu(message):
    user_id = message.from_user.id
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📩 فتح تذكرة جديدة", callback_data="open_ticket"))
    markup.add(types.InlineKeyboardButton("📋 تذاكري السابقة", callback_data="my_tickets"))
    
    bot.send_message(user_id, "☎️ أهلاً بك في قسم الدعم الفني. كيف يمكننا مساعدتك؟", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "open_ticket")
def open_ticket_start(call):
    user_id = call.from_user.id
    msg = bot.edit_message_text("📝 يرجى كتابة مشكلتك بالتفصيل (يمكنك إرسال نص أو صورة مع نص):", user_id, call.message.message_id)
    bot.register_next_step_handler(msg, save_ticket)

def save_ticket(message):
    user_id = message.from_user.id
    text = message.text if message.text else message.caption
    file_id = message.photo[-1].file_id if message.photo else None
    
    if not text and not file_id:
        bot.send_message(user_id, "❌ لا يمكن إرسال تذكرة فارغة.")
        return

    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("INSERT INTO tickets (user_id, message, file_id, created_at) VALUES (?, ?, ?, ?)",
                  (user_id, text, file_id, created_at))
    ticket_id = cursor.lastrowid
    conn.commit()
    
    bot.send_message(user_id, f"✅ تم فتح التذكرة بنجاح برقم: #{ticket_id}\nسيرد عليك الدعم في أقرب وقت.")
    
    # إخطار الإدارة
    bot.send_message(ADMIN_ID, f"🔔 تذكرة دعم جديدة رقم #{ticket_id} من المستخدم {user_id}")
# ==========================================
# 13. معالجة لوحة تحكم الإدارة (Admin Handlers)
# ==========================================
@bot.message_handler(func=lambda message: message.text == "👨‍✈️ لوحة تحكم الإدارة")
def admin_main(message):
    user_id = message.from_user.id
    if not is_moderator(user_id):
        return
    
    bot.send_message(user_id, "⚙️ أهلاً بك في لوحة التحكم، اختر القسم المطلوب:", reply_markup=admin_panel())

@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_'))
def handle_admin_callbacks(call):
    user_id = call.from_user.id
    if not is_moderator(user_id):
        bot.answer_callback_query(call.id, "❌ لا تملك صلاحيات.")
        return

    action = call.data.split('_')[1]
    
    if action == "stats":
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        cursor.execute("SELECT SUM(balance) FROM users")
        total_balance = cursor.fetchone()[0] or 0
        
        stats_msg = f"""
📊 **إحصائيات البوت الحالية:**
━━━━━━━━━━━━━━━━━
👥 إجمالي المستخدمين: {total_users}
💰 إجمالي أرصدة المستخدمين: {total_balance} $
💳 عمليات اليوم: (جاري الفحص...)
━━━━━━━━━━━━━━━━━
"""
        bot.edit_message_text(stats_msg, user_id, call.message.message_id, reply_markup=admin_panel())

    elif action == "deposit":
        cursor.execute("SELECT * FROM transactions WHERE type='deposit' AND status='pending'")
        rows = cursor.fetchall()
        if not rows:
            bot.answer_callback_query(call.id, "✅ لا توجد طلبات شحن معلقة.")
            return
        
        for row in rows:
            msg = f"📩 طلب شحن من: {row[1]}\nالمبلغ المتوقع: {row[3]}\nالوسيلة: {row[6]}\nالتاريخ: {row[8]}"
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("✅ قبول", callback_data=f"approve_dep_{row[9]}"),
                       types.InlineKeyboardButton("❌ رفض", callback_data=f"reject_dep_{row[9]}"))
            bot.send_message(user_id, msg, reply_markup=markup)

# ==========================================
# 14. نظام قبول ورفض العمليات (Approve/Reject)
# ==========================================
@bot.callback_query_handler(func=lambda call: call.data.startswith(('approve_dep_', 'reject_dep_')))
def process_dep_decision(call):
    admin_id = call.from_user.id
    action = "approve" if "approve" in call.data else "reject"
    receipt = call.data.split('_')[-1]

    cursor.execute("SELECT user_id, amount, method, details FROM transactions WHERE receipt_number=?", (receipt,))
    trans = cursor.fetchone()
    if not trans:
        bot.answer_callback_query(call.id, "❌ لم يتم العثور على العملية.")
        return

    target_user_id = trans[0]

    if action == "approve":
        # طلب إدخال المبلغ النهائي الذي وصل فعلياً
        msg = bot.send_message(admin_id, f"👤 المستخدم: {target_user_id}\nأدخل المبلغ الذي تريد إضافته لحسابه ($):")
        bot.register_next_step_handler(msg, finalize_deposit_approval, target_user_id, receipt)
    else:
        # رفض العملية
        cursor.execute("UPDATE transactions SET status='rejected' WHERE receipt_number=?", (receipt,))
        conn.commit()
        bot.edit_message_caption("❌ تم رفض الطلب.", admin_id, call.message.message_id, reply_markup=None)
        bot.send_message(target_user_id, "❌ عذراً، تم رفض طلب الشحن الخاص بك. تأكد من صحة البيانات أو تواصل مع الدعم.")

def finalize_deposit_approval(message, target_user_id, receipt):
    try:
        amount = float(message.text)
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount, target_user_id))
        cursor.execute("UPDATE transactions SET status='completed', amount=? WHERE receipt_number=?", (amount, receipt))
        
        # نظام عمولة الإحالة (Referral Commission)
        cursor.execute("SELECT referred_by FROM users WHERE user_id=?", (target_user_id,))
        ref_by = cursor.fetchone()[0]
        if ref_by:
            percent = float(get_setting('referral_percentage')) / 100
            bonus = amount * percent
            cursor.execute("UPDATE users SET balance = balance + ?, total_earnings = total_earnings + ? WHERE user_id=?", 
                          (bonus, bonus, ref_by))
            bot.send_message(ref_by, f"🎊 مبروك! حصلت على عمولة إحالة بقيمة {bonus}$ من شحن صديقك.")

        conn.commit()
        bot.send_message(ADMIN_ID, f"✅ تم شحن {amount}$ للمستخدم {target_user_id}")
        bot.send_message(target_user_id, f"✅ تم قبول طلب الشحن! أضيف لحسابك {amount} $")
    except:
        bot.send_message(ADMIN_ID, "❌ خطأ في إدخال المبلغ. لم يتم تنفيذ العملية.")

# استكمال نظام السحب...
    elif action == "search":
        msg = bot.send_message(user_id, "🔍 أرسل (ID) المستخدم أو (اسم المستخدم) للبحث عنه:")
        bot.register_next_step_handler(msg, process_admin_search)

    elif action == "broadcast":
        msg = bot.send_message(user_id, "📢 أرسل الرسالة التي تريد إذاعتها لجميع المستخدمين (نص أو صورة مع نص):")
        bot.register_next_step_handler(msg, process_broadcast)

    elif action == "staff":
        if user_id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ عذراً، هذا القسم مخصص للأدمن الأساسي فقط.")
            return
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("➕ إضافة موظف جديد", callback_data="add_mod"))
        markup.add(types.InlineKeyboardButton("📋 قائمة الموظفين", callback_data="list_mods"))
        bot.edit_message_text("👥 إدارة طاقم العمل:", user_id, call.message.message_id, reply_markup=markup)

# ==========================================
# 15. وظائف البحث والإذاعة
# ==========================================
def process_admin_search(message):
    admin_id = message.from_user.id
    search_query = message.text
    
    cursor.execute("SELECT * FROM users WHERE user_id=? OR username=?", (search_query, search_query))
    user = cursor.fetchone()
    
    if not user:
        bot.send_message(admin_id, "❌ لم يتم العثور على هذا المستخدم.")
        return
        
    status = "✅ نشط" if user[5] == 'active' else "❌ محظور"
    msg = f"""
👤 **بيانات المستخدم:**
━━━━━━━━━━━━━━━━━
🆔 المعرف: `{user[0]}`
👤 الاسم: {user[10] if user[10] else user[8]}
🌐 يوزرنيم: @{user[9] if user[9] else "لا يوجد"}
📊 الحالة: {status}
💰 الرصيد: {user[3]} $
🤝 الإحالات: {user[13]}
━━━━━━━━━━━━━━━━━
"""
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💰 تعديل الرصيد", callback_data=f"edit_bal_{user[0]}"),
               types.InlineKeyboardButton("🚫 حظر/إلغاء", callback_data=f"ban_user_{user[0]}"))
    markup.add(types.InlineKeyboardButton("📝 تغيير البيانات", callback_data=f"edit_data_{user[0]}"))
    
    bot.send_message(admin_id, msg, parse_mode="Markdown", reply_markup=markup)

def process_broadcast(message):
    admin_id = message.from_user.id
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    
    count = 0
    bot.send_message(admin_id, f"⏳ بدأت عملية الإذاعة لـ {len(users)} مستخدم...")
    
    for user in users:
        try:
            if message.photo:
                bot.send_photo(user[0], message.photo[-1].file_id, caption=message.caption)
            else:
                bot.send_message(user[0], message.text)
            count += 1
            time.sleep(0.05) # حماية من حظر التلغرام (Anti-Flood)
        except:
            continue
            
    bot.send_message(admin_id, f"✅ تمت الإذاعة بنجاح لـ {count} مستخدم.")

# ==========================================
# 16. إدارة الموظفين (Moderator System)
# ==========================================
@bot.callback_query_handler(func=lambda call: call.data == "add_mod")
def add_mod_start(call):
    msg = bot.send_message(call.from_user.id, "👤 أرسل ID المستخدم المراد ترقيته لموظف:")
    bot.register_next_step_handler(msg, process_add_mod)

def process_add_mod(message):
    try:
        new_mod_id = int(message.text)
        permissions = {
            "can_reply": True,
            "can_change_codes": False,
            "can_view_transactions": True,
            "can_maintenance": False,
            "can_broadcast": False
        }
        
        cursor.execute("INSERT OR REPLACE INTO moderators (user_id, added_by, added_at, permissions) VALUES (?, ?, ?, ?)",
                      (new_mod_id, message.from_user.id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), json.dumps(permissions)))
        conn.commit()
        bot.send_message(message.from_user.id, f"✅ تم إضافة المستخدم {new_mod_id} كـ موظف بنجاح.")
        bot.send_message(new_mod_id, "🎊 تمت ترقيتك إلى موظف في البوت. يمكنك الآن الدخول للوحة التحكم.")
    except:
        bot.send_message(message.from_user.id, "❌ خطأ! تأكد من إرسال ID صحيح.")
# ==========================================
# 17. إدارة الإعدادات والردود المتقدمة
# ==========================================
@bot.callback_query_handler(func=lambda call: call.data == "admin_settings")
def admin_settings_list(call):
    user_id = call.from_user.id
    if not is_moderator(user_id): return
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    btns = [
        types.InlineKeyboardButton("📱 تعديل أرقام سيريتل كاش", callback_data="edit_set_syriatel"),
        types.InlineKeyboardButton("🏦 تعديل عنوان الهرم", callback_data="edit_set_sham"),
        types.InlineKeyboardButton("💰 تعديل الحد الأدنى للسحب", callback_data="edit_set_min_wit"),
        types.InlineKeyboardButton("📈 تعديل عمولة الإحالة", callback_data="edit_set_ref"),
        types.InlineKeyboardButton("📣 تعديل رسالة الترحيب", callback_data="edit_set_welcome")
    ]
    markup.add(*btns)
    bot.edit_message_text("⚙️ اختر الإعداد الذي تريد تعديله:", user_id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_set_'))
def process_setting_edit(call):
    user_id = call.from_user.id
    setting_key = call.data.replace('edit_set_', '')
    
    # خريطة المفاتيح لسهولة التعامل
    keys_map = {
        'syriatel': 'syriatel_numbers',
        'sham': 'sham_address',
        'min_wit': 'min_withdraw_syria',
        'ref': 'referral_percentage',
        'welcome': 'welcome_message'
    }
    
    real_key = keys_map.get(setting_key)
    msg = bot.send_message(user_id, f"📝 أرسل القيمة الجديدة لـ ({setting_key}):")
    bot.register_next_step_handler(msg, save_new_setting, real_key)

def save_new_setting(message, key):
    update_setting(key, message.text, message.from_user.id)
    bot.send_message(message.from_user.id, "✅ تم حفظ الإعدادات الجديدة بنجاح.")

# نظام الرد على التذاكر
@bot.callback_query_handler(func=lambda call: call.data == "admin_tickets")
def list_active_tickets(call):
    cursor.execute("SELECT ticket_id, user_id, message FROM tickets WHERE status='open' LIMIT 10")
    tickets = cursor.fetchall()
    if not tickets:
        bot.answer_callback_query(call.id, "✅ لا توجد تذاكر مفتوحة حالياً.")
        return
        
    for t in tickets:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("✍️ رد", callback_data=f"reply_tk_{t[0]}"),
                   types.InlineKeyboardButton("✅ إغلاق", callback_data=f"close_tk_{t[0]}"))
        bot.send_message(call.from_user.id, f"🎫 تذكرة #{t[0]}\n👤 من: {t[1]}\n📝 النص: {t[2]}", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('reply_tk_'))
def reply_ticket_start(call):
    ticket_id = call.data.split('_')[-1]
    msg = bot.send_message(call.from_user.id, f"✍️ اكتب ردك على التذكرة #{ticket_id}:")
    bot.register_next_step_handler(msg, send_ticket_reply, ticket_id)

def send_ticket_reply(message, ticket_id):
    cursor.execute("SELECT user_id FROM tickets WHERE ticket_id=?", (ticket_id,))
    user_id = cursor.fetchone()[0]
    
    reply_text = f"⚠️ **رد من الدعم الفني (تذكرة #{ticket_id}):**\n\n{message.text}"
    try:
        bot.send_message(user_id, reply_text, parse_mode="Markdown")
        bot.send_message(message.from_user.id, "✅ تم إرسال الرد للمستخدم.")
    except:
        bot.send_message(message.from_user.id, "❌ فشل إرسال الرد، ربما قام المستخدم بحظر البوت.")

# نظام حذف واسترجاع الحسابات (Ichancy Data)
@bot.callback_query_handler(func=lambda call: call.data == "admin_restore")
def restore_account_start(call):
    msg = bot.send_message(call.from_user.id, "🔄 أرسل ID المستخدم المراد استرجاع حسابه المحذوف:")
    bot.register_next_step_handler(msg, process_restore)

def process_restore(message):
    try:
        target_id = int(message.text)
        cursor.execute("SELECT acc_name, acc_password, site_balance, balance FROM deleted_accounts WHERE user_id=?", (target_id,))
        deleted = cursor.fetchone()
        
        if deleted:
            cursor.execute("""UPDATE users SET 
                acc_name=?, acc_password=?, site_balance=?, balance=?, deleted=0
                WHERE user_id=?""", (deleted[0], deleted[1], deleted[2], deleted[3], target_id))
            
            cursor.execute("DELETE FROM deleted_accounts WHERE user_id=?", (target_id,))
            conn.commit()
            
            bot.send_message(ADMIN_ID, f"✅ تم استرجاع حساب المستخدم {target_id}")
            bot.send_message(target_id, "🔄 تم استرجاع حسابك في Ichancy من قبل الإدارة.")
        else:
            bot.send_message(ADMIN_ID, "❌ لا يوجد حساب محذوف لهذا المستخدم")
    except ValueError:
        bot.send_message(ADMIN_ID, "❌ معرف المستخدم غير صحيح")
# ==========================================
# 18. دوال الحظر والتحكم النهائي بالمستخدمين
# ==========================================
@bot.callback_query_handler(func=lambda call: call.data.startswith('ban_user_'))
def ban_user_callback(call):
    admin_id = call.from_user.id
    if not is_moderator(admin_id): return
    
    target_id = int(call.data.split('_')[-1])
    
    cursor.execute("SELECT is_banned FROM users WHERE user_id=?", (target_id,))
    res = cursor.fetchone()
    
    if res:
        new_status = 1 if res[0] == 0 else 0
        cursor.execute("UPDATE users SET is_banned=? WHERE user_id=?", (new_status, target_id))
        conn.commit()
        
        status_text = "محظور 🚫" if new_status == 1 else "نشط ✅"
        bot.answer_callback_query(call.id, f"تم تغيير حالة المستخدم إلى: {status_text}")
        bot.send_message(target_id, f"⚠️ تم تحديث حالة حسابك من قبل الإدارة إلى: {status_text}")

# ==========================================
# 19. تشغيل البوت والحماية من التوقف (Anti-Crash)
# ==========================================
if __name__ == "__main__":
    # تشغيل سيرفر Flask في الخلفية لضمان عمل Render
    keep_alive()
    
    print("🚀 Matar Bot Final Version is starting...")
    print(f"👤 Admin ID: {ADMIN_ID}")
    print("✅ Anti-Lag System Active")
    print("✅ Database Connected and Fixed (Line 156)")
    
    # حلقة تشغيل لا نهائية لمنع البوت من التوقف عند حدوث أي خطأ بسيط
    while True:
        try:
            print("🔄 Bot is now Polling...")
            bot.polling(none_stop=True, interval=0, timeout=20)
        except Exception as e:
            print(f"⚠️ Polling Error: {e}")
            # الانتظار قليلاً قبل إعادة المحاولة لمنع استهلاك الموارد
            time.sleep(5)
            continue

