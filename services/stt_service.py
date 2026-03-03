"""Soniox Speech-to-Text service using async REST API."""
import asyncio
import logging
import httpx

logger = logging.getLogger(__name__)

_SONIOX_BASE = "https://api.soniox.com/v1"
_POLL_INTERVAL = 3.0  # seconds between status checks


class STTService:
    """Async wrapper around Soniox STT REST API."""

    def __init__(self, api_key: str, model: str = "stt-async-v4"):
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self._model = model

    async def transcribe(
        self, audio_path: str, language: str = "vi"
    ) -> tuple[str, list[dict]]:
        """Upload audio, transcribe asynchronously, return (transcript_text, tokens)."""
        async with httpx.AsyncClient(timeout=600) as client:
            file_id = await self._upload(client, audio_path)
            job_id = await self._create_job(client, file_id, language)
            try:
                await self._wait_for_completion(client, job_id)
                return await self._fetch_transcript(client, job_id)
            finally:
                await self._cleanup(client, job_id)

    async def _upload(self, client: httpx.AsyncClient, audio_path: str) -> str:
        """Upload audio file to Soniox Files API, return file ID."""
        with open(audio_path, "rb") as f:
            resp = await client.post(
                f"{_SONIOX_BASE}/files",
                headers=self._headers,
                files={"file": f},
            )
        resp.raise_for_status()
        data = resp.json()
        if "id" not in data:
            raise ValueError(f"Unexpected Soniox /files response: {data}")
        logger.debug("Uploaded file, id=%s", data["id"])
        return data["id"]

    async def _create_job(
        self, client: httpx.AsyncClient, file_id: str, language: str
    ) -> str:
        """Create an async transcription job, return job ID."""
        payload = {
            "model": self._model,
            "file_id": file_id,
            "language_hints": [language],
            "enable_speaker_diarization": True,
        }
        resp = await client.post(
            f"{_SONIOX_BASE}/transcriptions",
            headers={**self._headers, "Content-Type": "application/json"},
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
        if "id" not in data:
            raise ValueError(f"Unexpected Soniox /transcriptions response: {data}")
        logger.debug("Created transcription job, id=%s", data["id"])
        return data["id"]

    async def _wait_for_completion(
        self, client: httpx.AsyncClient, job_id: str
    ) -> None:
        """Poll until transcription job reaches 'completed' or raises on error."""
        while True:
            resp = await client.get(
                f"{_SONIOX_BASE}/transcriptions/{job_id}",
                headers=self._headers,
            )
            resp.raise_for_status()
            data = resp.json()
            status = data.get("status", "")

            if status == "completed":
                logger.debug("Transcription completed, job_id=%s", job_id)
                return
            if status == "error":
                raise RuntimeError(
                    f"Soniox transcription failed: {data.get('error', 'unknown error')}"
                )

            logger.debug("Transcription status=%s, waiting...", status)
            await asyncio.sleep(_POLL_INTERVAL)

    async def _fetch_transcript(
        self, client: httpx.AsyncClient, job_id: str
    ) -> tuple[str, list[dict]]:
        """Retrieve transcript text and tokens from completed job.

        Returns (text, clean_tokens) where:
        - text is the pre-assembled clean transcript (preferred) or token fallback
        - clean_tokens are filtered tokens retaining speaker/timing metadata
        """
        resp = await client.get(
            f"{_SONIOX_BASE}/transcriptions/{job_id}/transcript",
            headers=self._headers,
        )
        resp.raise_for_status()
        data = resp.json()

        tokens = data.get("tokens", [])
        clean_tokens = [
            t for t in tokens
            if t.get("text") and t["text"] not in ("<end>", "<eos>")
        ]

        # Prefer the pre-assembled text field — avoids character-level join artifacts
        # that break Vietnamese (e.g. "Đ i ện  k ích" instead of "Điện kích")
        text = data.get("text", "").strip()
        if not text and clean_tokens:
            # Fallback: join word-level tokens with a space
            text = " ".join(t["text"] for t in clean_tokens).strip()

        return text, clean_tokens

    async def _cleanup(self, client: httpx.AsyncClient, job_id: str) -> None:
        """Delete transcription job to free Soniox storage quota."""
        try:
            await client.delete(
                f"{_SONIOX_BASE}/transcriptions/{job_id}",
                headers=self._headers,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to cleanup Soniox job %s: %s", job_id, exc)
