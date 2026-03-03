"""Unit tests for transcript_formatter: format_html and md_to_telegram_html."""
import pytest

from services.transcript_formatter import format_html, md_to_telegram_html


# ── md_to_telegram_html ────────────────────────────────────────────────────────

class TestMdToTelegramHtml:
    def test_heading_becomes_bold(self):
        assert md_to_telegram_html("## Tóm tắt") == "<b>Tóm tắt</b>"

    def test_h1_heading(self):
        assert md_to_telegram_html("# Title") == "<b>Title</b>"

    def test_inline_bold(self):
        assert md_to_telegram_html("**quan trọng**") == "<b>quan trọng</b>"

    def test_inline_italic(self):
        assert md_to_telegram_html("*ghi chú*") == "<i>ghi chú</i>"

    def test_inline_code(self):
        assert md_to_telegram_html("`code`") == "<code>code</code>"

    def test_horizontal_rule(self):
        result = md_to_telegram_html("---")
        assert "─" in result

    def test_bullet_list(self):
        assert md_to_telegram_html("- mục một") == "• mục một"

    def test_bullet_asterisk(self):
        assert md_to_telegram_html("* mục hai") == "• mục hai"

    def test_action_item_unchecked(self):
        assert md_to_telegram_html("- [ ] việc cần làm") == "☐ việc cần làm"

    def test_action_item_checked(self):
        assert md_to_telegram_html("- [x] hoàn thành") == "☑ hoàn thành"

    def test_action_item_checked_uppercase(self):
        assert md_to_telegram_html("- [X] done") == "☑ done"

    def test_html_special_chars_escaped(self):
        result = md_to_telegram_html("a & b <test>")
        assert "&amp;" in result
        assert "&lt;" in result
        assert "&gt;" in result

    def test_multiline_preserved(self):
        result = md_to_telegram_html("line1\nline2")
        assert result == "line1\nline2"

    def test_empty_string(self):
        assert md_to_telegram_html("") == ""

    def test_plain_text_unchanged(self):
        assert md_to_telegram_html("just plain text") == "just plain text"


# ── format_html ────────────────────────────────────────────────────────────────

class TestFormatHtml:
    def test_returns_html_string(self):
        result = format_html("Hello world", [])
        assert result.startswith("<!DOCTYPE html>")

    def test_title_in_output(self):
        result = format_html("text", [], title="Test Meeting")
        assert "Test Meeting" in result

    def test_plain_fallback_when_no_speakers(self):
        result = format_html("Nội dung cuộc họp", [])
        assert "Nội dung cuộc họp" in result
        assert '<pre>' in result

    def test_speaker_turns_rendered_when_diarization_present(self):
        tokens = [
            {"text": "Xin ", "speaker": "S1"},
            {"text": "chào", "speaker": "S1"},
            {"text": " bạn", "speaker": "S2"},
        ]
        result = format_html("Xin chào bạn", tokens)
        assert "S1" in result
        assert "S2" in result
        assert 'class="turn"' in result

    def test_speaker_colors_differ(self):
        tokens = [
            {"text": "A", "speaker": "S1"},
            {"text": "B", "speaker": "S2"},
        ]
        result = format_html("A B", tokens)
        # Two distinct speaker color entries should appear
        assert result.count('class="speaker"') == 2

    def test_html_escapes_speaker_text(self):
        tokens = [{"text": "<script>", "speaker": "S1"}]
        result = format_html("<script>", tokens)
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_no_tokens_uses_text_field(self):
        text = "Cuộc họp hôm nay rất hiệu quả."
        result = format_html(text, [])
        assert text in result

    def test_utf8_characters_preserved(self):
        result = format_html("Điện kích phần mềm", [])
        assert "Điện kích phần mềm" in result
