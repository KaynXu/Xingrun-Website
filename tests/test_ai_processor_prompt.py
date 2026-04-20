import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import ai_processor


class _FakeChatCompletions:
    def __init__(self, content: dict):
        self.content = content
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return type(
            "Response",
            (),
            {
                "model": kwargs.get("model", ""),
                "choices": [
                    type(
                        "Choice",
                        (),
                        {
                            "message": type(
                                "Message",
                                (),
                                {
                                    "content": json.dumps(self.content, ensure_ascii=False),
                                },
                            )()
                        },
                    )()
                ],
            },
        )()


class _FakeClient:
    def __init__(self, content: dict):
        self.chat = type(
            "Chat",
            (),
            {"completions": _FakeChatCompletions(content)},
        )()


class _FakeUrlopenResponse:
    def __init__(self, payload: bytes):
        self.payload = payload

    def read(self):
        return self.payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeSegment:
    def __init__(self, text: str):
        self.text = text


class _FakeWhisperModel:
    init_calls: list[dict] = []
    transcribe_calls: list[dict] = []
    transcribe_results: list[tuple[object, object]] = []

    def __init__(self, model_size_or_path: str, device: str, compute_type: str):
        self.__class__.init_calls.append(
            {
                "model_size_or_path": model_size_or_path,
                "device": device,
                "compute_type": compute_type,
            }
        )

    def transcribe(self, audio_path: str, **kwargs):
        self.__class__.transcribe_calls.append(
            {
                "audio_path": audio_path,
                "kwargs": kwargs,
            }
        )
        if self.__class__.transcribe_results:
            return self.__class__.transcribe_results.pop(0)
        return [_FakeSegment(" 我把单位换算漏掉了 "), _FakeSegment(" ")], type("Info", (), {})()


class AiProcessorPromptTestCase(unittest.TestCase):
    def setUp(self):
        ai_processor._LOCAL_WHISPER_MODEL = None
        _FakeWhisperModel.init_calls = []
        _FakeWhisperModel.transcribe_calls = []
        _FakeWhisperModel.transcribe_results = []

    def tearDown(self):
        ai_processor._LOCAL_WHISPER_MODEL = None

    def test_ai_processor_imports_without_syntaxwarning(self):
        result = subprocess.run(
            [
                sys.executable,
                "-W",
                "error::SyntaxWarning",
                "-c",
                "import ai_processor",
            ],
            capture_output=True,
            text=True,
            cwd="/Users/ark.mini/Desktop/Xingrun-Website",
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_plan_system_prompt_limits_formula_only_fill_ratio(self):
        self.assertIn("纯公式型填空题", ai_processor.PLAN_SYSTEM_PROMPT)
        self.assertIn("不得超过 30%", ai_processor.PLAN_SYSTEM_PROMPT)
        self.assertIn("至少 70% 的填空题", ai_processor.PLAN_SYSTEM_PROMPT)

    def test_wrong_question_recognition_prompt_requests_mixed_latex_output(self):
        self.assertIn("正文 + LaTeX 公式", ai_processor.WRONG_QUESTION_RECOGNITION_PROMPT)
        self.assertIn("$...$", ai_processor.WRONG_QUESTION_RECOGNITION_PROMPT)
        self.assertIn("$$...$$", ai_processor.WRONG_QUESTION_RECOGNITION_PROMPT)
        self.assertIn("不要把整道题都改写成纯 LaTeX", ai_processor.WRONG_QUESTION_RECOGNITION_PROMPT)
        self.assertIn("反斜杠必须写成双反斜杠", ai_processor.WRONG_QUESTION_RECOGNITION_PROMPT)

    def test_wrong_question_practice_prompt_focuses_on_reflection_not_solution(self):
        self.assertIn("不要单独生成“下次提醒”", ai_processor.WRONG_QUESTION_PRACTICE_SHEET_PROMPT)
        self.assertIn("第一行是这个书写区的小标题", ai_processor.WRONG_QUESTION_PRACTICE_SHEET_PROMPT)
        self.assertIn("不要提示孩子该怎样把这道题一步一步做对", ai_processor.WRONG_QUESTION_PRACTICE_SHEET_PROMPT)
        self.assertIn("题目内容只用于确认错因语境", ai_processor.WRONG_QUESTION_PRACTICE_SHEET_PROMPT)
        self.assertIn("两个书写区都要以挖空题为主", ai_processor.WRONG_QUESTION_PRACTICE_SHEET_PROMPT)
        self.assertIn("每个书写区至少包含 3 个 ______ 空格", ai_processor.WRONG_QUESTION_PRACTICE_SHEET_PROMPT)
        self.assertIn("不要在挖空题后面再追加纯写字线", ai_processor.WRONG_QUESTION_PRACTICE_SHEET_PROMPT)
        self.assertIn("明确点出孩子缺的是哪个知识点", ai_processor.WRONG_QUESTION_PRACTICE_SHEET_PROMPT)
        self.assertNotIn("ai_hint", ai_processor.WRONG_QUESTION_PRACTICE_SHEET_PROMPT)

    def test_wrong_question_practice_reportlab_copy_avoids_fixed_section_labels(self):
        source = (Path(ai_processor.__file__).resolve().parent / "pdf_engine.py").read_text(encoding="utf-8")
        self.assertNotIn('Paragraph("AI 提示"', source)
        self.assertNotIn('Paragraph("下次提醒"', source)

    def test_parse_and_generate_plan_uses_configured_model_for_n1n(self):
        fake_client = _FakeClient(
            {
                "lesson_info": {},
                "days": [],
                "weekly_review_prompts": [],
            }
        )
        with patch(
            "ai_processor._load_config",
            return_value={
                "provider": "n1n",
                "n1n_model": "gpt-5.4",
                "n1n_api_key": "test-key",
                "n1n_base_url": "https://api.n1n.ai/v1",
            },
        ), patch("ai_processor._get_client", return_value=fake_client):
            ai_processor.parse_and_generate_plan("课堂总结")

        self.assertEqual(fake_client.chat.completions.last_kwargs["model"], "gpt-5.4")

    def test_generate_monthly_plan_uses_configured_model_for_n1n(self):
        fake_client = _FakeClient(
            {
                "lesson_info": {},
                "days": [],
                "weekly_review_prompts": [],
            }
        )
        with patch(
            "ai_processor._load_config",
            return_value={
                "provider": "n1n",
                "n1n_model": "gpt-5.4",
                "n1n_api_key": "test-key",
                "n1n_base_url": "https://api.n1n.ai/v1",
            },
        ), patch("ai_processor._get_client", return_value=fake_client):
            ai_processor.generate_monthly_plan(
                [{"date": "2026-04-09", "summary": "课堂总结", "topic": "一次函数"}],
                "2026-04",
            )

        self.assertEqual(fake_client.chat.completions.last_kwargs["model"], "gpt-5.4")

    def test_transcribe_child_reason_audio_uses_local_faster_whisper_auto_detect_first(self):
        fake_module = type("FakeFasterWhisperModule", (), {"WhisperModel": _FakeWhisperModel})
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(sys.modules, {"faster_whisper": fake_module}), patch(
                "urllib.request.urlopen",
                return_value=_FakeUrlopenResponse(b"fake-audio"),
            ), patch("ai_processor.Path.home", return_value=Path(temp_dir)):
                payload = ai_processor.transcribe_child_reason_audio("https://files.example.com/reason.m4a")

        self.assertEqual(payload, {"transcript_text": "我把单位换算漏掉了"})
        self.assertEqual(
            _FakeWhisperModel.init_calls,
            [
                {
                    "model_size_or_path": "base",
                    "device": "cpu",
                    "compute_type": "int8",
                }
            ],
        )
        self.assertEqual(len(_FakeWhisperModel.transcribe_calls), 1)
        self.assertNotIn("language", _FakeWhisperModel.transcribe_calls[0]["kwargs"])
        self.assertEqual(_FakeWhisperModel.transcribe_calls[0]["kwargs"]["task"], "transcribe")
        self.assertTrue(_FakeWhisperModel.transcribe_calls[0]["audio_path"].endswith(".m4a"))

    def test_transcribe_child_reason_audio_prefers_local_cached_snapshot_path(self):
        fake_module = type("FakeFasterWhisperModule", (), {"WhisperModel": _FakeWhisperModel})
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_root = Path(temp_dir) / ".cache" / "huggingface" / "hub"
            snapshot_dir = (
                cache_root
                / "models--Systran--faster-whisper-base"
                / "snapshots"
                / "revision-123"
            )
            snapshot_dir.mkdir(parents=True)
            refs_dir = snapshot_dir.parent.parent / "refs"
            refs_dir.mkdir(parents=True)
            (refs_dir / "main").write_text("revision-123", encoding="utf-8")

            with patch.dict(sys.modules, {"faster_whisper": fake_module}), patch(
                "urllib.request.urlopen",
                return_value=_FakeUrlopenResponse(b"fake-audio"),
            ), patch("ai_processor.Path.home", return_value=Path(temp_dir)):
                payload = ai_processor.transcribe_child_reason_audio("https://files.example.com/reason.m4a")

        self.assertEqual(payload, {"transcript_text": "我把单位换算漏掉了"})
        self.assertEqual(
            _FakeWhisperModel.init_calls,
            [
                {
                    "model_size_or_path": str(snapshot_dir),
                    "device": "cpu",
                    "compute_type": "int8",
                }
            ],
        )

    def test_transcribe_child_reason_audio_falls_back_to_chinese_when_auto_detect_is_empty(self):
        fake_module = type("FakeFasterWhisperModule", (), {"WhisperModel": _FakeWhisperModel})
        _FakeWhisperModel.transcribe_results = [
            ([_FakeSegment("   ")], type("Info", (), {})()),
            ([_FakeSegment("题目里有 x 加 y")], type("Info", (), {})()),
        ]

        with patch.dict(sys.modules, {"faster_whisper": fake_module}), patch(
            "urllib.request.urlopen",
            return_value=_FakeUrlopenResponse(b"fake-audio"),
        ):
            payload = ai_processor.transcribe_child_reason_audio("https://files.example.com/reason.m4a")

        self.assertEqual(payload, {"transcript_text": "题目里有 x 加 y"})
        self.assertEqual(len(_FakeWhisperModel.transcribe_calls), 2)
        self.assertNotIn("language", _FakeWhisperModel.transcribe_calls[0]["kwargs"])
        self.assertEqual(_FakeWhisperModel.transcribe_calls[1]["kwargs"]["language"], "zh")
        self.assertEqual(_FakeWhisperModel.transcribe_calls[1]["kwargs"]["task"], "transcribe")

    def test_transcribe_audio_returns_local_usage_payload(self):
        fake_module = type("FakeFasterWhisperModule", (), {"WhisperModel": _FakeWhisperModel})
        with tempfile.TemporaryDirectory() as temp_dir:
            audio_path = Path(temp_dir) / "lesson.m4a"
            audio_path.write_bytes(b"fake-audio")

            with patch.dict(sys.modules, {"faster_whisper": fake_module}):
                transcription, usage = ai_processor.transcribe_audio(str(audio_path), include_usage=True)

        self.assertEqual(transcription, "我把单位换算漏掉了")
        self.assertEqual(
            usage,
            {
                "provider": "local",
                "model": "faster-whisper-base",
                "input_tokens": 0,
                "output_tokens": 0,
            },
        )


if __name__ == "__main__":
    unittest.main()
