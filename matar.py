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
# إعداد قاعدة البيانات SQLite
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
# زر البداية ichancy
# ===========================
def main_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn1 = types.KeyboardButton('ichancy')
    btn2 = types.KeyboardButton('الشحن في البوت')
    btn3 = types.KeyboardButton('السحب من البوت')
    btn4 = types.KeyboardButton('اهداء صديق')
    btn5 = types.KeyboardButton('كود هدية')
    btn6 = types.KeyboardButton('الرصيد')
    btn7 = types.KeyboardButton('التواصل مع الدعم')
    if is_admin(current_user_id):
        btn8 = types.KeyboardButton('إدارة البوت')
        markup.add(btn1, btn2, btn3, btn4, btn5, btn6, btn7, btn8)
    else:
        markup.add(btn1, btn2, btn3, btn4, btn5, btn6, btn7)
    return markup

current_user_id = None  # متغير لحفظ ID المستخدم الحالي أثناء التعامل

@bot.message_handler(commands=['start'])
def start(message):
    global current_user_id
    current_user_id = message.from_user.id

    # تحقق من الاشتراك بالقناة
    if not is_subscribed(current_user_id):
        bot.send_message(message.chat.id,
                         f"أهلاً بك! 🌧️\nالرجاء الاشتراك في قناتنا لتتمكن من استخدام البوت: {CHANNEL_ID}")
        return

    cursor.execute("SELECT has_account FROM users WHERE user_id=?", (current_user_id,))
    result = cursor.fetchone()
    if not result:
        bot.send_message(message.chat.id,
                         f"مرحباً بك في بوت Matar الرسمي لموقع iChancy 🌧️\n"
                         "هذا البوت مخصص لإنشاء الحساب وإدارة الشحن والسحب.")
    bot.send_message(message.chat.id, "اختر الخدمة المطلوبة:", reply_markup=main_keyboard())

# ===========================
# التعامل مع الرسائل
# ===========================
@bot.message_handler(func=lambda message: True)
def handle_msg(message):
    global current_user_id
    current_user_id = message.from_user.id
    text = message.text

    # تحقق الاشتراك بالقناة
    if not is_subscribed(current_user_id):
        bot.send_message(message.chat.id,
                         f"الرجاء الاشتراك بالقناة لتتمكن من استخدام البوت: {CHANNEL_ID}")
        return

    # ===========================
    # زر ichancy
    # ===========================
    if text == 'ichancy':
        cursor.execute("SELECT * FROM users WHERE user_id=?", (current_user_id,))
        user = cursor.fetchone()
        if not user or user[4] == 0:  # لا يوجد حساب
            markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
            btn = types.KeyboardButton('إنشاء حساب ايشانسي')
            markup.add(btn)
            bot.send_message(message.chat.id,
                             "أهلاً بك! لإنشاء حساب، اضغط على الزر أدناه:", reply_markup=markup)
        else:  # لديه حساب
            bot.send_message(message.chat.id,
                             f"اسم الحساب: {user[1]}\nID: {user[0]}\nرصيدك على الموقع: {user[3]}")  # لاحقاً API

    # ===========================
    # زر إنشاء حساب
    # ===========================
    elif text == 'إنشاء حساب ايشانسي':
        msg = bot.send_message(message.chat.id, "ادخل اسم حسابك بالأحرف الإنكليزية:")
        bot.register_next_step_handler(msg, enter_account_name)

    # ===========================
    # زر الشحن في البوت
    # ===========================
    elif text == 'الشحن في البوت':
        markup = types.InlineKeyboardMarkup()
        p1 = types.InlineKeyboardButton("سيرياتل كاش 📱", callback_data="pay_syriatel")
        p2 = types.InlineKeyboardButton("شام كاش 💳", callback_data="pay_cham")
        p3 = types.InlineKeyboardButton("USDT", callback_data="pay_usdt")
        p4 = types.InlineKeyboardButton("بينانس", callback_data="pay_binance")
        markup.add(p1, p2)
        markup.add(p3, p4)
        bot.send_message(message.chat.id, "اختر وسيلة الشحن:", reply_markup=markup)

    # ===========================
    # زر السحب من البوت
    # ===========================
    elif text == 'السحب من البوت':
        markup = types.InlineKeyboardMarkup()
        s1 = types.InlineKeyboardButton("سيرياتل كاش 📱", callback_data="withdraw_syriatel")
        s2 = types.InlineKeyboardButton("شام كاش 💳", callback_data="withdraw_cham")
        s3 = types.InlineKeyboardButton("USDT", callback_data="withdraw_usdt")
        s4 = types.InlineKeyboardButton("بينانس", callback_data="withdraw_binance")
        markup.add(s1, s2)
        markup.add(s3, s4)
        bot.send_message(message.chat.id, "اختر وسيلة السحب:", reply_markup=markup)

    # ===========================
    # زر اهداء صديق
    # ===========================
    elif text == 'اهداء صديق':
        msg = bot.send_message(message.chat.id, "ادخل معرف ID الشخص المراد إرسال الرصيد إليه:")
        bot.register_next_step_handler(msg, enter_gift_id)

    # ===========================
    # زر كود هدية
    # ===========================
    elif text == 'كود هدية':
        msg = bot.send_message(message.chat.id, "ادخل كود الهدية:")
        bot.register_next_step_handler(msg, enter_gift_code)

    # ===========================
    # زر الرصيد
    # ===========================
    elif text == 'الرصيد':
        cursor.execute("SELECT balance FROM users WHERE user_id=?", (current_user_id,))
        user = cursor.fetchone()
        balance = user[0] if user else 0
        bot.send_message(message.chat.id, f"رصيدك الحالي: {balance}")

    # ===========================
    # زر التواصل مع الدعم
    # ===========================
    elif text == 'التواصل مع الدعم':
        msg = bot.send_message(message.chat.id, "الرجاء كتابة رسالتك وإرسالها:")
        bot.register_next_step_handler(msg, handle_support_message)

    # ===========================
    # زر إدارة البوت (أدمن)
    # ===========================
    elif text == 'إدارة البوت' and is_admin(current_user_id):
        markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
        btn1 = types.KeyboardButton('إنشاء كود هدية')
        btn2 = types.KeyboardButton('حظر مستخدم')
        btn3 = types.KeyboardButton('شحن رصيد لمستخدم')
        btn4 = types.KeyboardButton('سحب رصيد لمستخدم')
        btn5 = types.KeyboardButton('إنشاء حساب يدوي')
        btn6 = types.KeyboardButton('سجلات البوت')
        btn7 = types.KeyboardButton('إرسال رسائل جماعية')
        markup.add(btn1, btn2, btn3, btn4, btn5, btn6, btn7)
        bot.send_message(message.chat.id, "خيارات الأدمن:", reply_markup=markup)

# ===========================
# دوال لإنشاء الحساب
# ===========================
def enter_account_name(message):
    account_name = message.text
    if not account_name.isalnum():
        msg = bot.send_message(message.chat.id, "الاسم يجب أن يحتوي أحرف وأرقام إنكليزية فقط. حاول مرة أخرى:")
        bot.register_next_step_handler(msg, enter_account_name)
        return
    full_name = f"Matar-{account_name}"
    msg = bot.send_message(message.chat.id, "ادخل كلمة المرور بالأحرف والأرقام فقط:")
    bot.register_next_step_handler(msg, enter_password, full_name)

def enter_password(message, full_name):
    password = message.text
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
# دوال اهداء صديق
# ===========================
def enter_gift_id(message):
    recipient_id = message.text
    cursor.execute("SELECT * FROM users WHERE user_id=?", (recipient_id,))
    user = cursor.fetchone()
    if not user:
        bot.send_message(message.chat.id, "عذراً، لا يمكنك إهداء رصيد. هذا الشخص لا يملك حساب على بوت Matar")
        return
    msg = bot.send_message(message.chat.id, "ادخل قيمة المبلغ المراد إهداؤه:")
    bot.register_next_step_handler(msg, enter_gift_amount, recipient_id)

def enter_gift_amount(message, recipient_id):
    try:
        amount = float(message.text)
    except:
        msg = bot.send_message(message.chat.id, "الرجاء إدخال رقم صحيح:")
        bot.register_next_step_handler(msg, enter_gift_amount, recipient_id)
        return
    sender_id = message.from_user.id
    cursor.execute("SELECT balance FROM users WHERE user_id=?", (sender_id,))
    sender_balance = cursor.fetchone()[0]
    if sender_balance < amount:
        bot.send_message(message.chat.id, "رصيدك غير كافي لإتمام الإهداء.")
        return
    # خصم من المرسل
    cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id=?", (amount, sender_id))
    # إضافة للمستلم
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount, recipient_id))
    conn.commit()
    bot.send_message(message.chat.id, f"تم إهداء رصيد بقيمة {amount} بنجاح 🎁")

# ===========================
# دوال كود هدية
# ===========================
def enter_gift_code(message):
    code = message.text
    cursor.execute("SELECT value, used_by FROM gift_codes WHERE code=?", (code,))
    result = cursor.fetchone()
    if not result:
        bot.send_message(message.chat.id, "الكود غير صالح.")
        return
    value, used_by = result
    if used_by:
        bot.send_message(message.chat.id, "تم استخدام هذا الكود مسبقاً.")
        return
    user_id = message.from_user.id
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (value, user_id))
    cursor.execute("UPDATE gift_codes SET used_by=? WHERE code=?", (user_id, code))
    conn.commit()
    bot.send_message(message.chat.id, f"تم شحن رصيد بمبلغ {value} 💰")

# ===========================
# دوال التواصل مع الدعم
# ===========================
def handle_support_message(message):
    support_text = message.text
    bot.send_message(message.chat.id, "تم استلام رسالتك، وسيتم الرد عليك في أقرب وقت ⏳")
    for admin_id in ADMINS:
        bot.send_message(admin_id, f"رسالة جديدة من {message.from_user.first_name} (ID: {message.from_user.id}):\n{support_text}")

# ===========================
# Callbacks للشحن والسحب
# ===========================
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    # الشحن
    if call.data == "pay_syriatel":
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id,
                         "🚀 تم اختيار سيرياتل كاش.\n"
                         "الرجاء التحويل إلى الكود التالي [ضع الكود من لوحة التحكم]\n"
                         "طريقة التحويل: يدوي حصراً\n"
                         "أقل مبلغ للشحن: 100 ليرة جديدة\n"
                         "ثم إدخال رقم العملية")
    elif call.data == "pay_cham":
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id,
                         "🚀 تم اختيار شام كاش.\n"
                         "الرجاء إرسال المبلغ إلى العنوان التالي [ضع العنوان من لوحة التحكم]\n"
                         "ثم إدخال رقم العملية")
    elif call.data in ["pay_usdt", "pay_binance"]:
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "عذراً، الشحن بهذه الطريقة متوقف حالياً")

    # السحب
    elif call.data in ["withdraw_usdt", "withdraw_binance"]:
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "عذراً، السحب بهذه الطريقة متوقف حالياً")

# ===========================
# تشغيل البوت
# ===========================
if __name__ == "__main__":
    keep_alive()
    print("بوت مطر يعمل الآن مع ميزة عدم النوم...")
    bot.polling(none_stop=True)
