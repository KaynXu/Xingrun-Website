import unittest

from review_plan_workflow.source_pack import (
    build_lesson_source_pack,
    source_pack_cache_key_for_text,
    source_pack_needs_rebuild,
    source_pack_trace_payload,
)


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
        self.assertEqual(pack.cache_key, pack_again.cache_key)
        self.assertEqual(pack.raw_source_hash, pack.source_hash)
        self.assertTrue(pack.cleaned_source_hash.startswith("sha256:"))
        self.assertEqual(pack.parser_version, "source_pack_parser_v2")
        self.assertEqual([segment.id for segment in pack.segments], [segment.id for segment in pack_again.segments])
        self.assertEqual(pack.title, "勾股数、特殊角度αβ与和角推导")
        self.assertGreaterEqual(len(pack.segments), 4)
        self.assertTrue(any("整数勾股数" in topic for topic in pack.detected_topics))
        self.assertTrue(any(block.raw in {"3:4:5", "1:√2"} or "√2" in block.raw for block in pack.math_blocks))
        self.assertTrue(any(action.action_type == "homework" for action in pack.teacher_actions))
        self.assertTrue(any("抽查" in action.text for action in pack.teacher_actions))
        self.assertFalse(
            source_pack_needs_rebuild(
                pack,
                raw_source_hash=pack.raw_source_hash,
                cleaned_source_hash=pack.cleaned_source_hash,
            )
        )
        self.assertTrue(
            source_pack_needs_rebuild(
                {"schema_version": pack.schema_version, "source_hash": pack.source_hash},
                raw_source_hash=pack.raw_source_hash,
                cleaned_source_hash=pack.cleaned_source_hash,
            )
        )

    def test_source_pack_trace_payload_does_not_include_source_text(self):
        pack = build_lesson_source_pack(raw_text="主题：一次函数\n必须整理错题。", source_type="text")

        payload = source_pack_trace_payload(pack)

        self.assertEqual(payload["segments_count"], 2)
        self.assertEqual(payload["parser_version"], "source_pack_parser_v2")
        self.assertEqual(payload["cache_key"], pack.cache_key)
        self.assertIn("source_hash", payload)
        self.assertNotIn("一次函数", str(payload.get("segments", "")))

    def test_source_pack_cache_key_depends_on_raw_and_cleaned_text(self):
        key_a = source_pack_cache_key_for_text(raw_text=" 主题：一次函数\n\n必须整理错题。 ")
        key_b = source_pack_cache_key_for_text(raw_text="主题：一次函数\n必须整理错题。")
        key_c = source_pack_cache_key_for_text(raw_text="主题：二次函数\n必须整理错题。")

        self.assertNotEqual(key_a, key_b)
        self.assertNotEqual(key_b, key_c)

    def test_long_transcript_is_section_segmented_without_120_line_truncation(self):
        lines = [
            "勾股数、特殊角与和角推导完整课堂逐字稿",
            "第一部分：整数勾股数讲解",
        ]
        for index in range(1, 135):
            lines.append(f"说话人1：知识点：第{index}个勾股数例题，例题：3:4:5 的第{index}次应用。")
        lines.extend(
            [
                "第二部分：特殊角度 αβ 与和角推导",
                "说话人1：重点：α+β=45°，必须重新演算。",
                "课堂收尾",
                "说话人1：课后作业：完整抄写并明天抽查。",
            ]
        )

        pack = build_lesson_source_pack(raw_text="\n".join(lines), source_type="transcript", subject="数学")
        payload = source_pack_trace_payload(pack)

        self.assertGreater(len(pack.segments), 120)
        self.assertTrue(any("第134个勾股数例题" in segment.text for segment in pack.segments))
        self.assertTrue(any(segment.kind == "heading" and "第二部分" in segment.text for segment in pack.segments))
        self.assertTrue(any(getattr(segment, "section_title", "") == "第二部分：特殊角度 αβ 与和角推导" for segment in pack.segments))
        self.assertTrue(all(str(getattr(segment, "chunk_hash", "")).startswith("sha256:") for segment in pack.segments))
        self.assertTrue(all(str(getattr(segment, "extraction_cache_key", "")).startswith("sha256:") for segment in pack.segments))
        self.assertTrue(any(getattr(segment, "math_count", 0) > 0 for segment in pack.segments))
        self.assertIn("long_source_segmented", pack.warnings)
        self.assertGreaterEqual(payload["sections_count"], 3)
        self.assertEqual(payload["segment_cache_key_count"], len(pack.segments))
        self.assertNotIn("第134个勾股数例题", str(payload))


if __name__ == "__main__":
    unittest.main()
