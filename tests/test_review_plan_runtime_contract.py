import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app as app_module
import config_runtime
import lesson_manager
from tests.review_plan_test_utils import valid_single_lesson_plan

from app import _audio_transcription_model_name, _audio_transcription_provider_name
from config_runtime import (
    resolve_review_plan_model,
    resolve_review_plan_provider,
    resolve_review_plan_writer_model,
    resolve_review_plan_writer_provider,
)

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "verify_review_plan_runtime_contract.py"


def load_runtime_contract_script():
    spec = importlib.util.spec_from_file_location("verify_review_plan_runtime_contract", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


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

    def test_runtime_env_contract_is_read_from_real_environment(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(config_runtime, "CFG_PATH", Path(tmpdir) / "config.json"), patch.dict(
                os.environ,
                {
                    "XR_AUDIO_TRANSCRIPTION_PROVIDER": "tencent",
                    "XR_TENCENT_ASR_ENGINE_TYPE": "16k_zh",
                    "XR_REVIEW_PLAN_PROVIDER": "openai",
                    "XR_REVIEW_PLAN_MODEL": "gpt-5.5",
                    "XR_REVIEW_PLAN_WRITER_PROVIDER": "deepseek",
                    "XR_REVIEW_PLAN_WRITER_MODEL": "deepseek-v4-pro",
                    "XR_CLASS_COMMENTARY_PROVIDER": "openai",
                    "XR_CLASS_COMMENTARY_MODEL": "gpt-5.5",
                    "XR_PROVIDER": "deepseek",
                },
                clear=True,
            ):
                cfg = config_runtime.get_runtime_config()

                self.assertEqual(cfg["audio_transcription_provider"], "tencent")
                self.assertEqual(cfg["tencent_asr_engine_type"], "16k_zh")
                self.assertEqual(cfg["review_plan_provider"], "openai")
                self.assertEqual(cfg["review_plan_model"], "gpt-5.5")
                self.assertEqual(cfg["review_plan_writer_provider"], "deepseek")
                self.assertEqual(cfg["review_plan_writer_model"], "deepseek-v4-pro")
                self.assertEqual(cfg["class_commentary_provider"], "openai")
                self.assertEqual(cfg["class_commentary_model"], "gpt-5.5")

                self.assertEqual(resolve_review_plan_provider(cfg), "openai")
                self.assertEqual(resolve_review_plan_model(cfg), "gpt-5.5")
                self.assertEqual(resolve_review_plan_writer_provider(cfg), "deepseek")
                self.assertEqual(resolve_review_plan_writer_model(cfg), "deepseek-v4-pro")
                self.assertEqual(app_module._review_plan_ai_provider_name(), "openai")
                self.assertEqual(app_module._review_plan_chat_model_name(), "gpt-5.5")
                self.assertEqual(app_module._review_plan_writer_ai_provider_name(), "deepseek")
                self.assertEqual(app_module._review_plan_writer_chat_model_name(), "deepseek-v4-pro")
                self.assertEqual(app_module._class_commentary_ai_provider_name(fallback=app_module._default_ai_provider_name()), "openai")
                self.assertEqual(app_module._class_commentary_chat_model_name("openai", fallback_model=app_module._default_chat_model_name()), "gpt-5.5")
                self.assertEqual(_audio_transcription_provider_name(), "tencent")
                self.assertEqual(_audio_transcription_model_name(), "flash-16k_zh")

    def test_deepseek_writer_default_remains_v4_pro_when_env_is_omitted(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(config_runtime, "CFG_PATH", Path(tmpdir) / "config.json"), patch.dict(
                os.environ,
                {
                    "XR_REVIEW_PLAN_PROVIDER": "openai",
                    "XR_REVIEW_PLAN_MODEL": "gpt-5.5",
                    "XR_PROVIDER": "deepseek",
                },
                clear=True,
            ):
                cfg = config_runtime.get_runtime_config()

                self.assertEqual(resolve_review_plan_writer_provider(cfg), "deepseek")
                self.assertEqual(resolve_review_plan_writer_model(cfg), "deepseek-v4-pro")

    def test_review_plan_audio_metadata_no_longer_uses_local_defaults_when_tencent_is_active(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            with patch.object(lesson_manager, "DB_PATH", base / "xingrun.db"), patch.object(
                config_runtime,
                "CFG_PATH",
                base / "config.json",
            ), patch.dict(
                os.environ,
                {
                    "XR_AUDIO_TRANSCRIPTION_PROVIDER": "tencent",
                    "XR_TENCENT_ASR_ENGINE_TYPE": "16k_zh",
                    "XR_REVIEW_PLAN_PROVIDER": "openai",
                    "XR_REVIEW_PLAN_MODEL": "gpt-5.5",
                    "XR_REVIEW_PLAN_WRITER_PROVIDER": "deepseek",
                    "XR_REVIEW_PLAN_WRITER_MODEL": "deepseek-v4-pro",
                    "XR_CLASS_COMMENTARY_PROVIDER": "openai",
                    "XR_CLASS_COMMENTARY_MODEL": "gpt-5.5",
                    "XR_PROVIDER": "deepseek",
                },
                clear=True,
            ):
                lesson_manager.init_db()

                audio_path = base / "lesson.m4a"
                audio_path.write_bytes(b"audio")
                lesson_id = lesson_manager.create_pending_lesson(
                    date_str="2026-04-09",
                    subject="数学",
                    grade="初二",
                    topic="一次函数",
                    summary="课堂总结文本",
                    weak_points="斜率判断",
                    class_id=0,
                    record_status="transcribing",
                    created_by_user_id=1,
                    review_audio_path=str(audio_path),
                    review_audio_request_key="audio-key",
                    review_request_key="request-key",
                    review_request_id="request-id",
                    review_chat_provider="openai",
                    review_chat_model="gpt-5.5",
                )

                calls = []

                def fake_run_with_charge(**kwargs):
                    calls.append(kwargs)
                    if len(calls) == 1:
                        return "转写文本"
                    return kwargs["producer"]()

                with patch("app._run_ai_feature_with_charge", side_effect=fake_run_with_charge), patch(
                    "review_plan_workflow.nodes.plan_generator.generate_review_plan_json",
                    return_value=(
                        valid_single_lesson_plan(subject="数学", topic="一次函数"),
                        {"provider": "openai", "model": "gpt-5.5", "input_tokens": 1, "output_tokens": 1},
                    ),
                ), patch(
                    "review_plan_templates.single_lesson_pdf.generate_single_lesson_pdf",
                    return_value="/tmp/review-plan.pdf",
                ):
                    app_module._run_review_plan_generation_job(
                        lesson_id=lesson_id,
                        user={"id": 1, "organization_id": 1},
                        chat_provider="openai",
                        chat_model="gpt-5.5",
                        request_key="test-request-key",
                    )

                self.assertGreaterEqual(len(calls), 1)
                audio_charge = calls[0]
                self.assertEqual(audio_charge["provider"], "tencent")
                self.assertEqual(audio_charge["model"], "flash-16k_zh")
                self.assertNotEqual((audio_charge["provider"], audio_charge["model"]), ("local", "faster-whisper-base"))
                saved = lesson_manager.get_lesson(lesson_id)
                self.assertEqual(saved["record_status"], "ready")

    def test_verify_script_redacts_secret_presence(self):
        script = load_runtime_contract_script()
        env = {
            **script.EXPECTED_VALUES,
            "OPENAI_API_KEY": "sk-openai-secret",
            "DEEPSEEK_API_KEY": "sk-deepseek-secret",
            "LANGFUSE_PUBLIC_KEY": "pk-lf-secret",
        }

        self.assertEqual(script.validate_contract(env), [])
        report = "\n".join(script.build_contract_report(env))
        self.assertIn("OPENAI_API_KEY_present=True", report)
        self.assertIn("DEEPSEEK_API_KEY_present=True", report)
        self.assertIn("LANGFUSE_PUBLIC_KEY_present=True", report)
        self.assertNotIn("sk-openai-secret", report)
        self.assertNotIn("sk-deepseek-secret", report)
        self.assertNotIn("pk-lf-secret", report)


if __name__ == "__main__":
    unittest.main()
