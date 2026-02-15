import telebot
from telebot import types
from flask import Flask
from threading import Thread
import os
import sqlite3
from datetime import datetime
import random
import string
import time
import hashlib

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
# 2. نظام قاعدة البيانات المطور
# ==========================================
def setup_database():
    conn = sqlite3.connect("matar_pro_v301_final.db", check_same_thread=False)
    cursor = conn.cursor()
    
    # جدول المستخدمين الشامل (محدث)
    cursor.execute("""CREATE TABLE IF NOT EXISTS users(
        user_id INTEGER PRIMARY KEY, 
        acc_name TEXT, 
        acc_password TEXT,
        balance REAL DEFAULT 0, 
        site_balance REAL DEFAULT 0, 
        status TEXT DEFAULT 'active', 
        created_at TEXT,
        deleted INTEGER DEFAULT 0)""")

    # جدول الأكواد والهدايا
    cursor.execute("""CREATE TABLE IF NOT EXISTS gifts(
        code TEXT PRIMARY KEY, 
        value REAL, 
        limit_count INTEGER, 
        used_count INTEGER DEFAULT 0,
        type TEXT DEFAULT 'individual',
        created_by INTEGER,
        created_at TEXT)""")

    # سجل استخدام الهدايا
    cursor.execute("""CREATE TABLE IF NOT EXISTS gift_usage(
        user_id INTEGER, 
        code TEXT,
        used_at TEXT,
        UNIQUE(user_id, code))""")
    
    # جدول المعاملات
    cursor.execute("""CREATE TABLE IF NOT EXISTS transactions(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        type TEXT,
        amount REAL,
        method TEXT,
        status TEXT,
        transaction_date TEXT,
        admin_id INTEGER,
        details TEXT)""")
    
    # جدول سجل الحسابات المحذوفة
    cursor.execute("""CREATE TABLE IF NOT EXISTS deleted_accounts(
        user_id INTEGER PRIMARY KEY,
        acc_name TEXT,
        acc_password TEXT,
        balance REAL,
        deleted_at TEXT,
        restored_by INTEGER)""")
    
    # جدول الإعدادات العامة
    cursor.execute("CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT)")
    
    # إدخال الإعدادات الافتراضية
    cursor.execute("INSERT OR IGNORE INTO settings VALUES ('syriatel_num', '74205110')")
    cursor.execute("INSERT OR IGNORE INTO settings VALUES ('sham_num', 'SHAM-12345')")
    cursor.execute("INSERT OR IGNORE INTO settings VALUES ('usdt_status', 'متوقف')")
    cursor.execute("INSERT OR IGNORE INTO settings VALUES ('binance_status', 'متوقف')")
    cursor.execute("INSERT OR IGNORE INTO settings VALUES ('min_charge', '100')")
    cursor.execute("INSERT OR IGNORE INTO settings VALUES ('welcome_message', 'اهلا وسهلا بك في بوت Matar البوت الرسمي لموقع ichancy')")
    
    conn.commit()
    return conn, cursor

conn, cursor = setup_database()

# ==========================================
# 3. الوظائف المساعدة
# ==========================================
def check_subscription(uid):
    try:
        member = bot.get_chat_member(CHANNEL_ID, uid)
        return member.status in ['member', 'administrator', 'creator']
    except:
        return False

def get_db_setting(key_name):
    cursor.execute("SELECT value FROM settings WHERE key=?", (key_name,))
    result = cursor.fetchone()
    return result[0] if result else "غير متوفر"

def update_db_setting(key_name, value):
    cursor.execute("UPDATE settings SET value=? WHERE key=?", (value, key_name))
    conn.commit()

def reset_user_steps(uid):
    bot.clear_step_handler_by_chat_id(chat_id=uid)

def generate_gift_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

def log_transaction(user_id, type, amount, method, status, admin_id=None, details=""):
    cursor.execute("""INSERT INTO transactions 
        (user_id, type, amount, method, status, transaction_date, admin_id, details)
        VALUES (?,?,?,?,?,?,?,?)""",
        (user_id, type, amount, method, status, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), admin_id, details))
    conn.commit()# ==========================================
# 4. بناء القوائم (Keyboards)
# ==========================================
def get_main_keyboard(uid):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(types.KeyboardButton('⚽ Ichancy ⚽'))
    markup.add(types.KeyboardButton('🔽 الشحن في البوت'), types.KeyboardButton('🔼 السحب من البوت'))
    markup.add(types.KeyboardButton('🎁 اهداء صديق'), types.KeyboardButton('🎫 كود هدية'))
    markup.add(types.KeyboardButton('💵 الرصيد'), types.KeyboardButton('💬 التواصل مع الدعم'))
    if uid == ADMIN_ID:
        markup.add(types.KeyboardButton('🔐 إدارة البوت'))
    return markup

def get_ichancy_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(types.KeyboardButton('💰 معلومات الحساب 💰'))
    markup.add(types.KeyboardButton('➕ شحن رصيد في الحساب'), types.KeyboardButton('➖ سحب رصيد من الحساب'))
    markup.add(types.KeyboardButton('🗑 حذف الحساب'))
    markup.add(types.KeyboardButton('🔙 العودة للقائمة الرئيسية'))
    return markup

def get_charge_methods_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("سيرياتل كاش 📱", callback_data="pay_syria"),
        types.InlineKeyboardButton("شام كاش 💳", callback_data="pay_sham"),
        types.InlineKeyboardButton("USDT 🔷", callback_data="pay_usdt"),
        types.InlineKeyboardButton("بينانس 💱", callback_data="pay_binance")
    )
    return markup

def get_admin_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add('🎫 إنشاء كود هدية', '👥 إدارة المستخدمين')
    markup.add('📊 سجل المعاملات', '⚙️ إعدادات الشحن')
    markup.add('📨 رسالة جماعية', '📧 رسالة فردية')
    markup.add('🔄 استرجاع حساب', '🔙 العودة للقائمة الرئيسية')
    return markup

def get_gift_type_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("فردي 👤", callback_data="gift_individual"),
        types.InlineKeyboardButton("جماعي 👥", callback_data="gift_group")
    )
    return markup

def get_user_management_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add('🔨 حظر مستخدم', '✅ فك حظر مستخدم')
    markup.add('💰 شحن رصيد مستخدم', '💸 سحب رصيد مستخدم')
    markup.add('📝 إنشاء حساب لمستخدم', '📋 معلومات مستخدم')
    markup.add('🔙 العودة للإدارة')
    return markup

# ==========================================
# 5. معالجة الأوامر الرئيسية
# ==========================================
@bot.message_handler(commands=['start'])
def handle_start(message):
    uid = message.from_user.id
    reset_user_steps(uid)
    
    # رسالة الترحيب الجديدة
    welcome_text = (
        f"🎯 أهلاً وسهلاً بك في بوت Matar 🌧️\n\n"
        f"البوت الرسمي لموقع Ichancy ✅\n"
        f"هذا البوت مخصص لإنشاء حساب على موقع Ichancy وإدارته في عمليات الشحن والسحب\n\n"
        f"⚠️ شرط أساسي لاستخدام البوت:\n"
        f"الرجاء الاشتراك في قناتنا على تيلغرام لتتمكن من استخدام البوت"
    )
    
    if not check_subscription(uid):
        btn = types.InlineKeyboardMarkup().add(
            types.InlineKeyboardButton("📢 اشترك في القناة", url=CHANNEL_URL),
            types.InlineKeyboardButton("✅ تم الاشتراك", callback_data="check_sub")
        )
        bot.send_message(message.chat.id, welcome_text, reply_markup=btn)
        return
    
    bot.send_message(message.chat.id, "✅ تم التحقق من اشتراكك! مرحباً بك في البوت 🎉", 
                    reply_markup=get_main_keyboard(uid))

@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def check_sub_callback(call):
    uid = call.from_user.id
    if check_subscription(uid):
        bot.edit_message_text(
            "✅ اشتراكك مؤكد! مرحباً بك في البوت",
            call.message.chat.id,
            call.message.message_id
        )
        bot.send_message(uid, "اختر من القائمة الرئيسية:", reply_markup=get_main_keyboard(uid))
    else:
        bot.answer_callback_query(call.id, "❌ لم تشترك بعد! اشترك ثم حاول مرة أخرى", show_alert=True)

# ==========================================
# 6. معالجة الرسائل (الراوتر الرئيسي)
# ==========================================
@bot.message_handler(func=lambda m: True)
def main_router(m):
    uid = m.from_user.id
    text = m.text
    
    # فحص الحظر
    cursor.execute("SELECT status FROM users WHERE user_id=?", (uid,))
    user_status = cursor.fetchone()
    if user_status and user_status[0] == 'banned':
        bot.send_message(uid, "❌ نعتذر، حسابك محظور من استخدام النظام.")
        return

    # التحقق من الاشتراك
    if not check_subscription(uid):
        btn = types.InlineKeyboardMarkup().add(
            types.InlineKeyboardButton("📢 اشترك في القناة", url=CHANNEL_URL)
        )
        bot.send_message(uid, "⚠️ يجب الاشتراك في القناة أولاً", reply_markup=btn)
        return

    # تصفير الخطوات عند الأزرار الرئيسية
    if text in ['⚽ Ichancy ⚽', '🔙 العودة للقائمة الرئيسية', '🔐 إدارة البوت']:
        reset_user_steps(uid)

    # ===== قسم Ichancy =====
    if text == '⚽ Ichancy ⚽':
        cursor.execute("SELECT acc_name, acc_password, site_balance, deleted FROM users WHERE user_id=?", (uid,))
        user_data = cursor.fetchone()
        
        if not user_data or not user_data[0] or user_data[3] == 1:
            # إنشاء حساب جديد
            msg = bot.send_message(
                m.chat.id, 
                "📝 لإنشاء حساب جديد في Ichancy:\n"
                "الرجاء إدخال اسم المستخدم بالحروف الإنجليزية فقط:"
            )
            bot.register_next_step_handler(msg, process_registration_name)
        else:
            # عرض معلومات الحساب
            acc_info = (
                f"🌐 اسم المستخدم: {user_data[0]}\n"
                f"🔑 كلمة المرور: {user_data[1]}\n"
                f"💰 الرصيد على الموقع: {user_data[2]} NSP\n"
                f"📊 الحالة: نشط"
            )
            bot.send_message(m.chat.id, acc_info, reply_markup=get_ichancy_keyboard())

    # ===== أزرار Ichancy =====
    elif text == '💰 معلومات الحساب 💰':
        cursor.execute("SELECT acc_name, acc_password, site_balance, balance FROM users WHERE user_id=?", (uid,))
        u = cursor.fetchone()
        if u and u[0]:
            card = (
                f"🌐 اسم الحساب: {u[0]}\n"
                f"🔑 كلمة المرور: {u[1]}\n"
                f"💰 رصيد الموقع: {u[2]} NSP\n"
                f"🤖 رصيد البوت: {u[3]} NSP\n"
                f"🆔 معرفك: {uid}"
            )
            bot.send_message(m.chat.id, card, reply_markup=get_ichancy_keyboard())
        else:
            bot.send_message(m.chat.id, "❌ لا يوجد حساب مسجل", reply_markup=get_main_keyboard(uid))

    elif text == '➕ شحن رصيد في الحساب':
        bot.send_message(m.chat.id, "⚠️ هذه الخدمة غير مفعلة حالياً", reply_markup=get_ichancy_keyboard())

    elif text == '➖ سحب رصيد من الحساب':
        bot.send_message(m.chat.id, "⚠️ هذه الخدمة غير مفعلة حالياً", reply_markup=get_ichancy_keyboard())

    elif text == '🗑 حذف الحساب':
        msg = bot.send_message(
            m.chat.id,
            "⚠️ تحذير! لن تستطيع استرجاع حسابك بعد الحذف\n"
            "للتأكيد، اكتب كلمة (حذف) وأرسلها:"
        )
        bot.register_next_step_handler(msg, process_delete_account)

    # ===== الشحن في البوت =====
    elif text == '🔽 الشحن في البوت':
        bot.send_message(m.chat.id, "💰 اختر وسيلة الشحن:", reply_markup=get_charge_methods_keyboard())

    # ===== السحب من البوت =====
    elif text == '🔼 السحب من البوت':
        bot.send_message(m.chat.id, "⚠️ خدمة السحب غير متاحة حالياً")

    # ===== العودة للقائمة الرئيسية =====
    elif text == '🔙 العودة للقائمة الرئيسية':
        bot.send_message(uid, "القائمة الرئيسية:", reply_markup=get_main_keyboard(uid))

    # ===== كود هدية =====
    elif text == '🎫 كود هدية':
        msg = bot.send_message(uid, "🎁 أرسل الكود الذي تريد استخدامه:")
        bot.register_next_step_handler(msg, redeem_gift_code)

    # ===== الرصيد =====
    elif text == '💵 الرصيد':
        cursor.execute("SELECT balance FROM users WHERE user_id=?", (uid,))
        bal = cursor.fetchone()
        current_bal = bal[0] if bal else 0
        bot.send_message(uid, f"💰 رصيدك الحالي في البوت: {current_bal} ل.س")

    # ===== تواصل مع الدعم =====
    elif text == '💬 التواصل مع الدعم':
        bot.send_message(uid, "📞 للتواصل مع الدعم: @Matar_Support")

    # ===== إهداء صديق =====
    elif text == '🎁 اهداء صديق':
        bot.send_message(uid, "⚠️ هذه الخدمة غير متاحة حالياً")

    # ===== لوحة الإدارة =====
    elif text == '🔐 إدارة البوت' and uid == ADMIN_ID:
        bot.send_message(uid, "🔓 لوحة التحكم الخاصة بالمشرف:", reply_markup=get_admin_keyboard())
        # ==========================================
# 7. عمليات إنشاء الحساب
# ==========================================
def process_registration_name(message):
    uid = message.from_user.id
    if message.text in ['🔙 العودة للقائمة الرئيسية', '/start', '⚽ Ichancy ⚽']:
        handle_start(message)
        return
    
    # إضافة Matar- تلقائياً
    full_name = f"Matar-{message.text}"
    
    # تخزين الاسم مؤقتاً (هنستخدم context مؤقت)
    bot.register_next_step_handler_by_chat_id(
        uid, 
        process_registration_password, 
        full_name
    )
    msg = bot.send_message(uid, "🔑 الآن أدخل كلمة المرور (حروف إنجليزية وأرقام فقط):")
    bot.register_next_step_handler(msg, process_registration_password, full_name)

def process_registration_password(message, full_name):
    uid = message.from_user.id
    if message.text in ['🔙 العودة للقائمة الرئيسية', '/start', '⚽ Ichancy ⚽']:
        handle_start(message)
        return
    
    password = message.text
    created_at = datetime.now().strftime("%d-%m-%Y %H:%M")
    
    # حفظ في قاعدة البيانات
    cursor.execute("""INSERT OR REPLACE INTO users 
        (user_id, acc_name, acc_password, created_at, site_balance, balance, deleted) 
        VALUES (?,?,?,?,0,0,0)""",
        (uid, full_name, password, created_at))
    conn.commit()
    
    bot.send_message(
        uid, 
        f"✅ تم إنشاء حسابك بنجاح!\n"
        f"👤 اسم المستخدم: {full_name}\n"
        f"🔑 كلمة المرور: {password}\n\n"
        f"🎉 أهلاً وسهلاً بك في بوت Matar",
        reply_markup=get_main_keyboard(uid)
    )
    
    # تسجيل العملية
    log_transaction(uid, "create_account", 0, "system", "success", details=f"Account: {full_name}")

# ==========================================
# 8. عملية حذف الحساب
# ==========================================
def process_delete_account(message):
    uid = message.from_user.id
    if message.text == 'حذف':
        # نقل البيانات إلى جدول المحذوفات
        cursor.execute("SELECT acc_name, acc_password, site_balance FROM users WHERE user_id=?", (uid,))
        user_data = cursor.fetchone()
        
        if user_data and user_data[0]:
            deleted_at = datetime.now().strftime("%d-%m-%Y %H:%M")
            cursor.execute("""INSERT OR REPLACE INTO deleted_accounts 
                (user_id, acc_name, acc_password, balance, deleted_at) 
                VALUES (?,?,?,?,?)""",
                (uid, user_data[0], user_data[1], user_data[2], deleted_at))
            
            # تحديث حالة المستخدم
            cursor.execute("UPDATE users SET acc_name=NULL, acc_password=NULL, site_balance=0, deleted=1 WHERE user_id=?", (uid,))
            conn.commit()
            
            bot.send_message(uid, "✅ تم حذف حسابك بنجاح", reply_markup=get_main_keyboard(uid))
            log_transaction(uid, "delete_account", 0, "system", "success")
        else:
            bot.send_message(uid, "❌ لا يوجد حساب لحذفه", reply_markup=get_main_keyboard(uid))
    else:
        bot.send_message(uid, "❌ لم تؤكد الحذف بشكل صحيح", reply_markup=get_ichancy_keyboard())

# ==========================================
# 9. معالجة أكواد الهدايا
# ==========================================
def redeem_gift_code(message):
    uid = message.from_user.id
    if message.text in ['🔙 العودة للقائمة الرئيسية', '/start']:
        handle_start(message)
        return
    
    code = message.text.upper()
    
    # التحقق من الكود
    cursor.execute("""SELECT value, limit_count, used_count, type FROM gifts WHERE code=?""", (code,))
    gift = cursor.fetchone()
    
    if not gift:
        bot.send_message(uid, "❌ الكود غير صحيح")
        return
    
    # التحقق من الاستخدام السابق
    cursor.execute("SELECT * FROM gift_usage WHERE user_id=? AND code=?", (uid, code))
    if cursor.fetchone():
        bot.send_message(uid, "❌ لقد استخدمت هذا الكود من قبل")
        return
    
    # التحقق من العدد المسموح
    if gift[2] >= gift[1]:
        bot.send_message(uid, "❌ هذا الكود انتهت صلاحيته")
        return
    
    # إضافة الرصيد
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (gift[0], uid))
    cursor.execute("UPDATE gifts SET used_count = used_count + 1 WHERE code=?", (code,))
    cursor.execute("""INSERT INTO gift_usage (user_id, code, used_at) 
        VALUES (?,?,?)""", (uid, code, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    
    bot.send_message(uid, f"🎉 تم شحن {gift[0]} ل.س إلى رصيدك في البوت!")
    log_transaction(uid, "gift_redeem", gift[0], "gift", "success", details=f"Code: {code}")

# ==========================================
# 10. معالجة طرق الدفع
# ==========================================
@bot.callback_query_handler(func=lambda call: call.data.startswith('pay_'))
def handle_payment_methods(call):
    uid = call.from_user.id
    method = call.data.replace('pay_', '')
    
    if method == 'syria':
        num = get_db_setting('syriatel_num')
        min_amount = get_db_setting('min_charge')
        msg = bot.send_message(
            call.message.chat.id,
            f"💳 سيرياتل كاش\n"
            f"📱 الرقم: `{num}`\n"
            f"💰 أقل مبلغ: {min_amount} ل.س\n\n"
            f"⚠️ التحويل اليدوي حصراً\n"
            f"📝 أرسل رقم العملية (12 خانة):",
            parse_mode="Markdown"
        )
        bot.register_next_step_handler(msg, process_manual_payment, "syriatel")
    
    elif method == 'sham':
        num = get_db_setting('sham_num')
        min_amount = get_db_setting('min_charge')
        bot.send_message(
            call.message.chat.id,
            f"💳 شام كاش\n"
            f"📱 العنوان: {num}\n"
            f"💰 أقل مبلغ: {min_amount} ل.س\n\n"
            f"⚠️ هذه الخدمة قيد التفعيل"
        )
    
    elif method in ['usdt', 'binance']:
        status = get_db_setting(f'{method}_status')
        bot.send_message(
            call.message.chat.id,
            f"⛔ الشحن بـ {method.upper()} {status} حالياً"
        )

def process_manual_payment(message, method):
    uid = message.from_user.id
    if message.text in ['🔙 العودة للقائمة الرئيسية', '/start']:
        handle_start(message)
        return
    
    transaction_id = message.text
    msg = bot.send_message(uid, "💰 أرسل المبلغ الذي قمت بتحويله:")
    bot.register_next_step_handler(msg, finalize_manual_payment, method, transaction_id)

def finalize_manual_payment(message, method, transaction_id):
    uid = message.from_user.id
    if message.text in ['🔙 العودة للقائمة الرئيسية', '/start']:
        handle_start(message)
        return
    
    try:
        amount = float(message.text)
        # إرسال إشعار للمشرف
        admin_notification = (
            f"💰 طلب شحن جديد\n"
            f"👤 المستخدم: {uid}\n"
            f"💵 المبلغ: {amount} ل.س\n"
            f"📱 الطريقة: {method}\n"
            f"🔢 رقم العملية: {transaction_id}"
        )
        bot.send_message(ADMIN_ID, admin_notification)
        
        bot.send_message(uid, "✅ تم استلام طلبك، سيتم مراجعته وتفعيل الرصيد خلال دقائق")
        log_transaction(uid, "charge_request", amount, method, "pending", details=transaction_id)
        
    except ValueError:
        bot.send_message(uid, "❌ المبلغ غير صحيح، أعد المحاولة من البداية")

# ==========================================
# 11. أوامر الإدارة
# ==========================================
@bot.message_handler(func=lambda m: m.text == '🎫 إنشاء كود هدية' and m.from_user.id == ADMIN_ID)
def admin_create_gift_menu(m):
    bot.send_message(m.chat.id, "اختر نوع الكود:", reply_markup=get_gift_type_keyboard())

@bot.callback_query_handler(func=lambda call: call.data.startswith('gift_') and call.from_user.id == ADMIN_ID)
def admin_create_gift(call):
    gift_type = call.data.replace('gift_', '')
    
    if gift_type == 'individual':
        msg = bot.send_message(call.message.chat.id, "💰 أدخل قيمة الكود (بالليرة السورية):")
        bot.register_next_step_handler(msg, process_individual_gift)
    else:  # group
        msg = bot.send_message(call.message.chat.id, "👥 كم عدد الأشخاص الذين سيستخدمون هذا الكود؟")
        bot.register_next_step_handler(msg, process_group_gift_count)

def process_individual_gift(message):
    try:
        value = float(message.text)
        code = generate_gift_code()
        
        cursor.execute("""INSERT INTO gifts (code, value, limit_count, used_count, type, created_by, created_at)
            VALUES (?,?,?,?,?,?,?)""",
            (code, value, 1, 0, 'individual', ADMIN_ID, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        
        bot.send_message(
            ADMIN_ID,
            f"✅ تم إنشاء الكود:\n"
            f"🎫 `{code}`\n"
            f"💰 القيمة: {value} ل.س\n"
            f"👤 نوع: فردي",
            parse_mode="Markdown"
        )
    except ValueError:
        bot.send_message(ADMIN_ID, "❌ قيمة غير صحيحة")

def process_group_gift_count(message):
    try:
        count = int(message.text)
        msg = bot.send_message(ADMIN_ID, f"💰 أدخل قيمة الكود لكل شخص (بالليرة):")
        bot.register_next_step_handler(msg, process_group_gift_value, count)
    except ValueError:
        bot.send_message(ADMIN_ID, "❌ عدد غير صحيح")

def process_group_gift_value(message, count):
    try:
        value = float(message.text)
        code = generate_gift_code()
        
        cursor.execute("""INSERT INTO gifts (code, value, limit_count, used_count, type, created_by, created_at)
            VALUES (?,?,?,?,?,?,?)""",
            (code, value, count, 0, 'group', ADMIN_ID, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        
        bot.send_message(
            ADMIN_ID,
            f"✅ تم إنشاء الكود الجماعي:\n"
            f"🎫 `{code}`\n"
            f"💰 القيمة للشخص: {value} ل.س\n"
            f"👥 عدد المستخدمين: {count}\n"
            f"📊 إجمالي القيمة: {value * count} ل.س",
            parse_mode="Markdown"
        )
    except ValueError:
        bot.send_message(ADMIN_ID, "❌ قيمة غير صحيحة")

# ==========================================
# 12. تشغيل البوت
# ==========================================
if __name__ == "__main__":
    keep_alive()
    print("🚀 Matar Bot is starting...")
    print(f"👤 Admin ID: {ADMIN_ID}")
    print("✅ Anti-Lag System Active")
    
    while True:
        try:
            bot.polling(none_stop=True, skip_pending=True, timeout=30)
        except Exception as e:
            print(f"⚠️ Polling error: {e}")
            time.sleep(5)
            continue
