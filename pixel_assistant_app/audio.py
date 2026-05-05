import asyncio
import logging
import os
import shutil
import subprocess
import threading
import time

import edge_tts

from .paths import sync_temp_speech_mp3, temp_speech_mp3, write_temp_speech_text

logger = logging.getLogger(__name__)

# 嘗試導入 pygame 作為備用
try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False

class AudioHandler:
    def __init__(self, volume: float = 1.0) -> None:
        self.is_playing: bool = False
        self._cancel_requested: bool = False
        self._mpv_process: subprocess.Popen | None = None
        # 保護 _mpv_process 與 is_playing 的執行緒鎖
        self._lock = threading.Lock()
        # 音量範圍限制在 0.0 ~ 1.0
        self.volume: float = max(0.0, min(1.0, float(volume)))

        # 檢查 mpv 是否可用
        self.mpv_path = shutil.which("mpv")
        self.use_mpv = self.mpv_path is not None

        if not self.use_mpv and PYGAME_AVAILABLE:
            pygame.mixer.init()
            pygame.mixer.music.set_volume(self.volume)
            logger.info("MPV not found, using pygame fallback")
        elif self.use_mpv:
            logger.info("Using MPV for audio playback: %s", self.mpv_path)

    async def play_tts(self, text: str, voice: str = "zh-TW-HsiaoChenNeural") -> None:
        """使用 Edge-TTS 串流生成並播放語音"""
        self._cancel_requested = False

        try:
            # 保存文字內容到本地文件
            try:
                write_temp_speech_text(text)
            except Exception as save_err:
                logger.warning("Failed to save text: %s", save_err)

            if self.use_mpv:
                await self._play_tts_mpv_stream(text, voice)
            else:
                await self._play_tts_pygame(text, voice)

        except Exception as e:
            logger.error("Audio Error: %s", e)

    async def _play_tts_mpv_stream(self, text: str, voice: str) -> None:
        """使用 MPV 串流播放 - 邊下載邊播放，同時保存到暫存 mp3。"""
        output_file = temp_speech_mp3()
        try:
            communicate = edge_tts.Communicate(text, voice)

            # 啟動 mpv 從 stdin 讀取音訊 (隱藏視窗)
            mpv_volume = int(self.volume * 100)
            proc = subprocess.Popen(
                [self.mpv_path, "--no-video", "--no-terminal", f"--volume={mpv_volume}", "-"],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            with self._lock:
                self._mpv_process = proc
                self.is_playing = True

            # 串流寫入音訊資料到 mpv，同時保存到檔案
            with open(output_file, "wb") as f:
                async for chunk in communicate.stream():
                    if self._cancel_requested:
                        break
                    if chunk["type"] == "audio":
                        # 寫入檔案
                        f.write(chunk["data"])
                        # 同時送給 mpv 播放
                        try:
                            proc.stdin.write(chunk["data"])
                            proc.stdin.flush()
                        except (BrokenPipeError, OSError):
                            break

            sync_temp_speech_mp3()

            # 關閉 stdin 讓 mpv 知道資料結束
            if proc.stdin:
                try:
                    proc.stdin.close()
                except Exception:
                    pass

            # 等待播放完成
            if not self._cancel_requested:
                proc.wait()

            with self._lock:
                self.is_playing = False
                self._mpv_process = None

        except Exception as e:
            logger.error("MPV Stream Error: %s", e)
            with self._lock:
                self.is_playing = False
                self._mpv_process = None

    async def _play_tts_pygame(self, text: str, voice: str) -> None:
        """使用 pygame 播放 (備用方案)"""
        output_file = temp_speech_mp3()

        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_file)
        sync_temp_speech_mp3()

        if self._cancel_requested:
            return

        if not os.path.exists(output_file) or os.path.getsize(output_file) == 0:
            logger.error("TTS Error: mp3 file not created or empty")
            return

        if self._cancel_requested:
            return

        # 使用 Pygame 播放
        pygame.mixer.music.load(output_file)
        pygame.mixer.music.set_volume(self.volume)
        pygame.mixer.music.play()
        self.is_playing = True
        while pygame.mixer.music.get_busy():
            if self._cancel_requested:
                pygame.mixer.music.stop()
                break
            await asyncio.sleep(0.1)
        self.is_playing = False
        try:
            pygame.mixer.music.unload()
        except Exception:
            pass

    def stop(self) -> None:
        """停止當前播放的音訊"""
        self._cancel_requested = True
        try:
            # 取出並清除 _mpv_process 指標（加鎖防止與播放執行緒競爭）
            with self._lock:
                proc = self._mpv_process
                self._mpv_process = None
                self.is_playing = False

            if proc:
                proc.terminate()

            # 停止 pygame
            if not self.use_mpv and PYGAME_AVAILABLE and pygame.mixer.get_init():
                pygame.mixer.music.stop()
                pygame.mixer.music.unload()
        except Exception as e:
            logger.error("Audio Error (stop): %s", e)

    def play_file(self, file_path: str) -> None:
        """在背景執行播放指定的本地音訊檔案"""
        def run():
            self._cancel_requested = False
            try:
                if not os.path.exists(file_path):
                    logger.error("Audio Error: file not found: %s", file_path)
                    return

                if self.use_mpv:
                    mpv_volume = int(self.volume * 100)
                    proc = subprocess.Popen(
                        [self.mpv_path, "--no-video", "--no-terminal", f"--volume={mpv_volume}", file_path],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        creationflags=subprocess.CREATE_NO_WINDOW
                    )
                    with self._lock:
                        self._mpv_process = proc
                        self.is_playing = True
                    while proc.poll() is None:
                        if self._cancel_requested:
                            proc.terminate()
                            break
                        time.sleep(0.1)
                    with self._lock:
                        self.is_playing = False
                        self._mpv_process = None
                else:
                    pygame.mixer.music.load(file_path)
                    pygame.mixer.music.play()
                    self.is_playing = True
                    while pygame.mixer.music.get_busy():
                        if self._cancel_requested:
                            pygame.mixer.music.stop()
                            break
                        time.sleep(0.1)
                    self.is_playing = False
                    try:
                        pygame.mixer.music.unload()
                    except Exception:
                        pass

            except Exception as e:
                logger.error("Audio Error (play_file): %s", e)

        threading.Thread(target=run, daemon=True).start()
