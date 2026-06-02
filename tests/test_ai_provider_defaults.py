import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import ai_processor
import app
import config_runtime


class AiProviderDefaultsTest(unittest.TestCase):
    def test_unconfigured_runtime_defaults_to_deepseek_v4_pro(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            missing_config = Path(tmpdir) / "config.json"
            with patch.object(config_runtime, "CFG_PATH", missing_config), patch.dict(os.environ, {}, clear=True):
                cfg = config_runtime.get_runtime_config()

                self.assertEqual(cfg["provider"], "deepseek")
                self.assertEqual(cfg["vision_provider"], "qwen")
                self.assertEqual(cfg["vision_model"], "qwen-vl-max-latest")
                self.assertEqual(ai_processor._provider_name(), "deepseek")
                self.assertEqual(ai_processor._get_chat_model(), "deepseek-v4-pro")
                self.assertEqual(ai_processor._get_vision_model(), "qwen-vl-max-latest")
                self.assertEqual(app._default_ai_provider_name(), "deepseek")
                self.assertEqual(app._default_chat_model_name(), "deepseek-v4-pro")
                self.assertFalse(app.has_api_key())

    def test_deepseek_default_requires_deepseek_key_not_openai_key(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            missing_config = Path(tmpdir) / "config.json"
            with patch.object(config_runtime, "CFG_PATH", missing_config), patch.dict(
                os.environ,
                {"OPENAI_API_KEY": "sk-openai-test"},
                clear=True,
            ):
                self.assertFalse(app.has_api_key())

            with patch.object(config_runtime, "CFG_PATH", missing_config), patch.dict(
                os.environ,
                {"DEEPSEEK_API_KEY": "sk-deepseek-test"},
                clear=True,
            ):
                self.assertTrue(app.has_api_key())

    def test_deepseek_model_can_be_overridden_by_environment(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            missing_config = Path(tmpdir) / "config.json"
            with patch.object(config_runtime, "CFG_PATH", missing_config), patch.dict(
                os.environ,
                {"XR_DEEPSEEK_MODEL": "deepseek-custom"},
                clear=True,
            ):
                self.assertEqual(config_runtime.get_runtime_config()["deepseek_model"], "deepseek-custom")
                self.assertEqual(ai_processor._get_chat_model(), "deepseek-custom")
                self.assertEqual(app._default_chat_model_name(), "deepseek-custom")

    def test_vision_model_can_be_overridden_by_environment(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            missing_config = Path(tmpdir) / "config.json"
            with patch.object(config_runtime, "CFG_PATH", missing_config), patch.dict(
                os.environ,
                {"XR_VISION_PROVIDER": "qwen", "XR_VISION_MODEL": "qwen-vl-plus-latest"},
                clear=True,
            ):
                cfg = config_runtime.get_runtime_config()
                self.assertEqual(cfg["vision_provider"], "qwen")
                self.assertEqual(cfg["vision_model"], "qwen-vl-plus-latest")
                self.assertEqual(ai_processor._get_vision_model(), "qwen-vl-plus-latest")

    def test_qwen_vision_provider_uses_dashscope_compatible_endpoint(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            missing_config = Path(tmpdir) / "config.json"
            with patch.object(config_runtime, "CFG_PATH", missing_config), patch.dict(
                os.environ,
                {
                    "XR_VISION_PROVIDER": "qwen",
                    "XR_VISION_MODEL": "qwen-vl-max-latest",
                    "DASHSCOPE_API_KEY": "sk-dashscope-test",
                    "XR_QWEN_BASE_URL": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                },
                clear=True,
            ), patch("openai.OpenAI") as openai_mock:
                cfg = config_runtime.get_runtime_config()
                client = ai_processor._get_vision_client()

                self.assertEqual(cfg["vision_provider"], "qwen")
                self.assertEqual(cfg["vision_model"], "qwen-vl-max-latest")
                self.assertEqual(cfg["qwen_api_key"], "sk-dashscope-test")
                self.assertEqual(cfg["qwen_base_url"], "https://dashscope.aliyuncs.com/compatible-mode/v1")
                self.assertEqual(client, openai_mock.return_value)
                openai_mock.assert_called_once_with(
                    api_key="sk-dashscope-test",
                    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                )


if __name__ == "__main__":
    unittest.main()
