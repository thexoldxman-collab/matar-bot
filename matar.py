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
    return "Matar Bot is Online!"

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

cursor.execute("CREATE TABLE IF NOT EXISTS gift_codes(code TEXT PRIMARY KEY, value REAL, used_by TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS support_msgs(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, message TEXT)")
conn.commit()

# ===========================
# إعداد القناة والأدمن
# ===========================
CHANNEL_ID = "@Matar_ichancy"
CHANNEL_URL = "https://t.me/Matar_ichancy"
ADMINS = [846938470] # تم تثبيت الآيدي الخاص بك هنا

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
    btn1 = types.KeyboardButton('⚽ ichancy ⚽') # زر مستقل في أول الجدول
    markup.add(btn1)
    
    btn2 = types.KeyboardButton('🔽 الشحن في البوت 🔽')
    btn3 = types.KeyboardButton('🔼 السحب من البوت 🔼')
    btn4 = types.KeyboardButton('🎁 اهداء صديق')
    btn5 = types.KeyboardButton('🎫 كود هدية')
    btn6 = types.KeyboardButton('💵 الرصيد 💵')
    btn7 = types.KeyboardButton('💬 التواصل مع الدعم 💬')
    
    markup.add(btn2, btn3)
    markup.add(btn4, btn5)
    markup.add(btn6, btn7)
    
    if is_admin(user_id):
        markup.add(types.KeyboardButton('🔐 إدارة البوت'))
    return markup

# ===========================
# /start والتحقق
# ===========================
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    if not is_subscribed(user_id):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("اضغط للاشتراك بالقناة", url=CHANNEL_URL))
        bot.send_message(message.chat.id, "⚠️ يجب الاشتراك بالقناة أولاً لاستخدام البوت:", reply_markup=markup)
        return
    bot.send_message(message.chat.id, "مرحباً بك في بوت Matar الرسمي 🌧️", reply_markup=main_keyboard(user_id))

# ===========================
# التعامل مع الرسائل
# ===========================
@bot.message_handler(func=lambda message: True)
def handle_msg(message):
    user_id = message.from_user.id
    text = message.text

    if not is_subscribed(user_id): return

    # ======== زر ichancy المطوّر ========
    if text == '⚽ ichancy ⚽':
        cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
        user = cursor.fetchone()
        if not user or user[4] == 0:
            markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
            markup.add(types.KeyboardButton('✨ إنشاء حساب ichancy ✨'))
            bot.send_message(message.chat.id, "ليس لديك حساب حالياً، اضغط للإنشاء:", reply_markup=markup)
        else:
            info = f"👤 الاسم: {user[1]}\n🆔 الآيدي: {user[0]}\n💰 الرصيد: {user[3]} NSP"
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(types.InlineKeyboardButton("➕ شحن في الحساب", callback_data="dep_acc"),
                       types.InlineKeyboardButton("➖ سحب من الحساب", callback_data="wit_acc"))
            markup.add(types.InlineKeyboardButton("❌ حذف الحساب", callback_data="confirm_del"))
            bot.send_message(message.chat.id, info, reply_markup=markup)

    elif text == '✨ إنشاء حساب ichancy ✨':
        msg = bot.send_message(message.chat.id, "ادخل اسم الحساب بالأحرف الإنكليزية:")
        bot.register_next_step_handler(msg, enter_account_name)

    # ======== الشحن في البوت ========
    elif text == '🔽 الشحن في البوت 🔽':
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("سيرياتل كاش 📱", callback_data="p_s"),
                   types.InlineKeyboardButton("شام كاش 💳", callback_data="p_c"))
        bot.send_message(message.chat.id, "اختر وسيلة الشحن:", reply_markup=markup)

    # ======== حذف الحساب ========
    elif text == 'حذف':
        cursor.execute("UPDATE users SET has_account=0 WHERE user_id=?", (user_id,))
        conn.commit()
        bot.send_message(message.chat.id, "✅ تم حذف بيانات حسابك. يمكنك الآن إنشاء حساب جديد.", reply_markup=main_keyboard(user_id))

    # (بقية الأوامر مثل السحب، الرصيد، الدعم تبقى كما هي في كودك الأصلي)
    elif text == '💵 الرصيد 💵':
        cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
        res = cursor.fetchone()
        bot.send_message(message.chat.id, f"رصيدك الحالي: {res[0] if res else 0} NSP")

# ===========================
# دوال إنشاء الحساب والتعامل مع Callback
# ===========================
def enter_account_name(message):
    name = message.text.strip()
    full_name = f"Matar-{name}"
    msg = bot.send_message(message.chat.id, "ادخل كلمة المرور:")
    bot.register_next_step_handler(msg, enter_password, full_name)

def enter_password(message, full_name):
    user_id = message.from_user.id
    cursor.execute("INSERT OR REPLACE INTO users(user_id, account_name, password, balance, has_account) VALUES(?,?,?,?,?)",
                   (user_id, full_name, message.text, 0, 1))
    conn.commit()
    bot.send_message(message.chat.id, "✅ تم إنشاء الحساب بنجاح!", reply_markup=main_keyboard(user_id))

@bot.callback_query_handler(func=lambda call: True)
def callback_handling(call):
    if call.data == "confirm_del":
        bot.send_message(call.message.chat.id, "⚠️ سيتم حذف الحساب نهائياً! للتأكيد اكتب كلمة (حذف) في الشات.")
    elif call.data == "p_s":
        bot.send_message(call.message.chat.id, "📱 **سيرياتل كاش**\nحول للرقم: `09xxxxxx` ثم أرسل الإشعار.")
    elif call.data == "p_c":
        bot.send_message(call.message.chat.id, "💳 **شام كاش**\nحول للعنوان: `SHAM-XXXX` ثم أرسل الإشعار.")

# ===========================
# تشغيل البوت
# ===========================
if __name__ == "__main__":
    keep_alive()
    print("Matar Bot is Back!")
    bot.polling(none_stop=True)
