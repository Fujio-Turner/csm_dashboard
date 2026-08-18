from __future__ import annotations

import logging
import os
import sys


def configure_logging(level: int | None = None) -> None:
    if level is None:
        name = (os.environ.get("CSM_DASHBOARD_LOG") or "INFO").upper()
        level = getattr(logging, name, logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
