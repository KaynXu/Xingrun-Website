import hashlib
import json
import unittest

from class_commentary_feedback_schema import (
    ClassCommentaryStudentScopeError,
    ClassCommentaryStructuredFeedbackValidationError,
    build_class_commentary_feedback_read_envelope,
    canonicalize_class_commentary_structured_feedback,
    match_class_commentary_eligible_student_ids,
)


SCHEMA_VERSION = "class_commentary.student_feedback.v1"
MATCHER_VERSION = "class_commentary.student_name_matcher.v1"


def _canonical_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class ClassCommentaryFeedbackSchemaTest(unittest.TestCase):
    def test_matcher_normalizes_nfkc_and_whitespace_then_returns_unique_roster_order(self):
        roster = [
            {"student_id": 20, "student_name": "Ａ　同学"},
            {"student_id": 10, "student_name": "李 四"},
        ]

        eligible_ids = match_class_commentary_eligible_student_ids(
            transcript_text="李\t四先回答. A\n同学补充, 后面又点到Ａ 同学.",
            roster=roster,
        )

        self.assertEqual(eligible_ids, [20, 10])

    def test_matcher_rejects_exact_and_nfkc_equivalent_roster_names(self):
        cases = (
            ("exact", "张三", "张三"),
            ("nfkc", "Ａ　同学", "A 同学"),
        )
        for label, first_name, second_name in cases:
            with self.subTest(label=label):
                with self.assertRaises(ClassCommentaryStudentScopeError) as caught:
                    match_class_commentary_eligible_student_ids(
                        transcript_text=first_name,
                        roster=[
                            {"student_id": 1, "student_name": first_name},
                            {"student_id": 2, "student_name": second_name},
                        ],
                    )
                self.assertEqual(caught.exception.code, "student_roster_name_ambiguous")

    def test_matcher_uses_longest_non_overlapping_name_spans(self):
        roster = [
            {"student_id": 1, "student_name": "张三"},
            {"student_id": 2, "student_name": "张三丰"},
        ]

        only_long_name = match_class_commentary_eligible_student_ids(
            transcript_text="张三丰今天计算很稳定.",
            roster=roster,
        )
        separate_short_span = match_class_commentary_eligible_student_ids(
            transcript_text="张三丰先回答, 张三随后补充.",
            roster=roster,
        )

        self.assertEqual(only_long_name, [2])
        self.assertEqual(separate_short_span, [1, 2])

    def test_matcher_rejects_empty_eligible_scope(self):
        with self.assertRaises(ClassCommentaryStudentScopeError) as caught:
            match_class_commentary_eligible_student_ids(
                transcript_text="今天没有点名.",
                roster=[{"student_id": 1, "student_name": "张三"}],
            )

        self.assertEqual(caught.exception.code, "student_feedback_no_eligible_students")

    def test_canonicalization_reorders_items_and_derives_frozen_names(self):
        generation = self._generation()
        structured_feedback = {
            "schema_version": SCHEMA_VERSION,
            "items": [
                {"student_id": 22, "feedback_text": "需要继续写出验算过程.  \n"},
                {"student_id": 11, "feedback_text": "计算过程更稳定."},
            ],
        }

        result = canonicalize_class_commentary_structured_feedback(
            structured_feedback=structured_feedback,
            generation=generation,
        )

        expected_json = (
            '{"items":[{"feedback_text":"计算过程更稳定.","student_id":11},'
            '{"feedback_text":"需要继续写出验算过程.","student_id":22}],'
            '"schema_version":"class_commentary.student_feedback.v1"}'
        )
        self.assertEqual(
            result,
            {
                "feedback_schema_version": SCHEMA_VERSION,
                "structured_feedback_json": expected_json,
                "structured_feedback_hash": _sha256(expected_json),
                "derived_feedback_text": (
                    "张三:\n计算过程更稳定.\n\n"
                    "李四:\n需要继续写出验算过程."
                ),
                "student_feedback_items": [
                    {
                        "student_id": 11,
                        "student_name": "张三",
                        "feedback_text": "计算过程更稳定.",
                    },
                    {
                        "student_id": 22,
                        "student_name": "李四",
                        "feedback_text": "需要继续写出验算过程.",
                    },
                ],
            },
        )

    def test_read_envelope_treats_only_absent_inflight_payload_as_supported_read_only(self):
        for status in ("generating", "failed"):
            with self.subTest(status=status):
                generation = {**self._generation(), "status": status}
                envelope = build_class_commentary_feedback_read_envelope(
                    schema_version=SCHEMA_VERSION,
                    structured_json="",
                    stored_hash="",
                    derived_text="",
                    generation=generation,
                    allow_empty_generation_payload=True,
                )
                self.assertEqual(envelope["feedback_schema_status"], "supported")
                self.assertEqual(envelope["student_feedback_items"], [])
                self.assertFalse(envelope["writable"])

        succeeded = {**self._generation(), "status": "succeeded"}
        invalid = build_class_commentary_feedback_read_envelope(
            schema_version=SCHEMA_VERSION,
            structured_json="",
            stored_hash="",
            derived_text="",
            generation=succeeded,
            allow_empty_generation_payload=True,
        )
        self.assertEqual(invalid["feedback_schema_status"], "invalid")
        self.assertFalse(invalid["writable"])

    def test_read_envelope_rejects_tampered_generation_contract(self):
        generation = self._generation()
        canonical = canonicalize_class_commentary_structured_feedback(
            structured_feedback={
                "schema_version": SCHEMA_VERSION,
                "items": [
                    {"student_id": 11, "feedback_text": "计算过程更稳定."},
                    {"student_id": 22, "feedback_text": "验算步骤更完整."},
                ],
            },
            generation=generation,
        )
        mutations = (
            ("response_format", {"response_format_json": "{}"}),
            (
                "transcript_snapshot",
                {"confirmed_transcript_snapshot": "被篡改的转写"},
            ),
            (
                "roster_snapshot",
                {
                    "attending_roster_snapshot_json": _canonical_json([
                        {"student_id": 11, "student_name": "被改名学生"},
                        {"student_id": 22, "student_name": "李四"},
                        {"student_id": 33, "student_name": "王五"},
                    ])
                },
            ),
            ("skill_snapshot", {"skill_content_snapshot": "被篡改的 Skill"}),
        )
        for label, mutation in mutations:
            with self.subTest(label=label):
                envelope = build_class_commentary_feedback_read_envelope(
                    schema_version=SCHEMA_VERSION,
                    structured_json=canonical["structured_feedback_json"],
                    stored_hash=canonical["structured_feedback_hash"],
                    derived_text=canonical["derived_feedback_text"],
                    generation={**generation, **mutation},
                )

                self.assertEqual(envelope["feedback_schema_status"], "invalid")
                self.assertEqual(envelope["student_feedback_items"], [])
                self.assertFalse(envelope["writable"])

    def test_nonterminal_generation_with_result_payload_is_invalid(self):
        generation = self._generation()
        canonical = canonicalize_class_commentary_structured_feedback(
            structured_feedback={
                "schema_version": SCHEMA_VERSION,
                "items": [
                    {"student_id": 11, "feedback_text": "计算过程更稳定."},
                    {"student_id": 22, "feedback_text": "验算步骤更完整."},
                ],
            },
            generation=generation,
        )

        for status in ("generating", "failed"):
            with self.subTest(status=status):
                envelope = build_class_commentary_feedback_read_envelope(
                    schema_version=SCHEMA_VERSION,
                    structured_json=canonical["structured_feedback_json"],
                    stored_hash=canonical["structured_feedback_hash"],
                    derived_text=canonical["derived_feedback_text"],
                    generation={**generation, "status": status},
                    allow_empty_generation_payload=True,
                )

                self.assertEqual(envelope["feedback_schema_status"], "invalid")
                self.assertFalse(envelope["writable"])

    def test_validation_rejects_unknown_duplicate_coverage_empty_too_long_and_cross_student(self):
        valid_first = {"student_id": 11, "feedback_text": "计算过程更稳定."}
        valid_second = {"student_id": 22, "feedback_text": "验算步骤更完整."}
        cases = (
            (
                "unknown",
                "student_feedback_unknown_student",
                [valid_first, valid_second, {"student_id": 999, "feedback_text": "继续练习."}],
            ),
            (
                "duplicate",
                "student_feedback_duplicate_student",
                [valid_first, valid_first, valid_second],
            ),
            (
                "coverage",
                "student_feedback_coverage_mismatch",
                [valid_first],
            ),
            (
                "empty",
                "student_feedback_empty",
                [{"student_id": 11, "feedback_text": "  \n"}, valid_second],
            ),
            (
                "name_only",
                "student_feedback_empty",
                [{"student_id": 11, "feedback_text": "张三: ..."}, valid_second],
            ),
            (
                "too_long",
                "student_feedback_too_long",
                [{"student_id": 11, "feedback_text": "a" * 2001}, valid_second],
            ),
            (
                "cross_student",
                "student_feedback_cross_student_reference",
                [{"student_id": 11, "feedback_text": "需要像李四一样写出验算."}, valid_second],
            ),
        )
        for label, expected_code, items in cases:
            with self.subTest(label=label):
                with self.assertRaises(
                    ClassCommentaryStructuredFeedbackValidationError
                ) as caught:
                    canonicalize_class_commentary_structured_feedback(
                        structured_feedback={
                            "schema_version": SCHEMA_VERSION,
                            "items": items,
                        },
                        generation=self._generation(),
                    )
                self.assertEqual(caught.exception.code, expected_code)

    def test_validation_rejects_aggregate_text_over_30000_code_points(self):
        roster = [
            {"student_id": index, "student_name": f"学生{index:02d}"}
            for index in range(1, 17)
        ]
        generation = self._generation_for_roster(roster)

        with self.assertRaises(
            ClassCommentaryStructuredFeedbackValidationError
        ) as caught:
            canonicalize_class_commentary_structured_feedback(
                structured_feedback={
                    "schema_version": SCHEMA_VERSION,
                    "items": [
                        {
                            "student_id": item["student_id"],
                            "feedback_text": "a" * 1999,
                        }
                        for item in roster
                    ],
                },
                generation=generation,
            )

        self.assertEqual(caught.exception.code, "student_feedback_too_long")
        self.assertEqual(caught.exception.limit, 30000)

    def test_validation_wraps_lone_surrogate_as_stable_domain_error(self):
        generation = self._generation()
        payload = (
            '{"schema_version":"class_commentary.student_feedback.v1","items":['
            '{"student_id":11,"feedback_text":"\\ud800"},'
            '{"student_id":22,"feedback_text":"验算步骤更完整."}]}'
        )

        with self.assertRaises(
            ClassCommentaryStructuredFeedbackValidationError
        ) as caught:
            canonicalize_class_commentary_structured_feedback(
                structured_feedback=payload,
                generation=generation,
            )

        self.assertEqual(caught.exception.code, "structured_feedback_invalid")

    @staticmethod
    def _generation():
        roster = [
            {"student_id": 11, "student_name": "张三"},
            {"student_id": 22, "student_name": "李四"},
            {"student_id": 33, "student_name": "王五"},
        ]
        return ClassCommentaryFeedbackSchemaTest._generation_for_roster(
            roster,
            eligible_ids=[11, 22],
        )

    @staticmethod
    def _generation_for_roster(roster, eligible_ids=None):
        eligible_ids = eligible_ids or [item["student_id"] for item in roster]
        transcript_snapshot = " ".join(item["student_name"] for item in roster)
        roster_json = _canonical_json(roster)
        transcript_hash = _sha256(transcript_snapshot)
        roster_hash = _sha256(roster_json)
        skill_content_snapshot = "按课堂事实生成简洁反馈."
        scope_envelope = {
            "attending_roster_hash": roster_hash,
            "confirmed_transcript_hash": transcript_hash,
            "eligible_student_ids": eligible_ids,
            "student_mention_matcher_version": MATCHER_VERSION,
        }
        return {
            "feedback_schema_version": SCHEMA_VERSION,
            "attending_roster_snapshot_json": roster_json,
            "attending_roster_hash": roster_hash,
            "confirmed_transcript_snapshot": transcript_snapshot,
            "confirmed_transcript_hash": transcript_hash,
            "eligible_student_ids_json": _canonical_json(eligible_ids),
            "eligible_student_scope_hash": _sha256(_canonical_json(scope_envelope)),
            "student_mention_matcher_version": MATCHER_VERSION,
            "response_format_json": _canonical_json({"type": "json_object"}),
            "student_history_memory_mode": "disabled_v1",
            "prompt_version": "class-commentary-student-feedback-v1",
            "skill_content_snapshot": skill_content_snapshot,
            "skill_content_hash": _sha256(skill_content_snapshot),
        }


if __name__ == "__main__":
    unittest.main()
