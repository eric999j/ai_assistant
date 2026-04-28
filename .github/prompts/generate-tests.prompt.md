---
description: "為指定模組或函式產生 pytest 測試。USE FOR: 產生測試、寫測試、新增單元測試、補測試覆蓋率"
---

# 產生 Pytest 測試

根據使用者指定的模組或函式，產生符合專案慣例的 pytest 測試。

## 輸入

- `$input`：目標模組路徑或函式名稱（例如 `pixel_assistant_app/brain.py` 或 `GameOfLife.step`）

## 專案測試慣例

遵循以下已建立的模式：

1. **測試檔案位置**：`tests/test_<module>.py`
2. **Mock 模式**：使用專案既有的 Dummy 類別避免外部依賴：
   - `DummyConfig`：模擬 `ConfigManager`，預設含 `{'api_key': 'dummy'}`
   - `DummyAudio`：模擬 `AudioHandler`，避免初始化 pygame
   - `DummyBrain`：模擬 `AIBrain`，避免真實 API 呼叫
3. **Fixture 模式**：用 `monkeypatch` 替換依賴，用 `pytest.fixture` 建立可重用的測試物件
4. **Tkinter 測試**：使用 `scope="session"` 的 `tk_root` fixture，測試結束時 cleanup widgets
5. **Docstring**：使用中文描述測試目的
6. **斷言訊息**：assert 附帶清晰的失敗說明

## 產出要求

1. 先閱讀目標模組原始碼，理解所有公開方法與邊界條件
2. 檢查 `tests/` 是否已有對應測試檔案，有則新增測試，無則建立新檔
3. 產生的測試應涵蓋：
   - 正常路徑（happy path）
   - 邊界條件（空輸入、極端值）
   - 錯誤處理路徑（異常、無效輸入）
4. 不要測試 private 方法（`_` 開頭），除非該方法有複雜邏輯且無法透過公開 API 間接測試
5. 不要呼叫真實外部服務（API、網路、pygame）
6. 產完後執行 `python -m pytest tests/test_<module>.py -q` 驗證通過
