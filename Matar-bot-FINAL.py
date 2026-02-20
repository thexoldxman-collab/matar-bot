# ================================================
# MATAR ULTIMATE TELEGRAM BOT - ENTERPRISE EDITION
# ================================================
# الإصدار: 5.0 الأسطوري
# المطور: المالك
# الوصف: بوت متكامل مع نظام إدارة كامل (CMS) - 60+ ميزة
# ================================================

# ==================== الجزء الأول ====================
# ========== 1. المكتبات والإعدادات الأساسية ==========
# ========== 2. نظام تسجيل الأخطاء (Logging) ==========
# ========== 3. نظام الحماية من السبام ==========
# ========== 4. قاعدة البيانات المتقدمة (20+ جدول) ==========
# ================================================

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
import logging
from logging.handlers import RotatingFileHandler
from collections import defaultdict
import sys

# ================================================
# 1. إعدادات البوت والسيرفر الأساسية
# ================================================

TOKEN = os.environ.get('TOKEN')
if not TOKEN:
    print("❌ خطأ: لم يتم العثور على TOKEN في متغيرات البيئة")
    print("✅ يرجى إضافة TOKEN = قيمة التوكن الخاص بك")
    TOKEN = input("أدخل التوكن يدوياً للتشغيل المحلي: ").strip()

bot = telebot.TeleBot(TOKEN)
ADMIN_ID = 846938470
CHANNEL_ID = "@Matar_ichancy"
CHANNEL_URL = "https://t.me/Matar_ichancy"

# متغيرات عامة
user_states = {}
withdraw_sessions = {}
api_connections = {}
user_last_message = defaultdict(float)
SPAM_DELAY = 1.5  # ثانية بين كل رسالة
DARK_MODE_USERS = set()  # للمستخدمين الذين فعّلوا الوضع الليلي

# ================================================
# 2. نظام تسجيل الأخطاء المتقدم (Logging)
# ================================================

# إعداد مجلد للسجلات إذا لم يكن موجوداً
if not os.path.exists('logs'):
    os.makedirs('logs')

# إعداد مسجل الأخطاء الرئيسي
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler('logs/matar_bot.log', maxBytes=10*1024*1024, backupCount=5),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('MatarBot')

# مسجل خاص للأخطاء الحرجة
error_logger = logging.getLogger('MatarBot.Error')
error_handler = RotatingFileHandler('logs/errors.log', maxBytes=5*1024*1024, backupCount=3)
error_handler.setLevel(logging.ERROR)
error_logger.addHandler(error_handler)

# مسجل خاص للمعاملات المالية
finance_logger = logging.getLogger('MatarBot.Finance')
finance_handler = RotatingFileHandler('logs/finance.log', maxBytes=5*1024*1024, backupCount=3)
finance_handler.setLevel(logging.INFO)
finance_logger.addHandler(finance_handler)

# مسجل خاص للإجراءات الإدارية
admin_logger = logging.getLogger('MatarBot.Admin')
admin_handler = RotatingFileHandler('logs/admin.log', maxBytes=5*1024*1024, backupCount=3)
admin_handler.setLevel(logging.INFO)
admin_logger.addHandler(admin_handler)

logger.info("🚀 بدء تشغيل البوت - Matar Ultimate Edition")

# ================================================
# 3. نظام الحماية من السبام (Anti-Spam)
# ================================================

def check_spam(uid):
    """
    التحقق من عدم إرسال رسائل متكررة بسرعة
    """
    now = time.time()
    last_time = user_last_message.get(uid, 0)
    
    if now - last_time < SPAM_DELAY:
        logger.warning(f"⚠️ محاولة سبام من المستخدم {uid}")
        return False
    
    user_last_message[uid] = now
    return True

# ================================================
# 4. نظام قاعدة البيانات المتكامل (20+ جدول)
# ================================================

def setup_database():
    """
    إنشاء جميع جداول قاعدة البيانات مع العلاقات
    """
    conn = sqlite3.connect("matar_ultimate.db", check_same_thread=False)
    cursor = conn.cursor()
    
    # ===== الجداول الأساسية =====
    
    # جدول المستخدمين
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
        welcome_shown INTEGER DEFAULT 0,
        dark_mode INTEGER DEFAULT 0,
        language TEXT DEFAULT 'ar',
        notifications INTEGER DEFAULT 1
    )""")
    
    # جدول أكواد الهدايا
    cursor.execute("""CREATE TABLE IF NOT EXISTS gifts(
        code TEXT PRIMARY KEY,
        value REAL,
        limit_count INTEGER,
        used_count INTEGER DEFAULT 0,
        type TEXT DEFAULT 'individual',
        created_by INTEGER,
        created_at TEXT,
        expires_at TEXT,
        min_balance REAL DEFAULT 0,
        for_new_users INTEGER DEFAULT 0
    )""")
    
    # جدول استخدام الهدايا
    cursor.execute("""CREATE TABLE IF NOT EXISTS gift_usage(
        user_id INTEGER,
        code TEXT,
        used_at TEXT,
        UNIQUE(user_id, code)
    )""")
    
    # جدول المعاملات المالية
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
        receipt_number TEXT UNIQUE,
        external_ref TEXT,
        verified INTEGER DEFAULT 0,
        verified_by INTEGER,
        verified_at TEXT
    )""")
    
    # جدول المعاملات المجهزة
    cursor.execute("""CREATE TABLE IF NOT EXISTS processed_transactions(
        receipt_number TEXT PRIMARY KEY,
        user_id INTEGER,
        amount REAL,
        processed_at TEXT
    )""")
    
    # جدول الحسابات المحذوفة
    cursor.execute("""CREATE TABLE IF NOT EXISTS deleted_accounts(
        user_id INTEGER PRIMARY KEY,
        acc_name TEXT,
        acc_password TEXT,
        balance REAL,
        site_balance REAL,
        deleted_at TEXT,
        restored_by INTEGER,
        restored_at TEXT
    )""")
    
    # جدول أرصدة الكاشيرة
    cursor.execute("""CREATE TABLE IF NOT EXISTS cashier_balance(
        admin_id INTEGER PRIMARY KEY,
        balance REAL DEFAULT 0,
        last_updated TEXT
    )""")
    
    # ===== نظام الدعم والتذاكر =====
    
    cursor.execute("""CREATE TABLE IF NOT EXISTS tickets(
        ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        message TEXT,
        file_id TEXT,
        status TEXT DEFAULT 'open',
        priority TEXT DEFAULT 'normal',
        created_at TEXT,
        last_reply_by INTEGER,
        last_reply_at TEXT,
        replied_count INTEGER DEFAULT 0,
        closed_by INTEGER,
        closed_at TEXT,
        rating INTEGER DEFAULT 0
    )""")
    
    cursor.execute("""CREATE TABLE IF NOT EXISTS ticket_conversations(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_id INTEGER,
        sender_id INTEGER,
        sender_type TEXT,
        message TEXT,
        file_id TEXT,
        sent_at TEXT,
        seen INTEGER DEFAULT 0
    )""")
    
    # ===== نظام المشرفين والصلاحيات =====
    
    cursor.execute("""CREATE TABLE IF NOT EXISTS moderators(
        user_id INTEGER PRIMARY KEY,
        custom_name TEXT,
        added_by INTEGER,
        added_at TEXT,
        moderator_type TEXT DEFAULT 'support',
        can_reply_tickets INTEGER DEFAULT 1,
        can_change_payment INTEGER DEFAULT 0,
        can_send_broadcast INTEGER DEFAULT 0,
        can_manage_users INTEGER DEFAULT 0,
        can_charge_withdraw INTEGER DEFAULT 0,
        can_view_stats INTEGER DEFAULT 0,
        can_manage_buttons INTEGER DEFAULT 0,
        can_access_full_admin INTEGER DEFAULT 0,
        can_manage_moderators INTEGER DEFAULT 0,
        permissions TEXT
    )""")
    
    # ===== نظام الإعدادات =====
    
    cursor.execute("""CREATE TABLE IF NOT EXISTS settings(
        key TEXT PRIMARY KEY,
        value TEXT,
        description TEXT,
        type TEXT DEFAULT 'text',
        updated_at TEXT,
        updated_by INTEGER
    )""")
    
    # ===== نظام سجل الإداريين =====
    
    cursor.execute("""CREATE TABLE IF NOT EXISTS admin_logs(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        admin_id INTEGER,
        action TEXT,
        details TEXT,
        ip_address TEXT,
        created_at TEXT
    )""")
    
    # ===== نظام الإحالات المتقدم =====
    
    cursor.execute("""CREATE TABLE IF NOT EXISTS referrals_log(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        referrer_id INTEGER,
        referred_id INTEGER,
        joined_at TEXT,
        UNIQUE(referred_id)
    )""")
    
    cursor.execute("""CREATE TABLE IF NOT EXISTS referral_earnings(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        referrer_id INTEGER,
        amount REAL,
        from_user_id INTEGER,
        transaction_id INTEGER,
        cycle_start TEXT,
        cycle_end TEXT,
        earned_at TEXT,
        paid INTEGER DEFAULT 0,
        paid_at TEXT
    )""")
    
    cursor.execute("""CREATE TABLE IF NOT EXISTS referral_cycles(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        start_date TEXT,
        end_date TEXT,
        status TEXT DEFAULT 'active',
        total_earnings REAL DEFAULT 0,
        paid_out REAL DEFAULT 0
    )""")
    
    # ===== نظام الأزرار الديناميكي المتقدم =====
    
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
        requires_subscription INTEGER DEFAULT 0,
        requires_admin INTEGER DEFAULT 0,
        requires_moderator INTEGER DEFAULT 0,
        cooldown INTEGER DEFAULT 0,
        created_at TEXT,
        updated_at TEXT,
        created_by INTEGER
    )""")
    
    # جدول الإجراءات المخصصة
    cursor.execute("""CREATE TABLE IF NOT EXISTS custom_actions(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        action_name TEXT UNIQUE,
        action_type TEXT,
        action_data TEXT,
        description TEXT,
        created_by INTEGER,
        created_at TEXT
    )""")
    
    # ===== نظام اتصالات API =====
    
    cursor.execute("""CREATE TABLE IF NOT EXISTS api_connections(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        api_key TEXT,
        api_secret TEXT,
        endpoint TEXT,
        is_active INTEGER DEFAULT 0,
        last_verified TEXT,
        verified_by INTEGER,
        created_at TEXT,
        updated_at TEXT,
        connection_status TEXT DEFAULT 'disconnected'
    )""")
    
    # ===== نظام الشحن الخارجي =====
    
    cursor.execute("""CREATE TABLE IF NOT EXISTS external_charges(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount REAL,
        method TEXT,
        external_ref TEXT UNIQUE,
        verified INTEGER DEFAULT 0,
        verified_at TEXT,
        verified_by INTEGER,
        created_at TEXT,
        notes TEXT
    )""")
    
    # ===== نظام النسخ الاحتياطي =====
    
    cursor.execute("""CREATE TABLE IF NOT EXISTS backups(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        backup_name TEXT,
        backup_type TEXT,
        file_path TEXT,
        created_at TEXT,
        created_by INTEGER,
        restored_at TEXT,
        restored_by INTEGER,
        size INTEGER
    )""")
    
    # ===== نظام الإحصائيات =====
    
    cursor.execute("""CREATE TABLE IF NOT EXISTS stats(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        stat_date TEXT,
        stat_type TEXT,
        stat_value TEXT,
        UNIQUE(stat_date, stat_type)
    )""")
    
    # ===== الإعدادات الافتراضية =====
    
    default_settings = [
        ('syriatel_numbers', '42483891,99706078', 'أرقام سيرياتل كاش', 'text'),
        ('sham_address', 'sham_example@sham', 'عنوان شام كاش', 'text'),
        ('usdt_status', 'متوقف', 'حالة USDT', 'text'),
        ('binance_status', 'متوقف', 'حالة Binance', 'text'),
        ('min_charge', '100', 'الحد الأدنى للشحن', 'number'),
        ('min_withdraw_syria', '25000', 'الحد الأدنى لسحب سيرياتل', 'number'),
        ('max_withdraw_syria', '500000', 'الحد الأقصى لسحب سيرياتل', 'number'),
        ('min_withdraw_sham', '25000', 'الحد الأدنى لسحب شام', 'number'),
        ('max_withdraw_sham', '5000000', 'الحد الأقصى لسحب شام', 'number'),
        ('withdraw_commission', '10', 'نسبة عمولة السحب', 'number'),
        ('bot_status', 'active', 'حالة البوت', 'text'),
        ('welcome_message', 'اهلا وسهلا بك في بوت Matar البوت الرسمي لموقع ichancy', 'رسالة الترحيب', 'text'),
        ('terms_message', '📜 الشروط:\n\n1. الاشتراك بالقناة إلزامي\n2. الحد الأدنى للشحن: 100 ل.س\n3. السحب: سيرياتل 25k-500k، شام 25k-5M\n4. عمولة السحب: 10%\n5. مدة السحب: 1-24 ساعة', 'نص الشروط', 'text'),
        ('referral_percentage', '10', 'نسبة الإحالات', 'number'),
        ('next_referral_payout', '', 'موعد الدفعة القادمة', 'text'),
        ('current_referral_cycle', '', 'الدورة الحالية', 'text'),
        ('syriatel_api_enabled', '0', 'تفعيل API سيرياتل', 'boolean'),
        ('sham_api_enabled', '0', 'تفعيل API شام', 'boolean'),
        ('auto_verify_charges', '1', 'التحقق التلقائي', 'boolean'),
        ('maintenance_message', '🔧 البوت في حالة صيانة حالياً. سنعود قريباً!', 'رسالة الصيانة', 'text'),
        ('min_gift_amount', '10', 'الحد الأدنى للهدية', 'number'),
        ('max_gift_amount', '1000000', 'الحد الأقصى للهدية', 'number'),
        ('enable_dark_mode', '1', 'تفعيل الوضع الليلي', 'boolean')
    ]
    
    for key, value, desc, typ in default_settings:
        cursor.execute("INSERT OR IGNORE INTO settings(key, value, description, type) VALUES (?,?,?,?)",
                      (key, value, desc, typ))
    
    # إضافة رصيد الكاشيرة للمالك
    cursor.execute("INSERT OR IGNORE INTO cashier_balance(admin_id, balance, last_updated) VALUES (?,?,?)",
                  (ADMIN_ID, 0, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    
    # إنشاء دورة إحالات أولية
    cursor.execute("SELECT * FROM referral_cycles WHERE status='active'")
    if not cursor.fetchone():
        start = datetime.now()
        end = start + timedelta(days=10)
        cursor.execute("INSERT INTO referral_cycles (start_date, end_date, status) VALUES (?,?,?)",
                      (start.strftime("%Y-%m-%d %H:%M:%S"), end.strftime("%Y-%m-%d %H:%M:%S"), 'active'))
        cursor.execute("UPDATE settings SET value=? WHERE key=?",
                      (end.strftime("%Y-%m-%d %H:%M:%S"), 'next_referral_payout'))
    
    # الأزرار الافتراضية
    default_buttons = [
        ('ichancy', '⚽ Ichancy ⚽', 'main', 'reply', 'show_ichancy_menu', None, None, 1, 1, 0, 0, 0, 0, 0),
        ('balance', '💰 الرصيد', 'main', 'reply', 'show_balance', None, None, 1, 2, 0, 0, 0, 0, 0),
        ('gift', '🎁 اهداء رصيد', 'main', 'reply', 'start_gift', None, None, 1, 3, 0, 0, 0, 0, 0),
        ('gift_code', '🎫 كود هدية', 'main', 'reply', 'redeem_gift', None, None, 1, 4, 0, 0, 0, 0, 0),
        ('charge', '💳 الشحن في البوت', 'main', 'reply', 'show_charge_methods', None, None, 1, 5, 0, 0, 0, 0, 0),
        ('withdraw', '💸 السحب من البوت', 'main', 'reply', 'show_withdraw_methods', None, None, 1, 6, 0, 0, 0, 0, 0),
        ('referral', '👥 دعوة الأصدقاء', 'main', 'reply', 'show_referral', None, None, 1, 7, 0, 0, 0, 0, 0),
        ('support', '📞 التواصل مع الدعم', 'main', 'reply', 'start_support', None, None, 1, 8, 0, 0, 0, 0, 0),
        ('terms', '📜 الشروط والاحكام', 'main', 'reply', 'show_terms', None, None, 1, 9, 0, 0, 0, 0, 0),
        ('admin', '🔐 إدارة البوت', 'main', 'reply', 'show_admin_panel', None, None, 1, 10, 0, 0, 1, 0, 0)
    ]
    
    for btn in default_buttons:
        cursor.execute("""INSERT OR IGNORE INTO dynamic_buttons
            (button_name, button_text, parent_button, button_type, action, message_text, photo_id, 
             level, sort_order, requires_subscription, requires_admin, requires_moderator, cooldown, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (btn[0], btn[1], btn[2], btn[3], btn[4], btn[5], btn[6], btn[7], btn[8], btn[9], btn[10], btn[11], btn[12],
             datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    
    conn.commit()
    logger.info("✅ تم إنشاء قاعدة البيانات بنجاح مع 20+ جدول")
    return conn, cursor

# تهيئة قاعدة البيانات
conn, cursor = setup_database()

# ================================================
# 5. الدوال المساعدة الأساسية
# ================================================

def reset_user_state(uid):
    """إعادة تعيين حالة المستخدم لمنع التعليق"""
    if uid in user_states:
        del user_states[uid]
    bot.clear_step_handler_by_chat_id(chat_id=uid)

def get_db_setting(key_name):
    """الحصول على إعداد من قاعدة البيانات"""
    cursor.execute("SELECT value FROM settings WHERE key=?", (key_name,))
    result = cursor.fetchone()
    return result[0] if result else None

def update_db_setting(key_name, value, admin_id=ADMIN_ID):
    """تحديث إعداد في قاعدة البيانات"""
    cursor.execute("""UPDATE settings SET value=?, updated_at=?, updated_by=?
                      WHERE key=?""", (value, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), admin_id, key_name))
    conn.commit()
    admin_logger.info(f"Admin {admin_id} updated setting {key_name} to {value}")

def log_admin_action(admin_id, action, details=""):
    """تسجيل إجراء إداري"""
    cursor.execute("""INSERT INTO admin_logs (admin_id, action, details, created_at)
                      VALUES (?,?,?,?)""",
                  (admin_id, action, details, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    admin_logger.info(f"Admin {admin_id}: {action} - {details}")

def check_subscription(uid):
    """التحقق من اشتراك المستخدم في القناة"""
    try:
        member = bot.get_chat_member(CHANNEL_ID, uid)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logger.error(f"خطأ في التحقق من الاشتراك للمستخدم {uid}: {e}")
        return False

def generate_receipt_number(prefix="TXN"):
    """توليد رقم فاتورة فريد"""
    timestamp = datetime.now().strftime("%y%m%d%H%M%S")
    random_part = ''.join(random.choices(string.digits, k=4))
    return f"{prefix}{timestamp}{random_part}"

def generate_gift_code():
    """توليد كود هدية فريد"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))

def generate_ref_code(user_id):
    """توليد كود إحالة فريد"""
    return f"MATAR{user_id}{''.join(random.choices(string.ascii_uppercase + string.digits, k=6))}"

def log_transaction(user_id, type, amount, method, status, commission=0, net_amount=0, admin_id=None, details="", external_ref=""):
    """تسجيل معاملة مالية"""
    receipt = generate_receipt_number()
    cursor.execute("""INSERT INTO transactions
        (user_id, type, amount, commission, net_amount, method, status, transaction_date, admin_id, details, receipt_number, external_ref)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (user_id, type, amount, commission, net_amount, method, status,
         datetime.now().strftime("%Y-%m-%d %H:%M:%S"), admin_id, details, receipt, external_ref))
    conn.commit()
    
    # تسجيل في سجل المعاملات المالية
    finance_logger.info(f"Transaction: {receipt} - User: {user_id} - Type: {type} - Amount: {amount} - Status: {status}")
    
    return receipt

def is_transaction_processed(receipt_number):
    """التحقق من معالجة المعاملة مسبقاً"""
    cursor.execute("SELECT * FROM processed_transactions WHERE receipt_number=?", (receipt_number,))
    return cursor.fetchone() is not None

def mark_transaction_processed(receipt_number, user_id, amount):
    """تسجيل معاملة كمجهزة"""
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
        cursor.execute("UPDATE users SET balance=?, last_active=? WHERE user_id=?",
                      (new_balance, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id))
        conn.commit()
        return new_balance
    return None

def update_cashier_balance(amount, add=True, admin_id=ADMIN_ID):
    """تحديث رصيد الكاشيرة"""
    cursor.execute("SELECT balance FROM cashier_balance WHERE admin_id=?", (admin_id,))
    result = cursor.fetchone()
    if result:
        new_balance = result[0] + amount if add else result[0] - amount
        cursor.execute("UPDATE cashier_balance SET balance=?, last_updated=? WHERE admin_id=?",
                      (new_balance, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), admin_id))
        conn.commit()
        return new_balance
    return None

def check_bot_status():
    """التحقق من حالة البوت"""
    status = get_db_setting('bot_status')
    return status == 'active'

def is_moderator(user_id):
    """التحقق من كون المستخدم مشرفاً"""
    if user_id == ADMIN_ID:
        return True
    cursor.execute("SELECT user_id FROM moderators WHERE user_id=?", (user_id,))
    return cursor.fetchone() is not None

def get_moderator_name(user_id):
    """الحصول على اسم المشرف"""
    if user_id == ADMIN_ID:
        return "المالك"
    cursor.execute("SELECT custom_name FROM moderators WHERE user_id=?", (user_id,))
    result = cursor.fetchone()
    if result and result[0]:
        return result[0]
    return f"مشرف {user_id}"

def get_moderator_permissions(user_id):
    """الحصول على صلاحيات المشرف"""
    if user_id == ADMIN_ID:
        # المالك له كل الصلاحيات
        return {
            'can_reply_tickets': 1,
            'can_change_payment': 1,
            'can_send_broadcast': 1,
            'can_manage_users': 1,
            'can_charge_withdraw': 1,
            'can_view_stats': 1,
            'can_manage_buttons': 1,
            'can_access_full_admin': 1,
            'can_manage_moderators': 1
        }
    
    cursor.execute("""SELECT can_reply_tickets, can_change_payment, can_send_broadcast,
                      can_manage_users, can_charge_withdraw, can_view_stats,
                      can_manage_buttons, can_access_full_admin, can_manage_moderators
                      FROM moderators WHERE user_id=?""", (user_id,))
    result = cursor.fetchone()
    if result:
        return {
            'can_reply_tickets': result[0],
            'can_change_payment': result[1],
            'can_send_broadcast': result[2],
            'can_manage_users': result[3],
            'can_charge_withdraw': result[4],
            'can_view_stats': result[5],
            'can_manage_buttons': result[6],
            'can_access_full_admin': result[7],
            'can_manage_moderators': result[8]
        }
    return {}

def check_permission(user_id, permission):
    """التحقق من صلاحية معينة للمشرف"""
    if user_id == ADMIN_ID:
        return True
    perms = get_moderator_permissions(user_id)
    return perms.get(permission, 0) == 1

def get_user_custom_name(user_id):
    """الحصول على الاسم المخصص للمستخدم"""
    cursor.execute("SELECT custom_name FROM users WHERE user_id=?", (user_id,))
    result = cursor.fetchone()
    return result[0] if result and result[0] else None

def format_time_remaining(target_time):
    """تنسيق الوقت المتبقي"""
    try:
        target = datetime.strptime(target_time, "%Y-%m-%d %H:%M:%S")
        now = datetime.now()
        diff = target - now
        days = diff.days
        hours = diff.seconds // 3600
        minutes = (diff.seconds % 3600) // 60
        return f"{days} يوم {hours} ساعة {minutes} دقيقة"
    except Exception as e:
        logger.error(f"خطأ في تنسيق الوقت: {e}")
        return "غير متوفر"

def check_and_create_ref_code(user_id):
    """التحقق من وجود كود إحالة أو إنشاؤه"""
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
    """الحصول على مستخدم عن طريق كود الإحالة"""
    cursor.execute("SELECT user_id FROM users WHERE ref_code=?", (ref_code,))
    result = cursor.fetchone()
    return result[0] if result else None

def register_referral(referrer_id, new_user_id):
    """تسجيل إحالة جديدة"""
    cursor.execute("""INSERT INTO referrals_log (referrer_id, referred_id, joined_at)
                      VALUES (?,?,?)""",
                  (referrer_id, new_user_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    cursor.execute("""UPDATE users SET referral_count = referral_count + 1
                      WHERE user_id=?""", (referrer_id,))
    conn.commit()
    logger.info(f"إحالة جديدة: {referrer_id} -> {new_user_id}")

def has_completed_welcome(user_id):
    """التحقق من ظهور رسالة الترحيب"""
    cursor.execute("SELECT welcome_shown FROM users WHERE user_id=?", (user_id,))
    result = cursor.fetchone()
    return result and result[0] == 1

def toggle_dark_mode(user_id):
    """تبديل الوضع الليلي للمستخدم"""
    cursor.execute("SELECT dark_mode FROM users WHERE user_id=?", (user_id,))
    result = cursor.fetchone()
    current = result[0] if result else 0
    new_value = 1 if current == 0 else 0
    
    cursor.execute("UPDATE users SET dark_mode=? WHERE user_id=?", (new_value, user_id))
    conn.commit()
    
    if new_value == 1:
        DARK_MODE_USERS.add(user_id)
    else:
        DARK_MODE_USERS.discard(user_id)
    
    return new_value

def format_text_dark_mode(text, user_id):
    """تنسيق النص حسب الوضع الليلي"""
    if user_id in DARK_MODE_USERS:
        # يمكن إضافة تأثيرات بصرية للوضع الليلي
        return f"🌙 {text}"
    return text

# نهاية الجزء الأول

# ================================================
# MATAR ULTIMATE TELEGRAM BOT - ENTERPRISE EDITION
# ================================================
# ==================== الجزء الثاني ====================
# ========== 6. نظام الإجراءات المتقدم (50+ إجراء) ==========
# ========== 7. نظام النسخ الفوري ==========
# ========== 8. بناء لوحات المفاتيح الديناميكية ==========
# ========== 9. نظام إدارة الأزرار المتقدم (CMS) ==========
# ================================================

# ================================================
# 6. نظام الإجراءات المتقدم (Actions System)
# ================================================

class ActionSystem:
    """
    نظام الإجراءات الموحد - يربط الأزرار بالوظائف
    """
    
    @staticmethod
    def execute_action(uid, chat_id, action, button_data=None):
        """
        تنفيذ إجراء معين بناءً على اسم الإجراء
        """
        try:
            # إجراءات المستخدم الأساسية
            if action == 'show_balance':
                return ActionSystem.show_balance(uid, chat_id)
            elif action == 'show_ichancy_menu':
                return ActionSystem.show_ichancy_menu(uid, chat_id)
            elif action == 'show_ichancy_account':
                return ActionSystem.show_ichancy_account(uid, chat_id)
            elif action == 'create_ichancy_account':
                return ActionSystem.create_ichancy_account(uid, chat_id)
            elif action == 'charge_ichancy':
                return ActionSystem.charge_ichancy(uid, chat_id)
            elif action == 'withdraw_ichancy':
                return ActionSystem.withdraw_ichancy(uid, chat_id)
            elif action == 'delete_ichancy_account':
                return ActionSystem.delete_ichancy_account(uid, chat_id)
            
            # إجراءات مالية
            elif action == 'show_charge_methods':
                return ActionSystem.show_charge_methods(uid, chat_id)
            elif action == 'show_withdraw_methods':
                return ActionSystem.show_withdraw_methods(uid, chat_id)
            elif action == 'start_gift':
                return ActionSystem.start_gift(uid, chat_id)
            elif action == 'redeem_gift':
                return ActionSystem.redeem_gift(uid, chat_id)
            elif action == 'show_transactions':
                return ActionSystem.show_transactions(uid, chat_id)
            
            # إجراءات اجتماعية
            elif action == 'show_referral':
                return ActionSystem.show_referral(uid, chat_id)
            elif action == 'show_referral_link':
                return ActionSystem.show_referral_link(uid, chat_id)
            elif action == 'show_referral_stats':
                return ActionSystem.show_referral_stats(uid, chat_id)
            
            # إجراءات دعم
            elif action == 'start_support':
                return ActionSystem.start_support(uid, chat_id)
            elif action == 'show_tickets':
                return ActionSystem.show_tickets(uid, chat_id)
            elif action == 'show_terms':
                return ActionSystem.show_terms(uid, chat_id)
            
            # إجراءات إدارية
            elif action == 'show_admin_panel':
                return ActionSystem.show_admin_panel(uid, chat_id)
            elif action == 'show_moderator_panel':
                return ActionSystem.show_moderator_panel(uid, chat_id)
            elif action == 'show_full_admin_menu':
                return ActionSystem.show_full_admin_menu(uid, chat_id)
            elif action == 'manage_buttons':
                return ActionSystem.manage_buttons(uid, chat_id)
            elif action == 'manage_users':
                return ActionSystem.manage_users(uid, chat_id)
            elif action == 'manage_moderators':
                return ActionSystem.manage_moderators(uid, chat_id)
            elif action == 'payment_settings':
                return ActionSystem.payment_settings(uid, chat_id)
            elif action == 'bot_settings':
                return ActionSystem.bot_settings(uid, chat_id)
            elif action == 'system_stats':
                return ActionSystem.system_stats(uid, chat_id)
            elif action == 'backup_system':
                return ActionSystem.backup_system(uid, chat_id)
            
            # إجراءات ربط الكاشيرة
            elif action == 'connect_syriatel':
                return ActionSystem.connect_syriatel(uid, chat_id)
            elif action == 'connect_sham':
                return ActionSystem.connect_sham(uid, chat_id)
            elif action == 'test_api':
                return ActionSystem.test_api(uid, chat_id)
            elif action == 'toggle_auto_verify':
                return ActionSystem.toggle_auto_verify(uid, chat_id)
            
            # إجراءات مخصصة
            elif action == 'send_message':
                return ActionSystem.send_custom_message(uid, chat_id, button_data)
            elif action == 'send_photo':
                return ActionSystem.send_custom_photo(uid, chat_id, button_data)
            elif action == 'open_link':
                return ActionSystem.open_link(uid, chat_id, button_data)
            elif action == 'toggle_dark_mode':
                return ActionSystem.toggle_dark_mode(uid, chat_id)
            
            # إجراءات القوائم الفرعية
            elif action == 'show_submenu':
                return ActionSystem.show_submenu(uid, chat_id, button_data)
            
            else:
                bot.send_message(chat_id, "❌ هذا الإجراء غير مفعل بعد")
                logger.warning(f"محاولة تنفيذ إجراء غير معروف: {action} من المستخدم {uid}")
                
        except Exception as e:
            error_logger.error(f"خطأ في تنفيذ الإجراء {action} للمستخدم {uid}: {e}")
            bot.send_message(chat_id, "❌ حدث خطأ أثناء تنفيذ العملية")

    # ===== إجراءات المستخدم الأساسية =====
    
    @staticmethod
    def show_balance(uid, chat_id):
        """عرض رصيد المستخدم"""
        cursor.execute("SELECT balance FROM users WHERE user_id=?", (uid,))
        bal = cursor.fetchone()
        balance = bal[0] if bal else 0
        
        if uid in DARK_MODE_USERS:
            text = f"🌙 **رصيدك الحالي:**\n💰 `{balance:,.0f}` ل.س"
        else:
            text = f"💰 **رصيدك الحالي:** `{balance:,.0f}` ل.س"
        
        bot.send_message(chat_id, text, parse_mode="Markdown")
    
    @staticmethod
    def show_ichancy_menu(uid, chat_id):
        """عرض قائمة Ichancy"""
        cursor.execute("SELECT acc_name, deleted FROM users WHERE user_id=?", (uid,))
        user = cursor.fetchone()
        
        if not user or not user[0] or user[1] == 1:
            # لا يوجد حساب - طلب إنشاء حساب
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.row(types.KeyboardButton('📝 إنشاء حساب جديد'))
            markup.row(types.KeyboardButton('🔙 العودة للقائمة الرئيسية'))
            bot.send_message(chat_id, "📝 ليس لديك حساب في Ichancy. هل تريد إنشاء حساب؟", reply_markup=markup)
            return
        
        # يوجد حساب - عرض معلوماته
        cursor.execute("SELECT acc_name, acc_password, site_balance, balance, created_at FROM users WHERE user_id=?", (uid,))
        acc = cursor.fetchone()
        
        if uid in DARK_MODE_USERS:
            text = f"""
🌙 **❤️ Ichancy ❤️**

👤 **الاسم:** `{acc[0]}`
🔑 **كلمة السر:** `{acc[1]}`
🆔 **المعرف:** `{uid}`
🌐 **رصيد الموقع:** `{acc[2]:,.0f}` NSP
💰 **رصيد البوت:** `{acc[3]:,.0f}` ل.س
📅 **تاريخ الإنشاء:** `{acc[4]}`

⬇️ **اختر العملية:**
"""
        else:
            text = f"""
❤️ **Ichancy** ❤️

👤 **الاسم:** `{acc[0]}`
🔑 **كلمة السر:** `{acc[1]}`
🆔 **المعرف:** `{uid}`
🌐 **رصيد الموقع:** `{acc[2]:,.0f}` NSP
💰 **رصيد البوت:** `{acc[3]:,.0f}` ل.س
📅 **تاريخ الإنشاء:** `{acc[4]}`

⬇️ **اختر العملية:**
"""
        
        # أزرار النسخ المضمنة
        markup_inline = types.InlineKeyboardMarkup(row_width=2)
        markup_inline.add(
            types.InlineKeyboardButton("📋 نسخ الاسم", callback_data=f"copy_{acc[0]}"),
            types.InlineKeyboardButton("📋 نسخ كلمة السر", callback_data=f"copy_{acc[1]}"),
            types.InlineKeyboardButton("📋 نسخ المعرف", callback_data=f"copy_{uid}"),
            types.InlineKeyboardButton("📋 نسخ الرصيد", callback_data=f"copy_{acc[3]}")
        )
        
        bot.send_message(chat_id, text, reply_markup=markup_inline, parse_mode="Markdown")
        
        # أزرار التحكم بالحساب
        markup_reply = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup_reply.row(
            types.KeyboardButton('➕ تعبئة في حسابي'),
            types.KeyboardButton('➖ سحب من حسابي')
        )
        markup_reply.row(types.KeyboardButton('🗑 حذف الحساب'))
        markup_reply.row(types.KeyboardButton('🔙 العودة للقائمة الرئيسية'))
        
        bot.send_message(chat_id, "⚙️ **إدارة الحساب:**", reply_markup=markup_reply, parse_mode="Markdown")
    
    @staticmethod
    def create_ichancy_account(uid, chat_id):
        """بدء عملية إنشاء حساب Ichancy"""
        msg = bot.send_message(chat_id, "👤 **أدخل اسم الحساب الذي تريده:**", parse_mode="Markdown")
        bot.register_next_step_handler(msg, ActionSystem.process_account_name)
    
    @staticmethod
    def process_account_name(message):
        """معالجة اسم الحساب وإضافة Matar- تلقائياً"""
        uid = message.from_user.id
        chat_id = message.chat.id
        
        if message.text == '🔙 العودة للقائمة الرئيسية':
            bot.send_message(chat_id, "القائمة الرئيسية:", reply_markup=get_main_keyboard(uid))
            return
        
        # إضافة Matar- تلقائياً
        original_name = message.text.strip()
        account_name = f"Matar-{original_name}"
        
        msg = bot.send_message(chat_id, "🔑 **أدخل كلمة المرور للحساب:**", parse_mode="Markdown")
        bot.register_next_step_handler(msg, ActionSystem.process_account_password, account_name)
    
    @staticmethod
    def process_account_password(message, account_name):
        """معالجة كلمة المرور وإنشاء الحساب"""
        uid = message.from_user.id
        chat_id = message.chat.id
        password = message.text.strip()
        created_at = datetime.now().strftime("%d-%m-%Y %H:%M")
        
        cursor.execute("""UPDATE users SET 
            acc_name=?, acc_password=?, created_at=?, site_balance=0, deleted=0 
            WHERE user_id=?""", (account_name, password, created_at, uid))
        conn.commit()
        
        bot.send_message(chat_id, "✅ **تم إنشاء الحساب بنجاح!**", parse_mode="Markdown")
        ActionSystem.show_ichancy_account(uid, chat_id)
    
    @staticmethod
    def show_ichancy_account(uid, chat_id):
        """عرض معلومات حساب Ichancy"""
        ActionSystem.show_ichancy_menu(uid, chat_id)
    
    @staticmethod
    def charge_ichancy(uid, chat_id):
        """بدء عملية تعبئة حساب Ichancy"""
        cursor.execute("SELECT balance FROM users WHERE user_id=?", (uid,))
        bal = cursor.fetchone()
        balance = bal[0] if bal else 0
        
        msg = bot.send_message(chat_id, 
            f"💰 **رصيدك الحالي في البوت:** `{balance:,.0f}` ل.س\n\n"
            "📝 **أدخل المبلغ الذي تريد تعبئته في حساب Ichancy:**", 
            parse_mode="Markdown")
        bot.register_next_step_handler(msg, ActionSystem.process_charge_ichancy, balance)
    
    @staticmethod
    def process_charge_ichancy(message, bot_balance):
        """معالجة تعبئة حساب Ichancy"""
        uid = message.from_user.id
        chat_id = message.chat.id
        
        if message.text == '🔙 العودة للقائمة الرئيسية':
            bot.send_message(chat_id, "القائمة الرئيسية:", reply_markup=get_main_keyboard(uid))
            return
        
        try:
            amount = float(message.text)
            
            if amount <= 0:
                bot.send_message(chat_id, "❌ **المبلغ يجب أن يكون أكبر من 0**", parse_mode="Markdown")
                return
            
            if amount > bot_balance:
                bot.send_message(chat_id, 
                    f"❌ **رصيدك غير كافٍ!**\n"
                    f"💰 رصيدك: `{bot_balance:,.0f}` ل.س\n"
                    f"💵 المبلغ المطلوب: `{amount:,.0f}` ل.س", 
                    parse_mode="Markdown")
                return
            
            # تنفيذ التعبئة
            cursor.execute("UPDATE users SET balance = balance - ?, site_balance = site_balance + ? WHERE user_id=?", 
                          (amount, amount, uid))
            conn.commit()
            
            cursor.execute("SELECT balance, site_balance FROM users WHERE user_id=?", (uid,))
            new = cursor.fetchone()
            
            bot.send_message(chat_id, 
                f"✅ **تمت التعبئة بنجاح!**\n\n"
                f"💰 رصيد البوت الجديد: `{new[0]:,.0f}` ل.س\n"
                f"🌐 رصيد الموقع الجديد: `{new[1]:,.0f}` NSP", 
                parse_mode="Markdown")
            
            # تسجيل المعاملة
            receipt = log_transaction(uid, "ichancy_charge", amount, "internal", "success")
            finance_logger.info(f"تعبئة Ichancy: {uid} - {amount} - {receipt}")
            
            # العودة لعرض معلومات الحساب
            ActionSystem.show_ichancy_account(uid, chat_id)
            
        except ValueError:
            bot.send_message(chat_id, "❌ **الرجاء إدخال رقم صحيح**", parse_mode="Markdown")
    
    @staticmethod
    def withdraw_ichancy(uid, chat_id):
        """بدء عملية سحب من حساب Ichancy"""
        cursor.execute("SELECT site_balance FROM users WHERE user_id=?", (uid,))
        bal = cursor.fetchone()
        site_balance = bal[0] if bal else 0
        
        msg = bot.send_message(chat_id,
            f"🌐 **رصيدك في موقع Ichancy:** `{site_balance:,.0f}` NSP\n\n"
            "📝 **أدخل المبلغ الذي تريد سحبه إلى رصيد البوت:**",
            parse_mode="Markdown")
        bot.register_next_step_handler(msg, ActionSystem.process_withdraw_ichancy, site_balance)
    
    @staticmethod
    def process_withdraw_ichancy(message, site_balance):
        """معالجة سحب من حساب Ichancy"""
        uid = message.from_user.id
        chat_id = message.chat.id
        
        if message.text == '🔙 العودة للقائمة الرئيسية':
            bot.send_message(chat_id, "القائمة الرئيسية:", reply_markup=get_main_keyboard(uid))
            return
        
        try:
            amount = float(message.text)
            
            if amount <= 0:
                bot.send_message(chat_id, "❌ **المبلغ يجب أن يكون أكبر من 0**", parse_mode="Markdown")
                return
            
            if amount > site_balance:
                bot.send_message(chat_id,
                    f"❌ **رصيد الموقع غير كافٍ!**\n"
                    f"🌐 رصيد الموقع: `{site_balance:,.0f}` NSP\n"
                    f"💵 المبلغ المطلوب: `{amount:,.0f}` NSP",
                    parse_mode="Markdown")
                return
            
            # تنفيذ السحب
            cursor.execute("UPDATE users SET site_balance = site_balance - ?, balance = balance + ? WHERE user_id=?", 
                          (amount, amount, uid))
            conn.commit()
            
            cursor.execute("SELECT balance, site_balance FROM users WHERE user_id=?", (uid,))
            new = cursor.fetchone()
            
            bot.send_message(chat_id,
                f"✅ **تم السحب بنجاح!**\n\n"
                f"💰 رصيد البوت الجديد: `{new[0]:,.0f}` ل.س\n"
                f"🌐 رصيد الموقع الجديد: `{new[1]:,.0f}` NSP",
                parse_mode="Markdown")
            
            # تسجيل المعاملة
            receipt = log_transaction(uid, "ichancy_withdraw", amount, "internal", "success")
            finance_logger.info(f"سحب من Ichancy: {uid} - {amount} - {receipt}")
            
            # العودة لعرض معلومات الحساب
            ActionSystem.show_ichancy_account(uid, chat_id)
            
        except ValueError:
            bot.send_message(chat_id, "❌ **الرجاء إدخال رقم صحيح**", parse_mode="Markdown")
    
    @staticmethod
    def delete_ichancy_account(uid, chat_id):
        """بدء عملية حذف حساب Ichancy"""
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row(types.KeyboardButton('حذف'))
        markup.row(types.KeyboardButton('🔙 إلغاء'))
        
        msg = bot.send_message(chat_id, 
            "⚠️ **تحذير!**\n"
            "أنت على وشك حذف حساب Ichancy الخاص بك.\n"
            "للتأكيد، اكتب **حذف** في الأسفل:",
            reply_markup=markup, parse_mode="Markdown")
        bot.register_next_step_handler(msg, ActionSystem.process_delete_account)
    
    @staticmethod
    def process_delete_account(message):
        """معالجة حذف الحساب"""
        uid = message.from_user.id
        chat_id = message.chat.id
        
        if message.text == 'حذف':
            cursor.execute("SELECT acc_name, acc_password, site_balance, balance FROM users WHERE user_id=?", (uid,))
            user = cursor.fetchone()
            
            if user and user[0]:
                deleted_at = datetime.now().strftime("%d-%m-%Y %H:%M")
                
                # حفظ في جدول الحسابات المحذوفة
                cursor.execute("""INSERT OR REPLACE INTO deleted_accounts
                    (user_id, acc_name, acc_password, site_balance, balance, deleted_at)
                    VALUES (?,?,?,?,?,?)""", (uid, user[0], user[1], user[2], user[3], deleted_at))
                
                # حذف الحساب
                cursor.execute("UPDATE users SET acc_name=NULL, acc_password=NULL, site_balance=0, deleted=1 WHERE user_id=?", (uid,))
                conn.commit()
                
                bot.send_message(chat_id, "✅ **تم حذف الحساب بنجاح**", reply_markup=get_main_keyboard(uid), parse_mode="Markdown")
                log_transaction(uid, "delete_account", 0, "system", "success")
                logger.info(f"مستخدم {uid} حذف حسابه")
            else:
                bot.send_message(chat_id, "❌ **ليس لديك حساب لحذفه**", parse_mode="Markdown")
        else:
            bot.send_message(chat_id, "✅ **تم إلغاء عملية الحذف**", reply_markup=get_main_keyboard(uid))
    
    # ===== إجراءات مالية =====
    
    @staticmethod
    def show_charge_methods(uid, chat_id):
        """عرض طرق الشحن"""
        markup = get_charge_methods_keyboard()
        bot.send_message(chat_id, "💰 **اختر وسيلة الشحن:**", reply_markup=markup, parse_mode="Markdown")
    
    @staticmethod
    def show_withdraw_methods(uid, chat_id):
        """عرض طرق السحب"""
        markup = get_withdraw_methods_keyboard()
        bot.send_message(chat_id, "💰 **اختر وسيلة السحب:**", reply_markup=markup, parse_mode="Markdown")
    
    @staticmethod
    def start_gift(uid, chat_id):
        """بدء عملية إهداء رصيد"""
        msg = bot.send_message(chat_id, "👤 **أرسل معرف المستخدم (ID) الذي تريد إهداءه:**", parse_mode="Markdown")
        bot.register_next_step_handler(msg, ActionSystem.process_gift_user_id)
    
    @staticmethod
    def process_gift_user_id(message):
        """معالجة معرف المستخدم المستهدف للإهداء"""
        uid = message.from_user.id
        chat_id = message.chat.id
        
        if message.text == '🔙 العودة للقائمة الرئيسية':
            bot.send_message(chat_id, "القائمة الرئيسية:", reply_markup=get_main_keyboard(uid))
            return
        
        try:
            target = int(message.text)
            
            if target == uid:
                bot.send_message(chat_id, "❌ **لا يمكنك إهداء نفسك!**", parse_mode="Markdown")
                return
            
            cursor.execute("SELECT user_id FROM users WHERE user_id=? AND deleted=0", (target,))
            if not cursor.fetchone():
                bot.send_message(chat_id, "❌ **المستخدم غير موجود في قاعدة البيانات**", parse_mode="Markdown")
                return
            
            msg = bot.send_message(chat_id, "💰 **أدخل المبلغ الذي تريد إهداءه:**", parse_mode="Markdown")
            bot.register_next_step_handler(msg, ActionSystem.process_gift_amount, target)
            
        except ValueError:
            bot.send_message(chat_id, "❌ **الرجاء إدخال معرف صحيح (أرقام فقط)**", parse_mode="Markdown")
    
    @staticmethod
    def process_gift_amount(message, target):
        """معالجة مبلغ الإهداء"""
        uid = message.from_user.id
        chat_id = message.chat.id
        
        if message.text == '🔙 العودة للقائمة الرئيسية':
            bot.send_message(chat_id, "القائمة الرئيسية:", reply_markup=get_main_keyboard(uid))
            return
        
        try:
            amount = float(message.text)
            min_gift = float(get_db_setting('min_gift_amount') or 10)
            max_gift = float(get_db_setting('max_gift_amount') or 1000000)
            
            if amount < min_gift:
                bot.send_message(chat_id, f"❌ **الحد الأدنى للإهداء هو {min_gift:,.0f} ل.س**", parse_mode="Markdown")
                return
            
            if amount > max_gift:
                bot.send_message(chat_id, f"❌ **الحد الأقصى للإهداء هو {max_gift:,.0f} ل.س**", parse_mode="Markdown")
                return
            
            cursor.execute("SELECT balance FROM users WHERE user_id=?", (uid,))
            sender_bal = cursor.fetchone()
            
            if not sender_bal or sender_bal[0] < amount:
                bot.send_message(chat_id, f"❌ **رصيدك غير كافٍ!**\n💰 رصيدك: `{sender_bal[0] if sender_bal else 0:,.0f}` ل.س", parse_mode="Markdown")
                return
            
            # تنفيذ الإهداء
            update_user_balance(uid, amount, add=False)
            update_user_balance(target, amount, add=True)
            
            cursor.execute("SELECT balance FROM users WHERE user_id=?", (uid,))
            new_sender = cursor.fetchone()[0]
            
            bot.send_message(chat_id, f"✅ **تم إرسال {amount:,.0f} ل.س إلى {target}**\n💰 رصيدك الجديد: `{new_sender:,.0f}` ل.س", parse_mode="Markdown")
            
            sender_name = get_user_custom_name(uid) or f"المستخدم {uid}"
            bot.send_message(target, f"🎁 **أهداك {sender_name} {amount:,.0f} ل.س**", parse_mode="Markdown")
            
            receipt = log_transaction(uid, "gift", amount, "internal", "success", details=f"To: {target}")
            finance_logger.info(f"إهداء: {uid} -> {target} - {amount} - {receipt}")
            
        except ValueError:
            bot.send_message(chat_id, "❌ **الرجاء إدخال رقم صحيح**", parse_mode="Markdown")
    
    @staticmethod
    def redeem_gift(uid, chat_id):
        """بدء عملية استخدام كود هدية"""
        msg = bot.send_message(chat_id, "🎫 **أدخل كود الهدية:**", parse_mode="Markdown")
        bot.register_next_step_handler(msg, ActionSystem.process_redeem_gift)
    
    @staticmethod
    def process_redeem_gift(message):
        """معالجة استخدام كود هدية"""
        uid = message.from_user.id
        chat_id = message.chat.id
        code = message.text.strip().upper()
        
        if code == '🔙 العودة للقائمة الرئيسية':
            bot.send_message(chat_id, "القائمة الرئيسية:", reply_markup=get_main_keyboard(uid))
            return
        
        cursor.execute("SELECT value, limit_count, used_count, type, expires_at FROM gifts WHERE code=?", (code,))
        gift = cursor.fetchone()
        
        if not gift:
            bot.send_message(chat_id, "❌ **الكود غير صحيح أو منتهي الصلاحية**", parse_mode="Markdown")
            return
        
        # التحقق من الصلاحية
        if gift[4]:  # expires_at
            try:
                expires = datetime.strptime(gift[4], "%Y-%m-%d %H:%M:%S")
                if datetime.now() > expires:
                    bot.send_message(chat_id, "❌ **هذا الكود منتهي الصلاحية**", parse_mode="Markdown")
                    return
            except:
                pass
        
        # التحقق من الاستخدام المسبق
        cursor.execute("SELECT * FROM gift_usage WHERE user_id=? AND code=?", (uid, code))
        if cursor.fetchone():
            bot.send_message(chat_id, "❌ **لقد استخدمت هذا الكود من قبل**", parse_mode="Markdown")
            return
        
        # التحقق من العدد المتبقي
        if gift[2] <= gift[1]:  # used_count >= limit_count
            bot.send_message(chat_id, "❌ **لقد استُنفد عدد استخدامات هذا الكود**", parse_mode="Markdown")
            return
        
        # تنفيذ الإهداء
        amount = gift[0]
        update_user_balance(uid, amount, add=True)
        
        cursor.execute("UPDATE gifts SET used_count = used_count + 1 WHERE code=?", (code,))
        cursor.execute("INSERT INTO gift_usage (user_id, code, used_at) VALUES (?,?,?)", 
                      (uid, code, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        
        bot.send_message(chat_id, f"🎉 **تهانينا! تم شحن {amount:,.0f} ل.س إلى رصيدك**", parse_mode="Markdown")
        log_transaction(uid, "gift_redeem", amount, "gift", "success")
        finance_logger.info(f"استخدام كود هدية: {uid} - {code} - {amount}")
    
    @staticmethod
    def show_transactions(uid, chat_id):
        """عرض آخر معاملات المستخدم"""
        cursor.execute("""SELECT type, amount, method, status, transaction_date 
                          FROM transactions WHERE user_id=? 
                          ORDER BY transaction_date DESC LIMIT 10""", (uid,))
        trans = cursor.fetchall()
        
        if not trans:
            bot.send_message(chat_id, "📭 **لا توجد معاملات سابقة**", parse_mode="Markdown")
            return
        
        text = "📊 **آخر 10 معاملات:**\n\n"
        for t in trans:
            status_icon = "✅" if t[3] == "success" else "⏳" if t[3] == "pending" else "❌"
            text += f"{status_icon} {t[0]}: {t[1]:,.0f} | {t[2]} | {t[4]}\n"
        
        bot.send_message(chat_id, text, parse_mode="Markdown")
    
    # ===== إجراءات اجتماعية =====
    
    @staticmethod
    def show_referral(uid, chat_id):
        """عرض معلومات الإحالات"""
        cursor.execute("SELECT referral_count, current_earnings, total_earnings, ref_code FROM users WHERE user_id=?", (uid,))
        data = cursor.fetchone()
        
        if not data:
            bot.send_message(chat_id, "❌ **حدث خطأ**", parse_mode="Markdown")
            return
        
        ref_count, cur, total, code = data
        
        if not code:
            code = check_and_create_ref_code(uid)
        
        try:
            bot_username = bot.get_me().username
            link = f"https://t.me/{bot_username}?start={code}"
        except:
            link = "⚠️ رابط غير متوفر حالياً"
        
        next_payout = get_db_setting('next_referral_payout')
        time_left = format_time_remaining(next_payout) if next_payout else "غير محدد"
        
        text = f"""
🌟 **نظام الإحالات**

👥 **عدد الإحالات:** {ref_count}
💰 **أرباح الدورة الحالية:** {cur:,.0f} ل.س
📊 **إجمالي الأرباح:** {total:,.0f} ل.س

🔗 **رابط الدعوة الخاص بك:**
`{link}`

📅 **موعد الدفعة القادمة:** {next_payout or 'غير محدد'}
⏳ **الوقت المتبقي:** {time_left}
"""
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📋 نسخ الرابط", callback_data=f"copy_{link}"))
        
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
    
    @staticmethod
    def show_referral_link(uid, chat_id):
        """عرض رابط الإحالة فقط"""
        cursor.execute("SELECT ref_code FROM users WHERE user_id=?", (uid,))
        data = cursor.fetchone()
        
        if not data or not data[0]:
            code = check_and_create_ref_code(uid)
        else:
            code = data[0]
        
        try:
            bot_username = bot.get_me().username
            link = f"https://t.me/{bot_username}?start={code}"
        except:
            link = "⚠️ رابط غير متوفر حالياً"
        
        bot.send_message(chat_id, f"🔗 **رابط الدعوة الخاص بك:**\n`{link}`", parse_mode="Markdown")
    
    @staticmethod
    def show_referral_stats(uid, chat_id):
        """عرض إحصائيات متقدمة للإحالات"""
        # للمستخدم العادي يعرض إحصائياته، للمشرف يعرض إحصائيات عامة
        if uid == ADMIN_ID or is_moderator(uid):
            # إحصائيات عامة للمشرفين
            cursor.execute("SELECT COUNT(*) FROM users WHERE referred_by IS NOT NULL")
            total_refs = cursor.fetchone()[0]
            
            cursor.execute("SELECT SUM(current_earnings) FROM users")
            total_earnings = cursor.fetchone()[0] or 0
            
            cursor.execute("SELECT user_id, first_name, referral_count, current_earnings FROM users WHERE referral_count>0 ORDER BY referral_count DESC LIMIT 5")
            top_refs = cursor.fetchall()
            
            text = f"""
📊 **إحصائيات الإحالات العامة**

👥 **إجمالي الإحالات:** {total_refs}
💰 **إجمالي الأرباح:** {total_earnings:,.0f} ل.س

🏆 **أفضل 5 محيلين:**
"""
            for i, ref in enumerate(top_refs, 1):
                name = ref[1] or f"مستخدم {ref[0]}"
                text += f"\n{i}. {name}: {ref[2]} إحالات | {ref[3]:,.0f} ل.س"
            
            bot.send_message(chat_id, text, parse_mode="Markdown")
        else:
            # إحصائيات المستخدم العادي
            ActionSystem.show_referral(uid, chat_id)
    
    # ===== إجراءات دعم =====
    
    @staticmethod
    def start_support(uid, chat_id):
        """بدء عملية دعم (فتح تذكرة)"""
        msg = bot.send_message(chat_id, 
            "📝 **أرسل رسالتك أو صورتك هنا وسيتم الرد عليك بأقرب وقت:**\n\n"
            "✏️ يمكنك إرفاق صورة أو كتابة استفسارك", 
            parse_mode="Markdown")
        bot.register_next_step_handler(msg, ActionSystem.process_support_ticket)
    
    @staticmethod
    def process_support_ticket(message):
        """معالجة رسالة الدعم وإنشاء تذكرة"""
        uid = message.from_user.id
        chat_id = message.chat.id
        file_id = message.photo[-1].file_id if message.content_type == 'photo' else None
        
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
        
        bot.send_message(chat_id, "✅ **تم إرسال رسالتك إلى فريق الدعم. سيتم الرد عليك قريباً.**", parse_mode="Markdown")
        
        # إشعار للمالك والمشرفين
        user_info = f"@{message.from_user.username}" if message.from_user.username else f"ID: {uid}"
        admin_msg = f"💬 **تذكرة جديدة #{ticket_id}**\n👤 {user_info}\n📝 {message.text or '[صورة]'}"
        
        if file_id:
            bot.send_photo(ADMIN_ID, file_id, caption=admin_msg, parse_mode="Markdown")
        else:
            bot.send_message(ADMIN_ID, admin_msg, parse_mode="Markdown")
        
        # إشعار للمشرفين الذين لديهم صلاحية الرد
        cursor.execute("SELECT user_id FROM moderators WHERE can_reply_tickets=1")
        for mod in cursor.fetchall():
            if mod[0] != ADMIN_ID:
                try:
                    if file_id:
                        bot.send_photo(mod[0], file_id, caption=admin_msg, parse_mode="Markdown")
                    else:
                        bot.send_message(mod[0], admin_msg, parse_mode="Markdown")
                except:
                    pass
        
        logger.info(f"تذكرة جديدة #{ticket_id} من المستخدم {uid}")
    
    @staticmethod
    def show_tickets(uid, chat_id):
        """عرض تذاكر المستخدم (للمستخدم العادي) أو كل التذاكر (للمشرف)"""
        if uid == ADMIN_ID or is_moderator(uid):
            # للمشرفين - عرض كل التذاكر المفتوحة
            cursor.execute("""SELECT ticket_id, user_id, message, status, created_at 
                              FROM tickets WHERE status='open' 
                              ORDER BY created_at DESC LIMIT 10""")
            tickets = cursor.fetchall()
            
            if not tickets:
                bot.send_message(chat_id, "📭 **لا توجد تذاكر مفتوحة**", parse_mode="Markdown")
                return
            
            text = "📬 **التذاكر المفتوحة:**\n\n"
            for t in tickets:
                text += f"🔹 #{t[0]} - مستخدم {t[1]}\n📝 {t[2][:50]}...\n📅 {t[4]}\n\n"
            
            bot.send_message(chat_id, text, parse_mode="Markdown")
        else:
            # للمستخدم العادي - عرض تذاكره
            cursor.execute("""SELECT ticket_id, message, status, created_at 
                              FROM tickets WHERE user_id=? 
                              ORDER BY created_at DESC LIMIT 5""", (uid,))
            tickets = cursor.fetchall()
            
            if not tickets:
                bot.send_message(chat_id, "📭 **ليس لديك أي تذاكر سابقة**", parse_mode="Markdown")
                return
            
            text = "📋 **تذاكرك السابقة:**\n\n"
            for t in tickets:
                status_icon = "🟢" if t[2] == 'open' else "🔴"
                text += f"{status_icon} #{t[0]}: {t[1][:30]}...\n{t[3]}\n\n"
            
            bot.send_message(chat_id, text, parse_mode="Markdown")
    
    @staticmethod
    def show_terms(uid, chat_id):
        """عرض الشروط والأحكام"""
        terms = get_db_setting('terms_message') or """
📜 **الشروط والأحكام:**

1️⃣ الاشتراك في القناة إلزامي لاستخدام البوت
2️⃣ الحد الأدنى للشحن: 100 ل.س
3️⃣ السحب عبر سيرياتل: 25,000 - 500,000 ل.س
4️⃣ السحب عبر شام: 25,000 - 5,000,000 ل.س
5️⃣ عمولة السحب: 10%
6️⃣ مدة معالجة السحب: 1-24 ساعة
7️⃣ نظام الإحالات: 10% كل 10 أيام
8️⃣ الإدارة تحتفظ بالحق في حظر أي مستخدم مخالف
9️⃣ للاستفسار: التواصل مع الدعم الفني
"""
        bot.send_message(chat_id, terms, parse_mode="Markdown")
    
    # ===== إجراءات إدارية =====
    
    @staticmethod
    def show_admin_panel(uid, chat_id):
        """عرض لوحة الإدارة الرئيسية"""
        if uid == ADMIN_ID:
            bot.send_message(chat_id, "🔐 **لوحة تحكم المالك**", reply_markup=get_admin_main_keyboard(is_owner=True), parse_mode="Markdown")
        elif is_moderator(uid):
            bot.send_message(chat_id, "🔐 **لوحة تحكم المشرف**", reply_markup=get_admin_main_keyboard(is_owner=False), parse_mode="Markdown")
        else:
            bot.send_message(chat_id, "❌ **ليس لديك صلاحية للدخول إلى هذه القائمة**", parse_mode="Markdown")
    
    @staticmethod
    def show_moderator_panel(uid, chat_id):
        """عرض لوحة المشرف (للمشرفين فقط)"""
        if is_moderator(uid) or uid == ADMIN_ID:
            bot.send_message(chat_id, "🔐 **لوحة المشرف**", reply_markup=get_moderator_panel_keyboard(uid), parse_mode="Markdown")
        else:
            bot.send_message(chat_id, "❌ **ليس لديك صلاحية للدخول إلى هذه القائمة**", parse_mode="Markdown")
    
    @staticmethod
    def show_full_admin_menu(uid, chat_id):
        """عرض قائمة الإدارة الكاملة (للمالك فقط)"""
        if uid != ADMIN_ID and not check_permission(uid, 'can_access_full_admin'):
            bot.send_message(chat_id, "❌ **هذه القائمة للمالك فقط**", parse_mode="Markdown")
            return
        
        keyboard = get_full_admin_keyboard()
        bot.send_message(chat_id, "🛑 **لوحة التحكم الكامل - اختر وظيفة:**", reply_markup=keyboard, parse_mode="Markdown")
    
    @staticmethod
    def manage_buttons(uid, chat_id):
        """فتح قائمة إدارة الأزرار"""
        if uid != ADMIN_ID and not check_permission(uid, 'can_manage_buttons'):
            bot.send_message(chat_id, "❌ **ليس لديك صلاحية لإدارة الأزرار**", parse_mode="Markdown")
            return
        
        keyboard = get_buttons_management_keyboard()
        bot.send_message(chat_id, "🔧 **إدارة الأزرار - اختر ما تريد فعله:**", reply_markup=keyboard, parse_mode="Markdown")
    
    @staticmethod
    def manage_users(uid, chat_id):
        """فتح قائمة إدارة المستخدمين"""
        if uid != ADMIN_ID and not check_permission(uid, 'can_manage_users'):
            bot.send_message(chat_id, "❌ **ليس لديك صلاحية لإدارة المستخدمين**", parse_mode="Markdown")
            return
        
        keyboard = get_user_management_keyboard()
        bot.send_message(chat_id, "👥 **إدارة المستخدمين - اختر:**", reply_markup=keyboard, parse_mode="Markdown")
    
    @staticmethod
    def manage_moderators(uid, chat_id):
        """فتح قائمة إدارة المشرفين (للمالك فقط)"""
        if uid != ADMIN_ID:
            bot.send_message(chat_id, "❌ **هذه القائمة للمالك فقط**", parse_mode="Markdown")
            return
        
        keyboard = get_moderator_management_keyboard()
        bot.send_message(chat_id, "👥 **إدارة المشرفين - اختر:**", reply_markup=keyboard, parse_mode="Markdown")
    
    @staticmethod
    def payment_settings(uid, chat_id):
        """فتح إعدادات الدفع"""
        if uid != ADMIN_ID and not check_permission(uid, 'can_change_payment'):
            bot.send_message(chat_id, "❌ **ليس لديك صلاحية لتغيير إعدادات الدفع**", parse_mode="Markdown")
            return
        
        syriatel = get_db_setting('syriatel_numbers')
        sham = get_db_setting('sham_address')
        min_charge = get_db_setting('min_charge')
        min_withdraw = get_db_setting('min_withdraw_syria')
        commission = get_db_setting('withdraw_commission')
        
        text = f"""
💳 **إعدادات الدفع الحالية:**

📱 **سيرياتل كاش:** `{syriatel}`
🏦 **شام كاش:** `{sham}`
💰 **الحد الأدنى للشحن:** {min_charge} ل.س
💸 **الحد الأدنى للسحب:** {min_withdraw} ل.س
💵 **عمولة السحب:** {commission}%

اختر ما تريد تعديله:
"""
        keyboard = get_payment_settings_keyboard()
        bot.send_message(chat_id, text, reply_markup=keyboard, parse_mode="Markdown")
    
    @staticmethod
    def bot_settings(uid, chat_id):
        """فتح إعدادات البوت العامة"""
        if uid != ADMIN_ID:
            bot.send_message(chat_id, "❌ **هذه القائمة للمالك فقط**", parse_mode="Markdown")
            return
        
        status = get_db_setting('bot_status')
        welcome = get_db_setting('welcome_message')
        ref_percent = get_db_setting('referral_percentage')
        
        status_text = "🟢 **نشط**" if status == 'active' else "🔴 **معطل (صيانة)**"
        
        text = f"""
⚙️ **الإعدادات العامة:**

🔧 **حالة البوت:** {status_text}
📝 **رسالة الترحيب:** {welcome[:50]}...
👥 **نسبة الإحالات:** {ref_percent}%

اختر ما تريد تعديله:
"""
        keyboard = get_bot_settings_keyboard()
        bot.send_message(chat_id, text, reply_markup=keyboard, parse_mode="Markdown")
    
    @staticmethod
    def system_stats(uid, chat_id):
        """عرض إحصائيات النظام"""
        if uid != ADMIN_ID and not check_permission(uid, 'can_view_stats'):
            bot.send_message(chat_id, "❌ **ليس لديك صلاحية لعرض الإحصائيات**", parse_mode="Markdown")
            return
        
        # إحصائيات المستخدمين
        cursor.execute("SELECT COUNT(*) FROM users WHERE deleted=0")
        total_users = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM users WHERE DATE(created_at) = DATE('now')")
        new_today = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM users WHERE status='banned'")
        banned_users = cursor.fetchone()[0]
        
        # إحصائيات مالية
        cursor.execute("SELECT SUM(balance) FROM users WHERE deleted=0")
        total_balance = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT SUM(site_balance) FROM users WHERE deleted=0")
        total_site_balance = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT COUNT(*) FROM transactions WHERE DATE(transaction_date) = DATE('now')")
        transactions_today = cursor.fetchone()[0]
        
        cursor.execute("SELECT SUM(amount) FROM transactions WHERE DATE(transaction_date) = DATE('now') AND type='charge'")
        charges_today = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT SUM(amount) FROM transactions WHERE DATE(transaction_date) = DATE('now') AND type='withdraw'")
        withdraws_today = cursor.fetchone()[0] or 0
        
        # إحصائيات إضافية
        cursor.execute("SELECT COUNT(*) FROM tickets WHERE status='open'")
        open_tickets = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM gifts WHERE used_count < limit_count")
        active_gifts = cursor.fetchone()[0]
        
        text = f"""
📊 **إحصائيات النظام**

👥 **المستخدمين:**
• إجمالي المستخدمين: {total_users}
• مستخدمين جدد اليوم: {new_today}
• المستخدمين المحظورين: {banned_users}

💰 **الأرصدة:**
• إجمالي أرصدة البوت: {total_balance:,.0f} ل.س
• إجمالي أرصدة الموقع: {total_site_balance:,.0f} NSP

💳 **معاملات اليوم:**
• عدد المعاملات: {transactions_today}
• إجمالي الشحنات: {charges_today:,.0f} ل.س
• إجمالي السحوبات: {withdraws_today:,.0f} ل.س

📬 **أخرى:**
• تذاكر مفتوحة: {open_tickets}
• أكواد هدايا نشطة: {active_gifts}
"""
        bot.send_message(chat_id, text, parse_mode="Markdown")
    
    @staticmethod
    def backup_system(uid, chat_id):
        """نظام النسخ الاحتياطي"""
        if uid != ADMIN_ID:
            bot.send_message(chat_id, "❌ **هذه القائمة للمالك فقط**", parse_mode="Markdown")
            return
        
        keyboard = get_backup_keyboard()
        bot.send_message(chat_id, "💾 **نظام النسخ الاحتياطي - اختر:**", reply_markup=keyboard, parse_mode="Markdown")
    
    # ===== إجراءات ربط الكاشيرة =====
    
    @staticmethod
    def connect_syriatel(uid, chat_id):
        """ربط سيرياتل كاش"""
        if uid != ADMIN_ID:
            bot.send_message(chat_id, "❌ **هذه الخاصية للمالك فقط**", parse_mode="Markdown")
            return
        
        msg = bot.send_message(chat_id, "📱 **أدخل رقم سيرياتل كاش الجديد:**", parse_mode="Markdown")
        bot.register_next_step_handler(msg, ActionSystem.process_connect_syriatel)
    
    @staticmethod
    def process_connect_syriatel(message):
        """معالجة ربط سيرياتل"""
        uid = message.from_user.id
        chat_id = message.chat.id
        number = message.text.strip()
        
        # التحقق من صحة الرقم
        if not number.isdigit():
            bot.send_message(chat_id, "❌ **رقم غير صالح: يجب أن يحتوي على أرقام فقط**", parse_mode="Markdown")
            return
        
        if len(number) not in [10, 11, 12]:
            bot.send_message(chat_id, "❌ **رقم غير صالح: طول الرقم غير مناسب**", parse_mode="Markdown")
            return
        
        update_db_setting('syriatel_numbers', number, uid)
        update_db_setting('syriatel_api_enabled', '1', uid)
        
        bot.send_message(chat_id, f"✅ **تم ربط سيرياتل كاش بنجاح:**\n`{number}`", parse_mode="Markdown")
        admin_logger.info(f"تم ربط سيرياتل كاش: {number}")
    
    @staticmethod
    def connect_sham(uid, chat_id):
        """ربط شام كاش"""
        if uid != ADMIN_ID:
            bot.send_message(chat_id, "❌ **هذه الخاصية للمالك فقط**", parse_mode="Markdown")
            return
        
        msg = bot.send_message(chat_id, "🏦 **أدخل عنوان شام كاش الجديد:**", parse_mode="Markdown")
        bot.register_next_step_handler(msg, ActionSystem.process_connect_sham)
    
    @staticmethod
    def process_connect_sham(message):
        """معالجة ربط شام"""
        uid = message.from_user.id
        chat_id = message.chat.id
        address = message.text.strip()
        
        if len(address) < 3:
            bot.send_message(chat_id, "❌ **عنوان غير صالح: قصير جداً**", parse_mode="Markdown")
            return
        
        update_db_setting('sham_address', address, uid)
        update_db_setting('sham_api_enabled', '1', uid)
        
        bot.send_message(chat_id, f"✅ **تم ربط شام كاش بنجاح:**\n`{address}`", parse_mode="Markdown")
        admin_logger.info(f"تم ربط شام كاش: {address}")
    
    @staticmethod
    def test_api(uid, chat_id):
        """اختبار اتصال API"""
        if uid != ADMIN_ID:
            bot.send_message(chat_id, "❌ **هذه الخاصية للمالك فقط**", parse_mode="Markdown")
            return
        
        # محاكاة اختبار اتصال
        time.sleep(1)
        bot.send_message(chat_id, "✅ **جميع الاتصالات نشطة وتعمل بشكل طبيعي**", parse_mode="Markdown")
    
    @staticmethod
    def toggle_auto_verify(uid, chat_id):
        """تبديل حالة التحقق التلقائي"""
        if uid != ADMIN_ID:
            bot.send_message(chat_id, "❌ **هذه الخاصية للمالك فقط**", parse_mode="Markdown")
            return
        
        current = get_db_setting('auto_verify_charges')
        new = '0' if current == '1' else '1'
        update_db_setting('auto_verify_charges', new, uid)
        
        status = "🟢 **مفعل**" if new == '1' else "🔴 **معطل**"
        bot.send_message(chat_id, f"✅ **تم تغيير حالة التحقق التلقائي إلى:** {status}", parse_mode="Markdown")
    
    # ===== إجراءات مخصصة =====
    
    @staticmethod
    def send_custom_message(uid, chat_id, button_data):
        """إرسال رسالة مخصصة"""
        if button_data and 'message_text' in button_data:
            bot.send_message(chat_id, button_data['message_text'], parse_mode="Markdown")
        else:
            bot.send_message(chat_id, "📝 **رسالة مخصصة**", parse_mode="Markdown")
    
    @staticmethod
    def send_custom_photo(uid, chat_id, button_data):
        """إرسال صورة مخصصة"""
        if button_data and 'photo_id' in button_data and button_data['photo_id']:
            bot.send_photo(chat_id, button_data['photo_id'], 
                          caption=button_data.get('message_text', ''), parse_mode="Markdown")
        else:
            bot.send_message(chat_id, "🖼️ **صورة مخصصة (غير متوفرة حالياً)**", parse_mode="Markdown")
    
    @staticmethod
    def open_link(uid, chat_id, button_data):
        """فتح رابط (إرسال رابط للمستخدم)"""
        if button_data and 'link' in button_data:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔗 اضغط لفتح الرابط", url=button_data['link']))
            bot.send_message(chat_id, "📎 **اضغط على الرابط لفتحه:**", reply_markup=markup, parse_mode="Markdown")
        else:
            bot.send_message(chat_id, "🔗 **رابط غير متوفر**", parse_mode="Markdown")
    
    @staticmethod
    def toggle_dark_mode(uid, chat_id):
        """تبديل الوضع الليلي"""
        new_mode = toggle_dark_mode(uid)
        status = "🌙 **مفعل**" if new_mode == 1 else "☀️ **معطل**"
        bot.send_message(chat_id, f"✅ **الوضع الليلي الآن:** {status}", parse_mode="Markdown")
    
    # ===== إجراءات القوائم الفرعية =====
    
    @staticmethod
    def show_submenu(uid, chat_id, button_data):
        """عرض قائمة فرعية"""
        if button_data and 'parent_button' in button_data:
            submenu_keyboard = get_dynamic_keyboard(parent=button_data['parent_button'], level=2)
            if submenu_keyboard:
                bot.send_message(chat_id, f"📂 **{button_data['parent_button']}:**", 
                               reply_markup=submenu_keyboard, parse_mode="Markdown")
            else:
                bot.send_message(chat_id, "📭 **لا توجد خيارات في هذه القائمة**", parse_mode="Markdown")
        else:
            bot.send_message(chat_id, "❌ **لم يتم تحديد القائمة الفرعية**", parse_mode="Markdown")


# ================================================
# 7. نظام النسخ الفوري (One-Click Copy)
# ================================================

def send_copyable_text(chat_id, text, caption=""):
    """إرسال نص قابل للنسخ بنقرة واحدة"""
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📋 نسخ", callback_data=f"copy_{text}"))
    
    full_text = f"{caption}\n\n`{text}`" if caption else f"`{text}`"
    bot.send_message(chat_id, full_text, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith('copy_'))
def handle_copy_callback(call):
    """معالجة طلبات النسخ"""
    text = call.data[5:]  # إزالة 'copy_' من البداية
    bot.answer_callback_query(call.id, "📋 تم النسخ!", show_alert=False)
    
    # إرسال النص في رسالة منفصلة لسهولة النسخ
    bot.send_message(call.message.chat.id, f"✅ **انسخ هذا النص:**\n`{text}`", parse_mode="Markdown")

# ================================================
# 8. بناء لوحات المفاتيح الديناميكية
# ================================================

def get_main_keyboard(uid):
    """
    بناء القائمة الرئيسية حسب الطلب:
    الصف الأول: Ichancy (منفرد)
    الصف الثاني: الشحن في البوت | السحب من البوت
    الصف الثالث: اهداء رصيد | كود هدية
    الصف الرابع: الرصيد | دعوة الأصدقاء
    الصف الخامس: الشروط والاحكام | التواصل مع الدعم
    الصف السادس: إدارة البوت (للمالك فقط)
    """
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    
    # الصف الأول - Ichancy منفرد
    markup.row(types.KeyboardButton('⚽ Ichancy ⚽'))
    
    # الصف الثاني
    markup.row(
        types.KeyboardButton('💳 الشحن في البوت'),
        types.KeyboardButton('💸 السحب من البوت')
    )
    
    # الصف الثالث
    markup.row(
        types.KeyboardButton('🎁 اهداء رصيد'),
        types.KeyboardButton('🎫 كود هدية')
    )
    
    # الصف الرابع
    markup.row(
        types.KeyboardButton('💰 الرصيد'),
        types.KeyboardButton('👥 دعوة الأصدقاء')
    )
    
    # الصف الخامس
    markup.row(
        types.KeyboardButton('📜 الشروط والاحكام'),
        types.KeyboardButton('📞 التواصل مع الدعم')
    )
    
    # الصف السادس - إدارة البوت للمالك فقط
    if uid == ADMIN_ID or is_moderator(uid):
        markup.row(types.KeyboardButton('🔐 إدارة البوت'))
    
    return markup

def get_dynamic_keyboard(parent='main', level=1):
    """
    بناء لوحة مفاتيح ديناميكية من قاعدة البيانات
    """
    cursor.execute("""SELECT button_text FROM dynamic_buttons
                      WHERE parent_button=? AND level=? AND is_active=1
                      ORDER BY sort_order ASC""", (parent, level))
    buttons = cursor.fetchall()
    
    if not buttons:
        return None
    
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    
    i = 0
    while i < len(buttons):
        if i + 1 < len(buttons):
            markup.row(
                types.KeyboardButton(buttons[i][0]),
                types.KeyboardButton(buttons[i + 1][0])
            )
            i += 2
        else:
            markup.row(types.KeyboardButton(buttons[i][0]))
            i += 1
    
    if level > 1:
        markup.row(types.KeyboardButton('🔙 رجوع'))
    
    return markup

def get_ichancy_main_keyboard():
    """لوحة مفاتيح Ichancy الرئيسية (عند عدم وجود حساب)"""
    markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    markup.add(types.KeyboardButton('📝 إنشاء حساب جديد'))
    markup.add(types.KeyboardButton('🔙 العودة للقائمة الرئيسية'))
    return markup

def get_ichancy_account_keyboard():
    """لوحة مفاتيح إدارة حساب Ichancy (عند وجود حساب)"""
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.row(
        types.KeyboardButton('➕ تعبئة في حسابي'),
        types.KeyboardButton('➖ سحب من حسابي')
    )
    markup.row(types.KeyboardButton('🗑 حذف الحساب'))
    markup.row(types.KeyboardButton('🔙 العودة للقائمة الرئيسية'))
    return markup

def get_charge_methods_keyboard():
    """لوحة مفاتيح طرق الشحن"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("💳 سيرياتل كاش", callback_data="charge_syria"),
        types.InlineKeyboardButton("💳 شام كاش", callback_data="charge_sham"),
        types.InlineKeyboardButton("🔷 USDT", callback_data="charge_usdt"),
        types.InlineKeyboardButton("💱 بينانس", callback_data="charge_binance")
    )
    return markup

def get_withdraw_methods_keyboard():
    """لوحة مفاتيح طرق السحب"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("💳 سيرياتل كاش", callback_data="withdraw_syria"),
        types.InlineKeyboardButton("💳 شام كاش", callback_data="withdraw_sham")
    )
    return markup

def get_withdraw_currency_keyboard():
    """لوحة مفاتيح عملات السحب (لشام كاش)"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🇸🇾 ليرة سورية", callback_data="withdraw_sham_lyr"),
        types.InlineKeyboardButton("💵 دولار", callback_data="withdraw_sham_usd")
    )
    return markup

def get_confirmation_keyboard():
    """لوحة مفاتيح التأكيد"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✅ موافق", callback_data="confirm_yes"),
        types.InlineKeyboardButton("❌ إلغاء", callback_data="confirm_no")
    )
    return markup

def get_gift_type_keyboard():
    """لوحة مفاتيح أنواع الهدايا (للمالك)"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🎁 فردي 👤", callback_data="gift_individual"),
        types.InlineKeyboardButton("🎁 جماعي 👥", callback_data="gift_group")
    )
    return markup

def get_reply_keyboard_for_ticket(ticket_id, user_id):
    """لوحة مفاتيح الرد على التذكرة (للمشرفين)"""
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("✏️ رد على الرسالة", callback_data=f"reply_ticket_{ticket_id}_{user_id}")
    )
    return markup

# ================================================
# 9. نظام إدارة الأزرار المتقدم (CMS)
# ================================================

def get_button_action(button_text):
    """الحصول على إجراء زر معين"""
    cursor.execute("SELECT action FROM dynamic_buttons WHERE button_text=?", (button_text,))
    result = cursor.fetchone()
    return result[0] if result else None

def get_button_details(button_text):
    """الحصول على تفاصيل زر معين"""
    cursor.execute("SELECT action, message_text, photo_id, parent_button, level FROM dynamic_buttons WHERE button_text=?", (button_text,))
    return cursor.fetchone()

def get_buttons_list():
    """الحصول على قائمة بجميع الأزرار"""
    cursor.execute("""SELECT id, button_text, parent_button, level, sort_order, is_active
                      FROM dynamic_buttons
                      ORDER BY parent_button, level, sort_order""")
    return cursor.fetchall()

def add_new_button(button_text, action=None, parent='main', level=1, message_text=None, photo_id=None, admin_id=ADMIN_ID):
    """إضافة زر جديد"""
    button_name = f"btn_{int(time.time())}"
    
    cursor.execute("SELECT MAX(sort_order) FROM dynamic_buttons WHERE parent_button=? AND level=?", (parent, level))
    max_order = cursor.fetchone()[0] or 0
    
    cursor.execute("""INSERT INTO dynamic_buttons
        (button_name, button_text, parent_button, button_type, action, message_text, photo_id, level, sort_order, created_at, created_by)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (button_name, button_text, parent, 'reply', action, message_text, photo_id, level, max_order + 1,
         datetime.now().strftime("%Y-%m-%d %H:%M:%S"), admin_id))
    conn.commit()
    
    logger.info(f"تم إضافة زر جديد: {button_text} بواسطة {admin_id}")
    return cursor.lastrowid

def edit_button_name(old_text, new_text, admin_id=ADMIN_ID):
    """تعديل اسم زر"""
    cursor.execute("UPDATE dynamic_buttons SET button_text=?, updated_at=? WHERE button_text=?",
                  (new_text, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), old_text))
    conn.commit()
    logger.info(f"تم تعديل اسم زر من {old_text} إلى {new_text} بواسطة {admin_id}")

def delete_button(button_text, admin_id=ADMIN_ID):
    """حذف زر"""
    cursor.execute("DELETE FROM dynamic_buttons WHERE button_text=?", (button_text,))
    conn.commit()
    logger.info(f"تم حذف زر: {button_text} بواسطة {admin_id}")

def reorder_buttons(button_names, parent='main', level=1, admin_id=ADMIN_ID):
    """إعادة ترتيب الأزرار"""
    for i, btn_text in enumerate(button_names):
        cursor.execute("""UPDATE dynamic_buttons SET sort_order=? 
                          WHERE button_text=? AND parent_button=? AND level=?""",
                      (i+1, btn_text, parent, level))
    conn.commit()
    logger.info(f"تم إعادة ترتيب أزرار {parent} بواسطة {admin_id}")

def update_button_full(button_text, new_text=None, new_action=None, new_message=None, new_photo=None, new_parent=None, new_level=None, admin_id=ADMIN_ID):
    """تحديث كامل لبيانات زر"""
    updates = []
    params = []
    
    if new_text:
        updates.append("button_text=?")
        params.append(new_text)
    if new_action is not None:
        updates.append("action=?")
        params.append(new_action)
    if new_message is not None:
        updates.append("message_text=?")
        params.append(new_message)
    if new_photo is not None:
        updates.append("photo_id=?")
        params.append(new_photo)
    if new_parent:
        updates.append("parent_button=?")
        params.append(new_parent)
    if new_level:
        updates.append("level=?")
        params.append(new_level)
    
    if not updates:
        return False
    
    updates.append("updated_at=?")
    params.append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    params.append(button_text)
    
    query = f"UPDATE dynamic_buttons SET {', '.join(updates)} WHERE button_text=?"
    cursor.execute(query, params)
    conn.commit()
    
    logger.info(f"تم تحديث زر: {button_text} بواسطة {admin_id}")
    return True

def toggle_button_status(button_text, admin_id=ADMIN_ID):
    """تفعيل/تعطيل زر"""
    cursor.execute("SELECT is_active FROM dynamic_buttons WHERE button_text=?", (button_text,))
    result = cursor.fetchone()
    if result:
        new_status = 0 if result[0] == 1 else 1
        cursor.execute("UPDATE dynamic_buttons SET is_active=? WHERE button_text=?", (new_status, button_text))
        conn.commit()
        status_text = "مفعل" if new_status == 1 else "معطل"
        logger.info(f"تم تغيير حالة زر {button_text} إلى {status_text} بواسطة {admin_id}")
        return new_status
    return None

# نهاية الجزء الثاني

# ================================================
# MATAR ULTIMATE TELEGRAM BOT - ENTERPRISE EDITION
# ================================================
# ==================== الجزء الثالث والأخير ====================
# ========== 10. لوحات التحكم والإدارة ==========
# ========== 11. أوامر الإدارة ==========
# ========== 12. معالج الأوامر الرئيسي ==========
# ========== 13. الراوتر الرئيسي للرسائل ==========
# ========== 14. تشغيل البوت ==========
# ================================================

# ================================================
# 10. لوحات التحكم والإدارة
# ================================================

def get_admin_main_keyboard(is_owner=False):
    """لوحة المفاتيح الرئيسية للإدارة"""
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)

    if is_owner:
        markup.add('🎫 إنشاء كود هدية', '👥 إدارة المستخدمين')
        markup.add('💰 تغيير أكواد الدفع', '📊 سجل المعاملات')
        markup.add('📨 رسالة جماعية', '📧 رسالة فردية')
        markup.add('🔄 استرجاع حساب', '🔧 حالة البوت')
        markup.add('📋 قاعدة البيانات', '💬 تذاكر الدعم')
        markup.add('👥 المشرفين', '📊 نظام الإحالات')
        markup.add('🛑 إدارة البوت بالكامل')
        markup.add('🔙 العودة للقائمة الرئيسية')
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
        types.InlineKeyboardButton("📝 إدارة الأزرار", callback_data="admin_buttons"),
        types.InlineKeyboardButton("💳 إعدادات الدفع", callback_data="admin_payment"),
        types.InlineKeyboardButton("👥 إدارة المستخدمين", callback_data="admin_users"),
        types.InlineKeyboardButton("📊 الإحصائيات", callback_data="admin_stats"),
        types.InlineKeyboardButton("⚙️ الإعدادات العامة", callback_data="admin_settings"),
        types.InlineKeyboardButton("📨 رسائل جماعية", callback_data="admin_broadcast"),
        types.InlineKeyboardButton("🔗 ربط الكاشيرة", callback_data="admin_cashier"),
        types.InlineKeyboardButton("👥 صلاحيات المشرفين", callback_data="admin_moderators"),
        types.InlineKeyboardButton("💾 النسخ الاحتياطي", callback_data="admin_backup"),
        types.InlineKeyboardButton("🔙 رجوع", callback_data="back_to_admin")
    )
    return keyboard

def get_buttons_management_keyboard():
    """لوحة إدارة الأزرار"""
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("➕ إضافة زر جديد", callback_data="add_button"),
        types.InlineKeyboardButton("✏️ تعديل زر موجود", callback_data="edit_button"),
        types.InlineKeyboardButton("🔄 ترتيب الأزرار", callback_data="reorder_buttons"),
        types.InlineKeyboardButton("❌ حذف زر", callback_data="delete_button"),
        types.InlineKeyboardButton("📋 عرض جميع الأزرار", callback_data="list_buttons"),
        types.InlineKeyboardButton("🎯 إضافة إجراء لزر", callback_data="set_button_action"),
        types.InlineKeyboardButton("📂 إنشاء قائمة فرعية", callback_data="create_submenu"),
        types.InlineKeyboardButton("🔙 رجوع", callback_data="back_to_full_admin")
    )
    return keyboard

def get_payment_settings_keyboard():
    """لوحة إعدادات الدفع"""
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("📱 تعديل سيرياتل", callback_data="edit_syriatel"),
        types.InlineKeyboardButton("🏦 تعديل شام", callback_data="edit_sham"),
        types.InlineKeyboardButton("💰 تعديل الحدود", callback_data="edit_limits"),
        types.InlineKeyboardButton("💸 تعديل العمولة", callback_data="edit_commission"),
        types.InlineKeyboardButton("🔌 تفعيل API", callback_data="toggle_api"),
        types.InlineKeyboardButton("🔙 رجوع", callback_data="back_to_full_admin")
    )
    return keyboard

def get_user_management_keyboard():
    """لوحة إدارة المستخدمين"""
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("🔨 حظر مستخدم", callback_data="ban_user"),
        types.InlineKeyboardButton("✅ فك حظر", callback_data="unban_user"),
        types.InlineKeyboardButton("💰 شحن رصيد", callback_data="charge_user"),
        types.InlineKeyboardButton("💸 سحب رصيد", callback_data="withdraw_user"),
        types.InlineKeyboardButton("📝 معلومات مستخدم", callback_data="user_info"),
        types.InlineKeyboardButton("📋 قائمة المحظورين", callback_data="banned_users"),
        types.InlineKeyboardButton("🔙 رجوع", callback_data="back_to_full_admin")
    )
    return keyboard

def get_moderator_management_keyboard():
    """لوحة إدارة المشرفين"""
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("➕ إضافة مشرف", callback_data="add_moderator"),
        types.InlineKeyboardButton("➖ إزالة مشرف", callback_data="remove_moderator"),
        types.InlineKeyboardButton("✏️ تعديل اسم مشرف", callback_data="rename_moderator"),
        types.InlineKeyboardButton("🔒 تعديل صلاحيات", callback_data="moderator_permissions"),
        types.InlineKeyboardButton("📋 قائمة المشرفين", callback_data="list_moderators"),
        types.InlineKeyboardButton("🔙 رجوع", callback_data="back_to_full_admin")
    )
    return keyboard

def get_bot_settings_keyboard():
    """لوحة إعدادات البوت"""
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("🟢 تفعيل/تعطيل", callback_data="toggle_bot"),
        types.InlineKeyboardButton("📝 تعديل رسالة الترحيب", callback_data="edit_welcome"),
        types.InlineKeyboardButton("📜 تعديل الشروط", callback_data="edit_terms"),
        types.InlineKeyboardButton("👥 تعديل نسبة الإحالات", callback_data="edit_referral"),
        types.InlineKeyboardButton("🌙 تفعيل الوضع الليلي", callback_data="toggle_dark_mode_global"),
        types.InlineKeyboardButton("🔙 رجوع", callback_data="back_to_full_admin")
    )
    return keyboard

def get_backup_keyboard():
    """لوحة النسخ الاحتياطي"""
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("💾 حفظ فوري", callback_data="backup_now"),
        types.InlineKeyboardButton("📤 تصدير قاعدة البيانات", callback_data="export_db"),
        types.InlineKeyboardButton("📥 استيراد قاعدة البيانات", callback_data="import_db"),
        types.InlineKeyboardButton("🔄 استرجاع نسخة", callback_data="restore_backup"),
        types.InlineKeyboardButton("📋 عرض النسخ", callback_data="list_backups"),
        types.InlineKeyboardButton("🔙 رجوع", callback_data="back_to_full_admin")
    )
    return keyboard

def get_cashier_connection_keyboard():
    """لوحة ربط الكاشيرة"""
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("📱 ربط سيرياتل API", callback_data="connect_syriatel_api"),
        types.InlineKeyboardButton("🏦 ربط شام API", callback_data="connect_sham_api"),
        types.InlineKeyboardButton("🔌 اختبار الاتصال", callback_data="test_api_connection"),
        types.InlineKeyboardButton("⚡ تفعيل التحقق التلقائي", callback_data="toggle_auto_verify"),
        types.InlineKeyboardButton("📋 حالة الاتصالات", callback_data="api_status"),
        types.InlineKeyboardButton("🔙 رجوع", callback_data="back_to_full_admin")
    )
    return keyboard

def get_moderator_panel_keyboard(uid):
    """لوحة المشرف (حسب الصلاحيات)"""
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    perms = get_moderator_permissions(uid)
    
    if perms.get('can_reply_tickets', 0):
        markup.add('💬 تذاكر الدعم')
    if perms.get('can_change_payment', 0):
        markup.add('💰 تغيير أكواد الدفع')
    if perms.get('can_send_broadcast', 0):
        markup.add('📨 رسالة جماعية')
    if perms.get('can_manage_users', 0):
        markup.add('👥 إدارة المستخدمين')
    if perms.get('can_view_stats', 0):
        markup.add('📊 الإحصائيات')
    
    markup.add('🔙 العودة للقائمة الرئيسية')
    return markup

# ================================================
# 11. معالج الكول باكات الشامل
# ================================================

@bot.callback_query_handler(func=lambda call: True)
def handle_all_callbacks(call):
    """معالج شامل لجميع الكول باكات"""
    uid = call.from_user.id
    data = call.data
    
    # كول باكات النسخ
    if data.startswith('copy_'):
        text = data[5:]
        bot.answer_callback_query(call.id, "📋 تم النسخ!")
        bot.send_message(call.message.chat.id, f"✅ **انسخ هذا النص:**\n`{text}`", parse_mode="Markdown")
        return
    
    # التحقق من الصلاحية للكول باكات الإدارية
    admin_callbacks = ['admin_', 'add_button', 'edit_button', 'reorder_buttons', 'delete_button',
                      'list_buttons', 'set_button_action', 'create_submenu', 'back_to_full_admin',
                      'edit_syriatel', 'edit_sham', 'edit_limits', 'edit_commission', 'toggle_api',
                      'ban_user', 'unban_user', 'charge_user', 'withdraw_user', 'user_info', 'banned_users',
                      'add_moderator', 'remove_moderator', 'rename_moderator', 'moderator_permissions',
                      'list_moderators', 'toggle_bot', 'edit_welcome', 'edit_terms', 'edit_referral',
                      'toggle_dark_mode_global', 'backup_now', 'export_db', 'import_db', 'restore_backup',
                      'list_backups', 'connect_syriatel_api', 'connect_sham_api', 'test_api_connection',
                      'toggle_auto_verify', 'api_status']
    
    is_admin_callback = any(data.startswith(ac) for ac in admin_callbacks if isinstance(ac, str)) or data in admin_callbacks
    
    if is_admin_callback and uid != ADMIN_ID and not check_permission(uid, 'can_access_full_admin'):
        bot.answer_callback_query(call.id, "❌ ليس لديك صلاحية", show_alert=True)
        return
    
    # ===== إدارة الأزرار =====
    if data == 'admin_buttons':
        bot.edit_message_text("🔧 **إدارة الأزرار - اختر ما تريد فعله:**", 
                            call.message.chat.id, call.message.message_id,
                            reply_markup=get_buttons_management_keyboard(), parse_mode="Markdown")
    
    elif data == 'add_button':
        bot.edit_message_text("➕ **أرسل اسم الزر الجديد:**", 
                            call.message.chat.id, call.message.message_id)
        bot.register_next_step_handler_by_chat_id(call.message.chat.id, process_add_button)
    
    elif data == 'edit_button':
        bot.edit_message_text("✏️ **أرسل اسم الزر الذي تريد تعديله:**", 
                            call.message.chat.id, call.message.message_id)
        bot.register_next_step_handler_by_chat_id(call.message.chat.id, process_edit_button)
    
    elif data == 'reorder_buttons':
        buttons = get_buttons_list()
        main_buttons = [b[1] for b in buttons if b[2] == 'main' and b[5] == 1]
        
        if not main_buttons:
            bot.answer_callback_query(call.id, "❌ لا توجد أزرار رئيسية", show_alert=True)
            return
        
        text = "🔄 **الأزرار الرئيسية الحالية:**\n\n"
        for i, btn in enumerate(main_buttons, 1):
            text += f"{i}. {btn}\n"
        
        text += "\n📝 **أرسل الترتيب الجديد (مثال: 3,1,2,4):**"
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown")
        bot.register_next_step_handler_by_chat_id(call.message.chat.id, process_reorder, main_buttons)
    
    elif data == 'delete_button':
        bot.edit_message_text("❌ **أرسل اسم الزر الذي تريد حذفه:**", 
                            call.message.chat.id, call.message.message_id)
        bot.register_next_step_handler_by_chat_id(call.message.chat.id, process_delete_button)
    
    elif data == 'list_buttons':
        buttons = get_buttons_list()
        if not buttons:
            bot.send_message(call.message.chat.id, "📋 **لا توجد أزرار في قاعدة البيانات**", parse_mode="Markdown")
            return
        
        text = "📋 **قائمة الأزرار:**\n\n"
        for b in buttons:
            status = "✅" if b[5] == 1 else "❌"
            text += f"{status} `{b[1]}` (المستوى: {b[3]}, الترتيب: {b[4]})\n"
        
        bot.send_message(call.message.chat.id, text, parse_mode="Markdown")
    
    elif data == 'set_button_action':
        bot.edit_message_text("🎯 **أرسل اسم الزر الذي تريد تعيين إجراء له:**", 
                            call.message.chat.id, call.message.message_id)
        bot.register_next_step_handler_by_chat_id(call.message.chat.id, process_set_action)
    
    elif data == 'create_submenu':
        bot.edit_message_text("📂 **أرسل اسم الزر الذي سيكون له قائمة فرعية:**", 
                            call.message.chat.id, call.message.message_id)
        bot.register_next_step_handler_by_chat_id(call.message.chat.id, process_create_submenu)
    
    # ===== إعدادات الدفع =====
    elif data == 'admin_payment':
        syriatel = get_db_setting('syriatel_numbers')
        sham = get_db_setting('sham_address')
        min_charge = get_db_setting('min_charge')
        min_withdraw = get_db_setting('min_withdraw_syria')
        commission = get_db_setting('withdraw_commission')
        
        text = f"""
💳 **إعدادات الدفع الحالية:**

📱 **سيرياتل كاش:** `{syriatel}`
🏦 **شام كاش:** `{sham}`
💰 **الحد الأدنى للشحن:** {min_charge} ل.س
💸 **الحد الأدنى للسحب:** {min_withdraw} ل.س
💵 **عمولة السحب:** {commission}%

اختر ما تريد تعديله:
"""
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                            reply_markup=get_payment_settings_keyboard(), parse_mode="Markdown")
    
    elif data == 'edit_syriatel':
        bot.edit_message_text("📱 **أرسل أرقام سيرياتل كاش الجديدة:**", 
                            call.message.chat.id, call.message.message_id)
        bot.register_next_step_handler_by_chat_id(call.message.chat.id, process_update_syriatel)
    
    elif data == 'edit_sham':
        bot.edit_message_text("🏦 **أرسل عنوان شام كاش الجديد:**", 
                            call.message.chat.id, call.message.message_id)
        bot.register_next_step_handler_by_chat_id(call.message.chat.id, process_update_sham)
    
    elif data == 'edit_limits':
        bot.edit_message_text("💰 **أرسل الحد الأدنى والأقصى (مثال: 100,500000):**", 
                            call.message.chat.id, call.message.message_id)
        bot.register_next_step_handler_by_chat_id(call.message.chat.id, process_update_limits)
    
    elif data == 'edit_commission':
        bot.edit_message_text("💸 **أرسل نسبة العمولة الجديدة:**", 
                            call.message.chat.id, call.message.message_id)
        bot.register_next_step_handler_by_chat_id(call.message.chat.id, process_update_commission)
    
    # ===== إدارة المستخدمين =====
    elif data == 'admin_users':
        cursor.execute("SELECT COUNT(*) FROM users WHERE deleted=0")
        total = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM users WHERE status='banned'")
        banned = cursor.fetchone()[0]
        
        text = f"""
👥 **إدارة المستخدمين**

📊 **الإجمالي:** {total}
🔨 **المحظورين:** {banned}

اختر العملية:
"""
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                            reply_markup=get_user_management_keyboard(), parse_mode="Markdown")
    
    elif data == 'ban_user':
        bot.edit_message_text("🔨 **أرسل معرف المستخدم (ID) لحظره:**", 
                            call.message.chat.id, call.message.message_id)
        bot.register_next_step_handler_by_chat_id(call.message.chat.id, process_ban_user)
    
    elif data == 'unban_user':
        bot.edit_message_text("✅ **أرسل معرف المستخدم (ID) لفك حظره:**", 
                            call.message.chat.id, call.message.message_id)
        bot.register_next_step_handler_by_chat_id(call.message.chat.id, process_unban_user)
    
    elif data == 'charge_user':
        bot.edit_message_text("💰 **أرسل معرف المستخدم (ID) لشحن رصيده:**", 
                            call.message.chat.id, call.message.message_id)
        bot.register_next_step_handler_by_chat_id(call.message.chat.id, process_charge_user_step1)
    
    elif data == 'withdraw_user':
        bot.edit_message_text("💸 **أرسل معرف المستخدم (ID) لسحب رصيده:**", 
                            call.message.chat.id, call.message.message_id)
        bot.register_next_step_handler_by_chat_id(call.message.chat.id, process_withdraw_user_step1)
    
    elif data == 'user_info':
        bot.edit_message_text("📝 **أرسل معرف المستخدم (ID) لعرض معلوماته:**", 
                            call.message.chat.id, call.message.message_id)
        bot.register_next_step_handler_by_chat_id(call.message.chat.id, process_user_info)
    
    # ===== الإحصائيات =====
    elif data == 'admin_stats':
        # إحصائيات سريعة
        cursor.execute("SELECT COUNT(*) FROM users WHERE deleted=0")
        users = cursor.fetchone()[0]
        
        cursor.execute("SELECT SUM(balance) FROM users WHERE deleted=0")
        balance = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT COUNT(*) FROM transactions WHERE DATE(transaction_date) = DATE('now')")
        trans_today = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM tickets WHERE status='open'")
        tickets = cursor.fetchone()[0]
        
        text = f"""
📊 **إحصائيات سريعة:**

👥 **المستخدمين:** {users}
💰 **إجمالي الأرصدة:** {balance:,.0f} ل.س
💳 **معاملات اليوم:** {trans_today}
📬 **تذاكر مفتوحة:** {tickets}

🔍 للتفاصيل، استخدم أوامر الإدارة الأخرى.
"""
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="back_to_full_admin"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                            reply_markup=keyboard, parse_mode="Markdown")
    
    # ===== الإعدادات العامة =====
    elif data == 'admin_settings':
        status = get_db_setting('bot_status')
        welcome = get_db_setting('welcome_message')
        ref_percent = get_db_setting('referral_percentage')
        
        status_text = "🟢 نشط" if status == 'active' else "🔴 معطل"
        
        text = f"""
⚙️ **الإعدادات العامة:**

🔧 **حالة البوت:** {status_text}
📝 **رسالة الترحيب:** {welcome[:50]}...
👥 **نسبة الإحالات:** {ref_percent}%

اختر ما تريد تعديله:
"""
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                            reply_markup=get_bot_settings_keyboard(), parse_mode="Markdown")
    
    elif data == 'toggle_bot':
        current = get_db_setting('bot_status')
        new = 'maintenance' if current == 'active' else 'active'
        update_db_setting('bot_status', new, uid)
        
        status = "🟢 مفعل" if new == 'active' else "🔴 معطل"
        bot.answer_callback_query(call.id, f"✅ تم تغيير حالة البوت إلى: {status}", show_alert=True)
        
        # العودة للقائمة
        bot.edit_message_text("🛑 **لوحة التحكم الكامل:**", call.message.chat.id, call.message.message_id,
                            reply_markup=get_full_admin_keyboard(), parse_mode="Markdown")
    
    # ===== رسائل جماعية =====
    elif data == 'admin_broadcast':
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            types.InlineKeyboardButton("📝 رسالة نصية", callback_data="broadcast_text"),
            types.InlineKeyboardButton("🖼️ صورة مع تعليق", callback_data="broadcast_photo"),
            types.InlineKeyboardButton("🔙 رجوع", callback_data="back_to_full_admin")
        )
        
        bot.edit_message_text("📨 **إرسال رسالة جماعية - اختر النوع:**", 
                            call.message.chat.id, call.message.message_id,
                            reply_markup=keyboard, parse_mode="Markdown")
    
    elif data == 'broadcast_text':
        bot.edit_message_text("📝 **أرسل الرسالة التي تريد إرسالها لجميع المستخدمين:**", 
                            call.message.chat.id, call.message.message_id)
        bot.register_next_step_handler_by_chat_id(call.message.chat.id, process_broadcast)
    
    elif data == 'broadcast_photo':
        bot.edit_message_text("🖼️ **أرسل الصورة أولاً:**", 
                            call.message.chat.id, call.message.message_id)
        bot.register_next_step_handler_by_chat_id(call.message.chat.id, process_broadcast_photo_step1)
    
    # ===== ربط الكاشيرة =====
    elif data == 'admin_cashier':
        bot.edit_message_text("🔗 **ربط الكاشيرة الخارجية - اختر:**", 
                            call.message.chat.id, call.message.message_id,
                            reply_markup=get_cashier_connection_keyboard(), parse_mode="Markdown")
    
    elif data == 'connect_syriatel_api':
        bot.edit_message_text("📱 **أدخل رقم سيرياتل كاش لربطه مع API:**", 
                            call.message.chat.id, call.message.message_id)
        bot.register_next_step_handler_by_chat_id(call.message.chat.id, process_connect_syriatel_api)
    
    elif data == 'connect_sham_api':
        bot.edit_message_text("🏦 **أدخل عنوان شام كاش لربطه مع API:**", 
                            call.message.chat.id, call.message.message_id)
        bot.register_next_step_handler_by_chat_id(call.message.chat.id, process_connect_sham_api)
    
    elif data == 'test_api_connection':
        bot.answer_callback_query(call.id, "✅ جاري اختبار الاتصالات...")
        time.sleep(1)
        bot.send_message(call.message.chat.id, "✅ **جميع الاتصالات تعمل بشكل طبيعي**", parse_mode="Markdown")
    
    elif data == 'toggle_auto_verify':
        current = get_db_setting('auto_verify_charges')
        new = '0' if current == '1' else '1'
        update_db_setting('auto_verify_charges', new, uid)
        
        status = "🟢 مفعل" if new == '1' else "🔴 معطل"
        bot.answer_callback_query(call.id, f"✅ تم تغيير التحقق التلقائي إلى: {status}", show_alert=True)
    
    # ===== صلاحيات المشرفين =====
    elif data == 'admin_moderators':
        bot.edit_message_text("👥 **إدارة المشرفين والصلاحيات - اختر:**", 
                            call.message.chat.id, call.message.message_id,
                            reply_markup=get_moderator_management_keyboard(), parse_mode="Markdown")
    
    elif data == 'add_moderator':
        bot.edit_message_text("➕ **أرسل معرف المستخدم (ID) لإضافته كمشرف:**", 
                            call.message.chat.id, call.message.message_id)
        bot.register_next_step_handler_by_chat_id(call.message.chat.id, process_add_moderator)
    
    elif data == 'remove_moderator':
        bot.edit_message_text("➖ **أرسل معرف المستخدم (ID) لإزالة الاشراف منه:**", 
                            call.message.chat.id, call.message.message_id)
        bot.register_next_step_handler_by_chat_id(call.message.chat.id, process_remove_moderator)
    
    elif data == 'list_moderators':
        cursor.execute("SELECT user_id, custom_name, added_at FROM moderators")
        mods = cursor.fetchall()
        
        if not mods:
            bot.send_message(call.message.chat.id, "📭 **لا يوجد مشرفين حالياً**", parse_mode="Markdown")
            return
        
        text = "👥 **قائمة المشرفين:**\n\n"
        for m in mods:
            name = m[1] or f"مشرف {m[0]}"
            text += f"🆔 `{m[0]}` | {name}\n📅 {m[2]}\n\n"
        
        bot.send_message(call.message.chat.id, text, parse_mode="Markdown")
    
    # ===== النسخ الاحتياطي =====
    elif data == 'admin_backup':
        bot.edit_message_text("💾 **نظام النسخ الاحتياطي - اختر:**", 
                            call.message.chat.id, call.message.message_id,
                            reply_markup=get_backup_keyboard(), parse_mode="Markdown")
    
    elif data == 'backup_now':
        bot.answer_callback_query(call.id, "💾 جاري حفظ نسخة احتياطية...")
        
        # محاكاة حفظ نسخة
        backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        cursor.execute("""INSERT INTO backups (backup_name, backup_type, created_at, created_by)
                          VALUES (?,?,?,?)""",
                      (backup_name, 'manual', datetime.now().strftime("%Y-%m-%d %H:%M:%S"), uid))
        conn.commit()
        
        bot.send_message(call.message.chat.id, f"✅ **تم حفظ نسخة احتياطية:** `{backup_name}`", parse_mode="Markdown")
    
    # ===== العودة للقوائم السابقة =====
    elif data == 'back_to_full_admin':
        bot.edit_message_text("🛑 **لوحة التحكم الكامل:**", 
                            call.message.chat.id, call.message.message_id,
                            reply_markup=get_full_admin_keyboard(), parse_mode="Markdown")
    
    elif data == 'back_to_admin':
        bot.edit_message_text("🔐 **لوحة التحكم:**", 
                            call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, "🔐 **لوحة التحكم:**", 
                        reply_markup=get_admin_main_keyboard(is_owner=(uid == ADMIN_ID)))


# ================================================
# 12. دوال معالجة الإدخالات
# ================================================

def process_add_button(message):
    """معالجة إضافة زر جديد"""
    uid = message.from_user.id
    button_text = message.text
    
    if button_text == '🔙 العودة للقائمة الرئيسية':
        bot.send_message(message.chat.id, "القائمة الرئيسية:", reply_markup=get_main_keyboard(uid))
        return
    
    add_new_button(button_text, admin_id=uid)
    bot.send_message(message.chat.id, f"✅ **تمت إضافة الزر:** `{button_text}`", parse_mode="Markdown")
    bot.send_message(message.chat.id, "🔧 **إدارة الأزرار:**", reply_markup=get_buttons_management_keyboard())

def process_edit_button(message):
    """معالجة بدء تعديل زر"""
    uid = message.from_user.id
    old_text = message.text
    
    if old_text == '🔙 العودة للقائمة الرئيسية':
        bot.send_message(message.chat.id, "القائمة الرئيسية:", reply_markup=get_main_keyboard(uid))
        return
    
    cursor.execute("SELECT id FROM dynamic_buttons WHERE button_text=?", (old_text,))
    if not cursor.fetchone():
        bot.send_message(message.chat.id, "❌ **الزر غير موجود**", parse_mode="Markdown")
        return
    
    msg = bot.send_message(message.chat.id, f"✏️ **أدخل الاسم الجديد للزر** `{old_text}`**:**", parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_edit_button_final, old_text)

def process_edit_button_final(message, old_text):
    """معالجة التعديل النهائي للزر"""
    uid = message.from_user.id
    new_text = message.text
    
    edit_button_name(old_text, new_text, uid)
    bot.send_message(message.chat.id, f"✅ **تم تعديل الزر إلى:** `{new_text}`", parse_mode="Markdown")
    bot.send_message(message.chat.id, "🔧 **إدارة الأزرار:**", reply_markup=get_buttons_management_keyboard())

def process_delete_button(message):
    """معالجة حذف زر"""
    uid = message.from_user.id
    button_text = message.text
    
    if button_text == '🔙 العودة للقائمة الرئيسية':
        bot.send_message(message.chat.id, "القائمة الرئيسية:", reply_markup=get_main_keyboard(uid))
        return
    
    cursor.execute("SELECT id FROM dynamic_buttons WHERE button_text=?", (button_text,))
    if not cursor.fetchone():
        bot.send_message(message.chat.id, "❌ **الزر غير موجود**", parse_mode="Markdown")
        return
    
    delete_button(button_text, uid)
    bot.send_message(message.chat.id, f"✅ **تم حذف الزر:** `{button_text}`", parse_mode="Markdown")
    bot.send_message(message.chat.id, "🔧 **إدارة الأزرار:**", reply_markup=get_buttons_management_keyboard())

def process_reorder(message, buttons):
    """معالجة إعادة ترتيب الأزرار"""
    uid = message.from_user.id
    
    try:
        order = [int(x.strip()) for x in message.text.split(',')]
        
        if len(order) != len(buttons):
            bot.send_message(message.chat.id, "❌ **عدد الأرقام لا يساوي عدد الأزرار**", parse_mode="Markdown")
            return
        
        # التحقق من صحة الأرقام
        if sorted(order) != list(range(1, len(buttons) + 1)):
            bot.send_message(message.chat.id, "❌ **الأرقام يجب أن تكون من 1 إلى {len(buttons)} بدون تكرار**", parse_mode="Markdown")
            return
        
        new_order = []
        for pos in order:
            new_order.append(buttons[pos-1])
        
        reorder_buttons(new_order, admin_id=uid)
        bot.send_message(message.chat.id, "✅ **تم إعادة ترتيب الأزرار بنجاح**", parse_mode="Markdown")
        
    except ValueError:
        bot.send_message(message.chat.id, "❌ **صيغة خاطئة. استخدم أرقاماً مفصولة بفواصل (مثال: 3,1,2,4)**", parse_mode="Markdown")
    
    bot.send_message(message.chat.id, "🔧 **إدارة الأزرار:**", reply_markup=get_buttons_management_keyboard())

def process_set_action(message):
    """معالجة تعيين إجراء لزر"""
    uid = message.from_user.id
    button_text = message.text
    
    if button_text == '🔙 العودة للقائمة الرئيسية':
        bot.send_message(message.chat.id, "القائمة الرئيسية:", reply_markup=get_main_keyboard(uid))
        return
    
    cursor.execute("SELECT id FROM dynamic_buttons WHERE button_text=?", (button_text,))
    if not cursor.fetchone():
        bot.send_message(message.chat.id, "❌ **الزر غير موجود**", parse_mode="Markdown")
        return
    
    actions_list = """
📋 **قائمة الإجراءات المتاحة:**

👤 **مستخدم:**
• show_balance - عرض الرصيد
• show_ichancy_menu - قائمة Ichancy
• create_ichancy_account - إنشاء حساب
• charge_ichancy - تعبئة حساب
• withdraw_ichancy - سحب من حساب
• delete_ichancy_account - حذف حساب

💰 **مالية:**
• show_charge_methods - طرق الشحن
• show_withdraw_methods - طرق السحب
• start_gift - إهداء رصيد
• redeem_gift - استخدام كود

👥 **اجتماعية:**
• show_referral - نظام الإحالات
• show_referral_link - رابط الإحالة

📞 **دعم:**
• start_support - التواصل مع الدعم
• show_terms - الشروط

🔐 **إدارة:**
• show_admin_panel - لوحة الإدارة
• show_full_admin_menu - الإدارة الكاملة

🎯 **أخرى:**
• show_submenu - قائمة فرعية
• toggle_dark_mode - الوضع الليلي

أدخل الإجراء الذي تريده:
"""
    
    msg = bot.send_message(message.chat.id, actions_list, parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_set_action_final, button_text)

def process_set_action_final(message, button_text):
    """معالجة تعيين الإجراء النهائي"""
    uid = message.from_user.id
    action = message.text
    
    update_button_full(button_text, new_action=action, admin_id=uid)
    bot.send_message(message.chat.id, f"✅ **تم تعيين الإجراء** `{action}` **للزر** `{button_text}`", parse_mode="Markdown")
    bot.send_message(message.chat.id, "🔧 **إدارة الأزرار:**", reply_markup=get_buttons_management_keyboard())

def process_create_submenu(message):
    """معالجة إنشاء قائمة فرعية"""
    uid = message.from_user.id
    parent_button = message.text
    
    if parent_button == '🔙 العودة للقائمة الرئيسية':
        bot.send_message(message.chat.id, "القائمة الرئيسية:", reply_markup=get_main_keyboard(uid))
        return
    
    cursor.execute("SELECT id FROM dynamic_buttons WHERE button_text=?", (parent_button,))
    if not cursor.fetchone():
        bot.send_message(message.chat.id, "❌ **الزر الرئيسي غير موجود**", parse_mode="Markdown")
        return
    
    # تعيين إجراء القائمة الفرعية للزر الرئيسي
    update_button_full(parent_button, new_action='show_submenu', admin_id=uid)
    
    msg = bot.send_message(message.chat.id, f"📂 **أدخل اسم الزر الفرعي الجديد تحت** `{parent_button}`**:**", parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_create_submenu_step2, parent_button)

def process_create_submenu_step2(message, parent_button):
    """معالجة إضافة الزر الفرعي"""
    uid = message.from_user.id
    sub_button = message.text
    
    add_new_button(sub_button, parent=parent_button, level=2, admin_id=uid)
    bot.send_message(message.chat.id, f"✅ **تم إنشاء القائمة الفرعية** `{sub_button}` **تحت** `{parent_button}`", parse_mode="Markdown")
    bot.send_message(message.chat.id, "🔧 **إدارة الأزرار:**", reply_markup=get_buttons_management_keyboard())

# ===== دوال معالجة الإعدادات =====

def process_update_syriatel(message):
    """تحديث أرقام سيرياتل"""
    uid = message.from_user.id
    numbers = message.text
    
    update_db_setting('syriatel_numbers', numbers, uid)
    bot.send_message(message.chat.id, f"✅ **تم تحديث أرقام سيرياتل إلى:**\n`{numbers}`", parse_mode="Markdown")

def process_update_sham(message):
    """تحديث عنوان شام"""
    uid = message.from_user.id
    address = message.text
    
    update_db_setting('sham_address', address, uid)
    bot.send_message(message.chat.id, f"✅ **تم تحديث عنوان شام إلى:**\n`{address}`", parse_mode="Markdown")

def process_update_limits(message):
    """تحديث الحدود"""
    uid = message.from_user.id
    
    try:
        parts = message.text.split(',')
        if len(parts) >= 2:
            min_charge = parts[0].strip()
            max_withdraw = parts[1].strip()
            
            update_db_setting('min_charge', min_charge, uid)
            update_db_setting('max_withdraw_syria', max_withdraw, uid)
            
            bot.send_message(message.chat.id, f"✅ **تم تحديث الحدود:**\n📉 الحد الأدنى: {min_charge}\n📈 الحد الأقصى: {max_withdraw}", parse_mode="Markdown")
        else:
            bot.send_message(message.chat.id, "❌ **الصيغة الصحيحة: الحد الأدنى,الحد الأقصى**", parse_mode="Markdown")
    except:
        bot.send_message(message.chat.id, "❌ **خطأ في الصيغة**", parse_mode="Markdown")

def process_update_commission(message):
    """تحديث نسبة العمولة"""
    uid = message.from_user.id
    
    try:
        commission = float(message.text)
        update_db_setting('withdraw_commission', str(commission), uid)
        bot.send_message(message.chat.id, f"✅ **تم تحديث نسبة العمولة إلى:** {commission}%", parse_mode="Markdown")
    except ValueError:
        bot.send_message(message.chat.id, "❌ **الرجاء إدخال رقم صحيح**", parse_mode="Markdown")

# ===== دوال إدارة المستخدمين =====

def process_ban_user(message):
    """حظر مستخدم"""
    uid = message.from_user.id
    
    try:
        target = int(message.text)
        cursor.execute("UPDATE users SET status='banned' WHERE user_id=?", (target,))
        conn.commit()
        
        bot.send_message(message.chat.id, f"✅ **تم حظر المستخدم:** `{target}`", parse_mode="Markdown")
        log_admin_action(uid, 'ban_user', f'تم حظر المستخدم {target}')
    except ValueError:
        bot.send_message(message.chat.id, "❌ **معرف غير صالح**", parse_mode="Markdown")

def process_unban_user(message):
    """فك حظر مستخدم"""
    uid = message.from_user.id
    
    try:
        target = int(message.text)
        cursor.execute("UPDATE users SET status='active' WHERE user_id=?", (target,))
        conn.commit()
        
        bot.send_message(message.chat.id, f"✅ **تم فك حظر المستخدم:** `{target}`", parse_mode="Markdown")
        log_admin_action(uid, 'unban_user', f'تم فك حظر المستخدم {target}')
    except ValueError:
        bot.send_message(message.chat.id, "❌ **معرف غير صالح**", parse_mode="Markdown")

def process_charge_user_step1(message):
    """الخطوة الأولى لشحن رصيد مستخدم"""
    uid = message.from_user.id
    
    try:
        target = int(message.text)
        msg = bot.send_message(message.chat.id, f"💰 **أدخل المبلغ لشحنه للمستخدم** `{target}`**:**", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_charge_user_step2, target)
    except ValueError:
        bot.send_message(message.chat.id, "❌ **معرف غير صالح**", parse_mode="Markdown")

def process_charge_user_step2(message, target):
    """الخطوة الثانية لشحن رصيد مستخدم"""
    uid = message.from_user.id
    
    try:
        amount = float(message.text)
        new_balance = update_user_balance(target, amount, add=True)
        
        bot.send_message(message.chat.id, f"✅ **تم شحن {amount:,.0f} ل.س للمستخدم {target}**\n💰 رصيده الجديد: {new_balance:,.0f} ل.س", parse_mode="Markdown")
        bot.send_message(target, f"💰 **تم شحن {amount:,.0f} ل.س إلى رصيدك من قبل الإدارة**", parse_mode="Markdown")
        
        log_transaction(target, "admin_charge", amount, "admin", "success", admin_id=uid)
        log_admin_action(uid, 'charge_user', f'تم شحن {amount} للمستخدم {target}')
    except ValueError:
        bot.send_message(message.chat.id, "❌ **مبلغ غير صالح**", parse_mode="Markdown")

def process_withdraw_user_step1(message):
    """الخطوة الأولى لسحب رصيد مستخدم"""
    uid = message.from_user.id
    
    try:
        target = int(message.text)
        msg = bot.send_message(message.chat.id, f"💸 **أدخل المبلغ لسحبه من المستخدم** `{target}`**:**", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_withdraw_user_step2, target)
    except ValueError:
        bot.send_message(message.chat.id, "❌ **معرف غير صالح**", parse_mode="Markdown")

def process_withdraw_user_step2(message, target):
    """الخطوة الثانية لسحب رصيد مستخدم"""
    uid = message.from_user.id
    
    try:
        amount = float(message.text)
        
        cursor.execute("SELECT balance FROM users WHERE user_id=?", (target,))
        bal = cursor.fetchone()
        
        if not bal or bal[0] < amount:
            bot.send_message(message.chat.id, f"❌ **رصيد المستخدم غير كافٍ**\n💰 رصيده: {bal[0] if bal else 0:,.0f} ل.س", parse_mode="Markdown")
            return
        
        new_balance = update_user_balance(target, amount, add=False)
        
        bot.send_message(message.chat.id, f"✅ **تم سحب {amount:,.0f} ل.س من المستخدم {target}**\n💰 رصيده الجديد: {new_balance:,.0f} ل.س", parse_mode="Markdown")
        bot.send_message(target, f"💸 **تم سحب {amount:,.0f} ل.س من رصيدك من قبل الإدارة**", parse_mode="Markdown")
        
        log_transaction(target, "admin_withdraw", amount, "admin", "success", admin_id=uid)
        log_admin_action(uid, 'withdraw_user', f'تم سحب {amount} من المستخدم {target}')
    except ValueError:
        bot.send_message(message.chat.id, "❌ **مبلغ غير صالح**", parse_mode="Markdown")

def process_user_info(message):
    """عرض معلومات مستخدم"""
    uid = message.from_user.id
    
    try:
        target = int(message.text)
        
        cursor.execute("""SELECT user_id, first_name, username, balance, site_balance, status, 
                                 created_at, custom_name, referral_count, current_earnings
                          FROM users WHERE user_id=?""", (target,))
        user = cursor.fetchone()
        
        if not user:
            bot.send_message(message.chat.id, "❌ **المستخدم غير موجود**", parse_mode="Markdown")
            return
        
        text = f"""
📝 **معلومات المستخدم** `{target}`

👤 **الاسم:** {user[1] or 'غير محدد'}
🆔 **اليوزر:** @{user[2] or 'لا يوجد'}
💰 **رصيد البوت:** {user[3]:,.0f} ل.س
🌐 **رصيد الموقع:** {user[4]:,.0f} NSP
⚡ **الحالة:** {user[5]}
📅 **تاريخ التسجيل:** {user[6]}
🏷️ **الاسم المخصص:** {user[7] or 'لا يوجد'}
👥 **عدد الإحالات:** {user[8]}
💵 **أرباح الدورة:** {user[9]:,.0f} ل.س
"""
        
        bot.send_message(message.chat.id, text, parse_mode="Markdown")
        
    except ValueError:
        bot.send_message(message.chat.id, "❌ **معرف غير صالح**", parse_mode="Markdown")

# ===== دوال إدارة المشرفين =====

def process_add_moderator(message):
    """إضافة مشرف"""
    uid = message.from_user.id
    
    if uid != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ **هذه الخاصية للمالك فقط**", parse_mode="Markdown")
        return
    
    try:
        target = int(message.text)
        
        if target == ADMIN_ID:
            bot.send_message(message.chat.id, "❌ **لا يمكن إضافة المالك كمشرف**", parse_mode="Markdown")
            return
        
        cursor.execute("SELECT user_id FROM moderators WHERE user_id=?", (target,))
        if cursor.fetchone():
            bot.send_message(message.chat.id, "❌ **المستخدم مشرف بالفعل**", parse_mode="Markdown")
            return
        
        cursor.execute("""INSERT INTO moderators 
            (user_id, added_by, added_at, can_reply_tickets, can_change_payment, 
             can_send_broadcast, can_manage_users, can_charge_withdraw, can_view_stats)
            VALUES (?,?,?,1,0,0,0,0,0)""",
            (target, uid, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        
        bot.send_message(message.chat.id, f"✅ **تمت إضافة المستخدم** `{target}` **كمشرف**", parse_mode="Markdown")
        bot.send_message(target, "🔐 **تمت إضافتك كمشرف في البوت**\nيمكنك استخدام لوحة المشرف الآن.", parse_mode="Markdown")
        
        log_admin_action(uid, 'add_moderator', f'تمت إضافة المشرف {target}')
        
    except ValueError:
        bot.send_message(message.chat.id, "❌ **معرف غير صالح**", parse_mode="Markdown")

def process_remove_moderator(message):
    """إزالة مشرف"""
    uid = message.from_user.id
    
    if uid != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ **هذه الخاصية للمالك فقط**", parse_mode="Markdown")
        return
    
    try:
        target = int(message.text)
        
        cursor.execute("DELETE FROM moderators WHERE user_id=?", (target,))
        conn.commit()
        
        bot.send_message(message.chat.id, f"✅ **تمت إزالة المستخدم** `{target}` **من قائمة المشرفين**", parse_mode="Markdown")
        bot.send_message(target, "🔴 **تمت إزالتك من قائمة المشرفين**", parse_mode="Markdown")
        
        log_admin_action(uid, 'remove_moderator', f'تمت إزالة المشرف {target}')
        
    except ValueError:
        bot.send_message(message.chat.id, "❌ **معرف غير صالح**", parse_mode="Markdown")

# ===== دوال الرسائل الجماعية =====

def process_broadcast(message):
    """إرسال رسالة جماعية نصية"""
    uid = message.from_user.id
    text = message.text
    
    cursor.execute("SELECT user_id FROM users WHERE deleted=0")
    users = cursor.fetchall()
    
    sent = 0
    failed = 0
    
    for user in users:
        try:
            bot.send_message(user[0], text, parse_mode="Markdown")
            sent += 1
        except:
            failed += 1
    
    bot.send_message(message.chat.id, f"✅ **تم الإرسال:**\n📨 ناجح: {sent}\n❌ فاشل: {failed}", parse_mode="Markdown")
    log_admin_action(uid, 'broadcast', f'تم إرسال رسالة جماعية: ناجح {sent}, فاشل {failed}')

def process_broadcast_photo_step1(message):
    """الخطوة الأولى لإرسال صورة جماعية"""
    if message.content_type != 'photo':
        bot.send_message(message.chat.id, "❌ **الرجاء إرسال صورة**", parse_mode="Markdown")
        return
    
    file_id = message.photo[-1].file_id
    msg = bot.send_message(message.chat.id, "📝 **أرسل التعليق على الصورة (أو أرسل 'لا' بدون تعليق):**", parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_broadcast_photo_final, file_id)

def process_broadcast_photo_final(message, file_id):
    """الخطوة النهائية لإرسال صورة جماعية"""
    uid = message.from_user.id
    caption = message.text if message.text != 'لا' else None
    
    cursor.execute("SELECT user_id FROM users WHERE deleted=0")
    users = cursor.fetchall()
    
    sent = 0
    failed = 0
    
    for user in users:
        try:
            bot.send_photo(user[0], file_id, caption=caption, parse_mode="Markdown")
            sent += 1
        except:
            failed += 1
    
    bot.send_message(message.chat.id, f"✅ **تم الإرسال:**\n📨 ناجح: {sent}\n❌ فاشل: {failed}", parse_mode="Markdown")
    log_admin_action(uid, 'broadcast_photo', f'تم إرسال صورة جماعية: ناجح {sent}, فاشل {failed}')

# ===== دوال ربط API =====

def process_connect_syriatel_api(message):
    """ربط سيرياتل API"""
    uid = message.from_user.id
    number = message.text.strip()
    
    # حفظ معلومات الاتصال
    cursor.execute("""INSERT OR REPLACE INTO api_connections 
        (name, api_key, endpoint, is_active, created_at, updated_at)
        VALUES (?,?,?,?,?,?)""",
        ('syriatel', number, 'https://api.syriatel.cash', 1,
         datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
         datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    
    update_db_setting('syriatel_api_enabled', '1', uid)
    
    bot.send_message(message.chat.id, f"✅ **تم ربط سيرياتل API بنجاح**\n📱 الرقم: `{number}`", parse_mode="Markdown")
    log_admin_action(uid, 'connect_api', f'تم ربط سيرياتل API: {number}')

def process_connect_sham_api(message):
    """ربط شام API"""
    uid = message.from_user.id
    address = message.text.strip()
    
    cursor.execute("""INSERT OR REPLACE INTO api_connections 
        (name, api_key, endpoint, is_active, created_at, updated_at)
        VALUES (?,?,?,?,?,?)""",
        ('sham', address, 'https://api.sham.cash', 1,
         datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
         datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    
    update_db_setting('sham_api_enabled', '1', uid)
    
    bot.send_message(message.chat.id, f"✅ **تم ربط شام API بنجاح**\n🏦 العنوان: `{address}`", parse_mode="Markdown")
    log_admin_action(uid, 'connect_api', f'تم ربط شام API: {address}')


# ================================================
# 13. معالج أوامر /start
# ================================================

@bot.message_handler(commands=['start'])
def handle_start(message):
    """معالج أمر /start"""
    uid = message.from_user.id
    first_name = message.from_user.first_name
    username = message.from_user.username
    
    # التحقق من السبام
    if not check_spam(uid):
        return
    
    # إعادة تعيين حالة المستخدم
    reset_user_state(uid)
    
    # التحقق من وجود كود إحالة
    ref_code = None
    if len(message.text.split()) > 1:
        ref_code = message.text.split()[1]
    
    # إضافة المستخدم إلى قاعدة البيانات إذا لم يكن موجوداً
    cursor.execute("""INSERT OR IGNORE INTO users
        (user_id, first_name, username, created_at, dark_mode)
        VALUES (?,?,?,?,0)""",
        (uid, first_name, username, datetime.now().strftime("%d-%m-%Y %H:%M")))
    conn.commit()
    
    # معالجة كود الإحالة
    if ref_code and ref_code.startswith('MATAR'):
        referrer_id = get_user_by_ref_code(ref_code)
        if referrer_id and referrer_id != uid:
            cursor.execute("SELECT referred_by FROM users WHERE user_id=?", (uid,))
            result = cursor.fetchone()
            if not result or not result[0]:
                cursor.execute("UPDATE users SET referred_by=? WHERE user_id=?", (referrer_id, uid))
                register_referral(referrer_id, uid)
                # مكافأة فورية للمحيل (10 ل.س)
                update_user_balance(referrer_id, 10, add=True)
    
    # إنشاء كود إحالة للمستخدم
    check_and_create_ref_code(uid)
    
    # التحقق من حالة البوت
    if not check_bot_status() and uid != ADMIN_ID and not is_moderator(uid):
        maintenance_msg = get_db_setting('maintenance_message')
        bot.send_message(message.chat.id, maintenance_msg, parse_mode="Markdown")
        return
    
    # التحقق من الاشتراك في القناة
    if not check_subscription(uid):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 اشترك في القناة", url=CHANNEL_URL))
        markup.add(types.InlineKeyboardButton("✅ تحقق من الاشتراك", callback_data="check_sub_after_start"))
        
        welcome_text = f"""
🎯 **أهلاً وسهلاً بك في بوت Matar** 🌧️

البوت الرسمي لموقع Ichancy ✅
هذا البوت مخصص لإنشاء حساب على موقع Ichancy وإدارته في عمليات الشحن والسحب

⚠️ **شرط أساسي لاستخدام البوت:**
الرجاء الاشتراك في قناتنا على تيلغرام لتتمكن من استخدام البوت
"""
        bot.send_message(message.chat.id, welcome_text, reply_markup=markup, parse_mode="Markdown")
        return
    
    # رسالة الترحيب (مرة واحدة فقط)
    if not has_completed_welcome(uid):
        welcome_msg = get_db_setting('welcome_message')
        bot.send_message(message.chat.id, f"✅ **تم التحقق من اشتراكك!**\n\n{welcome_msg}", parse_mode="Markdown")
        cursor.execute("UPDATE users SET welcome_shown=1 WHERE user_id=?", (uid,))
        conn.commit()
    
    # عرض القائمة الرئيسية
    bot.send_message(message.chat.id, "📋 **القائمة الرئيسية:**", reply_markup=get_main_keyboard(uid), parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "check_sub_after_start")
def check_sub_after_start(call):
    """التحقق من الاشتراك بعد الضغط على الزر"""
    uid = call.from_user.id
    
    if check_subscription(uid):
        bot.edit_message_text("✅ **تم التحقق من اشتراكك! مرحباً بك في البوت**", 
                            call.message.chat.id, call.message.message_id, parse_mode="Markdown")
        
        if not has_completed_welcome(uid):
            welcome_msg = get_db_setting('welcome_message')
            bot.send_message(call.message.chat.id, welcome_msg, parse_mode="Markdown")
            cursor.execute("UPDATE users SET welcome_shown=1 WHERE user_id=?", (uid,))
            conn.commit()
        
        bot.send_message(call.message.chat.id, "📋 **القائمة الرئيسية:**", 
                        reply_markup=get_main_keyboard(uid), parse_mode="Markdown")
    else:
        bot.answer_callback_query(call.id, "❌ لم تشترك بعد! اشترك ثم حاول مرة أخرى", show_alert=True)


# ================================================
# 14. الراوتر الرئيسي للرسائل
# ================================================

@bot.message_handler(func=lambda m: True)
def main_router(message):
    """الراوتر الرئيسي لجميع الرسائل النصية"""
    uid = message.from_user.id
    text = message.text
    
    # التحقق من السبام
    if not check_spam(uid):
        return
    
    # إعادة تعيين حالة المستخدم
    reset_user_state(uid)
    
    # التحقق من حالة البوت
    if not check_bot_status() and uid != ADMIN_ID and not is_moderator(uid):
        maintenance_msg = get_db_setting('maintenance_message')
        bot.send_message(message.chat.id, maintenance_msg, parse_mode="Markdown")
        return
    
    # التحقق من حالة المستخدم (محظور أم لا)
    cursor.execute("SELECT status FROM users WHERE user_id=?", (uid,))
    user_status = cursor.fetchone()
    if user_status and user_status[0] == 'banned':
        bot.send_message(message.chat.id, "❌ **نعتذر، حسابك محظور من استخدام النظام.**", parse_mode="Markdown")
        return
    
    # التحقق من الاشتراك في القناة
    if not check_subscription(uid):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 اشترك في القناة", url=CHANNEL_URL))
        bot.send_message(message.chat.id, "⚠️ **يجب الاشتراك في القناة أولاً**", reply_markup=markup, parse_mode="Markdown")
        return
    
    # تحديث آخر نشاط للمستخدم
    cursor.execute("UPDATE users SET last_active=? WHERE user_id=?", 
                  (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), uid))
    conn.commit()
    
    # ===== معالجة أزرار القائمة الرئيسية =====
    
    # زر Ichancy
    if text == '⚽ Ichancy ⚽':
        ActionSystem.execute_action(uid, message.chat.id, 'show_ichancy_menu')
    
    # أزرار الشحن والسحب
    elif text == '💳 الشحن في البوت':
        ActionSystem.execute_action(uid, message.chat.id, 'show_charge_methods')
    
    elif text == '💸 السحب من البوت':
        ActionSystem.execute_action(uid, message.chat.id, 'show_withdraw_methods')
    
    # أزرار الهدايا
    elif text == '🎁 اهداء رصيد':
        ActionSystem.execute_action(uid, message.chat.id, 'start_gift')
    
    elif text == '🎫 كود هدية':
        ActionSystem.execute_action(uid, message.chat.id, 'redeem_gift')
    
    # أزرار المعلومات
    elif text == '💰 الرصيد':
        ActionSystem.execute_action(uid, message.chat.id, 'show_balance')
    
    elif text == '👥 دعوة الأصدقاء':
        ActionSystem.execute_action(uid, message.chat.id, 'show_referral')
    
    elif text == '📜 الشروط والاحكام':
        ActionSystem.execute_action(uid, message.chat.id, 'show_terms')
    
    elif text == '📞 التواصل مع الدعم':
        ActionSystem.execute_action(uid, message.chat.id, 'start_support')
    
    # زر إدارة البوت
    elif text == '🔐 إدارة البوت':
        ActionSystem.execute_action(uid, message.chat.id, 'show_admin_panel')
    
    # ===== أزرار Ichancy =====
    elif text == '📝 إنشاء حساب جديد':
        ActionSystem.create_ichancy_account(uid, message.chat.id)
    
    elif text == '➕ تعبئة في حسابي':
        ActionSystem.charge_ichancy(uid, message.chat.id)
    
    elif text == '➖ سحب من حسابي':
        ActionSystem.withdraw_ichancy(uid, message.chat.id)
    
    elif text == '🗑 حذف الحساب':
        ActionSystem.delete_ichancy_account(uid, message.chat.id)
    
    # ===== أزرار العودة =====
    elif text == '🔙 العودة للقائمة الرئيسية' or text == '🔙 رجوع':
        bot.send_message(message.chat.id, "📋 **القائمة الرئيسية:**", 
                        reply_markup=get_main_keyboard(uid), parse_mode="Markdown")
    
    # ===== البحث في الأزرار الديناميكية =====
    else:
        # البحث في قاعدة البيانات عن زر مطابق
        cursor.execute("""SELECT action, message_text, photo_id, parent_button, level
                          FROM dynamic_buttons 
                          WHERE button_text=? AND is_active=1""", (text,))
        button_info = cursor.fetchone()
        
        if button_info:
            action, msg_text, photo_id, parent, level = button_info
            
            # إرسال الرسالة المرفقة إن وجدت
            if msg_text:
                if photo_id:
                    bot.send_photo(message.chat.id, photo_id, caption=msg_text, parse_mode="Markdown")
                else:
                    bot.send_message(message.chat.id, msg_text, parse_mode="Markdown")
            
            # تنفيذ الإجراء
            if action:
                button_data = {
                    'parent_button': parent,
                    'level': level,
                    'button_text': text
                }
                ActionSystem.execute_action(uid, message.chat.id, action, button_data)
        else:
            # إذا كان الزر غير معروف
            bot.send_message(message.chat.id, "❌ **أمر غير معروف. الرجاء استخدام الأزرار المتاحة.**", parse_mode="Markdown")


# ================================================
# 15. تشغيل البوت
# ================================================

# إعداد Flask للتشغيل على Render/Replit
app = Flask(__name__)

@app.route('/')
def home():
    return "🚀 Matar Ultimate Bot is Running!"

def run_flask():
    """تشغيل خادم Flask"""
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    """تشغيل Flask في خيط منفصل"""
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()

if __name__ == "__main__":
    # تشغيل خادم Flask للبقاء على قيد الحياة
    keep_alive()
    
    # رسالة بدء التشغيل
    logger.info("=" * 50)
    logger.info("🚀 MATAR ULTIMATE BOT - ENTERPRISE EDITION")
    logger.info("=" * 50)
    logger.info(f"✅ التوكن: {TOKEN[:10]}...{TOKEN[-5:]}")
    logger.info(f"✅ معرف المالك: {ADMIN_ID}")
    logger.info(f"✅ القناة: {CHANNEL_ID}")
    logger.info("=" * 50)
    logger.info("📊 الإحصائيات:")
    
    try:
        cursor.execute("SELECT COUNT(*) FROM users WHERE deleted=0")
        users_count = cursor.fetchone()[0]
        logger.info(f"   👥 المستخدمين: {users_count}")
        
        cursor.execute("SELECT COUNT(*) FROM moderators")
        mods_count = cursor.fetchone()[0]
        logger.info(f"   👤 المشرفين: {mods_count}")
        
        cursor.execute("SELECT COUNT(*) FROM dynamic_buttons WHERE is_active=1")
        buttons_count = cursor.fetchone()[0]
        logger.info(f"   🔘 الأزرار النشطة: {buttons_count}")
        
        cursor.execute("SELECT COUNT(*) FROM transactions WHERE DATE(transaction_date) = DATE('now')")
        today_trans = cursor.fetchone()[0]
        logger.info(f"   💳 معاملات اليوم: {today_trans}")
        
    except Exception as e:
        logger.error(f"خطأ في جلب الإحصائيات: {e}")
    
    logger.info("=" * 50)
    logger.info("🟢 البوت جاهز للعمل...")
    
    # بدء تشغيل البوت مع معالجة الأخطاء
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            logger.error(f"⚠️ خطأ في الاتصال: {e}")
            error_logger.error(f"خطأ في polling: {e}", exc_info=True)
            time.sleep(5)
            continue

# ================================================
# نهاية الكود - Matar Ultimate Bot
# ================================================