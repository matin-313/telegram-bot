# ======================================================
# IMPORTS
# ======================================================


import os
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler
import logging
from datetime import datetime, time
from datetime import date, datetime, time, timedelta
import jdatetime 
from telegram import (
    Update,
    KeyboardButton,
    ReplyKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)
# ======================================================
# CONFIG
# ======================================================
BOT_TOKEN = os.getenv("BOT_TOKEN")

SUPER_ADMINS = [6807376124]
VIEWER_ADMINS = [22222222]


REPORT_TIME = time(23, 59)

# ======================================================
# IN-MEMORY GROUP LISTS
# ======================================================
FUTSAL_GROUPS = {chr(i): set() for i in range(ord("A"), ord("K"))}  # A تا J


# ======================================================
# RAM PLAYERS (بازیکن‌ها فقط در حافظه)
# ======================================================
RAM_PLAYERS = {
    "futsal": {g: {} for g in "ABCDEFGHIJ"},   # group -> {phone: name}
    "basketball": {},                         # phone -> name
    "volleyball": {}                          # phone -> name
}

# ✅ این مقداردهی اولیه را در ابتدای main() اضافه کن
def initialize_ram():
    """مقداردهی اولیه ساختارهای RAM"""
    global RAM_PLAYERS, RAM_TIMES, RAM_REGISTRATIONS
    
    # بازیکنان
    RAM_PLAYERS = {
        "futsal": {g: {} for g in "ABCDEFGHIJ"},
        "basketball": {},
        "volleyball": {}
    }
    
    # تایم‌ها
    RAM_TIMES = {
        "futsal": {g: [] for g in "ABCDEFGHIJ"},
        "basketball": [],
        "volleyball": []
    }
    
    # ثبت‌نام‌ها
    RAM_REGISTRATIONS = {
        "futsal": {g: {} for g in "ABCDEFGHIJ"},
        "basketball": {},
        "volleyball": {}
    }

# ======================================================
# RAM REGISTRATIONS (ثبت نام فقط در حافظه)
# ======================================================
RAM_REGISTRATIONS = {
    "futsal": {g: {} for g in "ABCDEFGHIJ"},  # group -> {time_id: {phone: name}}
    "basketball": {},  # time_id -> {phone: name}
    "volleyball": {}   # time_id -> {phone: name}
}

# ======================================================
# RAM TIMES (تایم‌ها فقط در حافظه)
# ======================================================

RAM_TIMES = {
    "futsal": {g: [] for g in "ABCDEFGHIJ"},  # group -> list of times with date
    "basketball": [],
    "volleyball": []
}

# هر تایم به این شکل ذخیره میشه:
# {
#     "date": "2026-02-11",
#     "start": "18:00",
#     "end": "19:00", 
#     "cap": 15,
#     "date_obj": date(2026, 2, 11)  # برای مقایسه راحت‌تر
# }


# ======================================================
# LOGGING
# ======================================================
logging.basicConfig(level=logging.INFO)


# ======================================================
# normalize phone
# ======================================================
def normalize_phone(raw: str) -> str:
    """
    تبدیل شماره‌ها به فرمت یکنواختِ دیتابیس:
    - حذف فاصله، - و + 
    - تبدیل 989... به 09...
    - اگر شماره با 9 و 10 رقم بود، به 0... تبدیل می‌کنیم
    """
    if not raw:
        return raw
    p = "".join(ch for ch in raw if ch.isdigit())
    # اگر با 98 و 12 رقم باشد -> 0 + باقی
    if p.startswith("98") and len(p) == 12:
        p = "0" + p[2:]
    # اگر با 9 و 10 رقم باشد -> 0 + ...
    if len(p) == 10 and p.startswith("9"):
        p = "0" + p
    return p

# ======================================================
# UTILS
# ======================================================
def is_super(uid): return uid in SUPER_ADMINS
def is_admin(uid): return uid in SUPER_ADMINS or uid in VIEWER_ADMINS


# ======================================================
# DATE UTILS
# ======================================================
def get_today_date():
    """تاریخ امروز به میلادی"""
    return date.today().isoformat()

def get_today_jalali():
    """تاریخ امروز به شمسی برای نمایش"""
    return jdatetime.date.today().strftime("%Y/%m/%d")

def parse_date(date_str):
    """تبدیل رشته تاریخ به آبجکت date"""
    try:
        # تلاش برای فرمت میلادی
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except:
        try:
            # تلاش برای فرمت شمسی
            j_date = jdatetime.datetime.strptime(date_str, "%Y/%m/%d").date()
            return j_date.togregorian()
        except:
            return None

def is_time_expired(time_dict):
    """بررسی اینکه تایم منقضی شده یا نه"""
    time_date = time_dict.get("date_obj")
    if not time_date:
        return True
    
    today = date.today()
    return time_date < today  # اگر تاریخش گذشته باشه

# ======================================================
# START
# ======================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ["⚽ فوتسال", "🏀 بسکتبال", "🏐 والیبال"]
    ]

    await update.message.reply_text(
        "🏟 لطفاً رشته مورد نظر را انتخاب کنید:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True
        )
    )


# ======================================================
# REGISTER TIME
# ======================================================
async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ─────────── sanity check ───────────
    if "sport" not in context.user_data or "time_index" not in context.user_data:
        await update.message.reply_text("❌ لطفاً دوباره از ابتدا ثبت‌نام کنید")
        context.user_data.clear()
        return

    sport = context.user_data["sport"]
    idx = context.user_data["time_index"]
    group = context.user_data.get("group")

    # ─────────── phone normalize ───────────
    raw_phone = update.message.text.strip()
    phone = normalize_phone(raw_phone)
    
    # ✅ لاگ برای دیباگ
    print(f"\n🟢 تلاش برای ثبت‌نام:")
    print(f"   ورزش: {sport}")
    print(f"   گروه: {group}")
    print(f"   شماره وارد شده: {raw_phone}")
    print(f"   شماره نرمالایز شده: {phone}")

    if not phone.startswith("09") or len(phone) != 11:
        await update.message.reply_text("❌ شماره نامعتبر است\nمثال: 09123456789")
        return

    # ─────────── time validation ───────────
    if sport == "futsal":
        if not group or group not in RAM_TIMES["futsal"]:
            await update.message.reply_text("❌ خطا در گروه فوتسال")
            context.user_data.clear()
            return

        if idx >= len(RAM_TIMES["futsal"][group]):
            await update.message.reply_text("❌ تایم فوتسال نامعتبر است")
            context.user_data.clear()
            return

        slot = RAM_TIMES["futsal"][group][idx]
        registrations = RAM_REGISTRATIONS["futsal"][group].setdefault(idx, {})

    else:
        if idx >= len(RAM_TIMES[sport]):
            await update.message.reply_text("❌ تایم نامعتبر است")
            context.user_data.clear()
            return

        slot = RAM_TIMES[sport][idx]
        registrations = RAM_REGISTRATIONS[sport].setdefault(idx, {})

    capacity = slot.get("cap", 0)

    # ─────────── بررسی بازیکن ───────────
    if sport == "futsal":
        # فوتسال: بررسی در گروه‌ها
        found_player = False
        found_name = None
        found_group = None
        
        # ✅ لاگ برای دیدن محتوای RAM_PLAYERS فوتسال
        print(f"   بررسی فوتسال - گروه هدف: {group}")
        for g in "ABCDEFGHIJ":
            if RAM_PLAYERS["futsal"][g]:
                print(f"     گروه {g}: {list(RAM_PLAYERS['futsal'][g].keys())}")
        
        # اول در همان گروه جستجو کن
        if phone in RAM_PLAYERS["futsal"][group]:
            found_player = True
            found_name = RAM_PLAYERS["futsal"][group][phone]
            found_group = group
            print(f"   ✅ بازیکن در گروه {group} پیدا شد: {found_name}")
        
        # اگر در همان گروه نبود، بقیه گروه‌ها رو چک کن
        else:
            for g in "ABCDEFGHIJ":
                if phone in RAM_PLAYERS["futsal"][g]:
                    found_player = True
                    found_name = RAM_PLAYERS["futsal"][g][phone]
                    found_group = g
                    print(f"   ⚠️ بازیکن در گروه {g} پیدا شد (نه گروه هدف)")
                    break
        
        # اگر اصلاً پیدا نشد
        if not found_player:
            print(f"   ❌ بازیکن با شماره {phone} در هیچ گروه فوتسال پیدا نشد")
            await update.message.reply_text("❌ شما در لیست فوتسال نیستید")
            return
        
        # اگر در گروه دیگری بود
        if found_group != group:
            await update.message.reply_text(
                f"❌ شما عضو گروه {found_group} هستید و نمی‌توانید در گروه {group} ثبت‌نام کنید"
            )
            return
        
        player_name = found_name

    else:  # بسکتبال و والیبال
        # ✅ لاگ برای دیدن محتوای RAM_PLAYERS
        print(f"   بررسی {sport} - محتوای RAM_PLAYERS[{sport}]: {RAM_PLAYERS.get(sport, {})}")
        print(f"   جستجوی شماره: {phone}")
        
        # اطمینان از وجود دیکشنری
        if RAM_PLAYERS.get(sport) is None:
            RAM_PLAYERS[sport] = {}
            print(f"   ⚠️ RAM_PLAYERS[{sport}] None بود، مقداردهی شد")
        
        player_name = RAM_PLAYERS[sport].get(phone)
        
        if not player_name:
            sport_name = {
                "basketball": "بسکتبال",
                "volleyball": "والیبال"
            }.get(sport, sport)
            
            print(f"   ❌ بازیکن با شماره {phone} در لیست {sport_name} پیدا نشد")
            print(f"   شماره‌های موجود: {list(RAM_PLAYERS[sport].keys())}")
            
            await update.message.reply_text(f"❌ شما در لیست {sport_name} نیستید")
            return
        
        print(f"   ✅ بازیکن پیدا شد: {player_name}")

    # ─────────── بررسی تکراری بودن ───────────
    if phone in registrations:
        await update.message.reply_text("❌ قبلاً در این تایم ثبت‌نام کرده‌اید")
        return

    # ─────────── بررسی ظرفیت ───────────
    if len(registrations) >= capacity:
        await update.message.reply_text("❌ ظرفیت این تایم تکمیل شده")
        return

    # ─────────── ذخیره نهایی ───────────
    registrations[phone] = player_name
    
    print(f"✅ ثبت‌نام موفق: {player_name} - {phone} در {sport}")

    # ─────────── پیام موفقیت ───────────
    sport_name = {
        "futsal": "فوتسال",
        "basketball": "بسکتبال",
        "volleyball": "والیبال"
    }.get(sport, sport)
    
    group_text = f" گروه {group}" if sport == "futsal" else ""
    
    await update.message.reply_text(
        f"✅ ثبت‌نام موفق\n"
        f"👤 {player_name}\n"
        f"🏅 {sport_name}{group_text}\n"
        f"⏰ {slot['start']} - {slot['end']}"
    )

    context.user_data.clear()


# ======================================================
# ADMIN COMMANDS
# ======================================================
async def today_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    text = "📄 ثبت‌نام‌های امروز (RAM):\n\n"
    has_users = False

    # فوتسال گروهی
    for g in "ABCDEFGHIJ":
        for time_key, users in RAM_REGISTRATIONS["futsal"][g].items():
            if users:
                has_users = True
                # پیدا کردن تاریخ تایم
                time_idx = int(time_key.split("_")[1]) if "_" in time_key else 0
                if time_idx < len(RAM_TIMES["futsal"][g]):
                    t = RAM_TIMES["futsal"][g][time_idx]
                    j_date = jdatetime.date.fromgregorian(date=t["date_obj"])
                    text += f"⚽ فوتسال گروه {g} - {j_date.strftime('%Y/%m/%d')} {t['start']}-{t['end']}:\n"
                else:
                    text += f"⚽ فوتسال گروه {g} تایم {time_key}:\n"
                
                for phone, name in users.items():
                    text += f"  👤 {name}\n"
                text += "\n"

    # بسکتبال
    for time_key, users in RAM_REGISTRATIONS["basketball"].items():
        if users:
            has_users = True
            time_idx = int(time_key.split("_")[1]) if "_" in time_key else 0
            if time_idx < len(RAM_TIMES["basketball"]):
                t = RAM_TIMES["basketball"][time_idx]
                j_date = jdatetime.date.fromgregorian(date=t["date_obj"])
                text += f"🏀 بسکتبال - {j_date.strftime('%Y/%m/%d')} {t['start']}-{t['end']}:\n"
            else:
                text += f"🏀 بسکتبال تایم {time_key}:\n"
            
            for phone, name in users.items():
                text += f"  👤 {name}\n"
            text += "\n"

    # والیبال
    for time_key, users in RAM_REGISTRATIONS["volleyball"].items():
        if users:
            has_users = True
            time_idx = int(time_key.split("_")[1]) if "_" in time_key else 0
            if time_idx < len(RAM_TIMES["volleyball"]):
                t = RAM_TIMES["volleyball"][time_idx]
                j_date = jdatetime.date.fromgregorian(date=t["date_obj"])
                text += f"🏐 والیبال - {j_date.strftime('%Y/%m/%d')} {t['start']}-{t['end']}:\n"
            else:
                text += f"🏐 والیبال تایم {time_key}:\n"
            
            for phone, name in users.items():
                text += f"  👤 {name}\n"
            text += "\n"

    await update.message.reply_text(text if has_users else "📭 هیچ ثبت‌نامی وجود ندارد")


# ======================================================
# DAILY REPORT
# ======================================================
async def daily_report(context: ContextTypes.DEFAULT_TYPE):
    # اول تایم‌های منقضی شده رو پاک کن
    await cleanup_expired_times()
    
    # بعد گزارش بده
    text = "📊 گزارش شبانه ثبت‌نام‌ها (RAM)\n"
    text += f"📅 تاریخ: {get_today_jalali()}\n\n"

    # فوتسال
    for g in "ABCDEFGHIJ":
        total = 0
        for users in RAM_REGISTRATIONS["futsal"][g].values():
            total += len(users)
        if total > 0:
            text += f"⚽ فوتسال گروه {g}: {total} نفر\n"

    # بسکتبال
    total_basketball = sum(len(users) for users in RAM_REGISTRATIONS["basketball"].values())
    if total_basketball > 0:
        text += f"🏀 بسکتبال: {total_basketball} نفر\n"

    # والیبال
    total_volleyball = sum(len(users) for users in RAM_REGISTRATIONS["volleyball"].values())
    if total_volleyball > 0:
        text += f"🏐 والیبال: {total_volleyball} نفر\n"

    if text == f"📊 گزارش شبانه ثبت‌نام‌ها (RAM)\n📅 تاریخ: {get_today_jalali()}\n\n":
        text += "📭 هیچ ثبت‌نامی وجود ندارد"

    for admin in SUPER_ADMINS + VIEWER_ADMINS:
        await context.bot.send_message(admin, text)


# ======================================================
#  sport select
# ======================================================

async def sport_text_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    sport_map = {
        "⚽ فوتسال": "futsal",
        "🏀 بسکتبال": "basketball",
        "🏐 والیبال": "volleyball"
    }

    if text not in sport_map:
        return

    sport = sport_map[text]
    context.user_data["sport"] = sport

    keyboard = []
    today = date.today()

    # فوتسال گروهی
    if sport == "futsal":
        for g in "ABCDEFGHIJ":
            # فقط تایم‌های امروز و آینده رو نشون بده
            active_times = []
            for t in RAM_TIMES["futsal"][g]:
                if not is_time_expired(t):
                    active_times.append(t)
            
            for idx, t in enumerate(active_times):
                # تاریخ شمسی
                j_date = jdatetime.date.fromgregorian(date=t["date_obj"])
                label = f"{j_date.strftime('%Y/%m/%d')} - {t['start']} - {t['end']} | گروه {g}"
                keyboard.append([
                    InlineKeyboardButton(label, callback_data=f"futsal:{g}:{idx}")
                ])

    else:
        # فقط تایم‌های امروز و آینده
        active_times = []
        for t in RAM_TIMES[sport]:
            if not is_time_expired(t):
                active_times.append(t)
        
        for idx, t in enumerate(active_times):
            j_date = jdatetime.date.fromgregorian(date=t["date_obj"])
            label = f"{j_date.strftime('%Y/%m/%d')} - {t['start']} - {t['end']}"
            keyboard.append([
                InlineKeyboardButton(label, callback_data=f"{sport}:{idx}")
            ])

    if not keyboard:
        await update.message.reply_text("❌ تایمی وجود ندارد")
        return

    await update.message.reply_text(
        "⏰ تایم‌های موجود:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ======================================================
#  time select
# ======================================================

async def time_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data.split(":")
    sport = data[0]

    # فوتسال گروهی
    if sport == "futsal":
        group = data[1]

        try:
            idx = int(data[2])
        except:
            await query.edit_message_text("❌ خطا در انتخاب تایم")
            return

        # ✅ اینجا بیرون except قرار گرفت
        context.user_data["sport"] = "futsal"
        context.user_data["group"] = group
        context.user_data["time_index"] = idx

    else:
        idx = int(data[1])
        context.user_data["sport"] = sport
        context.user_data["time_index"] = idx

    await query.edit_message_text(
        "📱 لطفاً شماره موبایل خود را وارد کنید:\nمثال: 09123456789"
    )




async def add_basketball(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_super(update.effective_user.id):
        return

    try:
        if len(context.args) < 2:
            await update.message.reply_text(
                "❌ فرمت:\n"
                "/add_basketball نام‌و‌فامیلی 09123456789\n"
                "مثال: /add_basketball علی محمدی 09123456789"
            )
            return
            
        phone = context.args[-1]
        full_name = " ".join(context.args[:-1])
        
        phone = normalize_phone(phone)
        
        print(f"🟡 افزودن بازیکن بسکتبال: {full_name} - {phone}")

        if RAM_PLAYERS.get("basketball") is None:
            RAM_PLAYERS["basketball"] = {}
            
        if phone in RAM_PLAYERS["basketball"]:
            await update.message.reply_text("❌ قبلاً ثبت شده")
            return

        RAM_PLAYERS["basketball"][phone] = full_name
        
        print(f"✅ بازیکن بسکتبال اضافه شد: {phone} -> {full_name}")
        await update.message.reply_text(
            f"✅ بازیکن بسکتبال اضافه شد:\n"
            f"👤 {full_name}\n"
            f"📱 {phone}"
        )
        
    except Exception as e:
        print(f"❌ خطا در add_basketball: {e}")
        await update.message.reply_text(
            "❌ فرمت: /add_basketball نام‌و‌فامیلی 09123456789"
        )



async def add_volleyball(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_super(update.effective_user.id):
        return

    try:
        if len(context.args) < 2:
            await update.message.reply_text(
                "❌ فرمت:\n"
                "/add_volleyball نام‌و‌فامیلی 09123456789\n"
                "مثال: /add_volleyball علی محمدی 09123456789"
            )
            return
            
        phone = context.args[-1]
        full_name = " ".join(context.args[:-1])
        
        phone = normalize_phone(phone)
        
        print(f"🟡 افزودن بازیکن والیبال: {full_name} - {phone}")

        if RAM_PLAYERS.get("volleyball") is None:
            RAM_PLAYERS["volleyball"] = {}
            
        if phone in RAM_PLAYERS["volleyball"]:
            await update.message.reply_text("❌ قبلاً ثبت شده")
            return

        RAM_PLAYERS["volleyball"][phone] = full_name
        
        print(f"✅ بازیکن والیبال اضافه شد: {phone} -> {full_name}")
        await update.message.reply_text(
            f"✅ بازیکن والیبال اضافه شد:\n"
            f"👤 {full_name}\n"
            f"📱 {phone}"
        )
        
    except Exception as e:
        print(f"❌ خطا در add_volleyball: {e}")
        await update.message.reply_text(
            "❌ فرمت: /add_volleyball نام‌و‌فامیلی 09123456789"
        )




async def add_basketball_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_super(update.effective_user.id):
        return

    try:
        # فرمت جدید: /add_basketball_time 2026-02-11 18:00 19:00 15
        # یا: /add_basketball_time 1404/11/23 18:00 19:00 15
        
        if len(context.args) != 4:
            await update.message.reply_text(
                "❌ فرمت:\n"
                "/add_basketball_time تاریخ start end cap\n"
                "مثال میلادی: /add_basketball_time 2026-02-11 18:00 19:00 15\n"
                "مثال شمسی: /add_basketball_time 1404/11/23 18:00 19:00 15"
            )
            return

        date_str, start, end, cap = context.args
        
        # تبدیل تاریخ
        date_obj = parse_date(date_str)
        if not date_obj:
            await update.message.reply_text("❌ تاریخ نامعتبر است")
            return
            
        # بررسی اینکه تاریخ گذشته نباشه
        if date_obj < date.today():
            await update.message.reply_text("❌ این تاریخ گذشته است!")
            return

        RAM_TIMES["basketball"].append({
            "date": date_obj.isoformat(),
            "date_obj": date_obj,
            "start": start,
            "end": end,
            "cap": int(cap)
        })

        # مرتب‌سازی بر اساس تاریخ
        RAM_TIMES["basketball"].sort(key=lambda x: x["date_obj"])
        
        # نمایش تاریخ شمسی
        j_date = jdatetime.date.fromgregorian(date=date_obj)
        await update.message.reply_text(
            f"✅ تایم بسکتبال اضافه شد:\n"
            f"📅 {j_date.strftime('%Y/%m/%d')}\n"
            f"⏰ {start} تا {end}\n"
            f"👥 ظرفیت: {cap} نفر"
        )

    except Exception as e:
        print(f"❌ خطا در add_basketball_time: {e}")
        await update.message.reply_text("❌ فرمت: /add_basketball_time تاریخ start end cap")



async def add_volleyball_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_super(update.effective_user.id):
        return

    try:
        if len(context.args) != 4:
            await update.message.reply_text(
                "❌ فرمت:\n"
                "/add_volleyball_time تاریخ start end cap\n"
                "مثال میلادی: /add_volleyball_time 2026-02-11 18:00 19:00 15\n"
                "مثال شمسی: /add_volleyball_time 1404/11/23 18:00 19:00 15"
            )
            return

        date_str, start, end, cap = context.args
        date_obj = parse_date(date_str)
        
        if not date_obj:
            await update.message.reply_text("❌ تاریخ نامعتبر است")
            return
            
        if date_obj < date.today():
            await update.message.reply_text("❌ این تاریخ گذشته است!")
            return

        RAM_TIMES["volleyball"].append({
            "date": date_obj.isoformat(),
            "date_obj": date_obj,
            "start": start,
            "end": end,
            "cap": int(cap)
        })

        RAM_TIMES["volleyball"].sort(key=lambda x: x["date_obj"])
        
        j_date = jdatetime.date.fromgregorian(date=date_obj)
        await update.message.reply_text(
            f"✅ تایم والیبال اضافه شد:\n"
            f"📅 {j_date.strftime('%Y/%m/%d')}\n"
            f"⏰ {start} تا {end}\n"
            f"👥 ظرفیت: {cap} نفر"
        )

    except Exception as e:
        print(f"❌ خطا در add_volleyball_time: {e}")
        await update.message.reply_text("❌ فرمت: /add_volleyball_time تاریخ start end cap")




async def add_group_player(update: Update, context: ContextTypes.DEFAULT_TYPE, group: str):
    if not is_super(update.effective_user.id):
        return

    try:
        # بررسی تعداد آرگومان‌ها - حداقل 2 تا (شماره + حداقل یک کلمه نام)
        if len(context.args) < 2:
            await update.message.reply_text(
                f"❌ فرمت:\n"
                f"/add{group}player نام‌و‌فامیلی 09123456789\n"
                f"مثال: /add{group}player علی محمدی 09123456789"
            )
            return
        
        # شماره همیشه آخرین آرگومان است
        phone = context.args[-1]
        # بقیه آرگومان‌ها نام و فامیلی هستند
        full_name = " ".join(context.args[:-1])
        
        phone = normalize_phone(phone)
        
        print(f"🟡 افزودن بازیکن فوتسال گروه {group}: {full_name} - {phone}")

        # اطمینان از وجود ساختار
        if group not in RAM_PLAYERS["futsal"]:
            RAM_PLAYERS["futsal"][group] = {}

        # اگر در همین گروه بود
        if phone in RAM_PLAYERS["futsal"][group]:
            await update.message.reply_text("❌ این بازیکن قبلاً در همین گروه ثبت شده")
            return

        # اگر در گروه دیگری بود
        for g in "ABCDEFGHIJ":
            if g != group and phone in RAM_PLAYERS["futsal"][g]:
                await update.message.reply_text(
                    f"❌ این شماره قبلاً در گروه {g} ثبت شده"
                )
                return

        # ذخیره با نام کامل
        RAM_PLAYERS["futsal"][group][phone] = full_name
        
        print(f"✅ بازیکن فوتسال اضافه شد: گروه {group}, {phone} -> {full_name}")

        await update.message.reply_text(
            f"✅ بازیکن به گروه فوتسال {group} اضافه شد:\n"
            f"👤 {full_name}\n"
            f"📱 {phone}"
        )

    except Exception as e:
        print(f"❌ خطا در add_group_player: {e}")
        await update.message.reply_text(
            f"❌ فرمت:\n"
            f"/add{group}player نام‌و‌فامیلی 09123456789"
        )



async def add_group_time(update: Update, context: ContextTypes.DEFAULT_TYPE, group: str):
    if not is_super(update.effective_user.id):
        return

    try:
        if len(context.args) != 4:
            await update.message.reply_text(
                f"❌ فرمت:\n"
                f"/add{group}time تاریخ start end cap\n"
                f"مثال میلادی: /add{group}time 2026-02-11 18:00 19:00 15\n"
                f"مثال شمسی: /add{group}time 1404/11/23 18:00 19:00 15"
            )
            return

        date_str, start, end, cap = context.args
        date_obj = parse_date(date_str)
        
        if not date_obj:
            await update.message.reply_text("❌ تاریخ نامعتبر است")
            return
            
        if date_obj < date.today():
            await update.message.reply_text("❌ این تاریخ گذشته است!")
            return

        RAM_TIMES["futsal"][group].append({
            "date": date_obj.isoformat(),
            "date_obj": date_obj,
            "start": start,
            "end": end,
            "cap": int(cap)
        })

        RAM_TIMES["futsal"][group].sort(key=lambda x: x["date_obj"])
        
        j_date = jdatetime.date.fromgregorian(date=date_obj)
        await update.message.reply_text(
            f"✅ تایم گروه {group} اضافه شد:\n"
            f"📅 {j_date.strftime('%Y/%m/%d')}\n"
            f"⏰ {start} تا {end}\n"
            f"👥 ظرفیت: {cap} نفر"
        )

    except Exception as e:
        print(f"❌ خطا در add_group_time: {e}")
        await update.message.reply_text(
            f"❌ فرمت:\n/add{group}time تاریخ start end cap"
        )


async def cleanup_expired_times():
    """پاک کردن تایم‌های منقضی شده و ثبت‌نام‌های مربوطه"""
    today = date.today()
    
    # فوتسال
    for g in "ABCDEFGHIJ":
        # تایم‌های منقضی شده را پیدا کن
        expired_indices = []
        for i, t in enumerate(RAM_TIMES["futsal"][g]):
            if is_time_expired(t):
                expired_indices.append(i)
        
        # از آخر به اول پاک کن
        for i in reversed(expired_indices):
            # پاک کردن ثبت‌نام‌های این تایم
            time_key = f"time_{i}"
            if time_key in RAM_REGISTRATIONS["futsal"][g]:
                del RAM_REGISTRATIONS["futsal"][g][time_key]
            # پاک کردن تایم
            del RAM_TIMES["futsal"][g][i]
    
    # بسکتبال
    expired_indices = []
    for i, t in enumerate(RAM_TIMES["basketball"]):
        if is_time_expired(t):
            expired_indices.append(i)
    
    for i in reversed(expired_indices):
        time_key = f"time_{i}"
        if time_key in RAM_REGISTRATIONS["basketball"]:
            del RAM_REGISTRATIONS["basketball"][time_key]
        del RAM_TIMES["basketball"][i]
    
    # والیبال
    expired_indices = []
    for i, t in enumerate(RAM_TIMES["volleyball"]):
        if is_time_expired(t):
            expired_indices.append(i)
    
    for i in reversed(expired_indices):
        time_key = f"time_{i}"
        if time_key in RAM_REGISTRATIONS["volleyball"]:
            del RAM_REGISTRATIONS["volleyball"][time_key]
        del RAM_TIMES["volleyball"][i]


async def show_players(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_super(update.effective_user.id):
        return
    
    text = "📋 لیست بازیکنان:\n\n"
    
    # فوتسال
    for g in "ABCDEFGHIJ":
        if RAM_PLAYERS["futsal"][g]:
            text += f"⚽ فوتسال گروه {g}: {len(RAM_PLAYERS['futsal'][g])} نفر\n"
            for phone, name in list(RAM_PLAYERS["futsal"][g].items())[:10]:  # فقط 10 تا
                text += f"  - {name} : {phone}\n"
            if len(RAM_PLAYERS["futsal"][g]) > 10:
                text += f"  ... و {len(RAM_PLAYERS['futsal'][g]) - 10} نفر دیگر\n"
            text += "\n"
    
    # بسکتبال
    if RAM_PLAYERS["basketball"]:
        text += f"🏀 بسکتبال: {len(RAM_PLAYERS['basketball'])} نفر\n"
        for phone, name in list(RAM_PLAYERS["basketball"].items())[:10]:
            text += f"  - {name} : {phone}\n"
        if len(RAM_PLAYERS["basketball"]) > 10:
            text += f"  ... و {len(RAM_PLAYERS['basketball']) - 10} نفر دیگر\n"
        text += "\n"
    
    # والیبال
    if RAM_PLAYERS["volleyball"]:
        text += f"🏐 والیبال: {len(RAM_PLAYERS['volleyball'])} نفر\n"
        for phone, name in list(RAM_PLAYERS["volleyball"].items())[:10]:
            text += f"  - {name} : {phone}\n"
        if len(RAM_PLAYERS["volleyball"]) > 10:
            text += f"  ... و {len(RAM_PLAYERS['volleyball']) - 10} نفر دیگر\n"
    
    await update.message.reply_text(text or "هیچ بازیکنی ثبت نشده")



async def remove_group_player(update: Update, context: ContextTypes.DEFAULT_TYPE, group: str):
    """حذف بازیکن از گروه فوتسال با شماره تلفن"""
    if not is_super(update.effective_user.id):
        await update.message.reply_text("❌ شما دسترسی به این دستور ندارید")
        return

    try:
        if len(context.args) != 1:
            await update.message.reply_text(
                f"❌ فرمت:\n"
                f"/remove{group}player 09123456789\n"
                f"مثال: /remove{group}player 09123456789"
            )
            return

        phone = normalize_phone(context.args[0])
        
        # بررسی وجود بازیکن در گروه
        if phone not in RAM_PLAYERS["futsal"][group]:
            await update.message.reply_text(
                f"❌ این شماره در گروه {group} وجود ندارد"
            )
            return

        # ذخیره نام قبل از حذف
        player_name = RAM_PLAYERS["futsal"][group][phone]
        
        # حذف بازیکن
        del RAM_PLAYERS["futsal"][group][phone]
        
        await update.message.reply_text(
            f"✅ بازیکن از گروه {group} حذف شد:\n"
            f"👤 {player_name}\n"
            f"📱 {phone}"
        )

    except Exception as e:
        print(f"❌ خطا در remove_group_player: {e}")
        await update.message.reply_text(
            f"❌ خطا در حذف بازیکن\n"
            f"فرمت: /remove{group}player 09123456789"
        )



async def remove_basketball(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حذف بازیکن بسکتبال با شماره تلفن"""
    if not is_super(update.effective_user.id):
        await update.message.reply_text("❌ شما دسترسی به این دستور ندارید")
        return

    try:
        if len(context.args) != 1:
            await update.message.reply_text(
                "❌ فرمت:\n"
                "/remove_basketball 09123456789\n"
                "مثال: /remove_basketball 09123456789"
            )
            return

        phone = normalize_phone(context.args[0])
        
        # بررسی وجود بازیکن
        if phone not in RAM_PLAYERS["basketball"]:
            await update.message.reply_text(
                "❌ این شماره در لیست بسکتبال وجود ندارد"
            )
            return

        # ذخیره نام قبل از حذف
        player_name = RAM_PLAYERS["basketball"][phone]
        
        # حذف بازیکن
        del RAM_PLAYERS["basketball"][phone]
        
        await update.message.reply_text(
            f"✅ بازیکن بسکتبال حذف شد:\n"
            f"👤 {player_name}\n"
            f"📱 {phone}"
        )

    except Exception as e:
        print(f"❌ خطا در remove_basketball: {e}")
        await update.message.reply_text(
            "❌ خطا در حذف بازیکن\n"
            "فرمت: /remove_basketball 09123456789"
        )



async def remove_volleyball(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حذف بازیکن والیبال با شماره تلفن"""
    if not is_super(update.effective_user.id):
        await update.message.reply_text("❌ شما دسترسی به این دستور ندارید")
        return

    try:
        if len(context.args) != 1:
            await update.message.reply_text(
                "❌ فرمت:\n"
                "/remove_volleyball 09123456789\n"
                "مثال: /remove_volleyball 09123456789"
            )
            return

        phone = normalize_phone(context.args[0])
        
        # بررسی وجود بازیکن
        if phone not in RAM_PLAYERS["volleyball"]:
            await update.message.reply_text(
                "❌ این شماره در لیست والیبال وجود ندارد"
            )
            return

        # ذخیره نام قبل از حذف
        player_name = RAM_PLAYERS["volleyball"][phone]
        
        # حذف بازیکن
        del RAM_PLAYERS["volleyball"][phone]
        
        await update.message.reply_text(
            f"✅ بازیکن والیبال حذف شد:\n"
            f"👤 {player_name}\n"
            f"📱 {phone}"
        )

    except Exception as e:
        print(f"❌ خطا در remove_volleyball: {e}")
        await update.message.reply_text(
            "❌ خطا در حذف بازیکن\n"
            "فرمت: /remove_volleyball 09123456789"
        )



async def remove_group_time(update: Update, context: ContextTypes.DEFAULT_TYPE, group: str):
    """حذف تایم از گروه فوتسال با شماره ایندکس"""
    if not is_super(update.effective_user.id):
        await update.message.reply_text("❌ شما دسترسی به این دستور ندارید")
        return

    try:
        if len(context.args) != 1:
            await update.message.reply_text(
                f"❌ فرمت:\n"
                f"/remove{group}time ایندکس\n"
                f"برای دیدن ایندکس‌ها از /show_times استفاده کنید"
            )
            return

        try:
            idx = int(context.args[0])
        except ValueError:
            await update.message.reply_text("❌ ایندکس باید عدد باشد")
            return

        # بررسی وجود تایم
        if idx >= len(RAM_TIMES["futsal"][group]) or idx < 0:
            await update.message.reply_text(
                f"❌ تایم با ایندکس {idx} در گروه {group} وجود ندارد"
            )
            return

        # ذخیره اطلاعات تایم قبل از حذف
        time_info = RAM_TIMES["futsal"][group][idx]
        j_date = jdatetime.date.fromgregorian(date=time_info["date_obj"])
        
        # حذف ثبت‌نام‌های مربوط به این تایم
        time_key = f"time_{idx}"
        if time_key in RAM_REGISTRATIONS["futsal"][group]:
            del RAM_REGISTRATIONS["futsal"][group][time_key]
        
        # حذف تایم
        del RAM_TIMES["futsal"][group][idx]
        
        # به‌روزرسانی کلیدهای ثبت‌نام‌ها (بعد از حذف، ایندکس‌ها تغییر می‌کنند)
        await reindex_futsal_times(group)
        
        await update.message.reply_text(
            f"✅ تایم از گروه {group} حذف شد:\n"
            f"📅 {j_date.strftime('%Y/%m/%d')}\n"
            f"⏰ {time_info['start']} - {time_info['end']}\n"
            f"👥 ظرفیت: {time_info['cap']} نفر"
        )

    except Exception as e:
        print(f"❌ خطا در remove_group_time: {e}")
        await update.message.reply_text(
            f"❌ خطا در حذف تایم\n"
            f"فرمت: /remove{group}time ایندکس"
        )

async def reindex_futsal_times(group: str):
    """به‌روزرسانی ایندکس ثبت‌نام‌ها بعد از حذف تایم"""
    new_registrations = {}
    for i, time in enumerate(RAM_TIMES["futsal"][group]):
        old_key = f"time_{i}"  # کلید جدید
        # اگه ثبت‌نامی برای این تایم جدید وجود داشت
        for old_key_existing in list(RAM_REGISTRATIONS["futsal"][group].keys()):
            if old_key_existing == f"time_{i}" or old_key_existing == i:
                new_registrations[old_key] = RAM_REGISTRATIONS["futsal"][group][old_key_existing]
                break
    
    RAM_REGISTRATIONS["futsal"][group] = new_registrations



async def remove_basketball_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حذف تایم بسکتبال با شماره ایندکس"""
    if not is_super(update.effective_user.id):
        await update.message.reply_text("❌ شما دسترسی به این دستور ندارید")
        return

    try:
        if len(context.args) != 1:
            await update.message.reply_text(
                "❌ فرمت:\n"
                "/remove_basketball_time ایندکس\n"
                "برای دیدن ایندکس‌ها از /show_times استفاده کنید"
            )
            return

        try:
            idx = int(context.args[0])
        except ValueError:
            await update.message.reply_text("❌ ایندکس باید عدد باشد")
            return

        # بررسی وجود تایم
        if idx >= len(RAM_TIMES["basketball"]) or idx < 0:
            await update.message.reply_text(
                f"❌ تایم با ایندکس {idx} در بسکتبال وجود ندارد"
            )
            return

        # ذخیره اطلاعات تایم قبل از حذف
        time_info = RAM_TIMES["basketball"][idx]
        j_date = jdatetime.date.fromgregorian(date=time_info["date_obj"])
        
        # حذف ثبت‌نام‌های مربوط به این تایم
        time_key = f"time_{idx}"
        if time_key in RAM_REGISTRATIONS["basketball"]:
            del RAM_REGISTRATIONS["basketball"][time_key]
        
        # حذف تایم
        del RAM_TIMES["basketball"][idx]
        
        # به‌روزرسانی کلیدهای ثبت‌نام‌ها
        await reindex_sport_times("basketball")
        
        await update.message.reply_text(
            f"✅ تایم بسکتبال حذف شد:\n"
            f"📅 {j_date.strftime('%Y/%m/%d')}\n"
            f"⏰ {time_info['start']} - {time_info['end']}\n"
            f"👥 ظرفیت: {time_info['cap']} نفر"
        )

    except Exception as e:
        print(f"❌ خطا در remove_basketball_time: {e}")
        await update.message.reply_text(
            "❌ خطا در حذف تایم\n"
            "فرمت: /remove_basketball_time ایندکس"
        )


async def remove_volleyball_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حذف تایم والیبال با شماره ایندکس"""
    if not is_super(update.effective_user.id):
        await update.message.reply_text("❌ شما دسترسی به این دستور ندارید")
        return

    try:
        if len(context.args) != 1:
            await update.message.reply_text(
                "❌ فرمت:\n"
                "/remove_volleyball_time ایندکس\n"
                "برای دیدن ایندکس‌ها از /show_times استفاده کنید"
            )
            return

        try:
            idx = int(context.args[0])
        except ValueError:
            await update.message.reply_text("❌ ایندکس باید عدد باشد")
            return

        # بررسی وجود تایم
        if idx >= len(RAM_TIMES["volleyball"]) or idx < 0:
            await update.message.reply_text(
                f"❌ تایم با ایندکس {idx} در والیبال وجود ندارد"
            )
            return

        # ذخیره اطلاعات تایم قبل از حذف
        time_info = RAM_TIMES["volleyball"][idx]
        j_date = jdatetime.date.fromgregorian(date=time_info["date_obj"])
        
        # حذف ثبت‌نام‌های مربوط به این تایم
        time_key = f"time_{idx}"
        if time_key in RAM_REGISTRATIONS["volleyball"]:
            del RAM_REGISTRATIONS["volleyball"][time_key]
        
        # حذف تایم
        del RAM_TIMES["volleyball"][idx]
        
        # به‌روزرسانی کلیدهای ثبت‌نام‌ها
        await reindex_sport_times("volleyball")
        
        await update.message.reply_text(
            f"✅ تایم والیبال حذف شد:\n"
            f"📅 {j_date.strftime('%Y/%m/%d')}\n"
            f"⏰ {time_info['start']} - {time_info['end']}\n"
            f"👥 ظرفیت: {time_info['cap']} نفر"
        )

    except Exception as e:
        print(f"❌ خطا در remove_volleyball_time: {e}")
        await update.message.reply_text(
            "❌ خطا در حذف تایم\n"
            "فرمت: /remove_volleyball_time ایندکس"
        )


async def reindex_sport_times(sport: str):
    """به‌روزرسانی ایندکس ثبت‌نام‌ها بعد از حذف تایم در بسکتبال/والیبال"""
    new_registrations = {}
    for i, time in enumerate(RAM_TIMES[sport]):
        new_key = f"time_{i}"
        # اگه ثبت‌نامی برای این تایم جدید وجود داشت
        for old_key in list(RAM_REGISTRATIONS[sport].keys()):
            if old_key == f"time_{i}" or old_key == i:
                new_registrations[new_key] = RAM_REGISTRATIONS[sport][old_key]
                break
    
    RAM_REGISTRATIONS[sport] = new_registrations



async def show_times(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش تمام تایم‌ها به همراه ایندکس برای حذف"""
    if not is_super(update.effective_user.id):
        return

    text = "📋 لیست تایم‌ها:\n\n"

    # فوتسال
    for g in "ABCDEFGHIJ":
        if RAM_TIMES["futsal"][g]:
            text += f"⚽ فوتسال گروه {g}:\n"
            for idx, t in enumerate(RAM_TIMES["futsal"][g]):
                j_date = jdatetime.date.fromgregorian(date=t["date_obj"])
                text += f"  [{idx}] {j_date.strftime('%Y/%m/%d')} {t['start']}-{t['end']} (ظرفیت: {t['cap']})\n"
            text += "\n"

    # بسکتبال
    if RAM_TIMES["basketball"]:
        text += f"🏀 بسکتبال:\n"
        for idx, t in enumerate(RAM_TIMES["basketball"]):
            j_date = jdatetime.date.fromgregorian(date=t["date_obj"])
            text += f"  [{idx}] {j_date.strftime('%Y/%m/%d')} {t['start']}-{t['end']} (ظرفیت: {t['cap']})\n"
        text += "\n"

    # والیبال
    if RAM_TIMES["volleyball"]:
        text += f"🏐 والیبال:\n"
        for idx, t in enumerate(RAM_TIMES["volleyball"]):
            j_date = jdatetime.date.fromgregorian(date=t["date_obj"])
            text += f"  [{idx}] {j_date.strftime('%Y/%m/%d')} {t['start']}-{t['end']} (ظرفیت: {t['cap']})\n"

    await update.message.reply_text(text or "هیچ تایمی وجود ندارد")



# ======================================================
# MAIN
# ======================================================
def main():
    # ✅ مقداردهی اولیه ساختارها
    global RAM_PLAYERS, RAM_TIMES, RAM_REGISTRATIONS
    
    RAM_PLAYERS = {
        "futsal": {g: {} for g in "ABCDEFGHIJ"},
        "basketball": {},
        "volleyball": {}
    }
    
    RAM_TIMES = {
        "futsal": {g: [] for g in "ABCDEFGHIJ"},
        "basketball": [],
        "volleyball": []
    }
    
    RAM_REGISTRATIONS = {
        "futsal": {g: {} for g in "ABCDEFGHIJ"},
        "basketball": {},
        "volleyball": {}
    }
    
    # ساخت اپلیکیشن
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # هندلرها
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("today", today_list))
    app.add_handler(CommandHandler("show_players", show_players))
    app.add_handler(CommandHandler("add_basketball", add_basketball))
    app.add_handler(CommandHandler("add_volleyball", add_volleyball))
    app.add_handler(CommandHandler("add_basketball_time", add_basketball_time))
    app.add_handler(CommandHandler("add_volleyball_time", add_volleyball_time))
    app.add_handler(CommandHandler("remove_basketball", remove_basketball))
    app.add_handler(CommandHandler("remove_volleyball", remove_volleyball))
    app.add_handler(CommandHandler("remove_basketball_time", remove_basketball_time))
    app.add_handler(CommandHandler("remove_volleyball_time", remove_volleyball_time))
    app.add_handler(CommandHandler("show_times", show_times))
    # ✅ دستورهای یونیک برای گروه‌های فوتسال A تا J
    for group in FUTSAL_GROUPS.keys():

        app.add_handler(
            CommandHandler(
                f"add{group}player",
                lambda update, context, g=group: add_group_player(update, context, g)
            )
        )

        app.add_handler(
            CommandHandler(
                f"add{group}time",
                lambda update, context, g=group: add_group_time(update, context, g)
            )
        )


        app.add_handler(
            CommandHandler(
                f"remove{group}player",
                lambda update, context, g=group: remove_group_player(update, context, g)
            )
        )
        app.add_handler(
            CommandHandler(
                f"remove{group}time",
                lambda update, context, g=group: remove_group_time(update, context, g)
            )
        )
    

    # 1️⃣ انتخاب رشته با دکمه‌های پایین
    app.add_handler(MessageHandler(
        filters.TEXT & filters.Regex("^(⚽ فوتسال|🏀 بسکتبال|🏐 والیبال)$"),
        sport_text_select
    ))
    
    # 2️⃣ انتخاب تایم (دکمه شیشه‌ای)
    app.add_handler(CallbackQueryHandler(time_select, pattern="^(futsal|basketball|volleyball):"))

    # 3️⃣ وارد کردن شماره موبایل
    app.add_handler(MessageHandler(
        filters.TEXT & filters.Regex(r"^09\d{9}$"),
        register
    ))






    # JobQueue برای گزارش شبانه
    app.job_queue.run_daily(
        daily_report,
        REPORT_TIME
    )

    print("Bot Started")

    # ❗ این خودش event loop رو مدیریت می‌کنه
    app.run_polling()


if __name__ == "__main__":
    main()
