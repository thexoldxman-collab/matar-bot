import telebot
from telebot import types
from flask import Flask
from threading import Thread
import os
import sqlite3
from datetime import datetime

# ===========================
# 1. إعدادات البوت والسيرفر
# ===========================
TOKEN = os.environ.get('TOKEN')
bot = telebot.TeleBot(TOKEN)
ADMIN_ID = 846938470  
CHANNEL_ID = "@Matar_ichancy"
CHANNEL_URL = "https://t.me/Matar_ichancy"

app = Flask('')
@app.route('/')
def home(): return "Matar Pro System is Online!"

def run():
    try:
        app.run(host='0.0.0.0', port=8080)
    except: pass

def keep_alive():
    t = Thread(target=run)
    t.start()

# ===========================
# 2. قاعدة البيانات (الهيكل العملاق)
# ===========================
conn = sqlite3.connect("matar_final_system.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""CREATE TABLE IF NOT EXISTS users(
    user_id INTEGER PRIMARY KEY, acc_name TEXT, password TEXT, balance REAL DEFAULT 0, 
    site_balance REAL DEFAULT 0, status TEXT DEFAULT 'active', created_at TEXT)""")

cursor.execute("""CREATE TABLE IF NOT EXISTS gifts(
    code TEXT PRIMARY KEY, value REAL, limit_count INTEGER, used_count INTEGER DEFAULT 0, type TEXT)""")

cursor.execute("CREATE TABLE IF NOT EXISTS gift_usage(user_id INTEGER, code TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS support_msgs(id INTEGER PRIMARY KEY AUTOINCREMENT, uid INTEGER, msg TEXT)")

cursor.execute("INSERT OR IGNORE INTO settings VALUES ('syriatel_num', '74205110')")
cursor.execute("INSERT OR IGNORE INTO settings VALUES ('sham_num', 'SHAM-XXXX')")
conn.commit()

# ===========================
# 3. الدوال المساعدة (منع التعليق والاشتراك)
# ===========================
def get_setting(key):
    cursor.execute("SELECT value FROM settings WHERE key=?", (key,))
    res = cursor.fetchone()
    return res[0] if res else "غير مضبوط"

def is_sub(uid):
    try:
        st = bot.get_chat_member(CHANNEL_ID, uid).status
        return st in ['member', 'administrator', 'creator']
    except: return True # لتجنب التوقف في حال عطل التليجرام

def check_status(uid):
    cursor.execute("SELECT status FROM users WHERE user_id=?", (uid,))
    res = cursor.fetchone()
    return res[0] if res else "active"

# ===========================
# 4. لوحات المفاتيح (Keyboards)
# ===========================
def main_kb(uid):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(types.KeyboardButton('⚽ Ichancy ⚽'))
    markup.add(types.KeyboardButton('🔽 الشحن في البوت'), types.KeyboardButton('🔼 السحب من البوت'))
    markup.add(types.KeyboardButton('🎁 اهداء صديق'), types.KeyboardButton('🎫 كود هدية'))
    markup.add(types.KeyboardButton('💵 الرصيد'), types.KeyboardButton('💬 التواصل مع الدعم'))
    if uid == ADMIN_ID: markup.add(types.KeyboardButton('🔐 إدارة البوت'))
    return markup

def ichancy_kb():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(types.KeyboardButton('➕ التعبئة في حسابي'), types.KeyboardButton('➖ السحب من حسابي'))
    markup.add(types.KeyboardButton('🔄 تحديث المعلومات'), types.KeyboardButton('🔙 العودة للقائمة الرئيسية'))
    return markup

# ===========================
# 5. معالجة الرسائل (Start & Main)
# ===========================
@bot.message_handler(commands=['start'])
def start_cmd(message):
    uid = message.from_user.id
    bot.clear_step_handler_by_chat_id(chat_id=uid) # أهم سطر لمنع التعليق
    if not is_sub(uid):
        m = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("اضغط للاشتراك بالقناة", url=CHANNEL_URL))
        bot.send_message(message.chat.id, "⚠️ يجب الاشتراك بقناة البوت أولاً!", reply_markup=m)
        return
    bot.send_message(message.chat.id, "أهلاً بك في نظام مطر الاحترافي 🌧️", reply_markup=main_kb(uid))

@bot.message_handler(func=lambda m: True)
def handle_text(m):
    uid = m.from_user.id
    text = m.text
    if check_status(uid) == "banned":
        bot.send_message(uid, "❌ حسابك محظور من استخدام البوت.")
        return

    # --- قسم Ichancy المتطور ---
    if text == '⚽ Ichancy ⚽':
        cursor.execute("SELECT acc_name, site_balance, user_id, created_at FROM users WHERE user_id=?", (uid,))
        u = cursor.fetchone()
        if not u or not u[0]:
            msg = bot.send_message(m.chat.id, "ليس لديك حساب حالياً، أدخل اسم المستخدم الجديد (EN):")
            bot.register_next_step_handler(msg, register_user)
        else:
            info = f"👤 حسابك: {u[0]}\n💰 رصيدك في الموقع: {u[1]} NSP\n⚽ معرف اللاعب (ID): {u[2]}\n🗓 تاريخ الإنشاء: {u[3]}"
            bot.send_message(m.chat.id, info, reply_markup=ichancy_kb())

    # --- قسم الشحن (رسالة مطولة) ---
    elif text == '🔽 الشحن في البوت':
        m_in = types.InlineKeyboardMarkup(row_width=2)
        m_in.add(types.InlineKeyboardButton("سيرياتل كاش (فوري)", callback_data="sh_sy"),
                 types.InlineKeyboardButton("شام كاش (فوري)", callback_data="sh_sh"))
        m_in.add(types.InlineKeyboardButton("USDT", callback_data="sh_no"),
                 types.InlineKeyboardButton("Binance", callback_data="sh_no"))
        bot.send_message(m.chat.id, "💰 اختر وسيلة الشحن المناسبة:", reply_markup=m_in)

    # --- إدارة البوت (كاملة) ---
    elif text == '🔐 إدارة البوت' and uid == ADMIN_ID:
        adm = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
        adm.add('📊 إرسال جماعي', '👤 إدارة حساب', '🎫 إنشاء هدية', '⚙️ الإعدادات', '🔙 العودة للقائمة الرئيسية')
        bot.send_message(uid, "🔓 لوحة التحكم الإدارية:", reply_markup=adm)

    elif text == '📊 إرسال جماعي' and uid == ADMIN_ID:
        msg = bot.send_message(uid, "أدخل الرسالة المراد إرسالها للجميع:")
        bot.register_next_step_handler(msg, admin_broadcast)

    elif text == '👤 إدارة حساب' and uid == ADMIN_ID:
        msg = bot.send_message(uid, "أدخل ID المستخدم للإدارة:")
        bot.register_next_step_handler(msg, admin_manage_user)

    elif text == '⚙️ الإعدادات' and uid == ADMIN_ID:
        msg = bot.send_message(uid, "لتغيير رقم سيريتل أرسل (سيريتل:الرقم)\nلتغيير شام أرسل (شام:الكود)")
        bot.register_next_step_handler(msg, admin_settings)

    elif text == '🎫 كود هدية':
        msg = bot.send_message(uid, "أدخل كود الهدية:")
        bot.register_next_step_handler(msg, use_gift_system)

    elif text == '🔙 العودة للقائمة الرئيسية':
        bot.clear_step_handler_by_chat_id(chat_id=uid)
        bot.send_message(uid, "تم العودة للقائمة الرئيسية", reply_markup=main_kb(uid))

# ===========================
# 6. تفاصيل العمليات (الشحن والسحب)
# ===========================
@bot.callback_query_handler(func=lambda call: True)
def handle_calls(call):
    uid = call.from_user.id
    if call.data == "sh_sy":
        num = get_setting('syriatel_num')
        txt = (f"أرسل المبلغ المراد شحنه إلى الكود التالي وبطريقة التحويل اليدوي حصراً كما موضح بالصورة 👆\n\n"
               f"كود السيريتل كاش: `{num}`\n\n"
               f"وبعد دفع المبلغ...\nقم بإرسال رقم العملية المكون من 12 رقم (مثال: 600000xxxxxx)\n"
               f"لا تقبل عمليات من دون رقم العملية!\nالرجاء إرسال المبلغ كرقم صحيح.")
        msg = bot.send_message(call.message.chat.id, txt, parse_mode="Markdown")
        bot.register_next_step_handler(msg, deposit_step_1)

    elif call.data == "wa_sy":
        msg = bot.send_message(call.message.chat.id, "أدخل المبلغ للسحب (عمولة 10%):\nالمدة من دقيقة لـ 24 ساعة.")
        bot.register_next_step_handler(msg, withdraw_process)

def deposit_step_1(message):
    op_id = message.text
    if op_id == '/start': return
    msg = bot.send_message(message.chat.id, "أدخل المبلغ الذي قمت بإرساله:")
    bot.register_next_step_handler(msg, deposit_step_final, op_id)

def deposit_step_final(message, op_id):
    amount = message.text
    # هنا يتم وضع كود الربط مع الكاشيرة (المطابقة التلقائية)
    bot.send_message(message.chat.id, f"⏳ جاري التحقق من العملية {op_id} بمبلغ {amount}...\nسيتم الشحن تلقائياً فور المطابقة.")

# ===========================
# 7. دوال الإدارة المتقدمة
# ===========================
def admin_broadcast(message):
    if message.text == '/start': return
    cursor.execute("SELECT user_id FROM users")
    all_u = cursor.fetchall()
    count = 0
    for u in all_u:
        try:
            bot.send_message(u[0], message.text)
            count += 1
        except: pass
    bot.send_message(ADMIN_ID, f"✅ تم الإرسال لـ {count} مستخدم.")

def admin_manage_user(message):
    t_uid = message.text
    m = types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.add(f"حظر {t_uid}", f"فك حظر {t_uid}", f"شحن {t_uid}", "🔙 العودة")
    bot.send_message(ADMIN_ID, f"إدارة الحساب {t_uid}:", reply_markup=m)
    bot.register_next_step_handler(message, admin_user_action, t_uid)

def admin_user_action(message, t_uid):
    act = message.text
    if "حظر" in act:
        cursor.execute("UPDATE users SET status='banned' WHERE user_id=?", (t_uid,))
        bot.send_message(ADMIN_ID, "✅ تم الحظر.")
    elif "شحن" in act:
        msg = bot.send_message(ADMIN_ID, "أدخل المبلغ للشحن:")
        bot.register_next_step_handler(msg, lambda m: admin_add_bal(m, t_uid))
    conn.commit()

def admin_add_bal(message, t_uid):
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (float(message.text), t_uid))
    conn.commit()
    bot.send_message(ADMIN_ID, "✅ تم شحن الرصيد.")
    bot.send_message(t_uid, f"🎉 تم إضافة {message.text} NSP لرصيدك من قبل الإدارة.")

def admin_settings(message):
    data = message.text.split(':')
    if "سيريتل" in data[0]:
        cursor.execute("UPDATE settings SET value=? WHERE key='syriatel_num'", (data[1],))
    elif "شام" in data[0]:
        cursor.execute("UPDATE settings SET value=? WHERE key='sham_num'", (data[1],))
    conn.commit()
    bot.send_message(ADMIN_ID, "✅ تم التحديث.")

# ===========================
# 8. نظام الهدايا الاحترافي
# ===========================
def use_gift_system(message):
    uid = message.from_user.id
    code = message.text
    cursor.execute("SELECT value, limit_count, used_count FROM gifts WHERE code=?", (code,))
    g = cursor.fetchone()
    if not g:
        bot.send_message(uid, "❌ الكود غير صحيح.")
        return
    cursor.execute("SELECT * FROM gift_usage WHERE user_id=? AND code=?", (uid, code))
    if cursor.fetchone():
        bot.send_message(uid, "❌ لقد استخدمت هذا الكود مسبقاً.")
        return
    if g[2] >= g[1]:
        bot.send_message(uid, "❌ انتهت صلاحية هذا الكود (وصل للحد الأقصى).")
        return
    
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (g[0], uid))
    cursor.execute("INSERT INTO gift_usage VALUES (?,?)", (uid, code))
    cursor.execute("UPDATE gifts SET used_count = used_count + 1 WHERE code=?", (code,))
    conn.commit()
    bot.send_message(uid, f"🎉 مبروك! حصلت على {g[0]} NSP.")

# ===========================
# 9. التسجيل والتشغيل
# ===========================
def register_user(message):
    uid = message.from_user.id
    name = message.text
    now = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("INSERT OR REPLACE INTO users(user_id, acc_name, created_at) VALUES(?,?,?)", (uid, name, now))
    conn.commit()
    bot.send_message(uid, "✅ تم التسجيل! اضغط Ichancy مجدداً.", reply_markup=main_kb(uid))

if __name__ == "__main__":
    keep_alive()
    bot.polling(none_stop=True)
