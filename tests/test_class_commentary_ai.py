import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import ai_processor
import config_runtime

import class_commentary


class ClassCommentaryAiTest(unittest.TestCase):
    def test_skill_scanner_lists_legacy_skill_files(self):
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

    def test_skill_scanner_lists_directory_skill_packages(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = root / "teacher-b"
            package.mkdir()
            (package / "SKILL.md").write_text("# Teacher B\nUse warm emoji.", encoding="utf-8")
            (package / "work.md").write_text("Work notes", encoding="utf-8")
            (package / "persona.md").write_text("Persona notes", encoding="utf-8")
            (package / "meta.json").write_text('{"name": "橘子老师"}', encoding="utf-8")
            (root / "draft").mkdir()

            skills = class_commentary.list_colleague_skills(str(root))
            loaded = class_commentary.load_colleague_skill(str(root), "teacher-b")

        self.assertEqual([item["id"] for item in skills], ["teacher-b"])
        self.assertEqual(skills[0]["filename"], "teacher-b/SKILL.md")
        self.assertEqual(skills[0]["name"], "橘子老师")
        self.assertEqual(loaded["name"], "橘子老师")
        self.assertEqual(loaded["filename"], "teacher-b/SKILL.md")
        self.assertIn("Use warm emoji.", loaded["content"])
        self.assertIn("Work notes", loaded["content"])
        self.assertIn("Persona notes", loaded["content"])

    def test_skill_scanner_accepts_colleague_skill_repo_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = root / "colleagues" / "teacher-c"
            package.mkdir(parents=True)
            (package / "SKILL.md").write_text("# Teacher C", encoding="utf-8")
            (package / "persona.md").write_text("Use parent-friendly emojis.", encoding="utf-8")

            skills = class_commentary.list_colleague_skills(str(root))
            loaded = class_commentary.load_colleague_skill(str(root), "teacher-c")

        self.assertEqual([item["id"] for item in skills], ["teacher-c"])
        self.assertEqual(skills[0]["filename"], "teacher-c/SKILL.md")
        self.assertIn("Use parent-friendly emojis.", loaded["content"])

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
        output_rules = "\n".join(payload["output_rules"])
        self.assertIn("Only include students", output_rules)
        self.assertIn("feedback structure", output_rules)
        self.assertIn("2-4 short paragraphs", output_rules)
        self.assertIn("emoji habits", output_rules)
        self.assertIn("Infer the selected skill's emoji tokens", output_rules)
        self.assertIn("density, placement, and meaning", output_rules)
        self.assertIn("Do not force emojis", output_rules)
        self.assertIn("Do not hard-code a different colleague's emoji set", output_rules)
        self.assertNotIn("[呲牙]", output_rules)
        self.assertNotIn("[破涕为笑]", output_rules)
        self.assertNotIn("one sendable paragraph", output_rules)
        self.assertIn("小王今天计算有进步", payload["transcript"])
        self.assertIn("warm concise style", payload["skill"]["content"])

    def test_build_class_commentary_chat_request_returns_complete_prompt_snapshot(self):
        teacher_style_memories = [
            {"memory_id": 11, "content": "Start with one concrete strength."},
        ]
        student_history_memories = [
            {
                "memory_id": 22,
                "student_id": 1,
                "content": "Previously needed slower arithmetic checks.",
            },
        ]
        request_payload = class_commentary.build_class_commentary_chat_request(
            class_record={"id": 7, "name": "Math Grade 7 Class 4"},
            students=[{"id": 1, "name": "Student Wang"}, {"id": 2, "name": "Student Li"}],
            transcript_text="Student Wang improved at arithmetic today.",
            skill={"id": "teacher-a", "name": "Teacher A", "content": "warm concise style"},
            teacher_style_memories=teacher_style_memories,
            student_history_memories=student_history_memories,
        )
        generation_payload = class_commentary.build_class_commentary_generation_payload(
            class_record={"id": 7, "name": "Math Grade 7 Class 4"},
            students=[{"id": 1, "name": "Student Wang"}, {"id": 2, "name": "Student Li"}],
            transcript_text="Student Wang improved at arithmetic today.",
            skill={"id": "teacher-a", "name": "Teacher A", "content": "warm concise style"},
        )
        current_task_facts = {
            "class": generation_payload["class"],
            "students": generation_payload["students"],
            "transcript": generation_payload["transcript"],
        }
        expected_user_prompt = "\n\n".join(
            [
                "[CURRENT_TASK_FACTS]\n" + class_commentary.payload_to_json(current_task_facts),
                "[ACTIVE_SKILL]\n" + class_commentary.payload_to_json(generation_payload["skill"]),
                "[TEACHER_STYLE_MEMORIES]\n" + class_commentary.payload_to_json(teacher_style_memories),
                "[STUDENT_HISTORY_MEMORIES]\n"
                + class_commentary.payload_to_json(student_history_memories),
                "[OUTPUT_RULES]\n"
                + "\n".join(f"- {rule}" for rule in generation_payload["output_rules"]),
            ]
        )

        self.assertEqual(
            set(request_payload),
            {"prompt_version", "messages", "temperature"},
        )
        self.assertEqual(
            request_payload["prompt_version"],
            class_commentary.CLASS_COMMENTARY_PROMPT_VERSION,
        )
        self.assertEqual(request_payload["temperature"], 0.55)
        self.assertEqual(
            [message["role"] for message in request_payload["messages"]],
            ["system", "user"],
        )
        self.assertIn(
            "CURRENT_TASK_FACTS is the only source",
            request_payload["messages"][0]["content"],
        )
        self.assertEqual(request_payload["messages"][1]["content"], expected_user_prompt)

    def test_build_class_commentary_chat_request_keeps_empty_memory_sections(self):
        request_payload = class_commentary.build_class_commentary_chat_request(
            class_record={"id": 7, "name": "Math Grade 7 Class 4"},
            students=[{"id": 1, "name": "Student Wang"}],
            transcript_text="Student Wang improved at arithmetic today.",
            skill={"id": "teacher-a", "name": "Teacher A", "content": "warm concise style"},
        )

        user_prompt = request_payload["messages"][1]["content"]
        self.assertIn("[TEACHER_STYLE_MEMORIES]\n[]", user_prompt)
        self.assertIn("[STUDENT_HISTORY_MEMORIES]\n[]", user_prompt)
        for section in [
            "CURRENT_TASK_FACTS",
            "ACTIVE_SKILL",
            "TEACHER_STYLE_MEMORIES",
            "STUDENT_HISTORY_MEMORIES",
            "OUTPUT_RULES",
        ]:
            self.assertEqual(user_prompt.count(f"[{section}]"), 1)

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
        self.assertIn("primary working instructions", messages[0]["content"])
        self.assertIn("paragraph rhythm", messages[0]["content"])
        self.assertIn("emoji habits", messages[0]["content"])
        self.assertIn("Infer the selected skill's emoji system", messages[0]["content"])
        self.assertIn("do not force emojis", messages[0]["content"])
        self.assertNotIn("with one block per mentioned student", messages[0]["content"])
        self.assertNotIn("only for voice, structure, and phrasing", messages[0]["content"])
        self.assertIn("小王", messages[1]["content"])
        self.assertIn("primary working contract", messages[1]["content"])
        self.assertIn("facts only from the transcript and roster", messages[1]["content"])
        self.assertIn("2-4 short paragraphs", messages[1]["content"])
        self.assertIn("Infer the selected skill's emoji tokens", messages[1]["content"])
        self.assertNotIn("[呲牙]", messages[1]["content"])
        self.assertNotIn("[破涕为笑]", messages[1]["content"])
        self.assertNotIn("only as expression style and feedback framing", messages[1]["content"])
        self.assertEqual(fake_client.chat.completions.kwargs["temperature"], 0.55)

    def test_generate_class_commentary_feedback_sends_prebuilt_chat_request_unchanged(self):
        class FakeMessage:
            content = "Student Wang:\nArithmetic checks improved."

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

        chat_request = {
            "prompt_version": "saved-prompt-v42",
            "messages": [
                {"role": "system", "content": "Saved system prompt."},
                {"role": "user", "content": "Saved user prompt with memory snapshot."},
            ],
            "temperature": 0.23,
        }
        fake_client = FakeClient()
        with patch.object(ai_processor, "_get_client", return_value=fake_client), patch.object(
            ai_processor,
            "build_class_commentary_chat_request",
            side_effect=AssertionError("prebuilt request must not be rebuilt"),
        ):
            text = ai_processor.generate_class_commentary_feedback(
                class_record={"id": 7, "name": "ignored class"},
                students=[{"id": 99, "name": "ignored student"}],
                transcript_text="ignored transcript",
                skill={"id": "ignored-skill", "name": "Ignored", "content": "ignored"},
                chat_request=chat_request,
            )

        call_payload = fake_client.chat.completions.kwargs
        self.assertEqual(text, "Student Wang:\nArithmetic checks improved.")
        self.assertIs(call_payload["messages"], chat_request["messages"])
        self.assertEqual(call_payload["temperature"], chat_request["temperature"])
        self.assertEqual(
            {
                "prompt_version": chat_request["prompt_version"],
                "messages": call_payload["messages"],
                "temperature": call_payload["temperature"],
            },
            chat_request,
        )

    def test_generate_class_commentary_feedback_uses_class_commentary_openai_override(self):
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
        with patch.object(ai_processor, "_get_client", return_value=fake_client) as get_client:
            text, usage = ai_processor.generate_class_commentary_feedback(
                class_record={"id": 7, "name": "数学·七年级·4班"},
                students=[{"id": 1, "name": "小王"}],
                transcript_text="小王今天计算有进步",
                skill={"id": "teacher-a", "name": "Teacher A", "content": "warm concise style"},
                provider="openai",
                model="gpt-5.5",
                openai_api_key="sk-class-test",
                openai_base_url="https://api.iiiiitoken.com",
                openai_headers='{"X-Trace":"aimami"}',
                include_usage=True,
            )

        self.assertEqual(text, "小王:\n今天计算有进步.")
        self.assertEqual(usage["provider"], "openai")
        self.assertEqual(usage["model"], "gpt-5.5")
        self.assertEqual(fake_client.chat.completions.kwargs["model"], "gpt-5.5")
        get_client.assert_called_once_with(
            "openai",
            openai_api_key="sk-class-test",
            openai_base_url="https://api.iiiiitoken.com",
            openai_headers={"X-Trace": "aimami"},
        )

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
