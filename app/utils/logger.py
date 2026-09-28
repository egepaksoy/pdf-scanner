import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import os


def configure_logging() -> Path:
    directory = Path(__file__).resolve().parents[2] / "logs"
    try:
        directory.mkdir(exist_ok=True)
        handler = RotatingFileHandler(directory / "app.log", maxBytes=2_000_000,
                                      backupCount=3, encoding="utf-8")
    except OSError:
        directory = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "StampChecker" / "logs"
        directory.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(directory / "app.log", maxBytes=2_000_000,
                                      backupCount=3, encoding="utf-8")
    logging.basicConfig(level=logging.INFO, handlers=[handler],
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s", force=True)
    logging.info("Uygulama açıldı")
    return directory
