Import telebot
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

# جدول المستخدمين
cursor.execute("""
CREATE TABLE IF NOT EXISTS users(
    user_id INTEGER PRIMARY KEY,
    account_name TEXT,
    password TEXT,
    balance REAL DEFAULT 0,
    has_account INTEGER DEFAULT 0
)
""")

# جدول أكواد الهدايا
cursor.execute("""
CREATE TABLE IF NOT EXISTS gift_codes(
    code TEXT PRIMARY KEY,
    value REAL,
    used_by TEXT
)
""")

# جدول رسائل الدعم
cursor.execute("""
CREATE TABLE IF NOT EXISTS support_msgs(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    message TEXT
)
""")

conn.commit()

# ===========================
# إعداد القناة والأدمن
# ===========================
CHANNEL_ID = "@Matar_ichancy"
ADMINS = [123456789]  # ضع ID تيليغرام تبعك هون

def is_subscribed(user_id):
    try:
        member = bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

def is_admin(user_id):
    return user_id in ADMINS

# ===========================
# لوحة المفاتيح الرئيسية
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

    if not is_subscribed(user_id):
        bot.send_message(message.chat.id,
                         f"الرجاء الاشتراك بالقناة لتتمكن من استخدام البوت: {CHANNEL_ID}")
        return

    # ======== زر ichancy ========
    if text == 'ichancy':
        cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
        user = cursor.fetchone()
        if not user or user[4] == 0:
            markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
            btn = types.KeyboardButton('إنشاء حساب ichancy')
            markup.add(btn)
            bot.send_message(message.chat.id,
                             "أهلاً بك! لإنشاء حساب، اضغط على الزر أدناه:", reply_markup=markup)
        else:
            bot.send_message(message.chat.id,
                             f"اسم الحساب: {user[1]}\nID: {user[0]}\nرصيدك على الموقع: {user[3]}")

    # ======== إنشاء حساب ========
    elif text == 'إنشاء حساب ichancy':
        msg = bot.send_message(message.chat.id, "ادخل اسم الحساب بالأحرف الإنكليزية فقط:")
        bot.register_next_step_handler(msg, enter_account_name)

    # ======== الشحن في البوت ========
    elif text == 'الشحن في البوت':
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("سيرياتل كاش 📱", callback_data="pay_syriatel"),
            types.InlineKeyboardButton("شام كاش 💳", callback_data="pay_cham")
        )
        markup.add(
            types.InlineKeyboardButton("USDT", callback_data="pay_usdt"),
            types.InlineKeyboardButton("بينانس", callback_data="pay_binance")
        )
        bot.send_message(message.chat.id, "اختر وسيلة الشحن:", reply_markup=markup)

    # ======== السحب من البوت ========
    elif text == 'السحب من البوت':
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("سيرياتل كاش 📱", callback_data="withdraw_syriatel"),
            types.InlineKeyboardButton("شام كاش 💳", callback_data="withdraw_cham")
        )
        markup.add(
            types.InlineKeyboardButton("USDT", callback_data="withdraw_usdt"),
            types.InlineKeyboardButton("بينانس", callback_data="withdraw_binance")
        )
        bot.send_message(message.chat.id, "اختر وسيلة السحب:", reply_markup=markup)

    # ======== اهداء صديق ========
    elif text == 'اهداء صديق':
        msg = bot.send_message(message.chat.id, "ادخل معرف ID الشخص المراد إرسال الرصيد إليه:")
        bot.register_next_step_handler(msg, enter_gift_id)

    # ======== كود هدية ========
    elif text == 'كود هدية':
        msg = bot.send_message(message.chat.id, "ادخل كود الهدية:")
        bot.register_next_step_handler(msg, enter_gift_code)

    # ======== الرصيد ========
    elif text == 'الرصيد':
        cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
        user = cursor.fetchone()
        balance = user[0] if user else 0
        bot.send_message(message.chat.id, f"رصيدك الحالي: {balance}")

    # ======== التواصل مع الدعم ========
    elif text == 'التواصل مع الدعم':
        msg = bot.send_message(message.chat.id, "الرجاء كتابة رسالتك وإرسالها:")
        bot.register_next_step_handler(msg, handle_support_message)

    # ======== إدارة البوت ========
    elif text == 'إدارة البوت' and is_admin(user_id):
        markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
        markup.add(
            types.KeyboardButton('إنشاء كود هدية'),
            types.KeyboardButton('حظر مستخدم'),
            types.KeyboardButton('شحن رصيد لمستخدم'),
            types.KeyboardButton('سحب رصيد لمستخدم'),
            types.KeyboardButton('إنشاء حساب يدوي'),
            types.KeyboardButton('سجلات البوت'),
            types.KeyboardButton('إرسال رسائل جماعية')
        )
        bot.send_message(message.chat.id, "خيارات الأدمن:", reply_markup=markup)

# ===========================
# دوال إنشاء الحساب
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
    bot.send_message(message.chat.id, "اختر الخدمة المطلوبة:", reply_markup=main_keyboard(user_id))

# ===========================
# دوال الهدايا والدعم وأزرار callback الخاصة بالشحن والسحب
# ===========================
def enter_gift_id(message):
    # هنا ممكن تضيف منطق التحقق من وجود الحساب وتسجيل الرصيد
    bot.send_message(message.chat.id, "تم تسجيل ID، تابع الخطوات لاحقاً...")

def enter_gift_code(message):
    bot.send_message(message.chat.id, "تم التحقق من كود الهدية (نماذج)...")

def handle_support_message(message):
    user_id = message.from_user.id
    cursor.execute("INSERT INTO support_msgs(user_id, message) VALUES(?,?)", (user_id, message.text))
    conn.commit()
    bot.send_message(message.chat.id, "تم استلام رسالتك! سيتم الرد عليك بأقرب وقت.")

# ===========================
# تشغيل البوت
# ===========================
if name == "main":
    keep_alive()
    print("بوت مطر يعمل الآن مع ميزة عدم النوم...")
    bot.polling(none_stop=True)
