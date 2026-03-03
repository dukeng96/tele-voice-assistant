"""Application configuration loaded from environment variables."""
import os
from dotenv import load_dotenv

load_dotenv()

def _require(key: str) -> str:
    val = os.getenv(key)
    if not val:
        raise EnvironmentError(f"Missing required env var: {key}")
    return val


TELEGRAM_BOT_TOKEN: str = _require("TELEGRAM_BOT_TOKEN")
SONIOX_API_KEY: str = _require("SONIOX_API_KEY")
VNPT_API_KEY: str = _require("VNPT_API_KEY")

MEETING_GROUP_NAME: str = os.getenv("MEETING_GROUP_NAME", "meeting")

VNPT_BASE_URL: str = "https://assistant-stream.vnpt.vn/v1/"
VNPT_MODEL: str = "llm-medium-v4"
SONIOX_API_BASE: str = "https://api.soniox.com/v1"
SONIOX_MODEL: str = "stt-async-v4"
SONIOX_POLL_INTERVAL: float = 3.0  # seconds between status polls
