"""VNPT LLM service for Vietnamese meeting summarization."""
import logging
from openai import OpenAI

logger = logging.getLogger(__name__)

# ── Summarization prompt ──────────────────────────────────────────────────────
# Best practices applied:
#   1. Clear expert role → improves output quality and tone
#   2. Explicit language instruction (Vietnamese)
#   3. Structured output with labeled sections → easy to scan
#   4. Action items with ownership/deadline placeholders → actionable output
#   5. Low temperature (0.4) → consistent, factual summaries
# ─────────────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = (
    "Bạn là chuyên gia phân tích cuộc họp chuyên nghiệp. "
    "Nhiệm vụ của bạn là đọc transcript và tạo bản tóm tắt ngắn gọn, "
    "súc tích, đầy đủ thông tin theo đúng cấu trúc yêu cầu. "
    "Luôn trả lời hoàn toàn bằng tiếng Việt. "
    "Không bịa đặt thông tin không có trong transcript."
)

_USER_PROMPT_TEMPLATE = """\
Dưới đây là transcript của một cuộc họp. Hãy tóm tắt theo cấu trúc sau:

## 📋 TÓM TẮT CUỘC HỌP

**1. Thông tin chung**
- Chủ đề: (xác định từ nội dung, hoặc ghi "Không rõ")
- Thành phần tham dự: (liệt kê nếu được đề cập)

**2. Nội dung chính đã thảo luận**
(Liệt kê các điểm quan trọng theo thứ tự ưu tiên, mỗi điểm 1-2 câu)

**3. Quyết định đã đưa ra**
(Các quyết định cụ thể; ghi "Không có quyết định rõ ràng" nếu không có)

**4. Đầu việc cần thực hiện (Action Items)**
- [ ] [Mô tả đầu việc] — Người phụ trách: [tên/bộ phận] — Deadline: [ngày/thời hạn]
(Nếu không rõ người phụ trách hoặc deadline, ghi "Không rõ")

**5. Vấn đề còn tồn đọng / Cần theo dõi**
(Vấn đề chưa giải quyết, cần làm rõ hoặc theo dõi tiếp)

---
**TRANSCRIPT:**
{transcript}
"""


class LLMService:
    """Wrapper around VNPT LLM API (OpenAI-compatible) for meeting summarization."""

    def __init__(self, api_key: str, base_url: str, model: str):
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._model = model

    def summarize(self, transcript: str) -> str:
        """Generate a structured Vietnamese summary from a meeting transcript."""
        logger.debug("Sending transcript to LLM for summarization, model=%s", self._model)
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": _USER_PROMPT_TEMPLATE.format(transcript=transcript)},
            ],
            max_tokens=4096,
            temperature=0.4,   # Low temp → consistent, factual output
            top_p=0.9,
            stream=False,
        )
        summary = (response.choices[0].message.content or "").strip()
        if not summary:
            raise RuntimeError("LLM returned empty response — possible API error or quota exceeded")
        logger.debug("Summary generated, length=%d chars", len(summary))
        return summary
