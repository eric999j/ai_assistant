"""統一的 logging 設定：console + RotatingFileHandler。"""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from .paths import log_dir

_CONFIGURED = False


def setup_logging(level: int = logging.INFO) -> None:
    """設定 root logger。重複呼叫不會重複新增 handler。"""
    global _CONFIGURED
    if _CONFIGURED:
        return

    root = logging.getLogger()
    root.setLevel(level)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    root.addHandler(sh)

    # Rotating file
    try:
        log_path = log_dir() / "pixel_assistant.log"
        fh = RotatingFileHandler(
            str(log_path), maxBytes=1_000_000, backupCount=3, encoding="utf-8"
        )
        fh.setFormatter(fmt)
        root.addHandler(fh)
    except Exception as e:  # pragma: no cover - 環境問題不應阻擋啟動
        root.warning("Failed to attach file log handler: %s", e)

    _CONFIGURED = True
