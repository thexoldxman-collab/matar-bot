import telebot
from telebot import types
import sqlite3
import os
from flask import Flask
from threading import Thread

# 1. الإعدادات الأساسية (الآيدي الخاص بك مثبت هنا)
TOKEN = os.environ.get('TOKEN')
bot = telebot.TeleBot(TOKEN)
ADMIN_ID = 846938470  # الآيدي الصحيح الخاص بك
CHANNEL_ID = "@Matar_ichancy"
CHANNEL_URL = "https://t.me/Matar_ichancy"

app = Flask('')
@app.route('/')
def home(): return "Matar Bot is Online!"

def run(): app.run(host='0.0.0.0', port=8080)
def keep_alive():
    t = Thread(target=run)
    t.start()

# 2. قاعدة البيانات
conn = sqlite3.connect("matar_pro.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, acc_name TEXT, acc_id TEXT, balance REAL DEFAULT 0, has_account INTEGER DEFAULT 0)")
conn.commit()

# --- وظيفة التحقق من الاشتراك ---
def is_subscribed(user_id):
    try:
        status = bot.get_chat_member(CHANNEL_ID, user_id).status
        return status in ['member', 'administrator', 'creator']
    except: return False

# 3. القوائم
def main_kb(user_id):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(types.KeyboardButton('⚽ ايشانسي | Ichancy ⚽'))
    markup.add(types.KeyboardButton('🔽 الشحن في البوت 🔽'), types.KeyboardButton('🔼 السحب من البوت 🔼'))
    markup.add(types.KeyboardButton('💵 الرصيد 💵'), types.KeyboardButton('🎁 كود هدية'))
    markup.add(types.KeyboardButton('💰 دعوة الأصدقاء 💰'), types.KeyboardButton('💬 التواصل مع الدعم 💬'))
    if user_id == ADMIN_ID:
        markup.add(types.KeyboardButton('🔐 إدارة البوت'))
    return markup

def deposit_kb():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add('🇸🇾 سيريتل كاش', '💎 شام كاش')
    markup.add('🔙 العودة')
    return markup

# 4. معالجة الأوامر
@bot.message_handler(commands=['start'])
def start(message):
    uid = message.from_user.id
    if not is_subscribed(uid):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("اضغط هنا للاشتراك", url=CHANNEL_URL))
        bot.send_message(message.chat.id, "⚠️ يجب عليك الاشتراك بقناة البوت أولاً!", reply_markup=markup)
        return

    cursor.execute("SELECT has_account FROM users WHERE user_id=?", (uid,))
    res = cursor.fetchone()
    if not res or res[0] == 0:
        bot.send_message(message.chat.id, "Welcome to MATAR 🎯\nاضغط إنشاء حساب للبدء.", 
                         reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add('✨ إنشاء حساب'))
    else:
        bot.send_message(message.chat.id, "أهلاً بك في مطر 🌧️", reply_markup=main_kb(uid))

@bot.message_handler(func=lambda m: True)
def handle_all(m):
    uid = m.from_user.id
    if not is_subscribed(uid): return

    if m.text == '✨ إنشاء حساب':
        msg = bot.send_message(m.chat.id, "أدخل اسم حسابك في ايشانسي:")
        bot.register_next_step_handler(msg, save_name)

    elif m.text == '🔐 إدارة البوت' and uid == ADMIN_ID:
        admin_markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
        admin_markup.add('📢 إذاعة عامة', '📊 الإحصائيات', '🔙 العودة')
        bot.send_message(uid, "🔓 لوحة تحكم الإدارة مفتوحة:", reply_markup=admin_markup)

    elif m.text == '🔽 الشحن في البوت 🔽':
        bot.send_message(m.chat.id, "اختر وسيلة الشحن:", reply_markup=deposit_kb())

    elif m.text == '🇸🇾 سيريتل كاش':
        bot.send_message(m.chat.id, "💳 **سيريتل كاش**\nحول للرقم: `09xxxxxxx` وأرسل الإشعار.")

    elif m.text == '💎 شام كاش':
        bot.send_message(m.chat.id, "💎 **شام كاش**\nحول للعنوان: `SHAM-XXXX` وأرسل الإشعار.")

    elif m.text == '🔙 العودة':
        bot.send_message(uid, "العودة للقائمة الرئيسية..", reply_markup=main_kb(uid))

    elif m.text == '⚽ ايشانسي | Ichancy ⚽':
        cursor.execute("SELECT acc_name, acc_id, balance FROM users WHERE user_id=?", (uid,))
        user = cursor.fetchone()
        if user:
            text = f"👤 الاسم: {user[0]}\n🆔 ID: {user[1]}\n💰 الرصيد: {user[2]} NSP"
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(types.InlineKeyboardButton("➕ شحن", callback_data="dep"), types.InlineKeyboardButton("➖ سحب", callback_data="wit"))
            markup.add(types.InlineKeyboardButton("❌ حذف الحساب", callback_data="confirm_delete"))
            bot.send_message(m.chat.id, text, reply
