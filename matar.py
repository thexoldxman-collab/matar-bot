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
# 2. نظام قاعدة البيانات المتكامل
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
        username TEXT)""")

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
    
    # جدول المعاملات الكامل
    cursor.execute("""CREATE TABLE IF NOT EXISTS transactions(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        type TEXT,
        amount REAL,
        commission REAL DEFAULT 0,
        net_amount REAL DEFAULT 0,
        method TEXT,
        status TEXT,
        transaction_date TEXT,
        admin_id INTEGER,
        details TEXT,
        receipt_number TEXT UNIQUE)""")
    
    # جدول العمليات المالية المكررة (لمنع النصب)
    cursor.execute("""CREATE TABLE IF NOT EXISTS processed_transactions(
        receipt_number TEXT PRIMARY KEY,
        user_id INTEGER,
        amount REAL,
        processed_at TEXT)""")
    
    # جدول سجل الحسابات المحذوفة
    cursor.execute("""CREATE TABLE IF NOT EXISTS deleted_accounts(
        user_id INTEGER PRIMARY KEY,
        acc_name TEXT,
        acc_password TEXT,
        balance REAL,
        site_balance REAL,
        deleted_at TEXT,
        restored_by INTEGER)""")
    
    # جدول رصيد الكاشيرة (المشرف)
    cursor.execute("""CREATE TABLE IF NOT EXISTS cashier_balance(
        admin_id INTEGER PRIMARY KEY,
        balance REAL DEFAULT 0)""")
    
    # جدول التذاكر (تواصل مع الدعم)
    cursor.execute("""CREATE TABLE IF NOT EXISTS tickets(
        ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        message TEXT,
        file_id TEXT,
        status TEXT DEFAULT 'open',
        created_at TEXT,
        admin_reply TEXT,
        replied_at TEXT)""")
    
    # جدول الإعدادات العامة
    cursor.execute("""CREATE TABLE IF NOT EXISTS settings(
        key TEXT PRIMARY KEY, 
        value TEXT,
        updated_at TEXT,
        updated_by INTEGER)""")
    
    # إدخال الإعدادات الافتراضية
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
        ('welcome_message', 'اهلا وسهلا بك في بوت Matar البوت الرسمي لموقع ichancy')
    ]
    
    for key, value in default_settings:
        cursor.execute("INSERT OR IGNORE INTO settings(key, value) VALUES (?,?)", (key, value))
    
    # إدخال رصيد الكاشيرة الافتراضي
    cursor.execute("INSERT OR IGNORE INTO cashier_balance(admin_id, balance) VALUES (?,0)", (ADMIN_ID,))
    
    conn.commit()
    return conn, cursor

conn, cursor = setup_database()

# ==========================================
# 3. الوظائف المساعدة الأساسية
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
    return result[0] if result else None

def update_db_setting(key_name, value, admin_id=ADMIN_ID):
    cursor.execute("""UPDATE settings SET value=?, updated_at=?, updated_by=? 
                      WHERE key=?""", (value, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), admin_id, key_name))
    conn.commit()

def reset_user_steps(uid):
    """تصفير الخطوات لضمان عدم التعليق"""
    bot.clear_step_handler_by_chat_id(chat_id=uid)

def generate_receipt_number(prefix="TXN"):
    """توليد رقم عملية فريد"""
    timestamp = datetime.now().strftime("%y%m%d%H%M%S")
    random_part = ''.join(random.choices(string.digits, k=4))
    return f"{prefix}{timestamp}{random_part}"

def generate_gift_code():
    """توليد كود هدية فريد"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))

def log_transaction(user_id, type, amount, method, status, commission=0, net_amount=0, admin_id=None, details=""):
    """تسجيل معاملة في السجلات"""
    receipt = generate_receipt_number()
    cursor.execute("""INSERT INTO transactions 
        (user_id, type, amount, commission, net_amount, method, status, transaction_date, admin_id, details, receipt_number)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (user_id, type, amount, commission, net_amount, method, status, 
         datetime.now().strftime("%Y-%m-%d %H:%M:%S"), admin_id, details, receipt))
    conn.commit()
    return receipt

def is_transaction_processed(receipt_number):
    """التحقق مما إذا كانت العملية مستخدمة مسبقاً"""
    cursor.execute("SELECT * FROM processed_transactions WHERE receipt_number=?", (receipt_number,))
    return cursor.fetchone() is not None

def mark_transaction_processed(receipt_number, user_id, amount):
    """تسجيل عملية كمعالجة مسبقاً"""
    cursor.execute("""INSERT INTO processed_transactions (receipt_number, user_id, amount, processed_at)
                      VALUES (?,?,?,?)""",
                   (receipt_number, user_id, amount, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()

def update_user_balance(user_id, amount, add=True):
    """تحديث رصيد المستخدم"""
    cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    result = cursor.fetchone()
    if result:
        new_balance = result[0] + amount if add else result[0] - amount
        cursor.execute("UPDATE users SET balance=? WHERE user_id=?", (new_balance, user_id))
        conn.commit()
        return new_balance
    return None

def update_cashier_balance(amount, add=True, admin_id=ADMIN_ID):
    """تحديث رصيد الكاشيرة"""
    cursor.execute("SELECT balance FROM cashier_balance WHERE admin_id=?", (admin_id,))
    result = cursor.fetchone()
    if result:
        new_balance = result[0] + amount if add else result[0] - amount
        cursor.execute("UPDATE cashier_balance SET balance=? WHERE admin_id=?", (new_balance, admin_id))
        conn.commit()
        return new_balance
    return None

def check_bot_status():
    """التحقق من حالة البوت (صيانة أم لا)"""
    status = get_db_setting('bot_status')
    return status == 'active'

def send_to_all_users(message_text, exclude_admin=False):
    """إرسال رسالة لجميع المستخدمين"""
    cursor.execute("SELECT user_id FROM users WHERE deleted=0")
    sent_count = 0
    for user in cursor.fetchall():
        if exclude_admin and user[0] == ADMIN_ID:
            continue
        try:
            bot.send_message(user[0], message_text)
            sent_count += 1
        except:
            continue
    return sent_count

# ==========================================
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

def get_ichancy_main_keyboard():
    """لوحة Ichancy الرئيسية (قبل إنشاء حساب)"""
    markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    markup.add(types.KeyboardButton('📝 إنشاء حساب جديد'))
    markup.add(types.KeyboardButton('🔙 العودة للقائمة الرئيسية'))
    return markup

def get_ichancy_account_keyboard(acc_name, site_balance, user_id):
    """لوحة Ichancy بعد إنشاء الحساب"""
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    
    # شريط المعلومات (نص فقط، ليس أزرار)
    info_text = f"👤 {acc_name} | 💰 {site_balance} NSP | 🆔 {user_id}"
    
    # الأزرار
    markup.add(types.KeyboardButton('➕ تعبئة في الحساب'), types.KeyboardButton('➖ سحب من الحساب'))
    markup.add(types.KeyboardButton('🗑 حذف الحساب'))
    markup.add(types.KeyboardButton('🔙 العودة للقائمة الرئيسية'))
    
    return markup, info_text

def get_charge_methods_keyboard():
    """طرق الشحن في البوت"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("سيرياتل كاش 📱", callback_data="charge_syria"),
        types.InlineKeyboardButton("شام كاش 💳", callback_data="charge_sham"),
        types.InlineKeyboardButton("USDT 🔷", callback_data="charge_usdt"),
        types.InlineKeyboardButton("بينانس 💱", callback_data="charge_binance")
    )
    return markup

def get_withdraw_methods_keyboard():
    """طرق السحب من البوت"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("سيرياتل كاش 📱", callback_data="withdraw_syria"),
        types.InlineKeyboardButton("شام كاش 💳", callback_data="withdraw_sham")
    )
    return markup

def get_withdraw_currency_keyboard():
    """اختيار عملة السحب (شام كاش)"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🇸🇾 ليرة سورية", callback_data="withdraw_sham_lyr"),
        types.InlineKeyboardButton("💵 دولار", callback_data="withdraw_sham_usd")
    )
    return markup

def get_confirmation_keyboard():
    """أزرار التأكيد"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✅ موافق", callback_data="confirm_yes"),
        types.InlineKeyboardButton("❌ إلغاء", callback_data="confirm_no")
    )
    return markup

def get_admin_main_keyboard():
    """لوحة الإدارة الرئيسية"""
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add('🎫 إنشاء كود هدية', '👥 إدارة المستخدمين')
    markup.add('💰 تغيير أكواد الدفع', '📊 سجل المعاملات')
    markup.add('📨 رسالة جماعية', '📧 رسالة فردية')
    markup.add('🔄 استرجاع حساب', '🔧 حالة البوت')
    markup.add('📋 قاعدة البيانات', '💬 تذاكر الدعم')
    markup.add('🔙 العودة للقائمة الرئيسية')
    return markup

def get_gift_type_keyboard():
    """نوع كود الهدية"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("فردي 👤", callback_data="gift_individual"),
        types.InlineKeyboardButton("جماعي 👥", callback_data="gift_group")
    )
    return markup

def get_user_management_keyboard():
    """إدارة المستخدمين"""
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add('🔨 حظر مستخدم', '✅ فك حظر مستخدم')
    markup.add('💰 شحن رصيد لمستخدم', '💸 سحب رصيد من مستخدم')
    markup.add('📝 إنشاء حساب لمستخدم', '📋 معلومات مستخدم')
    markup.add('🔙 العودة للإدارة')
    return markup

def get_payment_codes_keyboard():
    """تغيير أكواد الدفع"""
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add('📱 تغيير كود سيرياتل', '💳 تغيير عنوان شام كاش')
    markup.add('🔙 العودة للإدارة')
    return markup

def get_bot_status_keyboard():
    """التحكم بحالة البوت"""
    current_status = get_db_setting('bot_status')
    status_text = "🟢 تفعيل البوت" if current_status != 'active' else "🔴 تعطيل البوت (صيانة)"
    markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    markup.add(status_text)
    markup.add('🔙 العودة للإدارة')
    return markup

# ==========================================
# 5. معالجة الأوامر الرئيسية
# ==========================================
@bot.message_handler(commands=['start'])
def handle_start(message):
    uid = message.from_user.id
    first_name = message.from_user.first_name
    username = message.from_user.username
    
    reset_user_steps(uid)
    
    # حفظ معلومات المستخدم
    cursor.execute("""INSERT OR IGNORE INTO users 
        (user_id, first_name, username, created_at) 
        VALUES (?,?,?,?)""",
        (uid, first_name, username, datetime.now().strftime("%d-%m-%Y %H:%M")))
    conn.commit()
    
    # التحقق من حالة البوت
    if not check_bot_status() and uid != ADMIN_ID:
        bot.send_message(uid, "🔧 عذراً، البوت في حالة صيانة حالياً. سنعود للعمل خلال دقائق.")
        return
    
    # رسالة الترحيب
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
# 6. الراوتر الرئيسي للرسائل
# ==========================================
@bot.message_handler(func=lambda m: True)
def main_router(m):
    uid = m.from_user.id
    text = m.text
    
    # التحقق من حالة البوت
    if not check_bot_status() and uid != ADMIN_ID:
        bot.send_message(uid, "🔧 عذراً، البوت في حالة صيانة حالياً. سنعود للعمل خلال دقائق.")
        return
    
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

    # تصفير الخطوات عند الأزرار الرئيسية (لمنع التعليق)
    main_buttons = ['⚽ Ichancy ⚽', '🔽 الشحن في البوت', '🔼 السحب من البوت', 
                    '🔙 العودة للقائمة الرئيسية', '🔐 إدارة البوت', '📝 إنشاء حساب جديد',
                    '➕ تعبئة في الحساب', '➖ سحب من الحساب', '🗑 حذف الحساب']
    
    if text in main_buttons:
        reset_user_steps(uid)

    # ======================================
    # قسم Ichancy
    # ======================================
    if text == '⚽ Ichancy ⚽':
        cursor.execute("SELECT acc_name, acc_password, site_balance, deleted FROM users WHERE user_id=?", (uid,))
        user_data = cursor.fetchone()
        
        if not user_data or not user_data[0] or user_data[3] == 1:
            # لا يوجد حساب - عرض زر إنشاء حساب
            bot.send_message(m.chat.id, "📝 لا يوجد حساب مسجل لديك.", reply_markup=get_ichancy_main_keyboard())
        else:
            # يوجد حساب - عرض لوحة الحساب مع المعلومات
            keyboard, info_text = get_ichancy_account_keyboard(user_data[0], user_data[2], uid)
            bot.send_message(m.chat.id, info_text)  # الشريط العلوي
            bot.send_message(m.chat.id, "اختر من الخيارات:", reply_markup=keyboard)

    elif text == '📝 إنشاء حساب جديد':
        msg = bot.send_message(
            m.chat.id, 
            "📝 الرجاء إدخال اسم المستخدم بالحروف الإنجليزية فقط:"
        )
        bot.register_next_step_handler(msg, process_registration_name)

    elif text == '➕ تعبئة في الحساب':
        # شحن من رصيد البوت إلى رصيد الموقع
        cursor.execute("SELECT balance, site_balance, acc_name FROM users WHERE user_id=?", (uid,))
        data = cursor.fetchone()
        if data:
            msg = bot.send_message(
                m.chat.id,
                f"💰 رصيدك في البوت: {data[0]} ل.س\n"
                f"🌐 رصيدك في الموقع: {data[1]} NSP\n\n"
                f"أدخل المبلغ الذي تريد شحنه إلى حسابك في الموقع:"
            )
            bot.register_next_step_handler(msg, process_ichancy_charge, data[0])
        else:
            bot.send_message(m.chat.id, "❌ حدث خطأ، الرجاء المحاولة لاحقاً")

    elif text == '➖ سحب من الحساب':
        # سحب من رصيد الموقع إلى رصيد البوت
        cursor.execute("SELECT site_balance, balance FROM users WHERE user_id=?", (uid,))
        data = cursor.fetchone()
        if data:
            msg = bot.send_message(
                m.chat.id,
                f"🌐 رصيدك في الموقع: {data[0]} NSP\n"
                f"💰 رصيدك في البوت: {data[1]} ل.س\n\n"
                f"أدخل المبلغ الذي تريد سحبه من الموقع إلى رصيد البوت:"
            )
            bot.register_next_step_handler(msg, process_ichancy_withdraw, data[0])
        else:
            bot.send_message(m.chat.id, "❌ حدث خطأ، الرجاء المحاولة لاحقاً")

    elif text == '🗑 حذف الحساب':
        msg = bot.send_message(
            m.chat.id,
            "⚠️ تحذير! لن تستطيع استرجاع حسابك بعد الحذف\n"
            "للتأكيد، اكتب كلمة (حذف) وأرسلها:"
        )
        bot.register_next_step_handler(msg, process_delete_account)

    # ======================================
    # الشحن في البوت (خارجي)
    # ======================================
    elif text == '🔽 الشحن في البوت':
        bot.send_message(m.chat.id, "💰 اختر وسيلة الشحن:", reply_markup=get_charge_methods_keyboard())

    # ======================================
    # السحب من البوت (خارجي)
    # ======================================
    elif text == '🔼 السحب من البوت':
        bot.send_message(m.chat.id, "💰 اختر وسيلة السحب:", reply_markup=get_withdraw_methods_keyboard())

    # ======================================
    # العودة للقائمة الرئيسية
    # ======================================
    elif text == '🔙 العودة للقائمة الرئيسية':
        bot.send_message(uid, "القائمة الرئيسية:", reply_markup=get_main_keyboard(uid))

    # ======================================
    # أكواد الهدايا
    # ======================================
    elif text == '🎫 كود هدية':
        msg = bot.send_message(uid, "🎁 أرسل الكود الذي تريد استخدامه:")
        bot.register_next_step_handler(msg, redeem_gift_code)

    # ======================================
    # الرصيد
    # ======================================
    elif text == '💵 الرصيد':
        cursor.execute("SELECT balance FROM users WHERE user_id=?", (uid,))
        bal = cursor.fetchone()
        current_bal = bal[0] if bal else 0
        bot.send_message(uid, f"💰 رصيدك الحالي في البوت: {current_bal} ل.س")

    # ======================================
    # التواصل مع الدعم
    # ======================================
    elif text == '💬 التواصل مع الدعم':
        msg = bot.send_message(uid, "📝 أرسل رسالتك أو صورتك هنا وسيتم الرد عليك بأقرب وقت:")
        bot.register_next_step_handler(msg, process_support_ticket)

    # ======================================
    # إهداء صديق
    # ======================================
    elif text == '🎁 اهداء صديق':
        bot.send_message(uid, "⚠️ هذه الخدمة غير متاحة حالياً")

    # ======================================
    # لوحة الإدارة
    # ======================================
    elif text == '🔐 إدارة البوت' and uid == ADMIN_ID:
        bot.send_message(uid, "🔓 لوحة التحكم الخاصة بالمشرف:", reply_markup=get_admin_main_keyboard())

    # ===== أوامر الإدارة الفرعية =====
    elif text == '💰 تغيير أكواد الدفع' and uid == ADMIN_ID:
        bot.send_message(uid, "اختر ما تريد تغييره:", reply_markup=get_payment_codes_keyboard())

    elif text == '📱 تغيير كود سيرياتل' and uid == ADMIN_ID:
        msg = bot.send_message(uid, "📱 أرسل الأرقام الجديدة لسيرياتل كاش (يمكنك إرسال أكثر من رقم مفصولة بفواصل):")
        bot.register_next_step_handler(msg, process_update_syriatel)

    elif text == '💳 تغيير عنوان شام كاش' and uid == ADMIN_ID:
        msg = bot.send_message(uid, "💳 أرسل عنوان شام كاش الجديد:")
        bot.register_next_step_handler(msg, process_update_sham)

    elif text == '🎫 إنشاء كود هدية' and uid == ADMIN_ID:
        bot.send_message(uid, "اختر نوع الكود:", reply_markup=get_gift_type_keyboard())

    elif text == '👥 إدارة المستخدمين' and uid == ADMIN_ID:
        bot.send_message(uid, "اختر من خيارات إدارة المستخدمين:", reply_markup=get_user_management_keyboard())

    elif text == '📊 سجل المعاملات' and uid == ADMIN_ID:
        show_transactions_log(uid)

    elif text == '📋 قاعدة البيانات' and uid == ADMIN_ID:
        show_users_database(uid)

    elif text == '💬 تذاكر الدعم' and uid == ADMIN_ID:
        show_support_tickets(uid)

    elif text == '🔧 حالة البوت' and uid == ADMIN_ID:
        bot.send_message(uid, "التحكم بحالة البوت:", reply_markup=get_bot_status_keyboard())

    elif text in ['🟢 تفعيل البوت', '🔴 تعطيل البوت (صيانة)'] and uid == ADMIN_ID:
        new_status = 'active' if text == '🟢 تفعيل البوت' else 'maintenance'
        update_db_setting('bot_status', new_status, uid)
        status_msg = "🟢 تم تفعيل البوت" if new_status == 'active' else "🔴 تم تعطيل البوت (وضع الصيانة)"
        bot.send_message(uid, status_msg)
        
        if new_status == 'maintenance':
            # إرسال إشعار لجميع المستخدمين
            send_to_all_users("🔧 عذراً، البوت في حالة صيانة حالياً. سنعود للعمل خلال دقائق.", exclude_admin=True)

    elif text == '📨 رسالة جماعية' and uid == ADMIN_ID:
        msg = bot.send_message(uid, "📝 أرسل الرسالة التي تريد إرسالها لجميع المستخدمين:")
        bot.register_next_step_handler(msg, process_broadcast)

    elif text == '📧 رسالة فردية' and uid == ADMIN_ID:
        msg = bot.send_message(uid, "👤 أرسل معرف المستخدم (ID) أولاً:")
        bot.register_next_step_handler(msg, process_private_message_user)

    elif text == '🔄 استرجاع حساب' and uid == ADMIN_ID:
        msg = bot.send_message(uid, "👤 أرسل معرف المستخدم (ID) لاسترجاع حسابه:")
        bot.register_next_step_handler(msg, process_restore_account)

    elif text == '🔙 العودة للإدارة' and uid == ADMIN_ID:
        bot.send_message(uid, "لوحة الإدارة:", reply_markup=get_admin_main_keyboard())

    # ===== أوامر إدارة المستخدمين الفرعية =====
    elif text == '🔨 حظر مستخدم' and uid == ADMIN_ID:
        msg = bot.send_message(uid, "👤 أرسل معرف المستخدم (ID) الذي تريد حظره:")
        bot.register_next_step_handler(msg, process_ban_user)

    elif text == '✅ فك حظر مستخدم' and uid == ADMIN_ID:
        msg = bot.send_message(uid, "👤 أرسل معرف المستخدم (ID) الذي تريد فك حظره:")
        bot.register_next_step_handler(msg, process_unban_user)

    elif text == '💰 شحن رصيد لمستخدم' and uid == ADMIN_ID:
        msg = bot.send_message(uid, "👤 أرسل معرف المستخدم (ID) أولاً:")
        bot.register_next_step_handler(msg, process_charge_user_step1)

    elif text == '💸 سحب رصيد من مستخدم' and uid == ADMIN_ID:
        msg = bot.send_message(uid, "👤 أرسل معرف المستخدم (ID) أولاً:")
        bot.register_next_step_handler(msg, process_withdraw_user_step1)

    elif text == '📋 معلومات مستخدم' and uid == ADMIN_ID:
        msg = bot.send_message(uid, "👤 أرسل معرف المستخدم (ID) لعرض معلوماته:")
        bot.register_next_step_handler(msg, process_user_info)

# ==========================================
# 7. عمليات Ichancy (إنشاء حساب، شحن، سحب، حذف)
# ==========================================
def process_registration_name(message):
    uid = message.from_user.id
    if message.text in ['🔙 العودة للقائمة الرئيسية', '/start', '⚽ Ichancy ⚽']:
        handle_start(message)
        return
    
    # إضافة Matar- تلقائياً
    full_name = f"Matar-{message.text}"
    
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
        f"🎉 أهلاً وسهلاً بك في بوت Matar"
    )
    
    # عرض لوحة Ichancy
    keyboard, info_text = get_ichancy_account_keyboard(full_name, 0, uid)
    bot.send_message(uid, info_text)
    bot.send_message(uid, "اختر من الخيارات:", reply_markup=keyboard)
    
    # تسجيل العملية
    log_transaction(uid, "create_account", 0, "system", "success", details=f"Account: {full_name}")

def process_ichancy_charge(message, bot_balance):
    uid = message.from_user.id
    if message.text in ['🔙 العودة للقائمة الرئيسية', '/start']:
        handle_start(message)
        return
    
    try:
        amount = float(message.text)
        
        if amount > bot_balance:
            bot.send_message(uid, f"❌ رصيدك في البوت غير كافٍ. رصيدك الحالي: {bot_balance} ل.س")
            return
        
        if amount <= 0:
            bot.send_message(uid, "❌ المبلغ يجب أن يكون أكبر من صفر")
            return
        
        # محاكاة الشحن (حالياً - قبل ربط API)
        cursor.execute("UPDATE users SET balance = balance - ?, site_balance = site_balance + ? WHERE user_id=?", 
                      (amount, amount, uid))
        conn.commit()
        
        # الحصول على الرصيد الجديد
        cursor.execute("SELECT balance, site_balance FROM users WHERE user_id=?", (uid,))
        new_balances = cursor.fetchone()
        
        bot.send_message(
            uid, 
            f"✅ تم شحن حسابك في الموقع بنجاح!\n\n"
            f"💰 المبلغ المشحون: {amount} NSP\n"
            f"🆕 رصيدك الجديد في الموقع: {new_balances[1]} NSP\n"
            f"🔄 رصيدك المتبقي في البوت: {new_balances[0]} ل.س"
        )
        
        # تسجيل العملية
        log_transaction(uid, "ichancy_charge", amount, "internal", "success")
        
    except ValueError:
        bot.send_message(uid, "❌ الرجاء إدخال رقم صحيح")

def process_ichancy_withdraw(message, site_balance):
    uid = message.from_user.id
    if message.text in ['🔙 العودة للقائمة الرئيسية', '/start']:
        handle_start(message)
        return
    
    try:
        amount = float(message.text)
        
        if amount > site_balance:
            bot.send_message(uid, f"❌ رصيدك في الموقع غير كافٍ. رصيدك الحالي: {site_balance} NSP")
            return
        
        if amount <= 0:
            bot.send_message(uid, "❌ المبلغ يجب أن يكون أكبر من صفر")
            return
        
        # محاكاة السحب
        cursor.execute("UPDATE users SET site_balance = site_balance - ?, balance = balance + ? WHERE user_id=?", 
                      (amount, amount, uid))
        conn.commit()
        
        # الحصول على الرصيد الجديد
        cursor.execute("SELECT balance, site_balance FROM users WHERE user_id=?", (uid,))
        new_balances = cursor.fetchone()
        
        bot.send_message(
            uid, 
            f"✅ تم سحب رصيدك من الموقع إلى البوت بنجاح!\n\n"
            f"💰 المبلغ المسحوب: {amount} NSP\n"
            f"🆕 رصيدك الجديد في الموقع: {new_balances[1]} NSP\n"
            f"💰 رصيدك الجديد في البوت: {new_balances[0]} ل.س"
        )
        
        # تسجيل العملية
        log_transaction(uid, "ichancy_withdraw", amount, "internal", "success")
        
    except ValueError:
        bot.send_message(uid, "❌ الرجاء إدخال رقم صحيح")

def process_delete_account(message):
    uid = message.from_user.id
    if message.text == 'حذف':
        # نقل البيانات إلى جدول المحذوفات
        cursor.execute("SELECT acc_name, acc_password, site_balance, balance FROM users WHERE user_id=?", (uid,))
        user_data = cursor.fetchone()
        
        if user_data and user_data[0]:
            deleted_at = datetime.now().strftime("%d-%m-%Y %H:%M")
            cursor.execute("""INSERT OR REPLACE INTO deleted_accounts 
                (user_id, acc_name, acc_password, site_balance, balance, deleted_at) 
                VALUES (?,?,?,?,?,?)""",
                (uid, user_data[0], user_data[1], user_data[2], user_data[3], deleted_at))
            
            # تحديث حالة المستخدم
            cursor.execute("UPDATE users SET acc_name=NULL, acc_password=NULL, site_balance=0, deleted=1 WHERE user_id=?", (uid,))
            conn.commit()
            
            bot.send_message(uid, "✅ تم حذف حسابك بنجاح", reply_markup=get_main_keyboard(uid))
            log_transaction(uid, "delete_account", 0, "system", "success")
        else:
            bot.send_message(uid, "❌ لا يوجد حساب لحذفه", reply_markup=get_main_keyboard(uid))
    else:
        bot.send_message(uid, "❌ لم تؤكد الحذف بشكل صحيح", reply_markup=get_ichancy_main_keyboard())

# ==========================================
# 8. عمليات الشحن الخارجي (في البوت)
# ==========================================
@bot.callback_query_handler(func=lambda call: call.data.startswith('charge_'))
def handle_charge_methods(call):
    uid = call.from_user.id
    method = call.data.replace('charge_', '')
    
    if method == 'syria':
        numbers = get_db_setting('syriatel_numbers')
        min_amount = get_db_setting('min_charge')
        
        msg_text = (
            f"💳 سيرياتل كاش - الشحن اليدوي\n\n"
            f"📱 أرسل إلى أحد الأرقام التالية:\n"
            f"{numbers}\n\n"
            f"⚠️ أقل قيمة للشحن: {min_amount} ل.س\n"
            f"──────────────\n"
            f"📝 الآن، أرسل رقم عملية التحويل (12 خانة):"
        )
        msg = bot.send_message(call.message.chat.id, msg_text)
        bot.register_next_step_handler(msg, process_charge_receipt, "syriatel")
    
    elif method == 'sham':
        address = get_db_setting('sham_address')
        min_amount = get_db_setting('min_charge')
        
        msg_text = (
            f"💳 شام كاش - الشحن اليدوي\n\n"
            f"📱 أرسل إلى العنوان التالي:\n"
            f"{address}\n\n"
            f"⚠️ أقل قيمة للشحن: {min_amount} ل.س\n"
            f"──────────────\n"
            f"📝 الآن، أرسل رقم عملية التحويل:"
        )
        msg = bot.send_message(call.message.chat.id, msg_text)
        bot.register_next_step_handler(msg, process_charge_receipt, "sham")
    
    elif method in ['usdt', 'binance']:
        status = get_db_setting(f'{method}_status')
        bot.send_message(call.message.chat.id, f"⛔ الشحن بـ {method.upper()} {status} حالياً")

def process_charge_receipt(message, method):
    uid = message.from_user.id
    if message.text in ['🔙 العودة للقائمة الرئيسية', '/start']:
        handle_start(message)
        return
    
    receipt = message.text
    
    # التحقق من أن رقم العملية لم يستخدم مسبقاً
    if is_transaction_processed(receipt):
        bot.send_message(uid, "❌ عذراً، تم استخدام رقم العملية هذا من قبل. لا يمكن استخدام نفس الرقم مرتين.")
        return
    
    msg = bot.send_message(uid, "💰 الآن أرسل قيمة المبلغ الذي قمت بتحويله:")
    bot.register_next_step_handler(msg, process_charge_amount, method, receipt)

def process_charge_amount(message, method, receipt):
    uid = message.from_user.id
    if message.text in ['🔙 العودة للقائمة الرئيسية', '/start']:
        handle_start(message)
        return
    
    try:
        amount = float(message.text)
        min_amount = float(get_db_setting('min_charge'))
        
        if amount < min_amount:
            bot.send_message(uid, f"❌ أقل مبلغ للشحن هو {min_amount} ل.س")
            return
        
        # محاكاة التحقق (في الإصدار الحالي نقبل أي مبلغ)
        # تسجيل العملية كمستخدمة
        mark_transaction_processed(receipt, uid, amount)
        
        # شحن الرصيد
        new_balance = update_user_balance(uid, amount, add=True)
        
        # إشعار المشرف
        admin_msg = (
            f"💰 طلب شحن جديد\n"
            f"👤 المستخدم: {uid}\n"
            f"💵 المبلغ: {amount} ل.س\n"
            f"📱 الطريقة: {method}\n"
            f"🔢 رقم العملية: {receipt}"
        )
        bot.send_message(ADMIN_ID, admin_msg)
        
        # تأكيد للمستخدم
        bot.send_message(
            uid, 
            f"✅ تم شحن رصيدك بنجاح!\n"
            f"💰 المبلغ: {amount} ل.س\n"
            f"🆕 رصيدك الجديد: {new_balance} ل.س"
        )
        
        # تسجيل المعاملة
        log_transaction(uid, "charge", amount, method, "success", details=receipt)
        
    except ValueError:
        bot.send_message(uid, "❌ الرجاء إدخال رقم صحيح")

# ==========================================
# 9. عمليات السحب الخارجي (من البوت)
# ==========================================
@bot.callback_query_handler(func=lambda call: call.data.startswith('withdraw_'))
def handle_withdraw_methods(call):
    uid = call.from_user.id
    method = call.data.replace('withdraw_', '')
    
    if method == 'syria':
        msg = bot.send_message(call.message.chat.id, "💰 الرجاء إدخال قيمة المبلغ المراد سحبه:")
        bot.register_next_step_handler(msg, process_withdraw_amount, "syriatel")
    
    elif method == 'sham':
        # عرض اختيار العملة
        bot.send_message(call.message.chat.id, "اختر عملة السحب:", reply_markup=get_withdraw_currency_keyboard())

@bot.callback_query_handler(func=lambda call: call.data in ['withdraw_sham_lyr', 'withdraw_sham_usd'])
def handle_sham_currency(call):
    uid = call.from_user.id
    
    if call.data == 'withdraw_sham_usd':
        bot.send_message(call.message.chat.id, "⛔ عذراً، السحب بالدولار عبر شام كاش متوقف حالياً.")
        return
    
    # ليرة سورية
    msg = bot.send_message(call.message.chat.id, "💰 الرجاء إدخال قيمة المبلغ المراد سحبه (بالليرة السورية):")
    bot.register_next_step_handler(msg, process_withdraw_amount, "sham")

def process_withdraw_amount(message, method):
    uid = message.from_user.id
    if message.text in ['🔙 العودة للقائمة الرئيسية', '/start']:
        handle_start(message)
        return
    
    try:
        amount = float(message.text)
        
        # الحصول على الحدود حسب الطريقة
        if method == "syriatel":
            min_amount = float(get_db_setting('min_withdraw_syria'))
            max_amount = float(get_db_setting('max_withdraw_syria'))
        else:  # sham
            min_amount = float(get_db_setting('min_withdraw_sham'))
            max_amount = float(get_db_setting('max_withdraw_sham'))
        
        # التحقق من الحدود
        if amount < min_amount:
            bot.send_message(uid, f"❌ عذراً، أقل مبلغ للسحب هو {min_amount:,.0f} ل.س")
            return
        
        if amount > max_amount:
            bot.send_message(uid, f"❌ عذراً، أعلى مبلغ للسحب هو {max_amount:,.0f} ل.س")
            return
        
        # التحقق من رصيد المستخدم
        cursor.execute("SELECT balance FROM users WHERE user_id=?", (uid,))
        user_balance = cursor.fetchone()
        
        if not user_balance or user_balance[0] < amount:
            bot.send_message(uid, f"❌ رصيدك غير كافٍ. رصيدك الحالي: {user_balance[0] if user_balance else 0} ل.س")
            return
        
        # طلب رقم المحفظة
        if method == "syriatel":
            msg_text = "📱 الرجاء إدخال رقم سيرياتل كاش الذي تريد سحب الأرباح إليه:"
        else:  # sham
            msg_text = "📱 الرجاء إدخال عنوان شام كاش الذي تريد سحب الأرباح إليه:"
        
        msg = bot.send_message(uid, msg_text)
        bot.register_next_step_handler(msg, process_withdraw_account, method, amount)
        
    except ValueError:
        bot.send_message(uid, "❌ الرجاء إدخال رقم صحيح")

def process_withdraw_account(message, method, amount):
    uid = message.from_user.id
    if message.text in ['🔙 العودة للقائمة الرئيسية', '/start']:
        handle_start(message)
        return
    
    account = message.text
    
    # حساب العمولة
    commission_rate = float(get_db_setting('withdraw_commission'))
    commission = amount * commission_rate / 100
    net_amount = amount - commission
    
    # عرض التفاصيل
    details = (
        f"📊 تفاصيل عملية السحب:\n\n"
        f"💵 المبلغ المطلوب: {amount:,.0f} ل.س\n"
        f"💸 نسبة العمولة ({commission_rate}%): {commission:,.0f} ل.س\n"
        f"✅ المبلغ الصافي المستلم: {net_amount:,.0f} ل.س\n\n"
        f"هل أنت موافق على العملية؟"
    )
    
    # تخزين البيانات مؤقتاً للاستخدام لاحقاً
    bot.register_next_step_handler_by_chat_id(uid, lambda m: None)  # مسح أي خطوة سابقة
    bot.send_message(uid, details, reply_markup=get_confirmation_keyboard())
    
    # حفظ البيانات في الذاكرة المؤقتة (سيتم استخدامها في الكول باك)
    global temp_withdraw_data
    temp_withdraw_data = {
        'uid': uid,
        'method': method,
        'amount': amount,
        'commission': commission,
        'net_amount': net_amount,
        'account': account
    }

@bot.callback_query_handler(func=lambda call: call.data in ['confirm_yes', 'confirm_no'])
def handle_withdraw_confirmation(call):
    uid = call.from_user.id
    
    if call.data == 'confirm_no':
        bot.edit_message_text("❌ تم إلغاء عملية السحب.", call.message.chat.id, call.message.message_id)
        return
    
    # مستخدم موافق
    if 'temp_withdraw_data' not in globals() or temp_withdraw_data['uid'] != uid:
        bot.send_message(uid, "❌ حدث خطأ، الرجاء المحاولة من جديد")
        return
    
    data = temp_withdraw_data
    
    try:
        # خصم الرصيد من المستخدم
        update_user_balance(uid, data['amount'], add=False)
        
        # إضافة الرصيد إلى الكاشيرة
        update_cashier_balance(data['amount'], add=True)
        
        # إنشاء رقم عملية
        receipt = generate_receipt_number("WTH")
        
        # رسالة التأكيد للمستخدم
        confirm_msg = (
            f"✅ تم استلام طلب السحب بنجاح!\n\n"
            f"💰 المبلغ المطلوب: {data['amount']:,.0f} ل.س\n"
            f"💸 العمولة: {data['commission']:,.0f} ل.س\n"
            f"📱 ستستلم: {data['net_amount']:,.0f} ل.س\n"
            f"🏦 على: {data['account']}\n\n"
            f"⏳ سيصلك الرصيد خلال مدة تتراوح بين ساعة إلى 24 ساعة كحد أقصى.\n"
            f"🔢 رقم العملية: {receipt}"
        )
        bot.send_message(uid, confirm_msg)
        
        # إشعار للمشرف
        admin_msg = (
            f"🔔 طلب سحب جديد:\n"
            f"👤 المستخدم: {uid}\n"
            f"💳 الوسيلة: {data['method']}\n"
            f"💰 المبلغ المطلوب: {data['amount']:,.0f} ل.س\n"
            f"💸 العمولة: {data['commission']:,.0f} ل.س\n"
            f"✅ الصافي: {data['net_amount']:,.0f} ل.س\n"
            f"📱 الحساب: {data['account']}\n"
            f"🔢 رقم العملية: {receipt}"
        )
        bot.send_message(ADMIN_ID, admin_msg)
        
        # تسجيل المعاملة
        log_transaction(
            uid, "withdraw_request", data['amount'], data['method'], "pending",
            commission=data['commission'], net_amount=data['net_amount'],
            details=f"Account: {data['account']}, Receipt: {receipt}"
        )
        
        # حذف البيانات المؤقتة
        del globals()['temp_withdraw_data']
        
    except Exception as e:
        bot.send_message(uid, f"❌ حدث خطأ: {e}")
        bot.send_message(ADMIN_ID, f"⚠️ خطأ في عملية السحب: {e}")

# ==========================================
# 10. نظام أكواد الهدايا
# ==========================================
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
    if gift[2] <= gift[1]:  # limit_count <= used_count
        bot.send_message(uid, "❌ عذراً، تم استخدام الكود للعدد المحدد")
        return
    
    # إضافة الرصيد
    update_user_balance(uid, gift[0], add=True)
    cursor.execute("UPDATE gifts SET used_count = used_count + 1 WHERE code=?", (code,))
    cursor.execute("""INSERT INTO gift_usage (user_id, code, used_at) 
        VALUES (?,?,?)""", (uid, code, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    
    bot.send_message(uid, f"🎉 تم شحن {gift[0]} ل.س إلى رصيدك في البوت!")
    log_transaction(uid, "gift_redeem", gift[0], "gift", "success", details=f"Code: {code}")

# ==========================================
# 11. نظام التواصل مع الدعم (تذاكر)
# ==========================================
def process_support_ticket(message):
    uid = message.from_user.id
    
    # حفظ التذكرة
    file_id = None
    if message.content_type == 'photo':
        file_id = message.photo[-1].file_id
    
    cursor.execute("""INSERT INTO tickets 
        (user_id, message, file_id, status, created_at)
        VALUES (?,?,?,?,?)""",
        (uid, message.text or "[صورة]", file_id, 'open', 
         datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    
    ticket_id = cursor.lastrowid
    
    bot.send_message(uid, "✅ تم إرسال رسالتك، سيتم الرد عليك بأقرب وقت ممكن.")
    
    # إشعار المشرف
    user_info = f"@{message.from_user.username}" if message.from_user.username else f"ID: {uid}"
    admin_msg = (
        f"💬 تذكرة دعم جديدة #{ticket_id}\n"
        f"👤 المستخدم: {user_info}\n"
        f"📝 الرسالة: {message.text or '[صورة]'}\n"
        f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )
    
    if file_id:
        bot.send_photo(ADMIN_ID, file_id, caption=admin_msg)
    else:
        bot.send_message(ADMIN_ID, admin_msg)

def show_support_tickets(admin_id):
    cursor.execute("""SELECT ticket_id, user_id, message, status, created_at 
                      FROM tickets WHERE status='open' ORDER BY created_at DESC LIMIT 10""")
    tickets = cursor.fetchall()
    
    if not tickets:
        bot.send_message(admin_id, "📭 لا توجد تذاكر مفتوحة حالياً.")
        return
    
    msg = "📬 التذاكر المفتوحة:\n\n"
    for t in tickets:
        msg += f"#{t[0]} - المستخدم {t[1]} - {t[3]}\n{t[4]}\nرسالة: {t[2][:50]}...\n──────────\n"
    
    msg += "\nللرد على تذكرة، أرسل: /reply [رقم التذكرة] [الرد]"
    bot.send_message(admin_id, msg)

# ==========================================
# 12. أوامر الإدارة المتقدمة
# ==========================================
def process_update_syriatel(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    new_numbers = message.text
    update_db_setting('syriatel_numbers', new_numbers, ADMIN_ID)
    
    bot.send_message(ADMIN_ID, f"✅ تم تحديث أرقام سيرياتل كاش إلى:\n{new_numbers}")
    
    # إرسال إشعار لجميع المستخدمين
    send_to_all_users(f"⚠️ الرجاء الانتباه: تم تغيير أرقام سيرياتل كاش إلى:\n{new_numbers}", exclude_admin=True)

def process_update_sham(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    new_address = message.text
    update_db_setting('sham_address', new_address, ADMIN_ID)
    
    bot.send_message(ADMIN_ID, f"✅ تم تحديث عنوان شام كاش إلى:\n{new_address}")
    
    # إرسال إشعار لجميع المستخدمين
    send_to_all_users(f"⚠️ الرجاء الانتباه: تم تغيير عنوان شام كاش إلى:\n{new_address}", exclude_admin=True)

def process_broadcast(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    sent = send_to_all_users(message.text, exclude_admin=True)
    bot.send_message(ADMIN_ID, f"✅ تم إرسال الرسالة لـ {sent} مستخدم.")

def process_private_message_user(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        target_id = int(message.text)
        msg = bot.send_message(ADMIN_ID, f"📝 أرسل الرسالة للمستخدم {target_id}:")
        bot.register_next_step_handler(msg, process_private_message_text, target_id)
    except ValueError:
        bot.send_message(ADMIN_ID, "❌ معرف المستخدم غير صحيح")

def process_private_message_text(message, target_id):
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        bot.send_message(target_id, f"📨 رسالة من الإدارة:\n\n{message.text}")
        bot.send_message(ADMIN_ID, f"✅ تم إرسال الرسالة للمستخدم {target_id}")
    except Exception as e:
        bot.send_message(ADMIN_ID, f"❌ فشل الإرسال: {e}")

def process_ban_user(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        target_id = int(message.text)
        cursor.execute("UPDATE users SET status='banned' WHERE user_id=?", (target_id,))
        conn.commit()
        bot.send_message(ADMIN_ID, f"✅ تم حظر المستخدم {target_id}")
    except ValueError:
        bot.send_message(ADMIN_ID, "❌ معرف المستخدم غير صحيح")

def process_unban_user(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        target_id = int(message.text)
        cursor.execute("UPDATE users SET status='active' WHERE user_id=?", (target_id,))
        conn.commit()
        bot.send_message(ADMIN_ID, f"✅ تم فك حظر المستخدم {target_id}")
    except ValueError:
        bot.send_message(ADMIN_ID, "❌ معرف المستخدم غير صحيح")

def process_charge_user_step1(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        target_id = int(message.text)
        msg = bot.send_message(ADMIN_ID, f"💰 أدخل المبلغ لشحنه للمستخدم {target_id}:")
        bot.register_next_step_handler(msg, process_charge_user_step2, target_id)
    except ValueError:
        bot.send_message(ADMIN_ID, "❌ معرف المستخدم غير صحيح")

def process_charge_user_step2(message, target_id):
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        amount = float(message.text)
        new_balance = update_user_balance(target_id, amount, add=True)
        
        bot.send_message(ADMIN_ID, f"✅ تم شحن {amount} ل.س للمستخدم {target_id}. رصيده الجديد: {new_balance}")
        bot.send_message(target_id, f"💰 تم شحن {amount} ل.س إلى رصيدك في البوت من قبل الإدارة.")
        
        log_transaction(target_id, "admin_charge", amount, "admin", "success", admin_id=ADMIN_ID)
    except ValueError:
        bot.send_message(ADMIN_ID, "❌ قيمة غير صحيحة")

def process_withdraw_user_step1(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        target_id = int(message.text)
        msg = bot.send_message(ADMIN_ID, f"💰 أدخل المبلغ لسحبه من المستخدم {target_id}:")
        bot.register_next_step_handler(msg, process_withdraw_user_step2, target_id)
    except ValueError:
        bot.send_message(ADMIN_ID, "❌ معرف المستخدم غير صحيح")

def process_withdraw_user_step2(message, target_id):
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        amount = float(message.text)
        new_balance = update_user_balance(target_id, amount, add=False)
        
        bot.send_message(ADMIN_ID, f"✅ تم سحب {amount} ل.س من المستخدم {target_id}. رصيده الجديد: {new_balance}")
        bot.send_message(target_id, f"💸 تم سحب {amount} ل.س من رصيدك في البوت من قبل الإدارة.")
        
        log_transaction(target_id, "admin_withdraw", amount, "admin", "success", admin_id=ADMIN_ID)
    except ValueError:
        bot.send_message(ADMIN_ID, "❌ قيمة غير صحيحة")

def process_user_info(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        target_id = int(message.text)
        cursor.execute("""SELECT user_id, first_name, username, acc_name, acc_password, 
                                 balance, site_balance, status, created_at 
                          FROM users WHERE user_id=?""", (target_id,))
        user = cursor.fetchone()
        
        if user:
            info = (
                f"📋 معلومات المستخدم:\n"
                f"🆔 المعرف: {user[0]}\n"
                f"👤 الاسم: {user[1]}\n"
                f"📱 اليوزرنيم: @{user[2] if user[2] else 'لا يوجد'}\n"
                f"──────────\n"
                f"🌐 حساب Ichancy: {user[3] if user[3] else 'غير مسجل'}\n"
                f"🔑 كلمة السر: {user[4] if user[4] else '---'}\n"
                f"──────────\n"
                f"💰 رصيد البوت: {user[5]} ل.س\n"
                f"🌐 رصيد الموقع: {user[6]} NSP\n"
                f"📊 الحالة: {user[7]}\n"
                f"📅 تاريخ التسجيل: {user[8]}"
            )
            bot.send_message(ADMIN_ID, info)
        else:
            bot.send_message(ADMIN_ID, "❌ المستخدم غير موجود")
    except ValueError:
        bot.send_message(ADMIN_ID, "❌ معرف المستخدم غير صحيح")

def process_restore_account(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        target_id = int(message.text)
        
        # استعادة من جدول المحذوفات
        cursor.execute("""SELECT acc_name, acc_password, site_balance, balance 
                          FROM deleted_accounts WHERE user_id=?""", (target_id,))
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

def show_transactions_log(admin_id):
    cursor.execute("""SELECT id, user_id, type, amount, method, status, transaction_date 
                      FROM transactions ORDER BY id DESC LIMIT 20""")
    transactions = cursor.fetchall()
    
    if not transactions:
        bot.send_message(admin_id, "📊 لا توجد معاملات بعد.")
        return
    
    msg = "📊 آخر 20 معاملة:\n\n"
    for t in transactions:
        msg += f"#{t[0]} | 👤 {t[1]} | {t[2]}\n💰 {t[3]} | 📱 {t[5]} | {t[6]}\n──────────\n"
    
    bot.send_message(admin_id, msg)

def show_users_database(admin_id):
    cursor.execute("""SELECT COUNT(*), SUM(balance), SUM(site_balance) FROM users WHERE deleted=0""")
    stats = cursor.fetchone()
    
    cursor.execute("""SELECT user_id, first_name, acc_name, balance, status 
                      FROM users WHERE deleted=0 ORDER BY user_id LIMIT 20""")
    users = cursor.fetchall()
    
    msg = (
        f"📊 إحصائيات قاعدة البيانات:\n"
        f"👥 إجمالي المستخدمين: {stats[0]}\n"
        f"💰 إجمالي أرصدة البوت: {stats[1]:,.0f} ل.س\n"
        f"🌐 إجمالي أرصدة الموقع: {stats[2]:,.0f} NSP\n\n"
        f"📋 آخر 20 مستخدم:\n"
    )
    
    for u in users:
        msg += f"🆔 {u[0]} | {u[1]} | {u[2] or '—'} | {u[3]} ل.س | {u[4]}\n"
    
    bot.send_message(admin_id, msg)

# ==========================================
# 13. أمر الرد على التذاكر
# ==========================================
@bot.message_handler(commands=['reply'])
def handle_reply_command(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        parts = message.text.split(' ', 2)
        if len(parts) < 3:
            bot.send_message(ADMIN_ID, "❌ الاستخدام الصحيح: /reply [رقم التذكرة] [الرد]")
            return
        
        ticket_id = int(parts[1])
        reply_text = parts[2]
        
        # الحصول على معلومات التذكرة
        cursor.execute("SELECT user_id FROM tickets WHERE ticket_id=?", (ticket_id,))
        ticket = cursor.fetchone()
        
        if not ticket:
            bot.send_message(ADMIN_ID, "❌ تذكرة غير موجودة")
            return
        
        user_id = ticket[0]
        
        # تحديث التذكرة
        cursor.execute("""UPDATE tickets SET status='closed', admin_reply=?, replied_at=?
                          WHERE ticket_id=?""", 
                      (reply_text, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), ticket_id))
        conn.commit()
        
        # إرسال الرد للمستخدم
        bot.send_message(user_id, f"📨 رد من الدعم على تذكرتك #{ticket_id}:\n\n{reply_text}")
        
        bot.send_message(ADMIN_ID, f"✅ تم الرد على التذكرة #{ticket_id}")
        
    except Exception as e:
        bot.send_message(ADMIN_ID, f"❌ خطأ: {e}")

# ==========================================
# 14. تشغيل البوت والحماية
# ==========================================
if __name__ == "__main__":
    keep_alive()
    print("🚀 Matar Bot Final Version is starting...")
    print(f"👤 Admin ID: {ADMIN_ID}")
    print("✅ Anti-Lag System Active")
    print("✅ Database Connected")
    print("✅ All Features Loaded")
    
    # تشغيل البوت مع حماية من الأعطال
    while True:
        try:
            bot.polling(none_stop=True, skip_pending=True, timeout=30)
        except Exception as e:
            print(f"⚠️ Polling error: {e}")
            time.sleep(5)
            continue
