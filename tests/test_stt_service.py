"""Unit tests for STTService using mocked httpx responses."""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch, mock_open

from services.stt_service import STTService


@pytest.fixture
def stt():
    return STTService(api_key="test-key")


class TestUpload:
    @pytest.mark.asyncio
    async def test_upload_returns_file_id(self, stt):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"id": "file-123"}

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp

        with patch("builtins.open", mock_open(read_data=b"audio")):
            result = await stt._upload(mock_client, "audio.mp3")

        assert result == "file-123"

    @pytest.mark.asyncio
    async def test_upload_raises_on_missing_id(self, stt):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"error": "unauthorized"}

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp

        with patch("builtins.open", mock_open(read_data=b"audio")):
            with pytest.raises(ValueError, match="Unexpected Soniox /files"):
                await stt._upload(mock_client, "audio.mp3")


class TestCreateJob:
    @pytest.mark.asyncio
    async def test_create_job_returns_job_id(self, stt):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"id": "job-456"}

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp

        result = await stt._create_job(mock_client, "file-123", "vi")
        assert result == "job-456"

    @pytest.mark.asyncio
    async def test_create_job_raises_on_missing_id(self, stt):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"error": "invalid_model"}

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp

        with pytest.raises(ValueError, match="Unexpected Soniox /transcriptions"):
            await stt._create_job(mock_client, "file-123", "vi")


class TestWaitForCompletion:
    @pytest.mark.asyncio
    async def test_returns_on_completed(self, stt):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"status": "completed"}

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp

        # Should not raise
        await stt._wait_for_completion(mock_client, "job-456")

    @pytest.mark.asyncio
    async def test_raises_on_error_status(self, stt):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"status": "error", "error": "bad audio"}

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp

        with pytest.raises(RuntimeError, match="Soniox transcription failed"):
            await stt._wait_for_completion(mock_client, "job-456")

    @pytest.mark.asyncio
    async def test_polls_until_completed(self, stt):
        responses = [
            {"status": "pending"},
            {"status": "processing"},
            {"status": "completed"},
        ]
        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            mock_resp = MagicMock()
            mock_resp.raise_for_status = MagicMock()
            mock_resp.json.return_value = responses[min(call_count, len(responses) - 1)]
            call_count += 1
            return mock_resp

        mock_client = AsyncMock()
        mock_client.get.side_effect = side_effect

        with patch("asyncio.sleep", new_callable=AsyncMock):
            await stt._wait_for_completion(mock_client, "job-456")

        assert call_count == 3


class TestFetchTranscript:
    @pytest.mark.asyncio
    async def test_prefers_text_field_over_tokens(self, stt):
        """Pre-assembled text field is used — avoids character-level join artifacts."""
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "text": "Điện kích phần mềm",
            "tokens": [
                {"text": "Đ", "speaker": "S1"},
                {"text": "i", "speaker": "S1"},
                {"text": "ện", "speaker": "S1"},
            ],
        }
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp

        text, tokens = await stt._fetch_transcript(mock_client, "job-456")
        assert text == "Điện kích phần mềm"
        assert len(tokens) == 3  # clean tokens returned for speaker formatting

    @pytest.mark.asyncio
    async def test_falls_back_to_token_join_when_no_text_field(self, stt):
        """When text field is absent, fall back to joining token texts with spaces."""
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "tokens": [
                {"text": "Xin"},
                {"text": "chào"},
                {"text": "<end>"},
            ]
        }
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp

        text, tokens = await stt._fetch_transcript(mock_client, "job-456")
        assert text == "Xin chào"
        assert len(tokens) == 2  # <end> sentinel filtered out

    @pytest.mark.asyncio
    async def test_empty_response_returns_empty_string_and_no_tokens(self, stt):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"text": "", "tokens": []}
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp

        text, tokens = await stt._fetch_transcript(mock_client, "job-456")
        assert text == ""
        assert tokens == []
