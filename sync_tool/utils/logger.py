"""Application logging configuration."""

from __future__ import annotations

import logging
from pathlib import Path


def get_logger(name: str = "sync_tool", log_file: Path | None = None) -> logging.Logger:
    """Create or return a configured logger instance."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    output = log_file or Path("sync.log")
    file_handler = logging.FileHandler(output, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    logger.propagate = False
    return logger
