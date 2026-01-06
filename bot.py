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
# IN-MEMORY GROUP LISTS
# ======================================================

FUTSAL_GROUPS = {chr(i): set() for i in range(ord("A"), ord("K"))}  # A تا J
BASKETBALL_PLAYERS = set()
VOLLEYBALL_PLAYERS = set()

# ======================================================
# IN-MEMORY PLAYER LISTS
# ======================================================

FUTSAL_GROUPS = {chr(i): set() for i in range(ord("A"), ord("K"))}  # A تا J
BASKETBALL_PLAYERS = set()
VOLLEYBALL_PLAYERS = set()

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
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS time_slots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        sport TEXT,
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
        time_id INTEGER,
        date TEXT
    )""")
    conn.commit()


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
    # فقط وقتی تایم انتخاب شده اجازه ثبت شماره بده
    if "time_id" not in context.user_data:
        return


    # دریافت و نرمال‌سازی شماره ورودی کاربر
    raw_input = update.message.text.strip()
    phone = normalize_phone(raw_input)
    
    # بررسی اولیه فرمت (حالا با نرمال‌شده)
    if not phone or not phone.isdigit() or len(phone) < 10:
        await update.message.reply_text("❌ شماره نامعتبر است — لطفاً مثل: 09123456789 ارسال کنید")
        return


    today = datetime.now().strftime("%Y-%m-%d")
    time_id = context.user_data["time_id"]
    selected_sport = context.user_data["sport"]
    
    cursor.execute("""
        SELECT sport, group_code FROM time_slots WHERE id=?
    """, (time_id,))
    time_row = cursor.fetchone()
    
    if not time_row:
        await update.message.reply_text("❌ تایم نامعتبر")
        return
    
    time_sport, time_group = time_row


    if time_sport == "futsal":
        for g, members in FUTSAL_GROUPS.items():
            if phone in members and g != time_group:
                await update.message.reply_text("❌ شما قبلاً در گروه فوتسال دیگری ثبت شده‌اید")
                return
        FUTSAL_GROUPS[time_group].add(phone)
    
    elif time_sport == "basketball":
        BASKETBALL_PLAYERS.add(phone)
    
    elif time_sport == "volleyball":
        VOLLEYBALL_PLAYERS.add(phone)


    
    cursor.execute("""
    SELECT full_name, sport FROM players WHERE phone=?
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
    row = cursor.fetchone()
    if not row:
        await update.message.reply_text("❌ تایم انتخاب شده نامعتبر است، لطفاً دوباره انتخاب کنید")
        return
    cap = row[0]


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

        # تلاش برای یافتن توکن شماره (اولین توکنی که فقط عدد است و طول معقول دارد)
        phone_idx = None
        for i, tok in enumerate(args):
            tok_clean = tok.replace("+", "").replace("-", "").replace(" ", "")
            if tok_clean.isdigit() and len(tok_clean) >= 9:  # حداقل طول 9 (با 0/98)
                phone_idx = i
                break

        if phone_idx is None:
            await update.message.reply_text("❌ شماره معتبر پیدا نشد. لطفاً شماره را هم وارد کنید.")
            return

        # حالا نام = همه توکن‌های قبل از phone_idx
        name = " ".join(args[:phone_idx]).strip()
        phone = normalize_phone(args[phone_idx])
        # رشته باید بعد از شماره باشد (اگر وجود نداشته باشد خطا)
        if phone_idx + 1 >= len(args):
            await update.message.reply_text("❌ لطفاً رشته را هم وارد کنید (مثلاً futsal).")
            return

        sport = args[phone_idx + 1].lower()


        # اگر اسم خالی بود (مثلاً کاربر فرم phone first فرستاده) می‌گذاریم نام = شماره برای جلوگیری از خالی بودن
        if not name:
            name = phone

        # درج در دیتابیس با هندل کردن تکراری بودن شماره
        try:
            cursor.execute(
                "INSERT INTO players (full_name, phone, sport) VALUES (?,?,?)",
                (name, phone, sport)
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

    args = context.args
    if len(args) < 5:
        await update.message.reply_text(
            "❌ فرمت:\n/addtime YYYY-MM-DD sport start end capacity [GROUP]\n"
            "مثال فوتسال: /addtime 2025-01-10 futsal 18:00 19:00 15 A\n"
            "مثال بسکتبال: /addtime 2025-01-10 basketball 18:00 19:00 15"
        )
        return

    date, sport, start, end, cap = args[:5]
    group = args[5] if len(args) > 5 else None

    if sport == "futsal" and group not in FUTSAL_GROUPS:
        await update.message.reply_text("❌ گروه فوتسال باید بین A تا J باشد")
        return

    cursor.execute("""
        INSERT INTO time_slots (date, sport, start, end, capacity, group_code)
        VALUES (?,?,?,?,?,?)
    """, (date, sport, start, end, int(cap), group))
    conn.commit()

    await update.message.reply_text("✅ تایم اضافه شد")


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



async def add_futsal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_super(update.effective_user.id):
        return

    try:
        group, name, phone = context.args[0], context.args[1], context.args[2]
        phone = normalize_phone(phone)

        if group not in FUTSAL_GROUPS:
            await update.message.reply_text("❌ گروه باید بین A تا J باشد")
            return

        for g in FUTSAL_GROUPS.values():
            if phone in g:
                await update.message.reply_text("❌ این شماره قبلاً در گروه فوتسال دیگری ثبت شده")
                return

        FUTSAL_GROUPS[group].add(phone)
        await update.message.reply_text(f"✅ {name} به گروه فوتسال {group} اضافه شد")

    except:
        await update.message.reply_text("❌ فرمت: /add_futsal A نام 09123456789")




async def add_basketball(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_super(update.effective_user.id):
        return

    try:
        name, phone = context.args
        phone = normalize_phone(phone)

        if phone in BASKETBALL_PLAYERS:
            await update.message.reply_text("❌ قبلاً ثبت شده")
            return

        BASKETBALL_PLAYERS.add(phone)
        await update.message.reply_text("✅ بازیکن بسکتبال اضافه شد")
    except:
        await update.message.reply_text("❌ فرمت: /add_basketball نام 09123456789")





async def add_volleyball(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_super(update.effective_user.id):
        return

    try:
        name, phone = context.args
        phone = normalize_phone(phone)

        if phone in VOLLEYBALL_PLAYERS:
            await update.message.reply_text("❌ قبلاً ثبت شده")
            return

        VOLLEYBALL_PLAYERS.add(phone)
        await update.message.reply_text("✅ بازیکن والیبال اضافه شد")
    except:
        await update.message.reply_text("❌ فرمت: /add_volleyball نام 09123456789")




async def add_futsal_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_super(update.effective_user.id):
        return

    try:
        date, start, end, cap, group = context.args
        if group not in FUTSAL_GROUPS:
            await update.message.reply_text("❌ گروه نامعتبر")
            return

        cursor.execute("""
            INSERT INTO time_slots (date, sport, start, end, capacity, group_code)
            VALUES (?,?,?,?,?,?)
        """, (date, "futsal", start, end, int(cap), group))
        conn.commit()

        await update.message.reply_text("✅ تایم فوتسال اضافه شد")
    except:
        await update.message.reply_text(
            "❌ فرمت: /add_futsal_time YYYY-MM-DD 18:00 19:00 15 A"
        )




async def add_basketball_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_super(update.effective_user.id):
        return

    try:
        date, start, end, cap = context.args

        cursor.execute("""
            INSERT INTO time_slots (date, sport, start, end, capacity)
            VALUES (?,?,?,?,?)
        """, (date, "basketball", start, end, int(cap)))
        conn.commit()

        await update.message.reply_text("✅ تایم بسکتبال اضافه شد")
    except:
        await update.message.reply_text(
            "❌ فرمت: /add_basketball_time YYYY-MM-DD 18:00 19:00 15"
        )



async def add_volleyball_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_super(update.effective_user.id):
        return

    try:
        date, start, end, cap = context.args

        cursor.execute("""
            INSERT INTO time_slots (date, sport, start, end, capacity)
            VALUES (?,?,?,?,?)
        """, (date, "volleyball", start, end, int(cap)))
        conn.commit()

        await update.message.reply_text("✅ تایم والیبال اضافه شد")
    except:
        await update.message.reply_text(
            "❌ فرمت: /add_volleyball_time YYYY-MM-DD 18:00 19:00 15"
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
    app.add_handler(CommandHandler("add_futsal", add_futsal))
    app.add_handler(CommandHandler("add_basketball", add_basketball))
    app.add_handler(CommandHandler("add_volleyball", add_volleyball))
    app.add_handler(CommandHandler("add_futsal_time", add_futsal_time))
    app.add_handler(CommandHandler("add_basketball_time", add_basketball_time))
    app.add_handler(CommandHandler("add_volleyball_time", add_volleyball_time))


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
