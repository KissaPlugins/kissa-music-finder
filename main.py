
import os
import logging
import asyncio
from urllib.parse import quote_plus

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
AUDD_TOKEN = os.getenv("AUDD_TOKEN", "")


def music_links(query: str):
    q = quote_plus(query)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔎 YouTube", url=f"https://www.youtube.com/results?search_query={q}")],
        [InlineKeyboardButton("🎵 Spotify", url=f"https://open.spotify.com/search/{q}")],
        [InlineKeyboardButton("🍎 Apple Music", url=f"https://music.apple.com/search?term={q}")],
        [InlineKeyboardButton("🎧 SoundCloud", url=f"https://soundcloud.com/search?q={q}")],
        [InlineKeyboardButton("🌐 Google", url=f"https://www.google.com/search?q={q}+song")],
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎵 Привет! Я Kissa Music Finder.\n\n"
        "Пришли мне название песни, имя исполнителя, ссылку, "
        "или короткий аудио/видеофрагмент — попробуем найти музыку.\n\n"
        "Я ищу по нескольким музыкальным платформам. "
        "Для распознавания звука нужен настроенный API AudD."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Как пользоваться:\n"
        "• Напиши название песни или исполнителя.\n"
        "• Отправь ссылку на клип или музыкальную страницу.\n"
        "• Отправь аудио или видеофрагмент для распознавания.\n\n"
        "Если я не распознаю фрагмент, попробуй отправить более длинный и чёткий отрывок."
    )


async def recognize_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    media = message.audio or message.voice or message.video or message.document

    if not media:
        return

    if not AUDD_TOKEN:
        await message.reply_text(
            "🎧 Я получил файл, но распознавание звука ещё не настроено.\n"
            "Добавим AudD API-токен в настройки хостинга."
        )
        return

    await message.reply_text(
        "🎧 Файл получен. Распознавание через AudD подключим следующим шагом."
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    text = (message.text or "").strip()

    if not text:
        return

    if text.startswith(("http://", "https://")):
        query = text
        intro = "🔗 Вот где можно поискать музыку по ссылке:"
    else:
        query = text
        intro = f"🎵 Ищем музыку по запросу: {text}"

    await message.reply_text(
        intro,
        reply_markup=music_links(query),
        disable_web_page_preview=True,
    )


async def main():
    if not BOT_TOKEN:
        raise RuntimeError("Не задана переменная окружения BOT_TOKEN.")

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(
        MessageHandler(
            filters.AUDIO | filters.VOICE | filters.VIDEO | filters.Document.ALL,
            recognize_audio,
        )
    )
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)
    )

    logging.info("Kissa Music Finder запущен.")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    try:
        await asyncio.Event().wait()
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()


if __name__ == "__main__":
    asyncio.run(main())

