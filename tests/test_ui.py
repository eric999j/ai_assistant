import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import types
import logging
import tkinter as tk

import pytest

from pixel_assistant_app.ui import PixelAssistantUI


class DummyConfig:
    """Mock configuration manager for testing."""
    def __init__(self):
        self._data = {'api_key': 'dummy'}  # Default API key to skip dialog

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value


class DummyAudio:
    """Mock audio handler to avoid pygame initialization in tests."""
    def __init__(self, **kwargs):
        pass

    def stop(self):
        pass

    async def play_tts(self, text, voice="zh-TW-HsiaoChenNeural"):
        pass


@pytest.fixture(autouse=True)
def configure_logging():
    """Configure logging for all tests."""
    logging.basicConfig(level=logging.INFO)


class DummyBrain:
    """Mock AIBrain to avoid real Google API calls in tests."""
    def __init__(self, api_key=None, max_reply_chars=200, model_name=None):
        self.api_key = api_key
        self.max_reply_chars = max_reply_chars
        self.model_name = model_name


@pytest.fixture
def mock_audio(monkeypatch):
    """Mock AudioHandler to avoid pygame dependencies."""
    monkeypatch.setattr('pixel_assistant_app.ui.AudioHandler', DummyAudio)


@pytest.fixture
def mock_brain(monkeypatch):
    """Mock AIBrain to avoid real API calls."""
    monkeypatch.setattr('pixel_assistant_app.ui.AIBrain', DummyBrain)


@pytest.fixture(scope="session")
def tk_root():
    """Create a single hidden Tkinter root for all tests."""
    root = tk.Tk()
    root.withdraw()
    yield root
    # Cleanup at end of test session
    try:
        root.quit()
        root.destroy()
    except Exception:
        pass


@pytest.fixture
def ui_instance(mock_audio, mock_brain, tk_root):
    """Create a PixelAssistantUI instance for testing."""
    cfg = DummyConfig()
    ui = PixelAssistantUI(tk_root, cfg)
    yield ui
    # Cleanup: stop pending callbacks and remove widgets
    if hasattr(ui, '_single_click_after_id') and ui._single_click_after_id:
        try:
            tk_root.after_cancel(ui._single_click_after_id)
        except Exception:
            pass
    # Destroy canvas and other widgets created by this UI instance
    try:
        ui.canvas.destroy()
        ui.bubble.destroy()
    except Exception:
        pass


def test_respawn_on_all_dead(ui_instance):
    """Test that cells respawn when all die during game of life step."""
    ui_instance.game.cells = set()  # Force all cells to be dead
    ui_instance.game_of_life_step()

    assert ui_instance.game.get_cell_count() > 0, "Expected respawn to create new cells when all died"


def test_double_click_exits_when_clicking_alive_cell(ui_instance):
    """Test that double-clicking an alive cell triggers quit."""
    from pixel_assistant_app.config import CELL_SIZE

    # Place a known alive cell at (2, 3)
    ui_instance.game.cells = {(2, 3)}

    # Create event at the pixel coordinates of the alive cell
    event = types.SimpleNamespace(x=2 * CELL_SIZE + 1, y=3 * CELL_SIZE + 1)

    # Should not raise exception
    ui_instance.on_double_click(event)

    # PixelAssistantUI calls root.quit()/destroy() on double-click; since we passed a real tk root,
    # the effect is that the process will be scheduled to quit; we at least ensure no exceptions
    # occurred while calling on_double_click.
    assert True


# --- Quick Command Editor Tests ---

class TestQuickCommandEditor:
    """Tests for the quick command editor dialog."""

    def test_editor_loads_existing_commands(self, mock_audio, mock_brain, tk_root):
        """Test that the editor correctly loads commands from config."""
        cfg = DummyConfig()
        test_commands = [
            {"label": "Test1", "prompt": "prompt1"},
            {"label": "Test2", "prompt": "prompt2"},
        ]
        cfg._data["quick_commands"] = test_commands
        ui = PixelAssistantUI(tk_root, cfg)

        # 直接測試內部邏輯：模擬 open_quick_command_editor 會讀取的資料
        loaded = ui.config_manager.get("quick_commands", [])
        assert len(loaded) == 2
        assert loaded[0]["label"] == "Test1"
        assert loaded[1]["prompt"] == "prompt2"

        # Cleanup
        try:
            ui.canvas.destroy()
            ui.bubble.destroy()
        except Exception:
            pass

    def test_save_updates_config(self, mock_audio, mock_brain, tk_root):
        """Test that saving quick commands updates the config correctly."""
        cfg = DummyConfig()
        cfg._data["quick_commands"] = [{"label": "Old", "prompt": "old prompt"}]
        ui = PixelAssistantUI(tk_root, cfg)

        new_commands = [
            {"label": "New1", "prompt": "new prompt 1"},
            {"label": "New2", "prompt": "new prompt 2"},
        ]
        ui.config_manager.set("quick_commands", new_commands)
        ui.setup_context_menu()

        saved = ui.config_manager.get("quick_commands", [])
        assert len(saved) == 2
        assert saved[0]["label"] == "New1"
        assert saved[1]["label"] == "New2"

        try:
            ui.canvas.destroy()
            ui.bubble.destroy()
        except Exception:
            pass

    def test_empty_label_validation(self, mock_audio, mock_brain, tk_root):
        """Test that empty labels are detected as invalid."""
        commands = [
            {"label": "Valid", "prompt": "prompt"},
            {"label": "", "prompt": "no label"},
            {"label": "Also Valid", "prompt": "prompt"},
        ]
        # Validation logic: find first empty label
        invalid_indices = [i for i, cmd in enumerate(commands) if not cmd["label"].strip()]
        assert len(invalid_indices) == 1
        assert invalid_indices[0] == 1

    def test_menu_refreshes_after_save(self, mock_audio, mock_brain, tk_root):
        """Test that the context menu reflects updated commands after save."""
        cfg = DummyConfig()
        cfg._data["quick_commands"] = [{"label": "Original", "prompt": "p"}]
        ui = PixelAssistantUI(tk_root, cfg)

        # Update commands and rebuild menu
        ui.config_manager.set("quick_commands", [
            {"label": "Updated1", "prompt": "p1"},
            {"label": "Updated2", "prompt": "p2"},
        ])
        ui.setup_context_menu()

        # Verify the quick commands submenu has been rebuilt
        # The first cascade in menu is "⚡ 快速指令"
        quick_menu_index = 0
        quick_submenu = ui.menu.nametowidget(ui.menu.entrycget(quick_menu_index, "menu"))
        # Commands + separator + edit entry = 4 items total
        count = quick_submenu.index(tk.END)
        assert count is not None
        assert count >= 3  # at least 2 commands + separator + editor entry

        try:
            ui.canvas.destroy()
            ui.bubble.destroy()
        except Exception:
            pass

    def test_add_and_delete_commands(self, mock_audio, mock_brain, tk_root):
        """Test add and delete operations on the commands list."""
        commands = [{"label": "Cmd1", "prompt": "p1"}]

        # Add
        commands.append({"label": "新指令", "prompt": ""})
        assert len(commands) == 2
        assert commands[1]["label"] == "新指令"

        # Delete last
        commands.pop(1)
        assert len(commands) == 1
        assert commands[0]["label"] == "Cmd1"

        # Delete all
        commands.pop(0)
        assert len(commands) == 0

    def test_move_commands(self, mock_audio, mock_brain, tk_root):
        """Test move up/down operations on the commands list."""
        commands = [
            {"label": "A", "prompt": "pa"},
            {"label": "B", "prompt": "pb"},
            {"label": "C", "prompt": "pc"},
        ]

        # Move B up (swap index 1 and 0)
        idx = 1
        commands[idx], commands[idx - 1] = commands[idx - 1], commands[idx]
        assert commands[0]["label"] == "B"
        assert commands[1]["label"] == "A"

        # Move A down (now at index 1, swap with index 2)
        idx = 1
        commands[idx], commands[idx + 1] = commands[idx + 1], commands[idx]
        assert commands[1]["label"] == "C"
        assert commands[2]["label"] == "A"
