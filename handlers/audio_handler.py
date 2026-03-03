"""Telegram audio/voice message handler for the meeting assistant bot."""
import asyncio
import io
import logging
import os
import tempfile
from functools import partial
from typing import Optional

from telegram import InputFile, Message, Update
from telegram.constants import ChatType
from telegram.ext import ContextTypes

from services.stt_service import STTService
from services.llm_service import LLMService
from services.transcript_formatter import format_html, md_to_telegram_html

logger = logging.getLogger(__name__)


def make_handler(stt: STTService, llm: LLMService, group_name: str):
    """Return an async handler bound to the given services and group name."""
    return partial(_handle_audio, stt=stt, llm=llm, group_name=group_name)


async def _handle_audio(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    stt: STTService,
    llm: LLMService,
    group_name: str,
) -> None:
    """Process incoming audio/voice messages in the monitored group."""
    message: Optional[Message] = update.message
    if not message:
        return

    # Restrict to the designated meeting group only
    chat = message.chat
    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return
    if (chat.title or "").strip().lower() != group_name.strip().lower():
        return

    audio = message.voice or message.audio
    if not audio:
        return

    # Telegram bots can only download files up to 20 MB
    _MAX_BYTES = 20 * 1024 * 1024
    file_size = getattr(audio, "file_size", None)
    if file_size and file_size > _MAX_BYTES:
        await message.reply_text(
            f"❌ File quá lớn ({file_size // (1024*1024)} MB). Giới hạn tối đa là 20 MB."
        )
        return

    status_msg = await message.reply_text("⏳ Đang xử lý file âm thanh, vui lòng chờ...")
    tmp_path: Optional[str] = None

    try:
        # Download audio to a temporary file (hard 5-minute timeout)
        tg_file = await context.bot.get_file(audio.file_id)
        suffix = _get_suffix(message)
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp_path = tmp.name
        await asyncio.wait_for(tg_file.download_to_drive(tmp_path), timeout=300)
        logger.info("Downloaded audio to %s (suffix=%s)", tmp_path, suffix)

        # Step 1 – Speech-to-text
        await status_msg.edit_text("🎙️ Đang nhận dạng giọng nói sang văn bản...")
        transcript, tokens = await stt.transcribe(tmp_path)

        if not transcript:
            await status_msg.edit_text("❌ Không nhận dạng được nội dung. File âm thanh có thể bị lỗi hoặc quá ồn.")
            return

        logger.info("Transcription complete, %d chars", len(transcript))

        # Step 2 – Summarize (blocking SDK call offloaded to thread executor)
        await status_msg.edit_text("📝 Đang tóm tắt nội dung cuộc họp...")
        loop = asyncio.get_running_loop()
        summary = await loop.run_in_executor(None, llm.summarize, transcript)

        # Step 3 – Send transcript as styled HTML file
        html_content = format_html(transcript, tokens)
        html_buf = io.BytesIO(html_content.encode("utf-8"))
        await message.reply_document(
            document=InputFile(html_buf, filename="transcript.html"),
            caption="📄 Transcript đầy đủ (mở bằng trình duyệt để xem đẹp)",
        )

        # Step 4 – Send summary with Telegram HTML formatting.
        # md_to_telegram_html emits one complete HTML element per line, so
        # _split_text's newline-boundary splitting never breaks open tags.
        summary_html = md_to_telegram_html(summary)
        for chunk in _split_text(summary_html):
            await message.reply_text(chunk, parse_mode="HTML")

        await status_msg.delete()

    except Exception as exc:
        logger.error("Error processing audio message: %s", exc, exc_info=True)
        await status_msg.edit_text(f"❌ Lỗi xử lý: {exc}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


def _get_suffix(message: Message) -> str:
    """Determine file extension from Telegram message type."""
    if message.voice:
        return ".ogg"
    audio = message.audio
    if audio and audio.mime_type:
        ext = audio.mime_type.split("/")[-1]
        return f".{ext}"
    return ".mp3"


def _split_text(text: str, limit: int = 4096) -> list[str]:
    """Split long text into chunks that fit within Telegram's message limit.

    Preserves newlines so multi-line summaries remain readable.
    A single line longer than `limit` is kept as one chunk (unsplittable).
    """
    if len(text) <= limit:
        return [text]
    chunks, current = [], ""
    for line in text.splitlines(keepends=True):
        if current and len(current) + len(line) > limit:
            chunks.append(current)
            current = line
        else:
            current += line
    if current:
        chunks.append(current)
    return chunks
