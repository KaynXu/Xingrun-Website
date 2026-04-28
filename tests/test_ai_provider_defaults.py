import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import ai_processor
import app
import config_runtime


class AiProviderDefaultsTest(unittest.TestCase):
    def test_unconfigured_runtime_defaults_to_deepseek_chat(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            missing_config = Path(tmpdir) / "config.json"
            with patch.object(config_runtime, "CFG_PATH", missing_config), patch.dict(os.environ, {}, clear=True):
                cfg = config_runtime.get_runtime_config()

                self.assertEqual(cfg["provider"], "deepseek")
                self.assertEqual(ai_processor._provider_name(), "deepseek")
                self.assertEqual(ai_processor._get_chat_model(), "deepseek-chat")
                self.assertEqual(app._default_ai_provider_name(), "deepseek")
                self.assertEqual(app._default_chat_model_name(), "deepseek-chat")
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


if __name__ == "__main__":
    unittest.main()
