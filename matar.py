import telebot
from telebot import types
from flask import Flask
from threading import Thread
import os
import sqlite3
import random
import string

# ===========================
# 1. إعداد السيرفر (Render + UptimeRobot)
# ===========================
app = Flask('')
@app.route('/')
def home(): return "Matar Bot is Online!"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

# ===========================
# 2. إعداد البوت والقاعدة
# ===========================
TOKEN = os.environ.get('TOKEN')
bot = telebot.TeleBot(TOKEN)
conn = sqlite3.connect("matar.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""CREATE TABLE IF NOT EXISTS users(
    user_id INTEGER PRIMARY KEY, account_name TEXT, password TEXT, 
    balance REAL DEFAULT 0, site_balance REAL DEFAULT 0, 
    has_account INTEGER DEFAULT 0, is_banned INTEGER DEFAULT 0)""")

cursor.execute("CREATE TABLE IF NOT EXISTS gift_codes(code TEXT PRIMARY KEY, value REAL, limit_usage INTEGER, current_usage INTEGER DEFAULT 0)")
cursor.execute("CREATE TABLE IF NOT EXISTS used_codes(user_id INTEGER, code TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT)")
cursor.execute("INSERT OR IGNORE INTO settings VALUES ('syriatel_code', 'لم يحدد'), ('cham_address', 'لم يحدد')")
conn.commit()

# ===========================
# 3. الإعدادات (الأدمن والقناة)
# ===========================
CHANNEL_ID = "@Matar_ichancy"
CHANNEL_URL = "https://t.me/Matar_ichancy"
ADMINS = [8581064983] # الـ ID الخاص بك

def is_subscribed(user_id):
    try:
        member = bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ["member", "administrator", "creator"]
    except: return False

def is_admin(user_id): return user_id in ADMINS

# ===========================
# 4. لوحات المفاتيح
# ===========================
def main_keyboard(u_id):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add('ichancy', 'الشحن في البوت', 'السحب من البوت', 'اهداء صديق', 'كود هدية', 'الرصيد', 'التواصل مع الدعم')
    if is_admin(u_id): markup.add('إدارة البوت')
    return markup

# ===========================
# 5. منطق الأزرار والرسائل
# ===========================
@bot.message_handler(commands=['start'])
def start(message):
    u_id = message.from_user.id
    if not is_subscribed(u_id):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("اشترك هنا 📢", url=CHANNEL_URL),
                   types.InlineKeyboardButton("تم الاشتراك ✅", callback_data="check_sub"))
        bot.send_message(message.chat.id, "أهلاً بك في بوت Matar الرسمي لموقع iChancy 🌧️\nيرجى الاشتراك بالقناة للمتابعة.", reply_markup=markup)
        return
    bot.send_message(message.chat.id, "أهلاً بك في بوت مطر!", reply_markup=main_keyboard(u_id))

@bot.message_handler(func=lambda m: True)
def handle_text(message):
    u_id = message.from_user.id
    text = message.text

    if text == 'ichancy':
        cursor.execute("SELECT * FROM users WHERE user_id=?", (u_id,))
        u = cursor.fetchone()
        if not u or u[5] == 0:
            bot.send_message(message.chat.id, "اضغط لإنشاء حساب:", reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add('إنشاء حساب ichancy', 'الرجوع للقائمة'))
        else:
            info = f"👤 حسابك iChancy:\n━━━━━━━━━━━━━━━\n🆔 ID البوت: `{u_id}`\n👤 الاسم: `{u[1]}`\n🔑 السر: `{u[2]}`\n💰 رصيد الموقع: {u[4]}$"
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(types.InlineKeyboardButton("الشحن في الحساب 📥", callback_data="site_dep"),
                       types.InlineKeyboardButton("السحب من الحساب 📤", callback_data="site_with"),
                       types.InlineKeyboardButton("❌ حذف الحساب", callback_data="confirm_del"))
            bot.send_message(message.chat.id, info, reply_markup=markup, parse_mode="Markdown")

    elif text == 'إنشاء حساب ichancy':
        msg = bot.send_message(message.chat.id, "ادخل اسم الحساب (إنكليزي):")
        bot.register_next_step_handler(msg, process_acc_name)

    elif text == 'اهداء صديق':
        msg = bot.send_message(message.chat.id, "الرجاء إدخال معرف ID الشخص المراد إرسال المبلغ إليه:")
        bot.register_next_step_handler(msg, process_gift_id)

    elif text == 'الرصيد':
        cursor.execute("SELECT balance FROM users WHERE user_id=?", (u_id,))
        bal = cursor.fetchone()[0]
        bot.send_message(message.chat.id, f"💰 رصيدك في البوت: {bal}")

    elif text == 'إدارة البوت' and is_admin(u_id):
        markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
        markup.add('إنشاء كود هدية', 'حظر مستخدم', 'شحن رصيد لمستخدم', 'سحب رصيد لمستخدم', 'تغيير عناوين الكاش', 'الرجوع للقائمة')
        bot.send_message(message.chat.id, "🛠️ إدارة البوت:", reply_markup=markup)

    elif text == 'الرجوع للقائمة':
        bot.send_message(message.chat.id, "القائمة الرئيسية:", reply_markup=main_keyboard(u_id))

# ===========================
# 6. وظيفة اهداء صديق (التي طلبتها بدقة)
# ===========================
def process_gift_id(message):
    target_id = message.text.strip()
    cursor.execute("SELECT has_account FROM users WHERE user_id=?", (target_id,))
    res = cursor.fetchone()
    if not res or res[0] == 0:
        bot.send_message(message.chat.id, "❌ عذراً لا يمكنك اهداء رصيد فهذا الشخص لا يملك حساب على بوت Matar")
        return
    msg = bot.send_message(message.chat.id, "الرجاء إدخال القيمة المراد إهداءها:")
    bot.register_next_step_handler(msg, finalize_gift, target_id)

def finalize_gift(message, target_id):
    try:
        amount = float(message.text)
        sender_id = message.from_user.id
        cursor.execute("SELECT balance FROM users WHERE user_id=?", (sender_id,))
        sender_bal = cursor.fetchone()[0]
        if sender_bal < amount:
            bot.send_message(message.chat.id, "❌ رصيدك غير كافٍ!")
            return
        cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, sender_id))
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, target_id))
        conn.commit()
        bot.send_message(message.chat.id, f"✅ تم إهداء {amount} بنجاح للصديق {target_id}")
        bot.send_message(target_id, f"🎁 وصلك إهداء بقيمة {amount} من المستخدم {sender_id}")
    except: bot.send_message(message.chat.id, "❌ خطأ في القيمة.")

# ===========================
# 7. وظيفة إنشاء حساب (بادئة Matar-)
# ===========================
def process_acc_name(message):
    full_name = f"Matar-{message.text.strip()}"
    msg = bot.send_message(message.chat.id, f"الاسم: {full_name}\nادخل كلمة المرور:")
    bot.register_next_step_handler(msg, finalize_acc, full_name)

def finalize_acc(message, full_name):
    cursor.execute("INSERT OR REPLACE INTO users(user_id, account_name, password, has_account) VALUES(?,?,?,1)",
                   (message.from_user.id, full_name, message.text.strip()))
    conn.commit()
    bot.send_message(message.chat.id, "✅ تم إنشاء حسابك بنجاح أهلاً وسهلاً بك في بوت Matar", reply_markup=main_keyboard(message.from_user.id))

# ===========================
# 8. الكولباك (Check Sub & Delete)
# ===========================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    if call.data == "check_sub":
        if is_subscribed(call.from_user.id):
            bot.delete_message(call.message.chat.id, call.message.message_id)
            bot.send_message(call.message.chat.id, "✅ تم التحقق!", reply_markup=main_keyboard(call.from_user.id))
        else: bot.answer_callback_query(call.id, "❌ لم تشترك بعد!", show_alert=True)
    elif call.data == "confirm_del":
        msg = bot.send_message(call.message.chat.id, "⚠️ للتأكيد اكتب كلمة `حذف` وأرسلها:")
        bot.register_next_step_handler(msg, lambda m: bot.send_message(m.chat.id, "✅ تم الحذف") if m.text == "حذف" else None)

if __name__ == "__main__":
    keep_alive()
    bot.polling(none_stop=True)
