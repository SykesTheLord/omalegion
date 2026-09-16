"""Shared debug log file for the engine.

QML only ever sees the JSON on stdout, so failures deep in HID/sysfs code
(wrong device, permission denied, bad payload, an unexpected exception) are
otherwise invisible. Everything of note goes to
~/.config/omarchy/legion_debug.log instead, capped at ~1MB with one backup so
it can't grow unbounded.
"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

LOG_FILE = Path.home() / ".config" / "omarchy" / "legion_debug.log"

_configured = False


def get_logger(name: str) -> logging.Logger:
    global _configured
    logger = logging.getLogger("legion." + name)
    if not _configured:
        try:
            LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
            handler = logging.handlers.RotatingFileHandler(
                LOG_FILE, maxBytes=1_000_000, backupCount=1
            )
            handler.setFormatter(
                logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
            )
            root = logging.getLogger("legion")
            root.addHandler(handler)
            root.setLevel(logging.DEBUG)
            root.propagate = False
        except OSError:
            logging.getLogger("legion").addHandler(logging.NullHandler())
        _configured = True
    return logger
