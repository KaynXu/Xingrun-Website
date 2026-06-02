from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import ai_processor

ROOT = Path(__file__).resolve().parents[1]


class _FakeChatCompletions:
    def __init__(self, content: dict | str):
        self.content = content
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        raw_content = (
            self.content
            if isinstance(self.content, str)
            else json.dumps(self.content, ensure_ascii=False)
        )
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
                                    "content": raw_content,
                                },
                            )()
                        },
                    )()
                ],
            },
        )()


class _FakeClient:
    def __init__(self, content: dict | str):
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
            cwd=ROOT,
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_plan_system_prompt_limits_formula_only_fill_ratio(self):
        self.assertIn("纯公式型填空题", ai_processor.PLAN_SYSTEM_PROMPT)
        self.assertIn("不得超过 30%", ai_processor.PLAN_SYSTEM_PROMPT)
        self.assertIn("至少 70% 的填空题", ai_processor.PLAN_SYSTEM_PROMPT)

    def test_plan_system_prompt_requires_163320_style_method_map(self):
        for phrase in ["方法主线", "题型入口", "操作步骤", "易错提醒", "典型例题", "老师原话"]:
            self.assertIn(phrase, ai_processor.PLAN_SYSTEM_PROMPT)
        self.assertIn("看到什么条件", ai_processor.PLAN_SYSTEM_PROMPT)
        self.assertIn("先做什么", ai_processor.PLAN_SYSTEM_PROMPT)
        self.assertIn("同一节课", ai_processor.PLAN_SYSTEM_PROMPT)
        self.assertIn("多段材料", ai_processor.PLAN_SYSTEM_PROMPT)

    def test_wrong_question_recognition_prompt_requests_mixed_latex_output(self):
        self.assertIn("正文 + LaTeX 公式", ai_processor.WRONG_QUESTION_RECOGNITION_PROMPT)
        self.assertIn("$...$", ai_processor.WRONG_QUESTION_RECOGNITION_PROMPT)
        self.assertIn("$$...$$", ai_processor.WRONG_QUESTION_RECOGNITION_PROMPT)
        self.assertIn("不要把整道题都改写成纯 LaTeX", ai_processor.WRONG_QUESTION_RECOGNITION_PROMPT)
        self.assertIn("反斜杠必须写成双反斜杠", ai_processor.WRONG_QUESTION_RECOGNITION_PROMPT)
        self.assertIn("数轴", ai_processor.WRONG_QUESTION_RECOGNITION_PROMPT)
        self.assertIn("不要只写“如图所示”", ai_processor.WRONG_QUESTION_RECOGNITION_PROMPT)
        self.assertIn("A 在 B 左侧", ai_processor.WRONG_QUESTION_RECOGNITION_PROMPT)
        self.assertIn("重新识别", ai_processor.WRONG_QUESTION_RECOGNITION_PROMPT)
        self.assertIn("逐条修正", ai_processor.WRONG_QUESTION_RECOGNITION_PROMPT)
        self.assertIn("image_rotation_degrees", ai_processor.WRONG_QUESTION_RECOGNITION_PROMPT)
        self.assertIn("0、90、180、270", ai_processor.WRONG_QUESTION_RECOGNITION_PROMPT)
        self.assertIn("顺时针", ai_processor.WRONG_QUESTION_RECOGNITION_PROMPT)

    def test_wrong_question_quality_review_prompt_separates_blocking_errors_from_suggestions(self):
        self.assertIn("致命问题", ai_processor.WRONG_QUESTION_RECOGNITION_REVIEW_PROMPT)
        self.assertIn("可优化建议", ai_processor.WRONG_QUESTION_RECOGNITION_REVIEW_PROMPT)
        self.assertIn("不要因为没有重绘原图而直接判不通过", ai_processor.WRONG_QUESTION_RECOGNITION_REVIEW_PROMPT)

    def test_wrong_question_practice_prompt_focuses_on_reflection_not_solution(self):
        self.assertIn("不要单独生成“下次提醒”", ai_processor.WRONG_QUESTION_PRACTICE_SHEET_PROMPT)
        self.assertIn("第一行是这个书写区的小标题", ai_processor.WRONG_QUESTION_PRACTICE_SHEET_PROMPT)
        self.assertIn("标准答案和关键步骤只允许放在 answer、key_steps、pitfall_reminder 字段里", ai_processor.WRONG_QUESTION_PRACTICE_SHEET_PROMPT)
        self.assertIn("answer: string", ai_processor.WRONG_QUESTION_PRACTICE_SHEET_PROMPT)
        self.assertIn("key_steps: array[string]", ai_processor.WRONG_QUESTION_PRACTICE_SHEET_PROMPT)
        self.assertIn("pitfall_reminder: string", ai_processor.WRONG_QUESTION_PRACTICE_SHEET_PROMPT)
        self.assertIn("题目内容必须用于提取本题的对象、条件、问法或符号", ai_processor.WRONG_QUESTION_PRACTICE_SHEET_PROMPT)
        self.assertIn("topic_category 当成知识点靶心", ai_processor.WRONG_QUESTION_PRACTICE_SHEET_PROMPT)
        self.assertIn("不要只写“错因”“计算错因”“方法问题”", ai_processor.WRONG_QUESTION_PRACTICE_SHEET_PROMPT)
        self.assertIn("【相遇关系辨析】", ai_processor.WRONG_QUESTION_PRACTICE_SHEET_PROMPT)
        self.assertIn("【分类讨论补全】", ai_processor.WRONG_QUESTION_PRACTICE_SHEET_PROMPT)
        self.assertIn("优先把孩子语音/文字里提到的具体遗漏、误判、步骤顺序写进填空句", ai_processor.WRONG_QUESTION_PRACTICE_SHEET_PROMPT)
        self.assertIn("像复习计划里的填空题一样", ai_processor.WRONG_QUESTION_PRACTICE_SHEET_PROMPT)
        self.assertIn("定义域 [m-4,3m]", ai_processor.WRONG_QUESTION_PRACTICE_SHEET_PROMPT)
        self.assertIn("两个书写区都要以挖空题为主", ai_processor.WRONG_QUESTION_PRACTICE_SHEET_PROMPT)
        self.assertIn("每个书写区正文控制在 1 到 2 句", ai_processor.WRONG_QUESTION_PRACTICE_SHEET_PROMPT)
        self.assertIn("2 到 3 个 ______ 空格", ai_processor.WRONG_QUESTION_PRACTICE_SHEET_PROMPT)
        self.assertIn("不要在挖空题后面再追加纯写字线", ai_processor.WRONG_QUESTION_PRACTICE_SHEET_PROMPT)
        self.assertIn("不要把孩子没说过或题目里没明确给出的细节硬写成确定事实", ai_processor.WRONG_QUESTION_PRACTICE_SHEET_PROMPT)
        self.assertIn("只需要围绕错因做轻引导", ai_processor.WRONG_QUESTION_PRACTICE_SHEET_PROMPT)
        self.assertNotIn("ai_hint", ai_processor.WRONG_QUESTION_PRACTICE_SHEET_PROMPT)

    def test_practice_pack_variant_prompt_requires_same_reason_questions(self):
        prompt = ai_processor.WRONG_QUESTION_PRACTICE_PACK_VARIANT_PROMPT
        self.assertIn("同错因变式题", prompt)
        self.assertIn("不跨错因", prompt)
        self.assertIn("标准答案", prompt)
        self.assertIn("关键步骤", prompt)
        self.assertIn("易错提醒", prompt)

    def test_practice_pack_variant_review_prompt_checks_answer_and_target(self):
        prompt = ai_processor.WRONG_QUESTION_PRACTICE_PACK_VARIANT_REVIEW_PROMPT
        self.assertIn("题目可解", prompt)
        self.assertIn("答案一致", prompt)
        self.assertIn("目标错因", prompt)
        self.assertIn("结论：通过", prompt)

    def test_wrong_question_practice_reportlab_copy_avoids_fixed_section_labels(self):
        source = (Path(ai_processor.__file__).resolve().parent / "pdf_engine.py").read_text(encoding="utf-8")
        self.assertNotIn('Paragraph("AI 提示"', source)
        self.assertNotIn('Paragraph("下次提醒"', source)

    def test_wrong_question_practice_material_payload_includes_topic_category(self):
        fake_client = _FakeClient(
            {
                "title": "去分母错题练习",
                "items": [
                    {
                        "wrong_question_record_id": "record-1",
                        "reason_blank_prompt": "【去分母检查】\n这题先给等式两边每一项同乘 ______，容易漏乘的是 ______。",
                        "improvement_summary_prompt": "【下次先标分母】\n下次做去分母题，我先圈出 ______，再检查 ______ 是否同乘。",
                        "answer": "x=7",
                        "key_steps": ["两边同乘 2", "解得 x=7"],
                        "pitfall_reminder": "不要漏乘常数项。",
                    }
                ],
            }
        )
        with patch("ai_processor._get_client", return_value=fake_client):
            ai_processor.generate_wrong_question_practice_sheet_material(
                student_name="Alice",
                class_name="六年级 9 班",
                teacher_name="Kayn",
                items=[
                    {
                        "wrong_question_record_id": "record-1",
                        "question_order": 1,
                        "question_text_snapshot": "解方程 $\\frac{x-1}{2}=3$。",
                        "child_reason_text_snapshot": "我去分母时漏乘右边常数",
                        "primary_error_type_snapshot": "知识点问题",
                        "cause_note_snapshot": "去分母时常数项漏乘",
                        "topic_category_snapshot": "一元一次方程去分母",
                    }
                ],
            )

        user_payload = json.loads(fake_client.chat.completions.last_kwargs["messages"][1]["content"])
        self.assertEqual(user_payload["items"][0]["topic_category"], "一元一次方程去分母")

    def test_wrong_question_practice_prompt_bans_template_copy_and_bullets(self):
        prompt = ai_processor.WRONG_QUESTION_PRACTICE_SHEET_PROMPT

        self.assertIn("不要出现“本题重点修正”", prompt)
        self.assertIn("不要出现“订正时先补全”", prompt)
        self.assertIn("不要使用项目符号", prompt)
        self.assertIn("像老师手写给学生的一两句短提醒", prompt)

    def test_wrong_question_recognition_uses_vision_model_when_text_provider_is_deepseek(self):
        fake_client = _FakeClient(
            {
                "is_geometry": False,
                "question_text": "计算 $1+1$。",
                "confidence": "high",
            }
        )
        with patch(
            "ai_processor._load_config",
            return_value={
                "provider": "deepseek",
                "deepseek_model": "deepseek-chat",
                "vision_provider": "qwen",
                "vision_model": "qwen-vl-max-latest",
                "qwen_api_key": "test-key",
                "qwen_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            },
        ), patch("ai_processor._get_vision_client", return_value=fake_client):
            ai_processor._request_wrong_question_recognition_attempt(
                "https://files.example.com/question.png"
            )

        self.assertEqual(fake_client.chat.completions.last_kwargs["model"], "qwen-vl-max-latest")

    def test_wrong_question_recognition_retry_instruction_requires_diagram_details(self):
        fake_client = _FakeClient(
            {
                "is_geometry": False,
                "question_text": "点 A 在点 B 左侧。",
                "confidence": "high",
            }
        )
        ai_processor._request_wrong_question_recognition_attempt(
            "https://files.example.com/question.png",
            revision_feedback="上一版只写了如图所示。",
            client=fake_client,
        )

        user_message = fake_client.chat.completions.last_kwargs["messages"][1]["content"][0]["text"]
        self.assertIn("数轴", user_message)
        self.assertIn("不要只写“如图所示”", user_message)
        self.assertIn("图中关键信息", user_message)

    def test_wrong_question_latex_checker_uses_valid_stdout_when_node_aborts_after_output(self):
        completed = subprocess.CompletedProcess(
            args=["node"],
            returncode=-6,
            stdout=json.dumps({"errors": []}, ensure_ascii=False),
            stderr="",
        )
        with patch("ai_processor.subprocess.run", return_value=completed):
            issues = ai_processor._collect_wrong_question_latex_render_issues("计算 $\\frac{1}{2}$。")

        self.assertEqual(issues, [])

    def test_parse_and_generate_plan_recovers_bare_latex_backslashes(self):
        fake_client = _FakeClient(
            r"""{"lesson_info":{"topic":"含参方程"},"days":[{"items":[{"text":"观察 $\left(x+1\right)^2$ 的开口方向"}]}],"weekly_review_prompts":[]}"""
        )
        with patch("ai_processor._get_client", return_value=fake_client):
            plan = ai_processor.parse_and_generate_plan("课堂总结")

        self.assertEqual(plan["days"][0]["items"][0]["text"], r"观察 $\left(x+1\right)^2$ 的开口方向")

    def test_parse_and_generate_plan_preserves_bare_latex_json_control_escapes(self):
        fake_client = _FakeClient(
            r"""{"lesson_info":{"topic":"分式"},"days":[{"items":[{"text":"计算 $\frac{1}{2}$ 的值"}]}],"weekly_review_prompts":[]}"""
        )
        with patch("ai_processor._get_client", return_value=fake_client):
            plan = ai_processor.parse_and_generate_plan("课堂总结")

        self.assertEqual(plan["days"][0]["items"][0]["text"], r"计算 $\frac{1}{2}$ 的值")

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
