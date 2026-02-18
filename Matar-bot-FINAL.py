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

GITHUB_TOKEN = "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"
def update_db_setting(key, value):
    # هذه الدالة مجرد مثال لتحديث إعدادات البوت
    print(f"تم تحديث الإعداد: {key} = {value}")

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
        total_earnings REAL DEFAULT 0)""")

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
    
    for key, value in default_settings:
        cursor.execute("INSERT OR IGNORE INTO settings(key, value) VALUES (?,?)", (key, value))
    
    cursor.execute("INSERT OR IGNORE INTO cashier_balance(admin_id, balance) VALUES (?,0)", (ADMIN_ID,))
    
    cursor.execute("SELECT * FROM referral_cycles WHERE status='active'")
    if not cursor.fetchone():
        start = datetime.now()
        end = start + timedelta(days=10)
        cursor.execute("INSERT INTO referral_cycles (start_date, end_date, status) VALUES (?,?,?)", 
                      (start.strftime("%Y-%m-%d %H:%M:%S"), end.strftime("%Y-%m-%d %H:%M:%S"), 'active'))
        update_db_setting('next_referral_payout', end.strftime("%Y-%m-%d %H:%M:%S"))
    
    conn.commit()
    return conn, cursor

conn, cursor = setup_database()

# جلسات السحب المؤقتة لكل مستخدم
withdraw_sessions = {}

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
    return result[0] if result else None

def update_db_setting(key_name, value, admin_id=ADMIN_ID):
    cursor.execute("""UPDATE settings SET value=?, updated_at=?, updated_by=? 
                      WHERE key=?""", (value, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), admin_id, key_name))
    conn.commit()

def reset_user_steps(uid):
    bot.clear_step_handler_by_chat_id(chat_id=uid)

def generate_receipt_number(prefix="TXN"):
    timestamp = datetime.now().strftime("%y%m%d%H%M%S")
    random_part = ''.join(random.choices(string.digits, k=4))
    return f"{prefix}{timestamp}{random_part}"

def generate_gift_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))

def generate_ref_code(user_id):
    return f"MATAR{user_id}{''.join(random.choices(string.ascii_uppercase + string.digits, k=5))}"

def log_transaction(user_id, type, amount, method, status, commission=0, net_amount=0, admin_id=None, details=""):
    receipt = generate_receipt_number()
    cursor.execute("""INSERT INTO transactions 
        (user_id, type, amount, commission, net_amount, method, status, transaction_date, admin_id, details, receipt_number)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (user_id, type, amount, commission, net_amount, method, status, 
         datetime.now().strftime("%Y-%m-%d %H:%M:%S"), admin_id, details, receipt))
    conn.commit()
    return receipt

def is_transaction_processed(receipt_number):
    cursor.execute("SELECT * FROM processed_transactions WHERE receipt_number=?", (receipt_number,))
    return cursor.fetchone() is not None

def mark_transaction_processed(receipt_number, user_id, amount):
    cursor.execute("""INSERT INTO processed_transactions (receipt_number, user_id, amount, processed_at)
                      VALUES (?,?,?,?)""",
                   (receipt_number, user_id, amount, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()

def update_user_balance(user_id, amount, add=True):
    cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    result = cursor.fetchone()
    if result:
        new_balance = result[0] + amount if add else result[0] - amount
        cursor.execute("UPDATE users SET balance=? WHERE user_id=?", (new_balance, user_id))
        conn.commit()
        return new_balance
    return None

def update_cashier_balance(amount, add=True, admin_id=ADMIN_ID):
    cursor.execute("SELECT balance FROM cashier_balance WHERE admin_id=?", (admin_id,))
    result = cursor.fetchone()
    if result:
        new_balance = result[0] + amount if add else result[0] - amount
        cursor.execute("UPDATE cashier_balance SET balance=? WHERE admin_id=?", (new_balance, admin_id))
        conn.commit()
        return new_balance
    return None

def check_bot_status():
    status = get_db_setting('bot_status')
    return status == 'active'

def send_to_all_users(message_text, exclude_admin=False, exclude_moderators=False):
    cursor.execute("SELECT user_id FROM users WHERE deleted=0")
    sent_count = 0
    for user in cursor.fetchall():
        if exclude_admin and user[0] == ADMIN_ID:
            continue
        if exclude_moderators and is_moderator(user[0]):
            continue
        try:
            bot.send_message(user[0], message_text)
            sent_count += 1
        except:
            continue
    return sent_count

def is_moderator(user_id):
    if user_id == ADMIN_ID:
        return True
    cursor.execute("SELECT user_id FROM moderators WHERE user_id=?", (user_id,))
    return cursor.fetchone() is not None

def get_moderator_name(user_id):
    cursor.execute("SELECT custom_name FROM moderators WHERE user_id=?", (user_id,))
    result = cursor.fetchone()
    if result and result[0]:
        return result[0]
    return f"مشرف {user_id}"

def get_user_custom_name(user_id):
    cursor.execute("SELECT custom_name FROM users WHERE user_id=?", (user_id,))
    result = cursor.fetchone()
    return result[0] if result and result[0] else None

def format_time_remaining(target_time):
    try:
        target = datetime.strptime(target_time, "%Y-%m-%d %H:%M:%S")
        now = datetime.now()
        diff = target - now
        
        days = diff.days
        hours = diff.seconds // 3600
        minutes = (diff.seconds % 3600) // 60
        
        return f"{days} يوم {hours} ساعة {minutes} دقيقة"
    except:
        return "غير متوفر"

def add_referral_earning(referrer_id, amount, from_user_id, transaction_id):
    cursor.execute("""SELECT start_date FROM referral_cycles WHERE status='active'""")
    cycle = cursor.fetchone()
    cycle_start = cycle[0] if cycle else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    cursor.execute("""INSERT INTO referral_earnings 
        (referrer_id, amount, from_user_id, transaction_id, cycle_start, earned_at)
        VALUES (?,?,?,?,?,?)""",
        (referrer_id, amount, from_user_id, transaction_id, cycle_start,
         datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    
    cursor.execute("""UPDATE users SET current_earnings = current_earnings + ?,
                      total_earnings = total_earnings + ? WHERE user_id=?""",
                   (amount, amount, referrer_id))
    conn.commit()

def process_referral_charge(user_id, charge_amount, transaction_id):
    cursor.execute("SELECT referred_by FROM users WHERE user_id=?", (user_id,))
    result = cursor.fetchone()
    if result and result[0]:
        referrer_id = result[0]
        percentage = float(get_db_setting('referral_percentage'))
        earning = charge_amount * percentage / 100
        add_referral_earning(referrer_id, earning, user_id, transaction_id)
        return referrer_id, earning
    return None, None

def check_and_create_ref_code(user_id):
    cursor.execute("SELECT ref_code FROM users WHERE user_id=?", (user_id,))
    result = cursor.fetchone()
    if result and result[0]:
        return result[0]
    else:
        ref_code = generate_ref_code(user_id)
        cursor.execute("UPDATE users SET ref_code=? WHERE user_id=?", (ref_code, user_id))
        conn.commit()
        return ref_code

def get_user_by_ref_code(ref_code):
    cursor.execute("SELECT user_id FROM users WHERE ref_code=?", (ref_code,))
    result = cursor.fetchone()
    return result[0] if result else None

def register_referral(referrer_id, new_user_id):
    cursor.execute("""INSERT INTO referrals_log (referrer_id, referred_id, joined_at)
                      VALUES (?,?,?)""",
                  (referrer_id, new_user_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    cursor.execute("""UPDATE users SET referral_count = referral_count + 1 
                      WHERE user_id=?""", (referrer_id,))
    conn.commit()

def has_completed_welcome(user_id):
    cursor.execute("SELECT created_at FROM users WHERE user_id=?", (user_id,))
    result = cursor.fetchone()
    if result and result[0]:
        try:
            created = datetime.strptime(result[0], "%d-%m-%Y %H:%M")
            now = datetime.now()
            diff = now - created
            return diff.total_seconds() > 60
        except:
            return False
    return False

# ==========================================
# 4. بناء القوائم
# ==========================================
def get_main_keyboard(uid):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(types.KeyboardButton('⚽ Ichancy ⚽'))
    buttons = [
        types.KeyboardButton('💰 الرصيد'),
        types.KeyboardButton('🎁 اهداء رصيد'),
        types.KeyboardButton('🎫 كود هدية'),
        types.KeyboardButton('💳 الشحن في البوت'),
        types.KeyboardButton('💸 السحب من البوت'),
        types.KeyboardButton('👥 دعوة الأصدقاء'),
        types.KeyboardButton('📞 التواصل مع الدعم'),
        types.KeyboardButton('📜 الشروط والاحكام')
    ]
    markup.add(*buttons)
    if uid == ADMIN_ID or is_moderator(uid):
        markup.add(types.KeyboardButton('🔐 إدارة البوت'))
    return markup

def get_ichancy_main_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    markup.add(types.KeyboardButton('📝 إنشاء حساب جديد'))
    markup.add(types.KeyboardButton('🔙 العودة للقائمة الرئيسية'))
    return markup

def get_ichancy_account_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(
        types.KeyboardButton('➕ تعبئة في الحساب'),
        types.KeyboardButton('➖ سحب من الحساب')
    )
    markup.add(types.KeyboardButton('🗑 حذف الحساب'))
    markup.add(types.KeyboardButton('🔙 العودة للقائمة الرئيسية'))
    return markup

def format_ichancy_info(acc_name, acc_password, user_id, created_at):
    return (
        f"👤 الحساب: {acc_name}\n"
        f"🔑 كلمة السر: {acc_password}\n"
        f"🆔 ID: {user_id}\n"
        f"📅 تاريخ الانشاء: {created_at}"
    )

def get_charge_methods_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("💳 سيرياتل كاش", callback_data="charge_syria"),
        types.InlineKeyboardButton("💳 شام كاش", callback_data="charge_sham"),
        types.InlineKeyboardButton("🔷 USDT", callback_data="charge_usdt"),
        types.InlineKeyboardButton("💱 بينانس", callback_data="charge_binance")
    )
    return markup

def get_withdraw_methods_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("💳 سيرياتل كاش", callback_data="withdraw_syria"),
        types.InlineKeyboardButton("💳 شام كاش", callback_data="withdraw_sham")
    )
    return markup

def get_withdraw_currency_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🇸🇾 ليرة سورية", callback_data="withdraw_sham_lyr"),
        types.InlineKeyboardButton("💵 دولار", callback_data="withdraw_sham_usd")
    )
    return markup

def get_confirmation_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✅ موافق", callback_data="confirm_yes"),
        types.InlineKeyboardButton("❌ إلغاء", callback_data="confirm_no")
    )
    return markup

def get_gift_type_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("فردي 👤", callback_data="gift_individual"),
        types.InlineKeyboardButton("جماعي 👥", callback_data="gift_group")
    )
    return markup

def get_reply_keyboard_for_ticket(ticket_id, user_id):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("✏️ رد على الرسالة", callback_data=f"reply_ticket_{ticket_id}_{user_id}")
    )
    return markup

def get_admin_main_keyboard(is_owner=False):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    
    if is_owner:
        markup.add('🎫 إنشاء كود هدية', '👥 إدارة المستخدمين')
        markup.add('💰 تغيير أكواد الدفع', '📊 سجل المعاملات')
        markup.add('📨 رسالة جماعية', '📧 رسالة فردية')
        markup.add('🔄 استرجاع حساب', '🔧 حالة البوت')
        markup.add('📋 قاعدة البيانات', '💬 تذاكر الدعم')
        markup.add('👥 المشرفين', '📊 نظام الإحالات')
    else:
        markup.add('💰 تغيير أكواد الدفع', '🔧 حالة البوت')
        markup.add('📨 رسالة جماعية', '📧 رسالة فردية')
        markup.add('💬 تذاكر الدعم', '📋 عمليات التحويل')
        markup.add('✏️ إعادة تسمية مستخدم')
    
    markup.add('🔙 العودة للقائمة الرئيسية')
    return markup

def get_moderator_management_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add('➕ إضافة مشرف', '➖ إزالة مشرف')
    markup.add('✏️ إعادة تسمية مشرف', '🔒 صلاحيات مشرف')
    markup.add('📋 قائمة المشرفين')
    markup.add('🔙 العودة للإدارة')
    return markup

def get_referral_system_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add('📊 تقارير الإحالات', '👥 قائمة المحيلين')
    markup.add('💰 الأرباح الحالية', '📜 سجل الأرباح')
    markup.add('🔄 تصفير الدورة', '⚙️ تعديل النسبة')
    markup.add('🔙 العودة للإدارة')
    return markup

def get_payment_codes_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add('📱 تغيير كود سيرياتل', '💳 تغيير عنوان شام كاش')
    markup.add('🔙 العودة للإدارة')
    return markup

def get_bot_status_keyboard():
    current_status = get_db_setting('bot_status')
    status_text = "🟢 تفعيل البوت" if current_status != 'active' else "🔴 تعطيل البوت (صيانة)"
    markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    markup.add(status_text)
    markup.add('🔙 العودة للإدارة')
    return markup

def get_user_management_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add('🔨 حظر مستخدم', '✅ فك حظر مستخدم')
    markup.add('💰 شحن رصيد لمستخدم', '💸 سحب رصيد من مستخدم')
    markup.add('📝 معلومات مستخدم', '✏️ إعادة تسمية مستخدم')
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
    
    ref_code = None
    if len(message.text.split()) > 1:
        ref_code = message.text.split()[1]
    
    cursor.execute("""INSERT OR IGNORE INTO users 
        (user_id, first_name, username, created_at) 
        VALUES (?,?,?,?)""",
        (uid, first_name, username, datetime.now().strftime("%d-%m-%Y %H:%M")))
    conn.commit()
    
    if ref_code and ref_code.startswith('ref_'):
        referrer_id = get_user_by_ref_code(ref_code)
        if referrer_id and referrer_id != uid:
            cursor.execute("SELECT referred_by FROM users WHERE user_id=?", (uid,))
            if not cursor.fetchone()[0]:
                cursor.execute("UPDATE users SET referred_by=? WHERE user_id=?", (referrer_id, uid))
                register_referral(referrer_id, uid)
    
    check_and_create_ref_code(uid)
    
    if not check_bot_status() and uid != ADMIN_ID and not is_moderator(uid):
        bot.send_message(uid, "🔧 عذراً، البوت في حالة صيانة حالياً. سنعود للعمل خلال دقائق.")
        return
    
    if not check_subscription(uid):
        btn = types.InlineKeyboardMarkup().add(
            types.InlineKeyboardButton("📢 اشترك في القناة", url=CHANNEL_URL),
            types.InlineKeyboardButton("✅ تم الاشتراك", callback_data="check_sub")
        )
        
        welcome_text = (
            f"🎯 أهلاً وسهلاً بك في بوت Matar 🌧️\n\n"
            f"البوت الرسمي لموقع Ichancy ✅\n"
            f"هذا البوت مخصص لإنشاء حساب على موقع Ichancy وإدارته في عمليات الشحن والسحب\n\n"
            f"⚠️ شرط أساسي لاستخدام البوت:\n"
            f"الرجاء الاشتراك في قناتنا على تيلغرام لتتمكن من استخدام البوت"
        )
        bot.send_message(message.chat.id, welcome_text, reply_markup=btn)
        return
    
    if not has_completed_welcome(uid):
        bot.send_message(message.chat.id, "✅ تم التحقق من اشتراكك! مرحباً بك في البوت 🎉")
    
    bot.send_message(message.chat.id, "القائمة الرئيسية:", reply_markup=get_main_keyboard(uid))

@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def check_sub_callback(call):
    uid = call.from_user.id
    if check_subscription(uid):
        bot.edit_message_text(
            "✅ اشتراكك مؤكد! مرحباً بك في البوت",
            call.message.chat.id,
            call.message.message_id
        )
        bot.send_message(uid, "القائمة الرئيسية:", reply_markup=get_main_keyboard(uid))
    else:
        bot.answer_callback_query(call.id, "❌ لم تشترك بعد! اشترك ثم حاول مرة أخرى", show_alert=True)

# ==========================================
# 6. الراوتر الرئيسي للرسائل
# ==========================================
@bot.message_handler(func=lambda m: True)
def main_router(m):
    uid = m.from_user.id
    text = m.text
    
    reset_user_steps(uid)
    
    if not check_bot_status() and uid != ADMIN_ID and not is_moderator(uid):
        bot.send_message(uid, "🔧 عذراً، البوت في حالة صيانة حالياً. سنعود للعمل خلال دقائق.")
        return
    
    cursor.execute("SELECT status FROM users WHERE user_id=?", (uid,))
    user_status = cursor.fetchone()
    if user_status and user_status[0] == 'banned':
        bot.send_message(uid, "❌ نعتذر، حسابك محظور من استخدام النظام.")
        return

    if not check_subscription(uid):
        btn = types.InlineKeyboardMarkup().add(
            types.InlineKeyboardButton("📢 اشترك في القناة", url=CHANNEL_URL)
        )
        bot.send_message(uid, "⚠️ يجب الاشتراك في القناة أولاً", reply_markup=btn)
        return

    if text == '⚽ Ichancy ⚽':
        cursor.execute("SELECT acc_name, acc_password, site_balance, deleted, created_at FROM users WHERE user_id=?", (uid,))
        user_data = cursor.fetchone()
        
        if not user_data or not user_data[0] or user_data[3] == 1:
            bot.send_message(m.chat.id, "📝 لا يوجد حساب مسجل لديك.", reply_markup=get_ichancy_main_keyboard())
        else:
            info = format_ichancy_info(user_data[0], user_data[1], uid, user_data[4])
            bot.send_message(m.chat.id, info)
            bot.send_message(m.chat.id, "اختر من الخيارات:", reply_markup=get_ichancy_account_keyboard())

    elif text == '💰 الرصيد':
        cursor.execute("SELECT balance FROM users WHERE user_id=?", (uid,))
        bal = cursor.fetchone()
        current_bal = bal[0] if bal else 0
        bot.send_message(uid, f"💰 رصيدك الحالي في البوت: {current_bal} ل.س")

    elif text == '🎁 اهداء رصيد':
        msg = bot.send_message(uid, "👤 أرسل معرف المستخدم (ID) الذي تريد إهداءه:")
        bot.register_next_step_handler(msg, process_gift_user_id)

    elif text == '🎫 كود هدية':
        msg = bot.send_message(uid, "🎁 أرسل الكود الذي تريد استخدامه:")
        bot.register_next_step_handler(msg, redeem_gift_code)

    elif text == '💳 الشحن في البوت':
        bot.send_message(m.chat.id, "💰 اختر وسيلة الشحن:", reply_markup=get_charge_methods_keyboard())

    elif text == '💸 السحب من البوت':
        bot.send_message(m.chat.id, "💰 اختر وسيلة السحب:", reply_markup=get_withdraw_methods_keyboard())

    elif text == '👥 دعوة الأصدقاء':
        show_referral_info(uid)

    elif text == '📞 التواصل مع الدعم':
        msg = bot.send_message(uid, "📝 أرسل رسالتك أو صورتك هنا وسيتم الرد عليك بأقرب وقت:")
        bot.register_next_step_handler(msg, process_support_ticket)

    elif text == '📜 الشروط والاحكام':
        show_terms_and_conditions(uid)

    elif text == '🔙 العودة للقائمة الرئيسية':
        bot.send_message(uid, "القائمة الرئيسية:", reply_markup=get_main_keyboard(uid))

    elif text == '📝 إنشاء حساب جديد':
        msg = bot.send_message(
            m.chat.id, 
            "📝 الرجاء إدخال اسم المستخدم بالحروف الإنجليزية فقط:"
        )
        bot.register_next_step_handler(msg, process_registration_name)

    elif text == '➕ تعبئة في الحساب':
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

    elif text == '🔐 إدارة البوت':
        if uid == ADMIN_ID:
            bot.send_message(uid, "🔓 لوحة التحكم الخاصة بالمالك:", reply_markup=get_admin_main_keyboard(is_owner=True))
        elif is_moderator(uid):
            bot.send_message(uid, "🔓 لوحة التحكم الخاصة بالمشرف:", reply_markup=get_admin_main_keyboard(is_owner=False))

    elif uid == ADMIN_ID:
        if text == '🎫 إنشاء كود هدية':
            bot.send_message(uid, "اختر نوع الكود:", reply_markup=get_gift_type_keyboard())
        elif text == '👥 إدارة المستخدمين':
            bot.send_message(uid, "اختر من خيارات إدارة المستخدمين:", reply_markup=get_user_management_keyboard())
        elif text == '💰 تغيير أكواد الدفع':
            bot.send_message(uid, "اختر ما تريد تغييره:", reply_markup=get_payment_codes_keyboard())
        elif text == '📊 سجل المعاملات':
            show_transactions_log(uid)
        elif text == '📨 رسالة جماعية':
            msg = bot.send_message(uid, "📝 أرسل الرسالة التي تريد إرسالها لجميع المستخدمين:")
            bot.register_next_step_handler(msg, process_broadcast)
        elif text == '📧 رسالة فردية':
            msg = bot.send_message(uid, "👤 أرسل معرف المستخدم (ID) أولاً:")
            bot.register_next_step_handler(msg, process_private_message_user)
        elif text == '🔄 استرجاع حساب':
            msg = bot.send_message(uid, "👤 أرسل معرف المستخدم (ID) لاسترجاع حسابه:")
            bot.register_next_step_handler(msg, process_restore_account)
        elif text == '🔧 حالة البوت':
            bot.send_message(uid, "التحكم بحالة البوت:", reply_markup=get_bot_status_keyboard())
        elif text in ['🟢 تفعيل البوت', '🔴 تعطيل البوت (صيانة)']:
            new_status = 'active' if text == '🟢 تفعيل البوت' else 'maintenance'
            update_db_setting('bot_status', new_status, uid)
            status_msg = "🟢 تم تفعيل البوت" if new_status == 'active' else "🔴 تم تعطيل البوت (وضع الصيانة)"
            bot.send_message(uid, status_msg)
            if new_status == 'maintenance':
                send_to_all_users("🔧 عذراً، البوت في حالة صيانة حالياً. سنعود للعمل خلال دقائق.", 
                                exclude_admin=True, exclude_moderators=True)
        elif text == '📋 قاعدة البيانات':
            show_users_database(uid)
        elif text == '💬 تذاكر الدعم':
            show_support_tickets(uid)
        elif text == '👥 المشرفين':
            bot.send_message(uid, "إدارة المشرفين:", reply_markup=get_moderator_management_keyboard())
        elif text == '📊 نظام الإحالات':
            bot.send_message(uid, "نظام الإحالات:", reply_markup=get_referral_system_keyboard())
        elif text == '➕ إضافة مشرف':
            msg = bot.send_message(uid, "👤 أرسل معرف المستخدم (ID) لإضافته كمشرف:")
            bot.register_next_step_handler(msg, process_add_moderator)
        elif text == '➖ إزالة مشرف':
            msg = bot.send_message(uid, "👤 أرسل معرف المستخدم (ID) لإزالة الاشراف منه:")
            bot.register_next_step_handler(msg, process_remove_moderator)
        elif text == '✏️ إعادة تسمية مشرف':
            msg = bot.send_message(uid, "👤 أرسل معرف المستخدم (ID) لإعادة تسميته:")
            bot.register_next_step_handler(msg, process_rename_moderator_step1)
        elif text == '📋 قائمة المشرفين':
            show_moderators_list(uid)
        elif text == '🔙 العودة للإدارة':
            bot.send_message(uid, "لوحة الإدارة:", reply_markup=get_admin_main_keyboard(is_owner=True))

    elif is_moderator(uid):
        if text == '💰 تغيير أكواد الدفع':
            bot.send_message(uid, "اختر ما تريد تغييره:", reply_markup=get_payment_codes_keyboard())
        elif text == '🔧 حالة البوت':
            bot.send_message(uid, "التحكم بحالة البوت:", reply_markup=get_bot_status_keyboard())
        elif text in ['🟢 تفعيل البوت', '🔴 تعطيل البوت (صيانة)']:
            new_status = 'active' if text == '🟢 تفعيل البوت' else 'maintenance'
            update_db_setting('bot_status', new_status, uid)
            status_msg = "🟢 تم تفعيل البوت" if new_status == 'active' else "🔴 تم تعطيل البوت (وضع الصيانة)"
            bot.send_message(uid, status_msg)
        elif text == '📨 رسالة جماعية':
            msg = bot.send_message(uid, "📝 أرسل الرسالة التي تريد إرسالها لجميع المستخدمين:")
            bot.register_next_step_handler(msg, process_broadcast)
        elif text == '📧 رسالة فردية':
            msg = bot.send_message(uid, "👤 أرسل معرف المستخدم (ID) أولاً:")
            bot.register_next_step_handler(msg, process_private_message_user)
        elif text == '💬 تذاكر الدعم':
            show_support_tickets(uid)
        elif text == '📋 عمليات التحويل':
            show_transactions_log(uid)
        elif text == '✏️ إعادة تسمية مستخدم':
            msg = bot.send_message(uid, "👤 أرسل معرف المستخدم (ID) لإعادة تسميته:")
            bot.register_next_step_handler(msg, process_rename_user_step1)
        elif text == '🔙 العودة للإدارة':
            bot.send_message(uid, "لوحة الإدارة:", reply_markup=get_admin_main_keyboard(is_owner=False))

# ==========================================
# 7. نظام الإحالات
# ==========================================
def show_referral_info(uid):
    cursor.execute("SELECT referral_count, current_earnings, total_earnings, ref_code FROM users WHERE user_id=?", (uid,))
    data = cursor.fetchone()
    
    if not data:
        bot.send_message(uid, "❌ حدث خطأ في جلب البيانات")
        return
    
    ref_count, current_earnings, total_earnings, ref_code = data
    
    next_payout = get_db_setting('next_referral_payout')
    time_left = format_time_remaining(next_payout) if next_payout else "غير محدد"
    
    try:
        bot_username = bot.get_me().username
        ref_link = f"https://t.me/{bot_username}?start=ref_{ref_code}"
    except:
        ref_link = "رابط غير متوفر حالياً"
    
    referral_text = (
        f"🌟 نظام احالات Matar bot 🌟\n\n"
        f"يقدّم لك فرصة لدخل إضافي كل 10 أيام .\n"
        f"كن وكيلاً معنا بأبسط طريقة\n"
        f"إحصل على نسبة ثابتة لكل عمليات الشحن والتعبئة القادمة عن طريق رابط احالتك ضمن البوت\n\n"
        f"1- عند الدخول الى البوت قم بنسخ رابط الاحالة الخاص بك عن طريق الضغط على خيار رابط الاحالة الخاص بي\n"
        f"2- عندما تقوم بنشر رابط احالتك ويقوم أحد بالتسجيل عن طريقة سنبدأ بحساب نسبة ثابتة لجميع عمليات السحب والتعبئة عن طريقك .\n"
        f"3- يمكن الاطلاع على عدد الاحالات التي قامت بالتسجيل من خلال الرابط الخاص بك عن طريق الضغط على خيار عدد الاحالات الخاصة بك خلال المسابقة الحالية\n"
        f"4- يتم حساب الارباح عند وجود 3 إحالات نشطة او أكثر\n"
        f"ماذا تنتظر...! \n"
        f"توزيع النسب كل 10 أيام\n\n"
        f"عدد الاحالات التابعة لك: {ref_count}\n"
        f"رابط الإحالة الخاص بك:\n"
        f"{ref_link}\n\n"
        f"الموعد القادم لتوزيع الاحالات: {next_payout}\n"
        f"{time_left}"
    )
    
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(
        types.KeyboardButton("📋 رابط الإحالة الخاص بي"),
        types.KeyboardButton("👥 عدد احالاتي"),
        types.KeyboardButton("🔙 العودة للقائمة الرئيسية")
    )
    
    bot.send_message(uid, referral_text, reply_markup=markup)

# ==========================================
# 8. عمليات Ichancy
# ==========================================
def process_registration_name(message):
    uid = message.from_user.id
    if message.text in ['🔙 العودة للقائمة الرئيسية', '/start', '⚽ Ichancy ⚽']:
        handle_start(message)
        return
    
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
    
    info = format_ichancy_info(full_name, password, uid, created_at)
    bot.send_message(uid, info)
    bot.send_message(uid, "اختر من الخيارات:", reply_markup=get_ichancy_account_keyboard())
    
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
        
        cursor.execute("UPDATE users SET balance = balance - ?, site_balance = site_balance + ? WHERE user_id=?", 
                      (amount, amount, uid))
        conn.commit()
        
        cursor.execute("SELECT balance, site_balance FROM users WHERE user_id=?", (uid,))
        new_balances = cursor.fetchone()
        
        bot.send_message(
            uid, 
            f"✅ تم شحن حسابك في الموقع بنجاح!\n\n"
            f"💰 المبلغ المشحون: {amount} NSP\n"
            f"🆕 رصيدك الجديد في الموقع: {new_balances[1]} NSP\n"
            f"🔄 رصيدك المتبقي في البوت: {new_balances[0]} ل.س"
        )
        
        receipt = log_transaction(uid, "ichancy_charge", amount, "internal", "success")
        process_referral_charge(uid, amount, receipt)
        
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
        
        cursor.execute("UPDATE users SET site_balance = site_balance - ?, balance = balance + ? WHERE user_id=?", 
                      (amount, amount, uid))
        conn.commit()
        
        cursor.execute("SELECT balance, site_balance FROM users WHERE user_id=?", (uid,))
        new_balances = cursor.fetchone()
        
        bot.send_message(
            uid, 
            f"✅ تم سحب رصيدك من الموقع إلى البوت بنجاح!\n\n"
            f"💰 المبلغ المسحوب: {amount} NSP\n"
            f"🆕 رصيدك الجديد في الموقع: {new_balances[1]} NSP\n"
            f"💰 رصيدك الجديد في البوت: {new_balances[0]} ل.س"
        )
        
        log_transaction(uid, "ichancy_withdraw", amount, "internal", "success")
        
    except ValueError:
        bot.send_message(uid, "❌ الرجاء إدخال رقم صحيح")

def process_delete_account(message):
    uid = message.from_user.id
    if message.text == 'حذف':
        cursor.execute("SELECT acc_name, acc_password, site_balance, balance FROM users WHERE user_id=?", (uid,))
        user_data = cursor.fetchone()
        
        if user_data and user_data[0]:
            deleted_at = datetime.now().strftime("%d-%m-%Y %H:%M")
            cursor.execute("""INSERT OR REPLACE INTO deleted_accounts 
                (user_id, acc_name, acc_password, site_balance, balance, deleted_at) 
                VALUES (?,?,?,?,?,?)""",
                (uid, user_data[0], user_data[1], user_data[2], user_data[3], deleted_at))
            
            cursor.execute("UPDATE users SET acc_name=NULL, acc_password=NULL, site_balance=0, deleted=1 WHERE user_id=?", (uid,))
            conn.commit()
            
            bot.send_message(uid, "✅ تم حذف حسابك بنجاح", reply_markup=get_main_keyboard(uid))
            log_transaction(uid, "delete_account", 0, "system", "success")
        else:
            bot.send_message(uid, "❌ لا يوجد حساب لحذفه", reply_markup=get_main_keyboard(uid))
    else:
        bot.send_message(uid, "❌ لم تؤكد الحذف بشكل صحيح", reply_markup=get_ichancy_main_keyboard())

# ==========================================
# 9. نظام اهداء رصيد
# ==========================================
def process_gift_user_id(message):
    uid = message.from_user.id
    if message.text in ['🔙 العودة للقائمة الرئيسية', '/start']:
        handle_start(message)
        return
    
    try:
        target_id = int(message.text)
        
        cursor.execute("SELECT user_id FROM users WHERE user_id=? AND deleted=0", (target_id,))
        if not cursor.fetchone():
            bot.send_message(uid, "❌ المستخدم غير موجود أو لم يسجل في البوت بعد")
            msg = bot.send_message(uid, "👤 أرسل معرف المستخدم (ID) الذي تريد إهداءه:")
            bot.register_next_step_handler(msg, process_gift_user_id)
            return
        
        if target_id == uid:
            bot.send_message(uid, "❌ لا يمكنك إهداء نفسك")
            msg = bot.send_message(uid, "👤 أرسل معرف المستخدم (ID) الذي تريد إهداءه:")
            bot.register_next_step_handler(msg, process_gift_user_id)
            return
        
        msg = bot.send_message(uid, "💰 أرسل المبلغ الذي تريد إهداءه:")
        bot.register_next_step_handler(msg, process_gift_amount, target_id)
        
    except ValueError:
        bot.send_message(uid, "❌ معرف المستخدم غير صحيح")
        msg = bot.send_message(uid, "👤 أرسل معرف المستخدم (ID) الذي تريد إهداءه:")
        bot.register_next_step_handler(msg, process_gift_user_id)

def process_gift_amount(message, target_id):
    uid = message.from_user.id
    if message.text in ['🔙 العودة للقائمة الرئيسية', '/start']:
        handle_start(message)
        return
    
    try:
        amount = float(message.text)
        
        if amount <= 0:
            bot.send_message(uid, "❌ المبلغ يجب أن يكون أكبر من صفر")
            return
        
        cursor.execute("SELECT balance FROM users WHERE user_id=?", (uid,))
        sender_balance = cursor.fetchone()
        
        if not sender_balance or sender_balance[0] < amount:
            bot.send_message(uid, f"❌ رصيدك غير كافٍ. رصيدك الحالي: {sender_balance[0] if sender_balance else 0} ل.س")
            return
        
        cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id=?", (amount, uid))
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount, target_id))
        conn.commit()
        
        cursor.execute("SELECT balance FROM users WHERE user_id=?", (uid,))
        new_sender_balance = cursor.fetchone()[0]
        
        cursor.execute("SELECT balance FROM users WHERE user_id=?", (target_id,))
        new_target_balance = cursor.fetchone()[0]
        
        bot.send_message(
            uid, 
            f"✅ تم إرسال {amount} ل.س إلى المستخدم {target_id}\n"
            f"💰 رصيدك الجديد: {new_sender_balance} ل.س"
        )
        
        sender_name = get_user_custom_name(uid) or f"المستخدم {uid}"
        bot.send_message(
            target_id,
            f"🎁 لقد أهداك {sender_name} مبلغ {amount} ل.س\n"
            f"💰 رصيدك الجديد: {new_target_balance} ل.س"
        )
        
        log_transaction(uid, "gift", amount, "internal", "success", 
                       details=f"To: {target_id}")
        
    except ValueError:
        bot.send_message(uid, "❌ الرجاء إدخال رقم صحيح")

# ==========================================
# 10. عمليات الشحن الخارجي
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
        
        mark_transaction_processed(receipt, uid, amount)
        new_balance = update_user_balance(uid, amount, add=True)
        
        transaction_id = log_transaction(uid, "charge", amount, method, "success", details=receipt)
        referrer_id, earning = process_referral_charge(uid, amount, transaction_id)
        
        admin_msg = (
            f"💰 طلب شحن جديد\n"
            f"👤 المستخدم: {uid}\n"
            f"💵 المبلغ: {amount} ل.س\n"
            f"📱 الطريقة: {method}\n"
            f"🔢 رقم العملية: {receipt}"
        )
        
        if referrer_id:
            admin_msg += f"\n👥 إحالة لـ: {referrer_id} | الأرباح: {earning} ل.س"
        
        bot.send_message(ADMIN_ID, admin_msg)
        
        cursor.execute("SELECT user_id FROM moderators")
        for mod in cursor.fetchall():
            if mod[0] != ADMIN_ID:
                try:
                    bot.send_message(mod[0], admin_msg)
                except:
                    pass
        
        bot.send_message(
            uid, 
            f"✅ تم شحن رصيدك بنجاح!\n"
            f"💰 المبلغ: {amount} ل.س\n"
            f"🆕 رصيدك الجديد: {new_balance} ل.س"
        )
        
    except ValueError:
        bot.send_message(uid, "❌ الرجاء إدخال رقم صحيح")

# ==========================================
# 11. عمليات السحب الخارجي
# ==========================================
@bot.callback_query_handler(func=lambda call: call.data.startswith('withdraw_'))
def handle_withdraw_methods(call):
    uid = call.from_user.id
    method = call.data.replace('withdraw_', '')
    
    if method == 'syria':
        msg = bot.send_message(call.message.chat.id, "💰 الرجاء إدخال قيمة المبلغ المراد سحبه:")
        bot.register_next_step_handler(msg, process_withdraw_amount, "syriatel")
    
    elif method == 'sham':
        bot.send_message(call.message.chat.id, "اختر عملة السحب:", reply_markup=get_withdraw_currency_keyboard())

@bot.callback_query_handler(func=lambda call: call.data in ['withdraw_sham_lyr', 'withdraw_sham_usd'])
def handle_sham_currency(call):
    uid = call.from_user.id
    
    if call.data == 'withdraw_sham_usd':
        bot.send_message(call.message.chat.id, "⛔ عذراً، السحب بالدولار عبر شام كاش متوقف حالياً.")
        return
    
    msg = bot.send_message(call.message.chat.id, "💰 الرجاء إدخال قيمة المبلغ المراد سحبه (بالليرة السورية):")
    bot.register_next_step_handler(msg, process_withdraw_amount, "sham")

def process_withdraw_amount(message, method):
    uid = message.from_user.id
    if message.text in ['🔙 العودة للقائمة الرئيسية', '/start']:
        handle_start(message)
        return
    
    try:
        amount = float(message.text)
        
        if method == "syriatel":
            min_amount = float(get_db_setting('min_withdraw_syria'))
            max_amount = float(get_db_setting('max_withdraw_syria'))
        else:
            min_amount = float(get_db_setting('min_withdraw_sham'))
            max_amount = float(get_db_setting('max_withdraw_sham'))
        
        if amount < min_amount:
            bot.send_message(uid, f"❌ عذراً، أقل مبلغ للسحب هو {min_amount:,.0f} ل.س")
            return
        
        if amount > max_amount:
            bot.send_message(uid, f"❌ عذراً، أعلى مبلغ للسحب هو {max_amount:,.0f} ل.س")
            return
        
        cursor.execute("SELECT balance FROM users WHERE user_id=?", (uid,))
        user_balance = cursor.fetchone()
        
        if not user_balance or user_balance[0] < amount:
            bot.send_message(uid, f"❌ رصيدك غير كافٍ. رصيدك الحالي: {user_balance[0] if user_balance else 0} ل.س")
            return
        
        if method == "syriatel":
            msg_text = "📱 الرجاء إدخال رقم سيرياتل كاش الذي تريد سحب الأرباح إليه:"
        else:
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
    
    commission_rate = float(get_db_setting('withdraw_commission'))
    commission = amount * commission_rate / 100
    net_amount = amount - commission
    
    details = (
        f"📊 تفاصيل عملية السحب:\n\n"
        f"💵 المبلغ المطلوب: {amount:,.0f} ل.س\n"
        f"💸 نسبة العمولة ({commission_rate}%): {commission:,.0f} ل.س\n"
        f"✅ المبلغ الصافي المستلم: {net_amount:,.0f} ل.س\n\n"
        f"هل أنت موافق على العملية؟"
    )
    
    bot.register_next_step_handler_by_chat_id(uid, lambda m: None)
    bot.send_message(uid, details, reply_markup=get_confirmation_keyboard())
    
    
    withdraw_sessions[uid] = {
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
    
    if uid not in withdraw_sessions:
        bot.send_message(uid, "❌ حدث خطأ، الرجاء المحاولة من جديد")
        return
    
    data = withdraw_sessions[uid]
    
    try:
        update_user_balance(uid, data['amount'], add=False)
        update_cashier_balance(data['amount'], add=True)
        
        receipt = generate_receipt_number("WTH")
        
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
        
        cursor.execute("SELECT user_id FROM moderators")
        for mod in cursor.fetchall():
            if mod[0] != ADMIN_ID:
                try:
                    bot.send_message(mod[0], admin_msg)
                except:
                    pass
        
        log_transaction(
            uid, "withdraw_request", data['amount'], data['method'], "pending",
            commission=data['commission'], net_amount=data['net_amount'],
            details=f"Account: {data['account']}, Receipt: {receipt}"
        )
        
        del withdraw_sessions[uid]
        
    except Exception as e:
        bot.send_message(uid, f"❌ حدث خطأ: {e}")
        bot.send_message(ADMIN_ID, f"⚠️ خطأ في عملية السحب: {e}")

# ==========================================
# 12. نظام أكواد الهدايا
# ==========================================
@bot.callback_query_handler(func=lambda call: call.data.startswith('gift_') and call.from_user.id == ADMIN_ID)
def admin_create_gift(call):
    gift_type = call.data.replace('gift_', '')
    
    if gift_type == 'individual':
        msg = bot.send_message(call.message.chat.id, "💰 أدخل قيمة الكود (بالليرة السورية):")
        bot.register_next_step_handler(msg, process_individual_gift)
    else:
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
    
    cursor.execute("""SELECT value, limit_count, used_count, type FROM gifts WHERE code=?""", (code,))
    gift = cursor.fetchone()
    
    if not gift:
        bot.send_message(uid, "❌ الكود غير صحيح")
        return
    
    cursor.execute("SELECT * FROM gift_usage WHERE user_id=? AND code=?", (uid, code))
    if cursor.fetchone():
        bot.send_message(uid, "❌ لقد استخدمت هذا الكود من قبل")
        return
    
    if gift[2] <= gift[1]:
        bot.send_message(uid, "❌ عذراً، تم استخدام الكود للعدد المحدد")
        return
    
    update_user_balance(uid, gift[0], add=True)
    cursor.execute("UPDATE gifts SET used_count = used_count + 1 WHERE code=?", (code,))
    cursor.execute("""INSERT INTO gift_usage (user_id, code, used_at) 
        VALUES (?,?,?)""", (uid, code, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    
    bot.send_message(uid, f"🎉 تم شحن {gift[0]} ل.س إلى رصيدك في البوت!")
    log_transaction(uid, "gift_redeem", gift[0], "gift", "success", details=f"Code: {code}")

# ==========================================
# 13. نظام التواصل مع الدعم
# ==========================================
def process_support_ticket(message):
    uid = message.from_user.id
    
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
    
    cursor.execute("""INSERT INTO ticket_conversations 
        (ticket_id, sender_id, sender_type, message, file_id, sent_at)
        VALUES (?,?,?,?,?,?)""",
        (ticket_id, uid, 'user', message.text or "[صورة]", file_id,
         datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    
    bot.send_message(uid, "✅ تم إرسال رسالتك، سيتم الرد عليك بأقرب وقت ممكن.")
    
    user_info = f"@{message.from_user.username}" if message.from_user.username else f"ID: {uid}"
    user_custom_name = get_user_custom_name(uid)
    if user_custom_name:
        user_info += f" | {user_custom_name}"
    
    admin_msg = (
        f"💬 تذكرة دعم جديدة #{ticket_id}\n"
        f"👤 المستخدم: {user_info}\n"
        f"📝 الرسالة: {message.text or '[صورة]'}\n"
        f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )
    
    if file_id:
        bot.send_photo(ADMIN_ID, file_id, caption=admin_msg, reply_markup=get_reply_keyboard_for_ticket(ticket_id, uid))
    else:
        bot.send_message(ADMIN_ID, admin_msg, reply_markup=get_reply_keyboard_for_ticket(ticket_id, uid))
    
    cursor.execute("SELECT user_id FROM moderators WHERE can_reply=1")
    for mod in cursor.fetchall():
        if mod[0] != ADMIN_ID:
            try:
                if file_id:
                    bot.send_photo(mod[0], file_id, caption=admin_msg, reply_markup=get_reply_keyboard_for_ticket(ticket_id, uid))
                else:
                    bot.send_message(mod[0], admin_msg, reply_markup=get_reply_keyboard_for_ticket(ticket_id, uid))
            except:
                pass

@bot.callback_query_handler(func=lambda call: call.data.startswith('reply_ticket_'))
def handle_reply_ticket(call):
    if call.from_user.id != ADMIN_ID and not is_moderator(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ لا تملك صلاحية الرد", show_alert=True)
        return
    
    parts = call.data.split('_')
    ticket_id = int(parts[2])
    user_id = int(parts[3])
    
    cursor.execute("SELECT last_reply_by FROM tickets WHERE ticket_id=?", (ticket_id,))
    ticket = cursor.fetchone()
    
    if ticket and ticket[0]:
        last_replier = ticket[0]
        replier_name = "المالك" if last_replier == ADMIN_ID else get_moderator_name(last_replier)
        
        if last_replier != call.from_user.id and call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, f"❌ تم الرد على هذه الرسالة من قبل {replier_name}", show_alert=True)
            return
    
    bot.delete_message(call.message.chat.id, call.message.message_id)
    
    msg = bot.send_message(call.from_user.id, f"✏️ اكتب ردك للمستخدم {user_id}:")
    bot.register_next_step_handler(msg, process_ticket_reply, ticket_id, user_id, call.from_user.id)

def process_ticket_reply(message, ticket_id, user_id, replier_id):
    if message.text in ['🔙 العودة للقائمة الرئيسية', '/start']:
        handle_start(message)
        return
    
    cursor.execute("""UPDATE tickets SET status='closed', last_reply_by=?, last_reply_at=?
                      WHERE ticket_id=?""", 
                  (replier_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), ticket_id))
    
    cursor.execute("""INSERT INTO ticket_conversations 
        (ticket_id, sender_id, sender_type, message, sent_at)
        VALUES (?,?,?,?,?)""",
        (ticket_id, replier_id, 'admin' if replier_id == ADMIN_ID else 'moderator', 
         message.text, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    
    replier_name = "الإدارة" if replier_id == ADMIN_ID else "الدعم الفني"
    bot.send_message(user_id, f"📨 رد من {replier_name}:\n\n{message.text}")
    
    bot.send_message(replier_id, f"✅ تم إرسال ردك للمستخدم {user_id}")
    
    if replier_id != ADMIN_ID:
        bot.send_message(ADMIN_ID, f"ℹ️ تم الرد على المستخدم {user_id} من قبل {get_moderator_name(replier_id)}")
    
    cursor.execute("SELECT user_id FROM moderators WHERE can_reply=1 AND user_id != ?", (replier_id,))
    for mod in cursor.fetchall():
        if mod[0] != ADMIN_ID:
            try:
                bot.send_message(mod[0], f"ℹ️ تم الرد على المستخدم {user_id} من قبل {replier_name}")
            except:
                pass

def show_support_tickets(admin_id):
    cursor.execute("""SELECT ticket_id, user_id, message, status, created_at 
                      FROM tickets WHERE status='open' ORDER BY created_at DESC LIMIT 10""")
    tickets = cursor.fetchall()
    
    if not tickets:
        bot.send_message(admin_id, "📭 لا توجد تذاكر مفتوحة حالياً.")
        return
    
    msg = "📬 التذاكر المفتوحة:\n\n"
    for t in tickets:
        user_custom = get_user_custom_name(t[1])
        user_display = f"{t[1]} ({user_custom})" if user_custom else str(t[1])
        msg += f"#{t[0]} - المستخدم {user_display}\n{t[4]}\nرسالة: {t[2][:50]}...\n──────────\n"
    
    bot.send_message(admin_id, msg)

# ==========================================
# 14. نظام المشرفين
# ==========================================
def process_add_moderator(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        target_id = int(message.text)
        
        if target_id == ADMIN_ID:
            bot.send_message(ADMIN_ID, "❌ لا يمكن إضافة المالك كمشرف")
            return
        
        cursor.execute("SELECT user_id FROM moderators WHERE user_id=?", (target_id,))
        if cursor.fetchone():
            bot.send_message(ADMIN_ID, "❌ هذا المستخدم مشرف بالفعل")
            return
        
        cursor.execute("""INSERT INTO moderators 
            (user_id, added_by, added_at, can_reply, can_change_codes, can_view_transactions, can_maintenance, can_broadcast, can_rename_users)
            VALUES (?,?,?,1,1,1,1,1,1)""",
            (target_id, ADMIN_ID, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        
        bot.send_message(ADMIN_ID, f"✅ تمت إضافة المستخدم {target_id} كمشرف")
        bot.send_message(target_id, "🔓 تمت إضافتك كمشرف في بوت Matar. يمكنك الآن استخدام لوحة الإدارة.")
        
        bot.send_message(target_id, "🔓 لوحة التحكم الخاصة بالمشرف:", reply_markup=get_admin_main_keyboard(is_owner=False))
        
    except ValueError:
        bot.send_message(ADMIN_ID, "❌ معرف المستخدم غير صحيح")

def process_remove_moderator(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        target_id = int(message.text)
        
        cursor.execute("DELETE FROM moderators WHERE user_id=?", (target_id,))
        conn.commit()
        
        bot.send_message(ADMIN_ID, f"✅ تمت إزالة الاشراف من المستخدم {target_id}")
        bot.send_message(target_id, "🔴 تمت إزالتك من قائمة المشرفين في بوت Matar")
        
    except ValueError:
        bot.send_message(ADMIN_ID, "❌ معرف المستخدم غير صحيح")

def process_rename_moderator_step1(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        target_id = int(message.text)
        
        cursor.execute("SELECT user_id FROM moderators WHERE user_id=?", (target_id,))
        if not cursor.fetchone():
            bot.send_message(ADMIN_ID, "❌ هذا المستخدم ليس مشرفاً")
            return
        
        msg = bot.send_message(ADMIN_ID, f"✏️ أدخل الاسم الجديد للمشرف {target_id}:")
        bot.register_next_step_handler(msg, process_rename_moderator_step2, target_id)
        
    except ValueError:
        bot.send_message(ADMIN_ID, "❌ معرف المستخدم غير صحيح")

def process_rename_moderator_step2(message, target_id):
    if message.from_user.id != ADMIN_ID:
        return
    
    new_name = message.text
    
    cursor.execute("UPDATE moderators SET custom_name=? WHERE user_id=?", (new_name, target_id))
    conn.commit()
    
    bot.send_message(ADMIN_ID, f"✅ تمت إعادة تسمية المشرف {target_id} إلى: {new_name}")

def process_rename_user_step1(message):
    if message.from_user.id != ADMIN_ID and not is_moderator(message.from_user.id):
        return
    
    uid = message.from_user.id
    
    try:
        target_id = int(message.text)
        
        cursor.execute("SELECT user_id FROM users WHERE user_id=?", (target_id,))
        if not cursor.fetchone():
            bot.send_message(uid, "❌ المستخدم غير موجود")
            return
        
        msg = bot.send_message(uid, f"✏️ أدخل الاسم الجديد للمستخدم {target_id} (سيظهر للمشرفين فقط):")
        bot.register_next_step_handler(msg, process_rename_user_step2, target_id)
        
    except ValueError:
        bot.send_message(uid, "❌ معرف المستخدم غير صحيح")

def process_rename_user_step2(message, target_id):
    if message.from_user.id != ADMIN_ID and not is_moderator(message.from_user.id):
        return
    
    uid = message.from_user.id
    new_name = message.text
    
    cursor.execute("UPDATE users SET custom_name=? WHERE user_id=?", (new_name, target_id))
    conn.commit()
    
    bot.send_message(uid, f"✅ تمت إعادة تسمية المستخدم {target_id} إلى: {new_name}")

def show_moderators_list(admin_id):
    if admin_id != ADMIN_ID:
        return
    
    cursor.execute("""SELECT user_id, custom_name, added_at FROM moderators""")
    mods = cursor.fetchall()
    
    if not mods:
        bot.send_message(admin_id, "📭 لا يوجد مشرفين حالياً.")
        return
    
    msg = "👥 قائمة المشرفين:\n\n"
    for m in mods:
        name = m[1] if m[1] else "بدون اسم"
        msg += f"🆔 {m[0]} | {name}\n📅 أضيف: {m[2]}\n──────────\n"
    
    bot.send_message(admin_id, msg)

# ==========================================
# 15. نظام الإحالات للمالك
# ==========================================
@bot.message_handler(func=lambda m: m.text == '📊 تقارير الإحالات' and m.from_user.id == ADMIN_ID)
def show_referral_reports(m):
    uid = m.from_user.id
    
    cursor.execute("""SELECT user_id, first_name, username, referral_count, current_earnings, total_earnings 
                      FROM users WHERE referral_count > 0 ORDER BY current_earnings DESC""")
    referrers = cursor.fetchall()
    
    if not referrers:
        bot.send_message(uid, "📊 لا توجد إحالات نشطة حالياً.")
        return
    
    msg = "📊 تقارير الإحالات:\n\n"
    for r in referrers:
        user_display = f"@{r[2]}" if r[2] else f"ID: {r[0]}"
        custom_name = get_user_custom_name(r[0])
        if custom_name:
            user_display += f" ({custom_name})"
        
        msg += (
            f"👤 {user_display}\n"
            f"👥 الإحالات: {r[3]}\n"
            f"💰 أرباح الدورة: {r[4]} ل.س\n"
            f"📈 إجمالي الأرباح: {r[5]} ل.س\n"
            f"──────────\n"
        )
    
    next_payout = get_db_setting('next_referral_payout')
    time_left = format_time_remaining(next_payout) if next_payout else "غير محدد"
    
    msg += f"\n📅 الموعد القادم للتوزيع: {next_payout}\n⏳ {time_left}"
    
    bot.send_message(uid, msg)

@bot.message_handler(func=lambda m: m.text == '👥 قائمة المحيلين' and m.from_user.id == ADMIN_ID)
def show_referrers_list(m):
    uid = m.from_user.id
    
    cursor.execute("""SELECT user_id, first_name, username, referral_count 
                      FROM users WHERE referral_count > 0 ORDER BY referral_count DESC""")
    referrers = cursor.fetchall()
    
    if not referrers:
        bot.send_message(uid, "👥 لا يوجد محيلين حالياً.")
        return
    
    msg = "👥 قائمة المحيلين:\n\n"
    for r in referrers:
        user_display = f"@{r[2]}" if r[2] else f"ID: {r[0]}"
        custom_name = get_user_custom_name(r[0])
        if custom_name:
            user_display += f" ({custom_name})"
        
        msg += f"👤 {user_display}\n👥 الإحالات: {r[3]}\n──────────\n"
    
    bot.send_message(uid, msg)

@bot.message_handler(func=lambda m: m.text == '💰 الأرباح الحالية' and m.from_user.id == ADMIN_ID)
def show_current_earnings(m):
    uid = m.from_user.id
    
    cursor.execute("""SELECT user_id, first_name, username, current_earnings 
                      FROM users WHERE current_earnings > 0 ORDER BY current_earnings DESC""")
    earnings = cursor.fetchall()
    
    if not earnings:
        bot.send_message(uid, "💰 لا توجد أرباح حالية.")
        return
    
    msg = "💰 الأرباح الحالية (الدورة الحالية):\n\n"
    total = 0
    for e in earnings:
        user_display = f"@{e[2]}" if e[2] else f"ID: {e[0]}"
        custom_name = get_user_custom_name(e[0])
        if custom_name:
            user_display += f" ({custom_name})"
        
        msg += f"👤 {user_display}\n💰 {e[3]} ل.س\n──────────\n"
        total += e[3]
    
    msg += f"\n📊 إجمالي الأرباح الحالية: {total} ل.س"
    
    bot.send_message(uid, msg)

@bot.message_handler(func=lambda m: m.text == '📜 سجل الأرباح' and m.from_user.id == ADMIN_ID)
def show_earnings_history(m):
    uid = m.from_user.id
    
    cursor.execute("""SELECT referrer_id, amount, from_user_id, cycle_start, earned_at 
                      FROM referral_earnings ORDER BY earned_at DESC LIMIT 50""")
    earnings = cursor.fetchall()
    
    if not earnings:
        bot.send_message(uid, "📜 لا توجد أرباح سابقة.")
        return
    
    msg = "📜 سجل الأرباح (آخر 50):\n\n"
    for e in earnings:
        referrer_name = get_user_custom_name(e[0]) or f"ID {e[0]}"
        from_name = get_user_custom_name(e[2]) or f"ID {e[2]}"
        
        msg += (
            f"👤 {referrer_name}\n"
            f"💰 {e[1]} ل.س من {from_name}\n"
            f"📅 {e[4]}\n"
            f"──────────\n"
        )
    
    bot.send_message(uid, msg)

@bot.message_handler(func=lambda m: m.text == '🔄 تصفير الدورة' and m.from_user.id == ADMIN_ID)
def reset_referral_cycle(m):
    uid = m.from_user.id
    
    cursor.execute("UPDATE referral_cycles SET status='ended' WHERE status='active'")
    
    start = datetime.now()
    end = start + timedelta(days=10)
    cursor.execute("""INSERT INTO referral_cycles (start_date, end_date, status) 
                      VALUES (?,?,?)""", 
                  (start.strftime("%Y-%m-%d %H:%M:%S"), 
                   end.strftime("%Y-%m-%d %H:%M:%S"), 'active'))
    
    cursor.execute("UPDATE users SET current_earnings=0")
    
    update_db_setting('next_referral_payout', end.strftime("%Y-%m-%d %H:%M:%S"))
    
    conn.commit()
    
    bot.send_message(uid, f"✅ تم تصفير الدورة وبدء دورة جديدة تنتهي في {end.strftime('%Y-%m-%d %H:%M:%S')}")

@bot.message_handler(func=lambda m: m.text == '⚙️ تعديل النسبة' and m.from_user.id == ADMIN_ID)
def change_referral_percentage(m):
    uid = m.from_user.id
    
    current = get_db_setting('referral_percentage')
    msg = bot.send_message(uid, f"⚙️ النسبة الحالية: {current}%\nأدخل النسبة الجديدة:")
    bot.register_next_step_handler(msg, process_referral_percentage)

def process_referral_percentage(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        percentage = float(message.text)
        if percentage < 0 or percentage > 100:
            bot.send_message(ADMIN_ID, "❌ النسبة يجب أن تكون بين 0 و 100")
            return
        
        update_db_setting('referral_percentage', str(percentage))
        bot.send_message(ADMIN_ID, f"✅ تم تحديث النسبة إلى {percentage}%")
        
    except ValueError:
        bot.send_message(ADMIN_ID, "❌ قيمة غير صحيحة")

# ==========================================
# 16. الشروط والاحكام
# ==========================================
def show_terms_and_conditions(uid):
    terms_text = (
        "📜 الشروط والاحكام - بوت Matar\n\n"
        "1. الاشتراك في القناة شرط أساسي لاستخدام البوت.\n"
        "2. الحد الأدنى للشحن: 100 ل.س.\n"
        "3. الحد الأدنى للسحب عبر سيرياتل كاش: 25,000 ل.س (الحد الأقصى: 500,000 ل.س).\n"
        "4. الحد الأدنى للسحب عبر شام كاش: 25,000 ل.س (الحد الأقصى: 5,000,000 ل.س).\n"
        "5. عمولة السحب: 10% من قيمة المبلغ.\n"
        "6. مدة معالجة طلبات السحب: من ساعة إلى 24 ساعة.\n"
        "7. نظام الإحالات: نسبة 10% لكل عملية تعبئة يقوم بها المدعو.\n"
        "8. توزيع أرباح الإحالات كل 10 أيام.\n"
        "9. يحق للإدارة حظر أي مستخدم يخالف الشروط.\n"
        "10. في حالة وجود أي استفسار، يرجى التواصل مع الدعم الفني.\n\n"
        "نتمنى لك تجربة ممتعة مع بوت Matar 🌧️"
    )
    
    bot.send_message(uid, terms_text)

# ==========================================
# 17. أوامر الإدارة المساعدة
# ==========================================
def process_update_syriatel(message):
    if message.from_user.id != ADMIN_ID and not is_moderator(message.from_user.id):
        return
    
    uid = message.from_user.id
    new_numbers = message.text
    update_db_setting('syriatel_numbers', new_numbers, uid)
    
    bot.send_message(uid, f"✅ تم تحديث أرقام سيرياتل كاش إلى:\n{new_numbers}")
    
    if uid == ADMIN_ID:
        send_to_all_users(f"⚠️ الرجاء الانتباه: تم تغيير أرقام سيرياتل كاش إلى:\n{new_numbers}", exclude_admin=True, exclude_moderators=True)

def process_update_sham(message):
    if message.from_user.id != ADMIN_ID and not is_moderator(message.from_user.id):
        return
    
    uid = message.from_user.id
    new_address = message.text
    update_db_setting('sham_address', new_address, uid)
    
    bot.send_message(uid, f"✅ تم تحديث عنوان شام كاش إلى:\n{new_address}")
    
    if uid == ADMIN_ID:
        send_to_all_users(f"⚠️ الرجاء الانتباه: تم تغيير عنوان شام كاش إلى:\n{new_address}", exclude_admin=True, exclude_moderators=True)

def process_broadcast(message):
    if message.from_user.id != ADMIN_ID and not is_moderator(message.from_user.id):
        return
    
    uid = message.from_user.id
    sent = send_to_all_users(message.text, exclude_admin=(uid != ADMIN_ID), exclude_moderators=(uid != ADMIN_ID))
    bot.send_message(uid, f"✅ تم إرسال الرسالة لـ {sent} مستخدم.")

def process_private_message_user(message):
    if message.from_user.id != ADMIN_ID and not is_moderator(message.from_user.id):
        return
    
    uid = message.from_user.id
    
    try:
        target_id = int(message.text)
        msg = bot.send_message(uid, f"📝 أرسل الرسالة للمستخدم {target_id}:")
        bot.register_next_step_handler(msg, process_private_message_text, target_id)
    except ValueError:
        bot.send_message(uid, "❌ معرف المستخدم غير صحيح")

def process_private_message_text(message, target_id):
    if message.from_user.id != ADMIN_ID and not is_moderator(message.from_user.id):
        return
    
    uid = message.from_user.id
    
    try:
        bot.send_message(target_id, f"📨 رسالة من الإدارة:\n\n{message.text}")
        bot.send_message(uid, f"✅ تم إرسال الرسالة للمستخدم {target_id}")
    except Exception as e:
        bot.send_message(uid, f"❌ فشل الإرسال: {e}")

def show_transactions_log(admin_id):
    cursor.execute("""SELECT id, user_id, type, amount, method, status, transaction_date 
                      FROM transactions ORDER BY id DESC LIMIT 20""")
    transactions = cursor.fetchall()
    
    if not transactions:
        bot.send_message(admin_id, "📊 لا توجد معاملات بعد.")
        return
    
    msg = "📊 آخر 20 معاملة:\n\n"
    for t in transactions:
        user_custom = get_user_custom_name(t[1])
        user_display = f"{t[1]} ({user_custom})" if user_custom else str(t[1])
        msg += f"#{t[0]} | 👤 {user_display} | {t[2]}\n💰 {t[3]} | 📱 {t[4]} | {t[5]}\n{t[6]}\n──────────\n"
    
    bot.send_message(admin_id, msg)

def show_users_database(admin_id):
    cursor.execute("""SELECT COUNT(*), SUM(balance), SUM(site_balance) FROM users WHERE deleted=0""")
    stats = cursor.fetchone()
    
    cursor.execute("""SELECT user_id, first_name, username, acc_name, balance, status, custom_name
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
        custom = f" ({u[6]})" if u[6] else ""
        msg += f"🆔 {u[0]} | {u[1]}{custom} | @{u[2] if u[2] else '—'}\n💰 {u[4]} ل.س | {u[5]}\n"
    
    bot.send_message(admin_id, msg)

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

def process_restore_account(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        target_id = int(message.text)
        
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

# ==========================================
# 18. تشغيل البوت والحماية
# ==========================================
if __name__ == "__main__":
    keep_alive()
    print("🚀 Matar Bot Final Version is starting...")
    print(f"👤 Admin ID: {ADMIN_ID}")
    print("✅ Anti-Lag System Active")
    print("✅ Database Connected")
    print("✅ All Features Loaded")
    print("✅ Moderator System Active")
    print("✅ Referral System Active")
    print("✅ Smart Reply System Active")
    
    while True:
        try:
            bot.polling(none_stop=True, skip_pending=True, timeout=30)
        except Exception as e:
            print(f"⚠️ Polling error: {e}")
            time.sleep(5)
            continue
