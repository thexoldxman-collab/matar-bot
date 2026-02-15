import telebot
from telebot import types
from flask import Flask
from threading import Thread
import os
import sqlite3
from datetime import datetime

# ===========================
# 1. إعداد البوت والسيرفر (المنكز)
# ===========================
TOKEN = os.environ.get('TOKEN')
bot = telebot.TeleBot(TOKEN)
ADMIN_ID = 846938470  # الآيدي الخاص بك
CHANNEL_ID = "@Matar_ichancy"
CHANNEL_URL = "https://t.me/Matar_ichancy"

app = Flask('')
@app.route('/')
def home(): return "Matar Pro System is Online!"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

# ===========================
# 2. قاعدة البيانات (الشاملة والكاملة)
# ===========================
conn = sqlite3.connect("matar_pro_final.db", check_same_thread=False)
cursor = conn.cursor()

# إنشاء كل الجداول بدون استثناء
cursor.execute("""
CREATE TABLE IF NOT EXISTS users(
    user_id INTEGER PRIMARY KEY,
    account_name TEXT,
    password TEXT,
    balance REAL DEFAULT 0,
    site_balance REAL DEFAULT 0,
    has_account INTEGER DEFAULT 0,
    created_at TEXT
)""")

cursor.execute("CREATE TABLE IF NOT EXISTS gift_codes(code TEXT PRIMARY KEY, value REAL, used_by TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS support_msgs(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, message TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT)")

# إدخال إعدادات المحافظ الافتراضية
cursor.execute("INSERT OR IGNORE INTO settings VALUES ('syriatel_num', '74205110')")
cursor.execute("INSERT OR IGNORE INTO settings VALUES ('sham_num', 'SHAM-XXXX-XXXX')")
conn.commit()

# ===========================
# 3. الدوال المساعدة (الاشتراك والإعدادات)
# ===========================
def get_setting(key):
    cursor.execute("SELECT value FROM settings WHERE key=?", (key,))
    res = cursor.fetchone()
    return res[0] if res else "غير مضبوط"

def is_subscribed(uid):
    try:
        member = bot.get_chat_member(CHANNEL_ID, uid)
        return member.status in ["member", "administrator", "creator"]
    except: return False

# ===========================
# 4. لوحات المفاتيح (Keyboards)
# ===========================
def main_keyboard(uid):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(types.KeyboardButton('⚽ Ichancy ⚽'))
    markup.add(types.KeyboardButton('🔽 الشحن في البوت'), types.KeyboardButton('🔼 السحب من البوت'))
    markup.add(types.KeyboardButton('🎁 اهداء صديق'), types.KeyboardButton('🎫 كود هدية'))
    markup.add(types.KeyboardButton('💵 الرصيد'), types.KeyboardButton('💬 التواصل مع الدعم'))
    if uid == ADMIN_ID:
        markup.add(types.KeyboardButton('🔐 إدارة البوت'))
    return markup

def ichancy_inline_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("➕ التعبئة في حسابي", callback_data="dep_ich"),
               types.InlineKeyboardButton("➖ السحب من حسابي", callback_data="wit_ich"))
    markup.add(types.InlineKeyboardButton("💰 معلومات الحساب", callback_data="info_ich"))
    markup.add(types.InlineKeyboardButton("🔙 عودة", callback_data="back_main_inline"))
    return markup

# ===========================
# 5. معالجة الرسائل النصية (المنطق الكامل)
# ===========================
@bot.message_handler(func=lambda m: True)
def handle_msg(m):
    uid = m.from_user.id
    text = m.text

    if not is_subscribed(uid):
        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("اضغط للاشتراك بالقناة", url=CHANNEL_URL))
        bot.send_message(m.chat.id, f"أهلاً بك! 🌧️\nالرجاء الاشتراك في قناتنا لتتمكن من استخدام البوت: {CHANNEL_ID}", reply_markup=markup)
        return

    # ---- زر Ichancy ونظام الحساب ----
    if text == '⚽ Ichancy ⚽':
        cursor.execute("SELECT has_account FROM users WHERE user_id=?", (uid,))
        res = cursor.fetchone()
        if not res or res[0] == 0:
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True).add('✨ إنشاء حساب ichancy ✨')
            bot.send_message(m.chat.id, "ليس لديك حساب حالياً، اضغط على الزر أدناه للإنشاء:", reply_markup=markup)
        else:
            bot.send_message(m.chat.id, "الحد الادنى للتعبئة والسحب من حسابك Ichancy هو 100 ليرة سورية.", reply_markup=ichancy_inline_menu())

    elif text == '✨ إنشاء حساب ichancy ✨':
        msg = bot.send_message(m.chat.id, "ادخل اسم الحساب (أحرف إنكليزية وأرقام فقط):")
        bot.register_next_step_handler(msg, process_acc_name)

    # ---- نظام الشحن (ترتيبك الخاص) ----
    elif text == '🔽 الشحن في البوت':
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(types.InlineKeyboardButton("سيرياتل كاش (فوري) 📱", callback_data="sh_sy"),
                   types.InlineKeyboardButton("شام كاش (فوري) 💳", callback_data="sh_sh"))
        markup.add(types.InlineKeyboardButton("Binance", callback_data="sh_no"),
                   types.InlineKeyboardButton("USDT", callback_data="sh_no"))
        bot.send_message(m.chat.id, "💰 اختر وسيلة الشحن المناسبة:", reply_markup=markup)

    # ---- نظام السحب (عمولة 10%) ----
    elif text == '🔼 السحب من البوت':
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(types.InlineKeyboardButton("سيرياتل كاش", callback_data="wa_sy"),
                   types.InlineKeyboardButton("شام كاش", callback_data="wa_sh"))
        markup.add(types.InlineKeyboardButton("بنك بيمو", callback_data="wa_no"),
                   types.InlineKeyboardButton("CoinEx", callback_data="wa_no"),
                   types.InlineKeyboardButton("حوالة مالية", callback_data="wa_no"))
        bot.send_message(m.chat.id, "💸 اختر وسيلة السحب:", reply_markup=markup)

    # ---- الرصيد والدعم والهدايا ----
    elif text == '💵 الرصيد':
        cursor.execute("SELECT balance FROM users WHERE user_id=?", (uid,))
        res = cursor.fetchone()
        bot.send_message(m.chat.id, f"رصيدك الحالي في البوت: {res[0] if res else 0} NSP")

    elif text == '💬 التواصل مع الدعم':
        msg = bot.send_message(m.chat.id, "الرجاء كتابة رسالتك بوضوح وسيتم الرد عليك قريباً:")
        bot.register_next_step_handler(msg, save_support_msg)

    elif text == '🎫 كود هدية':
        msg = bot.send_message(m.chat.id, "أدخل كود الهدية:")
        bot.register_next_step_handler(msg, use_gift_code)

    # ---- لوحة إدارة البوت (تصحيح كامل) ----
    elif text == '🔐 إدارة البوت' and uid == ADMIN_ID:
        markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
        markup.add('تغيير كود سيريتل', 'تغيير كود شام', 'إرسال رسالة جماعية', 'إنشاء كود هدية', 'سجلات البوت', '🔙 عودة')
        bot.send_message(uid, "🔓 أهلاً بك في لوحة الإدارة:", reply_markup=markup)

    elif text == 'تغيير كود سيريتل' and uid == ADMIN_ID:
        msg = bot.send_message(uid, "أدخل رقم سيريتل كاش الجديد:")
        bot.register_next_step_handler(msg, lambda m: update_setting('syriatel_num', m.text))

    elif text == 'تغيير كود شام' and uid == ADMIN_ID:
        msg = bot.send_message(uid, "أدخل عنوان شام كاش الجديد:")
        bot.register_next_step_handler(msg, lambda m: update_setting('sham_num', m.text))

    elif text == 'حذف':
        cursor.execute("UPDATE users SET has_account=0 WHERE user_id=?", (uid,))
        conn.commit()
        bot.send_message(m.chat.id, "✅ تم حذف بيانات حسابك بنجاح. يمكنك إنشاء حساب جديد الآن.", reply_markup=main_keyboard(uid))

    elif text == '🔙 عودة':
        bot.send_message(m.chat.id, "تمت العودة للقائمة الرئيسية", reply_markup=main_keyboard(uid))

# ===========================
# 6. دوال إنشاء الحساب
# ===========================
def process_acc_name(message):
    name = message.text.strip()
    if not name.isalnum():
        msg = bot.send_message(message.chat.id, "الاسم يجب أن يكون إنكليزي فقط. حاول مرة أخرى:")
        bot.register_next_step_handler(msg, process_acc_name)
        return
    full_name = f"Matar-{name}"
    msg = bot.send_message(message.chat.id, "ادخل كلمة المرور الخاصة بحسابك:")
    bot.register_next_step_handler(msg, process_acc_pass, full_name)

def process_acc_pass(message, full_name):
    uid = message.from_user.id
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    cursor.execute("INSERT OR REPLACE INTO users(user_id, account_name, password, balance, has_account, created_at) VALUES(?,?,?,?,?,?)",
                   (uid, full_name, message.text, 0, 1, now))
    conn.commit()
    bot.send_message(message.chat.id, f"✅ تم إنشاء حسابك بنجاح 🌧️\nالاسم: {full_name}", reply_markup=main_keyboard(uid))

# ===========================
# 7. معالجة الـ Callback (أزرار شفافة)
# ===========================
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    uid = call.from_user.id
    
    if call.data == "info_ich":
        cursor.execute("SELECT account_name, site_balance, user_id, created_at FROM users WHERE user_id=?", (uid,))
        user = cursor.fetchone()
        if user:
            info = (f"🌐 اسم حسابك على الموقع : {user[0]}\n🌐 رصيدك على الموقع : {user[1]} NSP\n\n"
                    f"🤖 اسم حسابك على البوت : {call.from_user.first_name}\n🤖 رصيدك على البوت : 0 NSP\n\n"
                    f"⚽ معرف اللاعب: {user[2]}\n🗓 تاريخ إنشاء الحساب: {user[3]}")
            bot.send_message(call.message.chat.id, info)
        else: bot.answer_callback_query(call.id, "يرجى إنشاء حساب أولاً!")

    elif call.data == "sh_sy":
        num = get_setting('syriatel_num')
        bot.send_message(call.message.chat.id, f"📱 **سيريتل كاش**\nقم بالتحويل للرقم: `{num}`\nثم أرسل رقم العملية (12 رقم):")
        bot.register_next_step_handler(call.message, deposit_step_1)

    elif call.data == "wa_sy":
        bot.send_message(call.message.chat.id, "⚠️ السحب سيريتل كاش\n• العمولة: 10%\n• المدة: 1-24 ساعة\nأدخل المبلغ المراد سحبه:")
        bot.register_next_step_handler(call.message, process_withdraw, "سيريتل")

    elif call.data == "sh_no":
        bot.answer_callback_query(call.id, "عذراً، الشحن بهذه الطريقة متوقف حالياً ⚠️", show_alert=True)

    elif call.data == "back_main_inline":
        bot.edit_message_text("القائمة الرئيسية:", call.message.chat.id, call.message.message_id, reply_markup=None)

# ===========================
# 8. وظائف الإدارة والعمليات
# ===========================
def update_setting(key, val):
    cursor.execute("INSERT OR REPLACE INTO settings VALUES (?, ?)", (key, val))
    conn.commit()
    bot.send_message(ADMIN_ID, f"✅ تم التحديث بنجاح: {val}")

def deposit_step_1(message):
    op_id = message.text
    bot.send_message(message.chat.id, "أدخل المبلغ الذي قمت بإرساله:")
    bot.register_next_step_handler(message, lambda m: bot.send_message(m.chat.id, "⏳ جاري التحقق من العملية... سيتم الشحن فور المطابقة."))

def process_withdraw(message, method):
    try:
        amount = float(message.text)
        bot.send_message(message.chat.id, "✅ تم سحب رصيدك بنجاح، سيصلك المبلغ خلال مدة من دقيقة إلى 24 ساعة.")
        bot.send_message(ADMIN_ID, f"🔔 طلب سحب جديد:\nالمستخدم: {message.from_user.id}\nالمبلغ: {amount}\nالطريقة: {method}")
    except: bot.send_message(message.chat.id, "❌ خطأ! أدخل أرقام فقط.")

def save_support_msg(message):
    cursor.execute("INSERT INTO support_msgs(user_id, message) VALUES(?,?)", (message.from_user.id, message.text))
    conn.commit()
    bot.send_message(message.chat.id, "✅ تم استلام رسالتك! سيتم الرد عليك قريباً.")

def use_gift_code(message):
    bot.send_message(message.chat.id, "⏳ جاري التحقق من الكود...")

# ===========================
# 9. التشغيل النهائي
# ===========================
if __name__ == "__main__":
    keep_alive()
    print("Matar Bot is Fully Running!")
    bot.polling(none_stop=True)
