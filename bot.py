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

ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")  # set this in Railway Variables


USERS_FILE = "users.json"
SCHEDULE_FILE = "schedule.json"

tf = TimezoneFinder()

# =========================
# TZ choices (как раньше)
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

# =========================
# LINKS / BUTTONS
# =========================
INSTRUCTION_VIDEO_URL = "https://youtu.be/fMtloIsalSY"
GRATITUDE_BUTTON_LABEL = "🙏 Практика Благодарения"
HELP_BUTTON_LABEL = "🆘 Помощь / Связаться"
LOCATION_BUTTON_LABEL = "📍 Отправить геолокацию"

# =========================
# WINDOWS (local user time)
# =========================
MORNING_SEND_HOUR = 5
MORNING_SEND_MIN_FROM = 55
MORNING_SEND_MIN_TO = 59

EVENING_SEND_HOUR = 19
EVENING_SEND_MIN_FROM = 55
EVENING_SEND_MIN_TO = 59

GRATITUDE_SEND_HOUR = 21
GRATITUDE_SEND_MIN = 20

# =========================
# Onboarding follow-up (после инструкции)
# =========================
AFTER_INSTRUCTION_TEXT = """До встречи завтра на первом дне марафона!

Не забудь сегодня лечь по-раньше (до 22:00)
Ставь будильник на 5:55
Встречаемся завтра в 6:00!"""

# =========================
# FULL GRATITUDE TEXT (полный, без урезаний)
# =========================
GRATITUDE_TEXT = """Вечерняя практика благодарения.

Многие люди живут и не замечают в повседневной жизни поводов для благодарения, а поводов для благодарения каждый день более чем предостаточно. Если мы проснулись с утра, то это уже повод поблагодарить Вселенную за ещё один день. Да, да, поблагодарить. Мы порой воспринимаем жизнь как что-то должное, а следующий день как само собой разумеющееся, в то время как многие люди, закрыв глаза вечером, не просыпаются, и уходят в другое измерение (умирают). Вначале бывает сложно начать благодарить. Некоторые даже говорят: «Всё что у меня есть в жизни – я сам достиг, мне никто не помогал, зачем мне кого-то благодарить?» Однако если мы чего-то и достигли, то это точно не без помощи Бога (Вселенной), сложившимся обстоятельствам и другим людям.

И чем больше благодарности появляется у нас внутри, тем щедрее Вселенная начинает нас одаривать еще большими благами. Благодарить можно и нужно за все, что есть в нашей жизни, в том числе и свое тело за то, что оно позволяет познавать этот мир и получать от него удовольствие.

Для практики благодарения нужно взять блокнот/тетрадь/обычный лист бумаги и сверху написать БЛАГОДАРЮ и ниже минимум 5 пунктов (можно и больше), за что мы благодарны этому дню 🙏:
1.
2.
3.
4.
5.

Ниже, на второй половине листа, пишем «Я МОЛОДЕЦ (УМНИЦА)» и минимум 5 пунктов, за что мы можем себя похвалить:
1.
2.
3.
4.
5.

Как показывает практика, людям с низкой самооценкой, бывает непросто найти поводы, за что стоит себя похвалить. Однако с практикой все приходит. Даже эта простая привычка ежедневной практики Благодарности и Похвалы способна в значительной степени улучшить нашу жизнь.

Если во время практики нам приходят мысли того, что можно сделать, то ниже создаем список дел на завтрашний день. Имея план на следующий день, мозгу (нашему телу) намного проще будет проснуться с утра, чтобы начать новую интересную страницу своей жизни – день.

«День – это маленькая жизнь, и надо прожить её так, будто ты должен умереть сейчас, а тебе неожиданно подарили ещё сутки». – Максим Горький.

На самом деле успех в жизни прост – нужно научиться проживать правильно лишь один день – сегодняшний, а завтра (если оно наступит) – завтрашний. И так изо дня в день, мы улучшаем себя и свою жизнь. Если мы сможем улучшить себя всего на 1% в день, то за год это будет 365%! А если при этом учесть ещё сложный процент, то это ещё во много раз больше!
"""

# =========================
# Helpers: JSON
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
    u.setdefault("start_date", None)  # we will set it at first TZ selection (tomorrow by default)

    u.setdefault("last_sent_morning_local_date", None)
    u.setdefault("last_sent_evening_local_date", None)
    u.setdefault("last_sent_bonus_local_date", None)
    u.setdefault("last_sent_gratitude_local_date", None)

    # gating gratitude by evening send
    u.setdefault("evening_sent_today", False)


def now_local(tzname: str) -> datetime:
    return datetime.now(ZoneInfo(tzname))


def is_in_window(now: datetime, hour: int, min_from: int, min_to: int) -> bool:
    return now.hour == hour and min_from <= now.minute <= min_to


def parse_iso_date(iso: str) -> date:
    return datetime.fromisoformat(iso).date()


def calc_day_number(u: Dict[str, Any], local_today: date) -> int:
    """
    Day 1 happens on start_date.
    start_date is set to *tomorrow* by default when user first selects TZ.
    """
    try:
        if not u.get("start_date"):
            return 1
        start = parse_iso_date(u["start_date"])
    except Exception:
        return 1

    delta = (local_today - start).days

    # ✅ FIX: если старт ещё не наступил — день 0 (ничего не отправляем)
    if delta < 0:
        return 0

    return delta + 1


def tz_from_label(label: str) -> Optional[str]:
    for name, tz in TZ_CHOICES:
        if label == name:
            return tz
    return None


def compute_default_start_date(tzname: str) -> str:
    """
    По умолчанию старт марафона = завтра (локальная дата пользователя),
    чтобы "первое утро" было Днём 1.
    """
    d = now_local(tzname).date() + timedelta(days=1)
    return d.isoformat()


def set_user_timezone(users: Dict[str, Dict[str, Any]], chat_id: str, tzname: str) -> None:
    """
    Sets timezone. If user sets TZ for the first time (tz was None),
    start_date becomes tomorrow by default.
    """
    ensure_user(users, chat_id)
    u = users[chat_id]
    first_time = (u.get("tz") is None)

    u["tz"] = tzname

    if first_time or not u.get("start_date"):
        u["start_date"] = compute_default_start_date(tzname)

    # When (re)starting as new user, keep these sane
    if first_time:
        u["last_sent_morning_local_date"] = None
        u["last_sent_evening_local_date"] = None
        u["last_sent_bonus_local_date"] = None
        u["last_sent_gratitude_local_date"] = None
        u["evening_sent_today"] = False


# =========================
# Keyboards
# =========================
def build_tz_keyboard() -> ReplyKeyboardMarkup:
    labels = [name for (name, _tz) in TZ_CHOICES]
    rows = [labels[i:i + 2] for i in range(0, len(labels), 2)]
    rows.append([KeyboardButton(LOCATION_BUTTON_LABEL, request_location=True)])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, one_time_keyboard=True)


def _chunk2(items: List[str]) -> List[List[str]]:
    return [items[i:i + 2] for i in range(0, len(items), 2)]


def build_main_keyboard(schedule: Dict[str, Any]) -> ReplyKeyboardMarkup:
    """
    Постоянное меню:
    tutorial_buttons (без Help),
    потом Благодарение,
    потом Help.
    """
    buttons = schedule.get("tutorial_buttons", [])
    labels = [b.get("label") for b in buttons if b.get("label")]

    labels_no_help = [x for x in labels if x != HELP_BUTTON_LABEL]

    rows: List[List[str]] = []
    rows.extend(_chunk2(labels_no_help))
    rows.append([GRATITUDE_BUTTON_LABEL])

    if HELP_BUTTON_LABEL in labels:
        rows.append([HELP_BUTTON_LABEL])

    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


# =========================
# Senders
# =========================
async def send_instruction_and_followup(bot, chat_id: str) -> None:
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️ Смотреть инструкцию", url=INSTRUCTION_VIDEO_URL)],
    ])
    await bot.send_message(
        chat_id=chat_id,
        text="✅ Посмотри короткую инструкцию и стартуем 👇",
        reply_markup=kb,
        disable_web_page_preview=False,
    )
    await bot.send_message(
        chat_id=chat_id,
        text=AFTER_INSTRUCTION_TEXT,
        disable_web_page_preview=True,
    )


async def send_gratitude(bot, chat_id: str, schedule: Dict[str, Any]) -> None:
    await bot.send_message(
        chat_id=chat_id,
        text=GRATITUDE_TEXT,
        reply_markup=build_main_keyboard(schedule),
        disable_web_page_preview=True,
    )


async def send_block(bot, chat_id: str, text: str, url: Optional[str]) -> None:
    inline_rows = []
    if url:
        inline_rows.append([InlineKeyboardButton("▶️ Открыть видео", url=url)])

    await bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=InlineKeyboardMarkup(inline_rows) if inline_rows else None,
        disable_web_page_preview=True,
    )


def get_day_content(schedule: Dict[str, Any], day_number: int) -> Dict[str, Any]:
    days = schedule.get("days", [])
    idx = day_number - 1
    if 0 <= idx < len(days):
        return days[idx] or {}
    return {}


# =========================
# Handlers
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    users = load_json(USERS_FILE, {})
    ensure_user(users, chat_id)
    save_json(USERS_FILE, users)

    schedule = load_json(SCHEDULE_FILE, {})
    u = users[chat_id]

    if not u.get("tz"):
        await update.message.reply_text(
            "Выбери часовой пояс 👇\n"
            f"Если не нашли свою зону — нажми «{LOCATION_BUTTON_LABEL}».",
            reply_markup=build_tz_keyboard(),
        )
        return

    await update.message.reply_text(
        "Ты в марафоне ✅",
        reply_markup=build_main_keyboard(schedule),
    )


async def tz_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Выбери часовой пояс 👇\n"
        f"Если не нашли свою зону — нажми «{LOCATION_BUTTON_LABEL}».",
        reply_markup=build_tz_keyboard(),
    )

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Admin-only: delete one user by chat_id from users.json
    Usage: /reset <chat_id>
    """
    if not ADMIN_CHAT_ID or str(update.effective_chat.id) != str(ADMIN_CHAT_ID):
        return

    if not context.args:
        await update.message.reply_text("Использование: /reset <chat_id>")
        return

    target_id = str(context.args[0]).strip()
    users = load_json(USERS_FILE, {})

    if target_id in users:
        del users[target_id]
        save_json(USERS_FILE, users)
        await update.message.reply_text(f"✅ Пользователь {target_id} сброшен.")
    else:
        await update.message.reply_text("ℹ️ Пользователь не найден.")


async def on_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    loc = update.message.location
    if not loc:
        return

    chat_id = str(update.effective_chat.id)

    tzname = tf.timezone_at(lat=loc.latitude, lng=loc.longitude) or tf.closest_timezone_at(
        lat=loc.latitude, lng=loc.longitude
    )

    if not tzname:
        await update.message.reply_text(
            "Не смог определить таймзону 😕 Попробуй ещё раз или выбери вручную из списка.",
            reply_markup=build_tz_keyboard(),
        )
        return

    users = load_json(USERS_FILE, {})
    set_user_timezone(users, chat_id, tzname)
    save_json(USERS_FILE, users)

    schedule = load_json(SCHEDULE_FILE, {})
    start_d = users[chat_id].get("start_date", "")
    await update.message.reply_text(
        f"Таймзона установлена ✅ ({tzname})\nСтарт марафона: {start_d} (День 1).",
        reply_markup=build_main_keyboard(schedule),
    )

    # ✅ инструкция + сообщение "до встречи завтра..."
    await send_instruction_and_followup(context.bot, chat_id)


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    chat_id = str(update.effective_chat.id)

    schedule = load_json(SCHEDULE_FILE, {})
    users = load_json(USERS_FILE, {})
    ensure_user(users, chat_id)
    u = users[chat_id]

    # 1) Gratitude button
    if text == GRATITUDE_BUTTON_LABEL:
        await send_gratitude(context.bot, chat_id, schedule)
        return

    # 2) TZ choice by label
    tzname = tz_from_label(text)
    if tzname:
        set_user_timezone(users, chat_id, tzname)
        save_json(USERS_FILE, users)

        start_d = users[chat_id].get("start_date", "")
        await update.message.reply_text(
            f"Таймзона установлена ✅ ({tzname})\nСтарт марафона: {start_d} (День 1).",
            reply_markup=build_main_keyboard(schedule),
        )

        # ✅ ВАЖНО: инструкция + сообщение "до встречи завтра..."
        await send_instruction_and_followup(context.bot, chat_id)
        return

    # 3) tutorial_buttons open url
    for b in schedule.get("tutorial_buttons", []):
        if text == b.get("label") and b.get("url"):
            await update.message.reply_text(b["url"], reply_markup=build_main_keyboard(schedule))
            return

    # If user hasn't set TZ yet, guide them back
    if not u.get("tz"):
        await update.message.reply_text(
            "Сначала выбери часовой пояс 👇\n"
            f"Если не нашли свою зону — нажми «{LOCATION_BUTTON_LABEL}».",
            reply_markup=build_tz_keyboard(),
        )
        return


# =========================
# Scheduler tick
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

        # ✅ FIX: до даты старта не отправляем ничего (кроме онбординга)
        if day_number == 0:
            continue

        day_content = get_day_content(schedule, day_number)

        # Reset evening flag shortly after midnight
        if now.hour == 0 and now.minute < 5:
            if u.get("evening_sent_today"):
                u["evening_sent_today"] = False
                changed = True

        # Morning window
        if is_in_window(now, MORNING_SEND_HOUR, MORNING_SEND_MIN_FROM, MORNING_SEND_MIN_TO):
            if u.get("last_sent_morning_local_date") != today_iso:
                morning = (day_content or {}).get("morning")
                if morning and morning.get("text"):
                    await send_block(
                        context.bot,
                        chat_id,
                        morning.get("text"),
                        morning.get("url"),
                    )
                    u["last_sent_morning_local_date"] = today_iso
                    changed = True

        # Evening window
        if is_in_window(now, EVENING_SEND_HOUR, EVENING_SEND_MIN_FROM, EVENING_SEND_MIN_TO):
            if u.get("last_sent_evening_local_date") != today_iso:
                evening = (day_content or {}).get("evening")
                if evening and evening.get("text"):
                    await send_block(
                        context.bot,
                        chat_id,
                        evening.get("text"),
                        evening.get("url"),
                    )
                    u["last_sent_evening_local_date"] = today_iso
                    u["evening_sent_today"] = True
                    changed = True

                # Bonus (day 8) in evening window (если есть)
                bonus = schedule.get("bonus", {})
                bonus_day = bonus.get("day_number")
                if bonus_day == day_number:
                    bonus_evening = (bonus or {}).get("evening")
                    if bonus_evening and bonus_evening.get("text"):
                        if u.get("last_sent_bonus_local_date") != today_iso:
                            await send_block(
                                context.bot,
                                chat_id,
                                bonus_evening.get("text"),
                                bonus_evening.get("url"),
                            )
                            u["last_sent_bonus_local_date"] = today_iso
                            changed = True

        # Gratitude at 21:20 ONLY if evening was sent today
        if now.hour == GRATITUDE_SEND_HOUR and now.minute == GRATITUDE_SEND_MIN:
            if u.get("last_sent_gratitude_local_date") != today_iso and u.get("evening_sent_today") is True:
                await send_gratitude(context.bot, chat_id, schedule)
                u["last_sent_gratitude_local_date"] = today_iso
                changed = True

    if changed:
        save_json(USERS_FILE, users)


# =========================
# Main
# =========================
def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN is not set")

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tz", tz_cmd))

    app.add_handler(CommandHandler("reset", reset))
    # LOCATION must be before TEXT
    app.add_handler(MessageHandler(filters.LOCATION, on_location))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    # tick every 20 seconds to not miss exact 21:20
    app.job_queue.run_repeating(tick, interval=20, first=5)

    app.run_polling()


if __name__ == "__main__":
    main()