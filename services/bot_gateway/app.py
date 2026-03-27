# telegram bot - routes messages to the rag and vision services
# also keeps track of conversation history per user

import os, sys, io, logging
from collections import defaultdict

import httpx
from openai import OpenAI
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import config

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

RAG_SERVICE_URL = config.RAG_SERVICE_URL
VISION_SERVICE_URL = config.VISION_SERVICE_URL
openai_client = OpenAI(api_key=config.OPENAI_API_KEY)

# store last few messages per user
user_history = defaultdict(list)
MAX_HISTORY = 3


def add_to_history(user_id, role, content):
    user_history[user_id].append({"role": role, "content": content})
    # keep only last N exchanges
    if len(user_history[user_id]) > MAX_HISTORY * 2:
        user_history[user_id] = user_history[user_id][-(MAX_HISTORY * 2):]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hey! I'm a GenAI bot that can:\n\n"
        "- Answer questions from my knowledge base\n"
        "- Describe images you send me\n\n"
        "Commands:\n"
        "/ask <question> - ask something\n"
        "/image - send or reply to a photo\n"
        "/summarize - recap our conversation\n"
        "/help - show commands"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Commands:\n\n"
        "/ask <question> - I'll search through my docs and answer\n"
        "/image - send a photo or reply to one, I'll describe it\n"
        "/summarize - shows what we talked about recently\n"
        "/help - this message\n\n"
        "You can also just send a photo directly and I'll auto-describe it.\n"
        "I remember the last 3 interactions for follow-up questions."
    )


async def ask_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args) if context.args else ""
    if not query:
        await update.message.reply_text("usage: /ask <your question>")
        return

    user_id = update.effective_user.id
    add_to_history(user_id, "user", query)
    await update.message.reply_text("searching...")

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{RAG_SERVICE_URL}/ask",
                json={"query": query, "history": user_history.get(user_id, [])},
            )
            response.raise_for_status()
            data = response.json()

        answer = data["answer"]
        sources = data.get("sources", [])

        # show which docs the answer came from
        source_text = ""
        if sources:
            source_names = list(set(s["source"] for s in sources))
            source_text = "\n\nSources: " + ", ".join(source_names)

        add_to_history(user_id, "assistant", answer)
        await update.message.reply_text(f"{answer}{source_text}")

    except httpx.HTTPStatusError as e:
        logger.error(f"rag error: {e}")
        await update.message.reply_text("something went wrong, try again")
    except httpx.ConnectError:
        logger.error("cant reach rag service")
        await update.message.reply_text("rag service is down, try again later")


async def image_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # check if theres a photo - either in the message or as a reply
    photo = None
    if update.message.reply_to_message and update.message.reply_to_message.photo:
        photo = update.message.reply_to_message.photo[-1]
    elif update.message.photo:
        photo = update.message.photo[-1]

    if not photo:
        await update.message.reply_text("send a photo with /image or reply to a photo with /image")
        return

    await update.message.reply_text("analyzing image...")

    try:
        file = await photo.get_file()
        image_bytes = await file.download_as_bytearray()

        async with httpx.AsyncClient(timeout=60.0) as client:
            files = {"file": ("image.jpg", io.BytesIO(image_bytes), "image/jpeg")}
            response = await client.post(f"{VISION_SERVICE_URL}/describe", files=files)
            response.raise_for_status()
            data = response.json()

        caption = data["caption"]
        tags = data["tags"]
        tags_str = ", ".join(f"#{t.replace(' ', '_')}" for t in tags)

        user_id = update.effective_user.id
        add_to_history(user_id, "user", "[sent an image]")
        add_to_history(user_id, "assistant", f"Caption: {caption} | Tags: {tags_str}")

        await update.message.reply_text(f"Caption: {caption}\n\nTags: {tags_str}")

    except httpx.ConnectError:
        logger.error("cant reach vision service")
        await update.message.reply_text("vision service is down, try later")
    except Exception as e:
        logger.error(f"image error: {e}")
        await update.message.reply_text("couldnt process the image, try again")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # if someone just sends a photo without /image, describe it anyway
    await image_command(update, context)


async def summarize_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    history = user_history.get(user_id, [])

    if not history:
        await update.message.reply_text("no conversation yet. try /ask or send a photo first")
        return

    await update.message.reply_text("generating summary...")

    # format the raw conversation log
    history_text = "\n".join(
        f"{'You' if h['role'] == 'user' else 'Bot'}: {h['content']}" for h in history
    )

    # use openai to write a short description of what was discussed
    try:
        completion = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are given a conversation between a user and a bot. "
                               "Write a short 2-3 sentence description of what was discussed. "
                               "Keep it simple.",
                },
                {"role": "user", "content": f"Conversation:\n\n{history_text}"},
            ],
            temperature=0.3,
            max_tokens=150,
        )
        description = completion.choices[0].message.content
    except Exception as e:
        logger.error(f"summarize failed: {e}")
        description = "(couldnt generate description)"

    reply = (
        f"Summary ({len(history)} messages):\n\n"
        f"Description:\n{description}\n\n"
        f"---\n"
        f"Conversation log:\n\n{history_text}"
    )
    await update.message.reply_text(reply)


async def error_handler(update, context):
    import telegram.error
    if isinstance(context.error, telegram.error.Conflict):
        logger.warning("conflict - another bot instance might be running")
    else:
        logger.error(f"error: {context.error}")


def main():
    token = config.TELEGRAM_BOT_TOKEN
    if not token:
        print("ERROR: TELEGRAM_BOT_TOKEN not set!")
        sys.exit(1)

    # clear any stale telegram session from previous run
    import httpx as _httpx
    try:
        _httpx.post(f"https://api.telegram.org/bot{token}/deleteWebhook",
                     params={"drop_pending_updates": "true"}, timeout=10)
        _httpx.post(f"https://api.telegram.org/bot{token}/getUpdates",
                     json={"offset": -1, "timeout": 0}, timeout=10)
    except:
        pass  # not critical if this fails

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("ask", ask_command))
    app.add_handler(CommandHandler("image", image_command))
    app.add_handler(CommandHandler("summarize", summarize_command))
    app.add_handler(MessageHandler(filters.PHOTO & ~filters.COMMAND, handle_photo))
    app.add_error_handler(error_handler)

    logger.info("bot started")
    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
        poll_interval=2.0,
        timeout=10,
    )


if __name__ == "__main__":
    main()
