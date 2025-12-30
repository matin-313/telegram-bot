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

# ====== helpers ======
def normalize_phone(raw: str) -> str:
    if not raw:
        return raw
    p = "".join(ch for ch in raw if ch.isdigit())
    # تبدیل 98... به 0...
    if p.startswith("98") and len(p) == 12:
        p = "0" + p[2:]
    # اگر با 9 شروع کنه و طول 10 باشه -> 0 + ...
    if len(p) == 10 and p.startswith("9"):
        p = "0" + p
    # اگر قبلاً با 0 باشه و 11 رقم باشه، اوکی
    return p

def normalize_sport(s: str) -> str:
    if not s:
        return s
    t = s.strip().lower()
    mapping = {
        "فوتسال": "futsal", "فوتبال_سال": "futsal", "فوتسال؟": "futsal",
        "futsal": "futsal",
        "بسکتبال": "basketball", "basketball": "basketball",
        "والیبال": "volleyball", "vollyball": "volleyball", "volleyball": "volleyball"
    }
    return mapping.get(t, t)  # اگر نداشت همان متن کوچک‌شده را برمی‌گرداند

# اختیاری: برای اطمینان از مقادیر موجود در DB (نشانگر)
def safe_get_player_by_phone(phone_raw: str):
    p = normalize_phone(phone_raw)
    cursor.execute("SELECT full_name, sport, futsal_group FROM players WHERE phone=?", (p,))
    return cursor.fetchone()


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

    # normalize input phone
    phone_input = update.message.text.strip()
    phone = normalize_phone(phone_input)

    # get player by normalized phone
    cursor.execute("""
    SELECT full_name, sport, futsal_group
    FROM players
    WHERE phone=?
    """, (phone,))
    player = cursor.fetchone()

    if not player:
        await update.message.reply_text("❌ شما در لیست بازیکن‌ها نیستید")
        return

    name, player_sport_raw, group = player
    player_sport = normalize_sport(player_sport_raw)

    # if player has a group -> ensure not registered in other group before
    if group:
        cursor.execute("""
        SELECT r.id
        FROM registrations r
        JOIN time_slots t ON r.time_id = t.id
        WHERE r.phone=? AND t.futsal_group IS NOT NULL AND t.futsal_group != ?
        """, (phone, group))
        if cursor.fetchone():
            await update.message.reply_text("❌ شما نمی‌توانید در گروه دیگری ثبت نام کنید")
            return

    # compare sport normalized
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
        args = context.args
        if not args or len(args) < 2:
            await update.message.reply_text("❌ فرمت: /addplayer نام شماره رشته [گروه]\nمثال: /addplayer علی 09123456789 futsal A")
            return

        # پیدا کردن ایندکس شماره (مثل قبل)
        phone_idx = None
        for i, tok in enumerate(args):
            tok_clean = "".join(ch for ch in tok if ch.isdigit())
            if tok_clean.isdigit() and len(tok_clean) >= 9:
                phone_idx = i
                break

        if phone_idx is None:
            await update.message.reply_text("❌ شماره معتبر پیدا نشد. لطفاً شماره را هم وارد کنید.")
            return

        name = " ".join(args[:phone_idx]).strip()
        raw_phone = args[phone_idx]
        phone = normalize_phone(raw_phone)

        if phone_idx + 1 >= len(args):
            await update.message.reply_text("❌ لطفاً رشته را هم وارد کنید (مثلاً futsal).")
            return

        sport_raw = args[phone_idx + 1]
        sport = normalize_sport(sport_raw)

        group = args[phone_idx + 2] if (phone_idx + 2) < len(args) else None

        if not name:
            name = phone

        try:
            cursor.execute(
                "INSERT INTO players (full_name, phone, sport, futsal_group) VALUES (?,?,?,?)",
                (name, phone, sport, group)
            )
            conn.commit()
            await update.message.reply_text("✅ بازیکن اضافه شد")
        except sqlite3.IntegrityError:
            await update.message.reply_text("❌ این شماره قبلاً ثبت شده است.")
        except Exception as db_e:
            print("DB error in add_player:", db_e)
            await update.message.reply_text("❌ خطا در ثبت در دیتابیس")

    except Exception as e:
        print("Error in add_player:", e)
        await update.message.reply_text("❌ خطا در دستور — فرمت را بررسی کنید")


async def add_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_super(update.effective_user.id):
        return
    try:
        args = context.args
        if len(args) < 5:
            await update.message.reply_text("❌ فرمت: /addtime YYYY-MM-DD رشته شروع پایان ظرفیت [گروه]\nمثال: /addtime 2025-12-30 futsal 18:00 19:00 15 A")
            return

        date = args[0]
        sport = normalize_sport(args[1])
        start = args[2]
        end = args[3]
        try:
            cap = int(args[4])
        except:
            await update.message.reply_text("❌ ظرفیت باید عدد باشد.")
            return

        group = args[5] if len(args) > 5 else None

        cursor.execute(
            "INSERT INTO time_slots (date, sport, futsal_group, start, end, capacity) VALUES (?,?,?,?,?,?)",
            (date, sport, group, start, end, cap)
        )
        conn.commit()
        await update.message.reply_text("✅ تایم اضافه شد")
    except Exception as e:
        print("Error in add_time:", e)
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
            group_label = f" | گروه {s[3]}" if s[3] else ""
            label = f"{s[1]} - {s[2]}{group_label}"
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

