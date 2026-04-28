"""AudioHandler 基本行為測試。

由於真實 mpv/pygame 與 edge-tts 需要外部環境，這裡聚焦在初始化、音量限制、
stop() 安全性以及 paths 模組整合。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from pixel_assistant_app import paths
from pixel_assistant_app.audio import AudioHandler


def test_volume_clamped_to_range(monkeypatch):
    monkeypatch.setattr("pixel_assistant_app.audio.shutil.which", lambda _name: None)
    monkeypatch.setattr("pixel_assistant_app.audio.PYGAME_AVAILABLE", False)

    h = AudioHandler(volume=2.5)
    assert h.volume == 1.0
    h2 = AudioHandler(volume=-3.0)
    assert h2.volume == 0.0
    h3 = AudioHandler(volume=0.4)
    assert h3.volume == pytest.approx(0.4)


def test_stop_is_idempotent(monkeypatch):
    monkeypatch.setattr("pixel_assistant_app.audio.shutil.which", lambda _name: None)
    monkeypatch.setattr("pixel_assistant_app.audio.PYGAME_AVAILABLE", False)
    h = AudioHandler(volume=0.5)
    # 重複 stop 不應拋例外
    h.stop()
    h.stop()
    assert h.is_playing is False


def test_uses_mpv_when_available(monkeypatch):
    monkeypatch.setattr("pixel_assistant_app.audio.shutil.which", lambda _name: "/usr/bin/mpv")
    h = AudioHandler()
    assert h.use_mpv is True
    assert h.mpv_path == "/usr/bin/mpv"


def test_paths_in_app_home(tmp_path, monkeypatch):
    monkeypatch.setenv("PIXEL_ASSISTANT_HOME", str(tmp_path))
    # paths 函數每次呼叫都會 mkdir，因此可直接驗證
    home = paths.app_home()
    assert home == tmp_path
    mp3 = paths.temp_speech_mp3()
    assert mp3.startswith(str(tmp_path))
    assert mp3.endswith("temp_speech.mp3")
    txt = paths.temp_speech_text()
    assert txt.endswith("temp_speech.txt")
