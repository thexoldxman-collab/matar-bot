import telebot
from telebot import types
from flask import Flask
from threading import Thread
import os
import sqlite3

# ===========================
# إعداد البوت والسيرفر
# ===========================
TOKEN = os.environ.get('TOKEN')
bot = telebot.TeleBot(TOKEN)
app = Flask('')

@app.route('/')
def home():
    return "I am alive!"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

# ===========================
# قاعدة البيانات SQLite
# ===========================
conn = sqlite3.connect("matar.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users(
    user_id INTEGER PRIMARY KEY,
    account_name TEXT,
    password TEXT,
    balance REAL DEFAULT 0,
    has_account INTEGER DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS gift_codes(
    code TEXT PRIMARY KEY,
    value REAL,
    used_by TEXT
)
""")

conn.commit()

# ===========================
# التحقق من الاشتراك بالقناة
# ===========================
CHANNEL_ID = "@Matar_ichancy"

def is_subscribed(user_id):
    try:
        member = bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

# ===========================
# الأدمن
# ===========================
ADMINS = [123456789]  # ضع ID تيليغرام تبعك هون

def is_admin(user_id):
    return user_id in ADMINS

# ===========================
# لوحة المفاتيح الرئيسية ديناميكياً لكل رسالة
# ===========================
def main_keyboard(user_id):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    # زر ichancy أول خانة لحاله
    btn1 = types.KeyboardButton('ichancy')
    markup.add(btn1)

    # باقي الأزرار
    btn2 = types.KeyboardButton('الشحن في البوت')
    btn3 = types.KeyboardButton('السحب من البوت')
    btn4 = types.KeyboardButton('اهداء صديق')
    btn5 = types.KeyboardButton('كود هدية')
    btn6 = types.KeyboardButton('الرصيد')
    btn7 = types.KeyboardButton('التواصل مع الدعم')
    if is_admin(user_id):
        btn8 = types.KeyboardButton('إدارة البوت')
        markup.add(btn2, btn3, btn4, btn5, btn6, btn7, btn8)
    else:
        markup.add(btn2, btn3, btn4, btn5, btn6, btn7)
    return markup

# ===========================
# /start
# ===========================
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id

    # تحقق من الاشتراك بالقناة
    if not is_subscribed(user_id):
        bot.send_message(message.chat.id,
                         f"أهلاً بك! 🌧️\nالرجاء الاشتراك في قناتنا لتتمكن من استخدام البوت: {CHANNEL_ID}")
        return

    cursor.execute("SELECT has_account FROM users WHERE user_id=?", (user_id,))
    result = cursor.fetchone()
    if not result:
        bot.send_message(message.chat.id,
                         f"مرحباً بك في بوت Matar الرسمي لموقع iChancy 🌧️\n"
                         "هذا البوت مخصص لإنشاء الحساب وإدارة الشحن والسحب.")
    bot.send_message(message.chat.id, "اختر الخدمة المطلوبة:", reply_markup=main_keyboard(user_id))

# ===========================
# التعامل مع الرسائل
# ===========================
@bot.message_handler(func=lambda message: True)
def handle_msg(message):
    user_id = message.from_user.id
    text = message.text

    # تحقق الاشتراك بالقناة
    if not is_subscribed(user_id):
        bot.send_message(message.chat.id,
                         f"الرجاء الاشتراك بالقناة لتتمكن من استخدام البوت: {CHANNEL_ID}")
        return

    # ===========================
    # زر ichancy
    # ===========================
    if text == 'ichancy':
        cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
        user = cursor.fetchone()
        if not user or user[4] == 0:  # لا يوجد حساب
            markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
            btn = types.KeyboardButton('إنشاء حساب ichancy')
            markup.add(btn)
            bot.send_message(message.chat.id,
                             "أهلاً بك! لإنشاء حساب، اضغط على الزر أدناه:", reply_markup=markup)
        else:
            bot.send_message(message.chat.id,
                             f"اسم الحساب: {user[1]}\nID: {user[0]}\nرصيدك على الموقع: {user[3]}")  # لاحقاً API

    # ===========================
    # زر إنشاء الحساب
    # ===========================
    elif text == 'إنشاء حساب ichancy':
        msg = bot.send_message(message.chat.id, "ادخل اسم الحساب بالأحرف الإنكليزية فقط:")
        bot.register_next_step_handler(msg, enter_account_name)

# ===========================
# دوال إنشاء الحساب (محسّنة)
# ===========================
def enter_account_name(message):
    name = message.text.strip()
    if not name.isalnum():
        msg = bot.send_message(message.chat.id,
                               "الاسم يجب أن يحتوي أحرف وأرقام إنكليزية فقط. حاول مرة أخرى:")
        bot.register_next_step_handler(msg, enter_account_name)
        return
    full_name = f"Matar-{name}"
    msg = bot.send_message(message.chat.id, "ادخل كلمة المرور بالأحرف والأرقام فقط:")
    bot.register_next_step_handler(msg, enter_password, full_name)

def enter_password(message, full_name):
    password = message.text.strip()
    if not password.isalnum():
        msg = bot.send_message(message.chat.id, "كلمة المرور يجب أن تحتوي أحرف وأرقام فقط. حاول مرة أخرى:")
        bot.register_next_step_handler(msg, enter_password, full_name)
        return
    user_id = message.from_user.id
    cursor.execute("INSERT OR REPLACE INTO users(user_id, account_name, password, balance, has_account) VALUES(?,?,?,?,?)",
                   (user_id, full_name, password, 0, 1))
    conn.commit()
    bot.send_message(message.chat.id, f"تم إنشاء حسابك بنجاح 🌧️\nأهلاً وسهلاً بك في بوت Matar!")

# ===========================
# باقي الأزرار والوظائف مثل الشحن، السحب، الهدايا، الرصيد، الدعم، وأزرار الأدمن
# ===========================
# نفس الكود السابق بدون تغيير
# ===========================

# ===========================
# تشغيل البوت
# ===========================
if __name__ == "__main__":
    keep_alive()
    print("بوت مطر يعمل الآن مع ميزة عدم النوم...")
    bot.polling(none_stop=True)
