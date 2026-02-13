import os
from telebot import TeleBot, types

# =========================
# CONFIGURATIONS
# =========================
TOKEN = '8581064983:AAE43_TNTx8Fnww6-vs8MVlb97ahTzCvNhM'  # توكن البوت جاهز
bot = TeleBot(TOKEN)

# إعدادات افتراضية قابلة للتغيير من الإدمن
ADMIN_ID = 846938470  # ضع ID حسابك هنا
SYRIATEL_CASH_NUM = "09xxxxxxxx"
TRADER_CODE = "12345"
SHAM_CASH_ADDRESS = "SHAM123456"
USDT_BINANCE_ADDR = "Txxxxxxxxxxxxxxx"
WITHDRAW_COMMISSION = 0.10  # عمولة 10%
REFERRAL_PERCENT = 0.10    # عمولة الوكيل 10%
MAINTENANCE_MODE = False   # وضع الصيانة

# =========================
# DATABASE SIMULATION
# =========================
users = {}  # user_id: {'balance': float, 'pending_withdraw': float, 'referrer': id, 'pending_commission': float}
withdraw_requests = []  # قائمة طلبات السحب
referrals = {}  # user_id: [list of referred user_ids]

# =========================
# KEYBOARDS
# =========================
def main_kb():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add('⚽ ايشانسي | Ichancy', '💰 حسابي')
    markup.add('➕ شحن رصيد', '➖ سحب أرباح')
    markup.add('📢 القناة الرسمية', '🛠 الدعم الفني')
    markup.add('انضم كوكيل معتمد')
    return markup

def admin_kb():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add('📊 إحصائيات البوت', '➕ تعديل بيانات التحويل')
    markup.add('💰 تعديل الأسعار وال
