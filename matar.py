import re
from telebot import TeleBot, types

# =======================
# إعدادات البوت والإدمن
# =======================
TOKEN = '8581064983:AAE43_TNTx8Fnww6-vs8MVlb97ahTzCvNhM'
bot = TeleBot(TOKEN)
ADMIN_ID = 846938470

# =======================
# إعدادات النظام
# =======================
CHANNEL_USERNAME = "Matar_ichancy"

# =======================
# قواعد بيانات مؤقتة
# =======================
USERS = {}  # بيانات كل مستخدم {user_id: {...}}

# =======================
# لوحة المفاتيح
# =======================
def main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add('⚽ ايشانسي | Ichancy', '💰 حسابي')
    markup.add('➕ شحن رصيد', '➖ سحب أرباح')
    markup.add('📢 القناة الرسمية', '🛠 الدعم الفني')
    markup.add('إنشاء حساب', 'انضم كوكيل معتمد')
    return markup

def admin_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add('📊 إحصائيات البوت', '📋 تقرير الحسابات')
    markup.add('💵 تعديل كلمة السر/الحظر', '🔧 وضع صيانة')
    markup.add('📢 إذاعة للكل', '🔙 العودة للقائمة')
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
    USERS.setdefault(user_id, {
        "account_name": None,
        "password": None,
        "bot_balance": 0,
        "game_balance": 0,
        "referrer": None,
        "pending_commission": 0,
        "banned": False
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

    if USERS.get(user_id, {}).get("banned", False):
        bot.send_message(user_id, "🚫 تم حظر حسابك، لا يمكنك استخدام البوت.")
        return

    # ---------- أوامر الزبون ----------
    if text == '💰 حسابي':
        bot.send_message(user_id, f"💰 رصيد البوت: {USERS[user_id]['bot_balance']}\n👤 اسم الحساب: {USERS[user_id]['account_name']}")
    
    elif text == '⚽ ايشانسي | Ichancy':
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        markup.add('💳 التعبئة في حسابي', '💸 السحب من حسابي', '🔙 العودة')
        bot.send_message(user_id, f"👤 حسابك داخل اللعبة: {USERS[user_id]['account_name']}\n💰 رصيد اللعبة: {USERS[user_id]['game_balance']}", reply_markup=markup)
    
    elif text == '➕ شحن رصيد':
        bot.send_message(user_id, "💳 اختر طريقة شحن الرصيد داخل البوت (يمكنك إضافة طرق لاحقاً).")
    
    elif text == '➖ سحب أرباح':
        bot.send_message(user_id, "💸 اختر طريقة سحب الرصيد من البوت (يمكنك إضافة طرق لاحقاً).")
    
    elif text == '🛠 الدعم الفني':
        bot.send_message(user_id, "للتواصل مع الإدارة: @YourUsername")
    
    elif text == '📢 القناة الرسمية':
        bot.send_message(user_id, f"🔗 رابط القناة: https://t.me/{CHANNEL_USERNAME}")
    
    elif text == 'إنشاء حساب':
        msg = bot.send_message(user_id, "📌 اختر اسم الحساب (بالأحرف الإنجليزية والأرقام فقط):")
        bot.register_next_step_handler(msg, process_username)
    
    elif text == 'انضم كوكيل معتمد':
        bot.send_message(user_id, "احصل على دخل إضافي كل 10 أيام من خلال رابط إحالتك الخاص! 🤝")
    
    # ---------- أوامر الإدارة ----------
    elif text == '/admin' and user_id == ADMIN_ID:
        bot.send_message(user_id, "🔓 أهلاً بك يا زعيم", reply_markup=admin_keyboard())
    
    elif text == '📋 تقرير الحسابات' and user_id == ADMIN_ID:
        send_users_report(user_id)
    
    elif text == '💵 تعديل كلمة السر/الحظر' and user_id == ADMIN_ID:
        select_user_to_edit(user_id)
    
    elif text == '🔙 العودة':
        bot.send_message(user_id, "تمت العودة للقائمة الرئيسية 🏠", reply_markup=main_keyboard())

# =======================
# إنشاء الحساب
# =======================
def process_username(message):
    user_id = message.from_user.id
    username = message.text.strip()

    if not is_valid_username(username):
        msg = bot.send_message(user_id, "❌ الاسم غير صالح. استخدم فقط الأحرف الإنجليزية والأرقام:")
        bot.register_next_step_handler(msg, process_username)
        return
    
    full_username = f"Matar-{username}"
    USERS[user_id]["account_name"] = full_username

    msg = bot.send_message(user_id, "📌 الآن اختر كلمة السر (بالأحرف الإنجليزية والأرقام فقط):")
    bot.register_next_step_handler(msg, process_password)

def process_password(message):
    user_id = message.from_user.id
    password = message.text.strip()

    if not is_valid_password(password):
        msg = bot.send_message(user_id, "❌ كلمة السر غير صالحة. استخدم فقط الأحرف الإنجليزية والأرقام:")
        bot.register_next_step_handler(msg, process_password)
        return
    
    USERS[user_id]["password"] = password
    bot.send_message(user_id, f"✅ تم إنشاء الحساب بنجاح!\n👤 اسم الحساب: {USERS[user_id]['account_name']}")

# =======================
# لوحة الإدارة: تقرير الحسابات
# =======================
def send_users_report(admin_id):
    report = ""
    for uid, data in USERS.items():
        report += f"ID: {uid}\nالحساب: {data['account_name']}\nكلمة السر: {data['password']}\nالحالة: {'محظور' if data['banned'] else 'مفعل'}\n\n"
    bot.send_message(admin_id, report or "لا يوجد مستخدمين حتى الآن.")

# =======================
# لوحة الإدارة: تعديل كلمة السر أو الحظر
# =======================
def select_user_to_edit(admin_id):
    if not USERS:
        bot.send_message(admin_id, "لا يوجد مستخدمين لتعديلهم.")
        return

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    for uid, data in USERS.items():
        markup.add(f"{uid} | {data['account_name']}")
    markup.add("🔙 العودة")
    
    msg = bot.send_message(admin_id, "اختر المستخدم لتعديل كلمة السر أو حظره:", reply_markup=markup)
    bot.register_next_step_handler(msg, process_user_edit)

def process_user_edit(message):
    admin_id = message.from_user.id
    text = message.text.strip()

    if text == "🔙 العودة":
        bot.send_message(admin_id, "تمت العودة للقائمة", reply_markup=admin_keyboard())
        return

    try:
        uid = int(text.split("|")[0].strip())
    except:
        bot.send_message(admin_id, "❌ اختيار غير صالح.")
        select_user_to_edit(admin_id)
        return

    if uid not in USERS:
        bot.send_message(admin_id, "❌ المستخدم غير موجود.")
        select_user_to_edit(admin_id)
        return

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("تغيير كلمة السر", "حظر/إلغاء الحظر", "🔙 العودة")
    msg = bot.send_message(admin_id, f"تعديل المستخدم: {USERS[uid]['account_name']}", reply_markup=markup)
    bot.register_next_step_handler(msg, lambda m: process_edit_action(m, uid))

def process_edit_action(message, uid):
    admin_id = message.from_user.id
    text = message.text.strip()

    if text == "تغيير كلمة السر":
        msg = bot.send_message(admin_id, "أدخل كلمة السر الجديدة (بالأحرف الإنجليزية والأرقام فقط):")
        bot.register_next_step_handler(msg, lambda m: update_password(m, uid))
    elif text == "حظر/إلغاء الحظر":
        USERS[uid]["banned"] = not USERS[uid]["banned"]
        status = "محظور" if USERS[uid]["banned"] else "مفعل"
        bot.send_message(admin_id, f"تم تعديل حالة المستخدم: {status}")
        select_user_to_edit(admin_id)
    elif text == "🔙 العودة":
        bot.send_message(admin_id, "تمت العودة للقائمة", reply_markup=admin_keyboard())
    else:
        bot.send_message(admin_id, "اختيار غير صالح.")
        select_user_to_edit(admin_id)

def update_password(message, uid):
    admin_id = message.from_user.id
    password = message.text.strip()

    if not is_valid_password(password):
        msg = bot.send_message(admin_id, "❌ كلمة السر غير صالحة. استخدم فقط الأحرف الإنجليزية والأرقام:")
        bot.register_next_step_handler(msg, lambda m: update_password(m, uid))
        return
    
    USERS[uid]["password"] = password
    bot.send_message(admin_id, f"✅ تم تغيير كلمة السر للمستخدم {USERS[uid]['account_name']}")
    select_user_to_edit(admin_id)

# =======================
# بدء تشغيل البوت
# =======================
if __name__ == "__main__":
    print("البوت شغال الآن...")
    bot.polling(none_stop=True)
