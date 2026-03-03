import json
import os
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from typing import Any, Dict, Optional, List, Tuple

from timezonefinder import TimezoneFinder
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
)
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

TOKEN = os.getenv("BOT_TOKEN")

USERS_FILE = "users.json"
SCHEDULE_FILE = "schedule.json"

tf = TimezoneFinder()

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

INSTRUCTION_VIDEO_URL = "https://youtu.be/fMtloIsalSY"
GRATITUDE_BUTTON_LABEL = "🙏 Практика Благодарения"
HELP_BUTTON_LABEL = "🆘 Помощь / Связаться"
LOCATION_BUTTON_LABEL = "📍 Отправить геолокацию"

MORNING_SEND_HOUR = 5
MORNING_SEND_MIN_FROM = 55
MORNING_SEND_MIN_TO = 59

EVENING_SEND_HOUR = 19
EVENING_SEND_MIN_FROM = 55
EVENING_SEND_MIN_TO = 59

GRATITUDE_SEND_HOUR = 21
GRATITUDE_SEND_MIN = 20

AFTER_INSTRUCTION_TEXT = """До встречи завтра на первом дне марафона!

Не забудь сегодня лечь по-раньше (до 22:00)
Ставь будильник на 5:55
Встречаемся завтра в 6:00!"""

# =========================
# JSON helpers
# =========================
def load_json(path: str, default: Any) -> Any:
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path: str, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# =========================
# Users
# =========================
def ensure_user(users: Dict[str, Dict[str, Any]], chat_id: str) -> None:
    if chat_id not in users:
        users[chat_id] = {}

    u = users[chat_id]
    u.setdefault("tz", None)
    u.setdefault("start_date", None)
    u.setdefault("last_sent_morning_local_date", None)
    u.setdefault("last_sent_evening_local_date", None)
    u.setdefault("last_sent_bonus_local_date", None)
    u.setdefault("last_sent_gratitude_local_date", None)
    u.setdefault("evening_sent_today", False)


def now_local(tzname: str) -> datetime:
    return datetime.now(ZoneInfo(tzname))


def is_in_window(now: datetime, hour: int, min_from: int, min_to: int) -> bool:
    return now.hour == hour and min_from <= now.minute <= min_to


def parse_iso_date(iso: str) -> date:
    return datetime.fromisoformat(iso).date()


# 🔥 ИЗМЕНЕНО ЗДЕСЬ
def calc_day_number(u: Dict[str, Any], local_today: date) -> int:
    if not u.get("start_date"):
        return 1

    try:
        start = parse_iso_date(u["start_date"])
    except Exception:
        return 1

    delta = (local_today - start).days

    if delta < 0:
        return 0  # марафон ещё не начался

    return delta + 1


def compute_default_start_date(tzname: str) -> str:
    d = now_local(tzname).date() + timedelta(days=1)
    return d.isoformat()


def set_user_timezone(users: Dict[str, Dict[str, Any]], chat_id: str, tzname: str) -> None:
    ensure_user(users, chat_id)
    u = users[chat_id]
    first_time = (u.get("tz") is None)

    u["tz"] = tzname

    if first_time or not u.get("start_date"):
        u["start_date"] = compute_default_start_date(tzname)


# =========================
# Scheduler
# =========================
async def tick(context: ContextTypes.DEFAULT_TYPE):
    users = load_json(USERS_FILE, {})
    schedule = load_json(SCHEDULE_FILE, {})
    changed = False

    for chat_id, u in list(users.items()):
        ensure_user(users, chat_id)
        tzname = u.get("tz")
        if not tzname:
            continue

        try:
            now = now_local(tzname)
            today = now.date()
            today_iso = today.isoformat()
        except Exception:
            continue

        day_number = calc_day_number(u, today)

        # 🔥 ИЗМЕНЕНО ЗДЕСЬ — блокируем отправку до старта
        if day_number == 0:
            continue

        day_content = schedule.get("days", [])[day_number - 1] if day_number - 1 < len(schedule.get("days", [])) else {}

        if is_in_window(now, MORNING_SEND_HOUR, MORNING_SEND_MIN_FROM, MORNING_SEND_MIN_TO):
            if u.get("last_sent_morning_local_date") != today_iso:
                morning = day_content.get("morning")
                if morning:
                    await context.bot.send_message(chat_id, morning.get("text"))
                    u["last_sent_morning_local_date"] = today_iso
                    changed = True

        if is_in_window(now, EVENING_SEND_HOUR, EVENING_SEND_MIN_FROM, EVENING_SEND_MIN_TO):
            if u.get("last_sent_evening_local_date") != today_iso:
                evening = day_content.get("evening")
                if evening:
                    await context.bot.send_message(chat_id, evening.get("text"))
                    u["last_sent_evening_local_date"] = today_iso
                    changed = True

    if changed:
        save_json(USERS_FILE, users)


def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN is not set")

    app = Application.builder().token(TOKEN).build()
    app.job_queue.run_repeating(tick, interval=20, first=5)
    app.run_polling()


if __name__ == "__main__":
    main()