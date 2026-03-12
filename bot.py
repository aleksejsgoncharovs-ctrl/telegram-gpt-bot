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
    return bool(user and str(user.id) == str(OWNER_TELEGRAM_ID))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    chat = update.effective_chat
    chat_id = str(chat.id)
    chat_type = chat.type
    user_message = update.message.text.strip()
    user_message_lower = user_message.lower()

    # В личке бот всегда отвечает
    if chat_type == "private":
        active = True
    else:
        # Команды старт/стоп только от владельца
        if is_owner(update):
            if user_message_lower == "старт":
                chat_active_state[chat_id] = True
                await update.message.reply_text("Бот активирован в этом чате.")
                return

            if user_message_lower == "стоп":
                chat_active_state[chat_id] = False
                await update.message.reply_text("Бот остановлен в этом чате.")
                return

        active = chat_active_state.get(chat_id, False)

    if not active:
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
