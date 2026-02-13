import telebot
from telebot import types

# --- البيانات الأساسية (جاهزة بالتوكن الخاص بك) ---
TOKEN = '8581064983:AAE43_TNTx8Fnww6-vs8MVlb97ahTzCvNhM'
bot = telebot.TeleBot(TOKEN)
ADMIN_ID = 846938470  # هاد الـ ID تبعك لفتح لوحة التحكم
CHANNEL_ID = "@Matar_ichancy" 
CHANNEL_LINK = "https://t.me/Matar_ichancy"

# جداول البيانات (لحفظ العمليات مؤقتاً)
user_data = {} 
referrals = {} # نظام الوكلاء السري

# --- دالة التحقق من الاشتراك الإجباري ---
def is_subscribed(user_id):
    try:
        status = bot.get_chat_member(CHANNEL_ID, user_id).status
        return status in ['member', 'administrator', 'creator']
    except: return False

# --- لوحة تحكم الزبون (القائمة الرئيسية) ---
def main_kb():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(types.KeyboardButton('⚽ ايشانسي | Ichancy ⚽'))
    markup.add(types.KeyboardButton('🔽 الشحن في البوت 🔽'), types.KeyboardButton('🔼 السحب من البوت 🔼'))
    markup.add(types.KeyboardButton('💵 الرصيد 💵'), types.KeyboardButton('💰 انضم كشريك (فرصة عمل) 💰'))
    markup.add(types.KeyboardButton('💬 التواصل مع الدعم 💬'), types.KeyboardButton('📄 الشروط والأحكام 📄'))
    return markup

# --- رسالة البداية ونظام الوكيل السري ---
@bot.message_handler(commands=['start'])
def start(message):
    uid = message.from_user.id
    # منطق الوكلاء: إذا دخل شخص برابط إحالة
    text_split = message.text.split()
    if len(text_split) > 1:
        ref_id = text_split[1]
        if ref_id.isdigit() and int(ref_id) != uid:
            referrals[uid] = int(ref_id) # تسجيله تحت الوكيل بالخفاء

    if is_subscribed(uid):
        msg = (f"🎯 أهلاً بك في بوت Matar المطور\n\n"
               f"عزيزي {message.from_user.first_name}، يمكنك الآن البدء باستخدام كافة الخدمات.\n"
               "موقعنا الرسمي: [ichancy.com](https://ichancy.com)")
        bot.send_message(message.chat.id, msg, reply_markup=main_kb(), parse_mode="Markdown")
    else:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔗 اشترك في القناة أولاً", url=CHANNEL_LINK))
        bot.send_message(message.chat.id, "⚠️ عذراً، يجب الاشتراك في القناة لاستخدام البوت.", reply_markup=markup)

# --- نظام السحب والعمولة 10% وإشعار الإدمن ---
@bot.message_handler(func=lambda message: message.text == '🔼 السحب من البوت 🔼')
def withdraw_start(message):
    msg = bot.send_message(message.chat.id, "💰 أدخل المبلغ المراد سحبه بالليرة السورية:")
    bot.register_next_step_handler(msg, process_amount)

def process_amount(message):
    try:
        amount = int(message.text)
        if amount < 10000:
            bot.reply_to(message, "❌ الحد الأدنى للسحب هو 10,000 ليرة.")
            return
        user_data[message.chat.id] = {'amount': amount}
        msg = bot.send_message(message.chat.id, "📱 أدخل رقم حسابك أو محفظتك (سيريتل كاش / شام كاش):")
        bot.register_next_step_handler(msg, process_account)
    except:
        bot.reply_to(message, "⚠️ يرجى إدخال أرقام فقط.")

def process_account(message):
    uid = message.chat.id
    account = message.text
    amount = user_data[uid]['amount']
    fee = amount * 0.10
    net = amount - fee
    user_data[uid]['account'] = account

    confirm_text = (
        "📊 تأكيد طلب السحب\n"
        "━━━━━━━━━━━━━━\n"
        f"💰 المبلغ المطلوب: {amount:,} ل.س\n"
        f"🏷 رسوم التحويل (10%): {fee:,} ل.س\n"
        "━━━━━━━━━━━━━━\n"
        f"✅ صافي المبلغ الذي سيصلك: {net:,} ل.س\n"
        f"📱 الحساب: {account}\n"
        "━━━━━━━━━━━━━━\n"
        "هل تريد تأكيد الطلب؟"
    )
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ تأكيد الإرسال", callback_data="confirm_w"), 
               types.InlineKeyboardButton("❌ إلغاء", callback_data="cancel"))
    bot.send_message(uid, confirm_text, reply_markup=markup)

# --- معالجة الضغطات (تأكيد السحب + إشعار الإدمن) ---
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    uid = call.message.chat.id
    if call.data == "confirm_w":
        data = user_data.get(uid)
        if data:
            admin_msg = (f"🚨 **طلب سحب جديد**\n"
                         f"👤 المستخدم: {call.from_user.first_name}\n"
                         f"🆔 الأيدي: `{uid}`\n"
                         f"💰 الصافي للتحويل: {data['amount'] - (data['amount']*0.1):,} ل.س\n"
                         f"📱 الحساب: `{data['account']}`")
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("✅ تم التحويل للزبون", callback_data=f"done_{uid}"))
            bot.send_message(ADMIN_ID, admin_msg, reply_markup=markup, parse_mode="Markdown")
            
            bot.edit_message_text("✅ تم إرسال طلبك للإدارة، سيتم التنفيذ خلال 12 ساعة.", uid, call.message.message_id)
    
    elif call.data.startswith("done_"):
        target_user = call.data.split("_")[1]
        bot.send_message(target_user, "✅ تم تحويل المبلغ إلى حسابك بنجاح. شكراً لثقتك!")
        bot.edit_message_text("✅ تمت العملية وأرسلنا إشعار للزبون.", ADMIN_ID, call.message.message_id)

    elif call.data == "cancel":
        bot.edit_message_text("❌ تم إلغاء العملية.", uid, call.message.message_id)

# --- نظام الوكلاء (انضم كشريك) ---
@bot.message_handler(func=lambda message: message.text == '💰 انضم كشريك (فرصة عمل) 💰')
def invite_friends(message):
    ref_link = f"https://t.me/{bot.get_me().username}?start={message.from_user.id}"
    msg = (f"🤝 **انضم إلينا كشريك (وكيل معتمد)**\n\n"
           f"احصل على دخل إضافي كل 10 أيام من خلال رابط إحالتك.\n"
           f"كل شخص يشترك ويشحن عن طريقك، لك عمولة 10%.\n\n"
           f"🔗 رابطك الخاص: `{ref_link}`")
    bot.send_message(message.chat.id, msg, parse_mode="Markdown")

bot.polling()
