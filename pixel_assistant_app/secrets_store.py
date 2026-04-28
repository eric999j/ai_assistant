"""安全處理 Gemini API Key：優先 OS keyring → 環境變數 → 設定檔。"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

SERVICE_NAME = "pixel_assistant"
KEY_NAME = "gemini_api_key"
ENV_VAR = "GEMINI_API_KEY"


def _try_keyring():
    try:
        import keyring  # type: ignore
        return keyring
    except Exception:
        return None


def get_api_key(config_value: str | None = None) -> str:
    """依優先順序取得 API Key。"""
    kr = _try_keyring()
    if kr is not None:
        try:
            v = kr.get_password(SERVICE_NAME, KEY_NAME)
            if v:
                return v
        except Exception as e:
            logger.debug("keyring lookup failed: %s", e)

    env = os.environ.get(ENV_VAR, "")
    if env:
        return env

    return config_value or ""


def store_api_key(value: str) -> bool:
    """嘗試將 API Key 存入 OS keyring。回傳 True 表示成功。"""
    if not value:
        return False
    kr = _try_keyring()
    if kr is None:
        return False
    try:
        kr.set_password(SERVICE_NAME, KEY_NAME, value)
        return True
    except Exception as e:
        logger.warning("Failed to store API key in keyring: %s", e)
        return False


def delete_api_key() -> None:
    kr = _try_keyring()
    if kr is None:
        return
    try:
        kr.delete_password(SERVICE_NAME, KEY_NAME)
    except Exception:
        pass
