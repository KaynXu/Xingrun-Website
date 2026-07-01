import unittest
from unittest.mock import patch

from config_runtime import (
    resolve_review_plan_model,
    resolve_review_plan_provider,
    resolve_review_plan_writer_model,
    resolve_review_plan_writer_provider,
)
from app import _audio_transcription_model_name, _audio_transcription_provider_name


class ReviewPlanRuntimeContractTestCase(unittest.TestCase):
    def test_review_plan_parent_and_writer_models_are_separate(self):
        cfg = {
            "review_plan_provider": "openai",
            "review_plan_model": "gpt-5.5",
            "review_plan_writer_provider": "deepseek",
            "review_plan_writer_model": "deepseek-v4-pro",
            "provider": "deepseek",
            "model": "deepseek-v4-flash",
        }

        self.assertEqual(resolve_review_plan_provider(cfg), "openai")
        self.assertEqual(resolve_review_plan_model(cfg), "gpt-5.5")
        self.assertEqual(resolve_review_plan_writer_provider(cfg), "deepseek")
        self.assertEqual(resolve_review_plan_writer_model(cfg), "deepseek-v4-pro")

    def test_deepseek_writer_default_remains_v4_pro_when_env_is_omitted(self):
        cfg = {
            "review_plan_provider": "openai",
            "review_plan_model": "gpt-5.5",
            "provider": "deepseek",
            "model": "deepseek-v4-flash",
        }

        self.assertEqual(resolve_review_plan_writer_provider(cfg), "deepseek")
        self.assertEqual(resolve_review_plan_writer_model(cfg), "deepseek-v4-pro")

    def test_review_plan_audio_metadata_uses_tencent_asr_runtime_config(self):
        with patch(
            "app.get_config",
            return_value={
                "audio_transcription_provider": "tencent",
                "tencent_asr_engine_type": "16k_zh",
            },
        ):
            self.assertEqual(_audio_transcription_provider_name(), "tencent")
            self.assertEqual(_audio_transcription_model_name(), "flash-16k_zh")


if __name__ == "__main__":
    unittest.main()
