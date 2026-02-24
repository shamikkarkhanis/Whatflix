import logging
import os
from logging.handlers import RotatingFileHandler

from dotenv import load_dotenv

from tmdb_api import TMDBClient


os.makedirs("logs", exist_ok=True)
log_filename = "logs/server.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        RotatingFileHandler(log_filename, maxBytes=5 * 1024 * 1024, backupCount=3),
        logging.StreamHandler(),
    ],
)

logger = logging.getLogger("recc-engine")
logger.info("Starting server. Logging to %s", log_filename)

load_dotenv()
tmdb_client = TMDBClient(os.getenv("TMDB_BEARER"))
