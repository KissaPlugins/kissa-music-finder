import os
import logging
import asyncio
from urllib.parse import quote_plus

from shazamio import Shazam
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
MAX_FILE_SIZE = 20 * 1024 * 1024


def music_links(query: str):
    q = quote_plus(query)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔎 YouTube", url=f"https://www.youtube.com/results?search_query={q}")],
        [InlineKeyboardButton("🎵 Spotify", url=f"https://open.spotify.com/search/{q}")],
        [InlineKeyboardButton("🍎 Apple Music", url=f"https://music.apple.com/search?term={q}")],
        [InlineKeyboardButton("🎧 SoundCloud", url=f"https://soundcloud.com/search?q={q}")],
        [InlineKeyboardButton("💿 Яндекс Музыка", url=f"https://music.yandex.ru/search?text={q}")],
        [InlineKeyboardButton("🌐 Google", url=f"https://www.google.com/search?q={q}+song")],
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎵 Привет! Я Kissa Music Finder.\n\n"
        "Пришли название песни или исполнителя, ссылку, аудио, голосовое "
        "или короткий видеофрагмент — попробую найти музыку.\n\n"
        "Распознавание использует ShazamIO без API-ключа. Это бесплатная "
        "библиотека, но распознавание зависит от доступности сервиса Shazam."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Как пользоваться:\n"
        "• Напиши название песни или исполнителя.\n"
        "• Отправь ссылку на клип или музыкальную страницу.\n"
        "• Отправь аудио, голосовое или короткий видеофрагмент.\n\n"
        "Лучше всего работает чёткий фрагмент примерно 5–12 секунд. "
        "Если видео не обработается, отправь звук отдельно."
    )


async def recognize_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    media = message.audio or message.voice or message.video or message.document

    if not media:
        return

    mime_type = getattr(media, "mime_type", None) or ""
    if message.document and not (
        mime_type.startswith("audio/")
        or mime_type.startswith("video/")
        or mime_type in ("application/ogg", "application/octet-stream")
    ):
        await message.reply_text("Пришли аудио, голосовое или видеофайл.")
        return

    if media.file_size and media.file_size > MAX_FILE_SIZE:
        await message.reply_text("Файл слишком большой. Пришли файл меньше 20 МБ.")
        return

    status = await message.reply_text("🎧 Слушаю фрагмент и ищу совпадение…")
    try:
        telegram_file = await context.bot.get_file(media.file_id)
        audio_bytes = bytes(await telegram_file.download_as_bytearray())
        if not audio_bytes:
            await status.edit_text("Не удалось прочитать файл. Попробуй отправить его ещё раз.")
            return

        async with Shazam() as shazam:
            result = await shazam.recognize(audio_bytes)

        track = result.get("track") if isinstance(result, dict) else None
        if not track:
            await status.edit_text(
                "😕 Не удалось определить песню. Попробуй другой фрагмент "
                "длиной 5–12 секунд с более чистым звуком. Если это видео, "
                "пришли аудио отдельно."
            )
            return

        title = (track.get("title") or "Неизвестное название").strip()
        artist = (track.get("subtitle") or "").strip()
        query = f"{artist} {title}".strip()
        text = f"🎵 Похоже, нашёл песню!\n\n**{title}**"
        if artist:
            text += f"\nИсполнитель: {artist}"
        await status.edit_text(
            text,
            parse_mode="Markdown",
            reply_markup=music_links(query),
            disable_web_page_preview=True,
        )
    except Exception:
        logging.exception("Ошибка распознавания аудио")
        await status.edit_text(
            "⚠️ Не получилось обработать этот файл. Попробуй отправить "
            "короткий аудиофрагмент или голосовое сообщение. Видео может "
            "не поддерживаться напрямую на хостинге."
        )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    text = (message.text or "").strip()

    if not text:
        return

    if text.startswith(("http://", "https://")):
        intro = "🔗 Вот где можно поискать музыку по ссылке:"
    else:
        intro = f"🎵 Ищем музыку по запросу: {text}"

    await message.reply_text(
        intro,
        reply_markup=music_links(text),
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
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

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
