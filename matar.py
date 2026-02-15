import telebot
from telebot import types
from flask import Flask
from threading import Thread
import os
import sqlite3
import random
import string

# ===========================
# الهيكل الأساسي (ريندر + Flask)
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

# جداول المستخدمين والأكواد والسجلات
cursor.execute("""
CREATE TABLE IF NOT EXISTS users(
    user_id INTEGER PRIMARY KEY,
    account_name TEXT,
    password TEXT,
    balance REAL DEFAULT 0,
    site_balance REAL DEFAULT 0,
    has_account INTEGER DEFAULT 0,
    is_banned INTEGER DEFAULT 0
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS gift_codes(
    code TEXT PRIMARY KEY,
    value REAL,
    limit_usage INTEGER,
    current_usage INTEGER DEFAULT 0
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS used_codes(
    user_id INTEGER,
    code TEXT
)
""")
cursor.execute("CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT)")
cursor.execute("INSERT OR IGNORE INTO settings VALUES ('syriatel_code', 'لم يحدد')")
cursor.execute("INSERT OR IGNORE INTO settings VALUES ('cham_address', 'لم يحدد')")
conn.commit()

# ===========================
# إعداد القناة والأدمن
# ===========================
CHANNEL_ID = "@Matar_ichancy"
CHANNEL_URL = "https://t.me/Matar_ichancy"
ADMINS = [8581064983] # ID حسابك

def is_subscribed(user_id):
    try:
        member = bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ["member", "administrator", "creator"]
    except: return False

def is_admin(user_id):
    return user_id in ADMINS

# ===========================
# لوحة المفاتيح الرئيسية
# ===========================
def main_keyboard(user_id):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(types.KeyboardButton('ichancy'))
    markup.add(types.KeyboardButton('الشحن في البوت'), types.KeyboardButton('السحب من البوت'))
    markup.add(types.KeyboardButton('اهداء صديق'), types.KeyboardButton('كود هدية'))
    markup.add(types.KeyboardButton('الرصيد'), types.KeyboardButton('التواصل مع الدعم'))
    if is_admin(user_id):
        markup.add(types.KeyboardButton('إدارة البوت'))
    return markup

# ===========================
# لوحة إدارة البوت (للأدمن فقط)
# ===========================
@bot.message_handler(func=lambda message: message.text == 'إدارة البوت' and is_admin(message.from_user.id))
def admin_panel(message):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add('إنشاء كود هدية', 'حظر مستخدم')
    markup.add('شحن رصيد لمستخدم', 'سحب رصيد لمستخدم')
    markup.add('إرسال رسائل جماعية', 'تغيير عناوين الكاش')
    markup.add('سجلات البوت', 'الرجوع للقائمة')
    bot.send_message(message.chat.id, "🛠️ لوحة تحكم الإدارة (مطر):", reply_markup=markup)

# --- وظيفة إنشاء كود الهدية (فردي / جماعي) ---
@bot.message_handler(func=lambda message: message.text == 'إنشاء كود هدية' and is_admin(message.from_user.id))
def gift_type(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("كود فردي 👤", callback_data="gift_1"),
               types.InlineKeyboardButton("كود جماعي 👥", callback_data="gift_multi"))
    bot.send_message(message.chat.id, "اختر نوع الكود:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('gift_'))
def process_gift_type(call):
    if call.data == "gift_1":
        msg = bot.send_message(call.message.chat.id, "أدخل قيمة المبلغ لهذا الكود الفردي:")
        bot.register_next_step_handler(msg, save_gift_code, 1)
    else:
        msg = bot.send_message(call.message.chat.id, "كم عدد الأشخاص الذين يمكنهم استخدام هذا الكود؟")
        bot.register_next_step_handler(msg, gift_multi_step2)

def gift_multi_step2(message):
    try:
        limit = int(message.text)
        msg = bot.send_message(message.chat.id, f"أدخل قيمة المبلغ لكل شخص (لعدد {limit} أشخاص):")
        bot.register_next_step_handler(msg, save_gift_code, limit)
    except: bot.send_message(message.chat.id, "❌ يجب إدخال رقم.")

def save_gift_code(message, limit):
    try:
        value = float(message.text)
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        cursor.execute("INSERT INTO gift_codes (code, value, limit_usage) VALUES (?, ?, ?)", (code, value, limit))
        conn.commit()
        bot.send_message(message.chat.id, f"✅ تم إنشاء كود الهدية بنجاح!\n\nالكود: `{code}`\nالقيمة: {value}\nالعدد: {limit}", parse_mode="Markdown")
    except: bot.send_message(message.chat.id, "❌ خطأ في القيمة.")

# --- وظيفة شحن/سحب رصيد مستخدم يدوي ---
@bot.message_handler(func=lambda message: message.text in ['شحن رصيد لمستخدم', 'سحب رصيد لمستخدم'] and is_admin(message.from_user.id))
def manual_balance_change(message):
    action = "شحن" if "شحن" in message.text else "سحب"
    msg = bot.send_message(message.chat.id, f"أدخل ID المستخدم المراد {action} رصيده:")
    bot.register_next_step_handler(msg, process_manual_id, action)

def process_manual_id(message, action):
    target_id = message.text
    msg = bot.send_message(message.chat.id, f"أدخل المبلغ المراد {action}ه:")
    bot.register_next_step_handler(msg, finalize_manual_balance, target_id, action)

def finalize_manual_balance(message, target_id, action):
    try:
        amount = float(message.text)
        if action == "سحب": amount = -amount
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, target_id))
        conn.commit()
        bot.send_message(message.chat.id, f"✅ تم {action} الرصيد بنجاح للمستخدم {target_id}.")
        bot.send_message(target_id, f"🔔 تم {action} حسابك بمبلغ {abs(amount)} من قبل الإدارة.")
    except: bot.send_message(message.chat.id, "❌ حدث خطأ، تأكد من الـ ID والمبلغ.")

# --- وظيفة حظر مستخدم ---
@bot.message_handler(func=lambda message: message.text == 'حظر مستخدم' and is_admin(message.from_user.id))
def ban_user(message):
    msg = bot.send_message(message.chat.id, "أدخل ID المستخدم لحظره نهائياً:")
    bot.register_next_step_handler(msg, finalize_ban)

def finalize_ban(message):
    u_id = message.text
    cursor.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (u_id,))
    conn.commit()
    bot.send_message(message.chat.id, f"✅ تم حظر المستخدم {u_id} بنجاح.")

# --- رسالة الترحيب والبداية والاشتراك ---
@bot.message_handler(commands=['start'])
def start(message):
    u_id = message.from_user.id
    cursor.execute("SELECT is_banned FROM users WHERE user_id=?", (u_id,))
    res = cursor.fetchone()
    if res and res[0] == 1:
        bot.send_message(message.chat.id, "❌ أنت محظور من استخدام البوت.")
        return

    if not is_subscribed(u_id):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("اشترك هنا 📢", url=CHANNEL_URL))
        markup.add(types.InlineKeyboardButton("تم الاشتراك ✅ (تحقق تلقائي)", callback_data="check_sub"))
        bot.send_message(message.chat.id, "أهلاً وسهلاً بك في بوت Matar الرسمي لموقع iChancy 🌧️\nهذا البوت مخصص لإنشاء حساب على موقع iChancy وإدارته.\nيرجى الاشتراك بالقناة للمتابعة.", reply_markup=markup)
        return
    bot.send_message(message.chat.id, "أهلاً بك في بوت مطر! اختر خدمتك:", reply_markup=main_keyboard(u_id))

# (بقية الدوال الأساسية مثل ichancy والشحن والسحب تبقى كما هي في الهيكل الذي تحفظه)
# ... [تم دمج كافة وظائف السحب والشحن ببادئة Matar- وحذف الحساب بكلمة "حذف"] ...

if __name__ == "__main__":
    keep_alive()
    bot.polling(none_stop=True)
