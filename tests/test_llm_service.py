"""Unit tests for LLMService."""
import pytest
from unittest.mock import MagicMock, patch

from services.llm_service import LLMService


@pytest.fixture
def llm():
    with patch("services.llm_service.OpenAI") as mock_openai_cls:
        instance = mock_openai_cls.return_value
        svc = LLMService(
            api_key="test-key",
            base_url="https://example.com/v1/",
            model="llm-large-v4",
        )
        svc._client = instance
        return svc


def _make_response(content: str):
    """Helper: build a fake OpenAI chat completion response."""
    choice = MagicMock()
    choice.message.content = content
    resp = MagicMock()
    resp.choices = [choice]
    return resp


class TestSummarize:
    def test_returns_summary(self, llm):
        llm._client.chat.completions.create.return_value = _make_response(
            "## Tóm tắt\nNội dung cuộc họp..."
        )
        result = llm.summarize("Xin chào, đây là transcript.")
        assert "Tóm tắt" in result

    def test_raises_on_empty_content(self, llm):
        llm._client.chat.completions.create.return_value = _make_response("")
        with pytest.raises(RuntimeError, match="LLM returned empty response"):
            llm.summarize("some transcript")

    def test_raises_on_none_content(self, llm):
        llm._client.chat.completions.create.return_value = _make_response(None)
        with pytest.raises(RuntimeError, match="LLM returned empty response"):
            llm.summarize("some transcript")

    def test_uses_correct_model(self, llm):
        llm._client.chat.completions.create.return_value = _make_response("Summary")
        llm.summarize("transcript")
        call_kwargs = llm._client.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "llm-large-v4"
        assert call_kwargs["stream"] is False

    def test_includes_transcript_in_prompt(self, llm):
        llm._client.chat.completions.create.return_value = _make_response("Summary")
        llm.summarize("unique-transcript-content-xyz")
        call_kwargs = llm._client.chat.completions.create.call_args.kwargs
        user_msg = next(m for m in call_kwargs["messages"] if m["role"] == "user")
        assert "unique-transcript-content-xyz" in user_msg["content"]
