import re
import telebot
import json
import os
from telebot import TeleBot, types

# =======================
# إعدادات البوت والإدمن
# =======================
TOKEN = '8581064983:AAE43_TNTx8Fnww6-vs8MVlb97ahTzCvNhM'
bot = TeleBot(TOKEN)
ADMIN_ID = 846938470
CHANNEL_USERNAME = "Matar_ichancy"
DB_FILE = 'database.json'

# =======================
# وظائف قاعدة البيانات (JSON)
# =======================
def load_data():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_data():
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(USERS, f, ensure_ascii=False, indent=4)

# تحميل البيانات عند البدء
USERS = load_data()
USER_STATE = {}

# =======================
# لوحات المفاتيح (القوائم)
# =======================
def main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add('⚽ ايشانسي | Ichancy')
    markup.add('➕ شحن رصيد', '➖ سحب أرباح')
    markup.add('💰 رصيدي', '📢 القناة الرسمية')
    markup.add('🛠 الدعم الفني', '🎁 إهداء رصيد')
    markup.add('🎟 كود هدية', 'انضم كوكيل معتمد')
    return markup

def back_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add('🔙 العودة للقائمة الرئيسية')
    return markup

# =======================
# التحقق من المدخلات
# =======================
def is_valid_input(text):
    return bool(re.match(r'^[A-Za-z0-9]+$', text))

# =======================
# أوامر البداية
# =======================
@bot.message_handler(commands=['start'])
def start(message):
    user_id = str(message.from_user.id)
    USER_STATE[user_id] = None
    
    if user_id not in USERS:
        USERS[user_id] = {
            "account_name": None,
            "password": None,
            "bot_balance": 0,
            "game_balance": 0,
            "banned": False,
            "deleted": False
        }
        save_data()
        
    bot.send_message(
        message.chat.id,
        f"أهلاً بك {message.from_user.first_name} في بوت مطر 🎯\nوسيطك المعتمد لمنصة iChancy.\n\n🔗 تابعنا هنا: https://t.me/{CHANNEL_USERNAME}",
        reply_markup=main_keyboard()
    )

# =======================
# معالجة إنشاء الحساب (الخطوات)
# =======================
def process_username(message):
    user_id = str(message.from_user.id)
    if message.text == '🔙 العودة للقائمة الرئيسية':
        start(message)
        return

    if not is_valid_input(message.text):
        msg = bot.send_message(user_id, "❌ الاسم غير صالح! استخدم أحرف إنجليزية وأرقام فقط:")
        bot.register_next_step_handler(msg, process_username)
        return
        
    USERS[user_id]["account_name"] = message.text
    save_data()
    msg = bot.send_message(user_id, "🔒 ممتاز، الآن اختر كلمة مرور قوية (أحرف وأرقام فقط):")
    bot.register_next_step_handler(msg, process_password)

def process_password(message):
    user_id = str(message.from_user.id)
    if message.text == '🔙 العودة للقائمة الرئيسية':
        start(message)
        return

    if not is_valid_input(message.text):
        msg = bot.send_message(user_id, "❌ كلمة المرور غير صالحة! استخدم أحرف إنجليزية وأرقام فقط:")
        bot.register_next_step_handler(msg, process_password)
        return
        
    USERS[user_id]["password"] = message.text
    USERS[user_id]["deleted"] = False
    save_data()
    bot.send_message(user_id, "✅ تم إنشاء حسابك بنجاح! يمكنك الآن الشحن واللعب.", reply_markup=main_keyboard())

# =======================
# التعامل مع الرسائل والأزرار
# =======================
@bot.message_handler(func=lambda m: True)
def handle_msg(message):
    user_id = str(message.from_user.id)
    text = message.text

    if user_id not in USERS:
        start(message)
        return

    if USERS[user_id].get("banned", False):
        bot.send_message(user_id, "🚫 حسابك محظور من قِبل الإدارة.")
        return

    # --- زر ايشانسي ---
    if text == '⚽ ايشانسي | Ichancy':
        if not USERS[user_id]["account_name"] or USERS[user_id]["deleted"]:
            msg = bot.send_message(user_id, "📌 لنبدأ بإنشاء حسابك.\nاختر اسم المستخدم (أحرف إنجليزية وأرقام):", reply_markup=back_keyboard())
            bot.register_next_step_handler(msg, process_username)
        else:
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
            markup.add('💳 التعبئة في حسابي', '💸 السحب من حسابي')
            markup.add('🗑 حذف الحساب', '🔙 العودة للقائمة الرئيسية')
            bot.send_message(user_id,
                             f"👤 حسابك النشط: {USERS[user_id]['account_name']}\n"
                             f"💰 رصيدك المتاح: {USERS[user_id]['game_balance']}$\n"
                             f"🆔 معرف البوت: {user_id}",
                             reply_markup=markup)

    # --- الرجوع ---
    elif text == '🔙 العودة للقائمة الرئيسية':
        start(message)

    # --- رصيدي ---
    elif text == '💰 رصيدي':
        bal = USERS[user_id].get("bot_balance", 0)
        bot.send_message(user_id, f"💳 رصيدك الحالي في البوت: {bal}$")

    # --- الدعم الفني ---
    elif text == '🛠 الدعم الفني':
        bot.send_message(user_id, f"👨‍💻 للتواصل مع الدعم الفني والوكلاء:\n@{CHANNEL_USERNAME}")

    # --- حذف الحساب ---
    elif text == '🗑 حذف الحساب':
        USER_STATE[user_id] = "confirm_delete"
        bot.send_message(user_id, "⚠️ هل أنت متأكد؟ سيتم تعطيل حسابك. أرسل كلمة (حذف) للتأكيد:")

    elif USER_STATE.get(user_id) == "confirm_delete":
        if text == "حذف":
            USERS[user_id]["deleted"] = True
            USERS[user_id]["account_name"] = None
            save_data()
            bot.send_message(user_id, "✅ تم حذف بيانات الحساب. يمكنك إنشاء واحد جديد في أي وقت.", reply_markup=main_keyboard())
        else:
            bot.send_message(user_id, "❌ تم إلغاء عملية الحذف.", reply_markup=main_keyboard())
        USER_STATE[user_id] = None

    # --- أزرار تحت التطوير ---
    elif text in ['➕ شحن رصيد', '➖ سحب أرباح', '🎁 إهداء رصيد', '🎟 كود هدية']:
        bot.send_message(user_id, "🚧 هذه الميزة قيد التجهيز من قبل الإدارة، سيتم تفعيلها قريباً.")

# =======================
# تشغيل البوت
# =======================
if __name__ == '__main__':
    print("--- بوت مطر يعمل الآن بكفاءة ---")
    bot.infinity_polling()
