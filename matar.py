import telebot
from telebot import types
import os

# جلب التوكن من إعدادات السيرفر
TOKEN = os.getenv('TOKEN')
bot = telebot.TeleBot(TOKEN)

# --- إعدادات الإدمن (الآيدي الصحيح الخاص بك) ---
ADMIN_ID = 846938470 

# --- لوحة المفاتيح الرئيسية ---
def main_kb():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn1 = types.KeyboardButton('⚽ ايشانسي | Ichancy')
    btn2 = types.KeyboardButton('💰 حسابي')
    btn3 = types.KeyboardButton('➕ شحن رصيد')
    btn4 = types.KeyboardButton('➖ سحب أرباح')
    btn5 = types.KeyboardButton('📢 القناة الرسمية')
    btn6 = types.KeyboardButton('🛠 الدعم الفني')
    markup.add(btn1, btn2, btn3, btn4, btn5, btn6)
    return markup

# --- لوحة التحكم (تظهر لك أنت فقط) ---
def admin_kb():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add('📊 إحصائيات البوت', '➕ إضافة رصيد')
    markup.add('📢 إرسال إعلان للكل', '🔙 العودة للقائمة')
    return markup

# --- أمر التشغيل /start ---
@bot.message_handler(commands=['start'])
def start(message):
    welcome_text = (f"🎯 أهلاً بك يا {message.from_user.first_name} في نسخة الإمبراطور.\n\n"
                    "البوت الأسرع لخدمات الشحن والسحب.")
    bot.send_message(message.chat.id, welcome_text, reply_markup=main_kb())

# --- معالجة الأوامر والأزرار ---
@bot.message_handler(func=lambda message: True)
def handle_all(message):
    uid = message.from_user.id
    
    if message.text == '💰 حسابي':
        info = (f"👤 الاسم: {message.from_user.first_name}\n"
                f"🆔 الآيدي: `{uid}`\n"
                f"💰 رصيدك: 0.00 ليرة")
        bot.reply_to(message, info, parse_mode="Markdown")
    
    elif message.text == '⚽ ايشانسي | Ichancy':
        bot.reply_to(message, "✅ الحد الأدنى للتعبئة والسحب هو 100 ليرة.\nأرسل صورة التحويل للإدارة.")

    elif message.text == '🛠 الدعم الفني':
        bot.reply_to(message, "للتواصل مع المطور.")

    # --- الدخول للوحة الإدمن عبر أمر سري ---
    elif message.text == '/admin' and uid == ADMIN_ID:
        bot.send_message(uid, "🔓 أهلاً بك يا زعيم في لوحة التحكم السرية.", reply_markup=admin_kb())

    elif message.text == '🔙 العودة للقائمة':
        bot.send_message(uid, "تمت العودة للقائمة الرئيسية.", reply_markup=main_kb())

# تشغيل البوت
bot.polling(none_stop=True)
