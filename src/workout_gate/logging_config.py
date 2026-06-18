"""Logging strutturato su file rotante + console."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from .paths import log_dir

_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"


def setup_logging(level: int = logging.INFO, *, to_file: bool = True) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if to_file:
        fh = RotatingFileHandler(
            log_dir() / "workout-gate.log",
            maxBytes=1_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        handlers.append(fh)
    logging.basicConfig(level=level, format=_FORMAT, handlers=handlers, force=True)
    # Riduce il rumore di librerie verbose.
    logging.getLogger("mediapipe").setLevel(logging.WARNING)
