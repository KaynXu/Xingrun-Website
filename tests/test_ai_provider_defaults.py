import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import ai_processor
import app
import config_runtime
from review_plan_workflow.llm import client as review_plan_llm_client


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
                self.assertEqual(app._review_plan_ai_provider_name(), "deepseek")
                self.assertEqual(app._review_plan_chat_model_name(), "deepseek-v4-pro")
                self.assertEqual(app._review_plan_writer_ai_provider_name(), "deepseek")
                self.assertEqual(app._review_plan_writer_chat_model_name(), "deepseek-v4-pro")
                self.assertEqual(review_plan_llm_client.resolve_chat_provider(), "deepseek")
                self.assertEqual(review_plan_llm_client.resolve_chat_model(), "deepseek-v4-pro")
                self.assertFalse(app.has_api_key())
                self.assertFalse(app.has_review_plan_api_key())

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
                self.assertEqual(app._review_plan_chat_model_name(), "deepseek-custom")
                self.assertEqual(app._review_plan_writer_chat_model_name(), "deepseek-v4-pro")

    def test_review_plan_model_can_be_overridden_independently(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            missing_config = Path(tmpdir) / "config.json"
            with patch.object(config_runtime, "CFG_PATH", missing_config), patch.dict(
                os.environ,
                {
                    "XR_REVIEW_PLAN_PROVIDER": "openai",
                    "XR_REVIEW_PLAN_MODEL": "gpt-4.1",
                    "XR_REVIEW_PLAN_REASONING_EFFORT": "high",
                    "XR_OPENAI_BASE_URL": "https://api.iiiiitoken.com/v1",
                    "OPENAI_API_KEY": "sk-openai-test",
                },
                clear=True,
            ):
                cfg = config_runtime.get_runtime_config()
                self.assertEqual(cfg["provider"], "deepseek")
                self.assertEqual(cfg["review_plan_provider"], "openai")
                self.assertEqual(cfg["review_plan_model"], "gpt-4.1")
                self.assertEqual(cfg["review_plan_reasoning_effort"], "high")
                self.assertEqual(cfg["review_plan_writer_provider"], "deepseek")
                self.assertEqual(cfg["review_plan_writer_model"], "")
                self.assertEqual(cfg["openai_base_url"], "https://api.iiiiitoken.com/v1")
                self.assertEqual(app._default_ai_provider_name(), "deepseek")
                self.assertEqual(app._default_chat_model_name(), "deepseek-v4-pro")
                self.assertEqual(app._review_plan_ai_provider_name(), "openai")
                self.assertEqual(app._review_plan_chat_model_name(), "gpt-4.1")
                self.assertEqual(app._review_plan_reasoning_effort(), "high")
                self.assertEqual(app._review_plan_writer_ai_provider_name(), "deepseek")
                self.assertEqual(app._review_plan_writer_chat_model_name(), "deepseek-v4-pro")
                self.assertEqual(review_plan_llm_client.resolve_chat_provider(), "openai")
                self.assertEqual(review_plan_llm_client.resolve_chat_model(), "gpt-4.1")
                self.assertFalse(app.has_api_key())
                self.assertFalse(app.has_review_plan_api_key())

    def test_review_plan_langfuse_observability_is_env_only_and_disabled_by_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            missing_config = Path(tmpdir) / "config.json"
            with patch.object(config_runtime, "CFG_PATH", missing_config), patch.dict(os.environ, {}, clear=True):
                cfg = config_runtime.get_runtime_config()
                self.assertFalse(cfg["review_plan_langfuse_enabled"])
                self.assertEqual(cfg["langfuse_public_key"], "")
                self.assertEqual(cfg["langfuse_secret_key"], "")
                self.assertEqual(cfg["langfuse_base_url"], "")

            with patch.object(config_runtime, "CFG_PATH", missing_config), patch.dict(
                os.environ,
                {
                    "XR_REVIEW_PLAN_LANGFUSE_ENABLED": "true",
                    "LANGFUSE_PUBLIC_KEY": "pk-lf-test",
                    "LANGFUSE_SECRET_KEY": "sk-lf-test",
                    "LANGFUSE_BASE_URL": "https://cloud.langfuse.com",
                },
                clear=True,
            ):
                cfg = config_runtime.get_runtime_config()
                self.assertTrue(cfg["review_plan_langfuse_enabled"])
                self.assertEqual(cfg["langfuse_public_key"], "pk-lf-test")
                self.assertEqual(cfg["langfuse_secret_key"], "sk-lf-test")
                self.assertEqual(cfg["langfuse_base_url"], "https://cloud.langfuse.com")

    def test_review_plan_writer_key_is_required_when_chain_uses_openai(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            missing_config = Path(tmpdir) / "config.json"
            with patch.object(config_runtime, "CFG_PATH", missing_config), patch.dict(
                os.environ,
                {
                    "XR_REVIEW_PLAN_PROVIDER": "openai",
                    "XR_REVIEW_PLAN_MODEL": "gpt-4.1",
                    "OPENAI_API_KEY": "sk-openai-test",
                    "DEEPSEEK_API_KEY": "sk-deepseek-test",
                },
                clear=True,
            ):
                self.assertTrue(app.has_review_plan_api_key())

    def test_review_plan_writer_model_can_be_overridden_independently(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            missing_config = Path(tmpdir) / "config.json"
            with patch.object(config_runtime, "CFG_PATH", missing_config), patch.dict(
                os.environ,
                {
                    "XR_REVIEW_PLAN_WRITER_PROVIDER": "openai",
                    "XR_REVIEW_PLAN_WRITER_MODEL": "gpt-4.1-mini",
                },
                clear=True,
            ):
                cfg = config_runtime.get_runtime_config()
                self.assertEqual(cfg["review_plan_writer_provider"], "openai")
                self.assertEqual(cfg["review_plan_writer_model"], "gpt-4.1-mini")
                self.assertEqual(app._review_plan_writer_ai_provider_name(), "openai")
                self.assertEqual(app._review_plan_writer_chat_model_name(), "gpt-4.1-mini")

    def test_unknown_chat_provider_falls_back_to_deepseek_defaults(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            missing_config = Path(tmpdir) / "config.json"
            with patch.object(config_runtime, "CFG_PATH", missing_config), patch.dict(
                os.environ,
                {"XR_PROVIDER": "legacy-provider"},
                clear=True,
            ):
                cfg = config_runtime.get_runtime_config()
                self.assertEqual(cfg["provider"], "deepseek")
                self.assertEqual(ai_processor._provider_name(), "deepseek")
                self.assertEqual(ai_processor._get_chat_model(), "deepseek-v4-pro")
                self.assertEqual(app._default_ai_provider_name(), "deepseek")
                self.assertEqual(app._default_chat_model_name(), "deepseek-v4-pro")
                self.assertEqual(app._review_plan_ai_provider_name(), "deepseek")
                self.assertEqual(app._review_plan_chat_model_name(), "deepseek-v4-pro")
                self.assertEqual(app._review_plan_writer_ai_provider_name(), "deepseek")
                self.assertEqual(app._review_plan_writer_chat_model_name(), "deepseek-v4-pro")

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

    def test_unknown_vision_provider_falls_back_to_qwen(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            missing_config = Path(tmpdir) / "config.json"
            with patch.object(config_runtime, "CFG_PATH", missing_config), patch.dict(
                os.environ,
                {"XR_VISION_PROVIDER": "legacy-provider"},
                clear=True,
            ):
                cfg = config_runtime.get_runtime_config()
                self.assertEqual(cfg["vision_provider"], "qwen")

    def test_qwen_vision_provider_uses_dashscope_compatible_endpoint(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            missing_config = Path(tmpdir) / "config.json"
            openai_mock = unittest.mock.Mock()
            fake_openai_module = types.SimpleNamespace(OpenAI=openai_mock)
            with patch.object(config_runtime, "CFG_PATH", missing_config), patch.dict(
                os.environ,
                {
                    "XR_VISION_PROVIDER": "qwen",
                    "XR_VISION_MODEL": "qwen-vl-max-latest",
                    "DASHSCOPE_API_KEY": "sk-dashscope-test",
                    "XR_QWEN_BASE_URL": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                },
                clear=True,
            ), patch.dict(sys.modules, {"openai": fake_openai_module}):
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

    def test_openai_chat_provider_uses_configured_compatible_base_url(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            missing_config = Path(tmpdir) / "config.json"
            openai_mock = unittest.mock.Mock()
            fake_openai_module = types.SimpleNamespace(OpenAI=openai_mock)
            with patch.object(config_runtime, "CFG_PATH", missing_config), patch.dict(
                os.environ,
                {
                    "XR_PROVIDER": "openai",
                    "XR_OPENAI_MODEL": "gpt-5.4",
                    "XR_OPENAI_BASE_URL": "https://api.iiiiitoken.com/v1",
                    "OPENAI_API_KEY": "sk-openai-test",
                },
                clear=True,
            ), patch.dict(sys.modules, {"openai": fake_openai_module}):
                client = ai_processor._get_client()

                self.assertEqual(client, openai_mock.return_value)
                openai_mock.assert_called_once_with(
                    api_key="sk-openai-test",
                    base_url="https://api.iiiiitoken.com/v1",
                )


if __name__ == "__main__":
    unittest.main()
