import telebot
from telebot import types

TOKEN = '8581064983:AAE43_TNTx8Fnww6-vs8MVlb97ahTzCvNhM'
bot = telebot.TeleBot(TOKEN)

def main_markup():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(types.KeyboardButton('⚽ ايشانسي | Ichancy ⚽'))
    markup.add(types.KeyboardButton('🔽 الشحن في البوت'), types.KeyboardButton('🔼 السحب من البوت'))
    markup.add(types.KeyboardButton('🤝 كن وكيلاً معنا'), types.KeyboardButton('💵 الرصيد'))
    markup.add(types.KeyboardButton('💬 التواصل مع الدعم'), types.KeyboardButton('📜 الشروط والاحكام'))
    return markup

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "أهلاً بك في بوت مطر 🎯", reply_markup=main_markup())

@bot.message_handler(func=lambda message: True)
def handle_msg(message):
    if message.text == '⚽ ايشانسي | Ichancy ⚽':
        markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
        markup.add(types.KeyboardButton('➕ التعبئة في حسابي'), types.KeyboardButton('➖ السحب من حسابي'))
        markup.add(types.KeyboardButton('💰 معلومات الحساب'), types.KeyboardButton('🔙 عودة'))
        bot.send_message(message.chat.id, "الحد الادنى للتعبئة والسحب 100 ليرة.", reply_markup=markup)
    elif message.text == '🔙 عودة':
        bot.send_message(message.chat.id, "تم العودة للقائمة الرئيسية 🏠", reply_markup=main_markup())

print("البوت شغال الآن...")
bot.polling()
