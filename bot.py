# ======================================================
# IMPORTS
# ======================================================
import sqlite3
import os
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

SUPER_ADMINS = [11111111]
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
    kb = [[KeyboardButton("📱 ارسال شماره", request_contact=True)]]
    await update.message.reply_text(
        "به ربات رزرو سالن خوش آمدید",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
    )

# ======================================================
# HANDLE CONTACT
# ======================================================
async def contact_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.contact.phone_number
    today = datetime.now().strftime("%Y-%m-%d")

    cursor.execute("SELECT full_name, sport, futsal_group FROM players WHERE phone=?", (phone,))
    p = cursor.fetchone()
    if not p:
        await update.message.reply_text("❌ شما در لیست بازیکن‌ها نیستید")
        return

    cursor.execute("SELECT 1 FROM registrations WHERE phone=? AND date=?", (phone, today))
    if cursor.fetchone():
        await update.message.reply_text("❌ امروز قبلاً ثبت‌نام کرده‌اید")
        return

    name, sport, group = p

    if sport == "futsal":
        cursor.execute(
            "SELECT id,start,end FROM time_slots WHERE date=? AND sport=? AND futsal_group=?",
            (today, sport, group)
        )
    else:
        cursor.execute(
            "SELECT id,start,end FROM time_slots WHERE date=? AND sport=?",
            (today, sport)
        )

    slots = cursor.fetchall()
    if not slots:
        await update.message.reply_text("❌ تایمی برای شما وجود ندارد")
        return

    context.user_data["player"] = (phone, name, sport, group)

    msg = "⏰ تایم‌های امروز:\n"
    for s in slots:
        msg += f"{s[0]} ➜ {s[1]}-{s[2]}\n"

    await update.message.reply_text(msg + "\nعدد تایم را بفرست")

# ======================================================
# REGISTER TIME
# ======================================================
async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "player" not in context.user_data:
        return

    time_id = update.message.text
    phone, name, sport, group = context.user_data["player"]
    today = datetime.now().strftime("%Y-%m-%d")

    cursor.execute("SELECT capacity FROM time_slots WHERE id=?", (time_id,))
    r = cursor.fetchone()
    if not r:
        await update.message.reply_text("❌ تایم نامعتبر")
        return

    cap = r[0]
    cursor.execute("SELECT COUNT(*) FROM registrations WHERE time_id=?", (time_id,))
    if cursor.fetchone()[0] >= cap:
        await update.message.reply_text("❌ ظرفیت تکمیل شده")
        return

    cursor.execute("""
    INSERT INTO registrations VALUES (NULL,?,?,?,?,?,?)
    """, (phone, name, sport, group, time_id, today))
    conn.commit()

    await update.message.reply_text("✅ ثبت‌نام انجام شد")
    context.user_data.clear()

# ======================================================
# ADMIN COMMANDS
# ======================================================
async def add_player(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_super(update.effective_user.id):
        return
    try:
        name, phone, sport, group = context.args + [None]
        cursor.execute(
            "INSERT INTO players VALUES (NULL,?,?,?,?)",
            (name, phone, sport, group)
        )
        conn.commit()
        await update.message.reply_text("✅ بازیکن اضافه شد")
    except:
        await update.message.reply_text("❌ خطا در دستور")

async def add_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_super(update.effective_user.id):
        return
    try:
        date, sport, group, start, end, cap = context.args
        cursor.execute("""
        INSERT INTO time_slots VALUES (NULL,?,?,?,?,?,?)
        """, (date, sport, group, start, end, int(cap)))
        conn.commit()
        await update.message.reply_text("✅ تایم اضافه شد")
    except:
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

    app.add_handler(MessageHandler(filters.CONTACT, contact_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, register))

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

