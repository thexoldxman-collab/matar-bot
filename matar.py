import telebot
from telebot import types
import sqlite3
import os
from flask import Flask
from threading import Thread

# 1. الإعدادات (تأكد من وضع التوكن الصحيح هنا)
TOKEN = os.environ.get('TOKEN')
bot = telebot.TeleBot(TOKEN)
ADMIN_ID = 846938470  # آيديك الصحيح

# --- تشغيل الموقع الصغير ليضل البوت شغال ---
app = Flask('')
@app.route('/')
def home(): return "Matar Bot is Online!"

def run(): app.run(host='0.0.0.0', port=8080)
def keep_alive():
    t = Thread(target=run)
    t.start()

# 2. قاعدة البيانات (تخزين بسيط)
conn = sqlite3.connect("matar.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS users (uid INTEGER PRIMARY KEY, name TEXT, acc_id TEXT, balance REAL DEFAULT 0, step TEXT)")
conn.commit()

# --- القوائم ---
def main_kb(uid):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(types.KeyboardButton('⚽ ايشانسي | Ichancy ⚽'))
    markup.add(types.KeyboardButton('🔽 الشحن في البوت 🔽'), types.KeyboardButton('🔼 السحب من البوت 🔼'))
    markup.add(types.KeyboardButton('💵 الرصيد 💵'), types.KeyboardButton('🎁 كود هدية'))
    markup.add(types.KeyboardButton('💰 دعوة الأصدقاء 💰'), types.KeyboardButton('💬 التواصل مع الدعم 💬'))
    if uid == ADMIN_ID:
        markup.add(types.KeyboardButton('🔐 إدارة البوت'))
    return markup

# 3. معالجة الرسائل
@bot.message_handler(commands=['start'])
def start(message):
    uid = message.from_user.id
    cursor.execute("INSERT OR IGNORE INTO users (uid) VALUES (?)", (uid,))
    conn.commit()
    bot.send_message(message.chat.id, "🎯 أهلاً بك في بوت مطر الشغال.", reply_markup=main_kb(uid))

@bot.message_handler(func=lambda m: True)
def handle(m):
    uid = m.from_user.id
    text = m.text

    if text == '⚽ ايشانسي | Ichancy ⚽':
        cursor.execute("SELECT name, acc_id, balance FROM users WHERE uid=?", (uid,))
        res = cursor.fetchone()
        name = res[0] if res and res[0] else "لم يتم الضبط"
        acc_id = res[1] if res and res[1] else "لم يتم الضبط"
        
        info = f"👤 اسم الحساب: {name}\n🆔 آيدي الحساب: {acc_id}\n💰 الرصيد: {res[2] if res else 0} NSP"
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(types.InlineKeyboardButton("➕ شحن الحساب", callback_data="dep"),
                   types.InlineKeyboardButton("➖ سحب من الحساب", callback_data="wit"))
        markup.add(types.InlineKeyboardButton("❌ حذف الحساب", callback_data="del_confirm"))
        bot.send_message(m.chat.id, info, reply_markup=markup)

    elif text == '🔽 الشحن في البوت 🔽':
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add('🇸🇾 سيريتل كاش', '💎 شام كاش', '🔙 العودة')
        bot.send_message(m.chat.id, "اختر وسيلة الشحن:", reply_markup=markup)

    elif text == '🇸🇾 سيريتل كاش':
        bot.send_message(m.chat.id, "💳 حول للرقم: `09xxxxxxx` ثم أرسل الإشعار.")

    elif text == '🔐 إدارة البوت' and uid == ADMIN_ID:
        bot.send_message(uid, "🔓 لوحة التحكم:\n1. /broadcast (رسالة) للإذاعة\n2. /set_balance (id) (amount)")

    elif text == 'حذف':
        cursor.execute("UPDATE users SET name=NULL, acc_id=NULL WHERE uid=?", (uid,))
        conn.commit()
        bot.send_message(m.chat.id, "✅ تم حذف بيانات حسابك بنجاح.")

    elif text == '🔙 العودة':
        bot.send_message(m.chat.id, "القائمة الرئيسية:", reply_markup=main_kb(uid))

# 4. تشغيل البوت
if __name__ == "__main__":
    try:
        keep_alive()
        print("جاري التشغيل...")
        bot.polling(none_stop=True)
    except Exception as e:
        print(f"خطأ في التشغيل: {e}")
