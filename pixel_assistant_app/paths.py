"""集中管理 runtime 路徑（暫存音訊、文字、log）。

預設將暫存與 log 檔案放在使用者家目錄下的 `~/.pixel_assistant/` 以避免污染專案目錄。
若環境變數 `PIXEL_ASSISTANT_HOME` 有設定，則改用該路徑。
"""
from __future__ import annotations

import os
from pathlib import Path


def app_home() -> Path:
    env = os.environ.get("PIXEL_ASSISTANT_HOME")
    if env:
        base = Path(env).expanduser()
    else:
        base = Path.home() / ".pixel_assistant"
    base.mkdir(parents=True, exist_ok=True)
    return base


def cache_dir() -> Path:
    d = app_home() / "cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def log_dir() -> Path:
    d = app_home() / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def temp_speech_mp3() -> str:
    return str(cache_dir() / "temp_speech.mp3")


def temp_speech_text() -> str:
    return str(cache_dir() / "temp_speech.txt")
