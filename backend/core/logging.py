import logging
import sys
from typing import Any


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """Configure structured logging for the application."""
    logger = logging.getLogger("signalroute")
    if logger.handlers:
        return logger

    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
    return logger


logger = setup_logging()


def log_request(method: str, path: str, extra: dict[str, Any] | None = None) -> None:
    parts = [f"{method} {path}"]
    if extra:
        parts.append(" ".join(f"{k}={v}" for k, v in extra.items()))
    logger.info(" | ".join(parts))


def log_error(msg: str, exc: Exception | None = None) -> None:
    if exc:
        logger.error(f"{msg} | {type(exc).__name__}: {exc}")
    else:
        logger.error(msg)
