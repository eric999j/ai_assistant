import tkinter as tk

from pixel_assistant_app.config import ConfigManager
from pixel_assistant_app.logging_setup import setup_logging
from pixel_assistant_app.ui import PixelAssistantUI


def main():
    setup_logging()
    root = tk.Tk()
    config = ConfigManager()
    PixelAssistantUI(root, config)
    root.mainloop()


if __name__ == "__main__":
    main()
