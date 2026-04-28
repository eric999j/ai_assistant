"""
測試 AIBrain 模組
驗證 AI 初始化、對話、錯誤處理等邏輯
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import types
import concurrent.futures

import pytest

from pixel_assistant_app.brain import AIBrain


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

class DummyModel:
    """模擬 genai.GenerativeModel"""
    def __init__(self, name=None, tools=None):
        self.name = name
        self.tools = tools

    def start_chat(self, history=None):
        return DummyChat()

    def count_tokens(self, text):
        return types.SimpleNamespace(total_tokens=5)


class DummyChat:
    """模擬 chat session"""
    def send_message(self, content):
        text = content if isinstance(content, str) else str(content)
        return types.SimpleNamespace(text=f"echo: {text}")


class DummyModelInfo:
    """模擬 genai.list_models 回傳的模型資訊"""
    def __init__(self, name, methods=None):
        self.name = name
        self.supported_generation_methods = methods or ['generateContent']


class DummyGenAI:
    """模擬 google.generativeai 模組的必要方法"""
    configured_key = None
    _models = [
        DummyModelInfo("models/gemini-2.5-flash"),
        DummyModelInfo("models/gemini-2.0-flash"),
        DummyModelInfo("models/gemini-1.5-flash"),
    ]

    @staticmethod
    def configure(api_key=None):
        DummyGenAI.configured_key = api_key

    @staticmethod
    def list_models():
        return iter(DummyGenAI._models)

    @staticmethod
    def GenerativeModel(name, tools=None):
        return DummyModel(name=name, tools=tools)


@pytest.fixture(autouse=True)
def mock_genai(monkeypatch):
    """將 brain 模組中的 genai 替換為 DummyGenAI"""
    monkeypatch.setattr('pixel_assistant_app.brain.genai', DummyGenAI)


# ---------------------------------------------------------------------------
# 初始化測試
# ---------------------------------------------------------------------------

class TestAIBrainInit:
    """測試 AIBrain 初始化行為"""

    def test_init_with_api_key_calls_setup(self):
        """有 api_key 時應自動呼叫 setup，建立 model 與 chat"""
        brain = AIBrain(api_key="test-key", max_reply_chars=100)
        assert brain.model is not None, "應建立 model 物件"
        assert brain.chat is not None, "應建立 chat session"
        brain.close()

    def test_init_without_api_key_skips_setup(self):
        """無 api_key 時不應呼叫 setup"""
        brain = AIBrain(api_key=None)
        assert brain.model is None, "api_key 為 None 時不應建立 model"
        assert brain.chat is None, "api_key 為 None 時不應建立 chat"
        brain.close()

    def test_init_with_empty_api_key_skips_setup(self):
        """空字串 api_key 為 falsy，不應呼叫 setup"""
        brain = AIBrain(api_key="")
        assert brain.model is None, "空字串 api_key 不應觸發 setup"
        brain.close()

    def test_max_reply_chars_default(self):
        """未指定 max_reply_chars 時應使用預設值 50"""
        brain = AIBrain(api_key=None, max_reply_chars=None)
        assert brain.max_reply_chars == 50, "預設 max_reply_chars 應為 50"
        brain.close()

    def test_max_reply_chars_zero_uses_default(self):
        """max_reply_chars 為 0 時應 fallback 到 50"""
        brain = AIBrain(api_key=None, max_reply_chars=0)
        assert brain.max_reply_chars == 50, "max_reply_chars=0 應 fallback 到 50"
        brain.close()

    def test_custom_max_reply_chars(self):
        """自訂 max_reply_chars 應被保留"""
        brain = AIBrain(api_key=None, max_reply_chars=300)
        assert brain.max_reply_chars == 300
        brain.close()


# ---------------------------------------------------------------------------
# setup 測試
# ---------------------------------------------------------------------------

class TestAIBrainSetup:
    """測試 setup 方法的模型選擇邏輯"""

    def test_setup_with_specified_model(self):
        """指定 model_name 時應使用該模型"""
        brain = AIBrain(api_key="key", model_name="models/gemini-2.0-flash")
        assert brain.target_model_name == "models/gemini-2.0-flash"
        assert brain.chat is not None
        brain.close()

    def test_setup_auto_selects_preferred_model(self):
        """未指定 model_name 時應依 MODEL_PREFERENCES 自動選擇"""
        brain = AIBrain(api_key="key")
        assert brain.model is not None, "自動選擇模型應成功"
        brain.close()

    def test_setup_configures_api_key(self):
        """setup 應以 api_key 呼叫 genai.configure"""
        DummyGenAI.configured_key = None
        brain = AIBrain(api_key="my-secret-key")
        assert DummyGenAI.configured_key == "my-secret-key", "應以正確的 api_key 設定 genai"
        brain.close()

    def test_setup_invalid_model_raises(self, monkeypatch):
        """指定不存在的模型且驗證失敗時應拋出例外"""
        def bad_count_tokens(self, text):
            raise Exception("model not found")

        monkeypatch.setattr(DummyModel, 'count_tokens', bad_count_tokens)
        # 讓 list_models 回傳空列表，使模型找不到
        monkeypatch.setattr(DummyGenAI, '_models', [])

        with pytest.raises(ValueError, match="驗證失敗"):
            AIBrain(api_key="key", model_name="models/nonexistent-model")

    def test_setup_genai_error_propagates(self, monkeypatch):
        """genai.configure 失敗時應把例外向上傳遞"""
        def bad_configure(api_key=None):
            raise RuntimeError("network error")

        monkeypatch.setattr(DummyGenAI, 'configure', staticmethod(bad_configure))

        with pytest.raises(RuntimeError, match="network error"):
            AIBrain(api_key="key")


# ---------------------------------------------------------------------------
# ask 測試
# ---------------------------------------------------------------------------

class TestAIBrainAsk:
    """測試 ask 方法的對話邏輯"""

    def test_ask_returns_response_text(self):
        """正常 ask 應回傳模型的回應文字"""
        brain = AIBrain(api_key="key")
        result = brain.ask("你好")
        assert "echo:" in result, "回應應包含 DummyChat 的 echo 內容"
        brain.close()

    def test_ask_without_init_raises(self):
        """chat 未初始化時呼叫 ask 應拋出例外"""
        brain = AIBrain(api_key=None)
        with pytest.raises(Exception, match="AI not initialized"):
            brain.ask("hello")
        brain.close()

    def test_ask_with_image(self):
        """傳入 image 參數時應能正常回應"""
        brain = AIBrain(api_key="key")
        fake_image = b"fake-image-bytes"
        result = brain.ask("描述這張圖", image=fake_image)
        assert result is not None, "帶圖片的 ask 應成功回傳"
        brain.close()

    def test_ask_timeout_raises(self, monkeypatch):
        """回應逾時應拋出 TimeoutError"""
        brain = AIBrain(api_key="key")

        def slow_send(content):
            import time
            time.sleep(5)
            return types.SimpleNamespace(text="too late")

        brain.chat.send_message = slow_send
        with pytest.raises(TimeoutError, match="逾時"):
            brain.ask("hello", timeout=1)
        brain.close()

    def test_ask_empty_response_returns_fallback(self):
        """模型回應 text 為 None 時應回傳安全提示文字"""
        brain = AIBrain(api_key="key")

        def null_send(content):
            return types.SimpleNamespace(text=None)

        brain.chat.send_message = null_send
        result = brain.ask("敏感問題")
        assert "無法回應" in result, "text 為 None 時應回傳 fallback 訊息"
        brain.close()


# ---------------------------------------------------------------------------
# close / 生命週期測試
# ---------------------------------------------------------------------------

class TestAIBrainLifecycle:
    """測試資源清理與生命週期"""

    def test_close_shuts_down_executor(self):
        """close 應關閉 executor 並設為 None"""
        brain = AIBrain(api_key="key")
        assert brain._executor is not None
        brain.close()
        assert brain._executor is None, "close 後 executor 應為 None"

    def test_double_close_no_error(self):
        """重複呼叫 close 不應拋出例外"""
        brain = AIBrain(api_key="key")
        brain.close()
        brain.close()  # 不應出錯

    def test_ask_after_close_raises(self):
        """close 後呼叫 ask 應拋出 RuntimeError"""
        brain = AIBrain(api_key="key")
        brain.close()
        with pytest.raises(RuntimeError, match="executor unavailable"):
            brain.ask("hello")
