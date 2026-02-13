import re
from telebot import TeleBot, types

# =======================
# إعدادات البوت والإدمن
# =======================
TOKEN = '8581064983:AAE43_TNTx8Fnww6-vs8MVlb97ahTzCvNhM'
bot = TeleBot(TOKEN)
ADMIN_ID = 846938470
CHANNEL_USERNAME = "Matar_ichancy"

# =======================
# قواعد بيانات مؤقتة
# =======================
USERS = {}        # بيانات كل مستخدم
USER_STATE = {}   # حالة المستخدم أثناء العمليات
USER_TEMP = {}    # بيانات مؤقتة مثل إهداء الرصيد
GIFTS = {}        # أكواد الهدايا {كود: قيمة}

# =======================
# لوحة المفاتيح
# =======================
def main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add('⚽ ايشانسي | Ichancy')  # أول زر بمفرده
    markup.add('➕ شحن رصيد', '➖ سحب أرباح')
    markup.add('💰 رصيدي', '📢 القناة الرسمية')
    markup.add('🛠 الدعم الفني', 'انضم كوكيل معتمد')
    markup.add('🎁 إهداء رصيد', '🎟 كود هدية')
    return markup

def admin_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add('📊 إحصائيات البوت', '📋 تقرير الحسابات')
    markup.add('💵 تعديل الرصيد/كلمة السر/الحظر', '🔧 وضع صيانة')
    markup.add('📢 إذاعة للكل', '🗃 إدارة أكواد الهدايا')
    markup.add('🔙 العودة للقائمة')
    return markup

# =======================
# التحقق من اسم الحساب وكلمة السر
# =======================
def is_valid_username(name):
    return bool(re.match(r'^[A-Za-z0-9]+$', name))

def is_valid_password(password):
    return bool(re.match(r'^[A-Za-z0-9]+$', password))

# =======================
# أوامر البداية
# =======================
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    USER_STATE[user_id] = None
    USER_TEMP[user_id] = {}
    USERS.setdefault(user_id, {
        "account_name": None,
        "password": None,
        "bot_balance": 0,
        "game_balance": 0,
        "referrer": None,
        "pending_commission": 0,
        "banned": False,
        "game_id": None,
        "deleted": False
    })
    bot.send_message(
        message.chat.id,
        f"أهلاً بك في بوت مطر 🎯\n🔗 يرجى الاشتراك في القناة: https://t.me/{CHANNEL_USERNAME}",
        reply_markup=main_keyboard()
    )

# =======================
# التعامل مع الرسائل
# =======================
@bot.message_handler(func=lambda m: True)
def handle_msg(message):
    user_id = message.from_user.id
    text = message.text

    # ---------- تحقق من الحظر ----------
    if USERS.get(user_id, {}).get("banned", False):
        bot.send_message(user_id, "🚫 تم حظر حسابك، لا يمكنك استخدام البوت.")
        return

    # ---------- زر Ichancy ----------
    if text == '⚽ ايشانسي | Ichancy':
        if not USERS[user_id]["account_name"] or USERS[user_id]["deleted"]:
            USER_STATE[user_id] = "creating_account_username"
            msg = bot.send_message(user_id, "📌 اختر اسم الحساب داخل اللعبة (بالأحرف الإنجليزية والأرقام فقط):")
            bot.register_next_step_handler(msg, process_username)
        else:
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
            markup.add('💳 التعبئة في حسابي', '💸 السحب من حسابي', '🗑 حذف الحساب', '🔙 العودة')
            bot.send_message(user_id,
                             f"👤 حسابك داخل اللعبة: {USERS[user_id]['account_name']}\n"
                             f"💰 رصيد اللعبة: {USERS[user_id]['game_balance']}\n"
                             f"🆔 ID الحساب: {USERS[user_id]['game_id']}",
                             reply_markup=markup)

    # ---------- إنشاء الحساب ----------
    elif USER_STATE.get(user_id) == "creating_account_username":
        process_username(message)
    elif USER_STATE.get(user_id) == "creating_account_password":
        process_password(message)

    # ---------- إدارة الحساب داخل اللعبة ----------
    elif text == '💳 التعبئة في حسابي':
        bot.send_message(user_id, "💰 هذه عملية شحن داخل اللعبة (يمكنك إضافة طريقة لاحقاً).")
    elif text == '💸 السحب من حسابي':
        bot.send_message(user_id, "💸 هذه عملية سحب من اللعبة (يمكنك إضافة طريقة لاحقاً).")
    elif text == '🗑 حذف الحساب':
        USER_STATE[user_id] = "confirm_delete"
        bot.send_message(user_id, "⚠️ سيتم تعطيل حسابك! اكتب كلمة **حذف** لتأكيد العملية:")

    elif USER_STATE.get(user_id) == "confirm_delete":
        if text.lower() == "حذف":
            USERS[user_id]["deleted"] = True
            USER_STATE[user_id] = None
            bot.send_message(user_id, "✅ تم تعطيل حسابك! يمكنك إنشاء حساب جديد.")
        else:
            USER_STATE[user_id] = None
            bot.send_message(user_id, "❌ تم إلغاء عملية الحذف.")

    # ---------- أوامر البوت ----------
    elif text == '➕ شحن رصيد':
        bot.send_message(user_id, "💳 اختر طريقة شحن الرصيد داخل البوت (يمكنك إضافة طرق لاحقاً).")
    elif text == '➖ سحب أرباح':
        bot.send_message(user_id, "💸 اختر طريقة سحب أرباحك (يمكنك إضافة طرق لاحقاً).")

# ========== وظائف مساعدة ==========
def process_username(message):
    user_id = message.from_user.id
    username = message.text
    if not is_valid_username(username):
        msg = bot.send_message(user_id, "❌ الاسم غير صالح! استخدم أحرف إنجليزية وأرقام فقط:")
        bot.register_next_step_handler(msg, process_username)
        return
    USERS[user_id]["account_name"] = username
    USER_STATE[user_id] = "creating_account_password"
    msg = bot.send_message(user_id, "🔒 اختر كلمة المرور (أحرف وأرقام فقط):")
    bot.register_next_step_handler(msg, process_password)

def process_password(message):
    user_id = message.from_user.id
    password = message.text
    if not is_valid_password(password):
        msg = bot.send_message(user_id, "❌ كلمة المرور غير صالحة! استخدم أحرف إنجليزية وأرقام فقط:")
        bot.register_next_step_handler(msg, process_password)
        return
    USERS[user_id]["password"] = password
    USER_STATE[user_id] = None
    bot.send_message(user_id, "✅ تم إنشاء الحساب بنجاح! يمكنك الآن استخدام البوت.")

# =======================
# تشغيل البوت
# =======================
bot.infinity_polling()
