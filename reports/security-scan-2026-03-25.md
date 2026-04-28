# 安全掃描報告 — ai_assistant

**掃描時間**: 2026-03-25
**掃描模式**: 快速模式
**前次修復驗證**: pillow CVE-2026-25990 ✅ 已修復 | SSRF 防護 ✅ 已加入

---

## 安全掃描摘要

- **掃描範圍**: Python 桌面助手專案 (`pixel_assistant_app/`, `run_assistant.py`)
- **執行工具與版本**:
  - pip-audit 2.10.0 — 依賴套件 CVE 掃描
  - bandit 1.9.4 — Python 靜態安全分析 (1143 行程式碼)
  - regex 手動掃描 — 機密與憑證檢查
- **涵蓋範圍缺口**: 未使用 gitleaks/trufflehog 掃描 git 歷史（快速模式）
- **已安裝 pillow 版本**: 12.1.1（已升級）

---

## 前次修復驗證

| 項目 | 狀態 | 說明 |
|------|------|------|
| pillow CVE-2026-25990 | ✅ 已修復 | 升級至 12.1.1，pip-audit 不再報告 |
| SSRF 防護 | ✅ 已加入 | `_is_safe_url()` 方法阻擋 private/loopback/reserved IP |

---

## 發現事項（嚴重 → 低）

### 1. 嚴重度：**低** — 間接依賴 pygments CVE-2026-4539（無修復版本）

- **問題描述**: `pygments==2.19.2`（pytest 的間接依賴）存在 ReDoS 弱點 (CVE-2026-4539)，影響 `AdlLexer`
- **證據**: pip-audit 掃描結果；`pygments` 非專案直接依賴，由 `pytest` 間接引入
- **影響說明**: 此弱點需要**本地存取**才能觸發，且影響的是 `AdlLexer`（Archetype Definition Language），本專案不使用該 lexer。此外 `pygments` 為開發依賴（pytest），不會在生產環境中執行。**實際風險極低**。
- **Fix Versions**: 尚無修復版本發布
- **建議修復方式**: 持續監控，待 pygments 發布修復版本後升級；或將 pytest 移至 dev-dependencies

### 2. 嚴重度：**低** — API Key 明文存儲於設定檔

- **問題描述**: `pixel_config.json` 以明文 JSON 儲存 Google Gemini API Key
- **證據**: `pixel_assistant_app/config.py` L88、`pixel_assistant_app/ui.py` L56
- **影響說明**: `.gitignore` 已正確排除 `pixel_config.json`，風險受控
- **建議修復方式**: 優先使用環境變數 `GEMINI_API_KEY`；考慮使用 OS keyring

### 3. 嚴重度：**低** — subprocess 呼叫 (CWE-78)

- **問題描述**: `AudioHandler` 使用 `subprocess.Popen` 呼叫外部 mpv
- **證據**: `pixel_assistant_app/audio.py` L69、L180
- **影響說明**: 使用列表形式（非 `shell=True`），注入風險低；`file_path` 來自硬編碼暫存檔
- **建議修復方式**: 加入路徑驗證（限制特定目錄）

### 4. 嚴重度：**低** — 多處 except + pass 吞噬異常 (CWE-703)

- **問題描述**: 7 處使用 `except Exception: pass`
- **證據**: bandit 標記 audio.py (3處)、brain.py (1處)、ui.py (3處)
- **影響說明**: 資源清理中可接受，業務邏輯中應記錄 log
- **建議修復方式**: 將 `pass` 改為 `logger.debug(...)`

### 5. 嚴重度：**資訊** — 非加密 PRNG (CWE-330) [誤報]

- **問題描述**: `game_of_life.py` 使用 `random.random()`
- **影響說明**: 遊戲視覺展示用途，**無安全風險**

---

## 掃描統計

| 指標 | 數值 |
|------|------|
| bandit 嚴重 | 0 |
| bandit 高 | 0 |
| bandit 中 | 0 |
| bandit 低 | 15 |
| pip-audit CVE | 1（pygments，間接依賴，無修復版本） |
| 機密洩漏 | 0 |

---

## 速效改善

1. **將 pytest 移至 dev-dependencies**: 避免 pygments 弱點影響生產環境判斷
2. **異常處理改善**: 在非清理路徑的 `except: pass` 改為 `logger.warning(...)`
3. **考慮使用 keyring**: 取代明文 JSON 儲存 API Key

---

## 建議重現指令

```powershell
# 依賴弱點掃描
pip-audit -r requirements.txt

# 靜態安全掃描（僅中高嚴重度）
bandit -r pixel_assistant_app run_assistant.py -ll

# 靜態安全掃描（全嚴重度）
bandit -r pixel_assistant_app run_assistant.py

# 機密掃描（regex）
Select-String -Recurse -Pattern "AIza[0-9A-Za-z_-]{35}|sk-[a-zA-Z0-9]{20,}" -Include *.py,*.json,*.md

# 完整模式建議（需額外安裝 gitleaks）
# gitleaks detect --source . --verbose
```
