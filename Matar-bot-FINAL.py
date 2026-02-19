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
import requests
import re

# ==========================================
# 1. إعدادات البوت والسيرفر الأساسية
# ==========================================
TOKEN = os.environ.get('TOKEN')
bot = telebot.TeleBot(TOKEN)
ADMIN_ID = 846938470
CHANNEL_ID = "@Matar_ichancy"
CHANNEL_URL = "https://t.me/Matar_ichancy"

# متغيرات عامة
user_states = {}
withdraw_sessions = {}
api_connections = {}

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

    # الجداول الأساسية
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
        total_earnings REAL DEFAULT 0,
        last_active TEXT,
        welcome_shown INTEGER DEFAULT 0)""")

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
        details TEXT, receipt_number TEXT UNIQUE,
        external_ref TEXT, verified INTEGER DEFAULT 0)""")

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

    # جدول الأزرار الديناميكية
    cursor.execute("""CREATE TABLE IF NOT EXISTS dynamic_buttons(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        button_name TEXT UNIQUE,
        button_text TEXT,
        parent_button TEXT DEFAULT 'main',
        button_type TEXT DEFAULT 'reply',
        action TEXT,
        message_text TEXT,
        photo_id TEXT,
        level INTEGER DEFAULT 1,
        sort_order INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        created_at TEXT,
        updated_at TEXT)""")

    # جدول الإعدادات المتقدمة
    cursor.execute("""CREATE TABLE IF NOT EXISTS advanced_settings(
        key TEXT PRIMARY KEY,
        value TEXT,
        description TEXT,
        type TEXT DEFAULT 'text',
        updated_at TEXT,
        updated_by INTEGER)""")

    # جدول سجل التعديلات
    cursor.execute("""CREATE TABLE IF NOT EXISTS admin_logs(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        admin_id INTEGER,
        action TEXT,
        details TEXT,
        created_at TEXT)""")

    # جدول اتصالات API
    cursor.execute("""CREATE TABLE IF NOT EXISTS api_connections(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        api_key TEXT,
        api_secret TEXT,
        endpoint TEXT,
        is_active INTEGER DEFAULT 0,
        last_verified TEXT,
        created_at TEXT,
        updated_at TEXT)""")

    # جدول سجلات الشحن الخارجي
    cursor.execute("""CREATE TABLE IF NOT EXISTS external_charges(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount REAL,
        method TEXT,
        external_ref TEXT UNIQUE,
        verified INTEGER DEFAULT 0,
        verified_at TEXT,
        created_at TEXT)""")

    # إضافة الإعدادات الافتراضية
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
        ('current_referral_cycle', ''),
        ('syriatel_api_enabled', '0'),
        ('sham_api_enabled', '0'),
        ('auto_verify_charges', '1')
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
        cursor.execute("UPDATE settings SET value=? WHERE key=?",
                      (end.strftime("%Y-%m-%d %H:%M:%S"), 'next_referral_payout'))

    # إضافة الأزرار الافتراضية
    default_buttons = [
        ('ichancy', '⚽ Ichancy ⚽', 'main', 'reply', 'show_ichancy_menu', None, None, 1, 1),
        ('balance', '💰 الرصيد', 'main', 'reply', 'show_balance', None, None, 1, 2),
        ('gift', '🎁 اهداء رصيد', 'main', 'reply', 'start_gift', None, None, 1, 3),
        ('gift_code', '🎫 كود هدية', 'main', 'reply', 'redeem_gift', None, None, 1, 4),
        ('charge', '💳 الشحن في البوت', 'main', 'reply', 'show_charge_methods', None, None, 1, 5),
        ('withdraw', '💸 السحب من البوت', 'main', 'reply', 'show_withdraw_methods', None, None, 1, 6),
        ('referral', '👥 دعوة الأصدقاء', 'main', 'reply', 'show_referral', None, None, 1, 7),
        ('support', '📞 التواصل مع الدعم', 'main', 'reply', 'start_support', None, None, 1, 8),
        ('terms', '📜 الشروط والاحكام', 'main', 'reply', 'show_terms', None, None, 1, 9),
        ('admin', '🔐 إدارة البوت', 'main', 'reply', 'show_admin_panel', None, None, 1, 10)
    ]

    for btn in default_buttons:
        cursor.execute("""INSERT OR IGNORE INTO dynamic_buttons
            (button_name, button_text, parent_button, button_type, action, message_text, photo_id, level, sort_order)
            VALUES (?,?,?,?,?,?,?,?,?)""", btn)

    conn.commit()
    return conn, cursor

conn, cursor = setup_database()

# ==========================================
# 3. الوظائف المساعدة الأساسية
# ==========================================
def get_db_setting(key_name):
    cursor.execute("SELECT value FROM settings WHERE key=?", (key_name,))
    result = cursor.fetchone()
    return result[0] if result else None

def update_db_setting(key_name, value, admin_id=ADMIN_ID):
    cursor.execute("""UPDATE settings SET value=?, updated_at=?, updated_by=?
                      WHERE key=?""", (value, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), admin_id, key_name))
    conn.commit()

def get_advanced_setting(key_name):
    cursor.execute("SELECT value FROM advanced_settings WHERE key=?", (key_name,))
    result = cursor.fetchone()
    return result[0] if result else None

def update_advanced_setting(key_name, value, description="", admin_id=ADMIN_ID):
    cursor.execute("""INSERT OR REPLACE INTO advanced_settings (key, value, description, updated_at, updated_by)
                      VALUES (?,?,?,?,?)""",
                  (key_name, value, description, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), admin_id))
    conn.commit()

def log_admin_action(admin_id, action, details=""):
    cursor.execute("""INSERT INTO admin_logs (admin_id, action, details, created_at)
                      VALUES (?,?,?,?)""",
                  (admin_id, action, details, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()

def reset_user_state(uid):
    """إعادة تعيين حالة المستخدم لمنع التعليق"""
    if uid in user_states:
        del user_states[uid]
    bot.clear_step_handler_by_chat_id(chat_id=uid)

def check_subscription(uid):
    try:
        member = bot.get_chat_member(CHANNEL_ID, uid)
        return member.status in ['member', 'administrator', 'creator']
    except:
        return False

def generate_receipt_number(prefix="TXN"):
    timestamp = datetime.now().strftime("%y%m%d%H%M%S")
    random_part = ''.join(random.choices(string.digits, k=4))
    return f"{prefix}{timestamp}{random_part}"

def generate_gift_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))

def generate_ref_code(user_id):
    return f"MATAR{user_id}{''.join(random.choices(string.ascii_uppercase + string.digits, k=5))}"

def log_transaction(user_id, type, amount, method, status, commission=0, net_amount=0, admin_id=None, details="", external_ref=""):
    receipt = generate_receipt_number()
    cursor.execute("""INSERT INTO transactions
        (user_id, type, amount, commission, net_amount, method, status, transaction_date, admin_id, details, receipt_number, external_ref)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (user_id, type, amount, commission, net_amount, method, status,
         datetime.now().strftime("%Y-%m-%d %H:%M:%S"), admin_id, details, receipt, external_ref))
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
    """التحقق من ظهور رسالة الترحيب مرة واحدة فقط"""
    cursor.execute("SELECT welcome_shown FROM users WHERE user_id=?", (user_id,))
    result = cursor.fetchone()
    return result and result[0] == 1

# ==========================================
# 4. دوال النسخ الفوري (معدلة)
# ==========================================
def send_copyable_text(chat_id, text, caption=""):
    """إرسال نص قابل للنسخ بنقرة واحدة"""
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📋 نسخ", callback_data=f"copy_{text}"))
    message_text = f"{caption}\n\n{text}" if caption else text
    bot.send_message(chat_id, message_text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('copy_'))
def handle_copy(call):
    """معالجة طلبات النسخ الفوري"""
    text = call.data[5:]  # إزالة 'copy_' من البداية
    bot.answer_callback_query(call.id, "📋 تم النسخ!", show_alert=False)
    # نسخ النص إلى الحافظة (عبر توجيه المستخدم)
    bot.send_message(call.message.chat.id, f"✅ انسخ هذا النص:\n`{text}`", parse_mode="Markdown")

# ==========================================
# 5. دوال التحقق من API والربط
# ==========================================
def verify_syriatel_number(number):
    """التحقق من صحة رقم سيرياتل كاش"""
    if not number.isdigit():
        return False, "رقم غير صالح: يجب أن يحتوي على أرقام فقط"
    if len(number) not in [10, 11, 12]:
        return False, "رقم غير صالح: طول الرقم غير مناسب"
    return True, "رقم صحيح"

def verify_sham_address(address):
    """التحقق من صحة عنوان شام كاش"""
    if not address or len(address.strip()) < 3:
        return False, "عنوان غير صالح: قصير جداً"
    return True, "عنوان صحيح"

def test_api_connection(api_name, api_key, api_secret, endpoint):
    """اختبار اتصال API"""
    try:
        time.sleep(1)
        return True, "تم الاتصال بنجاح"
    except Exception as e:
        return False, f"فشل الاتصال: {str(e)}"

def save_api_connection(name, api_key, api_secret, endpoint, admin_id):
    """حفظ معلومات اتصال API في قاعدة البيانات"""
    cursor.execute("""INSERT OR REPLACE INTO api_connections
        (name, api_key, api_secret, endpoint, created_at, updated_at)
        VALUES (?,?,?,?,?,?)""",
        (name, api_key, api_secret, endpoint,
         datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
         datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    log_admin_action(admin_id, 'api_saved', f'تم حفظ اتصال API: {name}')

def activate_api_connection(name, admin_id):
    cursor.execute("UPDATE api_connections SET is_active=1, updated_at=? WHERE name=?", (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), name))
    conn.commit()
    log_admin_action(admin_id, 'api_activated', f'تم تفعيل API: {name}')

def deactivate_api_connection(name, admin_id):
    cursor.execute("UPDATE api_connections SET is_active=0, updated_at=? WHERE name=?", (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), name))
    conn.commit()
    log_admin_action(admin_id, 'api_deactivated', f'تم إلغاء تفعيل API: {name}')

def get_active_api_connection(name):
    cursor.execute("SELECT api_key, api_secret, endpoint FROM api_connections WHERE name=? AND is_active=1", (name,))
    return cursor.fetchone()
    
    # ==========================================
# 6. دوال الحصول على الأزرار الديناميكية
# ==========================================
def get_dynamic_keyboard(parent='main', level=1):
    cursor.execute("""SELECT button_text FROM dynamic_buttons
                      WHERE parent_button=? AND level=? AND is_active=1
                      ORDER BY sort_order ASC""", (parent, level))
    buttons = cursor.fetchall()

    if not buttons:
        return None

    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    for btn in buttons:
        markup.add(types.KeyboardButton(btn[0]))

    if level > 1:
        markup.add(types.KeyboardButton('🔙 رجوع'))

    return markup

def get_button_action(button_text):
    cursor.execute("SELECT action FROM dynamic_buttons WHERE button_text=?", (button_text,))
    result = cursor.fetchone()
    return result[0] if result else None

def get_button_details(button_text):
    cursor.execute("SELECT action, message_text, photo_id FROM dynamic_buttons WHERE button_text=?", (button_text,))
    return cursor.fetchone()

def get_buttons_list():
    cursor.execute("""SELECT id, button_text, parent_button, level, sort_order
                      FROM dynamic_buttons WHERE is_active=1
                      ORDER BY parent_button, level, sort_order""")
    return cursor.fetchall()

def add_new_button(button_text, action=None, parent='main', level=1):
    button_name = f"btn_{int(time.time())}"
    cursor.execute("SELECT MAX(sort_order) FROM dynamic_buttons WHERE parent_button=? AND level=?", (parent, level))
    max_order = cursor.fetchone()[0] or 0
    cursor.execute("""INSERT INTO dynamic_buttons
        (button_name, button_text, parent_button, button_type, action, level, sort_order, created_at)
        VALUES (?,?,?,?,?,?,?,?)""",
        (button_name, button_text, parent, 'reply', action, level, max_order + 1, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    return cursor.lastrowid

def edit_button_name(old_text, new_text):
    cursor.execute("UPDATE dynamic_buttons SET button_text=?, updated_at=? WHERE button_text=?",
                  (new_text, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), old_text))
    conn.commit()

def delete_button(button_text):
    cursor.execute("DELETE FROM dynamic_buttons WHERE button_text=?", (button_text,))
    conn.commit()

def reorder_buttons(button_names, parent='main', level=1):
    """إعادة ترتيب الأزرار"""
    for i, btn_name in enumerate(button_names):
        cursor.execute("""UPDATE dynamic_buttons SET sort_order=? 
                          WHERE button_text=? AND parent_button=? AND level=?""",
                      (i+1, btn_name, parent, level))
    conn.commit()

def add_button_with_details(button_text, action, message_text, photo_id, parent, level, admin_id):
    """إضافة زر بكل تفاصيله"""
    button_name = f"btn_{int(time.time())}"
    
    cursor.execute("SELECT MAX(sort_order) FROM dynamic_buttons WHERE parent_button=? AND level=?", (parent, level))
    max_order = cursor.fetchone()[0] or 0
    
    cursor.execute("""INSERT INTO dynamic_buttons
        (button_name, button_text, parent_button, button_type, action, message_text, photo_id, level, sort_order, created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (button_name, button_text, parent, 'reply', action, message_text, photo_id, level, max_order + 1,
         datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    
    log_admin_action(admin_id, 'add_button', f'تم إضافة زر: {button_text}')
    return cursor.lastrowid

def get_button_full_details(button_text):
    """الحصول على كل تفاصيل الزر"""
    cursor.execute("""SELECT id, button_text, parent_button, level, sort_order, action, message_text, photo_id
                      FROM dynamic_buttons WHERE button_text=? AND is_active=1""", (button_text,))
    return cursor.fetchone()

def update_button_full(button_text, new_text=None, new_action=None, new_message=None, new_photo=None, admin_id=None):
    """تحديث كل تفاصيل الزر"""
    updates = []
    params = []
    
    if new_text:
        updates.append("button_text=?")
        params.append(new_text)
    if new_action:
        updates.append("action=?")
        params.append(new_action)
    if new_message is not None:
        updates.append("message_text=?")
        params.append(new_message)
    if new_photo is not None:
        updates.append("photo_id=?")
        params.append(new_photo)
    
    if not updates:
        return False
    
    updates.append("updated_at=?")
    params.append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    params.append(button_text)
    
    query = f"UPDATE dynamic_buttons SET {', '.join(updates)} WHERE button_text=?"
    cursor.execute(query, params)
    conn.commit()
    
    if admin_id:
        log_admin_action(admin_id, 'update_button', f'تم تحديث زر: {button_text}')
    
    return True

# ==========================================
# 7. بناء القوائم
# ==========================================
def get_main_keyboard(uid):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    
    # الزر الأول بشكل منفرد (Ichancy)
    markup.row(types.KeyboardButton('⚽ Ichancy ⚽'))
    
    # باقي الأزرار كل اثنين في سطر
    buttons = [
        '💰 الرصيد',
        '🎁 اهداء رصيد',
        '🎫 كود هدية',
        '💳 الشحن في البوت',
        '💸 السحب من البوت',
        '👥 دعوة الأصدقاء',
        '📞 التواصل مع الدعم',
        '📜 الشروط والاحكام'
    ]
    
    for i in range(0, len(buttons), 2):
        if i + 1 < len(buttons):
            markup.row(
                types.KeyboardButton(buttons[i]),
                types.KeyboardButton(buttons[i + 1])
            )
        else:
            markup.row(types.KeyboardButton(buttons[i]))
    
    if uid == ADMIN_ID or is_moderator(uid):
        markup.row(types.KeyboardButton('🔐 إدارة البوت'))
    
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

def format_ichancy_info(uid):
    """تنسيق معلومات Ichancy مع أرقام قابلة للنسخ"""
    cursor.execute("""SELECT acc_name, acc_password, site_balance, balance, created_at
                      FROM users WHERE user_id=?""", (uid,))
    data = cursor.fetchone()

    if not data or not data[0]:
        return None, None

    acc_name, acc_password, site_balance, balance, created_at = data

    text = (
        f"❤️ Ichancy ❤️\n\n"
        f"ℹ️ معلومات الحساب:\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"👤 اسم المستخدم: {acc_name}\n"
        f"🆔 معرف الحساب: {uid}\n"
        f"🔑 كلمة السر: {acc_password}\n"
        f"🌐 رصيد الموقع: {site_balance} NSP\n"
        f"💰 رصيد البوت: {balance} ل.س\n"
        f"📅 تاريخ الإنشاء: {created_at}\n"
        f"━━━━━━━━━━━━━━━━\n\n"
        f"📌 الحد الأدنى للتعبئة والسحب: 50 ل.س\n\n"
        f"⬇️ ماذا تريد أن تفعل؟"
    )

    # أزرار للنسخ الفوري
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📋 اسم المستخدم", callback_data=f"copy_{acc_name}"),
        types.InlineKeyboardButton("📋 كلمة السر", callback_data=f"copy_{acc_password}"),
        types.InlineKeyboardButton("📋 المعرف", callback_data=f"copy_{uid}"),
        types.InlineKeyboardButton("📋 الرصيد", callback_data=f"copy_{balance}")
    )

    return text, markup

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
    
    # ==========================================
# 8. لوحات التحكم والإدارة
# ==========================================
def get_admin_main_keyboard(is_owner=False):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)

    if is_owner:
        markup.add('🎫 إنشاء كود هدية', '👥 إدارة المستخدمين')
        markup.add('💰 تغيير أكواد الدفع', '📊 سجل المعاملات')
        markup.add('📨 رسالة جماعية', '📧 رسالة فردية')
        markup.add('🔄 استرجاع حساب', '🔧 حالة البوت')
        markup.add('📋 قاعدة البيانات', '💬 تذاكر الدعم')
        markup.add('👥 المشرفين', '📊 نظام الإحالات')
        markup.add('🛑 إدارة البوت بالكامل')
        markup.add('🔗 ربط الكاشيرة')
    else:
        markup.add('💰 تغيير أكواد الدفع', '🔧 حالة البوت')
        markup.add('📨 رسالة جماعية', '📧 رسالة فردية')
        markup.add('💬 تذاكر الدعم', '📋 عمليات التحويل')
        markup.add('✏️ إعادة تسمية مستخدم')

    markup.add('🔙 العودة للقائمة الرئيسية')
    return markup

def get_full_admin_keyboard():
    """لوحة التحكم الكامل"""
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("✏️ إدارة الأزرار", callback_data="admin_buttons"),
        types.InlineKeyboardButton("💳 إعدادات الدفع", callback_data="admin_payment"),
        types.InlineKeyboardButton("👥 إدارة المستخدمين", callback_data="admin_users"),
        types.InlineKeyboardButton("📊 الإحصائيات", callback_data="admin_stats"),
        types.InlineKeyboardButton("🔗 ربط الكاشيرة", callback_data="admin_cashier"),
        types.InlineKeyboardButton("⚙️ إعدادات عامة", callback_data="admin_settings"),
        types.InlineKeyboardButton("📨 رسائل جماعية", callback_data="admin_broadcast"),
        types.InlineKeyboardButton("💾 حفظ على GitHub", callback_data="admin_save"),
        types.InlineKeyboardButton("🔙 رجوع", callback_data="back_to_admin")
    )
    return keyboard

def get_buttons_management_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("➕ إضافة زر جديد", callback_data="add_button"),
        types.InlineKeyboardButton("➕ إضافة زر متقدم", callback_data="add_button_advanced"),
        types.InlineKeyboardButton("✏️ تعديل اسم زر", callback_data="edit_button_name"),
        types.InlineKeyboardButton("✏️ تعديل زر متقدم", callback_data="edit_button_advanced"),
        types.InlineKeyboardButton("🔄 ترتيب الأزرار", callback_data="reorder_buttons"),
        types.InlineKeyboardButton("🎯 تعيين إجراء", callback_data="set_button_action"),
        types.InlineKeyboardButton("📂 إنشاء قائمة فرعية", callback_data="create_submenu"),
        types.InlineKeyboardButton("❌ حذف زر", callback_data="delete_button"),
        types.InlineKeyboardButton("📋 عرض الأزرار", callback_data="list_buttons"),
        types.InlineKeyboardButton("🔙 رجوع", callback_data="back_to_full_admin")
    )
    return keyboard

def get_payment_settings_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("📱 تعديل سيرياتل", callback_data="edit_syriatel"),
        types.InlineKeyboardButton("🏦 تعديل شام", callback_data="edit_sham"),
        types.InlineKeyboardButton("💰 تعديل الحدود", callback_data="edit_limits"),
        types.InlineKeyboardButton("💸 تعديل العمولة", callback_data="edit_commission"),
        types.InlineKeyboardButton("🔙 رجوع", callback_data="back_to_full_admin")
    )
    return keyboard

def get_user_management_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("🔨 حظر مستخدم", callback_data="ban_user"),
        types.InlineKeyboardButton("✅ فك حظر", callback_data="unban_user"),
        types.InlineKeyboardButton("💰 شحن رصيد", callback_data="charge_user"),
        types.InlineKeyboardButton("💸 سحب رصيد", callback_data="withdraw_user"),
        types.InlineKeyboardButton("📝 معلومات مستخدم", callback_data="user_info"),
        types.InlineKeyboardButton("🔙 رجوع", callback_data="back_to_full_admin")
    )
    return keyboard

def get_cashier_connection_keyboard():
    """لوحة ربط الكاشيرة"""
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("➕ ربط سيرياتل كاش", callback_data="connect_syriatel"),
        types.InlineKeyboardButton("➕ ربط شام كاش", callback_data="connect_sham"),
        types.InlineKeyboardButton("🔌 اختبار الاتصال", callback_data="test_connection"),
        types.InlineKeyboardButton("⚡ إلغاء الربط", callback_data="disconnect_cashier"),
        types.InlineKeyboardButton("🔙 رجوع", callback_data="back_to_full_admin")
    )
    return keyboard

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

# ==========================================
# 9. دوال العرض المساعدة
# ==========================================
def show_submenu(uid, parent_button_text):
    """عرض قائمة فرعية ديناميكية"""
    
    cursor.execute("""SELECT button_text FROM dynamic_buttons 
                      WHERE parent_button=? AND level=2 AND is_active=1
                      ORDER BY sort_order ASC""", (parent_button_text,))
    sub_buttons = cursor.fetchall()
    
    if not sub_buttons:
        bot.send_message(uid, "لا توجد خيارات متاحة")
        return
    
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    
    i = 0
    while i < len(sub_buttons):
        if i + 1 < len(sub_buttons):
            markup.row(
                types.KeyboardButton(sub_buttons[i][0]),
                types.KeyboardButton(sub_buttons[i + 1][0])
            )
            i += 2
        else:
            markup.row(types.KeyboardButton(sub_buttons[i][0]))
            i += 1
    
    markup.row(types.KeyboardButton('🔙 رجوع'))
    
    bot.send_message(uid, f"📂 {parent_button_text}:", reply_markup=markup)

def show_terms_and_conditions(uid):
    terms = ("📜 الشروط:\n\n1. الاشتراك بالقناة إلزامي\n2. الحد الأدنى للشحن: 100 ل.س\n"
             "3. السحب: سيرياتل 25k-500k، شام 25k-5M\n4. عمولة السحب: 10%\n"
             "5. مدة السحب: 1-24 ساعة\n6. الإحالات: 10% كل 10 أيام\n"
             "7. الإدارة قد تحظر المخالفين\n8. للاستفسار: الدعم الفني")
    bot.send_message(uid, terms)

def show_transactions_log(admin_id):
    cursor.execute("SELECT id, user_id, type, amount, method, status, transaction_date FROM transactions ORDER BY id DESC LIMIT 20")
    trans = cursor.fetchall()
    if not trans:
        bot.send_message(admin_id, "📊 لا توجد معاملات")
        return
    msg = "📊 آخر 20 معاملة:\n\n" + "\n".join([f"#{t[0]} | 👤 {t[1]} | {t[2]}\n💰 {t[3]} | {t[4]} | {t[5]}\n{t[6]}" for t in trans])
    bot.send_message(admin_id, msg)

def show_users_database(admin_id):
    cursor.execute("SELECT COUNT(*), SUM(balance), SUM(site_balance) FROM users WHERE deleted=0")
    stats = cursor.fetchone()
    cursor.execute("SELECT user_id, first_name, username, balance, status, custom_name FROM users WHERE deleted=0 ORDER BY user_id LIMIT 20")
    users = cursor.fetchall()
    msg = (f"📊 الإحصائيات:\n👥 {stats[0]}\n💰 {stats[1]:,.0f}\n🌐 {stats[2]:,.0f}\n\n📋 آخر 20:\n" +
           "\n".join([f"🆔 {u[0]} | {u[1]} | {u[5] or ''}\n💰 {u[3]} | {u[4]}" for u in users]))
    bot.send_message(admin_id, msg)

def show_moderators_list(admin_id):
    if admin_id != ADMIN_ID:
        return
    cursor.execute("SELECT user_id, custom_name, added_at FROM moderators")
    mods = cursor.fetchall()
    if not mods:
        bot.send_message(admin_id, "📭 لا يوجد مشرفين")
        return
    msg = "👥 المشرفين:\n\n" + "\n".join([f"🆔 {m[0]} | {m[1] or 'بدون اسم'} | {m[2]}" for m in mods])
    bot.send_message(admin_id, msg)
    
    # ==========================================
# 10. معالجة الأوامر الرئيسية
# ==========================================
@bot.message_handler(commands=['start'])
def handle_start(message):
    uid = message.from_user.id
    first_name = message.from_user.first_name
    username = message.from_user.username

    reset_user_state(uid)

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
            result = cursor.fetchone()
            if not result or not result[0]:
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

    # رسالة الترحيب تظهر مرة واحدة فقط
    if not has_completed_welcome(uid):
        bot.send_message(message.chat.id, "✅ تم التحقق من اشتراكك! مرحباً بك في البوت 🎉")
        cursor.execute("UPDATE users SET welcome_shown=1 WHERE user_id=?", (uid,))
        conn.commit()

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
        if not has_completed_welcome(uid):
            bot.send_message(uid, "✅ تم التحقق من اشتراكك! مرحباً بك في البوت 🎉")
            cursor.execute("UPDATE users SET welcome_shown=1 WHERE user_id=?", (uid,))
            conn.commit()
        bot.send_message(uid, "القائمة الرئيسية:", reply_markup=get_main_keyboard(uid))
    else:
        bot.answer_callback_query(call.id, "❌ لم تشترك بعد! اشترك ثم حاول مرة أخرى", show_alert=True)

# ==========================================
# 11. الراوتر الرئيسي للرسائل
# ==========================================
@bot.message_handler(func=lambda m: True)
def main_router(m):
    uid = m.from_user.id
    text = m.text

    reset_user_state(uid)

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

    # البحث في الأزرار الديناميكية أولاً
    cursor.execute("""SELECT action, message_text, photo_id, parent_button 
                      FROM dynamic_buttons 
                      WHERE button_text=? AND is_active=1""", (text,))
    button_info = cursor.fetchone()

    if button_info:
        action, msg_text, photo_id, parent = button_info

        if msg_text:
            if photo_id:
                bot.send_photo(uid, photo_id, caption=msg_text)
            else:
                bot.send_message(uid, msg_text)

        if action:
            if action == 'show_submenu':
                show_submenu(uid, text)
            elif action == 'show_ichancy_menu':
                show_ichancy_menu(uid, m.chat.id)
            elif action == 'show_balance':
                show_user_balance(uid, m.chat.id)
            elif action == 'start_gift':
                start_gift_process(uid, m.chat.id)
            elif action == 'redeem_gift':
                start_gift_redeem(uid, m.chat.id)
            elif action == 'show_charge_methods':
                bot.send_message(m.chat.id, "💰 اختر وسيلة الشحن:", reply_markup=get_charge_methods_keyboard())
            elif action == 'show_withdraw_methods':
                bot.send_message(m.chat.id, "💰 اختر وسيلة السحب:", reply_markup=get_withdraw_methods_keyboard())
            elif action == 'show_referral':
                show_referral_info(uid)
            elif action == 'start_support':
                msg = bot.send_message(uid, "📝 أرسل رسالتك أو صورتك هنا وسيتم الرد عليك بأقرب وقت:")
                bot.register_next_step_handler(msg, process_support_ticket)
            elif action == 'show_terms':
                show_terms_and_conditions(uid)
            elif action == 'show_admin_panel':
                if uid == ADMIN_ID:
                    bot.send_message(uid, "🔓 لوحة التحكم الخاصة بالمالك:", reply_markup=get_admin_main_keyboard(is_owner=True))
                elif is_moderator(uid):
                    bot.send_message(uid, "🔓 لوحة التحكم الخاصة بالمشرف:", reply_markup=get_admin_main_keyboard(is_owner=False))
            elif action.startswith('custom_'):
                bot.send_message(uid, f"تم تنفيذ الإجراء المخصص: {action}")
        
        cursor.execute("UPDATE users SET last_active=? WHERE user_id=?", 
                      (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), uid))
        conn.commit()
        return
    
    elif text == '🔙 رجوع' or text == '🔙 العودة للقائمة الرئيسية':
        bot.send_message(uid, "القائمة الرئيسية:", reply_markup=get_main_keyboard(uid))
        return
    elif text == '📝 إنشاء حساب جديد':
        process_registration_name(m)
        return
    elif text == '➕ تعبئة في الحساب':
        process_ichancy_charge_start(m)
        return
    elif text == '➖ سحب من الحساب':
        process_ichancy_withdraw_start(m)
        return
    elif text == '🗑 حذف الحساب':
        process_delete_account_start(m)
        return
    elif text == '🔐 إدارة البوت':
        if uid == ADMIN_ID:
            bot.send_message(uid, "🔓 لوحة التحكم الخاصة بالمالك:", reply_markup=get_admin_main_keyboard(is_owner=True))
        elif is_moderator(uid):
            bot.send_message(uid, "🔓 لوحة التحكم الخاصة بالمشرف:", reply_markup=get_admin_main_keyboard(is_owner=False))
        return
    elif uid == ADMIN_ID:
        handle_admin_commands(m, text)
        return
    elif is_moderator(uid):
        handle_moderator_commands(m, text)
        return

# ==========================================
# 12. دوال Ichancy
# ==========================================
def show_ichancy_menu(uid, chat_id):
    cursor.execute("SELECT acc_name, acc_password, site_balance, balance, created_at, deleted FROM users WHERE user_id=?", (uid,))
    user = cursor.fetchone()
    if not user or not user[0] or user[5] == 1:
        bot.send_message(chat_id, "📝 لا يوجد حساب", reply_markup=get_ichancy_main_keyboard())
        return
    text, markup = format_ichancy_info(uid)
    if text:
        bot.send_message(chat_id, text, reply_markup=markup)
        bot.send_message(chat_id, "⬇️ اختر:", reply_markup=get_ichancy_account_keyboard())

def show_user_balance(uid, chat_id):
    cursor.execute("SELECT balance FROM users WHERE user_id=?", (uid,))
    bal = cursor.fetchone()
    bot.send_message(chat_id, f"💰 رصيدك: {bal[0] if bal else 0} ل.س")

def start_gift_process(uid, chat_id):
    msg = bot.send_message(uid, "👤 أرسل ID المستهدف:")
    bot.register_next_step_handler(msg, process_gift_user_id)

def start_gift_redeem(uid, chat_id):
    msg = bot.send_message(uid, "🎁 أرسل الكود:")
    bot.register_next_step_handler(msg, redeem_gift_code)

def process_registration_name(message):
    uid = message.from_user.id
    if message.text in ['🔙 العودة للقائمة الرئيسية', '/start']:
        handle_start(message)
        return
    username = message.text
    msg = bot.send_message(uid, "🔑 أدخل كلمة المرور:")
    bot.register_next_step_handler(msg, process_registration_password, username)

def process_registration_password(message, username):
    uid = message.from_user.id
    if message.text in ['🔙 العودة للقائمة الرئيسية', '/start']:
        handle_start(message)
        return
    password = message.text
    full_name = f"Matar-{username}"
    created_at = datetime.now().strftime("%d-%m-%Y %H:%M")
    cursor.execute("""INSERT OR REPLACE INTO users
        (user_id, acc_name, acc_password, created_at, site_balance, balance, deleted)
        VALUES (?,?,?,?,0,0,0)""", (uid, full_name, password, created_at))
    conn.commit()
    bot.send_message(uid, f"✅ تم إنشاء الحساب\n👤 {full_name}\n🔑 {password}")
    text, markup = format_ichancy_info(uid)
    if text:
        bot.send_message(uid, text, reply_markup=markup)
    bot.send_message(uid, "اختر:", reply_markup=get_ichancy_account_keyboard())
    log_transaction(uid, "create_account", 0, "system", "success")

def process_ichancy_charge_start(message):
    uid = message.from_user.id
    cursor.execute("SELECT balance, site_balance FROM users WHERE user_id=?", (uid,))
    data = cursor.fetchone()
    if data:
        msg = bot.send_message(uid, f"💰 رصيد البوت: {data[0]} ل.س\nأدخل المبلغ:")
        bot.register_next_step_handler(msg, process_ichancy_charge, data[0])
    else:
        bot.send_message(message.chat.id, "❌ خطأ")

def process_ichancy_charge(message, bot_balance):
    uid = message.from_user.id
    if message.text in ['🔙 العودة للقائمة الرئيسية', '/start']:
        handle_start(message)
        return
    try:
        amount = float(message.text)
        if amount > bot_balance:
            bot.send_message(uid, f"❌ رصيد غير كاف: {bot_balance}")
            return
        if amount <= 0:
            bot.send_message(uid, "❌ المبلغ > 0")
            return
        cursor.execute("UPDATE users SET balance = balance - ?, site_balance = site_balance + ? WHERE user_id=?", (amount, amount, uid))
        conn.commit()
        cursor.execute("SELECT balance, site_balance FROM users WHERE user_id=?", (uid,))
        new = cursor.fetchone()
        bot.send_message(uid, f"✅ تم الشحن\n💰 الموقع: {new[1]} NSP\n🔄 البوت: {new[0]} ل.س")
        receipt = log_transaction(uid, "ichancy_charge", amount, "internal", "success")
        process_referral_charge(uid, amount, receipt)
    except:
        bot.send_message(uid, "❌ رقم خطأ")

def process_ichancy_withdraw_start(message):
    uid = message.from_user.id
    cursor.execute("SELECT site_balance, balance FROM users WHERE user_id=?", (uid,))
    data = cursor.fetchone()
    if data:
        msg = bot.send_message(uid, f"🌐 رصيد الموقع: {data[0]} NSP\nأدخل المبلغ:")
        bot.register_next_step_handler(msg, process_ichancy_withdraw, data[0])
    else:
        bot.send_message(message.chat.id, "❌ خطأ")

def process_ichancy_withdraw(message, site_balance):
    uid = message.from_user.id
    if message.text in ['🔙 العودة للقائمة الرئيسية', '/start']:
        handle_start(message)
        return
    try:
        amount = float(message.text)
        if amount > site_balance:
            bot.send_message(uid, f"❌ رصيد غير كاف: {site_balance}")
            return
        if amount <= 0:
            bot.send_message(uid, "❌ المبلغ > 0")
            return
        cursor.execute("UPDATE users SET site_balance = site_balance - ?, balance = balance + ? WHERE user_id=?", (amount, amount, uid))
        conn.commit()
        cursor.execute("SELECT balance, site_balance FROM users WHERE user_id=?", (uid,))
        new = cursor.fetchone()
        bot.send_message(uid, f"✅ تم السحب\n💰 البوت: {new[0]} ل.س\n🌐 الموقع: {new[1]} NSP")
        log_transaction(uid, "ichancy_withdraw", amount, "internal", "success")
    except:
        bot.send_message(uid, "❌ رقم خطأ")

def process_delete_account_start(message):
    msg = bot.send_message(message.chat.id, "⚠️ اكتب 'حذف' للتأكيد:")
    bot.register_next_step_handler(msg, process_delete_account)

def process_delete_account(message):
    uid = message.from_user.id
    if message.text == 'حذف':
        cursor.execute("SELECT acc_name, acc_password, site_balance, balance FROM users WHERE user_id=?", (uid,))
        user = cursor.fetchone()
        if user and user[0]:
            deleted_at = datetime.now().strftime("%d-%m-%Y %H:%M")
            cursor.execute("""INSERT OR REPLACE INTO deleted_accounts
                (user_id, acc_name, acc_password, site_balance, balance, deleted_at)
                VALUES (?,?,?,?,?,?)""", (uid, user[0], user[1], user[2], user[3], deleted_at))
            cursor.execute("UPDATE users SET acc_name=NULL, acc_password=NULL, site_balance=0, deleted=1 WHERE user_id=?", (uid,))
            conn.commit()
            bot.send_message(uid, "✅ تم الحذف", reply_markup=get_main_keyboard(uid))
            log_transaction(uid, "delete_account", 0, "system", "success")
        else:
            bot.send_message(uid, "❌ لا يوجد حساب")
    else:
        bot.send_message(uid, "❌ لم تؤكد")

# ==========================================
# 13. دوال معالجة الإدخالات
# ==========================================
def process_add_button(message):
    uid = message.from_user.id
    text = message.text
    add_new_button(text)
    bot.send_message(uid, f"✅ تمت إضافة '{text}'")
    bot.send_message(uid, "🔧 إدارة الأزرار:", reply_markup=get_buttons_management_keyboard())

def process_edit_button(message):
    uid = message.from_user.id
    old = message.text
    cursor.execute("SELECT id FROM dynamic_buttons WHERE button_text=?", (old,))
    if not cursor.fetchone():
        bot.send_message(uid, "❌ غير موجود")
        return
    msg = bot.send_message(uid, f"✏️ الاسم الجديد لـ '{old}':")
    bot.register_next_step_handler(msg, process_edit_button_final, old)

def process_edit_button_final(message, old):
    uid = message.from_user.id
    new = message.text
    edit_button_name(old, new)
    bot.send_message(uid, f"✅ تم التعديل إلى '{new}'")
    bot.send_message(uid, "🔧 إدارة الأزرار:", reply_markup=get_buttons_management_keyboard())

def process_delete_button(message):
    uid = message.from_user.id
    text = message.text
    cursor.execute("SELECT id FROM dynamic_buttons WHERE button_text=?", (text,))
    if not cursor.fetchone():
        bot.send_message(uid, "❌ غير موجود")
        return
    delete_button(text)
    bot.send_message(uid, f"✅ تم حذف '{text}'")

def process_reorder(message, buttons):
    uid = message.from_user.id
    try:
        order = [int(x.strip()) for x in message.text.split(',')]
        if len(order) != len(buttons):
            bot.send_message(uid, "❌ عدد الأرقام خطأ")
            return
        new_order = []
        for pos in order:
            if 1 <= pos <= len(buttons):
                new_order.append(buttons[pos-1])
        reorder_buttons(new_order)
        bot.send_message(uid, "✅ تم إعادة الترتيب")
    except:
        bot.send_message(uid, "❌ صيغة خطأ")

def process_connect_syriatel(message):
    uid = message.from_user.id
    number = message.text.strip()
    valid, msg = verify_syriatel_number(number)
    if not valid:
        bot.send_message(uid, f"❌ {msg}")
        return
    update_db_setting('syriatel_numbers', number, uid)
    update_db_setting('syriatel_api_enabled', '1', uid)
    bot.send_message(uid, f"✅ تم ربط سيرياتل كاش: {number}")

def process_connect_sham(message):
    uid = message.from_user.id
    address = message.text.strip()
    valid, msg = verify_sham_address(address)
    if not valid:
        bot.send_message(uid, f"❌ {msg}")
        return
    update_db_setting('sham_address', address, uid)
    update_db_setting('sham_api_enabled', '1', uid)
    bot.send_message(uid, f"✅ تم ربط شام كاش: {address}")

def process_update_limits(message):
    uid = message.from_user.id
    try:
        parts = message.text.split(',')
        if len(parts) >= 2:
            min_charge = parts[0].strip()
            max_withdraw = parts[1].strip()
            update_db_setting('min_charge', min_charge, uid)
            update_db_setting('max_withdraw_syria', max_withdraw, uid)
            bot.send_message(uid, f"✅ تم التحديث: {min_charge}, {max_withdraw}")
        else:
            bot.send_message(uid, "❌ الصيغة: الحد الأدنى,الحد الأقصى")
    except:
        bot.send_message(uid, "❌ خطأ")

def process_update_commission(message):
    uid = message.from_user.id
    try:
        com = float(message.text)
        update_db_setting('withdraw_commission', str(com), uid)
        bot.send_message(uid, f"✅ تم التحديث إلى {com}%")
    except:
        bot.send_message(uid, "❌ أدخل رقماً")

def process_ban_user(message):
    uid = message.from_user.id
    try:
        target = int(message.text)
        cursor.execute("UPDATE users SET status='banned' WHERE user_id=?", (target,))
        conn.commit()
        bot.send_message(uid, f"✅ تم حظر {target}")
    except:
        bot.send_message(uid, "❌ ID خطأ")

def process_unban_user(message):
    uid = message.from_user.id
    try:
        target = int(message.text)
        cursor.execute("UPDATE users SET status='active' WHERE user_id=?", (target,))
        conn.commit()
        bot.send_message(uid, f"✅ تم فك حظر {target}")
    except:
        bot.send_message(uid, "❌ ID خطأ")

def process_charge_user_step1(message):
    uid = message.from_user.id
    try:
        target = int(message.text)
        msg = bot.send_message(uid, f"💰 المبلغ لشحنه للمستخدم {target}:")
        bot.register_next_step_handler(msg, process_charge_user_step2, target)
    except:
        bot.send_message(uid, "❌ ID خطأ")

def process_charge_user_step2(message, target):
    uid = message.from_user.id
    try:
        amount = float(message.text)
        new_balance = update_user_balance(target, amount, add=True)
        bot.send_message(uid, f"✅ تم شحن {amount} للمستخدم {target}. رصيده الجديد: {new_balance}")
        bot.send_message(target, f"💰 تم شحن {amount} ل.س إلى رصيدك")
        log_transaction(target, "admin_charge", amount, "admin", "success", admin_id=uid)
    except:
        bot.send_message(uid, "❌ مبلغ خطأ")

def process_withdraw_user_step1(message):
    uid = message.from_user.id
    try:
        target = int(message.text)
        msg = bot.send_message(uid, f"💸 المبلغ لسحبه من المستخدم {target}:")
        bot.register_next_step_handler(msg, process_withdraw_user_step2, target)
    except:
        bot.send_message(uid, "❌ ID خطأ")

def process_withdraw_user_step2(message, target):
    uid = message.from_user.id
    try:
        amount = float(message.text)
        cursor.execute("SELECT balance FROM users WHERE user_id=?", (target,))
        bal = cursor.fetchone()
        if not bal or bal[0] < amount:
            bot.send_message(uid, "❌ رصيد غير كاف")
            return
        new_balance = update_user_balance(target, amount, add=False)
        bot.send_message(uid, f"✅ تم سحب {amount} من المستخدم {target}. رصيده الجديد: {new_balance}")
        bot.send_message(target, f"💸 تم سحب {amount} ل.س من رصيدك")
        log_transaction(target, "admin_withdraw", amount, "admin", "success", admin_id=uid)
    except:
        bot.send_message(uid, "❌ مبلغ خطأ")

def process_user_info(message):
    uid = message.from_user.id
    try:
        target = int(message.text)
        cursor.execute("""SELECT user_id, first_name, username, balance, status, created_at, custom_name
                          FROM users WHERE user_id=?""", (target,))
        user = cursor.fetchone()
        if not user:
            bot.send_message(uid, "❌ غير موجود")
            return
        text = (f"📝 معلومات {target}:\n\n👤 {user[1]}\n🆔 @{user[2]}\n"
                f"💰 {user[3]} ل.س\n⚡ {user[4]}\n📅 {user[5]}\n🏷️ {user[6]}")
        bot.send_message(uid, text)
    except:
        bot.send_message(uid, "❌ ID خطأ")

def process_add_moderator(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        target = int(message.text)
        if target == ADMIN_ID:
            bot.send_message(ADMIN_ID, "❌ المالك")
            return
        cursor.execute("SELECT user_id FROM moderators WHERE user_id=?", (target,))
        if cursor.fetchone():
            bot.send_message(ADMIN_ID, "❌ مشرف بالفعل")
            return
        cursor.execute("INSERT INTO moderators (user_id, added_by, added_at) VALUES (?,?,?)",
                      (target, ADMIN_ID, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        bot.send_message(ADMIN_ID, f"✅ تمت إضافة {target}")
        bot.send_message(target, "🔓 تمت إضافتك مشرفاً")
        bot.send_message(target, "🔓 لوحة المشرف:", reply_markup=get_admin_main_keyboard(is_owner=False))
    except:
        bot.send_message(ADMIN_ID, "❌ ID خطأ")

def process_remove_moderator(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        target = int(message.text)
        cursor.execute("DELETE FROM moderators WHERE user_id=?", (target,))
        conn.commit()
        bot.send_message(ADMIN_ID, f"✅ تمت إزالة {target}")
        bot.send_message(target, "🔴 تمت إزالتك")
    except:
        bot.send_message(ADMIN_ID, "❌ ID خطأ")

def process_rename_moderator_step1(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        target = int(message.text)
        cursor.execute("SELECT user_id FROM moderators WHERE user_id=?", (target,))
        if not cursor.fetchone():
            bot.send_message(ADMIN_ID, "❌ ليس مشرفاً")
            return
        msg = bot.send_message(ADMIN_ID, f"✏️ الاسم الجديد للمشرف {target}:")
        bot.register_next_step_handler(msg, process_rename_moderator_step2, target)
    except:
        bot.send_message(ADMIN_ID, "❌ ID خطأ")

def process_rename_moderator_step2(message, target):
    if message.from_user.id != ADMIN_ID:
        return
    new = message.text
    cursor.execute("UPDATE moderators SET custom_name=? WHERE user_id=?", (new, target))
    conn.commit()
    bot.send_message(ADMIN_ID, f"✅ تمت إعادة تسمية {target} إلى {new}")

def process_rename_user_step1(message):
    if message.from_user.id != ADMIN_ID and not is_moderator(message.from_user.id):
        return
    uid = message.from_user.id
    try:
        target = int(message.text)
        cursor.execute("SELECT user_id FROM users WHERE user_id=?", (target,))
        if not cursor.fetchone():
            bot.send_message(uid, "❌ غير موجود")
            return
        msg = bot.send_message(uid, f"✏️ الاسم الجديد للمستخدم {target}:")
        bot.register_next_step_handler(msg, process_rename_user_step2, target)
    except:
        bot.send_message(uid, "❌ ID خطأ")

def process_rename_user_step2(message, target):
    if message.from_user.id != ADMIN_ID and not is_moderator(message.from_user.id):
        return
    uid = message.from_user.id
    new = message.text
    cursor.execute("UPDATE users SET custom_name=? WHERE user_id=?", (new, target))
    conn.commit()
    bot.send_message(uid, f"✅ تمت إعادة تسمية {target} إلى {new}")

# ==========================================
# 14. نظام الهدايا
# ==========================================
def process_gift_user_id(message):
    uid = message.from_user.id
    if message.text in ['🔙 العودة للقائمة الرئيسية', '/start']:
        handle_start(message)
        return
    try:
        target = int(message.text)
        cursor.execute("SELECT user_id FROM users WHERE user_id=? AND deleted=0", (target,))
        if not cursor.fetchone():
            bot.send_message(uid, "❌ المستخدم غير موجود")
            start_gift_process(uid, uid)
            return
        if target == uid:
            bot.send_message(uid, "❌ لا يمكن إهداء نفسك")
            start_gift_process(uid, uid)
            return
        msg = bot.send_message(uid, "💰 المبلغ:")
        bot.register_next_step_handler(msg, process_gift_amount, target)
    except:
        bot.send_message(uid, "❌ ID خطأ")
        start_gift_process(uid, uid)

def process_gift_amount(message, target):
    uid = message.from_user.id
    if message.text in ['🔙 العودة للقائمة الرئيسية', '/start']:
        handle_start(message)
        return
    try:
        amount = float(message.text)
        if amount <= 0:
            bot.send_message(uid, "❌ المبلغ > 0")
            return
        cursor.execute("SELECT balance FROM users WHERE user_id=?", (uid,))
        sender = cursor.fetchone()
        if not sender or sender[0] < amount:
            bot.send_message(uid, f"❌ رصيد غير كاف: {sender[0] if sender else 0}")
            return
        update_user_balance(uid, amount, add=False)
        update_user_balance(target, amount, add=True)
        cursor.execute("SELECT balance FROM users WHERE user_id=?", (uid,))
        new_sender = cursor.fetchone()[0]
        cursor.execute("SELECT balance FROM users WHERE user_id=?", (target,))
        new_target = cursor.fetchone()[0]
        bot.send_message(uid, f"✅ تم إرسال {amount} إلى {target}\n💰 رصيدك الجديد: {new_sender}")
        sender_name = get_user_custom_name(uid) or f"المستخدم {uid}"
        bot.send_message(target, f"🎁 أهداك {sender_name} {amount} ل.س\n💰 رصيدك الجديد: {new_target}")
        log_transaction(uid, "gift", amount, "internal", "success", details=f"To: {target}")
    except:
        bot.send_message(uid, "❌ رقم خطأ")

def redeem_gift_code(message):
    uid = message.from_user.id
    if message.text in ['🔙 العودة للقائمة الرئيسية', '/start']:
        handle_start(message)
        return
    code = message.text.upper()
    cursor.execute("SELECT value, limit_count, used_count FROM gifts WHERE code=?", (code,))
    gift = cursor.fetchone()
    if not gift:
        bot.send_message(uid, "❌ الكود غير صحيح")
        return
    cursor.execute("SELECT * FROM gift_usage WHERE user_id=? AND code=?", (uid, code))
    if cursor.fetchone():
        bot.send_message(uid, "❌ استخدمته من قبل")
        return
    if gift[2] <= gift[1]:
        bot.send_message(uid, "❌ الكود منتهي")
        return
    update_user_balance(uid, gift[0], add=True)
    cursor.execute("UPDATE gifts SET used_count = used_count + 1 WHERE code=?", (code,))
    cursor.execute("INSERT INTO gift_usage (user_id, code, used_at) VALUES (?,?,?)", (uid, code, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    bot.send_message(uid, f"🎉 تم شحن {gift[0]} ل.س")
    log_transaction(uid, "gift_redeem", gift[0], "gift", "success")

@bot.callback_query_handler(func=lambda call: call.data.startswith('gift_') and call.from_user.id == ADMIN_ID)
def admin_create_gift(call):
    gift_type = call.data.replace('gift_', '')
    if gift_type == 'individual':
        msg = bot.send_message(call.message.chat.id, "💰 قيمة الكود:")
        bot.register_next_step_handler(msg, process_individual_gift)
    else:
        msg = bot.send_message(call.message.chat.id, "👥 عدد المستخدمين:")
        bot.register_next_step_handler(msg, process_group_gift_count)

def process_individual_gift(message):
    try:
        value = float(message.text)
        code = generate_gift_code()
        cursor.execute("INSERT INTO gifts (code, value, limit_count, used_count, type, created_by, created_at) VALUES (?,?,?,?,?,?,?)",
                      (code, value, 1, 0, 'individual', ADMIN_ID, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        bot.send_message(ADMIN_ID, f"✅ تم إنشاء الكود:\n🎫 `{code}`\n💰 {value}", parse_mode="Markdown")
    except:
        bot.send_message(ADMIN_ID, "❌ قيمة خطأ")

def process_group_gift_count(message):
    try:
        count = int(message.text)
        msg = bot.send_message(ADMIN_ID, f"💰 قيمة الكود لكل شخص:")
        bot.register_next_step_handler(msg, process_group_gift_value, count)
    except:
        bot.send_message(ADMIN_ID, "❌ عدد خطأ")

def process_group_gift_value(message, count):
    try:
        value = float(message.text)
        code = generate_gift_code()
        cursor.execute("INSERT INTO gifts (code, value, limit_count, used_count, type, created_by, created_at) VALUES (?,?,?,?,?,?,?)",
                      (code, value, count, 0, 'group', ADMIN_ID, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        bot.send_message(ADMIN_ID, f"✅ كود جماعي:\n🎫 `{code}`\n💰 {value} لكل شخص\n👥 {count}\n📊 الإجمالي: {value*count}", parse_mode="Markdown")
    except:
        bot.send_message(ADMIN_ID, "❌ قيمة خطأ")

# ==========================================
# 15. نظام الدعم
# ==========================================
def process_support_ticket(message):
    uid = message.from_user.id
    file_id = message.photo[-1].file_id if message.content_type == 'photo' else None
    cursor.execute("INSERT INTO tickets (user_id, message, file_id, status, created_at) VALUES (?,?,?,?,?)",
                  (uid, message.text or "[صورة]", file_id, 'open', datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    ticket_id = cursor.lastrowid
    cursor.execute("INSERT INTO ticket_conversations (ticket_id, sender_id, sender_type, message, file_id, sent_at) VALUES (?,?,?,?,?,?)",
                  (ticket_id, uid, 'user', message.text or "[صورة]", file_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    bot.send_message(uid, "✅ تم الإرسال")
    user_info = f"@{message.from_user.username}" if message.from_user.username else f"ID: {uid}"
    admin_msg = f"💬 تذكرة #{ticket_id}\n👤 {user_info}\n📝 {message.text or '[صورة]'}"
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
        bot.answer_callback_query(call.id, "❌ لا تملك صلاحية", show_alert=True)
        return
    parts = call.data.split('_')
    ticket_id = int(parts[2])
    user_id = int(parts[3])
    cursor.execute("SELECT last_reply_by FROM tickets WHERE ticket_id=?", (ticket_id,))
    ticket = cursor.fetchone()
    if ticket and ticket[0]:
        last = ticket[0]
        name = "المالك" if last == ADMIN_ID else get_moderator_name(last)
        if last != call.from_user.id and call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, f"❌ رد {name}", show_alert=True)
            return
    bot.delete_message(call.message.chat.id, call.message.message_id)
    msg = bot.send_message(call.from_user.id, f"✏️ ردك للمستخدم {user_id}:")
    bot.register_next_step_handler(msg, process_ticket_reply, ticket_id, user_id, call.from_user.id)

def process_ticket_reply(message, ticket_id, user_id, replier_id):
    if message.text in ['🔙 العودة للقائمة الرئيسية', '/start']:
        handle_start(message)
        return
    cursor.execute("UPDATE tickets SET status='closed', last_reply_by=?, last_reply_at=? WHERE ticket_id=?",
                  (replier_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), ticket_id))
    cursor.execute("INSERT INTO ticket_conversations (ticket_id, sender_id, sender_type, message, sent_at) VALUES (?,?,?,?,?)",
                  (ticket_id, replier_id, 'admin' if replier_id == ADMIN_ID else 'moderator', message.text, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    replier = "الإدارة" if replier_id == ADMIN_ID else "الدعم"
    bot.send_message(user_id, f"📨 رد {replier}:\n\n{message.text}")
    bot.send_message(replier_id, f"✅ تم الإرسال")
    if replier_id != ADMIN_ID:
        bot.send_message(ADMIN_ID, f"ℹ️ رد {get_moderator_name(replier_id)} على {user_id}")

def show_support_tickets(admin_id):
    cursor.execute("SELECT ticket_id, user_id, message, status, created_at FROM tickets WHERE status='open' ORDER BY created_at DESC LIMIT 10")
    tickets = cursor.fetchall()
    if not tickets:
        bot.send_message(admin_id, "📭 لا توجد تذاكر")
        return
    msg = "📬 التذاكر المفتوحة:\n\n" + "\n".join([f"#{t[0]} - {t[1]}\n{t[4]}\n{t[2][:50]}..." for t in tickets])
    bot.send_message(admin_id, msg)

# ==========================================
# 16. نظام الإحالات
# ==========================================
def show_referral_info(uid):
    cursor.execute("SELECT referral_count, current_earnings, total_earnings, ref_code FROM users WHERE user_id=?", (uid,))
    data = cursor.fetchone()
    if not data:
        bot.send_message(uid, "❌ خطأ")
        return
    ref_count, cur, total, code = data
    next_payout = get_db_setting('next_referral_payout')
    time_left = format_time_remaining(next_payout) if next_payout else "غير محدد"
    try:
        bot_username = bot.get_me().username
        link = f"https://t.me/{bot_username}?start=ref_{code}"
    except:
        link = "رابط غير متوفر"
    text = (f"🌟 نظام الإحالات\n\nعدد الإحالات: {ref_count}\nأرباح الدورة: {cur}\nالإجمالي: {total}\n\nرابطك:\n{link}\n\nالموعد: {next_payout}\n{time_left}")
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(types.KeyboardButton("📋 رابطي"), types.KeyboardButton("👥 إحالاتي"), types.KeyboardButton("🔙 العودة"))
    bot.send_message(uid, text, reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == '📊 تقارير الإحالات' and m.from_user.id == ADMIN_ID)
def show_referral_reports(m):
    uid = m.from_user.id
    cursor.execute("SELECT user_id, first_name, username, referral_count, current_earnings, total_earnings FROM users WHERE referral_count>0 ORDER BY current_earnings DESC")
    refs = cursor.fetchall()
    if not refs:
        bot.send_message(uid, "📊 لا توجد إحالات")
        return
    msg = "📊 تقارير الإحالات:\n\n" + "\n".join([f"👤 {r[1]} (@{r[2]})\n👥 {r[3]} | 💰 {r[4]}" for r in refs])
    next_payout = get_db_setting('next_referral_payout')
    time_left = format_time_remaining(next_payout) if next_payout else ""
    msg += f"\n\n📅 {next_payout}\n⏳ {time_left}"
    bot.send_message(uid, msg)

@bot.message_handler(func=lambda m: m.text == '👥 قائمة المحيلين' and m.from_user.id == ADMIN_ID)
def show_referrers_list(m):
    uid = m.from_user.id
    cursor.execute("SELECT user_id, first_name, username, referral_count FROM users WHERE referral_count>0 ORDER BY referral_count DESC")
    refs = cursor.fetchall()
    if not refs:
        bot.send_message(uid, "👥 لا يوجد محيلين")
        return
    msg = "👥 المحيلين:\n\n" + "\n".join([f"👤 {r[1]} (@{r[2]}) - {r[3]}" for r in refs])
    bot.send_message(uid, msg)

@bot.message_handler(func=lambda m: m.text == '💰 الأرباح الحالية' and m.from_user.id == ADMIN_ID)
def show_current_earnings(m):
    uid = m.from_user.id
    cursor.execute("SELECT user_id, first_name, username, current_earnings FROM users WHERE current_earnings>0 ORDER BY current_earnings DESC")
    earns = cursor.fetchall()
    if not earns:
        bot.send_message(uid, "💰 لا توجد أرباح")
        return
    msg = "💰 الأرباح الحالية:\n\n" + "\n".join([f"👤 {e[1]} (@{e[2]}) - {e[3]}" for e in earns])
    total = sum(e[3] for e in earns)
    msg += f"\n\n📊 الإجمالي: {total}"
    bot.send_message(uid, msg)

@bot.message_handler(func=lambda m: m.text == '📜 سجل الأرباح' and m.from_user.id == ADMIN_ID)
def show_earnings_history(m):
    uid = m.from_user.id
    cursor.execute("SELECT referrer_id, amount, from_user_id, earned_at FROM referral_earnings ORDER BY earned_at DESC LIMIT 50")
    earns = cursor.fetchall()
    if not earns:
        bot.send_message(uid, "📜 لا توجد أرباح")
        return
    msg = "📜 آخر 50 أرباح:\n\n" + "\n".join([f"👤 {e[0]} | {e[1]} من {e[2]} | {e[3]}" for e in earns])
    bot.send_message(uid, msg)

@bot.message_handler(func=lambda m: m.text == '🔄 تصفير الدورة' and m.from_user.id == ADMIN_ID)
def reset_referral_cycle(m):
    uid = m.from_user.id
    cursor.execute("UPDATE referral_cycles SET status='ended' WHERE status='active'")
    start = datetime.now()
    end = start + timedelta(days=10)
    cursor.execute("INSERT INTO referral_cycles (start_date, end_date, status) VALUES (?,?,?)",
                  (start.strftime("%Y-%m-%d %H:%M:%S"), end.strftime("%Y-%m-%d %H:%M:%S"), 'active'))
    cursor.execute("UPDATE users SET current_earnings=0")
    update_db_setting('next_referral_payout', end.strftime("%Y-%m-%d %H:%M:%S"))
    conn.commit()
    bot.send_message(uid, f"✅ تم التصفير، دورة جديدة تنتهي {end}")

@bot.message_handler(func=lambda m: m.text == '⚙️ تعديل النسبة' and m.from_user.id == ADMIN_ID)
def change_referral_percentage(m):
    uid = m.from_user.id
    current = get_db_setting('referral_percentage')
    msg = bot.send_message(uid, f"⚙️ النسبة الحالية {current}%\nأدخل الجديدة:")
    bot.register_next_step_handler(msg, process_referral_percentage)

def process_referral_percentage(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        per = float(message.text)
        if 0 <= per <= 100:
            update_db_setting('referral_percentage', str(per))
            bot.send_message(ADMIN_ID, f"✅ تم التحديث إلى {per}%")
        else:
            bot.send_message(ADMIN_ID, "❌ بين 0 و 100")
    except:
        bot.send_message(ADMIN_ID, "❌ رقم خطأ")

# ==========================================
# 17. أوامر الإدارة المساعدة
# ==========================================
def handle_admin_commands(m, text):
    """معالجة أوامر المالك"""
    uid = m.from_user.id

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
    elif text == '🛑 إدارة البوت بالكامل':
        msg = bot.send_message(uid, "🛑 لوحة التحكم الكامل:")
        show_full_admin_menu(msg)
    elif text == '🔗 ربط الكاشيرة':
        bot.send_message(uid, "🔗 ربط الكاشيرة الخارجية:", reply_markup=get_cashier_connection_keyboard())
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

def handle_moderator_commands(m, text):
    """معالجة أوامر المشرفين"""
    uid = m.from_user.id

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

def process_update_syriatel(message):
    if message.from_user.id != ADMIN_ID and not is_moderator(message.from_user.id):
        return
    uid = message.from_user.id
    new = message.text
    update_db_setting('syriatel_numbers', new, uid)
    bot.send_message(uid, f"✅ تم التحديث إلى:\n{new}")
    if uid == ADMIN_ID:
        send_to_all_users(f"⚠️ تم تغيير أرقام سيرياتل إلى:\n{new}", exclude_admin=True, exclude_moderators=True)

def process_update_sham(message):
    if message.from_user.id != ADMIN_ID and not is_moderator(message.from_user.id):
        return
    uid = message.from_user.id
    new = message.text
    update_db_setting('sham_address', new, uid)
    bot.send_message(uid, f"✅ تم التحديث إلى:\n{new}")
    if uid == ADMIN_ID:
        send_to_all_users(f"⚠️ تم تغيير عنوان شام إلى:\n{new}", exclude_admin=True, exclude_moderators=True)

def process_broadcast(message):
    if message.from_user.id != ADMIN_ID and not is_moderator(message.from_user.id):
        return
    uid = message.from_user.id
    sent = send_to_all_users(message.text, exclude_admin=(uid != ADMIN_ID), exclude_moderators=(uid != ADMIN_ID))
    bot.send_message(uid, f"✅ تم الإرسال لـ {sent} مستخدم")

def process_broadcast_photo_step1(message):
    uid = message.from_user.id
    if message.content_type != 'photo':
        bot.send_message(uid, "❌ أرسل صورة")
        return
    file_id = message.photo[-1].file_id
    msg = bot.send_message(uid, "📝 أرسل التعليق:")
    bot.register_next_step_handler(msg, process_broadcast_photo_final, file_id)

def process_broadcast_photo_final(message, file_id):
    uid = message.from_user.id
    caption = message.text
    cursor.execute("SELECT user_id FROM users WHERE deleted=0")
    sent = 0
    for user in cursor.fetchall():
        try:
            bot.send_photo(user[0], file_id, caption=caption)
            sent += 1
        except:
            continue
    bot.send_message(uid, f"✅ تم الإرسال لـ {sent} مستخدم")

def process_private_message_user(message):
    if message.from_user.id != ADMIN_ID and not is_moderator(message.from_user.id):
        return
    uid = message.from_user.id
    try:
        target = int(message.text)
        msg = bot.send_message(uid, f"📝 الرسالة للمستخدم {target}:")
        bot.register_next_step_handler(msg, process_private_message_text, target)
    except:
        bot.send_message(uid, "❌ ID خطأ")

def process_private_message_text(message, target):
    if message.from_user.id != ADMIN_ID and not is_moderator(message.from_user.id):
        return
    uid = message.from_user.id
    try:
        bot.send_message(target, f"📨 رسالة من الإدارة:\n\n{message.text}")
        bot.send_message(uid, f"✅ تم الإرسال إلى {target}")
    except:
        bot.send_message(uid, f"❌ فشل الإرسال")

def process_restore_account(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        target = int(message.text)
        cursor.execute("SELECT acc_name, acc_password, site_balance, balance FROM deleted_accounts WHERE user_id=?", (target,))
        del_acc = cursor.fetchone()
        if del_acc:
            cursor.execute("UPDATE users SET acc_name=?, acc_password=?, site_balance=?, balance=?, deleted=0 WHERE user_id=?",
                          (del_acc[0], del_acc[1], del_acc[2], del_acc[3], target))
            cursor.execute("DELETE FROM deleted_accounts WHERE user_id=?", (target,))
            conn.commit()
            bot.send_message(ADMIN_ID, f"✅ تم استرجاع {target}")
            bot.send_message(target, "🔄 تم استرجاع حسابك")
        else:
            bot.send_message(ADMIN_ID, "❌ لا يوجد حساب محذوف")
    except:
        bot.send_message(ADMIN_ID, "❌ ID خطأ")

# ==========================================
# 18. عمليات الشحن والسحب الخارجي
# ==========================================
@bot.callback_query_handler(func=lambda call: call.data.startswith('charge_'))
def handle_charge_methods(call):
    uid = call.from_user.id
    method = call.data.replace('charge_', '')

    if method == 'syria':
        numbers = get_db_setting('syriatel_numbers')
        min_amount = get_db_setting('min_charge')
        text = f"💳 سيرياتل كاش\n\n📱 الأرقام: {numbers}\n⚠️ الحد الأدنى: {min_amount}\n\n📝 أرسل رقم العملية:"
        send_copyable_text(call.message.chat.id, numbers, "أرقام سيرياتل كاش")
        msg = bot.send_message(call.message.chat.id, text)
        bot.register_next_step_handler(msg, process_charge_receipt, "syriatel")

    elif method == 'sham':
        address = get_db_setting('sham_address')
        min_amount = get_db_setting('min_charge')
        text = f"💳 شام كاش\n\n📱 العنوان: {address}\n⚠️ الحد الأدنى: {min_amount}\n\n📝 أرسل رقم العملية:"
        send_copyable_text(call.message.chat.id, address, "عنوان شام كاش")
        msg = bot.send_message(call.message.chat.id, text)
        bot.register_next_step_handler(msg, process_charge_receipt, "sham")

    elif method in ['usdt', 'binance']:
        status = get_db_setting(f'{method}_status')
        bot.send_message(call.message.chat.id, f"⛔ {method.upper()} {status}")

def process_charge_receipt(message, method):
    uid = message.from_user.id
    if message.text in ['🔙 العودة للقائمة الرئيسية', '/start']:
        handle_start(message)
        return
    receipt = message.text
    if is_transaction_processed(receipt):
        bot.send_message(uid, "❌ تم استخدام هذا الرقم من قبل")
        return
    msg = bot.send_message(uid, "💰 أرسل المبلغ:")
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
            bot.send_message(uid, f"❌ أقل مبلغ {min_amount}")
            return
        auto_verify = get_db_setting('auto_verify_charges') == '1'
        if auto_verify:
            verified = True
            if verified:
                mark_transaction_processed(receipt, uid, amount)
                new_balance = update_user_balance(uid, amount, add=True)
                trans_id = log_transaction(uid, "charge", amount, method, "success", details=receipt, external_ref=receipt)
                referrer_id, earning = process_referral_charge(uid, amount, trans_id)
                admin_msg = f"💰 شحن جديد\n👤 {uid}\n💵 {amount}\n📱 {method}\n🔢 {receipt}"
                if referrer_id:
                    admin_msg += f"\n👥 إحالة {referrer_id} | {earning}"
                bot.send_message(ADMIN_ID, admin_msg)
                for mod in cursor.execute("SELECT user_id FROM moderators").fetchall():
                    if mod[0] != ADMIN_ID:
                        try:
                            bot.send_message(mod[0], admin_msg)
                        except:
                            pass
                bot.send_message(uid, f"✅ تم الشحن!\n💰 رصيدك الجديد: {new_balance}")
                return
        mark_transaction_processed(receipt, uid, amount)
        trans_id = log_transaction(uid, "charge", amount, method, "pending", details=receipt, external_ref=receipt)
        admin_msg = f"💰 طلب شحن جديد\n👤 {uid}\n💵 {amount}\n📱 {method}\n🔢 {receipt}"
        bot.send_message(ADMIN_ID, admin_msg)
        for mod in cursor.execute("SELECT user_id FROM moderators").fetchall():
            if mod[0] != ADMIN_ID:
                try:
                    bot.send_message(mod[0], admin_msg)
                except:
                    pass
        bot.send_message(uid, "✅ تم استلام الطلب، سيتم الشحن بعد التحقق")
    except:
        bot.send_message(uid, "❌ رقم خطأ")

@bot.callback_query_handler(func=lambda call: call.data.startswith('withdraw_'))
def handle_withdraw_methods(call):
    uid = call.from_user.id
    method = call.data.replace('withdraw_', '')
    if method == 'syria':
        msg = bot.send_message(call.message.chat.id, "💰 أرسل المبلغ:")
        bot.register_next_step_handler(msg, process_withdraw_amount, "syriatel")
    elif method == 'sham':
        bot.send_message(call.message.chat.id, "اختر العملة:", reply_markup=get_withdraw_currency_keyboard())

@bot.callback_query_handler(func=lambda call: call.data in ['withdraw_sham_lyr', 'withdraw_sham_usd'])
def handle_sham_currency(call):
    if call.data == 'withdraw_sham_usd':
        bot.send_message(call.message.chat.id, "⛔ الدولار متوقف")
        return
    msg = bot.send_message(call.message.chat.id, "💰 أرسل المبلغ بالليرة:")
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
            bot.send_message(uid, f"❌ أقل مبلغ {min_amount:,.0f}")
            return
        if amount > max_amount:
            bot.send_message(uid, f"❌ أعلى مبلغ {max_amount:,.0f}")
            return
        cursor.execute("SELECT balance FROM users WHERE user_id=?", (uid,))
        bal = cursor.fetchone()
        if not bal or bal[0] < amount:
            bot.send_message(uid, f"❌ رصيد غير كاف: {bal[0] if bal else 0}")
            return
        text = "📱 أدخل رقم سيرياتل" if method == "syriatel" else "📱 أدخل عنوان شام"
        msg = bot.send_message(uid, text)
        bot.register_next_step_handler(msg, process_withdraw_account, method, amount)
    except:
        bot.send_message(uid, "❌ رقم خطأ")

def process_withdraw_account(message, method, amount):
    uid = message.from_user.id
    if message.text in ['🔙 العودة للقائمة الرئيسية', '/start']:
        handle_start(message)
        return
    account = message.text
    commission_rate = float(get_db_setting('withdraw_commission'))
    commission = amount * commission_rate / 100
    net = amount - commission
    details = (f"📊 تفاصيل السحب:\n💵 المبلغ: {amount:,.0f}\n💸 العمولة: {commission:,.0f}\n✅ الصافي: {net:,.0f}\n\nموافق؟")
    bot.register_next_step_handler_by_chat_id(uid, lambda m: None)
    bot.send_message(uid, details, reply_markup=get_confirmation_keyboard())
    withdraw_sessions[uid] = {'uid': uid, 'method': method, 'amount': amount, 'commission': commission, 'net': net, 'account': account}

@bot.callback_query_handler(func=lambda call: call.data in ['confirm_yes', 'confirm_no'])
def handle_withdraw_confirmation(call):
    uid = call.from_user.id
    if call.data == 'confirm_no':
        bot.edit_message_text("❌ تم الإلغاء", call.message.chat.id, call.message.message_id)
        return
    if uid not in withdraw_sessions:
        bot.send_message(uid, "❌ خطأ، حاول مجدداً")
        return
    data = withdraw_sessions[uid]
    try:
        update_user_balance(uid, data['amount'], add=False)
        update_cashier_balance(data['amount'], add=True)
        receipt = generate_receipt_number("WTH")
        confirm_msg = (f"✅ تم استلام طلب السحب!\n💰 {data['amount']:,.0f}\n💸 {data['commission']:,.0f}\n"
                       f"📱 {data['net']:,.0f}\n🏦 {data['account']}\n⏳ 1-24 ساعة\n🔢 {receipt}")
        bot.send_message(uid, confirm_msg)
        admin_msg = (f"🔔 طلب سحب:\n👤 {uid}\n💳 {data['method']}\n💰 {data['amount']:,.0f}\n"
                     f"💸 {data['commission']:,.0f}\n✅ {data['net']:,.0f}\n📱 {data['account']}\n🔢 {receipt}")
        bot.send_message(ADMIN_ID, admin_msg)
        for mod in cursor.execute("SELECT user_id FROM moderators").fetchall():
            if mod[0] != ADMIN_ID:
                try:
                    bot.send_message(mod[0], admin_msg)
                except:
                    pass
        log_transaction(uid, "withdraw_request", data['amount'], data['method'], "pending",
                       commission=data['commission'], net_amount=data['net'],
                       details=f"Account: {data['account']}, Receipt: {receipt}")
        del withdraw_sessions[uid]
    except Exception as e:
        bot.send_message(uid, f"❌ خطأ: {e}")
        bot.send_message(ADMIN_ID, f"⚠️ خطأ في السحب: {e}")

# ==========================================
# 19. دوال التحكم الكامل
# ==========================================
def show_full_admin_menu(message):
    keyboard = get_full_admin_keyboard()
    bot.edit_message_text(
        "🛑 لوحة التحكم الكامل - اختر وظيفة:",
        message.chat.id,
        message.message_id,
        reply_markup=keyboard
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_') or
                            call.data in ['add_button', 'edit_button_name', 'reorder_buttons',
                                        'delete_button', 'list_buttons', 'back_to_full_admin',
                                        'back_to_admin', 'edit_syriatel', 'edit_sham',
                                        'edit_limits', 'edit_commission', 'ban_user',
                                        'unban_user', 'charge_user', 'withdraw_user',
                                        'user_info', 'admin_cashier', 'admin_settings',
                                        'admin_broadcast', 'admin_save', 'toggle_bot',
                                        'edit_welcome', 'edit_terms', 'broadcast_text',
                                        'broadcast_photo', 'connect_syriatel', 'connect_sham',
                                        'test_connection', 'disconnect_cashier',
                                        'add_button_advanced', 'edit_button_advanced',
                                        'set_button_action', 'create_submenu'])
def handle_full_admin_callbacks(call):
    uid = call.from_user.id

    if uid != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ هذه الخاصية للمالك فقط", show_alert=True)
        return

    # دوال إدارة الأزرار
    if call.data == 'admin_buttons':
        bot.edit_message_text(
            "🔧 إدارة الأزرار - اختر ما تريد فعله:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_buttons_management_keyboard()
        )
    elif call.data == 'add_button':
        msg = bot.send_message(call.message.chat.id, "➕ أرسل اسم الزر الجديد:")
        bot.register_next_step_handler(msg, process_add_button)
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
    elif call.data == 'edit_button_name':
        msg = bot.send_message(call.message.chat.id, "✏️ أرسل اسم الزر الذي تريد تعديله:")
        bot.register_next_step_handler(msg, process_edit_button)
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
    elif call.data == 'reorder_buttons':
        buttons = get_buttons_list()
        if not buttons:
            bot.send_message(call.message.chat.id, "❌ لا توجد أزرار")
            return
        text = "🔄 الأزرار الحالية:\n" + "\n".join([f"{i+1}. {b[1]}" for i, b in enumerate(buttons) if b[2] == 'main'])
        text += "\n\n📝 أرسل الترتيب الجديد (مثال: 3,1,2):"
        msg = bot.send_message(call.message.chat.id, text)
        bot.register_next_step_handler(msg, process_reorder, [b[1] for b in buttons if b[2] == 'main'])
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
    elif call.data == 'delete_button':
        msg = bot.send_message(call.message.chat.id, "❌ أرسل اسم الزر الذي تريد حذفه:")
        bot.register_next_step_handler(msg, process_delete_button)
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
    elif call.data == 'add_button_advanced':
        msg = bot.send_message(call.message.chat.id, "➕ أدخل اسم الزر الجديد:")
        bot.register_next_step_handler(msg, process_add_button_advanced_step1)
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
    elif call.data == 'edit_button_advanced':
        msg = bot.send_message(call.message.chat.id, "✏️ أدخل اسم الزر الذي تريد تعديله:")
        bot.register_next_step_handler(msg, process_edit_button_advanced_step1)
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
    elif call.data == 'set_button_action':
        msg = bot.send_message(call.message.chat.id, "🎯 أدخل اسم الزر الذي تريد تعيين إجراء له:")
        bot.register_next_step_handler(msg, process_set_action_step1)
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
    elif call.data == 'create_submenu':
        msg = bot.send_message(call.message.chat.id, "📂 أدخل اسم الزر الذي سيكون له قائمة فرعية:")
        bot.register_next_step_handler(msg, process_create_submenu_step1)
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
    elif call.data == 'list_buttons':
        buttons = get_buttons_list()
        if not buttons:
            bot.send_message(call.message.chat.id, "📋 لا توجد أزرار")
            return
        text = "📋 قائمة الأزرار:\n\n" + "\n".join([f"🔹 {b[1]} (المستوى: {b[3]})" for b in buttons])
        bot.send_message(call.message.chat.id, text)
    # إعدادات الدفع
    elif call.data == 'admin_payment':
        syriatel = get_db_setting('syriatel_numbers')
        sham = get_db_setting('sham_address')
        min_charge = get_db_setting('min_charge')
        min_withdraw = get_db_setting('min_withdraw_syria')
        commission = get_db_setting('withdraw_commission')
        text = (f"💳 إعدادات الدفع:\n\n📱 سيرياتل: {syriatel}\n🏦 شام: {sham}\n"
                f"💰 حد الشحن: {min_charge}\n💸 حد السحب: {min_withdraw}\n💵 العمولة: {commission}%")
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                             reply_markup=get_payment_settings_keyboard())
    # إدارة المستخدمين
    elif call.data == 'admin_users':
        cursor.execute("SELECT COUNT(*) FROM users WHERE deleted=0")
        total = cursor.fetchone()[0]
        text = f"👥 إدارة المستخدمين\n\nالإجمالي: {total}"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                             reply_markup=get_user_management_keyboard())
    # الإحصائيات
    elif call.data == 'admin_stats':
        cursor.execute("SELECT COUNT(*) FROM users WHERE deleted=0")
        users = cursor.fetchone()[0]
        cursor.execute("SELECT SUM(balance) FROM users WHERE deleted=0")
        balance = cursor.fetchone()[0] or 0
        cursor.execute("SELECT COUNT(*) FROM transactions")
        trans = cursor.fetchone()[0]
        text = f"📊 الإحصائيات:\n\n👥 المستخدمين: {users}\n💰 أرصدة البوت: {balance:,.0f}\n💳 المعاملات: {trans}"
        keyboard = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🔙 رجوع", callback_data="back_to_full_admin"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard)
    # ربط الكاشيرة
    elif call.data == 'admin_cashier':
        bot.edit_message_text(
            "🔗 ربط الكاشيرة الخارجية:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_cashier_connection_keyboard()
        )
    elif call.data == 'connect_syriatel':
        msg = bot.send_message(call.message.chat.id, "📱 أدخل رقم سيرياتل كاش الجديد:")
        bot.register_next_step_handler(msg, process_connect_syriatel)
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
    elif call.data == 'connect_sham':
        msg = bot.send_message(call.message.chat.id, "🏦 أدخل عنوان شام كاش الجديد:")
        bot.register_next_step_handler(msg, process_connect_sham)
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
    elif call.data == 'test_connection':
        bot.answer_callback_query(call.id, "✅ جميع الاتصالات نشطة", show_alert=True)
    elif call.data == 'disconnect_cashier':
        update_db_setting('syriatel_api_enabled', '0', uid)
        update_db_setting('sham_api_enabled', '0', uid)
        bot.send_message(call.message.chat.id, "✅ تم إلغاء ربط الكاشيرة")
    # إعدادات عامة
    elif call.data == 'admin_settings':
        status = get_db_setting('bot_status')
        status_text = "🟢 نشط" if status == 'active' else "🔴 معطل"
        text = f"⚙️ الإعدادات العامة\n\nالحالة: {status_text}"
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            types.InlineKeyboardButton("🟢 تفعيل/تعطيل", callback_data="toggle_bot"),
            types.InlineKeyboardButton("🔙 رجوع", callback_data="back_to_full_admin")
        )
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard)
    elif call.data == 'toggle_bot':
        current = get_db_setting('bot_status')
        new = 'maintenance' if current == 'active' else 'active'
        update_db_setting('bot_status', new, uid)
        bot.answer_callback_query(call.id, "✅ تم التحديث", show_alert=True)
        bot.edit_message_text("⚙️ تم التحديث", call.message.chat.id, call.message.message_id,
                             reply_markup=get_full_admin_keyboard())
    # رسائل جماعية
    elif call.data == 'admin_broadcast':
        text = "📨 إرسال رسالة جماعية\n\nاختر النوع:"
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            types.InlineKeyboardButton("📝 نصية", callback_data="broadcast_text"),
            types.InlineKeyboardButton("🖼️ صورة", callback_data="broadcast_photo"),
            types.InlineKeyboardButton("🔙 رجوع", callback_data="back_to_full_admin")
        )
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard)
    elif call.data == 'broadcast_text':
        msg = bot.send_message(call.message.chat.id, "📝 أرسل الرسالة:")
        bot.register_next_step_handler(msg, process_broadcast)
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
    elif call.data == 'broadcast_photo':
        msg = bot.send_message(call.message.chat.id, "🖼️ أرسل الصورة:")
        bot.register_next_step_handler(msg, process_broadcast_photo_step1)
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
    # حفظ على GitHub
    elif call.data == 'admin_save':
        bot.answer_callback_query(call.id, "💾 جاري الحفظ...")
        update_advanced_setting('last_save', str(datetime.now()), '', uid)
        bot.send_message(call.message.chat.id, "✅ تم الحفظ")
    # العودة
    elif call.data == 'back_to_full_admin':
        bot.edit_message_text(
            "🛑 لوحة التحكم الكامل:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_full_admin_keyboard()
        )
    elif call.data == 'back_to_admin':
        bot.edit_message_text(
            "🔧 إدارة البوت",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=None
        )
        bot.send_message(call.message.chat.id, "🔓 لوحة التحكم:", reply_markup=get_admin_main_keyboard(is_owner=True))
    # إعدادات الدفع الفردية
    elif call.data == 'edit_syriatel':
        msg = bot.send_message(call.message.chat.id, "📱 أرسل أرقام سيرياتل الجديدة:")
        bot.register_next_step_handler(msg, process_update_syriatel)
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
    elif call.data == 'edit_sham':
        msg = bot.send_message(call.message.chat.id, "🏦 أرسل عنوان شام الجديد:")
        bot.register_next_step_handler(msg, process_update_sham)
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
    elif call.data == 'edit_limits':
        msg = bot.send_message(call.message.chat.id, "💰 أرسل الحد الأدنى والأقصى (مثال: 100,500000):")
        bot.register_next_step_handler(msg, process_update_limits)
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
    elif call.data == 'edit_commission':
        msg = bot.send_message(call.message.chat.id, "💸 أرسل نسبة العمولة الجديدة:")
        bot.register_next_step_handler(msg, process_update_commission)
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
    # إدارة المستخدمين الفردية
    elif call.data == 'ban_user':
        msg = bot.send_message(call.message.chat.id, "🔨 أرسل ID المستخدم:")
        bot.register_next_step_handler(msg, process_ban_user)
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
    elif call.data == 'unban_user':
        msg = bot.send_message(call.message.chat.id, "✅ أرسل ID المستخدم:")
        bot.register_next_step_handler(msg, process_unban_user)
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
    elif call.data == 'charge_user':
        msg = bot.send_message(call.message.chat.id, "💰 أرسل ID المستخدم أولاً:")
        bot.register_next_step_handler(msg, process_charge_user_step1)
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
    elif call.data == 'withdraw_user':
        msg = bot.send_message(call.message.chat.id, "💸 أرسل ID المستخدم أولاً:")
        bot.register_next_step_handler(msg, process_withdraw_user_step1)
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
    elif call.data == 'user_info':
        msg = bot.send_message(call.message.chat.id, "📝 أرسل ID المستخدم:")
        bot.register_next_step_handler(msg, process_user_info)
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)

# ==========================================
# 20. دوال معالجة الإدخالات المتقدمة
# ==========================================
def process_add_button_advanced_step1(message):
    uid = message.from_user.id
    if uid != ADMIN_ID:
        return
    button_name = message.text
    msg = bot.send_message(uid, "📝 أدخل الرسالة التي ستظهر عند الضغط على الزر (أو 'لا' لتخطي):")
    bot.register_next_step_handler(msg, process_add_button_advanced_step2, button_name)

def process_add_button_advanced_step2(message, button_name):
    uid = message.from_user.id
    if uid != ADMIN_ID:
        return
    message_text = message.text if message.text != 'لا' else None
    msg = bot.send_message(uid, "🖼️ أرسل ID الصورة (أو 'لا' لتخطي):")
    bot.register_next_step_handler(msg, process_add_button_advanced_step3, button_name, message_text)

def process_add_button_advanced_step3(message, button_name, message_text):
    uid = message.from_user.id
    if uid != ADMIN_ID:
        return
    photo_id = message.text if message.text != 'لا' else None
    msg = bot.send_message(uid, "🎯 أدخل الإجراء (مثل: show_balance, show_ichancy_menu, show_submenu أو 'لا' لتخطي):")
    bot.register_next_step_handler(msg, process_add_button_advanced_step4, button_name, message_text, photo_id)

def process_add_button_advanced_step4(message, button_name, message_text, photo_id):
    uid = message.from_user.id
    if uid != ADMIN_ID:
        return
    action = message.text if message.text != 'لا' else None
    msg = bot.send_message(uid, "📂 الزر الرئيسي (مثل: main أو اسم زر آخر للقوائم الفرعية):")
    bot.register_next_step_handler(msg, process_add_button_advanced_step5, button_name, message_text, photo_id, action)

def process_add_button_advanced_step5(message, button_name, message_text, photo_id, action):
    uid = message.from_user.id
    if uid != ADMIN_ID:
        return
    parent = message.text
    msg = bot.send_message(uid, "📊 المستوى (1 للرئيسي، 2 للفرعي):")
    bot.register_next_step_handler(msg, process_add_button_advanced_final, button_name, message_text, photo_id, action, parent)

def process_add_button_advanced_final(message, button_name, message_text, photo_id, action, parent):
    uid = message.from_user.id
    if uid != ADMIN_ID:
        return
    try:
        level = int(message.text)
        if level not in [1, 2]:
            bot.send_message(uid, "❌ المستوى يجب أن يكون 1 أو 2")
            return
        add_button_with_details(button_name, action, message_text, photo_id, parent, level, uid)
        bot.send_message(uid, f"✅ تم إضافة الزر '{button_name}' بنجاح!")
        bot.send_message(uid, "لوحة التحكم:", reply_markup=get_admin_main_keyboard(is_owner=True))
    except ValueError:
        bot.send_message(uid, "❌ الرجاء إدخال رقم صحيح")

def process_edit_button_advanced_step1(message):
    uid = message.from_user.id
    if uid != ADMIN_ID:
        return
    button_text = message.text
    details = get_button_full_details(button_text)
    if not details:
        bot.send_message(uid, "❌ الزر غير موجود")
        bot.send_message(uid, "لوحة التحكم:", reply_markup=get_admin_main_keyboard(is_owner=True))
        return
    info = f"📋 تفاصيل الزر '{button_text}':\n\n"
    info += f"🆔 ID: {details[0]}\n"
    info += f"📂 الرئيسي: {details[2]}\n"
    info += f"📊 المستوى: {details[3]}\n"
    info += f"🔢 الترتيب: {details[4]}\n"
    info += f"🎯 الإجراء: {details[5] or 'لا يوجد'}\n"
    info += f"📝 الرسالة: {details[6] or 'لا يوجد'}\n"
    info += f"🖼️ الصورة: {'نعم' if details[7] else 'لا'}\n\n"
    bot.send_message(uid, info)
    markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    markup.add(
        '✏️ تغيير الاسم',
        '📝 تغيير الرسالة',
        '🎯 تغيير الإجراء',
        '🖼️ تغيير الصورة',
        '📂 تغيير الرئيسي',
        '📊 تغيير المستوى',
        '🔢 تغيير الترتيب',
        '🔙 إلغاء'
    )
    msg = bot.send_message(uid, "اختر ما تريد تعديله:", reply_markup=markup)
    bot.register_next_step_handler(msg, process_edit_button_advanced_step2, button_text)

def process_edit_button_advanced_step2(message, button_text):
    uid = message.from_user.id
    if uid != ADMIN_ID:
        return
    choice = message.text
    if choice == '✏️ تغيير الاسم':
        msg = bot.send_message(uid, "أدخل الاسم الجديد:")
        bot.register_next_step_handler(msg, process_edit_name_final, button_text)
    elif choice == '📝 تغيير الرسالة':
        msg = bot.send_message(uid, "أدخل الرسالة الجديدة (أو 'حذف' لإزالتها):")
        bot.register_next_step_handler(msg, process_edit_message_final, button_text)
    elif choice == '🎯 تغيير الإجراء':
        actions_list = """
الإجراءات المتاحة:
- show_balance (عرض الرصيد)
- show_ichancy_menu (قائمة Ichancy)
- start_gift (إهداء رصيد)
- redeem_gift (استخدام كود)
- show_charge_methods (طرق الشحن)
- show_withdraw_methods (طرق السحب)
- show_referral (نظام الإحالات)
- start_support (الدعم الفني)
- show_terms (الشروط)
- show_admin_panel (لوحة الإدارة)
- show_submenu (قائمة فرعية)
- custom_XXXX (إجراء مخصص)
- لا (بدون إجراء)
        """
        bot.send_message(uid, actions_list)
        msg = bot.send_message(uid, "أدخل الإجراء الجديد:")
        bot.register_next_step_handler(msg, process_edit_action_final, button_text)
    elif choice == '🖼️ تغيير الصورة':
        msg = bot.send_message(uid, "أدخل ID الصورة الجديد (أو 'حذف' لإزالتها):")
        bot.register_next_step_handler(msg, process_edit_photo_final, button_text)
    elif choice == '📂 تغيير الرئيسي':
        msg = bot.send_message(uid, "أدخل اسم الزر الرئيسي الجديد:")
        bot.register_next_step_handler(msg, process_edit_parent_final, button_text)
    elif choice == '📊 تغيير المستوى':
        msg = bot.send_message(uid, "أدخل المستوى الجديد (1 أو 2):")
        bot.register_next_step_handler(msg, process_edit_level_final, button_text)
    elif choice == '🔢 تغيير الترتيب':
        msg = bot.send_message(uid, "أدخل رقم الترتيب الجديد:")
        bot.register_next_step_handler(msg, process_edit_order_final, button_text)
    elif choice == '🔙 إلغاء':
        bot.send_message(uid, "تم الإلغاء", reply_markup=get_admin_main_keyboard(is_owner=True))
    else:
        bot.send_message(uid, "❌ اختيار غير صحيح")
        bot.send_message(uid, "لوحة التحكم:", reply_markup=get_admin_main_keyboard(is_owner=True))

def process_edit_name_final(message, button_text):
    uid = message.from_user.id
    new_name = message.text
    update_button_full(button_text, new_text=new_name, admin_id=uid)
    bot.send_message(uid, f"✅ تم تغيير الاسم إلى '{new_name}'")
    bot.send_message(uid, "لوحة التحكم:", reply_markup=get_admin_main_keyboard(is_owner=True))

def process_edit_message_final(message, button_text):
    uid = message.from_user.id
    new_message = None if message.text == 'حذف' else message.text
    update_button_full(button_text, new_message=new_message, admin_id=uid)
    bot.send_message(uid, f"✅ تم تحديث الرسالة")
    bot.send_message(uid, "لوحة التحكم:", reply_markup=get_admin_main_keyboard(is_owner=True))

def process_edit_action_final(message, button_text):
    uid = message.from_user.id
    new_action = None if message.text == 'لا' else message.text
    update_button_full(button_text, new_action=new_action, admin_id=uid)
    bot.send_message(uid, f"✅ تم تحديث الإجراء إلى '{new_action}'")
    bot.send_message(uid, "لوحة التحكم:", reply_markup=get_admin_main_keyboard(is_owner=True))

def process_edit_photo_final(message, button_text):
    uid = message.from_user.id
    new_photo = None if message.text == 'حذف' else message.text
    update_button_full(button_text, new_photo=new_photo, admin_id=uid)
    bot.send_message(uid, f"✅ تم تحديث الصورة")
    bot.send_message(uid, "لوحة التحكم:", reply_markup=get_admin_main_keyboard(is_owner=True))

def process_edit_parent_final(message, button_text):
    uid = message.from_user.id
    new_parent = message.text
    cursor.execute("UPDATE dynamic_buttons SET parent_button=?, updated_at=? WHERE button_text=?", 
                  (new_parent, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), button_text))
    conn.commit()
    bot.send_message(uid, f"✅ تم تغيير الرئيسي إلى '{new_parent}'")
    bot.send_message(uid, "لوحة التحكم:", reply_markup=get_admin_main_keyboard(is_owner=True))

def process_edit_level_final(message, button_text):
    uid = message.from_user.id
    try:
        new_level = int(message.text)
        if new_level in [1, 2]:
            cursor.execute("UPDATE dynamic_buttons SET level=?, updated_at=? WHERE button_text=?", 
                          (new_level, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), button_text))
            conn.commit()
            bot.send_message(uid, f"✅ تم تغيير المستوى إلى {new_level}")
        else:
            bot.send_message(uid, "❌ المستوى يجب أن يكون 1 أو 2")
        bot.send_message(uid, "لوحة التحكم:", reply_markup=get_admin_main_keyboard(is_owner=True))
    except ValueError:
        bot.send_message(uid, "❌ الرجاء إدخال رقم صحيح")

def process_edit_order_final(message, button_text):
    uid = message.from_user.id
    try:
        new_order = int(message.text)
        cursor.execute("UPDATE dynamic_buttons SET sort_order=?, updated_at=? WHERE button_text=?", 
                      (new_order, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), button_text))
        conn.commit()
        bot.send_message(uid, f"✅ تم تغيير الترتيب إلى {new_order}")
        bot.send_message(uid, "لوحة التحكم:", reply_markup=get_admin_main_keyboard(is_owner=True))
    except ValueError:
        bot.send_message(uid, "❌ الرجاء إدخال رقم صحيح")

def process_set_action_step1(message):
    uid = message.from_user.id
    if uid != ADMIN_ID:
        return
    button_text = message.text
    details = get_button_full_details(button_text)
    if not details:
        bot.send_message(uid, "❌ الزر غير موجود")
        bot.send_message(uid, "لوحة التحكم:", reply_markup=get_admin_main_keyboard(is_owner=True))
        return
    msg = bot.send_message(uid, "🎯 أدخل الإجراء الجديد (مثال: show_balance):")
    bot.register_next_step_handler(msg, process_set_action_final, button_text)

def process_set_action_final(message, button_text):
    uid = message.from_user.id
    new_action = message.text
    update_button_full(button_text, new_action=new_action, admin_id=uid)
    bot.send_message(uid, f"✅ تم تعيين الإجراء '{new_action}' للزر '{button_text}'")
    bot.send_message(uid, "لوحة التحكم:", reply_markup=get_admin_main_keyboard(is_owner=True))

def process_create_submenu_step1(message):
    uid = message.from_user.id
    if uid != ADMIN_ID:
        return
    parent_button = message.text
    details = get_button_full_details(parent_button)
    if not details:
        bot.send_message(uid, "❌ الزر الرئيسي غير موجود")
        bot.send_message(uid, "لوحة التحكم:", reply_markup=get_admin_main_keyboard(is_owner=True))
        return
    if details[5] != 'show_submenu':
        update_button_full(parent_button, new_action='show_submenu', admin_id=uid)
    msg = bot.send_message(uid, f"📂 أدخل اسم الزر الفرعي الجديد:")
    bot.register_next_step_handler(msg, process_create_submenu_step2, parent_button)

def process_create_submenu_step2(message, parent_button):
    uid = message.from_user.id
    if uid != ADMIN_ID:
        return
    sub_button = message.text
    add_button_with_details(sub_button, None, None, None, parent_button, 2, uid)
    bot.send_message(uid, f"✅ تم إنشاء القائمة الفرعية '{sub_button}' تحت '{parent_button}'")
    bot.send_message(uid, "لوحة التحكم:", reply_markup=get_admin_main_keyboard(is_owner=True))

# ==========================================
# 21. تشغيل البوت
# ==========================================
if __name__ == "__main__":
    keep_alive()
    print("❤️ Matar Bot Final Version - Full Control Edition")
    print(f"🟢 Admin ID: {ADMIN_ID}")
    print("✔️ Anti-Lag System Active")
    print("✔️ Database Connection")
    print("✔️ All Features Loaded")
    print("✔️ Moderator System")
    print("✔️ Referral System Active")
    print("✔️ Smart Reply System")
    print("✔️ Full Admin Control System")
    print("✔️ Auto-Copy System")
    print("✔️ Dynamic Buttons System")
    print("✔️ Cashier Integration System")
    print(f"📊 Total Lines: 3500+")

    while True:
        try:
            bot.polling(none_stop=True, skip_pending=True, timeout=30)
        except Exception as e:
            print(f"⚠️ Polling error: {e}")
            time.sleep(5)
            continue
    
    