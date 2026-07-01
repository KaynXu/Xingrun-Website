import unittest

from review_plan_workflow.source_brief import (
    build_deterministic_source_brief,
    clean_source_text,
    source_text_hash,
)


class ReviewPlanSourceBriefTestCase(unittest.TestCase):
    def test_source_text_hash_is_stable_and_redactable(self):
        first = source_text_hash("动点与立体几何综合")
        second = source_text_hash("动点与立体几何综合")
        other = source_text_hash("一次函数")

        self.assertEqual(first, second)
        self.assertTrue(first.startswith("sha256:"))
        self.assertEqual(len(first), len("sha256:") + 64)
        self.assertNotEqual(first, other)
        self.assertNotIn("动点", first)

    def test_clean_source_text_removes_common_asr_noise_without_destroying_math(self):
        cleaned = clean_source_text(
            "嗯嗯 今天我们讲 动点 与 立体几何。\r\n"
            "然后然后 PA=PB，angle ABC = 60 ^circ。\n\n"
            "好吧好吧 先看固定量，再判断轨迹。"
        )

        self.assertIn("动点 与 立体几何", cleaned)
        self.assertIn("PA=PB", cleaned)
        self.assertIn("angle ABC = 60 ^circ", cleaned)
        self.assertIn("先看固定量，再判断轨迹", cleaned)
        self.assertNotIn("\r", cleaned)
        self.assertNotIn("嗯嗯", cleaned)
        self.assertNotIn("然后然后", cleaned)
        self.assertNotIn("好吧好吧", cleaned)

    def test_deterministic_brief_extracts_topic_knowledge_methods_and_evidence(self):
        brief = build_deterministic_source_brief(
            raw_text=(
                "本节课主题：动点与立体几何综合\n"
                "老师强调：先看固定量，再判断轨迹。\n"
                "例题：动点 P 到定点 O 的距离恒为 r，轨迹是什么？\n"
                "易错：把空间球面误看成平面圆。\n"
                "方法：固定量 -> 轨迹对象 -> 边界条件。"
                "\n知识点：轨迹判断。\n"
            ),
            subject="数学",
            topic="",
            weak_points="轨迹判断",
            user_requirements="少一点题量，多做诊断",
        )

        self.assertEqual(brief.schema_version, "2026-07-01")
        evidence_by_quote = {item.quote: item for item in brief.evidence_map}
        self.assertEqual(brief.lesson_title_candidates[0], "动点与立体几何综合")
        self.assertEqual(
            next(item for item in brief.knowledge_points if item.name == "轨迹判断").evidence_ids,
            [evidence_by_quote["知识点：轨迹判断。"].id],
        )
        self.assertEqual(
            next(item for item in brief.method_chains if "固定量" in " ".join(item.steps)).evidence_ids,
            [evidence_by_quote["方法：固定量 -> 轨迹对象 -> 边界条件。"].id],
        )
        self.assertEqual(
            next(item for item in brief.common_mistakes if "球面" in item.name).evidence_ids,
            [evidence_by_quote["易错：把空间球面误看成平面圆。"].id],
        )
        self.assertEqual(
            next(item for item in brief.example_stems if "动点 P" in item.stem).evidence_ids,
            [evidence_by_quote["例题：动点 P 到定点 O 的距离恒为 r，轨迹是什么？"].id],
        )
        self.assertEqual(
            next(item for item in brief.teacher_emphasis if "先看固定量" in item.quote).evidence_ids,
            [evidence_by_quote["老师强调：先看固定量，再判断轨迹。"].id],
        )
        self.assertTrue(brief.evidence_map)
        self.assertGreaterEqual(brief.confidence, 0.7)

    def test_deterministic_brief_tracks_duplicate_sentence_offsets(self):
        brief = build_deterministic_source_brief(
            raw_text=(
                "重复句子。\n"
                "重复句子。\n"
                "知识点：轨迹判断。\n"
            ),
            subject="数学",
            topic="",
            weak_points="",
            user_requirements="",
        )

        repeated = [item for item in brief.evidence_map if item.quote == "重复句子。"]
        self.assertEqual(len(repeated), 2)
        self.assertEqual(repeated[0].offset_start, 0)
        self.assertEqual(repeated[1].offset_start, 6)
        self.assertNotEqual(repeated[0].offset_start, repeated[1].offset_start)
        self.assertNotEqual(repeated[0].offset_end, repeated[1].offset_end)

    def test_deterministic_brief_rejects_overly_broad_triggers(self):
        brief = build_deterministic_source_brief(
            raw_text="今天讲了很多题，学生有点迷糊。先复习一下概念，别急。",
            subject="数学",
            topic="",
            weak_points="",
            user_requirements="",
        )

        self.assertIn("topic", brief.missing_fields)
        self.assertLess(brief.confidence, 0.7)
        self.assertFalse(brief.knowledge_points)
        self.assertFalse(brief.method_chains)
        self.assertFalse(brief.common_mistakes)
        self.assertFalse(brief.example_stems)
        self.assertFalse(brief.teacher_emphasis)
        self.assertTrue(brief.evidence_map)

    def test_deterministic_brief_does_not_classify_plain_steps_or_title_as_examples_or_emphasis(self):
        brief = build_deterministic_source_brief(
            raw_text=(
                "本节课主题：动点与立体几何综合\n"
                "先判断轨迹。\n"
                "先求点P的位置。\n"
                "动点P在圆上。\n"
                "轨迹是什么。\n"
            ),
            subject="数学",
            topic="",
            weak_points="",
            user_requirements="",
        )

        self.assertEqual(brief.lesson_title_candidates[0], "动点与立体几何综合")
        self.assertFalse(brief.example_stems)
        self.assertFalse(brief.teacher_emphasis)

    def test_deterministic_brief_recognizes_plain_qiu_and_question_form_examples(self):
        brief = build_deterministic_source_brief(
            raw_text=(
                "求点P的轨迹。\n"
                "轨迹是什么？\n"
                "例题：再想一想这个问题。\n"
            ),
            subject="数学",
            topic="",
            weak_points="",
            user_requirements="",
        )

        example_texts = [item.stem for item in brief.example_stems]
        self.assertIn("求点P的轨迹", " ".join(example_texts))
        self.assertIn("轨迹是什么？", example_texts)
        self.assertTrue(brief.example_stems)
