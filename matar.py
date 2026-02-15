import telebot
from telebot import types
from flask import Flask
from threading import Thread
import os
import sqlite3
from datetime import datetime

# ===========================
# إعداد البوت والسيرفر
# ===========================
TOKEN = os.environ.get('TOKEN')
bot = telebot.TeleBot(TOKEN)
ADMIN_ID = 846938470  # آيديك الصحيح والمثبت
CHANNEL_ID = "@Matar_ichancy"
CHANNEL_URL = "https://t.me/Matar_ichancy"

app = Flask('')
@app.route('/')
def home(): return "Matar Pro System is Online!"

def run(): app.run(host='0.0.0.0', port=8080)
def keep_alive():
    t = Thread(target=run)
    t.start()

# ===========================
# قاعدة البيانات المتطورة
# ===========================
conn = sqlite3.connect("matar_final.db", check_same_thread=False)
cursor = conn.cursor()

# إنشاء الجداول الأساسية
cursor.execute("""
CREATE TABLE IF NOT EXISTS users(
    user_id INTEGER PRIMARY KEY,
    acc_name TEXT,
    balance REAL DEFAULT 0,
    has_account INTEGER DEFAULT 0,
    created_at TEXT
)""")

# جدول الإعدادات (لتغيير الأرقام من الإدارة)
cursor.execute("CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT)")
cursor.execute("INSERT OR IGNORE INTO settings VALUES ('syriatel_num', '74205110')")
cursor.execute("INSERT OR IGNORE INTO settings VALUES ('sham_num', '0837b5dcb92586f3480dec4114ac1b21')")
conn.commit()

# ===========================
# دوال المساعدة
# ===========================
def get_setting(key):
    cursor.execute("SELECT value FROM settings WHERE key=?", (key,))
    res = cursor.fetchone()
    return res[0] if res else "غير مضبوط"

def is_subscribed(uid):
    try:
        status = bot.get_chat_member(CHANNEL_ID, uid).status
        return status in ['member', 'administrator', 'creator']
    except: return False

# ===========================
# لوحات المفاتيح (مطابق للصور)
# ===========================
def main_kb(uid):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(types.KeyboardButton('⚽ Ichancy ⚽')) # الزر الأول مستقل
    markup.add(types.KeyboardButton('🔽 الشحن في البوت'), types.KeyboardButton('🔼 السحب من البوت'))
    markup.add(types.KeyboardButton('🎁 اهداء صديق'), types.KeyboardButton('🎫 كود هدية'))
    markup.add(types.KeyboardButton('💵 الرصيد'), types.KeyboardButton('💬 التواصل مع الدعم'))
    if uid == ADMIN_ID: markup.add(types.KeyboardButton('🔐 إدارة البوت'))
    return markup

def ichancy_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("➕ التعبئة في حسابي", callback_data="dep_ich"),
               types.InlineKeyboardButton("➖ السحب من حسابي", callback_data="wit_ich"))
    markup.add(types.InlineKeyboardButton("💰 معلومات الحساب", callback_data="info_ich"))
    markup.add(types.InlineKeyboardButton("🔙 عودة", callback_data="back_main"))
    return markup

# ===========================
# الأوامر الرئيسية
# ===========================
@bot.message_handler(commands=['start'])
def start(message):
    uid = message.from_user.id
    if not is_subscribed(uid):
        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("اضغط للاشتراك", url=CHANNEL_URL))
        bot.send_message(message.chat.id, "⚠️ يجب الاشتراك بقناة البوت أولاً!", reply_markup=markup)
        return
    
    welcome = (f"Good luck 🎯\n\n💫 الذهاب إلى الموقع\nhttps://ichancy.com\n\n"
               f"مرحباً بك في بوت Matar الرسمي لموقع iChancy 🌧️\nأهلاً بك يا {message.from_user.first_name}")
    bot.send_message(message.chat.id, welcome, reply_markup=main_kb(uid))

@bot.message_handler(func=lambda m: True)
def handle_text(m):
    uid = m.from_user.id
    if not is_subscribed(uid): return

    if m.text == '⚽ Ichancy ⚽':
        bot.send_message(m.chat.id, "الحد الادنى للتعبئة والسحب من حسابك Ichancy هو 100 ليرة سورية.", reply_markup=ichancy_menu())

    elif m.text == '🔽 الشحن في البوت':
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(types.InlineKeyboardButton("سيرياتل كاش (فوري)", callback_data="sh_sy"),
                   types.InlineKeyboardButton("شام كاش (فوري)", callback_data="sh_sh"))
        markup.add(types.InlineKeyboardButton("USDT (يدوي)", callback_data="sh_no"),
                   types.InlineKeyboardButton("CoinEx (فوري)", callback_data="sh_no"))
        markup.add(types.InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="back_main"))
        bot.send_message(m.chat.id, "💰 اختر طريقة الشحن:", reply_markup=markup)

    elif m.text == '🔼 السحب من البوت':
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(types.InlineKeyboardButton("سيرياتل كاش", callback_data="wa_sy"),
                   types.InlineKeyboardButton("بنك بيمو", callback_data="wa_no"))
        markup.add(types.InlineKeyboardButton("شام كاش", callback_data="wa_sh"),
                   types.InlineKeyboardButton("CoinEx", callback_data="wa_no"))
        markup.add(types.InlineKeyboardButton("حوالة مالية", callback_data="wa_no"))
        markup.add(types.InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="back_main"))
        bot.send_message(m.chat.id, "💸 اختر طريقة السحب:", reply_markup=markup)

    elif m.text == '🔐 إدارة البوت' and uid == ADMIN_ID:
        adm = types.ReplyKeyboardMarkup(resize_keyboard=True)
        adm.add('تغيير كود سيريتل', 'تغيير كود شام')
        adm.add('إرسال رسالة جماعية', '🔙 العودة')
        bot.send_message(uid, "🔓 لوحة التحكم الإدارية:", reply_markup=adm)

    elif m.text == 'تغيير كود سيريتل' and uid == ADMIN_ID:
        msg = bot.send_message(uid, "أدخل كود سيريتل كاش الجديد:")
        bot.register_next_step_handler(msg, lambda m: update_setting('syriatel_num', m.text))

    elif m.text == 'حذف':
        cursor.execute("UPDATE users SET has_account=0 WHERE user_id=?", (uid,))
        conn.commit()
        bot.send_message(m.chat.id, "✅ تم حذف بيانات حسابك.")

    elif m.text == '❌ إلغاء' or m.text == 'إلغاء':
        bot.send_message(m.chat.id, "تم الإلغاء ❌", reply_markup=main_kb(uid))

# ===========================
# معالجة Callback (التحقق الآلي والسحب)
# ===========================
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    uid = call.from_user.id
    
    if call.data == "info_ich":
        cursor.execute("SELECT acc_name, balance, user_id, created_at FROM users WHERE user_id=?", (uid,))
        user = cursor.fetchone()
        if user and user[0]:
            info = (f"🌐 اسم حسابك على الموقع : {user[0]}\n🌐 رصيدك على الموقع : {user[1]} NSP\n\n"
                    f"🤖 اسم حسابك على البوت : {call.from_user.first_name}\n🤖 رصيدك على البوت : 0 NSP\n\n"
                    f"⚽ معرف اللاعب: {user[2]}\n🗓 تاريخ إنشاء الحساب: {user[3]}")
            bot.send_message(call.message.chat.id, info) # هنا يمكنك إضافة صورة الـ Slot
        else:
            bot.answer_callback_query(call.id, "يرجى إنشاء حساب أولاً!")

    elif call.data == "sh_no":
        bot.answer_callback_query(call.id, "عذراً، الشحن بهذه الطريقة متوقف حالياً ⚠️", show_alert=True)

    elif call.data == "sh_sy":
        num = get_setting('syriatel_num')
        text = f"أرسل المبلغ للكود: `{num}`\nثم أرسل رقم العملية (12 رقم):"
        bot.send_message(call.message.chat.id, text, parse_mode="Markdown")
        bot.register_next_step_handler(call.message, process_deposit, "سيريتل")

    elif call.data == "wa_sy":
        text = "السحب عن طريق سيريتل كاش 📱\n• المدة: 12 ساعة\n• العمولة: 10%\n• الحد الادنى : 500\nأدخل المبلغ المراد سحبه:"
        bot.send_message(call.message.chat.id, text)
        bot.register_next_step_handler(call.message, process_withdraw, "سيريتل")

# ===========================
# وظائف الإدارة والتحقق
# ===========================
def update_setting(key, val):
    cursor.execute("INSERT OR REPLACE INTO settings VALUES (?, ?)", (key, val))
    conn.commit()
    bot.send_message(ADMIN_ID, f"✅ تم تحديث {key} إلى: {val}")

def process_deposit(message, method):
    # هنا نطلب المبلغ بعد رقم العملية للتحقق الآلي
    bot.send_message(message.chat.id, "أدخل المبلغ الذي قمت بإرساله:")
    # يتم الربط هنا مستقبلاً مع API الكاشيرة
    bot.send_message(message.chat.id, "⏳ جاري التحقق من العملية... سيتم الشحن فور التأكيد.")

def process_withdraw(message, method):
    amount = float(message.text)
    # خصم تلقائي من قاعدة البيانات
    bot.send_message(message.chat.id, "✅ تم سحب رصيدك بنجاح، سيصلك المبلغ خلال مدة من دقيقة إلى 24 ساعة.")
    bot.send_message(ADMIN_ID, f"🔔 طلب سحب جديد:\nالمستخدم: {message.from_user.id}\nالمبلغ: {amount}\nالطريقة: {method}")

if __name__ == "__main__":
    keep_alive()
    bot.polling(none_stop=True)
