"""集中管理 runtime 路徑（暫存音訊、文字、log）。

預設將暫存與 log 檔案放在使用者家目錄下的 `~/.pixel_assistant/` 以避免污染專案目錄。
若環境變數 `PIXEL_ASSISTANT_HOME` 有設定，則改用該路徑。
"""
from __future__ import annotations

import os
import shutil
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


def project_root() -> Path:
    env = os.environ.get("PIXEL_ASSISTANT_PROJECT_ROOT")
    if env:
        return Path(env).expanduser()
    return Path(__file__).resolve().parents[1]


def project_temp_speech_mp3() -> str:
    return str(project_root() / "temp_speech.mp3")


def project_temp_speech_text() -> str:
    return str(project_root() / "temp_speech.txt")


def temp_speech_mp3() -> str:
    return str(cache_dir() / "temp_speech.mp3")


def temp_speech_text() -> str:
    return str(cache_dir() / "temp_speech.txt")


def write_temp_speech_text(text: str) -> None:
    cache_path = Path(temp_speech_text())
    project_path = Path(project_temp_speech_text())
    cache_path.write_text(text, encoding="utf-8")
    shutil.copyfile(cache_path, project_path)


def sync_temp_speech_mp3() -> None:
    cache_path = Path(temp_speech_mp3())
    project_path = Path(project_temp_speech_mp3())
    if not cache_path.exists():
        return
    shutil.copyfile(cache_path, project_path)
