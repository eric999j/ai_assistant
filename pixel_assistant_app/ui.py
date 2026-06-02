import asyncio
import logging
import os
import queue
import threading
import time
import tkinter as tk
from tkinter import Menu, messagebox, simpledialog

import pyperclip
import speech_recognition as sr
from PIL import Image, ImageGrab

from .audio import AudioHandler
from .brain import AIBrain
from .clipboard_utils import download_image, looks_like_image_url
from .config import (
    AI_MODELS,
    CELL_SIZE,
    DOUBLE_CLICK_DELAY_MS,
    FPS,
    GRID_H,
    GRID_W,
    THEMES,
    VOICES,
)
from .dialogs import ask_text_command, edit_welcome_message, open_quick_command_editor
from .enums import Action, Mode
from .game_of_life import GameOfLife
from .paths import temp_speech_mp3, temp_speech_text, write_temp_speech_text

# 說話模式時的閃爍週期（毫秒）
SPEAKING_FLICKER_INTERVAL_MS = 200
# UI 訊息佇列的虛擬事件名稱
QUEUE_EVENT = "<<PixelMsg>>"


class PixelAssistantUI:
    def __init__(self, root, config_manager):
        self.root = root
        self.config_manager = config_manager
        self.logger = logging.getLogger("PixelAssistantUI")
        if not logging.getLogger().handlers:
            logging.basicConfig(level=logging.INFO)

        # 變數初始化
        self.theme_name = self.config_manager.get("theme", "Hacker Green")
        self.colors = THEMES[self.theme_name]
        self.voice_id = self.config_manager.get("voice_id", "zh-TW-HsiaoChenNeural")
        self.model_name = self.config_manager.get("ai_model", "")

        # 選單狀態變數
        self.theme_var = tk.StringVar(value=self.theme_name)
        self.voice_var = tk.StringVar(value=self.voice_id)
        self.model_var = tk.StringVar(value=self.model_name or "Auto")

        # 初始化 Game of Life
        self.game = GameOfLife(GRID_W, GRID_H)
        self.rects = {}
        self.running = True
        self.mode: Mode = Mode.IDLE
        self._single_click_after_id = None

        _volume = self.config_manager.get("volume", 1.0)
        self.audio_handler = AudioHandler(volume=_volume)
        self.msg_queue = queue.Queue()
        self._last_alive_cells = set()
        self._last_alive_color = None
        self._force_full_redraw = True
        self._bubble_after_id = None
        self._tts_lock = threading.Lock()
        self._tts_job_id = 0
        # SPEAKING 模式下用 time-based 切換顏色，避免每幀亂數
        self._speaking_alt_color = False
        self._speaking_last_toggle = 0.0

        # AI
        self.api_key = self.config_manager.get("api_key", "") or os.environ.get("GEMINI_API_KEY", "")
        self.brain = None
        self.max_reply_chars = self.config_manager.get("max_reply_chars", 200)
        self.bubble_duration = self.config_manager.get("bubble_duration", 5000)

        if not self.api_key:
            self.ask_api_key()
        else:
            try:
                self.init_brain()
            except Exception as e:
                self.logger.error("AI initialization failed: %s", e)
                msg = f"AI 初始化失敗: {e}\n請檢查 API Key 或網路連線。"
                if "404" in str(e) or "not found" in str(e).lower():
                    msg = f"選擇的模型 {self.model_name} 無法使用，將重置為自動選擇。"
                    self.config_manager.set("ai_model", "")
                    self.model_name = ""
                    try:
                        self.init_brain()
                        msg += "\n(已自動切換回預設模型)"
                    except Exception:
                        pass
                messagebox.showerror("AI Error", msg)

        # 視窗設定
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.transparent_color = "#000001"
        try:
            self.root.wm_attributes("-transparentcolor", self.transparent_color)
        except tk.TclError:
            # 非 Windows 平台不支援，忽略
            self.logger.info("Transparent color not supported on this platform")
        self.root.configure(bg=self.transparent_color)

        self.setup_ui()
        self.position_window_bottom_right()
        self.setup_context_menu()
        self.setup_bubble()

        # 訊息佇列：改用 virtual event，由 worker thread 透過 event_generate 喚醒
        self.root.bind(QUEUE_EVENT, lambda _e: self.process_queue())

        self.spawn_creature()
        try:
            always = self.config_manager.get("always_play_welcome", True)
            welcome = self.config_manager.get("welcome_text", "歡迎使用 Pixel Assistant！")
            seen = self.config_manager.get("seen_welcome", False)
            if always or (not always and not seen):
                self.run_async_tts(welcome)
                if not always:
                    self.config_manager.set("seen_welcome", True)
        except Exception:
            pass
        self.update_loop()

    # ---------------- AI ----------------
    def init_brain(self):
        self.brain = AIBrain(self.api_key, max_reply_chars=self.max_reply_chars, model_name=self.model_name)

    def _reload_brain(self):
        try:
            self.init_brain()
            self._enqueue(Action.SPEAK, text="AI 模型已更新")
        except Exception as e:
            self.logger.error("Failed to reload brain: %s", e)
            msg = f"模型切換失敗: {str(e)}"
            if "404" in str(e) or "not found" in str(e).lower():
                msg = f"模型 {self.model_name} 無法使用或不存在\n請切換其他模型"
            self._enqueue(Action.SPEAK, text="模型切換失敗")
            self._enqueue(Action.SHOW_ERROR, text=msg)
            self.root.after(0, lambda: self.change_model(""))

    def ask_api_key(self):
        key = simpledialog.askstring("API Key", "請輸入 Google Gemini API Key:", parent=self.root)
        if key:
            self.api_key = key
            # ConfigManager 會優先嘗試 keyring，否則保留 in-memory
            self.config_manager.set("api_key", key)
            self.max_reply_chars = self.config_manager.get("max_reply_chars", self.max_reply_chars)
            try:
                self.init_brain()
            except Exception as e:
                messagebox.showerror("Error", f"初始化失敗: {e}")
        else:
            messagebox.showwarning("警告", "沒有 API Key，助手將無法回答問題。")

    # ---------------- UI 元件 ----------------
    def setup_ui(self):
        self.canvas = tk.Canvas(
            self.root,
            width=GRID_W * CELL_SIZE,
            height=GRID_H * CELL_SIZE,
            bg=self.transparent_color,
            highlightthickness=0,
        )
        self.canvas.pack()

        for y in range(GRID_H):
            for x in range(GRID_W):
                rect_id = self.canvas.create_rectangle(
                    x * CELL_SIZE, y * CELL_SIZE,
                    (x + 1) * CELL_SIZE, (y + 1) * CELL_SIZE,
                    fill=self.transparent_color, outline=""
                )
                self.rects[(x, y)] = rect_id
        self._all_grid_positions = tuple(self.rects.keys())

        self.canvas.bind("<Button-1>", self.on_left_click)
        self.canvas.bind("<Double-Button-1>", self.on_double_click)
        self.canvas.bind("<Button-3>", self.show_context_menu)
        self.canvas.bind("<B1-Motion>", self.move_window)
        self.canvas.bind("<ButtonPress-1>", self.start_move)

    def setup_bubble(self):
        self.bubble = tk.Toplevel(self.root)
        self.bubble.overrideredirect(True)
        self.bubble.attributes("-topmost", True)
        self.bubble.configure(bg="#333333")
        self.bubble_label = tk.Label(
            self.bubble, text="", fg="white", bg="#333333",
            font=("Arial", 10), wraplength=500, justify="left", padx=10, pady=5
        )
        self.bubble_label.pack()
        self.bubble.withdraw()

    def update_bubble_position(self):
        if self.bubble.winfo_viewable():
            self.bubble.update_idletasks()
            root_x = self.root.winfo_x()
            root_y = self.root.winfo_y()
            x = root_x + self.root.winfo_width() + 8
            y = root_y
            screen_w = self.root.winfo_screenwidth()
            screen_h = self.root.winfo_screenheight()
            bubble_w = self.bubble.winfo_width()
            bubble_h = self.bubble.winfo_height()
            if x + bubble_w > screen_w - 8:
                x = root_x - bubble_w - 8
            x = max(8, min(x, screen_w - bubble_w - 8))
            y = max(8, min(y, screen_h - bubble_h - 8))
            self.bubble.geometry(f"+{x}+{y}")

    def position_window_bottom_right(self):
        self.root.update_idletasks()
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        window_width = GRID_W * CELL_SIZE
        window_height = GRID_H * CELL_SIZE
        margin = 20
        x = screen_width - window_width - margin
        y = screen_height - window_height - margin - 40
        self.root.geometry(f"+{x}+{y}")

    def save_bubble_text(self, text):
        try:
            write_temp_speech_text(text)
        except Exception as e:
            self.logger.error("Failed to save bubble text: %s", e)

    def load_bubble_text(self):
        try:
            path = temp_speech_text()
            if os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    return f.read()
        except Exception as e:
            self.logger.error("Failed to load bubble text: %s", e)
        return None

    def _cancel_bubble_timer(self):
        if not self._bubble_after_id:
            return
        try:
            self.root.after_cancel(self._bubble_after_id)
        except Exception as e:
            self.logger.debug("Bubble timer was already unavailable: %s", e)
        self._bubble_after_id = None

    def show_message(self, text, duration=None):
        if duration is None:
            duration = self.config_manager.get("bubble_duration", 5000)
        self._cancel_bubble_timer()
        self.bubble_label.config(text=text)
        self.bubble.deiconify()
        self.update_bubble_position()
        self.save_bubble_text(text)
        self._bubble_after_id = self.root.after(duration, self._hide_bubble)

    def _hide_bubble(self):
        self._bubble_after_id = None
        self.bubble.withdraw()

    def setup_context_menu(self):
        if hasattr(self, "menu"):
            try:
                self.menu.destroy()
            except Exception as e:
                self.logger.debug("Previous context menu was already unavailable: %s", e)
        self.menu = Menu(self.root, tearoff=0)
        quick_menu = Menu(self.menu, tearoff=0)
        quick_commands = self.config_manager.get("quick_commands", [])
        if quick_commands:
            for idx, qc in enumerate(quick_commands):
                label = qc.get("label", f"Command {idx+1}")
                prompt = qc.get("prompt", "")
                quick_menu.add_command(label=label, command=lambda p=prompt: self.run_quick_command(p))
        else:
            quick_menu.add_command(label="(無)", state="disabled")
        quick_menu.add_separator()
        quick_menu.add_command(label="✏️ 編輯指令...", command=self.open_quick_command_editor)
        self.menu.add_cascade(label="⚡ 快速指令", menu=quick_menu)
        self.menu.add_command(label="⌨️ 輸入指令", command=self.input_text_command)
        self.menu.add_command(label="📋 分析剪貼簿", command=self.analyze_clipboard)
        self.menu.add_command(label="🔁 回放上次語音", command=self.replay_local_audio)
        self.menu.add_command(label="🔄 重置形象", command=self.spawn_creature)
        self.menu.add_separator()

        theme_menu = Menu(self.menu, tearoff=0)
        for name in THEMES.keys():
            theme_menu.add_radiobutton(
                label=name, variable=self.theme_var, value=name,
                command=lambda: self.change_theme(self.theme_var.get())
            )
        self.menu.add_cascade(label="🎨 顏色主題", menu=theme_menu)

        model_menu = Menu(self.menu, tearoff=0)
        model_menu.add_radiobutton(
            label="自動選擇 (Auto)", variable=self.model_var, value="Auto",
            command=lambda: self.change_model("")
        )
        model_menu.add_separator()
        for name, model_id in AI_MODELS.items():
            model_menu.add_radiobutton(
                label=name, variable=self.model_var, value=model_id,
                command=lambda: self.change_model(self.model_var.get())
            )
        self.menu.add_cascade(label="🤖 切換 AI 模型", menu=model_menu)

        voice_menu = Menu(self.menu, tearoff=0)
        for name, voice_id in VOICES.items():
            voice_menu.add_radiobutton(
                label=name, variable=self.voice_var, value=voice_id,
                command=lambda: self.change_voice(self.voice_var.get())
            )
        self.menu.add_cascade(label="🗣️ 切換語音", menu=voice_menu)
        self.menu.add_command(label="🔑 設定 API Key", command=self.ask_api_key)
        self.menu.add_command(label="✏️ 編輯歡迎訊息", command=self.edit_welcome_message)
        self.menu.add_separator()
        self.menu.add_command(label="❌ 離開", command=self.root.quit)

    # ---------------- 設定切換 ----------------
    def change_model(self, model_id):
        if model_id == "Auto":
            model_id = ""
        self.model_name = model_id
        self.model_var.set("Auto" if not model_id else model_id)
        self.config_manager.set("ai_model", model_id)
        self.show_message(f"正在切換模型到: {model_id if model_id else '自動選擇'}...")
        threading.Thread(target=self._reload_brain, daemon=True).start()

    def change_theme(self, theme_name):
        self.theme_name = theme_name
        self.theme_var.set(theme_name)
        self.colors = THEMES[theme_name]
        self.config_manager.set("theme", theme_name)
        self._force_full_redraw = True
        self.draw_grid()

    def change_voice(self, voice_id):
        self.voice_id = voice_id
        self.voice_var.set(voice_id)
        self.config_manager.set("voice_id", voice_id)
        is_english = "en-" in voice_id.lower()
        if is_english:
            message = "Voice changed"
            demo_text = "Hello! This is your new voice."
        else:
            message = "已切換語音"
            demo_text = "你好！這是你的新語音。"
        self.show_message(message)
        try:
            self.run_async_tts(demo_text)
        except Exception as e:
            self.logger.error("Failed to play demo with new voice: %s", e)

    # ---------------- 視窗拖曳 ----------------
    def start_move(self, event):
        self.x = event.x
        self.y = event.y

    def move_window(self, event):
        deltax = event.x - self.x
        deltay = event.y - self.y
        x = self.root.winfo_x() + deltax
        y = self.root.winfo_y() + deltay
        self.root.geometry(f"+{x}+{y}")
        self.update_bubble_position()

    def show_context_menu(self, event):
        self.menu.post(event.x_root, event.y_root)

    # ---------------- 像素邏輯 ----------------
    def spawn_creature(self):
        if hasattr(self, "audio_handler"):
            self.audio_handler.stop()
        if hasattr(self, "bubble"):
            self._cancel_bubble_timer()
            self.bubble.withdraw()
        self._force_full_redraw = True
        self.game.spawn_creature()

    def game_of_life_step(self):
        if not self.game.step():
            self.logger.info("game_of_life_step: all cells died -> respawning")
            self.spawn_creature()

    def _current_alive_color(self) -> str:
        """SPEAKING 模式下以固定間隔切換顏色，其餘維持主題色。"""
        if self.mode != Mode.SPEAKING:
            return self.colors["alive"]
        now = time.monotonic() * 1000
        if now - self._speaking_last_toggle >= SPEAKING_FLICKER_INTERVAL_MS:
            self._speaking_alt_color = not self._speaking_alt_color
            self._speaking_last_toggle = now
        return "#FFFFFF" if self._speaking_alt_color else self.colors["alive"]

    def draw_grid(self):
        alive_cells = self.game.get_cells()
        alive_color = self._current_alive_color()

        if self._force_full_redraw:
            update_cells = self._all_grid_positions
        elif alive_color != self._last_alive_color:
            update_cells = self._last_alive_cells | alive_cells
        else:
            update_cells = self._last_alive_cells ^ alive_cells

        for cell in update_cells:
            rect_id = self.rects[cell]
            fill = alive_color if cell in alive_cells else self.transparent_color
            self.canvas.itemconfigure(rect_id, fill=fill)

        self._last_alive_cells = alive_cells
        self._last_alive_color = alive_color
        self._force_full_redraw = False

    def update_loop(self):
        if self.mode == Mode.IDLE:
            self.game_of_life_step()
        elif self.mode == Mode.THINKING:
            self.game.spawn_creature()

        self.draw_grid()

        delay = 1000 // FPS
        if self.mode == Mode.THINKING:
            delay = 50
        self.root.after(delay, self.update_loop)

    # ---------------- 訊息佇列（virtual event 驅動） ----------------
    def _enqueue(self, action: Action, **payload) -> None:
        """Worker thread 用：放入訊息並通知主執行緒。"""
        msg = {"action": action.value if isinstance(action, Action) else action}
        msg.update(payload)
        self.msg_queue.put(msg)
        try:
            self.root.event_generate(QUEUE_EVENT, when="tail")
        except Exception:
            # 視窗已銷毀
            pass

    def process_queue(self):
        try:
            while True:
                task = self.msg_queue.get_nowait()
                action = task.get("action")
                if action == Action.SHOW_TEXT.value:
                    self.show_message(task["text"])
                elif action == Action.SET_MODE.value:
                    raw = task["mode"]
                    self.mode = raw if isinstance(raw, Mode) else Mode(raw)
                elif action == Action.SPEAK.value:
                    self.run_async_tts(task["text"])
                elif action == Action.SHOW_ERROR.value:
                    self.show_error(task.get("text", "Error"))
                self.msg_queue.task_done()
        except queue.Empty:
            pass

    def show_error(self, text, duration=10000):
        try:
            old_bg = self.bubble_label.cget("bg")
            old_fg = self.bubble_label.cget("fg")
        except Exception:
            old_bg, old_fg = "#333333", "white"

        self.bubble_label.config(bg="#550000", fg="#FFFFFF")
        self.bubble.configure(bg="#550000")
        self.show_message(text, duration=duration)

        def restore():
            try:
                self.bubble_label.config(bg=old_bg, fg=old_fg)
                self.bubble.configure(bg="#333333")
            except Exception:
                pass
        self.root.after(duration, restore)

    # ---------------- 對話框入口 ----------------
    def input_text_command(self):
        text = ask_text_command(self.root)
        if text:
            self.handle_ai_response(text)

    def open_quick_command_editor(self):
        commands = self.config_manager.get("quick_commands", []) or []

        def on_save(new_commands):
            self.config_manager.set("quick_commands", new_commands)
            self.setup_context_menu()

        open_quick_command_editor(self.root, commands, on_save)

    def edit_welcome_message(self):
        current = self.config_manager.get("welcome_text", "歡迎使用 Pixel Assistant！")
        always = self.config_manager.get("always_play_welcome", True)

        def on_save(new_text, new_always):
            with self.config_manager.batch():
                self.config_manager.set("welcome_text", new_text)
                self.config_manager.set("always_play_welcome", new_always)
            self.show_message("已更新歡迎訊息", 3000)

        edit_welcome_message(self.root, current, always, on_save)

    # ---------------- AI 互動 ----------------
    def run_quick_command(self, prompt_template):
        self._enqueue(Action.SHOW_TEXT, text="正在處理指令...")

        def _background_run():
            image_to_analyze = self._grab_clipboard_image()
            if image_to_analyze:
                self.logger.info("Quick command - using image recognition")
                if "{clipboard}" in prompt_template:
                    prompt = prompt_template.replace("{clipboard}", "這張圖片")
                else:
                    prompt = prompt_template
                self._enqueue(Action.SHOW_TEXT, text="發現圖片，正在分析...")
                self.handle_ai_response(prompt, image=image_to_analyze)
                return

            clipboard = pyperclip.paste()
            prompt = prompt_template.replace("{clipboard}", clipboard)
            if not prompt.strip():
                self._enqueue(Action.SHOW_TEXT, text="快速指令內容為空")
                return
            self.handle_ai_response(prompt)

        threading.Thread(target=_background_run, daemon=True).start()

    def _grab_clipboard_image(self) -> Image.Image | None:
        try:
            img = ImageGrab.grabclipboard()
        except Exception as e:
            self.logger.error("ImageGrab error: %s", e)
            return None
        if isinstance(img, Image.Image):
            return img
        if isinstance(img, list) and img and isinstance(img[0], str) and os.path.isfile(img[0]):
            try:
                return Image.open(img[0])
            except Exception as e:
                self.logger.error("Failed to load image from file: %s", e)
        return None

    def analyze_clipboard(self):
        self._enqueue(Action.SHOW_TEXT, text="正在分析剪貼簿...")

        def _background_analysis():
            image_to_analyze = self._grab_clipboard_image()
            source_type = "剪貼簿圖片" if image_to_analyze else ""

            text_content = pyperclip.paste()

            if not image_to_analyze and text_content:
                raw = text_content.strip()
                if looks_like_image_url(raw):
                    self._enqueue(Action.SHOW_TEXT, text="偵測到圖片連結，下載中...")
                    image_to_analyze = download_image(raw)
                    if image_to_analyze:
                        source_type = "網路圖片連結"
                    else:
                        self._enqueue(Action.SHOW_TEXT, text="圖片下載失敗或被安全策略阻擋")

            if image_to_analyze:
                self._enqueue(Action.SHOW_TEXT, text=f"已取得圖片 ({source_type})，正在辨識...")
                self.handle_ai_response("請詳盡描述這張圖片的內容。", image=image_to_analyze)
            else:
                if not text_content:
                    self._enqueue(Action.SHOW_TEXT, text="剪貼簿為空或無法辨識內容")
                else:
                    self._enqueue(Action.SHOW_TEXT, text="未發現圖片，分析文字內容...")
                    prompt = f"請簡短總結或解釋以下內容：\n{text_content[:500]}"
                    self.handle_ai_response(prompt)

        threading.Thread(target=_background_analysis, daemon=True).start()

    def run_async_tts(self, text):
        with self._tts_lock:
            self._tts_job_id += 1
            job_id = self._tts_job_id

        def run():
            self._enqueue(Action.SET_MODE, mode=Mode.SPEAKING.value)
            try:
                asyncio.run(self.audio_handler.play_tts(text, self.voice_id))
            except Exception as e:
                self.logger.error("TTS error: %s", e)
            finally:
                with self._tts_lock:
                    if job_id == self._tts_job_id:
                        self._enqueue(Action.SET_MODE, mode=Mode.IDLE.value)
        threading.Thread(target=run, daemon=True).start()

    def handle_ai_response(self, prompt, image=None):
        def run():
            self._enqueue(Action.SET_MODE, mode=Mode.THINKING.value)
            try:
                if not self.brain:
                    raise Exception("AI not initialized")
                text = self.brain.ask(prompt, image=image)
                self.logger.info("AI response: %s", text)
                self._enqueue(Action.SHOW_TEXT, text=text)
                tts_text = text.replace("*", "")
                self._enqueue(Action.SPEAK, text=tts_text)
            except Exception as e:
                self.logger.error("AI error: %s", e)
                self._enqueue(Action.SHOW_TEXT, text=f"Error: {e}")
                self._enqueue(Action.SET_MODE, mode=Mode.IDLE.value)

        threading.Thread(target=run, daemon=True).start()

    # ---------------- 點擊事件 ----------------
    def on_left_click(self, event):
        if self.mode != Mode.IDLE:
            return
        try:
            if self._single_click_after_id:
                self.root.after_cancel(self._single_click_after_id)
        except Exception:
            pass
        self._single_click_after_id = self.root.after(DOUBLE_CLICK_DELAY_MS, self._handle_single_click)

    def _handle_single_click(self):
        self._single_click_after_id = None
        if self.mode != Mode.IDLE:
            return
        self.mode = Mode.LISTENING
        self.show_message("聽取中...", 10000)
        threading.Thread(target=self.listen_audio, daemon=True).start()

    def on_double_click(self, event):
        try:
            if self._single_click_after_id:
                self.root.after_cancel(self._single_click_after_id)
                self._single_click_after_id = None
        except Exception:
            pass
        cx, cy = event.x // CELL_SIZE, event.y // CELL_SIZE
        if self.game.is_cell_alive(cx, cy):
            try:
                self.root.quit()
            except Exception:
                self.root.destroy()

    def listen_audio(self):
        r = sr.Recognizer()
        with sr.Microphone() as source:
            try:
                audio = r.listen(source, timeout=5)
                text = r.recognize_google(audio, language="zh-TW")
                self._enqueue(Action.SHOW_TEXT, text=f"你說: {text}")
                self.handle_ai_response(text)
            except sr.WaitTimeoutError:
                self._enqueue(Action.SHOW_TEXT, text="沒聽到聲音...")
                self._enqueue(Action.SET_MODE, mode=Mode.IDLE.value)
            except sr.UnknownValueError:
                self._enqueue(Action.SHOW_TEXT, text="聽不懂...")
                self._enqueue(Action.SET_MODE, mode=Mode.IDLE.value)
            except Exception as e:
                self.logger.error("Audio recognition error: %s", e)
                self._enqueue(Action.SET_MODE, mode=Mode.IDLE.value)

    def replay_local_audio(self):
        try:
            temp_file = temp_speech_mp3()
            if not os.path.exists(temp_file):
                self.show_message("找不到暫存語音檔")
                return
            try:
                self.audio_handler.play_file(temp_file)
                last_text = self.load_bubble_text()
                if last_text:
                    self.show_message(f"回放: {last_text}")
                else:
                    self.show_message(f"回放上次語音: {os.path.basename(temp_file)}")
            except Exception as e:
                self.logger.error("Failed to replay temp speech: %s", e)
                self.show_message("無法播放暫存語音檔")
        except Exception as e:
            self.logger.error("replay_local_audio error: %s", e)
            self.show_message("回放音檔時發生錯誤")
