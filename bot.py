# ======================================================
# IMPORTS
# ======================================================
import sqlite3
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

DB_NAME = "sports.db"

REPORT_TIME = time(23, 59)

# ======================================================
# LOGGING
# ======================================================
logging.basicConfig(level=logging.INFO)

# ======================================================
# DATABASE
# ======================================================
conn = sqlite3.connect(DB_NAME, check_same_thread=False)
cursor = conn.cursor()

def init_db():
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS players (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT,
        phone TEXT UNIQUE,
        sport TEXT,
        futsal_group TEXT
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS time_slots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        sport TEXT,
        futsal_group TEXT,
        start TEXT,
        end TEXT,
        capacity INTEGER
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS registrations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phone TEXT,
        name TEXT,
        sport TEXT,
        futsal_group TEXT,
        time_id INTEGER,
        date TEXT
    )""")
    conn.commit()

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
    # فقط وقتی تایم انتخاب شده اجازه ثبت شماره بده
    if "time_id" not in context.user_data:
        return


    phone = update.message.text.strip()
    phone = phone.replace(" ", "").replace("-", "")

    if not phone.isdigit() or len(phone) < 10:
        await update.message.reply_text("❌ شماره نامعتبر است")
        return

    today = datetime.now().strftime("%Y-%m-%d")
    time_id = context.user_data["time_id"]
    selected_sport = context.user_data["sport"]

    cursor.execute("""
    SELECT full_name, sport, futsal_group
    FROM players
    WHERE phone=?
    """, (phone,))
    player = cursor.fetchone()

    if not player:
        await update.message.reply_text("❌ شما در لیست بازیکن‌ها نیستید")
        return

    name, player_sport, group = player

    if group:  # اگر بازیکن گروه دارد
        cursor.execute("""
        SELECT r.id
        FROM registrations r
        JOIN time_slots t ON r.time_id = t.id
        WHERE r.phone=? AND t.futsal_group IS NOT NULL AND t.futsal_group != ?
        """, (phone, group))
        if cursor.fetchone():
            await update.message.reply_text("❌ شما نمی‌توانید در گروه دیگری ثبت نام کنید")
            return


    if player_sport != selected_sport:
        await update.message.reply_text("❌ این رشته مربوط به شما نیست")
        return

    cursor.execute("""
    SELECT 1 FROM registrations
    WHERE phone=? AND date=?
    """, (phone, today))
    if cursor.fetchone():
        await update.message.reply_text("❌ امروز قبلاً ثبت‌نام کرده‌اید")
        return

    cursor.execute("SELECT capacity FROM time_slots WHERE id=?", (time_id,))
    cap = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM registrations WHERE time_id=?", (time_id,))
    if cursor.fetchone()[0] >= cap:
        await update.message.reply_text("❌ ظرفیت این تایم تکمیل شده")
        return

    cursor.execute("""
    INSERT INTO registrations VALUES (NULL,?,?,?,?,?,?)
    """, (phone, name, selected_sport, group, time_id, today))
    conn.commit()

    await update.message.reply_text("✅ ثبت‌نام شما با موفقیت انجام شد")
    context.user_data.clear()

# ======================================================
# ADMIN COMMANDS
# ======================================================
async def add_player(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_super(update.effective_user.id):
        return
    try:
        if len(context.args) < 3:
            await update.message.reply_text("❌ لطفاً حداقل نام، شماره و رشته را وارد کنید")
            return

        name = context.args[0]
        phone = context.args[1]
        sport = context.args[2]
        group = context.args[3] if len(context.args) > 3 else None  # گروه اختیاری

        cursor.execute(
            "INSERT INTO players (full_name, phone, sport, futsal_group) VALUES (?,?,?,?)",
            (name, phone, sport, group)
        )
        conn.commit()
        await update.message.reply_text("✅ بازیکن اضافه شد")
    except Exception as e:
        print(e)
        await update.message.reply_text("❌ خطا در دستور")


async def add_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_super(update.effective_user.id):
        return
    try:
        if len(context.args) < 5:
            await update.message.reply_text("❌ لطفاً حداقل تاریخ، رشته، شروع، پایان و ظرفیت را وارد کنید")
            return

        date = context.args[0]
        sport = context.args[1]
        start = context.args[2]
        end = context.args[3]
        cap = int(context.args[4])
        group = context.args[5] if len(context.args) > 5 else None  # گروه اختیاری

        cursor.execute(
            "INSERT INTO time_slots (date, sport, futsal_group, start, end, capacity) VALUES (?,?,?,?,?,?)",
            (date, sport, group, start, end, cap)
        )
        conn.commit()
        await update.message.reply_text("✅ تایم اضافه شد")
    except Exception as e:
        print(e)
        await update.message.reply_text("❌ خطا در دستور")


async def today_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    today = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("SELECT name,phone,sport FROM registrations WHERE date=?", (today,))
    rows = cursor.fetchall()
    text = "📄 ثبت‌نام‌های امروز:\n"
    for r in rows:
        text += f"{r[0]} | {r[1]} | {r[2]}\n"
    await update.message.reply_text(text or "خالی")

# ======================================================
# DAILY REPORT
# ======================================================
async def daily_report(context: ContextTypes.DEFAULT_TYPE):
    today = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("SELECT name,phone,sport FROM registrations WHERE date=?", (today,))
    rows = cursor.fetchall()
    text = f"📊 گزارش {today}\n"
    for r in rows:
        text += f"{r[0]} | {r[1]} | {r[2]}\n"
    for admin in SUPER_ADMINS + VIEWER_ADMINS:
        await context.bot.send_message(admin, text or "بدون ثبت‌نام")

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
    today = datetime.now().strftime("%Y-%m-%d")

    context.user_data.clear()
    context.user_data["sport"] = sport

    if sport == "futsal":
        cursor.execute("""
        SELECT id, start, end, futsal_group
        FROM time_slots
        WHERE date=? AND sport=?
        """, (today, sport))
    else:
        cursor.execute("""
        SELECT id, start, end
        FROM time_slots
        WHERE date=? AND sport=?
        """, (today, sport))

    slots = cursor.fetchall()
    if not slots:
        await update.message.reply_text("❌ تایمی برای امروز وجود ندارد")
        return

    keyboard = []
    for s in slots:
        if sport == "futsal":
            label = f"{s[1]} - {s[2]} | گروه {s[3]}"
        else:
            label = f"{s[1]} - {s[2]}"

        keyboard.append([
            InlineKeyboardButton(label, callback_data=f"time:{s[0]}")
        ])

    await update.message.reply_text(
        "⏰ تایم‌های امروز:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ======================================================
#  time select
# ======================================================

async def time_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    time_id = int(query.data.split(":")[1])
    context.user_data["time_id"] = time_id

    await query.edit_message_text(
        "📱 لطفاً شماره موبایل خود را وارد کنید:\nمثال: 09123456789"
    )

# ======================================================
# MAIN
# ======================================================
def main():
    # دیتابیس رو آماده می‌کنه
    init_db()

    # ساخت اپلیکیشن
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # هندلرها
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addplayer", add_player))
    app.add_handler(CommandHandler("addtime", add_time))
    app.add_handler(CommandHandler("today", today_list))

    # 1️⃣ انتخاب رشته با دکمه‌های پایین
    app.add_handler(MessageHandler(
        filters.TEXT & filters.Regex("^(⚽ فوتسال|🏀 بسکتبال|🏐 والیبال)$"),
        sport_text_select
    ))
    
    # 2️⃣ انتخاب تایم (دکمه شیشه‌ای)
    app.add_handler(CallbackQueryHandler(time_select, pattern="^time:"))
    
    # 3️⃣ وارد کردن شماره موبایل
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
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

