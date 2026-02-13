import telebot
from telebot import types
import os

TOKEN = os.getenv('TOKEN')
bot = telebot.TeleBot(TOKEN)
ADMIN_ID = 846938470 
CHANNEL_ID = "@Matar_ichancy" 
CHANNEL_LINK = "https://t.me/Matar_ichancy"

# متغيرات وهمية لتجربة الكود (سيتم ربطها بقاعدة بيانات لاحقاً)
user_data = {} 

def is_subscribed(user_id):
    try:
        status = bot.get_chat_member(CHANNEL_ID, user_id).status
        return status in ['member', 'administrator', 'creator']
    except: return False

def main_kb():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(types.KeyboardButton('⚽ ايشانسي | Ichancy ⚽'))
    markup.add(types.KeyboardButton('🔽 الشحن في البوت 🔽'), types.KeyboardButton('🔼 السحب من البوت 🔼'))
    markup.add(types.KeyboardButton('💵 الرصيد 💵'), types.KeyboardButton('💰 دعوة الأصدقاء 💰'))
    markup.add(types.KeyboardButton('💬 التواصل مع الدعم 💬'), types.KeyboardButton('📄 الشروط والأحكام 📄'))
    return markup

@bot.message_handler(commands=['start'])
def start(message):
    uid = message.from_user.id
    if is_subscribed(uid):
        msg = (f"🎯 أهلاً بك في بوت **Matar** المطور\n\n"
               f"عزيزي {message.from_user.first_name}، يمكنك الآن البدء باستخدام كافة الخدمات.\n"
               "موقعنا الرسمي: [ichancy.com](https://ichancy.com)")
        bot.send_message(message.chat.id, msg, reply_markup=main_kb(), parse_mode="Markdown")
    else:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔗 اشترك في القناة أولاً", url=CHANNEL_LINK))
        markup.add(types.InlineKeyboardButton("✅ تم الاشتراك", callback_data="check_sub"))
        bot.send_message(message.chat.id, "⚠️ **عذراً، يجب الاشتراك في القناة لاستخدام البوت.**", reply_markup=markup, parse_mode="Markdown")

# --- منطق السحب والعمولة 10% (بناءً على الصورة الأخيرة) ---
@bot.message_handler(func=lambda message: message.text == '🔼 السحب من البوت 🔼')
def withdraw_start(message):
    msg = bot.send_message(message.chat.id, "💰 **أدخل المبلغ المراد سحبه بالليرة السورية:**")
    bot.register_next_step_handler(msg, process_amount)

def process_amount(message):
    try:
        amount = int(message.text)
        if amount < 10000:
            bot.reply_to(message, "❌ الحد الأدنى للسحب هو 10,000 ليرة.")
            return
        user_data[message.chat.id] = {'amount': amount}
        msg = bot.send_message(message.chat.id, "📱 **أدخل رقم حسابك أو محفظتك (سيريتل كاش / شام كاش):**")
        bot.register_next_step_handler(msg, process_account)
    except:
        bot.reply_to(message, "⚠️ يرجى إدخال مبلغ صحيح (أرقام فقط).")

def process_account(message):
    chat_id = message.chat.id
    account = message.text
    amount = user_data[chat_id]['amount']
    fee = amount * 0.10
    net = amount - fee

    confirm_text = (
        "📊 **تأكيد طلب السحب**\n"
        "━━━━━━━━━━━━━━\n"
        f"💰 المبلغ المطلوب: {amount:,} ل.س\n"
        f"🏷 رسوم التحويل (10%): {fee:,} ل.س\n"
        "━━━━━━━━━━━━━━\n"
        f"✅ **صافي المبلغ الذي سيصلك: {net:,} ل.س**\n"
        f"📱 الحساب: `{account}`\n"
        "━━━━━━━━━━━━━━\n"
        "هل تريد تأكيد الطلب؟"
    )
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ تأكيد", callback_data="confirm_w"), 
               types.InlineKeyboardButton("❌ إلغاء", callback_data="cancel"))
    bot.send_message(chat_id, confirm_text, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    if call.data == "check_sub":
        if is_subscribed(call.from_user.id):
            bot.answer_callback_query(call.id, "✅ تم التفعيل!")
            start(call.message)
        else:
            bot.answer_callback_query(call.id, "❌ لم تشترك بعد!", show_alert=True)
    elif call.data == "confirm_w":
        bot.edit_message_text("✅ تم إرسال طلبك للإدارة، سيتم التنفيذ خلال 12 ساعة.", call.message.chat.id, call.message.message_id)
    elif call.data == "cancel":
        bot.edit_message_text("❌ تم إلغاء العملية.", call.message.chat.id, call.message.message_id)

bot.polling(none_stop=True)
