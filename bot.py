import json
import os
import random
import re
import asyncio
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from typing import Optional, List, Tuple, Dict, Any

from timezonefinder import TimezoneFinder
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

TOKEN = os.getenv("BOT_TOKEN")
USERS_FILE = "users.json"
SCHEDULE_FILE = "schedule.json"

tf = TimezoneFinder()

# =========================
# ВРЕМЯ
# =========================
MORNING_SEND_HOUR = 5
MORNING_SEND_MIN_FROM = 55
MORNING_SEND_MIN_TO = 59

EVENING_SEND_HOUR = 19
EVENING_SEND_MIN_FROM = 55
EVENING_SEND_MIN_TO = 59

EVENING_REMINDER_HOUR = 21
EVENING_REMINDER_MIN_FROM = 20
EVENING_REMINDER_MIN_TO = 25

# =========================
# ТАЙМЗОНЫ (без Астаны)
# =========================
TZ_CHOICES: List[Tuple[str, str]] = [
    ("Portugal (Lisbon)", "Europe/Lisbon"),
    ("UK (London)", "Europe/London"),
    ("Germany (Berlin)", "Europe/Berlin"),
    ("Poland (Warsaw)", "Europe/Warsaw"),
    ("Ukraine (Kyiv)", "Europe/Kyiv"),
    ("Egypt (Cairo)", "Africa/Cairo"),
    ("Turkey (Istanbul)", "Europe/Istanbul"),

    ("Moscow (MSK)", "Europe/Moscow"),
    ("Russia — Ural (Yekaterinburg)", "Asia/Yekaterinburg"),
    ("Russia — Omsk", "Asia/Omsk"),
    ("Kazakhstan (Almaty)", "Asia/Almaty"),

    ("UAE (Dubai)", "Asia/Dubai"),
    ("USA East (New York)", "America/New_York"),
    ("USA West (Los Angeles)", "America/Los_Angeles"),
]

BADGES = [
    (1, "🌱 Первые шаги"),
    (2, "🔥 Два дня силы"),
    (3, "⚡ Три дня энергии"),
    (5, "🛡️ Железная дисциплина"),
    (7, "🏆 Герой недели"),
    (8, "🎁 Бонус-мастер"),
]

PRAISE_LINES = [
    "Дисциплина — это любовь к себе в действии.",
    "Ты сейчас строишь характер.",
    "Маленький шаг. Большая сила.",
    "Сегодня ты выиграл у «потом».",
]

YOUTUBE_RE = re.compile(r"(https?://(?:www\.)?(?:youtube\.com|youtu\.be)/\S+)", re.IGNORECASE)

# =========================
# JSON
# =========================
def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# =========================
# USERS
# =========================
def ensure_user(users, chat_id):
    if chat_id not in users:
        users[chat_id] = {}

    u = users[chat_id]
    u.setdefault("start_date", datetime.utcnow().date().isoformat())
    u.setdefault("tz", None)

    u.setdefault("last_sent_morning_local_date", None)
    u.setdefault("last_sent_evening_local_date", None)
    u.setdefault("last_sent_reminder_local_date", None)
    u.setdefault("bonus_sent", False)

    u.setdefault("completed_parts", [])
    u.setdefault("last_done_day", None)
    u.setdefault("streak", 0)
    u.setdefault("best_streak", 0)
    u.setdefault("points", 0)
    u.setdefault("badges", [])


# =========================
# TIME
# =========================
def now_local(tzname):
    return datetime.now(ZoneInfo(tzname))


def local_today(tzname):
    return now_local(tzname).date()


def calc_day_number(start_date_iso, tzname):
    start = datetime.strptime(start_date_iso, "%Y-%m-%d").date()
    return (local_today(tzname) - start).days + 1


def is_in_window(now, hour, min_from, min_to):
    return now.hour == hour and min_from <= now.minute <= min_to


# =========================
# KEYBOARDS
# =========================
def build_tz_keyboard():
    labels = [name for (name, _tz) in TZ_CHOICES]
    rows = [labels[i:i + 2] for i in range(0, len(labels), 2)]
    rows.append(["📍 Определить по локации"])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


def build_tutorial_keyboard(schedule):
    buttons = schedule.get("tutorial_buttons", [])
    labels = [b.get("label") for b in buttons if b.get("label")]
    rows = [labels[i:i + 2] for i in range(0, len(labels), 2)]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


def tz_from_label(label):
    for name, tz in TZ_CHOICES:
        if label == name:
            return tz
    return None


# =========================
# VIDEO MESSAGE
# =========================
async def send_video_message(bot, chat_id, text, url, day, part):
    buttons = []
    if url:
        buttons.append([InlineKeyboardButton("▶️ Открыть видео", url=url)])
    buttons.append([InlineKeyboardButton("✔️ Я сделал(а) практику", callback_data=f"done_{part}_{day}")])

    await bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=InlineKeyboardMarkup(buttons),
        disable_web_page_preview=True,
    )


# =========================
# COMMANDS
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    users = load_json(USERS_FILE, {})
    ensure_user(users, chat_id)
    save_json(USERS_FILE, users)

    if not users[chat_id].get("tz"):
        await update.message.reply_text(
            "Выбери часовой пояс 👇",
            reply_markup=build_tz_keyboard(),
        )
        return

    schedule = load_json(SCHEDULE_FILE, {})
    await update.message.reply_text(
        "Ты в марафоне ✅",
        reply_markup=build_tutorial_keyboard(schedule),
    )


async def tz_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Выбери часовой пояс 👇",
        reply_markup=build_tz_keyboard(),
    )


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if text == "📍 Определить по локации":
        await update.message.reply_text("Пришли геолокацию 📍")
        return

    tzname = tz_from_label(text)
    if tzname:
        chat_id = str(update.effective_chat.id)
        users = load_json(USERS_FILE, {})
        ensure_user(users, chat_id)
        users[chat_id]["tz"] = tzname
        save_json(USERS_FILE, users)

        schedule = load_json(SCHEDULE_FILE, {})
        await update.message.reply_text(
            f"Таймзона установлена ✅ ({text})",
            reply_markup=build_tutorial_keyboard(schedule),
        )
        return

    schedule = load_json(SCHEDULE_FILE, {})
    for b in schedule.get("tutorial_buttons", []):
        if text == b.get("label"):
            await update.message.reply_text(b["url"])
            return


async def done_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    chat_id = str(query.message.chat.id)
    _, part, day = query.data.split("_")
    day = int(day)

    users = load_json(USERS_FILE, {})
    ensure_user(users, chat_id)
    u = users[chat_id]

    key = f"{part}:{day}"
    if key in u["completed_parts"]:
        return

    u["completed_parts"].append(key)
    u["points"] += 10
    save_json(USERS_FILE, users)

    await query.edit_message_text("✔️ Засчитано! +10 очков")


# =========================
# MAIN
# =========================
def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN is not set")

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tz", tz_cmd))

    app.add_handler(CallbackQueryHandler(done_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    app.run_polling()


if __name__ == "__main__":
    main()