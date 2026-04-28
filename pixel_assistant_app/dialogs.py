"""快速指令編輯器、文字輸入、歡迎訊息編輯等對話框。

所有對話框設計為純函式（接受 parent 與 callbacks），不直接依賴 PixelAssistantUI 類別，
以利測試與重複使用。
"""
from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import messagebox, simpledialog


def _position_near(dialog: tk.Toplevel, parent: tk.Tk) -> None:
    """將對話框定位於 parent 周邊。"""
    dialog.update_idletasks()
    dw, dh = dialog.winfo_width(), dialog.winfo_height()
    ax, ay = parent.winfo_x(), parent.winfo_y()
    aw = parent.winfo_width()
    sw = parent.winfo_screenwidth()
    sh = parent.winfo_screenheight()

    tx = ax + (aw - dw) // 2
    ty = ay - dh - 20
    if tx < 10:
        tx = 10
    if tx + dw > sw - 10:
        tx = sw - dw - 10
    if ty < 10:
        ty = ay
        if ax > dw + 20:
            tx = ax - dw - 20
        else:
            tx = ax + aw + 20
    if ty + dh > sh - 10:
        ty = sh - dh - 40
    dialog.geometry(f"+{tx}+{ty}")


def ask_text_command(parent: tk.Tk) -> str | None:
    """彈出文字輸入對話框，回傳使用者輸入或 None。"""
    dialog = tk.Toplevel(parent)
    dialog.title("輸入指令")
    dialog.transient(parent)
    dialog.grab_set()

    tk.Label(dialog, text="你想對助手說什麼？", font=("Arial", 10)).pack(padx=15, pady=(15, 5))
    entry = tk.Entry(dialog, width=50, font=("Arial", 10))
    entry.pack(padx=15, pady=5)
    entry.focus_set()

    _position_near(dialog, parent)
    dialog.resizable(False, False)

    result: dict[str, str | None] = {"text": None}

    def on_submit(_event=None):
        result["text"] = entry.get()
        dialog.destroy()

    def on_cancel(_event=None):
        dialog.destroy()

    entry.bind("<Return>", on_submit)
    dialog.bind("<Escape>", on_cancel)

    btn_frame = tk.Frame(dialog)
    btn_frame.pack(pady=(5, 15))
    tk.Button(btn_frame, text="確定", width=10, command=on_submit).pack(side=tk.LEFT, padx=5)
    tk.Button(btn_frame, text="取消", width=10, command=on_cancel).pack(side=tk.LEFT, padx=5)

    dialog.wait_window()
    return result["text"]


def open_quick_command_editor(
    parent: tk.Tk,
    initial_commands: list[dict],
    on_save: Callable[[list[dict]], None],
) -> None:
    """快速指令編輯器。儲存時呼叫 on_save(new_commands)。"""
    dialog = tk.Toplevel(parent)
    dialog.title("編輯快速指令")
    dialog.transient(parent)
    dialog.grab_set()

    commands = [{"label": qc.get("label", ""), "prompt": qc.get("prompt", "")} for qc in (initial_commands or [])]
    current_index = {"val": -1}

    left_frame = tk.Frame(dialog)
    left_frame.pack(side=tk.LEFT, fill=tk.BOTH, padx=(10, 5), pady=10)

    tk.Label(left_frame, text="指令列表", font=("Arial", 10, "bold")).pack(anchor="w")
    listbox = tk.Listbox(left_frame, width=18, height=15, font=("Arial", 10), exportselection=False)
    listbox.pack(fill=tk.BOTH, expand=True)

    left_btn_frame = tk.Frame(left_frame)
    left_btn_frame.pack(fill=tk.X, pady=(5, 0))

    right_frame = tk.Frame(dialog)
    right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 10), pady=10)

    tk.Label(right_frame, text="指令名稱", font=("Arial", 10, "bold")).pack(anchor="w")
    label_entry = tk.Entry(right_frame, width=40, font=("Arial", 10))
    label_entry.pack(fill=tk.X, pady=(0, 8))

    tk.Label(right_frame, text="Prompt 模板", font=("Arial", 10, "bold")).pack(anchor="w")
    tk.Label(right_frame, text="提示：可用 {clipboard} 插入剪貼簿內容", font=("Arial", 8), fg="gray").pack(anchor="w")
    prompt_text = tk.Text(right_frame, width=40, height=12, font=("Arial", 10), wrap=tk.WORD)
    prompt_text.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

    def refresh_listbox(select_idx=None):
        listbox.delete(0, tk.END)
        for cmd in commands:
            listbox.insert(tk.END, cmd["label"] or "(未命名)")
        if select_idx is not None and 0 <= select_idx < len(commands):
            listbox.selection_set(select_idx)
            listbox.see(select_idx)
            load_command(select_idx)
        elif not commands:
            clear_editor()

    def save_current_edit():
        idx = current_index["val"]
        if 0 <= idx < len(commands):
            commands[idx]["label"] = label_entry.get().strip()
            commands[idx]["prompt"] = prompt_text.get("1.0", tk.END).rstrip("\n")
            listbox.delete(idx)
            listbox.insert(idx, commands[idx]["label"] or "(未命名)")
            listbox.selection_set(idx)

    def load_command(idx):
        current_index["val"] = idx
        label_entry.delete(0, tk.END)
        label_entry.insert(0, commands[idx]["label"])
        prompt_text.delete("1.0", tk.END)
        prompt_text.insert("1.0", commands[idx]["prompt"])

    def clear_editor():
        current_index["val"] = -1
        label_entry.delete(0, tk.END)
        prompt_text.delete("1.0", tk.END)

    def on_listbox_select(_event=None):
        sel = listbox.curselection()
        if not sel:
            return
        new_idx = sel[0]
        if new_idx == current_index["val"]:
            return
        save_current_edit()
        load_command(new_idx)

    listbox.bind("<<ListboxSelect>>", on_listbox_select)

    def cmd_add():
        save_current_edit()
        commands.append({"label": "新指令", "prompt": ""})
        refresh_listbox(select_idx=len(commands) - 1)
        label_entry.focus_set()
        label_entry.select_range(0, tk.END)

    def cmd_delete():
        idx = current_index["val"]
        if idx < 0 or idx >= len(commands):
            return
        commands.pop(idx)
        new_idx = min(idx, len(commands) - 1)
        current_index["val"] = -1
        refresh_listbox(select_idx=new_idx if commands else None)

    def cmd_move_up():
        idx = current_index["val"]
        if idx <= 0:
            return
        save_current_edit()
        commands[idx], commands[idx - 1] = commands[idx - 1], commands[idx]
        refresh_listbox(select_idx=idx - 1)

    def cmd_move_down():
        idx = current_index["val"]
        if idx < 0 or idx >= len(commands) - 1:
            return
        save_current_edit()
        commands[idx], commands[idx + 1] = commands[idx + 1], commands[idx]
        refresh_listbox(select_idx=idx + 1)

    tk.Button(left_btn_frame, text="＋ 新增", width=8, command=cmd_add).pack(side=tk.LEFT, padx=2)
    tk.Button(left_btn_frame, text="－ 刪除", width=8, command=cmd_delete).pack(side=tk.LEFT, padx=2)
    tk.Button(left_btn_frame, text="▲", width=3, command=cmd_move_up).pack(side=tk.LEFT, padx=2)
    tk.Button(left_btn_frame, text="▼", width=3, command=cmd_move_down).pack(side=tk.LEFT, padx=2)

    bottom_frame = tk.Frame(dialog)
    bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=(0, 10))

    def do_save():
        save_current_edit()
        for i, cmd in enumerate(commands):
            if not cmd["label"].strip():
                listbox.selection_clear(0, tk.END)
                listbox.selection_set(i)
                listbox.see(i)
                load_command(i)
                label_entry.focus_set()
                messagebox.showwarning("驗證錯誤", f"第 {i+1} 條指令的名稱不可為空。", parent=dialog)
                return
        on_save(commands)
        dialog.destroy()

    def do_cancel():
        dialog.destroy()

    tk.Button(bottom_frame, text="儲存", width=10, command=do_save).pack(side=tk.RIGHT, padx=5)
    tk.Button(bottom_frame, text="取消", width=10, command=do_cancel).pack(side=tk.RIGHT, padx=5)
    dialog.bind("<Escape>", lambda e: do_cancel())

    refresh_listbox(select_idx=0 if commands else None)

    _position_near(dialog, parent)
    dialog.geometry(f"600x400+{dialog.winfo_x()}+{dialog.winfo_y()}")
    dialog.resizable(False, False)
    dialog.wait_window()


def edit_welcome_message(
    parent: tk.Tk,
    current_text: str,
    current_always: bool,
    on_save: Callable[[str, bool], None],
) -> None:
    new = simpledialog.askstring("編輯歡迎訊息", "歡迎訊息內容：", initialvalue=current_text, parent=parent)
    if new is None:
        return
    always = messagebox.askyesno(
        "每次播放？",
        f"目前設定為每次啟動播放: {current_always}\n是否要在每次啟動時都播放歡迎訊息？",
        parent=parent,
    )
    on_save(new, always)
