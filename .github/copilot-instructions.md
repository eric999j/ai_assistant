# Pixel Life Assistant — Copilot Instructions

## 快速指令

```bash
pip install -r requirements.txt          # 安裝依賴
python run_assistant.py                   # 啟動應用
python -m pytest tests/ -q               # 全部測試
python -m pytest tests/test_<module>.py -q  # 單一模組測試
pip-audit                                 # CVE 掃描
```

## 專案概述

Python 桌面智能助手，整合 Google Gemini AI + 像素風格 Conway's Game of Life 動畫。
技術棧：Python 3.8+ / tkinter / google-generativeai / edge-tts / SpeechRecognition / pygame。

## 語言與文檔

- **所有 docstring、註解、commit message 使用繁體中文**
- Docstring 格式：簡要說明 + `Args` / `Returns` / `Raises` 區塊

## 命名規約

| 類型 | 風格 | 範例 |
|------|------|------|
| 類別 | CamelCase | `PixelAssistantUI`, `AIBrain` |
| 函數 / 變數 | snake_case | `spawn_creature`, `grid_data` |
| 常數 | UPPER_CASE | `GRID_W`, `CELL_SIZE`, `FPS` |
| 模組檔案 | snake_case | `game_of_life.py` |

## 專案結構

```
pixel_assistant_app/   # 主程式碼（config / brain / ui / audio / game_of_life）
tests/                 # pytest 測試（test_<module>.py）
scripts/               # pre-commit hook 腳本（機密掃描、CVE 稽核）
reports/               # 安全掃描報告（由 @安全弱點稽核員 agent 產出）
.github/agents/        # Copilot 自訂代理（安全稽核、Code Review）
.github/prompts/       # Copilot 提示範本（generate-tests）
.github/skills/        # Copilot 技能（code-review）
```

- 新模組放 `pixel_assistant_app/`，對應測試放 `tests/test_<module>.py`
- 不要在根目錄建立新 Python 模組（`run_assistant.py` 是唯一入口）

## 架構原則

1. **關注點分離**：`game_of_life.py` 不依賴 tkinter；`brain.py` 不依賴 UI
2. **執行緒安全**：AI 呼叫用 `ThreadPoolExecutor`；音訊用 `threading.Lock`；UI 透過 `queue.Queue` 通訊
3. **優雅降級**：外部依賴（MPV、pygame、麥克風）失敗時 fallback，不直接 crash
4. **配置集中化**：所有設定透過 `ConfigManager` 讀寫 `pixel_config.json`
5. **不暴露機密**：API key 僅存在 `pixel_config.json`（已 .gitignore），禁止硬編碼

## 測試規約

- Mock 模式：`DummyConfig`、`DummyAudio`、`DummyBrain` 避免外部依賴
- Tkinter 測試用 `scope="session"` 的 `tk_root` fixture
- 不呼叫真實 API、不依賴網路、不初始化 pygame
- 測試 docstring 用中文描述測試目的
- assert 附帶清晰的失敗說明訊息
- 新增功能必須附帶對應測試
- 詳細測試慣例見 `.github/prompts/generate-tests.prompt.md`

## 安全要求

- Pre-commit hooks 自動執行 Bandit + 機密偵測（見 `.pre-commit-config.yaml`）
- Pre-push hooks 自動執行 pytest + pip-audit
- 禁止 commit 含有 API key、私鑰等機密資訊
- 新增依賴時確認無已知 CVE
- Bandit 中高嚴重度問題必須修復才能 commit

## 修改後驗證

修改任何模組後，執行對應測試確認無回歸：

| 修改目標 | 驗證指令 |
|---------|---------|
| `game_of_life.py` | `python -m pytest tests/test_game_of_life.py -q` |
| `brain.py` | `python -m pytest tests/test_brain.py -q` |
| `ui.py` | `python -m pytest tests/test_ui.py -q` |
| `audio.py` / `config.py` | `python -m pytest tests/ -q` |
| 跨模組變更 | `python -m pytest tests/ -q` |
