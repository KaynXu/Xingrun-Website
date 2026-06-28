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

    def test_runtime_config_reads_colleague_skill_dir_from_env(self):
        with patch.dict("os.environ", {"XR_COLLEAGUE_SKILL_DIR": "/srv/skills"}, clear=False):
            self.assertEqual(config_runtime.get_runtime_config()["colleague_skill_dir"], "/srv/skills")
