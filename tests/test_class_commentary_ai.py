import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import ai_processor
import config_runtime

import class_commentary


class ClassCommentaryAiTest(unittest.TestCase):
    def test_skill_scanner_lists_only_top_level_skill_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "teacher-a.skill").write_text("style a", encoding="utf-8")
            (root / "notes.txt").write_text("ignore", encoding="utf-8")
            (root / "nested").mkdir()
            (root / "nested" / "teacher-b.skill").write_text("ignore nested", encoding="utf-8")

            skills = class_commentary.list_colleague_skills(str(root))

        self.assertEqual([item["id"] for item in skills], ["teacher-a"])
        self.assertEqual(skills[0]["filename"], "teacher-a.skill")
        self.assertEqual(skills[0]["name"], "teacher-a")

    def test_load_skill_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                class_commentary.load_colleague_skill(tmp, "../secret")

    def test_payload_contains_roster_transcript_skill_and_output_rules(self):
        payload = class_commentary.build_class_commentary_generation_payload(
            class_record={"id": 7, "name": "数学·七年级·4班"},
            students=[{"id": 1, "name": "小王"}, {"id": 2, "name": "小李"}],
            transcript_text="小王今天计算有进步",
            skill={"id": "teacher-a", "name": "Teacher A", "content": "warm concise style"},
        )
        self.assertEqual(payload["class"]["name"], "数学·七年级·4班")
        self.assertEqual(payload["students"], [{"id": 1, "name": "小王"}, {"id": 2, "name": "小李"}])
        self.assertIn("Only include students", "\n".join(payload["output_rules"]))
        self.assertIn("小王今天计算有进步", payload["transcript"])
        self.assertIn("warm concise style", payload["skill"]["content"])

    def test_sanitize_class_commentary_roster_keeps_only_id_and_name(self):
        roster = class_commentary.sanitize_class_commentary_roster([
            {
                "id": 1,
                "name": " 小王 ",
                "parent_contact": "secret",
                "source": "wechat",
                "status": "active",
                "archived_at": "2026-06-01",
                "created_at": "2026-06-28",
                "extra_metadata": "private",
            },
            {"id": 2, "name": "   "},
            {"id": "3", "name": "小李", "created_at": "2026-06-28", "extra_metadata": "private"},
        ])

        self.assertEqual(roster, [{"id": 1, "name": "小王"}, {"id": 3, "name": "小李"}])
        serialized = str(roster)
        for forbidden in ["parent_contact", "source", "status", "archived_at", "created_at", "extra_metadata"]:
            self.assertNotIn(forbidden, serialized)

    def test_transcript_polish_payload_uses_sanitized_roster_and_math_terms(self):
        payload = class_commentary.build_class_commentary_transcript_polish_payload(
            class_record={"id": 7, "name": "数学·七年级·4班"},
            students=[{
                "id": 1,
                "name": "小王",
                "parent_contact": "secret",
                "source": "wechat",
                "status": "active",
                "archived_at": "2026-06-01",
                "created_at": "2026-06-28",
                "extra_metadata": "private",
            }],
            raw_transcript_text="小汪今天绝对纸学得不错",
            math_terms=["绝对值", "整式"],
        )

        self.assertEqual(payload["class"], {"id": 7, "name": "数学·七年级·4班"})
        self.assertEqual(payload["students"], [{"id": 1, "name": "小王"}])
        self.assertEqual(payload["math_terms"], ["绝对值", "整式"])
        self.assertIn("小汪今天", payload["raw_transcript"])
        serialized_payload = class_commentary.payload_to_json(payload)
        for forbidden in ["parent_contact", "source", "status", "archived_at", "created_at", "extra_metadata"]:
            self.assertNotIn(forbidden, serialized_payload)
        self.assertIn("Only correct student names to names in students.", payload["rules"])

    def test_generate_class_commentary_feedback_uses_plain_text_contract(self):
        class FakeMessage:
            content = "小王:\n今天计算有进步."

        class FakeChoice:
            message = FakeMessage()

        class FakeResponse:
            choices = [FakeChoice()]
            usage = None

        class FakeCompletions:
            def create(self, **kwargs):
                self.kwargs = kwargs
                return FakeResponse()

        class FakeChat:
            def __init__(self):
                self.completions = FakeCompletions()

        class FakeClient:
            def __init__(self):
                self.chat = FakeChat()

        fake_client = FakeClient()
        with patch.object(ai_processor, "_get_client", return_value=fake_client):
            text = ai_processor.generate_class_commentary_feedback(
                class_record={"id": 7, "name": "数学·七年级·4班"},
                students=[{"id": 1, "name": "小王"}],
                transcript_text="小王今天计算有进步",
                skill={"id": "teacher-a", "name": "Teacher A", "content": "warm concise style"},
            )

        self.assertEqual(text, "小王:\n今天计算有进步.")
        messages = fake_client.chat.completions.kwargs["messages"]
        self.assertIn("Do not invent facts", messages[0]["content"])
        self.assertIn("小王", messages[1]["content"])

    def test_polish_class_commentary_transcript_uses_roster_prompt_contract(self):
        class FakeMessage:
            content = "小王今天绝对值学得不错。"

        class FakeChoice:
            message = FakeMessage()

        class FakeResponse:
            choices = [FakeChoice()]
            usage = None

        class FakeCompletions:
            def create(self, **kwargs):
                self.kwargs = kwargs
                return FakeResponse()

        class FakeChat:
            def __init__(self):
                self.completions = FakeCompletions()

        class FakeClient:
            def __init__(self):
                self.chat = FakeChat()

        fake_client = FakeClient()
        with patch.object(ai_processor, "_get_client", return_value=fake_client):
            text, usage = ai_processor.polish_class_commentary_transcript(
                class_record={"id": 7, "name": "数学·七年级·4班"},
                students=[{
                    "id": 1,
                    "name": "小王",
                    "parent_contact": "secret",
                    "source": "wechat",
                    "status": "active",
                    "archived_at": "2026-06-01",
                    "created_at": "2026-06-28",
                    "extra_metadata": "private",
                }],
                raw_transcript_text="小汪今天绝对纸学得不错",
                math_terms=["绝对值"],
                include_usage=True,
            )

        self.assertEqual(text, "小王今天绝对值学得不错。")
        self.assertEqual(usage["provider"], ai_processor._provider_name())
        messages = fake_client.chat.completions.kwargs["messages"]
        self.assertIn("correcting ASR text", messages[0]["content"])
        self.assertIn("Do not rewrite", messages[0]["content"])
        user_payload = messages[1]["content"]
        self.assertIn("小王", user_payload)
        self.assertIn("绝对值", user_payload)
        for forbidden in ["parent_contact", "source", "status", "archived_at", "created_at", "extra_metadata"]:
            self.assertNotIn(forbidden, user_payload)
        self.assertEqual(fake_client.chat.completions.kwargs["temperature"], 0.1)

    def test_runtime_config_reads_colleague_skill_dir_from_env(self):
        with patch.dict("os.environ", {"XR_COLLEAGUE_SKILL_DIR": "/srv/skills"}, clear=False):
            self.assertEqual(config_runtime.get_runtime_config()["colleague_skill_dir"], "/srv/skills")
