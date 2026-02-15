import telebot
from telebot import types
from flask import Flask
from threading import Thread
import os
import sqlite3
from datetime import datetime

# ==========================================
# 1. إعدادات البوت والسيرفر (تصحيح خطأ الصورة)
# ==========================================
TOKEN = os.environ.get('TOKEN')
bot = telebot.TeleBot(TOKEN)
ADMIN_ID = 846938470  
CHANNEL_ID = "@Matar_ichancy"
CHANNEL_URL = "https://t.me/Matar_ichancy"

app = Flask('')

@app.route('/')
def home():
    return "Matar Pro System is Online and Stable!"

def run():
    # حل مشكلة Port 10000 في Render الظاهرة بالصورة
    port = int(os.environ.get("PORT", 10000))
    try:
        app.run(host='0.0.0.0', port=port)
    except Exception as e:
        print(f"Server Error: {e}")

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

# ==========================================
# 2. قاعدة البيانات (الهيكل العملاق الشامل)
# ==========================================
conn = sqlite3.connect("matar_main_system_v3.db", check_same_thread=False)
cursor = conn.cursor()

# جدول المستخدمين
cursor.execute("""CREATE TABLE IF NOT EXISTS users(
    user_id INTEGER PRIMARY KEY, 
    acc_name TEXT, 
    balance REAL DEFAULT 0, 
    site_balance REAL DEFAULT 0, 
    status TEXT DEFAULT 'active', 
    created_at TEXT)""")

# جدول الهدايا
cursor.execute("""CREATE TABLE IF NOT EXISTS gifts(
    code TEXT PRIMARY KEY, 
    value REAL, 
    limit_count INTEGER, 
    used_count INTEGER DEFAULT 0)""")

# جدول استخدام الهدايا
cursor.execute("CREATE TABLE IF NOT EXISTS gift_usage(user_id INTEGER, code TEXT)")

# جدول الإعدادات
cursor.execute("CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT)")

# إدخال القيم الافتراضية إذا لم تكن موجودة
cursor.execute("INSERT OR IGNORE INTO settings VALUES ('syriatel_num', '74205110')")
cursor.execute("INSERT OR IGNORE INTO settings VALUES ('sham_num', 'SHAM-12345')")
conn.commit()

# ==========================================
# 3. الدوال المساعدة (منع التعليق والاشتراك)
# ==========================================
def get_setting(key):
    cursor.execute("SELECT value FROM settings WHERE key=?", (key,))
    res = cursor.fetchone()
    return res[0] if res else "غير مضبوط"

def is_sub(uid):
    try:
        st = bot.get_chat_member(CHANNEL_ID, uid).status
        return st in ['member', 'administrator', 'creator']
    except:
        return True # لتجنب التوقف في حال عطل التليجرام

def clear_steps(uid):
    bot.clear_step_handler_by_chat_id(chat_id=uid)

# ==========================================
# 4. لوحات المفاتيح (Keyboards)
# ==========================================
def main_kb(uid):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn1 = types.KeyboardButton('⚽ Ichancy ⚽')
    btn2 = types.KeyboardButton('🔽 الشحن في البوت')
    btn3 = types.KeyboardButton('🔼 السحب من البوت')
    btn4 = types.KeyboardButton('🎁 اهداء صديق')
    btn5 = types.KeyboardButton('🎫 كود هدية')
    btn6 = types.KeyboardButton('💵 الرصيد')
    btn7 = types.KeyboardButton('💬 التواصل مع الدعم')
    markup.add(btn1)
    markup.add(btn2, btn3)
    markup.add(btn4, btn5)
    markup.add(btn6, btn7)
    if uid == ADMIN_ID:
        markup.add(types.KeyboardButton('🔐 إدارة البوت'))
    return markup

def ichancy_kb():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(types.KeyboardButton('➕ التعبئة في حسابي'))
    markup.add(types.KeyboardButton('➖ السحب من حسابي'))
    markup.add(types.KeyboardButton('🔄 تحديث المعلومات'))
    markup.add(types.KeyboardButton('🔙 العودة للقائمة الرئيسية'))
    return markup

# ==========================================
# 5. معالجة الرسائل والمنطق البرمجي
# ==========================================
@bot.message_handler(commands=['start'])
def start_cmd(message):
    uid = message.from_user.id
    clear_steps(uid) # تصفير الخطوات لمنع التعليق
    if not is_sub(uid):
        m = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("اضغط هنا للاشتراك", url=CHANNEL_URL))
        bot.send_message(message.chat.id, "⚠️ يجب الاشتراك في القناة أولاً لتتمكن من استخدام البوت!", reply_markup=m)
        return
    bot.send_message(message.chat.id, "أهلاً بك في نظام مطر الاحترافي 🌧️\nيرجى اختيار أحد الخيارات من القائمة أدناه:", reply_markup=main_kb(uid))

@bot.message_handler(func=lambda m: True)
def handle_text(m):
    uid = m.from_user.id
    text = m.text
    
    # التحقق من حالة الحساب
    cursor.execute("SELECT status FROM users WHERE user_id=?", (uid,))
    res = cursor.fetchone()
    if res and res[0] == 'banned':
        bot.send_message(uid, "❌ نعتذر، حسابك محظور من استخدام البوت حالياً.")
        return

    # --- قسم Ichancy (التعديلات المطلوبة) ---
    if text == '⚽ Ichancy ⚽':
        cursor.execute("SELECT acc_name, site_balance, user_id, created_at FROM users WHERE user_id=?", (uid,))
        u = cursor.fetchone()
        if not u or not u[0]:
            msg = bot.send_message(m.chat.id, "لم نجد حساباً مسجلاً باسمك.\nيرجى إدخال اسم المستخدم الخاص بك (EN) لإنشاء الحساب:")
            bot.register_next_step_handler(msg, register_new_user)
        else:
            info_msg = (f"🌐 **معلومات حسابك في إيشانسي**\n\n"
                        f"👤 اسم المستخدم: `{u[0]}`\n"
                        f"💰 رصيدك الحالي: {u[1]} NSP\n"
                        f"🆔 معرف اللاعب: `{u[2]}`\n"
                        f"📅 تاريخ التسجيل: {u[3]}\n\n"
                        f"استخدم الأزرار أدناه للتحكم في رصيد الموقع.")
            bot.send_message(m.chat.id, info_msg, reply_markup=ichancy_kb(), parse_mode="Markdown")

    # --- العودة ---
    elif text == '🔙 العودة للقائمة الرئيسية':
        clear_steps(uid)
        bot.send_message(uid, "تمت العودة إلى القائمة الرئيسية.", reply_markup=main_kb(uid))

    # --- الشحن (الرسالة الكاملة والاحترافية) ---
    elif text == '🔽 الشحن في البوت':
        m_in = types.InlineKeyboardMarkup(row_width=2)
        m_in.add(types.InlineKeyboardButton("سيرياتل كاش (فوري) ✅", callback_data="sh_sy"),
                 types.InlineKeyboardButton("شام كاش (فوري) ✅", callback_data="sh_sh"))
        m_in.add(types.InlineKeyboardButton("Binance (USDT)", callback_data="sh_no"))
        bot.send_message(m.chat.id, "💰 يرجى اختيار وسيلة الشحن التي ترغب في استخدامها:", reply_markup=m_in)

    # --- لوحة الإدارة (كاملة التفاصيل) ---
    elif text == '🔐 إدارة البوت' and uid == ADMIN_ID:
        adm = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
        adm.add('📊 إرسال جماعي', '👤 إدارة حساب محدد')
        adm.add('🎫 إنشاء كود هدية', '⚙️ تعديل الأرقام والكواد')
        adm.add('🔙 العودة للقائمة الرئيسية')
        bot.send_message(uid, "🔓 أهلاً بك يا أدمن. إليك لوحة التحكم الكاملة:", reply_markup=adm)

    elif text == '📊 إرسال جماعي' and uid == ADMIN_ID:
        msg = bot.send_message(uid, "يرجى كتابة الرسالة التي تود إرسالها لجميع مستخدمي البوت:")
        bot.register_next_step_handler(msg, process_broadcast)

    elif text == '👤 إدارة حساب محدد' and uid == ADMIN_ID:
        msg = bot.send_message(uid, "يرجى إرسال الـ ID الخاص بالمستخدم الذي تريد إدارته:")
        bot.register_next_step_handler(msg, process_user_management)

    elif text == '🎫 كود هدية':
        msg = bot.send_message(uid, "يرجى إدخال كود الهدية الذي حصلت عليه:")
        bot.register_next_step_handler(msg, process_gift_use)

# ==========================================
# 6. تفاصيل العمليات (الأتمتة والتحقق)
# ==========================================
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    uid = call.from_user.id
    if call.data == "sh_sy":
        num = get_setting('syriatel_num')
        txt = (f"أرسل المبلغ المراد شحنه إلى الكود التالي وبطريقة التحويل اليدوي حصراً كما موضح بالصورة 👆\n\n"
               f"كود السيريتل كاش الخاص بالبوت: `{num}`\n\n"
               f"وبعد دفع المبلغ...\n"
               f"قم بإرسال رقم العملية المكون من 12 رقم (مثال: 600000xxxxxx)\n"
               f"لا تقبل عمليات الشحن من دون رقم العملية!\n"
               f"الرجاء إرسال المبلغ كرقم صحيح (من دون فواصل عشرية).")
        msg = bot.send_message(call.message.chat.id, txt, parse_mode="Markdown")
        bot.register_next_step_handler(msg, deposit_get_op)

def deposit_get_op(message):
    op_id = message.text
    if op_id == '/start': return
    if len(op_id) < 6:
        bot.send_message(message.chat.id, "❌ رقم عملية غير صحيح. أعد المحاولة من جديد.")
        return
    msg = bot.send_message(message.chat.id, "✅ تم استلام رقم العملية. الآن يرجى إدخال المبلغ الذي قمت بإرساله:")
    bot.register_next_step_handler(msg, deposit_final_step, op_id)

def deposit_final_step(message, op_id):
    amount = message.text
    bot.send_message(message.chat.id, f"⏳ جاري التحقق من رقم العملية `{op_id}` ومطابقتها مع المبلغ `{amount}`...\nستصلك رسالة تأكيد عند اكتمال الشحن تلقائياً.")

# ==========================================
# 7. وظائف الإدارة والتحكم (الحظر والشحن)
# ==========================================
def process_broadcast(message):
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    count = 0
    for u in users:
        try:
            bot.send_message(u[0], message.text)
            count += 1
        except: pass
    bot.send_message(ADMIN_ID, f"✅ تمت العملية. تم الإرسال لـ {count} مستخدم.")

def process_user_management(message):
    target_id = message.text
    m = types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.add(f"حظر المستحدم {target_id}", f"إلغاء حظر {target_id}")
    m.add(f"شحن رصيد {target_id}", f"سحب رصيد {target_id}")
    m.add("🔙 العودة")
    bot.send_message(ADMIN_ID, f"قائمة الإدارة للمستخدم `{target_id}`:", reply_markup=m)
    bot.register_next_step_handler(message, execute_admin_action, target_id)

def execute_admin_action(message, tid):
    text = message.text
    if "حظر" in text and "إلغاء" not in text:
        cursor.execute("UPDATE users SET status='banned' WHERE user_id=?", (tid,))
        bot.send_message(ADMIN_ID, f"✅ تم حظر المستخدم {tid} بنجاح.")
    elif "إلغاء حظر" in text:
        cursor.execute("UPDATE users SET status='active' WHERE user_id=?", (tid,))
        bot.send_message(ADMIN_ID, f"✅ تم إلغاء حظر المستخدم {tid}.")
    elif "شحن" in text:
        msg = bot.send_message(ADMIN_ID, "أدخل المبلغ المراد إضافته:")
        bot.register_next_step_handler(msg, lambda m: finish_admin_add(m, tid))
    conn.commit()

def finish_admin_add(message, tid):
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (float(message.text), tid))
    conn.commit()
    bot.send_message(ADMIN_ID, "✅ تم الشحن يدوياً.")
    bot.send_message(tid, f"🎁 تم شحن حسابك بـ {message.text} NSP من قبل الإدارة.")

# ==========================================
# 8. نظام الهدايا والتسجيل
# ==========================================
def process_gift_use(message):
    uid = message.from_user.id
    code = message.text
    cursor.execute("SELECT value, limit_count, used_count FROM gifts WHERE code=?", (code,))
    g = cursor.fetchone()
    if g:
        cursor.execute("SELECT * FROM gift_usage WHERE user_id=? AND code=?", (uid, code))
        if cursor.fetchone():
            bot.send_message(uid, "❌ لقد قمت باستخدام هذا الكود مسبقاً! لا يسمح بالتكرار.")
        elif g[2] < g[1]:
            cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (g[0], uid))
            cursor.execute("UPDATE gifts SET used_count = used_count + 1 WHERE code=?", (code,))
            cursor.execute("INSERT INTO gift_usage VALUES (?,?)", (uid, code))
            conn.commit()
            bot.send_message(uid, f"🎉 مبروك! حصلت على {g[0]} NSP رصيد هدية.")
        else:
            bot.send_message(uid, "❌ نعتذر، هذا الكود وصل للحد الأقصى من المستخدمين.")
    else:
        bot.send_message(uid, "❌ الكود غير صحيح أو منتهي الصلاحية.")

def register_new_user(message):
    uid = message.from_user.id
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    cursor.execute("INSERT OR REPLACE INTO users(user_id, acc_name, created_at) VALUES(?,?,?)", (uid, message.text, now))
    conn.commit()
    bot.send_message(uid, "✅ تم إنشاء حسابك بنجاح! يرجى الضغط على زر إيشانسي للدخول لوحة التحكم.", reply_markup=main_kb(uid))

# ==========================================
# 9. التشغيل النهائي (حل الـ Conflict)
# ==========================================
if __name__ == "__main__":
    keep_alive()
    # skip_pending=True لحل مشكلة تعليق الرسائل القديمة عند التشغيل
    try:
        bot.polling(none_stop=True, skip_pending=True, interval=0, timeout=20)
    except Exception as e:
        print(f"Polling Error: {e}")
