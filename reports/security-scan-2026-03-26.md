# 安全掃描報告

**日期**：2026-03-26
**專案**：pixel_assistant_app
**模式**：快速掃描
**執行者**：安全弱點稽核員 agent

---

## 安全掃描摘要

### 掃描範圍
- `pixel_assistant_app/` — 主應用程式套件
- `scripts/` — 輔助腳本
- `run_assistant.py` — 進入點
- `requirements.txt` — 依賴套件清單
- `pixel_config.json` — 設定檔（機密掃描）
- `git log` — 歷史提交機密掃描

### 執行工具與版本
| 工具 | 版本 | 用途 |
|------|------|------|
| pip-audit | 2.10.0 | 依賴套件 CVE 掃描 |
| bandit | 1.9.4 | 靜態安全分析 |
| 自訂 regex 掃描 | — | 機密模式比對（check_secrets.py） |
| git log 審查 | — | 歷史提交機密確認 |

### 涵蓋範圍缺口
- gitleaks/trufflehog 未安裝，改用 regex 備援掃描
- 未掃描 `tests/` 目錄（測試程式碼非主要風險面）

---

## 發現事項（嚴重→低）

### 1. 嚴重度：低（間接依賴 CVE）

- **問題描述**：間接依賴套件 `pygments 2.19.2` 存在已知 CVE
- **CVE 編號**：CVE-2026-4539
- **證據**：pip-audit 回報（非 requirements.txt 直接依賴，為工具鏈間接引入）
- **影響說明**：
  - 專案應用程式未直接呼叫 pygments API，實際執行時風險極低
  - dependency-checker 子代理評估：開發環境間接依賴，生產執行路徑未使用受影響功能
- **建議修復**：`pip install pygments --upgrade`

### 2. 嚴重度：低（subprocess 使用 B603）

- **問題描述**：`audio.py` 使用 `subprocess.Popen` 呼叫 mpv
- **證據**：`audio.py:69`, `audio.py:180`
- **影響說明**：所有參數為內部控制（shutil.which、固定路徑、型別限制整數），無注入向量，判定誤報
- **建議**：加 `# nosec B603` 注釋

### 3. 嚴重度：低（try/except pass B110）

- **問題描述**：9 處靜默吞掉異常
- **證據**：`audio.py:99,146,209`、`brain.py:28`、`ui.py:81,113,492,588,609,839`、`check_secrets.py:27`
- **影響說明**：安全相關錯誤可能被隱藏，影響可觀測性
- **建議**：改為 `except Exception as e: logger.debug(..., e)`

### 4. 嚴重度：低（非加密亂數 B311）

- **問題描述**：UI 視覺效果使用 `random.random()`
- **證據**：`game_of_life.py:37`, `ui.py:414`
- **影響說明**：純視覺用途，判定誤報
- **建議**：加 `# nosec B311` 注釋

---

## 機密掃描結果

| 項目 | 結果 |
|------|------|
| 原始碼 API Key 模式 | ✅ 未發現 |
| pixel_config.json api_key | ✅ 空字串 |
| git 歷史 api_key | ✅ 歷史中均為空字串 |
| .gitignore 覆蓋 pixel_config.json | ✅ 已正確忽略 |

---

## 速效改善

1. `pip install pygments --upgrade`（等待 CVE-2026-4539 修復版本）
2. 對 `audio.py:69,180` 加上 `# nosec B603`
3. 在 except pass 處加入 `logger.debug()` 日誌
4. CI 加入驗證 `pixel_config.example.json` 的 api_key 必須為空

---

## 建議重現指令

```bash
python -m pip_audit -r requirements.txt --skip-editable
python -m bandit -r pixel_assistant_app/ scripts/ run_assistant.py
python scripts/check_secrets.py pixel_assistant_app/*.py run_assistant.py
git log --all -p -- pixel_config.json | grep "api_key"
```

---

## 整體風險評估：低

| 類別 | 發現數 | 最高嚴重度 |
|------|--------|-----------|
| 依賴套件 CVE | 1 | 低（間接依賴） |
| 靜態分析 | 18 | 低 |
| 機密洩漏 | 0 | 無 |

> 整體安全狀態良好，無中/高嚴重度發現。
