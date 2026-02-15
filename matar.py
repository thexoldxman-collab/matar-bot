import telebot
from telebot import types
from flask import Flask
from threading import Thread
import os
TOKEN = os.environ.get('TOKEN')


# 1. إعداد سيرفر صغير لإبقاء البوت مستيقظاً
app = Flask('')

@app.route('/')
def home():
    return "I am alive!"

def run():
    # Render بيعطي منفذ (Port) تلقائي، لازم نستخدمه
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

# 2. إعداد البوت (حط التوكن تبعك هون)
TOKEN = os.environ.get('TOKEN')
bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn1 = types.KeyboardButton('🆔 إنشاء حساب iChancy')
    btn2 = types.KeyboardButton('💰 شحن رصيد')
    btn3 = types.KeyboardButton('📥 سحب أرباح')
    btn4 = types.KeyboardButton('📊 حسابي الشخصي')
    btn5 = types.KeyboardButton('🛠️ خدمات أخرى')
    btn6 = types.KeyboardButton('📞 الدعم الفني')
    markup.add(btn1, btn2, btn3, btn4, btn5, btn6)
    
    welcome_text = (f"مرحباً بك {message.from_user.first_name} في بوت مطر الرسمي 🌧️\n\n"
                    "نحن هنا لتسهيل عملياتك المالية على منصة iChancy بكل سرعة وأمان.\n"
                    "الرجاء اختيار الخدمة المطلوبة من القائمة أدناه:")
    bot.send_message(message.chat.id, welcome_text, reply_markup=markup)

@bot.message_handler(func=lambda message: True)
def handle_msg(message):
    if message.text == '🆔 إنشاء حساب iChancy':
        bot.reply_to(message, "✅ لفتح حساب جديد، يرجى إرسال الاسم الثلاثي + رقم الهاتف.\nسيقوم الموظف المختص بتجهيز حسابك فوراً.")
    
    elif message.text == '💰 شحن رصيد':
        payment_markup = types.InlineKeyboardMarkup()
        p1 = types.InlineKeyboardButton("Syriatel Cash 📱", callback_data="pay_syriatel")
        p2 = types.InlineKeyboardButton("Cham Cash 💳", callback_data="pay_cham")
        payment_markup.add(p1, p2)
        bot.send_message(message.chat.id, "اختر وسيلة الشحن المناسبة لك:", reply_markup=payment_markup)
    
    elif message.text == '📥 سحب أرباح':
        bot.reply_to(message, "📥 لطلب سحب الأرباح، أرسل ID الحساب والمبلغ المراد سحبه، مع تحديد وسيلة الاستلام (سيرياتل كاش / شام كاش).")
    
    elif message.text == '📊 حسابي الشخصي':
        bot.reply_to(message, "👤 معلومات الحساب:\nالرصيد: 0.00$\nالديون: 0.00$\nالعمليات الناجحة: 0")
    
    elif message.text == '📞 الدعم الفني':
        bot.reply_to(message, "👨‍💻 الإدارة جاهزة للرد على استفساراتكم:\nتواصل هنا: @Your_Username")

@bot.callback_query_handler(func=lambda call: call.data.startswith('pay_'))
def callback_payment(call):
    if call.data == "pay_syriatel":
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "🚀 تم اختيار سيرياتل كاش.\nيرجى تحويل المبلغ للمحفظة: [رقمك هنا]\nثم أرسل صورة الإشعار.")
    elif call.data == "pay_cham":
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "🚀 تم اختيار شام كاش.\nيرجى تحويل المبلغ للمحفظة: [رقمك هنا]\nثم أرسل صورة الإشعار.")

# 3. تشغيل البوت مع ميزة الـ Keep Alive
if __name__ == "__main__":
    keep_alive()  # تشغيل السيرفر المساعد
    print("بوت مطر يعمل الآن مع ميزة عدم النوم...")
    bot.polling(none_stop=True)
