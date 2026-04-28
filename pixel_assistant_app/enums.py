"""集中管理 UI 與訊息佇列使用的列舉，避免拼字錯誤的 magic string。"""
from enum import Enum


class Mode(str, Enum):
    """主介面顯示模式。"""

    IDLE = "IDLE"
    LISTENING = "LISTENING"
    THINKING = "THINKING"
    SPEAKING = "SPEAKING"


class Action(str, Enum):
    """跨執行緒訊息佇列的動作類型。"""

    SHOW_TEXT = "show_text"
    SET_MODE = "set_mode"
    SPEAK = "speak"
    SHOW_ERROR = "show_error"
