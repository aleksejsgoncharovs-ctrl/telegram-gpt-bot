import os
import time
import random
from datetime import time as dtime
from zoneinfo import ZoneInfo

from openai import OpenAI
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Твой Telegram user ID
OWNER_TELEGRAM_ID = "563791610"

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN is missing")

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY is missing")

client = OpenAI(api_key=OPENAI_API_KEY)

BOT_TIMEZONE = ZoneInfo("Europe/Nicosia")

chat_active_state = {}
chat_histories = {}
chat_modes = {}
last_reply_time = {}
known_members = {}

MIN_REPLY_INTERVAL_SECONDS = 12

SYSTEM_PROMPT = """
Ты живой, уместный, дружелюбный и немного инициативный участник Telegram-чата.
Отвечай по-русски.
Пиши естественно и разговорно.
Не будь слишком формальным.
Не спамь.
Если участие не нужно — лучше промолчи.
Если обсуждение требует совета, комментария, шутки, уточнения или свежей информации — подключайся.
Если не уверен — так и скажи.
Отвечай внятно, без лишней воды.
"""

def is_owner(update: Update) -> bool:
    user = update.effective_user
    if not user:
        return False
    return str(user.id).strip() == OWNER_TELEGRAM_ID

def get_chat_mode(chat_id: str) -> str:
    return chat_modes.get(chat_id, "обычный")

def is_rate_limited(chat_id: str) -> bool:
    now = time.time()
    last_time = last_reply_time.get(chat_id, 0)
    return (now - last_time) < MIN_REPLY_INTERVAL_SECONDS

def mark_replied(chat_id: str) -> None:
    last_reply_time[chat_id] = time.time()

def get_display_name(user) -> str:
    if not user:
        return "друг"
    if user.first_name and user.last_name:
        return f"{user.first_name} {user.last_name}".strip()
    if user.first_name:
        return user.first_name.strip()
    if user.username:
        return f"@{user.username}"
    return "друг"

def remember_member(chat_id: str, user) -> None:
    if not user or user.is_bot:
        return
    if chat_id not in known_members:
        known_members[chat_id] = {}
    known_members[chat_id][str(user.id)] = get_display_name(user)

def get_member_names(chat_id: str):
    return list(known_members.get(chat_id, {}).values())

def fallback_greeting(chat_id: str, morning: bool = True) -> str:
    members = get_member_names(chat_id)
    names = ", ".join(members) if members else "друзья"

    morning_variants = [
        f"Доброе утро, {names}! Пусть день будет лёгким и удачным 🌞",
        f"Всем доброе утро, {names}! Хорошего настроения и отличного дня ✨",
        f"Доброе утро, {names}! Желаю продуктивного и приятного дня ☀️",
    ]

    night_variants = [
        f"Спокойной ночи, {names}! Пусть сны будут добрыми и тёплыми 🌙",
        f"Доброй ночи, {names}! Хорошего отдыха и сладких снов ✨",
        f"Спокойной ночи, {names}! Отдыхайте хорошо и набирайтесь сил 🌜",
    ]

    return random.choice(morning_variants if morning else night_variants)

def generate_dynamic_greeting(chat_id: str, morning: bool = True) -> str:
    members = get_member_names(chat_id)
    names = ", ".join(members) if members else "друзья"

    prompt = (
        f"Сгенерируй короткое, тёплое и живое сообщение для Telegram-чата. "
        f"Обратись к участникам: {names}. "
        f"{'Пожелай доброго утра и хорошего дня.' if morning else 'Пожелай спокойной ночи и хороших снов.'} "
        f"Сообщение должно быть 1-2 предложения, без длинной поэзии, без пафоса, естественное, дружелюбное, на русском языке."
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "system",
                    "content": "Ты пишешь короткие, тёплые и естественные сообщения для Telegram-чата на русском языке."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=120
        )
        text = response.choices[0].message.content.strip()
        return text if text else fallback_greeting(chat_id, morning=morning)
    except Exception:
        return fallback_greeting(chat_id, morning=morning)

def should_reply_in_group(user_message: str, user_message_lower: str, chat_id: str) -> bool:
    mode = get_chat_mode(chat_id)

    trigger_words = [
        "бот",
        "cepelin",
        "cepelini",
        "подскажи",
        "помоги",
        "что думаешь",
        "как",
        "почему",
        "зачем",
        "можешь",
        "объясни",
        "посоветуй",
        "найди",
        "посмотри",
        "актуально",
        "сейчас",
        "новости",
    ]

    has_question = "?" in user_message
    has_trigger = any(word in user_message_lower for word in trigger_words)
    is_long_message = len(user_message) >= 80

    if mode == "тихий":
        return has_question or has_trigger

    if mode == "обычный":
        if has_question or has_trigger or is_long_message:
            return True
        return random.random() < 0.18

    if mode == "активный":
        if has_question or has_trigger or is_long_message:
            return True
        return random.random() < 0.40

    return False

async def morning_greeting_job(context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(context.job.chat_id)
    text = generate_dynamic_greeting(chat_id, morning=True)
    await context.bot.send_message(chat_id=context.job.chat_id, text=text)

async def night_greeting_job(context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(context.job.chat_id)
    text = generate_dynamic_greeting(chat_id, morning=False)
    await context.bot.send_message(chat_id=context.job.chat_id, text=text)

def ensure_daily_jobs(application, chat_id: int):
    chat_id_str = str(chat_id)

    morning_job_name = f"morning_{chat_id_str}"
    night_job_name = f"night_{chat_id_str}"

    existing_morning = application.job_queue.get_jobs_by_name(morning_job_name)
    existing_night = application.job_queue.get_jobs_by_name(night_job_name)

    if not existing_morning:
        application.job_queue.run_daily(
            morning_greeting_job,
            time=dtime(hour=7, minute=0, tzinfo=BOT_TIMEZONE),
            name=morning_job_name,
            chat_id=chat_id,
        )

    if not existing_night:
        application.job_queue.run_daily(
            night_greeting_job,
            time=dtime(hour=22, minute=0, tzinfo=BOT_TIMEZONE),
            name=night_job_name,
            chat_id=chat_id,
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user = update.effective_user
    chat = update.effective_chat

    if not user or not chat:
        return

    if user.is_bot:
        return

    chat_id = str(chat.id)
    chat_type = chat.type
    user_id = str(user.id).strip()
    user_message = update.message.text.strip()
    user_message_lower = user_message.lower()

    remember_member(chat_id, user)

    if user_message_lower == "тестбот":
        await update.message.reply_text(
            f"Я вижу это сообщение.\n"
            f"chat_type={chat_type}\n"
            f"chat_id={chat_id}\n"
            f"user_id={user_id}\n"
            f"owner_match={is_owner(update)}\n"
            f"active={chat_active_state.get(chat_id, False)}\n"
            f"mode={get_chat_mode(chat_id)}\n"
            f"known_members={len(known_members.get(chat_id, {}))}"
        )
        return

    if chat_type == "private":
        active = True
    else:
        if is_owner(update):
            if user_message_lower == "старт":
                chat_active_state[chat_id] = True
                if chat_id not in chat_modes:
                    chat_modes[chat_id] = "обычный"

                ensure_daily_jobs(context.application, chat.id)

                await update.message.reply_text(
                    f"Бот активирован в этом чате.\n"
                    f"Режим: {get_chat_mode(chat_id)}\n"
                    f"Ежедневные приветствия включены: 07:00 и 22:00"
                )
                return

            if user_message_lower == "стоп":
                chat_active_state[chat_id] = False
                await update.message.reply_text("Бот остановлен в этом чате.")
                return

            if user_message_lower == "режим тихий":
                chat_modes[chat_id] = "тихий"
                await update.message.reply_text("Режим переключен на: тихий")
                return

            if user_message_lower == "режим обычный":
                chat_modes[chat_id] = "обычный"
                await update.message.reply_text("Режим переключен на: обычный")
                return

            if user_message_lower == "режим активный":
                chat_modes[chat_id] = "активный"
                await update.message.reply_text("Режим переключен на: активный")
                return

            if user_message_lower == "статус":
                await update.message.reply_text(
                    f"Активен: {chat_active_state.get(chat_id, False)}\n"
                    f"Режим: {get_chat_mode(chat_id)}\n"
                    f"История в памяти: {len(chat_histories.get(chat_id, []))} сообщений\n"
                    f"Известных участников: {len(known_members.get(chat_id, {}))}"
                )
                return

            if user_message_lower == "очистить память":
                chat_histories[chat_id] = []
                await update.message.reply_text("Память этого чата очищена.")
                return

            if user_message_lower == "кто в чате":
                members = get_member_names(chat_id)
                if not members:
                    await update.message.reply_text("Пока никого не запомнил в этом чате.")
                else:
                    await update.message.reply_text("Я знаю таких участников:\n" + "\n".join(members))
                return

        active = chat_active_state.get(chat_id, False)

    if not active:
        return

    if chat_type != "private":
        if is_rate_limited(chat_id):
            return
        if not should_reply_in_group(user_message, user_message_lower, chat_id):
            return

    if chat_id not in chat_histories:
        chat_histories[chat_id] = []

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(chat_histories[chat_id][-12:])
    messages.append({"role": "user", "content": user_message})

    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=messages,
            max_tokens=220
        )

        answer = response.choices[0].message.content

        chat_histories[chat_id].append({
            "role": "user",
            "content": user_message
        })
        chat_histories[chat_id].append({
            "role": "assistant",
            "content": answer
        })

        chat_histories[chat_id] = chat_histories[chat_id][-24:]

        await update.message.reply_text(answer)
        mark_replied(chat_id)

    except Exception as e:
        error_text = str(e)
        if "insufficient_quota" in error_text or "429" in error_text:
            await update.message.reply_text(
                "Сейчас не могу ответить: закончилась или ограничена квота OpenAI API."
            )
        else:
            await update.message.reply_text(f"Ошибка: {error_text[:300]}")

def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == "__main__":
    main()
