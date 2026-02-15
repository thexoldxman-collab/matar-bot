import telebot
from telebot import types
from flask import Flask
from threading import Thread
import os
import sqlite3
from datetime import datetime

# ==========================================
# 1. إعدادات البوت والسيرفر الأساسية
# ==========================================
TOKEN = os.environ.get('TOKEN')
bot = telebot.TeleBot(TOKEN)
ADMIN_ID = 846938470  
CHANNEL_ID = "@Matar_ichancy"
CHANNEL_URL = "https://t.me/Matar_ichancy"

app = Flask('')

@app.route('/')
def home():
    # رسالة الحالة للسيرفر لضمان العمل على Render
    return "Matar Pro System: Status Online - Port Active"

def run_server():
    # حل مشكلة Port 10000 وتجنب الـ Conflict
    port = int(os.environ.get("PORT", 10000))
    try:
        app.run(host='0.0.0.0', port=port)
    except Exception as e:
        print(f"Server Startup Error: {e}")

def keep_alive():
    # تشغيل السيرفر في خلفية البوت
    t = Thread(target=run_server)
    t.daemon = True
    t.start()

# ==========================================
# 2. نظام قاعدة البيانات (التفصيلي)
# ==========================================
def setup_database():
    conn = sqlite3.connect("matar_pro_v301.db", check_same_thread=False)
    cursor = conn.cursor()
    
    # جدول المستخدمين الشامل
    cursor.execute("""CREATE TABLE IF NOT EXISTS users(
        user_id INTEGER PRIMARY KEY, 
        acc_name TEXT, 
        balance REAL DEFAULT 0, 
        site_balance REAL DEFAULT 0, 
        status TEXT DEFAULT 'active', 
        created_at TEXT)""")

    # جدول الأكواد والهدايا
    cursor.execute("""CREATE TABLE IF NOT EXISTS gifts(
        code TEXT PRIMARY KEY, 
        value REAL, 
        limit_count INTEGER, 
        used_count INTEGER DEFAULT 0)""")

    # سجل استخدام الهدايا لمنع التكرار
    cursor.execute("CREATE TABLE IF NOT EXISTS gift_usage(user_id INTEGER, code TEXT)")
    
    # جدول الإعدادات العامة (أرقام الكاش)
    cursor.execute("CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT)")
    
    # تعبئة البيانات الافتراضية
    cursor.execute("INSERT OR IGNORE INTO settings VALUES ('syriatel_num', '74205110')")
    cursor.execute("INSERT OR IGNORE INTO settings VALUES ('sham_num', 'SHAM-12345')")
    
    conn.commit()
    return conn, cursor

conn, cursor = setup_database()

# ==========================================
# 3. محرك التحقق والوظائف المساعدة
# ==========================================
def check_subscription(uid):
    # التحقق من الاشتراك الإجباري في القناة
    try:
        member = bot.get_chat_member(CHANNEL_ID, uid)
        return member.status in ['member', 'administrator', 'creator']
    except:
        return False

def get_db_setting(key_name):
    # جلب الإعدادات من القاعدة
    cursor.execute("SELECT value FROM settings WHERE key=?", (key_name,))
    result = cursor.fetchone()
    return result[0] if result else "غير متوفر"

def reset_user_steps(uid):
    # حل مشكلة التعليق: تصفير أي خطوة سابقة
    bot.clear_step_handler_by_chat_id(chat_id=uid)

# ==========================================
# 4. بناء القوائم (Keyboards)
# ==========================================
def get_main_keyboard(uid):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(types.KeyboardButton('⚽ Ichancy ⚽'))
    markup.add(types.KeyboardButton('🔽 الشحن في البوت'), types.KeyboardButton('🔼 السحب من البوت'))
    markup.add(types.KeyboardButton('🎁 اهداء صديق'), types.KeyboardButton('🎫 كود هدية'))
    markup.add(types.KeyboardButton('💵 الرصيد'), types.KeyboardButton('💬 التواصل مع الدعم'))
    if uid == ADMIN_ID:
        markup.add(types.KeyboardButton('🔐 إدارة البوت'))
    return markup

def get_ichancy_keyboard():
    # قائمة Ichancy الفرعية
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(types.KeyboardButton('💰 معلومات الحساب 💰'))
    markup.add(types.KeyboardButton('➕ التعبئة في حسابي'), types.KeyboardButton('➖ السحب من حسابي'))
    markup.add(types.KeyboardButton('🔄 تحديث المعلومات'))
    markup.add(types.KeyboardButton('🔙 العودة للقائمة الرئيسية'))
    return markup

# ==========================================
# 5. معالجة الأوامر والرسائل الترحيبية
# ==========================================
@bot.message_handler(commands=['start'])
def handle_start(message):
    uid = message.from_user.id
    reset_user_steps(uid)
    
    # فحص الاشتراك قبل الترحيب
    if not check_subscription(uid):
        btn = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("انضم للقناة لتفعيل البوت ✅", url=CHANNEL_URL))
        bot.send_message(message.chat.id, "⚠️ توقف! البوت يتطلب الاشتراك في القناة الرسمية أولاً.", reply_markup=btn)
        return
        
    welcome_text = (f"🎯 أهلاً بك في نظام مطر (Matar) المتكامل 🌧️\n\n"
                    f"الخيار الأسرع والأكثر أماناً لشحن وسحب رصيد Ichancy في سوريا.\n"
                    f"استخدم الأزرار بالأسفل لبدء العمليات.")
    bot.send_message(message.chat.id, welcome_text, reply_markup=get_main_keyboard(uid))

@bot.message_handler(func=lambda m: True)
def main_router(m):
    uid = m.from_user.id
    text = m.text
    
    # فحص الحظر
    cursor.execute("SELECT status FROM users WHERE user_id=?", (uid,))
    user_status = cursor.fetchone()
    if user_status and user_status[0] == 'banned':
        bot.send_message(uid, "❌ نعتذر، حسابك محظور من استخدام النظام.")
        return

    # --- منطق قسم Ichancy ---
    if text == '⚽ Ichancy ⚽':
        reset_user_steps(uid)
        cursor.execute("SELECT acc_name FROM users WHERE user_id=?", (uid,))
        user_data = cursor.fetchone()
        
        if not user_data or not user_data[0]:
            prompt = bot.send_message(m.chat.id, "لم نجد حساباً مسجلاً.\nيرجى كتابة اسم المستخدم (باللغة الإنجليزية) لإنشاء حسابك:")
            bot.register_next_step_handler(prompt, process_registration)
        else:
            bot.send_message(m.chat.id, "⚽ لوحة تحكم إيشانسي (Matar Mode).\nأقل مبلغ للتعامل هو 100 ليرة.", reply_markup=get_ichancy_keyboard())

    # --- بطاقة معلومات الحساب (التفصيلية كما في الصورة) ---
    elif text == '💰 معلومات الحساب 💰':
        reset_user_steps(uid)
        cursor.execute("SELECT acc_name, site_balance, balance, user_id, created_at FROM users WHERE user_id=?", (uid,))
        u = cursor.fetchone()
        if u:
            card = (f"🌐 اسم حسابك على الموقع : {u[0]}\n"
                    f"🌐 رصيدك على الموقع : {u[1]} NSP\n\n"
                    f"🤖 اسم حسابك على البوت : {m.from_user.first_name}\n"
                    f"🤖 رصيدك على البوت : {u[2]} NSP\n\n"
                    f"⚽ معرف اللاعب: {u[3]}\n"
                    f"🗓 تاريخ إنشاء الحساب: {u[4]}")
            bot.send_message(m.chat.id, "🎰") # أيقونة الماكينة المطلوبة
            bot.send_message(m.chat.id, card, reply_markup=get_ichancy_keyboard())

    elif text == '🔙 العودة للقائمة الرئيسية':
        reset_user_steps(uid)
        bot.send_message(uid, "تم العودة للقائمة الرئيسية 🌧️", reply_markup=get_main_keyboard(uid))

    # --- نظام الشحن ---
    elif text == '🔽 الشحن في البوت':
        reset_user_steps(uid)
        inline_kb = types.InlineKeyboardMarkup(row_width=2)
        inline_kb.add(types.InlineKeyboardButton("سيرياتل كاش 📱", callback_data="pay_syria"),
                      types.InlineKeyboardButton("شام كاش 💳", callback_data="pay_sham"))
        bot.send_message(m.chat.id, "💰 اختر وسيلة الشحن التي تفضلها:", reply_markup=inline_kb)

    # --- لوحة الإدارة للأدمن ---
    elif text == '🔐 إدارة البوت' and uid == ADMIN_ID:
        admin_kb = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
        admin_kb.add('📊 إرسال جماعي', '👤 إدارة الحسابات', '🎫 توليد كود هدية', '🔙 العودة للقائمة الرئيسية')
        bot.send_message(uid, "🔓 أهلاً بك يا مدير النظام. تفضل بالتحكم:", reply_markup=admin_kb)

    elif text == '📊 إرسال جماعي' and uid == ADMIN_ID:
        msg = bot.send_message(uid, "اكتب الرسالة التي تود إرسالها لجميع الأعضاء:")
        bot.register_next_step_handler(msg, start_broadcast)

    elif text == '🎫 كود هدية':
        msg = bot.send_message(uid, "يرجى إدخال الكود للحصول على المكافأة:")
        bot.register_next_step_handler(msg, redeem_gift_code)

# ==========================================
# 6. وظائف العمليات (التسجيل والشحن)
# ==========================================
def process_registration(message):
    uid = message.from_user.id
    username_input = message.text
    if len(username_input) < 3:
        bot.send_message(uid, "❌ الاسم قصير جداً. أعد المحاولة من زر إيشانسي.")
        return
    
    reg_date = datetime.now().strftime("%d-%m-%Y %H:%M")
    cursor.execute("INSERT OR REPLACE INTO users(user_id, acc_name, created_at) VALUES(?,?,?)", (uid, username_input, reg_date))
    conn.commit()
    bot.send_message(uid, "✅ تم تسجيل حسابك بنجاح! يمكنك الآن استخدام خدماتنا.", reply_markup=get_main_keyboard(uid))

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    uid = call.from_user.id
    if call.data == "pay_syria":
        num = get_db_setting('syriatel_num')
        instr = (f"يرجى تحويل المبلغ يدوياً للكود التالي: `{num}`\n\n"
                 f"بعد التحويل، أرسل رقم العملية المكون من 12 خانة.\n"
                 f"⚠️ لا ترسل أي شيء آخر غير رقم العملية.")
        msg = bot.send_message(call.message.chat.id, instr, parse_mode="Markdown")
        bot.register_next_step_handler(msg, capture_transaction_id)

def capture_transaction_id(message):
    trans_id = message.text
    if len(trans_id) < 8:
        bot.send_message(message.chat.id, "❌ رقم العملية غير منطقي. حاول مجدداً.")
        return
    msg = bot.send_message(message.chat.id, "✅ رقم العملية مستلم. الآن أدخل المبلغ المحول:")
    bot.register_next_step_handler(msg, finalize_deposit, trans_id)

def finalize_deposit(message, tid):
    amount = message.text
    bot.send_message(message.chat.id, f"⏳ جاري تدقيق العملية `{tid}` بمبلغ `{amount}`...\nستصلك رسالة عند التأكيد.")

# ==========================================
# 7. وظائف الإدارة المتقدمة
# ==========================================
def start_broadcast(message):
    cursor.execute("SELECT user_id FROM users")
    all_users = cursor.fetchall()
    sent_count = 0
    for user in all_users:
        try:
            bot.send_message(user[0], message.text)
            sent_count += 1
        except: continue
    bot.send_message(ADMIN_ID, f"✅ تم الإرسال بنجاح لـ {sent_count} مستخدم.")

def redeem_gift_code(message):
    uid = message.from_user.id
    code = message.text
    cursor.execute("SELECT value, limit_count, used_count FROM gifts WHERE code=?", (code,))
    gift = cursor.fetchone()
    
    if gift:
        cursor.execute("SELECT * FROM gift_usage WHERE user_id=? AND code=?", (uid, code))
        if cursor.fetchone():
            bot.send_message(uid, "❌ لقد حصلت على هذه الهدية سابقاً!")
        elif gift[2] < gift[1]:
            cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (gift[0], uid))
            cursor.execute("UPDATE gifts SET used_count = used_count + 1 WHERE code=?", (code,))
            cursor.execute("INSERT INTO gift_usage VALUES (?,?)", (uid, code))
            conn.commit()
            bot.send_message(uid, f"🎉 مبروك! تم إضافة {gift[0]} ليرة لرصيدك.")
        else:
            bot.send_message(uid, "❌ نعتذر، انتهت صلاحية هذا الكود.")
    else:
        bot.send_message(uid, "❌ الكود غير صحيح أو غير موجود.")

# ==========================================
# 8. حلقة التشغيل والحماية (Render Stable)
# ==========================================
if __name__ == "__main__":
    # تشغيل السيرفر الجانبي
    keep_alive()
    
    # حل مشكلة Conflict 409 القديمة
    print("Matar Bot is firing up...")
    try:
        # استخدام skip_pending لتجاهل أي رسائل معلقة تسبب تعليق البوت
        bot.polling(none_stop=True, skip_pending=True, interval=0, timeout=40)
    except Exception as e:
        print(f"Polling Crashed: {e}")
    
