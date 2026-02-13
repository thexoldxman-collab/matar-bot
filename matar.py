import telebot
from telebot import types
import os

# جلب التوكن من إعدادات السيرفر
TOKEN = os.getenv('TOKEN')
bot = telebot.TeleBot(TOKEN)

# --- قائمة الأوامر (لإظهار زر Start للمستخدم) ---
bot.set_my_commands([
    telebot.types.BotCommand("start", "تشغيل البوت / القائمة الرئيسية")
])

# --- لوحة الأزرار الرئيسية ---
def main_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn1 = types.KeyboardButton('⚽ ايشانسي | Ichancy')
    btn2 = types.KeyboardButton('➕ التعبئة في حسابي')
    btn3 = types.KeyboardButton('➖ السحب من البوت')
    btn4 = types.KeyboardButton('💰 معلومات الحساب')
    btn5 = types.KeyboardButton('📢 قناة البوت')
    markup.add(btn1, btn2, btn3, btn4, btn5)
    return markup

# --- رد البوت عند الضغط على /start ---
@bot.message_handler(commands=['start'])
def start(message):
    welcome_text = (f"🎯 أهلاً بك يا {message.from_user.first_name} في بوت مطر\n\n"
                    "هذا البوت مصمم لخدمات الشحن والسحب التلقائي.\n"
                    "استخدم الأزرار بالأسفل للبدء.")
    bot.send_message(message.chat.id, welcome_text, reply_markup=main_keyboard())

# --- معالجة الضغط على الأزرار ---
@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    if message.text == '⚽ ايشانسي | Ichancy':
        bot.reply_to(message, "✅ الحد الأدنى للتعبئة والسحب هو 100 ليرة.")
        
    elif message.text == '💰 معلومات الحساب':
        user_id = message.from_user.id
        user_name = message.from_user.first_name
        info = (f"👤 *معلومات حسابك*:\n\n"
                f"📝 الاسم: {user_name}\n"
                f"🆔 الآيدي: `{user_id}`\n"
                f"💰 الرصيد: 0 ليرة")
        bot.send_message(message.chat.id, info, parse_mode="Markdown")

    elif message.text == '➕ التعبئة في حسابي':
        bot.reply_to(message, "🚀 قسم الشحن:\nيرجى إرسال صورة التحويل للإدارة ليتم إضافة الرصيد.")

    elif message.text == '➖ السحب من البوت':
        bot.reply_to(message, "💸 قسم السحب:\nأدخل المبلغ الذي تود سحبه (يجب توفر رصيد كافٍ).")
        
    elif message.text == '📢 قناة البوت':
        bot.reply_to(message, "تابع آخر التحديثات على قناتنا الرسمية.")

# تشغيل البوت
bot.polling(none_stop=True)
