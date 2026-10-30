import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

API_DIR = Path(__file__).resolve().parent.parent / "api"
sys.path.insert(0, str(API_DIR))

from app.classification_config import ClassificationError, provider_is_configured, provider_settings  # noqa: E402
from app.product_categories import _call_model, classification_request  # noqa: E402
from tests.test_product_categories import make_product  # noqa: E402


class ClassificationConfigTest(unittest.TestCase):
    def test_deepseek_is_the_compatible_default(self):
        with patch.dict(os.environ, {}, clear=True):
            settings = provider_settings()
        self.assertEqual(settings.name, "deepseek")
        self.assertEqual(settings.model, "deepseek-flash")
        self.assertEqual(settings.base_url, "https://api.deepseek.com/v1")
        self.assertFalse(provider_is_configured())

    def test_qwen_uses_dashscope_compatible_defaults(self):
        with patch.dict(os.environ, {"CLASSIFICATION_PROVIDER": " QWEN ", "QWEN_API_KEY": "test-qwen"}, clear=True):
            settings = provider_settings()
            self.assertTrue(provider_is_configured())
        self.assertEqual(settings.name, "qwen")
        self.assertEqual(settings.api_key, "test-qwen")
        self.assertEqual(settings.model, "qwen3.7-flash")
        self.assertEqual(settings.base_url, "https://dashscope.aliyuncs.com/compatible-mode/v1")

    def test_qwen_accepts_dashscope_key_fallback(self):
        with patch.dict(os.environ, {"CLASSIFICATION_PROVIDER": "qwen", "DASHSCOPE_API_KEY": "fallback"}, clear=True):
            self.assertEqual(provider_settings().api_key, "fallback")

    def test_other_provider_key_does_not_configure_selected_provider(self):
        with patch.dict(os.environ, {"CLASSIFICATION_PROVIDER": "qwen", "DEEPSEEK_API_KEY": "wrong-provider"}, clear=True):
            self.assertFalse(provider_is_configured())

    def test_invalid_provider_is_rejected(self):
        with patch.dict(os.environ, {"CLASSIFICATION_PROVIDER": "invalid"}, clear=True):
            with self.assertRaises(ClassificationError):
                provider_settings()
            self.assertFalse(provider_is_configured())

    def test_qwen_model_request_uses_selected_endpoint_key_and_model(self):
        response = MagicMock()
        response.read.return_value = json.dumps({"choices": [{"message": {"content": "{}"}}]}).encode()
        response.__enter__.return_value = response
        with patch.dict(os.environ, {"CLASSIFICATION_PROVIDER": "qwen", "QWEN_API_KEY": "test-qwen"}, clear=True), patch(
            "app.product_categories.urlopen", return_value=response
        ) as urlopen:
            _call_model(make_product())
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions")
        self.assertEqual(request.headers["Authorization"], "Bearer test-qwen")
        self.assertEqual(json.loads(request.data)["model"], "qwen3.7-flash")
        with patch.dict(os.environ, {"CLASSIFICATION_PROVIDER": "qwen"}, clear=True):
            self.assertEqual(classification_request(make_product())["model"], "qwen3.7-flash")
            self.assertEqual(
                classification_request(make_product())["chat_template_kwargs"],
                {"enable_thinking": False},
            )

    def test_deepseek_request_does_not_disable_thinking(self):
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test"}, clear=True):
            self.assertNotIn("chat_template_kwargs", classification_request(make_product()))


if __name__ == "__main__":
    unittest.main()
