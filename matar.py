import telebot
from telebot import types
import os
import json

# الإعدادات الأساسية
TOKEN = os.getenv('TOKEN')
bot = telebot.TeleBot(TOKEN)
ADMIN_ID = 846938470  # آيديك الصحيح

# قاعدة بيانات بسيطة للحفظ
DB_FILE = "database.json"

def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f: return json.load(f)
    return {"users": {}, "settings": {"min_deposit": 100}}

def save_db(db):
    with open(DB_FILE, "w") as f: json.dump(db, f, indent=4)

# --- كيبورد الإمبراطور ---
def main_markup():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add('⚽ قسم ايشانسي', '💰 رصيدي')
    markup.add('➕ شحن الحساب', '➖ طلب سحب')
    markup.add('📊 الإحصائيات', '🛠 الدعم')
    return markup

def admin_markup():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add('➕ إضافة رصيد', '📢 إذاعة عامة')
    markup.add('📉 خصم رصيد', '🔙 العودة')
    return markup

# --- الأوامر ---
@bot.message_handler(commands=['start'])
def welcome(message):
    db = load_db()
    uid = str(message.from_user.id)
    if uid not in db["users"]:
        db["users"][uid] = {"name": message.from_user.first_name, "balance": 0}
        save_db(db)
    bot.send_message(message.chat.id, f"🎯 مرحباً بك في بوت الإمبراطور للخدمات\n\nأهلاً بك: {message.from_user.first_name}", reply_markup=main_markup())

@bot.message_handler(func=lambda m: True)
def handle_text(m):
    uid = str(m.from_user.id)
    db = load_db()

    if m.text == '💰 رصيدي':
        bal = db["users"].get(uid, {}).get("balance", 0)
        bot.reply_to(m, f"💳 رصيدك الحالي هو: {bal} ليرة")

    elif m.text == '/admin' and int(uid) == ADMIN_ID:
        bot.send_message(uid, "🔓 دخلت لوحة التحكم الإمبراطورية", reply_markup=admin_markup())

    elif m.text == '➕ إضافة رصيد' and int(uid) == ADMIN_ID:
        msg = bot.send_message(uid, "أرسل (الآيدي:المبلغ) لإضافته")
        bot.register_next_step_handler(msg, add_bal_func)

    elif m.text == '🔙 العودة':
        bot.send_message(uid, "القائمة الرئيسية", reply_markup=main_markup())

def add_bal_func(message):
    try:
        target, amount = message.text.split(':')
        db = load_db()
        if target in db["users"]:
            db["users"][target]["balance"] += int(amount)
            save_db(db)
            bot.send_message(message.chat.id, "✅ تم الشحن بنجاح")
            bot.send_message(target, f"💰 تم إضافة {amount} ليرة لرصيدك!")
    except: bot.send_message(message.chat.id, "❌ خطأ بالتنسيق")

bot.polling(none_stop=True)
