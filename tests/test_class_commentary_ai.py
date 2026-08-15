import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import ai_processor
import config_runtime

import class_commentary


class ClassCommentaryAiTest(unittest.TestCase):
    def test_class_commentary_client_can_disable_sdk_retries(self):
        with patch("openai.OpenAI") as openai_client:
            ai_processor._get_class_commentary_client(
                "openai",
                openai_api_key="test-key",
                openai_base_url="https://example.invalid",
                max_retries=0,
            )

        openai_client.assert_called_once_with(
            api_key="test-key",
            base_url="https://example.invalid",
            max_retries=0,
        )

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

    def test_skill_loader_includes_nested_knowledge_markdown_in_stable_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = root / "teacher-knowledge"
            messages = package / "knowledge" / "messages"
            docs = package / "knowledge" / "docs"
            messages.mkdir(parents=True)
            docs.mkdir(parents=True)
            (package / "SKILL.md").write_text(
                "Use the frozen colleague voice.", encoding="utf-8"
            )
            (messages / "z-sample.md").write_text(
                "Long feedback example with [玫瑰] at the close.", encoding="utf-8"
            )
            (messages / "a-sample.md").write_text(
                "Warm opening example with [呲牙].", encoding="utf-8"
            )
            (docs / "workflow.md").write_text(
                "Write the diagnosis and concrete next action.", encoding="utf-8"
            )
            (package / "knowledge" / "ignore.txt").write_text(
                "not prompt context", encoding="utf-8"
            )

            loaded = class_commentary.load_colleague_skill(
                str(root), "teacher-knowledge"
            )

        content = loaded["content"]
        self.assertIn("## knowledge/docs/workflow.md", content)
        self.assertIn("## knowledge/messages/a-sample.md", content)
        self.assertIn("## knowledge/messages/z-sample.md", content)
        self.assertLess(
            content.index("## knowledge/docs/workflow.md"),
            content.index("## knowledge/messages/a-sample.md"),
        )
        self.assertLess(
            content.index("## knowledge/messages/a-sample.md"),
            content.index("## knowledge/messages/z-sample.md"),
        )
        self.assertIn("[呲牙]", content)
        self.assertIn("[玫瑰]", content)
        self.assertNotIn("not prompt context", content)

    def test_skill_package_updated_at_tracks_nested_knowledge_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = root / "teacher-updated"
            messages = package / "knowledge" / "messages"
            messages.mkdir(parents=True)
            (package / "SKILL.md").write_text("Skill", encoding="utf-8")
            sample = messages / "sample.md"
            sample.write_text("Example", encoding="utf-8")
            sample.touch()
            expected_updated_at = int(sample.stat().st_mtime)

            skills = class_commentary.list_colleague_skills(str(root))

        self.assertEqual(int(skills[0]["updated_at"]), expected_updated_at)

    def test_skill_loader_ignores_symlinked_knowledge_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = root / "teacher-safe"
            knowledge = package / "knowledge"
            knowledge.mkdir(parents=True)
            (package / "SKILL.md").write_text("Safe skill", encoding="utf-8")
            outside = root / "outside.md"
            outside.write_text("secret outside content", encoding="utf-8")
            (knowledge / "outside.md").symlink_to(outside)

            loaded = class_commentary.load_colleague_skill(
                str(root), "teacher-safe"
            )

        self.assertIn("Safe skill", loaded["content"])
        self.assertNotIn("secret outside content", loaded["content"])

    def test_skill_loader_ignores_macos_appledouble_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = root / "teacher-safe"
            knowledge = package / "knowledge"
            knowledge.mkdir(parents=True)
            (package / "SKILL.md").write_text("Safe skill", encoding="utf-8")
            (knowledge / "sample.md").write_text("Valid sample", encoding="utf-8")
            (knowledge / "._sample.md").write_bytes(b"\x00\x05\x16\x07\xa3")

            loaded = class_commentary.load_colleague_skill(
                str(root), "teacher-safe"
            )

        self.assertIn("Valid sample", loaded["content"])

    def test_skill_loader_ignores_oversized_macos_appledouble_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = root / "teacher-safe"
            knowledge = package / "knowledge"
            knowledge.mkdir(parents=True)
            (package / "SKILL.md").write_text("Safe", encoding="utf-8")
            (knowledge / "sample.md").write_text("Valid", encoding="utf-8")
            (knowledge / "._sample.md").write_bytes(b"x" * 9)

            with patch.object(
                class_commentary,
                "CLASS_COMMENTARY_SKILL_PACKAGE_MAX_FILE_BYTES",
                8,
            ), patch.object(
                class_commentary,
                "CLASS_COMMENTARY_SKILL_PACKAGE_MAX_MARKDOWN_FILES",
                2,
            ):
                loaded = class_commentary.load_colleague_skill(
                    str(root), "teacher-safe"
                )

        self.assertIn("Valid", loaded["content"])

    def test_skill_loader_rejects_skill_file_swapped_to_symlink_after_scan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = root / "teacher-race"
            package.mkdir()
            skill_path = package / "SKILL.md"
            skill_path.write_text("Safe skill", encoding="utf-8")
            outside = root / "outside.md"
            outside.write_text("OUTSIDE_SECRET", encoding="utf-8")
            original_scan = (
                class_commentary._class_commentary_skill_package_relative_markdown_paths
            )

            def swap_after_scan(package_fd):
                relative_paths = original_scan(package_fd)
                skill_path.unlink()
                skill_path.symlink_to(outside)
                return relative_paths

            with patch.object(
                class_commentary,
                "_class_commentary_skill_package_relative_markdown_paths",
                side_effect=swap_after_scan,
            ):
                with self.assertRaisesRegex(ValueError, "unsafe or unavailable"):
                    class_commentary.read_class_commentary_skill_package_content(
                        package
                    )

    def test_skill_loader_rejects_nested_directory_swapped_to_symlink_after_scan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = root / "teacher-race"
            messages = package / "knowledge" / "messages"
            messages.mkdir(parents=True)
            (package / "SKILL.md").write_text("Safe skill", encoding="utf-8")
            (messages / "sample.md").write_text("Safe sample", encoding="utf-8")
            outside = root / "outside"
            outside.mkdir()
            (outside / "sample.md").write_text("OUTSIDE_SECRET", encoding="utf-8")
            original_messages = package / "knowledge" / "messages-original"
            original_scan = (
                class_commentary._class_commentary_skill_package_relative_markdown_paths
            )

            def swap_after_scan(package_fd):
                relative_paths = original_scan(package_fd)
                messages.rename(original_messages)
                messages.symlink_to(outside, target_is_directory=True)
                return relative_paths

            with patch.object(
                class_commentary,
                "_class_commentary_skill_package_relative_markdown_paths",
                side_effect=swap_after_scan,
            ):
                with self.assertRaisesRegex(ValueError, "unsafe or unavailable"):
                    class_commentary.read_class_commentary_skill_package_content(
                        package
                    )

    def test_skill_scanner_and_loader_ignore_symlinked_packages(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside_tmp:
            root = Path(tmp)
            outside = Path(outside_tmp) / "outside-package"
            outside.mkdir()
            (outside / "SKILL.md").write_text("outside content", encoding="utf-8")
            (root / "linked-package").symlink_to(outside, target_is_directory=True)

            skills = class_commentary.list_colleague_skills(str(root))

            with self.assertRaises(FileNotFoundError):
                class_commentary.load_colleague_skill(str(root), "linked-package")

        self.assertEqual(skills, [])

    def test_skill_scanner_and_loader_ignore_symlinked_legacy_skill(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            outside = root / "outside.txt"
            outside.write_text("outside content", encoding="utf-8")
            (root / "linked.skill").symlink_to(outside)

            skills = class_commentary.list_colleague_skills(str(root))

            with self.assertRaises(FileNotFoundError):
                class_commentary.load_colleague_skill(str(root), "linked")

        self.assertEqual(skills, [])

    def test_skill_scanner_ignores_symlinked_meta_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = root / "teacher-safe-meta"
            package.mkdir()
            (package / "SKILL.md").write_text("safe content", encoding="utf-8")
            outside_meta = root / "outside-meta.json"
            outside_meta.write_text('{"name": "Outside name"}', encoding="utf-8")
            (package / "meta.json").symlink_to(outside_meta)

            skills = class_commentary.list_colleague_skills(str(root))
            loaded = class_commentary.load_colleague_skill(
                str(root), "teacher-safe-meta"
            )

        self.assertEqual(skills[0]["name"], "teacher-safe-meta")
        self.assertEqual(loaded["name"], "teacher-safe-meta")

    def test_skill_scanner_does_not_read_meta_json_swapped_to_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = root / "teacher-safe-meta"
            package.mkdir()
            (package / "SKILL.md").write_text("safe content", encoding="utf-8")
            meta_path = package / "meta.json"
            meta_path.write_text('{"name": "Safe name"}', encoding="utf-8")
            outside_meta = root / "outside-meta.json"
            outside_meta.write_text('{"name": "OUTSIDE_SECRET"}', encoding="utf-8")
            original_stat = (
                class_commentary._stat_class_commentary_skill_file_if_regular
            )
            swapped = False

            def swap_after_stat(directory_fd, filename):
                nonlocal swapped
                result = original_stat(directory_fd, filename)
                if filename == "meta.json" and not swapped:
                    swapped = True
                    meta_path.unlink()
                    meta_path.symlink_to(outside_meta)
                return result

            with patch.object(
                class_commentary,
                "_stat_class_commentary_skill_file_if_regular",
                side_effect=swap_after_stat,
            ):
                skills = class_commentary.list_colleague_skills(str(root))

        self.assertEqual(skills[0]["name"], "teacher-safe-meta")

    def test_skill_scanner_ignores_symlinked_colleagues_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            outside = root / "outside-colleagues"
            package = outside / "teacher-outside"
            package.mkdir(parents=True)
            (package / "SKILL.md").write_text("outside content", encoding="utf-8")
            visible = root / "skills"
            visible.mkdir()
            (visible / "colleagues").symlink_to(outside, target_is_directory=True)

            skills = class_commentary.list_colleague_skills(str(visible))

            with self.assertRaises(FileNotFoundError):
                class_commentary.load_colleague_skill(
                    str(visible), "teacher-outside"
                )

        self.assertEqual(skills, [])

    def test_skill_scanner_rejects_colleagues_root_swapped_to_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            colleagues = root / "colleagues"
            colleagues.mkdir()
            outside = root / "outside"
            outside.mkdir()
            (outside / "OUTSIDE_SECRET.skill").write_text(
                "secret", encoding="utf-8"
            )
            original_open = class_commentary._open_class_commentary_skill_directory
            swapped = False

            def swap_before_open(path, *, dir_fd=None):
                nonlocal swapped
                if path == "colleagues" and dir_fd is not None and not swapped:
                    swapped = True
                    colleagues.rmdir()
                    colleagues.symlink_to(outside, target_is_directory=True)
                return original_open(path, dir_fd=dir_fd)

            with patch.object(
                class_commentary,
                "_open_class_commentary_skill_directory",
                side_effect=swap_before_open,
            ):
                skills = class_commentary.list_colleague_skills(str(root))

        self.assertEqual(skills, [])

    def test_skill_scanner_stays_on_open_colleagues_fd_after_path_swap(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            colleagues = root / "colleagues"
            colleagues.mkdir()
            (colleagues / "safe.skill").write_text("safe", encoding="utf-8")
            outside = root / "outside"
            outside.mkdir()
            (outside / "OUTSIDE_SECRET.skill").write_text(
                "secret", encoding="utf-8"
            )
            moved_colleagues = root / "colleagues-original"
            original_open = class_commentary._open_class_commentary_skill_directory
            swapped = False

            def swap_after_open(path, *, dir_fd=None):
                nonlocal swapped
                opened_fd = original_open(path, dir_fd=dir_fd)
                if path == "colleagues" and dir_fd is not None and not swapped:
                    swapped = True
                    colleagues.rename(moved_colleagues)
                    colleagues.symlink_to(outside, target_is_directory=True)
                return opened_fd

            with patch.object(
                class_commentary,
                "_open_class_commentary_skill_directory",
                side_effect=swap_after_open,
            ):
                skills = class_commentary.list_colleague_skills(str(root))

        self.assertEqual([item["id"] for item in skills], ["safe"])

    def test_skill_scanner_uses_deterministic_case_tie_order(self):
        self.assertEqual(
            sorted(
                ["teacher-a", "Teacher-A"],
                key=class_commentary._colleague_skill_sort_key,
            ),
            ["Teacher-A", "teacher-a"],
        )

    def test_skill_loader_rejects_too_many_markdown_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = root / "teacher-too-many-files"
            knowledge = package / "knowledge"
            knowledge.mkdir(parents=True)
            (package / "SKILL.md").write_text("Skill", encoding="utf-8")
            (knowledge / "one.md").write_text("One", encoding="utf-8")
            (knowledge / "two.md").write_text("Two", encoding="utf-8")

            with patch.object(
                class_commentary,
                "CLASS_COMMENTARY_SKILL_PACKAGE_MAX_MARKDOWN_FILES",
                2,
            ):
                with self.assertRaisesRegex(ValueError, "file count exceeds limit"):
                    class_commentary.load_colleague_skill(
                        str(root), "teacher-too-many-files"
                    )

    def test_skill_loader_accepts_64_markdown_files_and_rejects_65(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = root / "teacher-file-boundary"
            knowledge = package / "knowledge"
            knowledge.mkdir(parents=True)
            (package / "SKILL.md").write_text("Skill", encoding="utf-8")
            for index in range(63):
                (knowledge / f"{index:02d}.md").write_text(
                    f"Example {index}", encoding="utf-8"
                )

            loaded = class_commentary.load_colleague_skill(
                str(root), "teacher-file-boundary"
            )
            self.assertIn("Example 62", loaded["content"])

            (knowledge / "overflow.md").write_text("Overflow", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "file count exceeds limit"):
                class_commentary.load_colleague_skill(
                    str(root), "teacher-file-boundary"
                )

    def test_skill_loader_rejects_oversized_markdown_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = root / "teacher-large-file"
            package.mkdir()
            (package / "SKILL.md").write_text("123456789", encoding="utf-8")

            with patch.object(
                class_commentary,
                "CLASS_COMMENTARY_SKILL_PACKAGE_MAX_FILE_BYTES",
                8,
            ):
                with self.assertRaisesRegex(ValueError, "file size exceeds limit"):
                    class_commentary.load_colleague_skill(
                        str(root), "teacher-large-file"
                    )

    def test_skill_loader_accepts_256_kib_file_and_rejects_one_byte_more(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = root / "teacher-file-size-boundary"
            package.mkdir()
            skill_path = package / "SKILL.md"
            skill_path.write_bytes(
                b"x" * class_commentary.CLASS_COMMENTARY_SKILL_PACKAGE_MAX_FILE_BYTES
            )

            loaded = class_commentary.load_colleague_skill(
                str(root), "teacher-file-size-boundary"
            )
            self.assertEqual(
                len(loaded["content"].split("\n", 1)[1].encode("utf-8")),
                class_commentary.CLASS_COMMENTARY_SKILL_PACKAGE_MAX_FILE_BYTES,
            )

            skill_path.write_bytes(
                b"x"
                * (class_commentary.CLASS_COMMENTARY_SKILL_PACKAGE_MAX_FILE_BYTES + 1)
            )
            with self.assertRaisesRegex(ValueError, "file size exceeds limit"):
                class_commentary.load_colleague_skill(
                    str(root), "teacher-file-size-boundary"
                )

    def test_skill_loader_rejects_oversized_legacy_skill_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "teacher-large-legacy.skill").write_text(
                "123456789", encoding="utf-8"
            )

            with patch.object(
                class_commentary,
                "CLASS_COMMENTARY_SKILL_PACKAGE_MAX_FILE_BYTES",
                8,
            ):
                with self.assertRaisesRegex(ValueError, "file size exceeds limit"):
                    class_commentary.load_colleague_skill(
                        str(root), "teacher-large-legacy"
                    )

    def test_skill_loader_rejects_oversized_markdown_total(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = root / "teacher-large-total"
            package.mkdir()
            (package / "SKILL.md").write_text("123456", encoding="utf-8")
            (package / "work.md").write_text("1234567", encoding="utf-8")

            with patch.object(
                class_commentary,
                "CLASS_COMMENTARY_SKILL_PACKAGE_MAX_FILE_BYTES",
                16,
            ), patch.object(
                class_commentary,
                "CLASS_COMMENTARY_SKILL_PACKAGE_MAX_TOTAL_BYTES",
                12,
            ):
                with self.assertRaisesRegex(ValueError, "total size exceeds limit"):
                    class_commentary.load_colleague_skill(
                        str(root), "teacher-large-total"
                    )

    def test_skill_loader_accepts_one_mib_total_and_rejects_one_byte_more(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = root / "teacher-total-boundary"
            knowledge = package / "knowledge"
            knowledge.mkdir(parents=True)
            per_file = class_commentary.CLASS_COMMENTARY_SKILL_PACKAGE_MAX_FILE_BYTES
            for path in (
                package / "SKILL.md",
                package / "work.md",
                package / "persona.md",
                knowledge / "sample.md",
            ):
                path.write_bytes(b"x" * per_file)

            loaded = class_commentary.load_colleague_skill(
                str(root), "teacher-total-boundary"
            )
            self.assertTrue(loaded["content"])

            (knowledge / "overflow.md").write_bytes(b"x")
            with self.assertRaisesRegex(ValueError, "total size exceeds limit"):
                class_commentary.load_colleague_skill(
                    str(root), "teacher-total-boundary"
                )

    def test_skill_loader_skips_package_files_already_embedded_in_skill_md(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = root / "teacher-d"
            package.mkdir()
            work_content = "# Work Skill\nUse direct, actionable feedback."
            persona_content = "# Persona\nUse a warm parent-group voice."
            (package / "SKILL.md").write_text(
                "# Teacher D\n\n## Part A\n"
                + work_content
                + "\n\n## Part B\n"
                + persona_content,
                encoding="utf-8",
            )
            (package / "work.md").write_text(work_content, encoding="utf-8")
            (package / "persona.md").write_text(persona_content, encoding="utf-8")

            loaded = class_commentary.load_colleague_skill(str(root), "teacher-d")

        self.assertEqual(loaded["content"].count(work_content), 1)
        self.assertEqual(loaded["content"].count(persona_content), 1)
        self.assertNotIn("## work.md", loaded["content"])
        self.assertNotIn("## persona.md", loaded["content"])

    def test_skill_loader_keeps_revised_work_and_skips_embedded_persona(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = root / "teacher-e"
            package.mkdir()
            embedded_work = "# Work Skill\nUse direct feedback."
            revised_work = embedded_work + "\nAlways include one next step."
            persona_content = "# Persona\nUse a calm parent-group voice."
            (package / "SKILL.md").write_text(
                "# Teacher E\n\n## Part A\n"
                + embedded_work
                + "\n\n## Part B\n"
                + persona_content,
                encoding="utf-8",
            )
            (package / "work.md").write_text(revised_work, encoding="utf-8")
            (package / "persona.md").write_text(persona_content, encoding="utf-8")

            loaded = class_commentary.load_colleague_skill(str(root), "teacher-e")

        self.assertIn("## work.md", loaded["content"])
        self.assertIn(revised_work, loaded["content"])
        self.assertEqual(loaded["content"].count(persona_content), 1)
        self.assertNotIn("## persona.md", loaded["content"])

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

    def test_structured_v2_prompt_maps_spoken_asr_names_to_complete_attending_roster(self):
        request_payload = class_commentary.build_class_commentary_chat_request(
            class_record={"id": 7, "name": "数学七年级四班"},
            students=[
                {"id": 1, "name": "陈致丹"},
                {"id": 2, "name": "严岚"},
            ],
            transcript_text="陈志丹今天计算更稳. 严兰下一步要继续验算.",
            skill={
                "id": "teacher-a",
                "name": "Teacher A",
                "content": "warm concise style",
            },
            teacher_style_memories=[],
            student_history_memories=[],
            feedback_schema_version="class_commentary.student_feedback.v1",
            eligible_student_ids=[1, 2],
            prompt_version=(
                class_commentary.CLASS_COMMENTARY_STRUCTURED_PROMPT_VERSION_V2
            ),
            response_format={"type": "json_object"},
            student_history_memory_mode="disabled_v1",
        )

        system_prompt = request_payload["messages"][0]["content"]
        user_prompt = request_payload["messages"][1]["content"]
        self.assertEqual(
            request_payload["prompt_version"],
            class_commentary.CLASS_COMMENTARY_STRUCTURED_PROMPT_VERSION_V2,
        )
        self.assertIn("complete attending scope", system_prompt)
        self.assertIn("homophones", system_prompt)
        self.assertIn("starts each student's segment", system_prompt)
        self.assertIn('"name": "陈致丹"', user_prompt)
        self.assertIn('"eligible_student_ids": [', user_prompt)
        self.assertIn("does not need to contain the official roster name exactly", user_prompt)
        self.assertNotIn("[STUDENT_HISTORY_MEMORIES]", user_prompt)

    def test_structured_v3_prompt_requires_teacher_to_speak_directly_to_student(self):
        request_payload = class_commentary.build_class_commentary_chat_request(
            class_record={"id": 7, "name": "数学七年级四班"},
            students=[{"id": 1, "name": "代子翔"}],
            transcript_text="代子翔下去要多复习函数.",
            skill={
                "id": "teacher-a",
                "name": "Teacher A",
                "content": "Write a concise third-person parent report.",
            },
            teacher_style_memories=[
                {"memory_id": 11, "content": "Use concise sentences."},
            ],
            student_history_memories=[],
            feedback_schema_version="class_commentary.student_feedback.v1",
            eligible_student_ids=[1],
            prompt_version=(
                class_commentary.CLASS_COMMENTARY_STRUCTURED_PROMPT_VERSION_V3
            ),
            response_format={"type": "json_object"},
            student_history_memory_mode="disabled_v1",
        )

        system_prompt = request_payload["messages"][0]["content"]
        user_prompt = request_payload["messages"][1]["content"]
        self.assertEqual(
            request_payload["prompt_version"],
            class_commentary.CLASS_COMMENTARY_STRUCTURED_PROMPT_VERSION_V3,
        )
        self.assertIn("teacher speaking directly to that student", system_prompt)
        self.assertIn("cannot add student facts or override the direct-address perspective", system_prompt)
        self.assertIn("Begin with the target student's official name", user_prompt)
        self.assertIn("Never refer to the target student as '他', '她', '该生'", user_prompt)
        self.assertIn("instead of repeatedly starting sentences with '你要'", user_prompt)
        self.assertIn("'代子翔, 你下去多复习一下函数'", user_prompt)
        self.assertIn("mandatory even if ACTIVE_SKILL", user_prompt)

    def test_batch_v4_prompt_uses_complete_skill_and_partitioned_context(self):
        skill_content = (
            "## SKILL.md\n先肯定具体表现🌱, 再指出问题🔍。\n\n"
            "## work.md\n每位学生写 2-4 个短段落, 给出下一步行动✨。\n\n"
            "## persona.md\n保持家长群里自然、温暖的口吻。"
        )
        request_payload = class_commentary.build_class_commentary_chat_request(
            class_record={"id": 7, "name": "数学七年级四班"},
            students=[
                {"id": 1, "name": "代子翔"},
                {"id": 2, "name": "陈致丹"},
            ],
            transcript_text=(
                "代子翔今天函数图像判断更稳, 但定义域还会漏写。"
                "陈致丹移项步骤清楚, 下一步要完整验算。"
            ),
            skill={
                "id": "teacher-a",
                "name": "Teacher A",
                "content": skill_content,
            },
            teacher_style_memories=[
                {"memory_id": 11, "content": "句子自然, 不写正式报告。"},
            ],
            student_history_memories=[],
            feedback_schema_version="class_commentary.student_feedback.v1",
            eligible_student_ids=[1, 2],
            prompt_version=(
                class_commentary.CLASS_COMMENTARY_BATCH_ISOLATED_PROMPT_VERSION_V4
            ),
            response_format={"type": "json_object"},
            student_history_memory_mode="batch_isolated_v3",
            student_contexts_by_id=[
                {
                    "student_id": 1,
                    "memory_retrieval_status": "ready",
                    "student_history_memories": [
                        {
                            "historical_context": "此前定义域书写不完整",
                            "source_time": "2026-08-01",
                        }
                    ],
                    "learning_graph": {
                        "retrieval_status": "ready",
                        "current_states": [],
                        "recent_changes": [],
                        "allowed_evidence_refs": ["evidence-1"],
                    },
                },
                {
                    "student_id": 2,
                    "memory_retrieval_status": "ready",
                    "student_history_memories": [
                        {
                            "historical_context": "此前验算步骤容易省略",
                            "source_time": "2026-08-02",
                        }
                    ],
                    "learning_graph": {
                        "retrieval_status": "empty",
                        "current_states": [],
                        "recent_changes": [],
                        "allowed_evidence_refs": [],
                    },
                },
            ],
        )

        system_prompt = request_payload["messages"][0]["content"]
        user_prompt = request_payload["messages"][1]["content"]
        active_skill_json = user_prompt.split("[ACTIVE_SKILL]\n", 1)[1].split(
            "\n\n[TEACHER_STYLE_MEMORIES]\n", 1
        )[0]
        active_skill = json.loads(active_skill_json)
        output_rules = user_prompt.split("[OUTPUT_RULES]\n", 1)[1]

        self.assertEqual(active_skill["content"], skill_content)
        self.assertEqual(
            request_payload["prompt_version"],
            class_commentary.CLASS_COMMENTARY_BATCH_ISOLATED_PROMPT_VERSION_V4,
        )
        self.assertEqual(
            request_payload["student_history_memory_mode"],
            "batch_isolated_v3",
        )
        self.assertEqual(user_prompt.count("[ACTIVE_SKILL]"), 1)
        self.assertIn("primary writing contract", system_prompt)
        self.assertIn("emoji tokens, density, placement, and purpose", system_prompt)
        self.assertIn("2-4 short paragraphs", output_rules)
        self.assertIn("specific problem", output_rules)
        self.assertIn("concrete next action", output_rules)
        self.assertIn("every student's feedback", output_rules)
        self.assertIn("at least one matching emoji", output_rules)
        self.assertIn("structured", output_rules)
        self.assertIn("conversational parent-group voice", output_rules)
        self.assertIn("used_graph_evidence_refs_by_student", output_rules)
        self.assertIn("[STUDENT_CONTEXTS_BY_ID]", user_prompt)
        self.assertIn("此前定义域书写不完整", user_prompt)
        self.assertIn("此前验算步骤容易省略", user_prompt)
        self.assertIn("evidence-1", user_prompt)
        self.assertNotIn("[STUDENT_HISTORY_MEMORIES]", user_prompt)

    def test_batch_v5_prompt_includes_complete_transcript_and_official_rosters(self):
        transcript = "刘峰峰今天移项步骤更清楚.张玉空验算更主动."
        request_payload = class_commentary.build_class_commentary_chat_request(
            class_record={"id": 7, "name": "数学七年级四班"},
            students=[
                {"id": 1, "name": "刘鹏鹏"},
                {"id": 2, "name": "张玉坤"},
            ],
            official_course_roster=[
                {"id": 1, "name": "刘鹏鹏"},
                {"id": 2, "name": "张玉坤"},
                {"id": 3, "name": "王小明"},
            ],
            transcript_text=transcript,
            skill={"id": "teacher-a", "name": "Teacher A", "content": "自然沟通."},
            teacher_style_memories=[],
            student_history_memories=[],
            feedback_schema_version="class_commentary.student_feedback.v1",
            eligible_student_ids=[1, 2],
            prompt_version=(
                class_commentary.CLASS_COMMENTARY_BATCH_ISOLATED_PROMPT_VERSION_V5
            ),
            response_format={"type": "json_object"},
            student_history_memory_mode="batch_isolated_v3",
            student_contexts_by_id=[
                {
                    "student_id": student_id,
                    "current_student_evidence": {"verified_fragments": []},
                    "memory_retrieval_status": "empty",
                    "student_history_memories": [],
                    "learning_graph": {
                        "retrieval_status": "empty",
                        "current_states": [],
                        "recent_changes": [],
                        "allowed_evidence_refs": [],
                    },
                }
                for student_id in (1, 2)
            ],
        )

        system_prompt = request_payload["messages"][0]["content"]
        user_prompt = request_payload["messages"][1]["content"]
        current_facts_json = user_prompt.split(
            "[CURRENT_TASK_FACTS]\n", 1
        )[1].split("\n\n[ACTIVE_SKILL]\n", 1)[0]
        current_facts = json.loads(current_facts_json)

        self.assertEqual(current_facts["transcript"], transcript)
        self.assertEqual(
            current_facts["students"],
            [{"id": 1, "name": "刘鹏鹏"}, {"id": 2, "name": "张玉坤"}],
        )
        self.assertEqual(
            current_facts["official_course_roster"],
            [
                {"id": 1, "name": "刘鹏鹏"},
                {"id": 2, "name": "张玉坤"},
                {"id": 3, "name": "王小明"},
            ],
        )
        self.assertEqual(current_facts["eligible_student_ids"], [1, 2])
        self.assertIn("homophones, near-sounding syllables", system_prompt)
        self.assertIn("If a spoken name cannot be mapped uniquely", system_prompt)
        self.assertIn("never generate an item", system_prompt)
        self.assertIn("[STUDENT_CONTEXTS_BY_ID]", user_prompt)
        self.assertIn('"verified_fragments": []', user_prompt)

    def test_batch_v6_prompt_requires_a_final_per_student_emoji_check(self):
        request_payload = class_commentary.build_class_commentary_chat_request(
            class_record={"id": 7, "name": "数学七年级四班"},
            students=[{"id": 1, "name": "刘鹏鹏"}],
            official_course_roster=[{"id": 1, "name": "刘鹏鹏"}],
            transcript_text="刘鹏鹏今天移项步骤更清楚.",
            skill={
                "id": "teacher-a",
                "name": "Teacher A",
                "content": "常用表情: [强] [抱拳].",
            },
            teacher_style_memories=[],
            student_history_memories=[],
            feedback_schema_version="class_commentary.student_feedback.v1",
            eligible_student_ids=[1],
            prompt_version=(
                class_commentary.CLASS_COMMENTARY_BATCH_ISOLATED_PROMPT_VERSION_V6
            ),
            response_format={"type": "json_object"},
            student_history_memory_mode="batch_isolated_v3",
            student_contexts_by_id=[{"student_id": 1}],
        )

        system_prompt = request_payload["messages"][0]["content"]
        output_rules = request_payload["messages"][1]["content"].split(
            "[OUTPUT_RULES]\n", 1
        )[1]

        self.assertEqual(
            request_payload["prompt_version"],
            class_commentary.CLASS_COMMENTARY_BATCH_ISOLATED_PROMPT_VERSION_V6,
        )
        self.assertIn("mandatory output constraint", system_prompt)
        self.assertIn("every feedback_text", output_rules)
        self.assertIn("exact emoji token from ACTIVE_SKILL", output_rules)
        self.assertIn("privately verify every eligible student item", output_rules)
        self.assertIn("repair every zero-token item", output_rules)

    def test_structured_prompt_rejects_unknown_prompt_version(self):
        with self.assertRaisesRegex(ValueError, "prompt version is invalid"):
            class_commentary.build_class_commentary_chat_request(
                class_record={"id": 7, "name": "数学七年级四班"},
                students=[{"id": 1, "name": "陈致丹"}],
                transcript_text="陈志丹今天计算更稳.",
                skill={"id": "teacher-a", "name": "Teacher A", "content": ""},
                feedback_schema_version="class_commentary.student_feedback.v1",
                eligible_student_ids=[1],
                prompt_version="class-commentary-student-feedback-unknown",
                response_format={"type": "json_object"},
                student_history_memory_mode="disabled_v1",
            )

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
        self.assertNotIn("response_format", fake_client.chat.completions.kwargs)

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

    def test_generate_class_commentary_feedback_forwards_frozen_response_format(self):
        model_content = (
            '{"schema_version":"class_commentary.student_feedback.v1",'
            '"items":[{"student_id":21,"feedback_text":"Arithmetic checks improved."}]}'
        )

        class FakeMessage:
            content = model_content

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

        response_format = {"type": "json_object"}
        chat_request = {
            "prompt_version": "class-commentary-student-feedback-v1",
            "messages": [
                {"role": "system", "content": "Return the frozen structured contract."},
                {"role": "user", "content": "Generate feedback for student 21. Output JSON."},
            ],
            "temperature": 0.23,
            "response_format": response_format,
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
        self.assertEqual(text, model_content)
        self.assertIs(call_payload["messages"], chat_request["messages"])
        self.assertEqual(call_payload["temperature"], chat_request["temperature"])
        self.assertIs(call_payload["response_format"], response_format)

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
            max_retries=None,
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
