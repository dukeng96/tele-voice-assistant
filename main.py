"""Entry point for the Telegram Meeting Summary Assistant bot."""
import logging

from telegram.ext import ApplicationBuilder, MessageHandler, filters

import config
from handlers.audio_handler import make_handler
from services.llm_service import LLMService
from services.stt_service import STTService

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def main() -> None:
    stt = STTService(api_key=config.SONIOX_API_KEY, model=config.SONIOX_MODEL)
    llm = LLMService(
        api_key=config.VNPT_API_KEY,
        base_url=config.VNPT_BASE_URL,
        model=config.VNPT_MODEL,
    )

    app = ApplicationBuilder().token(config.TELEGRAM_BOT_TOKEN).build()

    audio_handler = make_handler(stt, llm, config.MEETING_GROUP_NAME)
    app.add_handler(MessageHandler(filters.AUDIO | filters.VOICE, audio_handler))

    logger.info(
        "Bot started. Monitoring group '%s' for audio messages.",
        config.MEETING_GROUP_NAME,
    )
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
