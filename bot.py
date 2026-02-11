# ======================================================
# IMPORTS
# ======================================================


import os
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler
import logging
from datetime import datetime, time
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
    "futsal": {g: [] for g in "ABCDEFGHIJ"},  # group -> list of times
    "basketball": [],
    "volleyball": []
}


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
    group = context.user_data.get("group")  # فقط فوتسال

    # ─────────── phone normalize ───────────
    raw_phone = update.message.text.strip()
    phone = normalize_phone(raw_phone)

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

    # ─────────── player lookup ───────────
    if sport == "futsal":
        found_group = None
        found_name = None

        for g in RAM_PLAYERS["futsal"]:
            for p, name in RAM_PLAYERS["futsal"][g].items():
                if normalize_phone(p) == phone:
                    found_group = g
                    found_name = name
                    break
            if found_group:
                break

        if not found_name:
            await update.message.reply_text("❌ شما در لیست فوتسال نیستید")
            return

        if found_group != group:
            await update.message.reply_text(
                f"❌ شما عضو گروه {found_group} هستید و نمی‌توانید در گروه {group} ثبت‌نام کنید"
            )
            return

        player_name = found_name

    else:
        player_name = RAM_PLAYERS[sport].get(phone)
        if not player_name:
            await update.message.reply_text("❌ شما در لیست این رشته نیستید")
            return

    # ─────────── duplicate / capacity ───────────
    if phone in registrations:
        await update.message.reply_text("❌ قبلاً در این تایم ثبت‌نام کرده‌اید")
        return

    if len(registrations) >= capacity:
        await update.message.reply_text("❌ ظرفیت این تایم تکمیل شده")
        return

    # ─────────── save ───────────
    registrations[phone] = player_name

    await update.message.reply_text(
        f"✅ ثبت‌نام موفق\n"
        f"👤 {player_name}\n"
        f"🏅 {sport}"
    )

    context.user_data.clear()



# ======================================================
# ADMIN COMMANDS
# ======================================================
async def today_list(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not is_admin(update.effective_user.id):
        return

    text = "📄 ثبت‌نام‌های امروز (RAM):\n\n"

    # فوتسال گروهی
    for g in "ABCDEFGHIJ":
        for time_id, users in RAM_REGISTRATIONS["futsal"][g].items():
            text += f"⚽ فوتسال گروه {g} تایم {time_id}:\n"
            for phone, name in users.items():
                text += f" - {name} ({phone})\n"

    # بسکتبال
    for time_id, users in RAM_REGISTRATIONS["basketball"].items():
        text += f"\n🏀 بسکتبال تایم {time_id}:\n"
        for phone, name in users.items():
            text += f" - {name} ({phone})\n"


    # والیبال
    for time_id, users in RAM_REGISTRATIONS["volleyball"].items():
        text += f"\n🏐 والیبال تایم {time_id}:\n"
        for phone, name in users.items():
            text += f" - {name} ({phone})\n"


    has_users = False
    
    # فوتسال
    for g in "ABCDEFGHIJ":
        for users in RAM_REGISTRATIONS["futsal"][g].values():
            if users:
                has_users = True
                break
        if has_users:
            break
    
    # بسکتبال
    if not has_users:
        for users in RAM_REGISTRATIONS["basketball"].values():
            if users:
                has_users = True
                break
    
    # والیبال
    if not has_users:
        for users in RAM_REGISTRATIONS["volleyball"].values():
            if users:
                has_users = True
                break
    
    await update.message.reply_text(text if has_users else "خالی")


# ======================================================
# DAILY REPORT
# ======================================================
async def daily_report(context: ContextTypes.DEFAULT_TYPE):

    text = "📊 گزارش شبانه ثبت‌نام‌ها (RAM)\n\n"

    for g in "ABCDEFGHIJ":
        for time_id, users in RAM_REGISTRATIONS["futsal"][g].items():
            text += f"⚽ فوتسال گروه {g} تایم {time_id}: {len(users)} نفر\n"

    for time_id, users in RAM_REGISTRATIONS["basketball"].items():
        text += f"🏀 بسکتبال تایم {time_id}: {len(users)} نفر\n"

    for time_id, users in RAM_REGISTRATIONS["volleyball"].items():
        text += f"🏐 والیبال تایم {time_id}: {len(users)} نفر\n"

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

    # فوتسال گروهی
    if sport == "futsal":
        for g in "ABCDEFGHIJ":
            for idx, t in enumerate(RAM_TIMES["futsal"][g]):
                label = f"{t['start']} - {t['end']} | گروه {g}"
                keyboard.append([
                    InlineKeyboardButton(label, callback_data=f"futsal:{g}:{idx}")
                ])

    else:
        for idx, t in enumerate(RAM_TIMES[sport]):
            label = f"{t['start']} - {t['end']}"
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
        name, phone = context.args
        phone = normalize_phone(phone)

        if phone in RAM_PLAYERS["basketball"]:
            await update.message.reply_text("❌ قبلاً ثبت شده")
            return

        RAM_PLAYERS["basketball"][phone] = name

        await update.message.reply_text("✅ بازیکن بسکتبال اضافه شد")
    except:
        await update.message.reply_text("❌ فرمت: /add_basketball نام 09123456789")



async def add_volleyball(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_super(update.effective_user.id):
        return

    try:
        name, phone = context.args
        phone = normalize_phone(phone)

        if phone in RAM_PLAYERS["volleyball"]:
            await update.message.reply_text("❌ قبلاً ثبت شده")
            return

        RAM_PLAYERS["volleyball"][phone] = name

        await update.message.reply_text("✅ بازیکن والیبال اضافه شد")
    except:
        await update.message.reply_text("❌ فرمت: /add_volleyball نام 09123456789")




async def add_basketball_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_super(update.effective_user.id):
        return

    try:
        start, end, cap = context.args

        RAM_TIMES["basketball"].append({
            "start": start,
            "end": end,
            "cap": int(cap),
            "players": []
        })

        await update.message.reply_text("✅ تایم بسکتبال اضافه شد")

    except:
        await update.message.reply_text("❌ فرمت: /add_basketball_time 18:00 19:00 15")




async def add_volleyball_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_super(update.effective_user.id):
        return

    try:
        start, end, cap = context.args

        RAM_TIMES["volleyball"].append({
            "start": start,
            "end": end,
            "cap": int(cap),
            "players": []
        })

        await update.message.reply_text("✅ تایم والیبال اضافه شد")

    except:
        await update.message.reply_text("❌ فرمت: /add_volleyball_time 18:00 19:00 15")



async def add_group_player(update: Update, context: ContextTypes.DEFAULT_TYPE, group: str):
    if not is_super(update.effective_user.id):
        return

    try:
        name, phone = context.args
        phone = normalize_phone(phone)

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

        # ذخیره
        RAM_PLAYERS["futsal"][group][phone] = name

        await update.message.reply_text(
            f"✅ بازیکن {name} به گروه فوتسال {group} اضافه شد"
        )

    except:
        await update.message.reply_text(
            f"❌ فرمت:\n/add{group}player نام 09123456789"
        )



async def add_group_time(update: Update, context: ContextTypes.DEFAULT_TYPE, group: str):
    if not is_super(update.effective_user.id):
        return

    try:
        start, end, cap = context.args

        RAM_TIMES["futsal"][group].append({
            "start": start,
            "end": end,
            "cap": int(cap),
            "players": []

        })

        await update.message.reply_text(
            f"✅ تایم گروه {group} اضافه شد: {start} تا {end}"
        )

    except:
        await update.message.reply_text(
            f"❌ فرمت:\n/add{group}time 18:00 19:00 15"
        )



# ======================================================
# MAIN
# ======================================================
def main():
    
    # ساخت اپلیکیشن
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # هندلرها
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("today", today_list))
    app.add_handler(CommandHandler("add_basketball", add_basketball))
    app.add_handler(CommandHandler("add_volleyball", add_volleyball))
    app.add_handler(CommandHandler("add_basketball_time", add_basketball_time))
    app.add_handler(CommandHandler("add_volleyball_time", add_volleyball_time))
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
