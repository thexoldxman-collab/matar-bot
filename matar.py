import os
from telebot import TeleBot, types

# =======================
# إعدادات البوت والإدمن
# =======================
TOKEN = '8581064983:AAE43_TNTx8Fnww6-vs8MVlb97ahTzCvNhM'  # توكن البوت
bot = TeleBot(TOKEN)
ADMIN_ID = 846938470  # استبدل بـ ID حسابك

# =======================
# إعدادات النظام
# =======================
SYRIATEL_CASH_NUM = "09xxxxxxxx"
TRADER_CODE = "12345"
SHAM_CASH_ADDRESS = "SHAM123456"
USDT_BINANCE_ADDR = "Txxxxxxxxxxxxxxx"
WITHDRAW_COMMISSION = 0.10  # عمولة السحب 10%
REFERRAL_PERCENT = 0.10     # عمولة الوكلاء 10%
MAINTENANCE_MODE = False

# =======================
# قواعد بيانات مؤقتة
# =======================
USERS = {}        # بيانات كل مستخدم {user_id: {...}}
REFERRALS = {}    # بيانات الوكلاء {referrer_id: [user_id, ...]}
PENDING_WITHDRAWALS = {}  # طلبات السحب المعلقة {user_id: {...}}

# =======================
# لوحة المفاتيح
# =======================
def main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add('⚽ ايشانسي | Ichancy', '💰 حسابي')
    markup.add('➕ شحن رصيد', '➖ سحب أرباح')
    markup.add('📢 القناة الرسمية', '🛠 الدعم الفني')
    markup.add('انضم كوكيل معتمد')
    return markup

def admin_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add('📊 إحصائيات البوت', '➕ تعديل بيانات الشحن')
    markup.add('💵 تعديل العمولة', '📢 إذاعة للكل')
    markup.add('🔧 وضع صيانة', '📋 تقرير الوكلاء')
    markup.add('🔙 العودة للقائمة')
    return markup

# =======================
# أوامر البداية
# =======================
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    USERS.setdefault(user_id, {"balance":0, "referrer":None, "pending_commission":0})
    bot.send_message(message.chat.id, "أهلاً بك في بوت مطر 🎯", reply_markup=main_keyboard())

# =======================
# التعامل مع الرسائل
# =======================
@bot.message_handler(func=lambda m: True)
def handle_msg(message):
    user_id = message.from_user.id
    text = message.text

    # ------------- قائمة الزبون -------------
    if text == '💰 حسابي':
        balance = USERS[user_id]["balance"]
        bot.send_message(user_id, f"💰 رصيدك الحالي: {balance} ليرة")

    elif text == '⚽ ايشانسي | Ichancy':
        bot.send_message(user_id, "قسم المراهنات والخدمات الرياضية.\nأرسل لقطة شاشة للعملية ليتم التنفيذ.")

    elif text == '🛠 الدعم الفني':
        bot.send_message(user_id, "للتواصل مع الإدارة: @YourUsername")  # عدل يوزرك

    elif text == '➕ شحن رصيد':
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        markup.add('سيريتل كاش', 'شام كاش', 'USDT / Binance', '🔙 العودة')
        bot.send_message(user_id, "اختر طريقة الشحن:", reply_markup=markup)

    elif text == '➖ سحب أرباح':
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        markup.add('سيريتل كاش', 'شام كاش', 'USDT / Binance', '🔙 العودة')
        bot.send_message(user_id, "اختر طريقة السحب:", reply_markup=markup)

    elif text == 'انضم كوكيل معتمد':
        bot.send_message(user_id, "احصل على دخل إضافي كل 10 أيام من خلال رابط إحالتك الخاص! 🤝")
        # الرابط الافتراضي أو توليده حسب GitHub/Render لاحقاً

    # ------------- قائمة الإدارة -------------
    elif text == '/admin' and user_id == ADMIN_ID:
        bot.send_message(user_id, "🔓 أهلاً بك يا زعيم", reply_markup=admin_keyboard())

    elif text == '🔙 العودة':
        bot.send_message(user_id, "تمت العودة للقائمة الرئيسية 🏠", reply_markup=main_keyboard())

    # أي رسائل أخرى يمكن إضافة المعالجة لاحقاً

# =======================
# بدء تشغيل البوت
# =======================
if __name__ == "__main__":
    print("البوت شغال الآن...")
    bot.polling(none_stop=True)
