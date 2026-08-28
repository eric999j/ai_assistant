import concurrent.futures
import logging
import time

import google.generativeai as genai

from .config import MODEL_PREFERENCES

logger = logging.getLogger(__name__)

class AIBrain:
    def __init__(self, api_key: str, max_reply_chars: int = 50, model_name: str | None = None) -> None:
        self.api_key = api_key
        self.max_reply_chars = max_reply_chars or 50
        self.target_model_name = model_name
        self.model = None
        self.chat = None
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        if self.api_key:
            self.setup()

    def close(self) -> None:
        if self._executor:
            self._executor.shutdown(wait=False)
            self._executor = None

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    def setup(self) -> bool:
        try:
            genai.configure(api_key=self.api_key)

            # 預設値取自 MODEL_PREFERENCES 首選（避免 hardcode 已棄用型號）
            default_model = MODEL_PREFERENCES[0] if MODEL_PREFERENCES else "models/gemini-2.5-flash"
            model_name = default_model

            if self.target_model_name:
                model_name = self.target_model_name
                logger.info("使用指定模型: %s", model_name)

                # 驗證模型是否存在
                try:
                    found = False
                    for m in genai.list_models():
                        if m.name == model_name or m.name == f"models/{model_name}":
                            found = True
                            if 'generateContent' not in m.supported_generation_methods:
                                raise ValueError(f"模型 {model_name} 不支援 generateContent")
                            break

                    if not found:
                         # 嘗試寬鬆匹配，有些模型名稱可能自動加上 models/ 前綴
                         logger.warning("警告：在 list_models 中未找到 %s，可能已被棄用或無權限。", model_name)
                         # 這裡我們不強制拋出錯誤，因為有時候 API 行為可能會有差異，
                         # 但我們可以嘗試做一個測試調用來確保可用
                         try:
                             test_model = genai.GenerativeModel(model_name)
                             # 使用 count_tokens 作為輕量級測試
                             test_model.count_tokens("test")
                         except Exception as verify_err:
                             raise ValueError(f"模型 {model_name} 驗證失敗: {verify_err}") # 重新拋出更明確的錯誤

                except Exception as e:
                    logger.error("模型驗證錯誤: %s", e)
                    raise
            else:
                # 嘗試列出可用模型以自動選擇
                try:
                    logger.info("正在查詢可用模型列表...")
                    available_models = []
                    for m in genai.list_models():
                        if 'generateContent' in m.supported_generation_methods:
                            available_models.append(m.name)

                    logger.info("可用模型: %s", available_models)

                    # 使用統一的優先順序列表（來自 config）
                    selected = None
                    for pref in MODEL_PREFERENCES:
                        if pref in available_models:
                            selected = pref
                            break

                    if not selected and available_models:
                        # 尋找任何 gemini 模型
                        for m in available_models:
                            if 'gemini' in m:
                                selected = m
                                break
                        # 還是沒有，就選第一個
                        if not selected:
                            selected = available_models[0]

                    if selected:
                        model_name = selected

                except Exception as list_err:
                    logger.warning("列出模型失敗，使用預設値: %s", list_err)

            logger.info("已選擇模型: %s", model_name)

            # 使用者可配置的最大回覆字數，計算 max_output_tokens 上限
            try:
                max_chars = int(self.max_reply_chars)
            except Exception:
                max_chars = 50
            # 中文 1 char ≈ 1~2 tokens，保守給 4x，並夾在 [128, 2048] 之間
            max_out_tokens = max(128, min(2048, max_chars * 4))

            gen_config = {
                "temperature": 0.7,
                "top_p": 0.95,
                "max_output_tokens": max_out_tokens,
            }

            use_search = "gemini" in model_name
            tools = [{"google_search": {}}] if use_search else None
            self.model = self._build_model(model_name, tools=tools, gen_config=gen_config)

            current_date = time.strftime("%Y年%m月%d日")

            self.chat = self.model.start_chat(history=[
                {"role": "user", "parts": [
                    f"你是一個桌面助手。請用簡短、專業、自信的語氣回答。回答盡量在 {max_chars} 字以內。"
                    + f"如果遇到需要即時資訊的問題（如天氣、新聞），請使用搜尋工具查詢後回答，資訊務必精確。今天是 {current_date}。"
                ]}
            ])
            return True
        except Exception as e:
            logger.error("AI Setup Error: %s", e)
            raise

    def _build_model(self, name: str, tools, gen_config):
        """依序嘗試 (tools + generation_config) → (tools) → 基本建構，
        以兼容不同版本的 google-generativeai SDK 與測試 mock。
        """
        attempts: list[dict] = [{"tools": tools, "generation_config": gen_config}]
        if tools:
            attempts.append({"tools": tools})
        attempts.append({})

        last_err: Exception | None = None
        for kwargs in attempts:
            try:
                model = genai.GenerativeModel(name, **kwargs)
                if kwargs.get("tools"):
                    logger.info("已啟用 Google 搜尋 (Grounding)")
                if "generation_config" in kwargs:
                    logger.info("已套用 generation_config: %s", gen_config)
                return model
            except TypeError as e:
                # 舊 SDK 或測試 mock 不支援某些關鍵字，嘗試下一組
                last_err = e
                continue
            except Exception as e:
                last_err = e
                logger.warning("建立模型失敗 (%s)：%s", list(kwargs.keys()), e)
                continue
        if last_err:
            raise last_err
        raise RuntimeError("無法建立 GenerativeModel")

    def ask(self, prompt, image=None, timeout: int = 60):
        if not self.chat:
            raise Exception("AI not initialized")
        if not self._executor:
            raise RuntimeError("AI executor unavailable")

        def _send():
            if image:
                return self.chat.send_message([prompt, image])
            else:
                return self.chat.send_message(prompt)

        future = self._executor.submit(_send)
        try:
            response = future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            future.cancel()
            raise TimeoutError(f"AI 回應逾時（超過 {timeout} 秒），請稍後再試")

        # Gemini 在 SAFETY 等結束原因時 response.text 可能為 None
        if not response.text:
            return "(我無法回應這個問題，可能被內容安全策略攔截，請換個問法再試。)"

        return response.text
