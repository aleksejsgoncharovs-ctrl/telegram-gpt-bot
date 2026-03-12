import os
from openai import OpenAI
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OWNER_TELEGRAM_ID = os.getenv("OWNER_TELEGRAM_ID", "")

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN is missing")

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY is missing")

client = OpenAI(api_key=OPENAI_API_KEY)

chat_active_state = {}
chat_histories = {}

def is_owner(update: Update) -> bool:
    user = update.effective_user
    if not user:
        return False
    return str(user.id) == str(OWNER_TELEGRAM_ID)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    chat_id = str(update.effective_chat.id)
    user_message = update.message.text.strip()
    user_message_lower = user_message.lower()

    if OWNER_TELEGRAM_ID and is_owner(update):
        if user_message_lower == "старт":
            chat_active_state[chat_id] = True
            await update.message.reply_text("Бот активирован.")
            return

        if user_message_lower == "стоп":
            chat_active_state[chat_id] = False
            await update.message.reply_text("Бот остановлен.")
            return

    if not chat_active_state.get(chat_id, False):
        return

    if chat_id not in chat_histories:
        chat_histories[chat_id] = []

    chat_histories[chat_id].append({
        "role": "user",
        "content": user_message
    })

    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=chat_histories[chat_id][-10:]
        )

        answer = response.choices[0].message.content

        chat_histories[chat_id].append({
            "role": "assistant",
            "content": answer
        })

        await update.message.reply_text(answer)

    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")

def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == "__main__":
    main()
