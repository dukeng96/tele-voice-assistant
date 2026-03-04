"""Entry point for the Telegram Meeting Summary Assistant bot."""
import logging

from telegram.ext import ApplicationBuilder, MessageHandler, filters
from telegram.request import HTTPXRequest

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

    # Configure HTTP client with extended timeouts and connection pooling
    # read_timeout: time to wait for data chunks (critical for large files)
    #               Set to 10 min to accommodate 3 retries @ 3 min each
    # connect_timeout: time to establish connection
    # write_timeout: time to send data
    # pool_timeout: time to get connection from pool
    # connection_pool_size: number of connections to keep in pool for reuse
    request = HTTPXRequest(
        read_timeout=600.0,     # 10 minutes for reading large files with retries
        connect_timeout=30.0,   # 30 seconds to connect
        write_timeout=30.0,     # 30 seconds to write
        pool_timeout=10.0,      # 10 seconds for connection pool
        connection_pool_size=4, # 1 primary + 3 for retries/concurrent operations
    )

    app = (
        ApplicationBuilder()
        .token(config.TELEGRAM_BOT_TOKEN)
        .request(request)
        .build()
    )

    audio_handler = make_handler(stt, llm, config.MEETING_GROUP_NAME)
    app.add_handler(MessageHandler(filters.AUDIO | filters.VOICE, audio_handler))

    logger.info(
        "Bot started. Monitoring group '%s' for audio messages.",
        config.MEETING_GROUP_NAME,
    )
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
