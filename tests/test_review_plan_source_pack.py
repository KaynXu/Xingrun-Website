import unittest

from review_plan_workflow.source_pack import build_lesson_source_pack, source_pack_trace_payload


class ReviewPlanSourcePackTestCase(unittest.TestCase):
    def test_build_lesson_source_pack_is_stable_and_structured(self):
        transcript = (
            "勾股数、特殊角度αβ与和角推导完整课堂逐字稿\n"
            "第一部分：整数勾股数（奇数型、偶数型）、根式勾股数讲解\n"
            "说话人1：必须背熟 3:4:5、5:12:13、1:1:√2。\n"
            "说话人1：课后作业1：自己推导2β的勾股比；明天抽查。"
        )

        pack = build_lesson_source_pack(
            raw_text=transcript,
            source_type="transcript",
            subject="数学",
            user_requirements="题目控制在10道题",
        )
        pack_again = build_lesson_source_pack(
            raw_text=transcript,
            source_type="transcript",
            subject="数学",
            user_requirements="题目控制在10道题",
        )

        self.assertEqual(pack.source_hash, pack_again.source_hash)
        self.assertEqual(pack.source_id, pack_again.source_id)
        self.assertEqual([segment.id for segment in pack.segments], [segment.id for segment in pack_again.segments])
        self.assertEqual(pack.title, "勾股数、特殊角度αβ与和角推导")
        self.assertGreaterEqual(len(pack.segments), 4)
        self.assertTrue(any("整数勾股数" in topic for topic in pack.detected_topics))
        self.assertTrue(any(block.raw in {"3:4:5", "1:√2"} or "√2" in block.raw for block in pack.math_blocks))
        self.assertTrue(any(action.action_type == "homework" for action in pack.teacher_actions))
        self.assertTrue(any("抽查" in action.text for action in pack.teacher_actions))

    def test_source_pack_trace_payload_does_not_include_source_text(self):
        pack = build_lesson_source_pack(raw_text="主题：一次函数\n必须整理错题。", source_type="text")

        payload = source_pack_trace_payload(pack)

        self.assertEqual(payload["segments_count"], 2)
        self.assertIn("source_hash", payload)
        self.assertNotIn("一次函数", str(payload.get("segments", "")))


if __name__ == "__main__":
    unittest.main()
