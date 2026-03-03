"""Unit tests for the audio message handler."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call

from handlers.audio_handler import _split_text, _get_suffix, make_handler


# ── _split_text ───────────────────────────────────────────────────────────────

class TestSplitText:
    def test_short_text_unchanged(self):
        assert _split_text("hello", limit=100) == ["hello"]

    def test_splits_on_limit(self):
        # Each line is 51 chars (50 + newline). Limit=100 means 51+51=102 > 100,
        # so each line becomes its own chunk → 3 chunks for 3 lines.
        line = "a" * 50 + "\n"
        text = line * 3          # 153 chars total
        chunks = _split_text(text, limit=100)
        assert len(chunks) == 3
        assert all(len(c) <= 100 for c in chunks)
        # Newlines are preserved
        assert all(c.endswith("\n") for c in chunks)

    def test_splits_fits_two_lines(self):
        # Two 40-char lines (41 each with \n) fit in 100 → 1 chunk; third → new chunk
        line = "b" * 40 + "\n"
        text = line * 3          # 3 * 41 = 123 chars
        chunks = _split_text(text, limit=100)
        assert len(chunks) == 2
        assert all(len(c) <= 100 for c in chunks)

    def test_empty_string(self):
        assert _split_text("") == [""]

    def test_single_line_over_limit(self):
        # A line with no newlines cannot be split — returned as one chunk
        text = "x" * 200
        chunks = _split_text(text, limit=100)
        assert chunks == [text]


# ── _get_suffix ───────────────────────────────────────────────────────────────

class TestGetSuffix:
    def test_voice_message_returns_ogg(self):
        msg = MagicMock()
        msg.voice = MagicMock()
        msg.audio = None
        assert _get_suffix(msg) == ".ogg"

    def test_audio_with_mime(self):
        msg = MagicMock()
        msg.voice = None
        msg.audio = MagicMock(mime_type="audio/mpeg")
        assert _get_suffix(msg) == ".mpeg"

    def test_audio_without_mime_defaults_mp3(self):
        msg = MagicMock()
        msg.voice = None
        msg.audio = MagicMock(mime_type=None)
        assert _get_suffix(msg) == ".mp3"


# ── make_handler ──────────────────────────────────────────────────────────────

class TestMakeHandler:
    def test_returns_callable(self):
        stt = MagicMock()
        llm = MagicMock()
        handler = make_handler(stt, llm, "meeting")
        assert callable(handler)


# ── File size guard ───────────────────────────────────────────────────────────

class TestFileSizeGuard:
    @pytest.mark.asyncio
    async def test_rejects_files_over_20mb(self):
        """Handler must reject audio files larger than 20 MB."""
        from handlers.audio_handler import _handle_audio

        audio = MagicMock()
        audio.file_size = 21 * 1024 * 1024  # 21 MB

        message = MagicMock()
        message.chat.type = "supergroup"
        message.chat.title = "meeting"
        message.voice = None
        message.audio = audio
        message.reply_text = AsyncMock(return_value=MagicMock())

        update = MagicMock()
        update.message = message

        context = MagicMock()

        stt = MagicMock()
        llm = MagicMock()

        await _handle_audio(update, context, stt=stt, llm=llm, group_name="meeting")

        # reply_text should be called with the size-limit error, not the "processing" message
        call_args = message.reply_text.call_args[0][0]
        assert "quá lớn" in call_args
        # STT should never be called
        stt.transcribe.assert_not_called()

    @pytest.mark.asyncio
    async def test_ignores_non_meeting_groups(self):
        """Handler should silently ignore messages from other groups."""
        from handlers.audio_handler import _handle_audio

        message = MagicMock()
        message.chat.type = "supergroup"
        message.chat.title = "random-group"
        message.reply_text = AsyncMock()

        update = MagicMock()
        update.message = message

        stt = MagicMock()
        llm = MagicMock()

        await _handle_audio(
            update, MagicMock(), stt=stt, llm=llm, group_name="meeting"
        )

        message.reply_text.assert_not_called()
        stt.transcribe.assert_not_called()
