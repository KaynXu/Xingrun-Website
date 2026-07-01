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
            ),
            subject="数学",
            topic="",
            weak_points="轨迹判断",
            user_requirements="少一点题量，多做诊断",
        )

        self.assertEqual(brief.schema_version, "2026-07-01")
        self.assertEqual(brief.lesson_title_candidates[0], "动点与立体几何综合")
        self.assertTrue(any(item.name == "轨迹判断" for item in brief.knowledge_points))
        self.assertTrue(any("固定量" in " ".join(item.steps) for item in brief.method_chains))
        self.assertTrue(any("球面" in item.name for item in brief.common_mistakes))
        self.assertTrue(any("动点 P" in item.stem for item in brief.example_stems))
        self.assertTrue(any("先看固定量" in item.quote for item in brief.teacher_emphasis))
        self.assertTrue(brief.evidence_map)
        self.assertGreaterEqual(brief.confidence, 0.7)

    def test_deterministic_brief_marks_missing_topic_when_no_topic_signal_exists(self):
        brief = build_deterministic_source_brief(
            raw_text="今天讲了很多题，学生容易把条件看漏。",
            subject="数学",
            topic="",
            weak_points="",
            user_requirements="",
        )

        self.assertIn("topic", brief.missing_fields)
        self.assertLess(brief.confidence, 0.7)
        self.assertTrue(brief.evidence_map)
