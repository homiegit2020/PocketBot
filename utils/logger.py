import logging
import os
import sys
from datetime import datetime

LOG_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ERROR_LOG = os.path.join(LOG_DIR, "errors.log")
DEBUG_LOG = os.path.join(LOG_DIR, "bot_debug.log")


def _setup_logger() -> logging.Logger:
    fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    logger = logging.getLogger("pocketbot")
    logger.setLevel(logging.DEBUG)

    # Console handler — INFO and above
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter(fmt, datefmt))

    # Debug file handler
    dh = logging.FileHandler(DEBUG_LOG, encoding="utf-8")
    dh.setLevel(logging.DEBUG)
    dh.setFormatter(logging.Formatter(fmt, datefmt))

    # Error file handler
    eh = logging.FileHandler(ERROR_LOG, encoding="utf-8")
    eh.setLevel(logging.ERROR)
    eh.setFormatter(logging.Formatter(fmt, datefmt))

    logger.addHandler(ch)
    logger.addHandler(dh)
    logger.addHandler(eh)

    return logger


logger = _setup_logger()


def log(msg: str, level: str = "INFO") -> None:
    lvl = getattr(logging, level.upper(), logging.INFO)
    logger.log(lvl, msg)


def log_error(msg: str, exc_info: bool = False) -> None:
    logger.error(msg, exc_info=exc_info)


def log_debug(msg: str) -> None:
    logger.debug(msg)
