"""Formatting utilities: styled HTML transcript and Markdown-to-Telegram-HTML conversion."""
import html
import re

# Cycling color palette for distinct speaker turns
_SPEAKER_COLORS = ["#1a73e8", "#e53935", "#43a047", "#f57c00", "#8e24aa", "#00897b"]


# ── HTML transcript ────────────────────────────────────────────────────────────

def format_html(text: str, tokens: list[dict], title: str = "Meeting Transcript") -> str:
    """Build a styled HTML transcript page.

    Renders colored speaker turns when diarization data is available in tokens;
    falls back to a preformatted plain-text block otherwise.
    """
    has_speakers = any(t.get("speaker") for t in tokens)
    body = _render_speaker_turns(tokens) if has_speakers else _render_plain(text)
    return _html_page(html.escape(title), body)


def _render_speaker_turns(tokens: list[dict]) -> str:
    """Group tokens by speaker and build colored turn blocks."""
    speaker_colors: dict[str, str] = {}
    current_speaker: str | None = None
    current_parts: list[str] = []
    turns: list[tuple[str, str]] = []  # (speaker, assembled_text)

    for token in tokens:
        token_text = token.get("text", "")
        if not token_text:
            continue
        speaker = token.get("speaker") or "Unknown"

        if speaker not in speaker_colors:
            idx = len(speaker_colors) % len(_SPEAKER_COLORS)
            speaker_colors[speaker] = _SPEAKER_COLORS[idx]

        if speaker != current_speaker:
            if current_speaker is not None:
                # Tokens may have embedded leading spaces; concatenate directly
                turns.append((current_speaker, "".join(current_parts).strip()))
            current_speaker = speaker
            current_parts = [token_text]
        else:
            current_parts.append(token_text)

    if current_speaker and current_parts:
        turns.append((current_speaker, "".join(current_parts).strip()))

    parts = []
    for speaker, turn_text in turns:
        color = speaker_colors.get(speaker, "#555")
        parts.append(
            f'<div class="turn">'
            f'<span class="speaker" style="color:{color}">{html.escape(speaker)}</span>'
            f'<p class="text">{html.escape(turn_text)}</p>'
            f'</div>'
        )
    return "\n".join(parts)


def _render_plain(text: str) -> str:
    return f'<div class="plain"><pre>{html.escape(text)}</pre></div>'


def _html_page(safe_title: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{safe_title}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f0f2f5; color: #1a1a1a; padding: 24px 16px; }}
    .container {{ max-width: 860px; margin: 0 auto; }}
    h1 {{ font-size: 1.5rem; font-weight: 700; margin-bottom: 20px; border-bottom: 2px solid #ddd; padding-bottom: 10px; }}
    .turn {{ background: #fff; border-radius: 10px; padding: 14px 18px; margin: 10px 0; box-shadow: 0 1px 4px rgba(0,0,0,.08); }}
    .speaker {{ font-weight: 700; font-size: 0.78rem; text-transform: uppercase; letter-spacing: .06em; display: block; margin-bottom: 6px; }}
    .text {{ line-height: 1.65; font-size: 0.97rem; }}
    .plain pre {{ background: #fff; border-radius: 10px; padding: 18px; white-space: pre-wrap; word-break: break-word; line-height: 1.7; font-size: 0.95rem; font-family: inherit; box-shadow: 0 1px 4px rgba(0,0,0,.08); }}
  </style>
</head>
<body>
  <div class="container">
    <h1>{safe_title}</h1>
    {body}
  </div>
</body>
</html>"""


# ── Telegram HTML conversion ───────────────────────────────────────────────────

def md_to_telegram_html(md: str) -> str:
    """Convert Markdown to Telegram's supported HTML subset.

    Processes line by line. Content is HTML-escaped first to prevent injection,
    then Markdown syntax is converted to safe Telegram HTML tags.

    Supported: headings → <b>, **bold**, *italic*, `code`,
               --- separators, bullet lists, action items (- [ ] / - [x]).
    """
    result = []
    for line in md.split("\n"):
        safe = html.escape(line)

        # Headings (h1–h6) → bold text
        safe = re.sub(r"^#{1,6}\s+(.+)$", r"<b>\1</b>", safe)

        # Horizontal rules
        safe = re.sub(r"^(-{3,}|\*{3,}|_{3,})$", "─────────────────────", safe)

        # Action items — must run before generic bullet conversion
        safe = re.sub(r"^[-*]\s+\[x\]\s*", "☑ ", safe, flags=re.IGNORECASE)
        safe = re.sub(r"^[-*]\s+\[ \]\s*", "☐ ", safe)

        # Bullet lists
        safe = re.sub(r"^[-*]\s+", "• ", safe)

        # Inline formatting — bold runs before italic so ** is consumed first.
        # Malformed input (e.g. unclosed **) is passed through as-is (no crash).
        safe = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", safe)
        safe = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", safe)
        safe = re.sub(r"`(.+?)`", r"<code>\1</code>", safe)

        result.append(safe)
    return "\n".join(result)
