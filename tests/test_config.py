"""ConfigManager 與 secrets_store 測試。"""
import importlib
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    """重新載入 config 模組，將設定檔指向 tmp 路徑，並清除環境變數。"""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    cfg_file = tmp_path / "pixel_config.json"

    # 使 keyring 操作變成 no-op，避免污染本機 keyring
    from pixel_assistant_app import secrets_store

    monkeypatch.setattr(secrets_store, "_try_keyring", lambda: None)

    # 重新載入 config 以套用 monkeypatch
    from pixel_assistant_app import config as config_mod

    importlib.reload(config_mod)
    monkeypatch.setattr(config_mod, "CONFIG_FILE", str(cfg_file))
    return config_mod, cfg_file


def test_defaults_written_once(isolated_config):
    config_mod, cfg_file = isolated_config
    cm = config_mod.ConfigManager()
    assert cfg_file.exists(), "預設設定應寫入磁碟"
    data = json.loads(cfg_file.read_text(encoding="utf-8"))
    assert "quick_commands" in data
    assert data["max_reply_chars"] == cm.DEFAULT_MAX_REPLY_CHARS


def test_set_writes_immediately(isolated_config):
    config_mod, cfg_file = isolated_config
    cm = config_mod.ConfigManager()
    cm.set("theme", "Cyber Pink")
    data = json.loads(cfg_file.read_text(encoding="utf-8"))
    assert data["theme"] == "Cyber Pink"


def test_batch_writes_once(isolated_config, monkeypatch):
    config_mod, cfg_file = isolated_config
    cm = config_mod.ConfigManager()

    save_calls = {"n": 0}
    original_save = cm.save

    def counting_save():
        save_calls["n"] += 1
        original_save()

    monkeypatch.setattr(cm, "save", counting_save)

    with cm.batch():
        cm.set("theme", "Ice Blue")
        cm.set("voice_id", "en-US-AriaNeural")
        cm.set("max_reply_chars", 123)

    assert save_calls["n"] == 1, "batch 結束時應只寫盤一次"
    data = json.loads(cfg_file.read_text(encoding="utf-8"))
    assert data["theme"] == "Ice Blue"
    assert data["max_reply_chars"] == 123


def test_api_key_not_persisted_to_disk(isolated_config):
    config_mod, cfg_file = isolated_config
    cm = config_mod.ConfigManager()
    cm.set("api_key", "super-secret-value")
    data = json.loads(cfg_file.read_text(encoding="utf-8"))
    assert "api_key" not in data, "api_key 不應寫入 JSON 設定檔"
    # in-memory 仍可取得
    assert cm.get("api_key") == "super-secret-value"


def test_legacy_api_key_loaded_from_disk(isolated_config):
    """若舊版設定檔殘留 api_key（無 keyring），應 in-memory 仍可讀取。"""
    config_mod, cfg_file = isolated_config
    cfg_file.write_text(
        json.dumps({"api_key": "legacy-key", "theme": "Hacker Green"}),
        encoding="utf-8",
    )
    cm = config_mod.ConfigManager()
    assert cm.get("api_key") == "legacy-key"


def test_env_var_overrides_disk(isolated_config, monkeypatch):
    config_mod, cfg_file = isolated_config
    cfg_file.write_text(json.dumps({"api_key": "old-disk-key"}), encoding="utf-8")
    monkeypatch.setenv("GEMINI_API_KEY", "env-key-wins")
    cm = config_mod.ConfigManager()
    assert cm.get("api_key") == "env-key-wins"
