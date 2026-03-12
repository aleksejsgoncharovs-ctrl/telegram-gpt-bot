import os
import time
import random
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

# Включен ли бот в конкретном чате
chat_active_state = {}

# История сообщений по каждому чату
chat_histories = {}

# Режимы по каждому чату: тихий / обычный / активный
chat_modes = {}

# Антиспам: время последнего ответа в чате
last_reply_time = {}

# Минимальная пауза между ответами бота в группе
MIN_REPLY_INTERVAL_SECONDS = 12

SYSTEM_PROMPT = """
Ты живой, уместный, дружелюбный и немного инициативный участник Telegram-чата.
Отвечай по-русски.
Пиши естественно и разговорно.
Не будь слишком формальным.
Не спамь.
Если участие не нужно — лучше промолчи.
Если обсуждение требует полезного совета, комментария, шутки или уточнения — подключайся.
Не выдумывай факты.
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

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user = update.effective_user
    chat = update.effective_chat

    if not user or not chat:
        return

    # Игнорируем сообщения других ботов
    if user.is_bot:
        return

    chat_id = str(chat.id)
    chat_type = chat.type
    user_id = str(user.id).strip()
    user_message = update.message.text.strip()
    user_message_lower = user_message.lower()

    # Диагностика
    if user_message_lower == "тестбот":
        await update.message.reply_text(
            f"Я вижу это сообщение.\n"
            f"chat_type={chat_type}\n"
            f"chat_id={chat_id}\n"
            f"user_id={user_id}\n"
            f"owner_env={OWNER_TELEGRAM_ID}\n"
            f"owner_match={is_owner(update)}\n"
            f"active={chat_active_state.get(chat_id, False)}\n"
            f"mode={get_chat_mode(chat_id)}"
        )
        return

    # Личка: бот всегда активен
    if chat_type == "private":
        active = True
    else:
        # Управление только владельцем
        if is_owner(update):
            if user_message_lower == "старт":
                chat_active_state[chat_id] = True
                if chat_id not in chat_modes:
                    chat_modes[chat_id] = "обычный"
                await update.message.reply_text(
                    f"Бот активирован в этом чате.\n"
                    f"Режим: {get_chat_mode(chat_id)}"
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
                    f"История в памяти: {len(chat_histories.get(chat_id, []))} сообщений"
                )
                return

            if user_message_lower == "очистить память":
                chat_histories[chat_id] = []
                await update.message.reply_text("Память этого чата очищена.")
                return

        active = chat_active_state.get(chat_id, False)

    if not active:
        return

    # В группе не отвечаем слишком часто
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

        # Ограничиваем память
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
