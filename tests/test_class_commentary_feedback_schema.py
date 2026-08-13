import hashlib
import json
import unittest

import class_commentary

from class_commentary_feedback_schema import (
    CLASS_COMMENTARY_ATTENDING_ROSTER_SCOPE_V1,
    ClassCommentaryStudentScopeError,
    ClassCommentaryStructuredFeedbackValidationError,
    build_class_commentary_feedback_read_envelope,
    canonicalize_class_commentary_structured_feedback,
    match_class_commentary_eligible_student_ids,
    resolve_class_commentary_attending_roster_student_ids,
    validate_class_commentary_structured_generation_contract,
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

    def test_attending_roster_scope_returns_every_student_without_transcript_matching(self):
        roster = [
            {"student_id": 20, "student_name": "陈致丹"},
            {"student_id": 10, "student_name": "严岚"},
        ]

        eligible_ids = resolve_class_commentary_attending_roster_student_ids(
            roster=roster,
        )

        self.assertEqual(eligible_ids, [20, 10])

    def test_attending_roster_scope_rejects_empty_and_ambiguous_rosters(self):
        cases = (
            ("empty", [], "student_feedback_no_eligible_students"),
            (
                "ambiguous",
                [
                    {"student_id": 1, "student_name": "Ａ 同学"},
                    {"student_id": 2, "student_name": "A 同学"},
                ],
                "student_roster_name_ambiguous",
            ),
        )
        for label, roster, expected_code in cases:
            with self.subTest(label=label):
                with self.assertRaises(ClassCommentaryStudentScopeError) as caught:
                    resolve_class_commentary_attending_roster_student_ids(
                        roster=roster,
                    )
                self.assertEqual(caught.exception.code, expected_code)

    def test_structured_contract_accepts_v1_subset_and_v2_v3_full_roster_only(self):
        legacy_generation = self._generation()
        validate_class_commentary_structured_generation_contract(
            legacy_generation
        )

        roster = [
            {"student_id": 11, "student_name": "陈致丹"},
            {"student_id": 22, "student_name": "严岚"},
        ]
        full_ids = [11, 22]
        current_generation = self._generation_for_roster(
            roster,
            eligible_ids=full_ids,
        )
        current_generation.update(
            {
                "attending_roster_explicit": 1,
                "prompt_version": "class-commentary-student-feedback-v2",
                "student_mention_matcher_version": (
                    CLASS_COMMENTARY_ATTENDING_ROSTER_SCOPE_V1
                ),
            }
        )
        current_generation["eligible_student_scope_hash"] = _sha256(
            _canonical_json(
                {
                    "attending_roster_hash": current_generation[
                        "attending_roster_hash"
                    ],
                    "confirmed_transcript_hash": current_generation[
                        "confirmed_transcript_hash"
                    ],
                    "eligible_student_ids": full_ids,
                    "student_mention_matcher_version": (
                        CLASS_COMMENTARY_ATTENDING_ROSTER_SCOPE_V1
                    ),
                }
            )
        )
        validate_class_commentary_structured_generation_contract(
            current_generation
        )
        validate_class_commentary_structured_generation_contract(
            {
                **current_generation,
                "prompt_version": "class-commentary-student-feedback-v3",
            }
        )

        mutations = (
            (
                "v2_subset",
                {
                    "eligible_student_ids_json": _canonical_json([11]),
                },
            ),
            (
                "v2_legacy_matcher",
                {"student_mention_matcher_version": MATCHER_VERSION},
            ),
            (
                "v1_current_scope",
                {
                    "prompt_version": "class-commentary-student-feedback-v1",
                },
            ),
            ("v2_implicit_roster", {"attending_roster_explicit": 0}),
        )
        for label, mutation in mutations:
            with self.subTest(label=label):
                with self.assertRaises(ValueError):
                    validate_class_commentary_structured_generation_contract(
                        {**current_generation, **mutation}
                    )

    def test_canonicalization_reorders_items_and_derives_frozen_names(self):
        generation = self._generation_for_roster(
            [
                {"student_id": 11, "student_name": "张三"},
                {"student_id": 22, "student_name": "李四"},
            ]
        )
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

    def test_batch_v4_requires_complete_scoped_graph_reference_map(self):
        generation = self._batch_generation_for_roster(
            [
                {"student_id": 11, "student_name": "张三"},
                {"student_id": 22, "student_name": "李四"},
            ],
            evidence_by_student={
                11: ["张三今天计算过程稳定."],
                22: ["李四今天验算步骤完整."],
            },
        )
        payload = {
            "schema_version": SCHEMA_VERSION,
            "items": [
                {
                    "student_id": 11,
                    "feedback_text": "张三, 今天计算过程更稳定, 整体计算状态不错🌱.",
                },
                {
                    "student_id": 22,
                    "feedback_text": "李四, 今天验算步骤更完整, 整体验算状态不错✨.",
                },
            ],
            "used_graph_evidence_refs_by_student": [
                {"student_id": 11, "evidence_refs": ["graph-11"]},
                {"student_id": 22, "evidence_refs": []},
            ],
        }
        result = canonicalize_class_commentary_structured_feedback(
            structured_feedback=payload,
            generation=generation,
            allowed_graph_evidence_refs_by_student={
                11: ["graph-11"],
                22: ["graph-22"],
            },
            require_batch_graph_refs=True,
        )
        self.assertEqual(
            result["used_graph_evidence_refs_by_student"],
            {11: ["graph-11"], 22: []},
        )
        self.assertNotIn(
            "used_graph_evidence_refs_by_student",
            result["structured_feedback_json"],
        )

        invalid_payloads = (
            {**payload, "used_graph_evidence_refs_by_student": payload["used_graph_evidence_refs_by_student"][:1]},
            {
                **payload,
                "used_graph_evidence_refs_by_student": [
                    {"student_id": 11, "evidence_refs": ["graph-22"]},
                    {"student_id": 22, "evidence_refs": []},
                ],
            },
        )
        for invalid in invalid_payloads:
            with self.subTest(invalid=invalid):
                with self.assertRaises(
                    ClassCommentaryStructuredFeedbackValidationError
                ):
                    canonicalize_class_commentary_structured_feedback(
                        structured_feedback=invalid,
                        generation=generation,
                        allowed_graph_evidence_refs_by_student={
                            11: ["graph-11"],
                            22: ["graph-22"],
                        },
                        require_batch_graph_refs=True,
                    )

    def test_batch_v4_initial_output_preserves_normal_skill_emoji_style(self):
        roster = [
            {"student_id": 11, "student_name": "张三"},
            {"student_id": 22, "student_name": "李四"},
        ]
        generation = self._batch_generation_for_roster(
            roster,
            evidence_by_student={
                11: ["张三今天计算过程稳定."],
                22: ["李四今天验算步骤完整."],
            },
            skill_content="先肯定孩子的进步🌱, 再用✨自然收尾.",
        )
        payload = self._batch_payload(
            {
                11: "张三, 今天计算过程很稳定, 整体计算状态不错🌱.",
                22: "李四, 今天验算步骤很完整, 整体验算状态不错.",
            }
        )

        with self.assertRaises(
            ClassCommentaryStructuredFeedbackValidationError
        ) as caught:
            canonicalize_class_commentary_structured_feedback(
                structured_feedback=payload,
                generation=generation,
                allowed_graph_evidence_refs_by_student={11: [], 22: []},
                require_batch_graph_refs=True,
            )

        self.assertEqual(caught.exception.code, "student_feedback_missing_skill_emoji")
        self.assertEqual(caught.exception.student_id, 22)

        payload["items"][1]["feedback_text"] += "✨"
        accepted = canonicalize_class_commentary_structured_feedback(
            structured_feedback=payload,
            generation=generation,
            allowed_graph_evidence_refs_by_student={11: [], 22: []},
            require_batch_graph_refs=True,
        )
        self.assertEqual(len(accepted["student_feedback_items"]), 2)

    def test_batch_v4_preserves_wechat_text_emoji_style(self):
        roster = [{"student_id": 11, "student_name": "张三"}]
        generation = self._batch_generation_for_roster(
            roster,
            evidence_by_student={11: ["张三今天计算过程稳定."]},
            skill_content="先用[呲牙]自然肯定, 再用[破涕为笑]温和收尾.",
        )
        without_emoji = self._batch_payload(
            {11: "张三, 今天计算过程很稳定, 整体计算状态不错."}
        )

        with self.assertRaises(
            ClassCommentaryStructuredFeedbackValidationError
        ) as caught:
            canonicalize_class_commentary_structured_feedback(
                structured_feedback=without_emoji,
                generation=generation,
                allowed_graph_evidence_refs_by_student={11: []},
                require_batch_graph_refs=True,
            )

        self.assertEqual(
            caught.exception.code,
            "student_feedback_missing_skill_emoji",
        )
        accepted = canonicalize_class_commentary_structured_feedback(
            structured_feedback=self._batch_payload(
                {
                    11: (
                        "张三, 今天计算过程很稳定, "
                        "整体计算状态不错[呲牙]."
                    )
                }
            ),
            generation=generation,
            allowed_graph_evidence_refs_by_student={11: []},
            require_batch_graph_refs=True,
        )
        self.assertEqual(len(accepted["student_feedback_items"]), 1)

    def test_batch_v4_supports_real_wechat_style_tokens_but_not_media_markers(self):
        roster = [{"student_id": 11, "student_name": "张三"}]
        for token in ("握手", "爱心", "合十"):
            with self.subTest(token=token):
                generation = self._batch_generation_for_roster(
                    roster,
                    evidence_by_student={11: ["张三今天计算过程稳定."]},
                    skill_content=f"常用[{token}]肯定, 再用[{token}]收尾.",
                )
                accepted = canonicalize_class_commentary_structured_feedback(
                    structured_feedback=self._batch_payload(
                        {
                            11: (
                                "张三, 今天计算过程很稳定, "
                                f"整体计算状态不错[{token}]."
                            )
                        }
                    ),
                    generation=generation,
                    allowed_graph_evidence_refs_by_student={11: []},
                    require_batch_graph_refs=True,
                )
                self.assertEqual(len(accepted["student_feedback_items"]), 1)

        generation = self._batch_generation_for_roster(
            roster,
            evidence_by_student={11: ["张三今天计算过程稳定."]},
            skill_content="示例含[Photo]和[压缩内容], 但不要求表情.",
        )
        accepted = canonicalize_class_commentary_structured_feedback(
            structured_feedback=self._batch_payload(
                {11: "张三, 今天计算过程很稳定, 整体计算状态不错."}
            ),
            generation=generation,
            allowed_graph_evidence_refs_by_student={11: []},
            require_batch_graph_refs=True,
        )
        self.assertEqual(len(accepted["student_feedback_items"]), 1)

    def test_batch_v4_recognizes_cao_skill_wechat_tokens(self):
        roster = [{"student_id": 11, "student_name": "张三"}]
        for token in ("月亮", "哇", "转圈", "社会社会", "好的"):
            with self.subTest(token=token):
                generation = self._batch_generation_for_roster(
                    roster,
                    evidence_by_student={11: ["张三今天计算过程稳定."]},
                    skill_content=f"常用[{token}]提示重点, 再用[{token}]缓和语气.",
                )
                with self.assertRaises(
                    ClassCommentaryStructuredFeedbackValidationError
                ) as caught:
                    canonicalize_class_commentary_structured_feedback(
                        structured_feedback=self._batch_payload(
                            {
                                11: (
                                    "张三, 今天计算过程比较稳定, "
                                    "思路也表达得很清楚."
                                )
                            }
                        ),
                        generation=generation,
                        allowed_graph_evidence_refs_by_student={11: []},
                        require_batch_graph_refs=True,
                    )
                self.assertEqual(
                    caught.exception.code,
                    "student_feedback_missing_skill_emoji",
                )

                accepted = canonicalize_class_commentary_structured_feedback(
                    structured_feedback=self._batch_payload(
                        {
                            11: (
                                "张三, 今天计算过程比较稳定, "
                                f"思路也表达得很清楚[{token}]."
                            )
                        }
                    ),
                    generation=generation,
                    allowed_graph_evidence_refs_by_student={11: []},
                    require_batch_graph_refs=True,
                )
                self.assertEqual(len(accepted["student_feedback_items"]), 1)

    def test_batch_v4_explicit_occasional_emoji_style_preserves_one_classwide(self):
        roster = [{"student_id": 11, "student_name": "张三"}]
        generation = self._batch_generation_for_roster(
            roster,
            evidence_by_student={11: ["张三今天课堂参与积极."]},
            skill_content=(
                "表情只偶尔使用, 轻量即可, 不要过用. "
                "示例可用[呲牙], 也可用[玫瑰]."
            ),
        )

        feedback = "张三, 今天课堂参与很积极, 整体状态值得肯定."
        with self.assertRaises(
            ClassCommentaryStructuredFeedbackValidationError
        ) as caught:
            canonicalize_class_commentary_structured_feedback(
                structured_feedback=self._batch_payload({11: feedback}),
                generation=generation,
                allowed_graph_evidence_refs_by_student={11: []},
                require_batch_graph_refs=True,
            )
        self.assertEqual(caught.exception.code, "batch_feedback_missing_skill_emoji")

        accepted = canonicalize_class_commentary_structured_feedback(
            structured_feedback=self._batch_payload({11: feedback + "[玫瑰]"}),
            generation=generation,
            allowed_graph_evidence_refs_by_student={11: []},
            require_batch_graph_refs=True,
        )
        self.assertEqual(len(accepted["student_feedback_items"]), 1)

    def test_batch_v4_conditional_he_skill_emoji_does_not_force_every_student(self):
        roster = [
            {"student_id": 11, "student_name": "张三"},
            {"student_id": 12, "student_name": "李四"},
        ]
        generation = self._batch_generation_for_roster(
            roster,
            evidence_by_student={
                11: ["张三今天课堂参与积极."],
                12: ["李四今天遇到的题目难度较高."],
            },
            skill_content=(
                "表情占位符:\n"
                "- `[偷笑]` 可放在难题说明后, 缓和难度感."
            ),
        )

        accepted = canonicalize_class_commentary_structured_feedback(
            structured_feedback=self._batch_payload(
                {
                    11: "张三, 今天课堂参与很积极, 整体状态值得肯定.",
                    12: "李四, 今天遇到的题目难度较高, 但你一直在认真尝试[偷笑].",
                }
            ),
            generation=generation,
            allowed_graph_evidence_refs_by_student={11: [], 12: []},
            require_batch_graph_refs=True,
        )

        self.assertEqual(len(accepted["student_feedback_items"]), 2)

    def test_batch_v4_normal_emoji_style_requires_selected_skill_token_family(self):
        roster = [{"student_id": 11, "student_name": "张三"}]
        generation = self._batch_generation_for_roster(
            roster,
            evidence_by_student={11: ["张三今天课堂参与积极."]},
            skill_content="表情占位符常用[呲牙]肯定, 再用[玫瑰]鼓励.",
        )
        invalid_feedback = (
            "张三, 今天课堂参与很积极, 整体状态值得肯定{emoji}."
        )
        for label, emoji in (
            ("wrong_colleague_token", "[强]"),
            ("unlisted_unicode_emoji", "✨"),
        ):
            with self.subTest(label=label):
                with self.assertRaises(
                    ClassCommentaryStructuredFeedbackValidationError
                ) as caught:
                    canonicalize_class_commentary_structured_feedback(
                        structured_feedback=self._batch_payload(
                            {11: invalid_feedback.format(emoji=emoji)}
                        ),
                        generation=generation,
                        allowed_graph_evidence_refs_by_student={11: []},
                        require_batch_graph_refs=True,
                    )
                self.assertEqual(
                    caught.exception.code,
                    "student_feedback_missing_skill_emoji",
                )

        accepted = canonicalize_class_commentary_structured_feedback(
            structured_feedback=self._batch_payload(
                {
                    11: (
                        "张三, 今天课堂参与很积极, "
                        "整体状态值得肯定[呲牙]."
                    )
                }
            ),
            generation=generation,
            allowed_graph_evidence_refs_by_student={11: []},
            require_batch_graph_refs=True,
        )
        self.assertEqual(len(accepted["student_feedback_items"]), 1)

    def test_batch_v4_frequent_emoji_style_scales_with_evidence_richness(self):
        roster = [{"student_id": 11, "student_name": "张三"}]
        skill_content = (
            "emoji 使用频繁. 常用[呲牙]肯定表现, 用[玫瑰]鼓励行动."
        )
        sparse_generation = self._batch_generation_for_roster(
            roster,
            evidence_by_student={11: ["张三今天课堂参与积极."]},
            skill_content=skill_content,
        )
        sparse_without_emoji = (
            "张三, 今天课堂参与很积极, 整体状态值得肯定."
        )
        with self.assertRaises(
            ClassCommentaryStructuredFeedbackValidationError
        ) as caught:
            canonicalize_class_commentary_structured_feedback(
                structured_feedback=self._batch_payload(
                    {11: sparse_without_emoji}
                ),
                generation=sparse_generation,
                allowed_graph_evidence_refs_by_student={11: []},
                require_batch_graph_refs=True,
            )
        self.assertEqual(
            caught.exception.code,
            "student_feedback_missing_skill_emoji",
        )

        sparse_accepted = canonicalize_class_commentary_structured_feedback(
            structured_feedback=self._batch_payload(
                {11: sparse_without_emoji + "[呲牙]"}
            ),
            generation=sparse_generation,
            allowed_graph_evidence_refs_by_student={11: []},
            require_batch_graph_refs=True,
        )
        self.assertEqual(len(sparse_accepted["student_feedback_items"]), 1)

        rich_generation = self._batch_generation_for_roster(
            roster,
            evidence_by_student={
                11: [
                    "张三今天能准确列出方程.",
                    "张三移项时漏写了负号.",
                ]
            },
            skill_content=skill_content,
        )
        rich_feedback_with_one_emoji = (
            "张三, 今天列方程时思路清楚, "
            "能够准确抓住题目里的数量关系[呲牙].\n\n"
            "移项环节漏写了负号, 课后请把这道错题重做一遍, "
            "并在每次移项后圈出负号检查."
        )
        with self.assertRaises(
            ClassCommentaryStructuredFeedbackValidationError
        ) as caught:
            canonicalize_class_commentary_structured_feedback(
                structured_feedback=self._batch_payload(
                    {11: rich_feedback_with_one_emoji}
                ),
                generation=rich_generation,
                allowed_graph_evidence_refs_by_student={11: []},
                require_batch_graph_refs=True,
            )
        self.assertEqual(
            caught.exception.code,
            "student_feedback_missing_skill_emoji",
        )

        rich_accepted = canonicalize_class_commentary_structured_feedback(
            structured_feedback=self._batch_payload(
                {11: rich_feedback_with_one_emoji + "[玫瑰]"}
            ),
            generation=rich_generation,
            allowed_graph_evidence_refs_by_student={11: []},
            require_batch_graph_refs=True,
        )
        self.assertEqual(len(rich_accepted["student_feedback_items"]), 1)

    def test_batch_v4_duplicated_package_example_does_not_promote_emoji_density(self):
        roster = [{"student_id": 11, "student_name": "张三"}]
        duplicated_example = "示例: 今天课堂参与不错[呲牙]."
        generation = self._batch_generation_for_roster(
            roster,
            evidence_by_student={11: ["张三今天课堂参与积极."]},
            skill_content=(
                f"## SKILL.md\n{duplicated_example}\n\n"
                f"## work.md\n{duplicated_example}"
            ),
        )

        accepted = canonicalize_class_commentary_structured_feedback(
            structured_feedback=self._batch_payload(
                {11: "张三, 今天课堂参与很积极, 整体状态值得肯定."}
            ),
            generation=generation,
            allowed_graph_evidence_refs_by_student={11: []},
            require_batch_graph_refs=True,
        )

        self.assertEqual(len(accepted["student_feedback_items"]), 1)

    def test_batch_v4_occasional_emoji_style_requires_one_classwide_skill_token(self):
        roster = [
            {"student_id": 11, "student_name": "张三"},
            {"student_id": 12, "student_name": "李四"},
        ]
        generation = self._batch_generation_for_roster(
            roster,
            evidence_by_student={
                11: ["张三今天课堂参与积极."],
                12: ["李四今天计算步骤完整."],
            },
            skill_content=(
                "表情是轻量缓冲工具, 整班至少保留一个同体系表情. "
                "可用[月亮]提醒重点, "
                "不要堆满, 也不要每句都放."
            ),
        )
        feedback_by_student = {
            11: "张三, 今天课堂参与很积极, 整体状态值得肯定.",
            12: "李四, 今天计算步骤写得完整, 做题状态很稳.",
        }

        with self.assertRaises(
            ClassCommentaryStructuredFeedbackValidationError
        ) as caught:
            canonicalize_class_commentary_structured_feedback(
                structured_feedback=self._batch_payload(feedback_by_student),
                generation=generation,
                allowed_graph_evidence_refs_by_student={11: [], 12: []},
                require_batch_graph_refs=True,
            )
        self.assertEqual(
            caught.exception.code,
            "batch_feedback_missing_skill_emoji",
        )

        feedback_by_student[12] += "[月亮]"
        accepted = canonicalize_class_commentary_structured_feedback(
            structured_feedback=self._batch_payload(feedback_by_student),
            generation=generation,
            allowed_graph_evidence_refs_by_student={11: [], 12: []},
            require_batch_graph_refs=True,
        )
        self.assertEqual(len(accepted["student_feedback_items"]), 2)

    def test_batch_v4_occasional_emoji_style_without_concrete_token_stays_optional(self):
        roster = [{"student_id": 11, "student_name": "张三"}]
        generation = self._batch_generation_for_roster(
            roster,
            evidence_by_student={11: ["张三今天课堂参与积极."]},
            skill_content="偶尔使用笑脸缓和语气, 但没有可确认的具体表情 token.",
        )

        accepted = canonicalize_class_commentary_structured_feedback(
            structured_feedback=self._batch_payload(
                {11: "张三, 今天课堂参与很积极, 整体状态值得肯定."}
            ),
            generation=generation,
            allowed_graph_evidence_refs_by_student={11: []},
            require_batch_graph_refs=True,
        )
        self.assertEqual(len(accepted["student_feedback_items"]), 1)

    def test_batch_v4_sparse_initial_feedback_rejects_generic_empty_calories(self):
        roster = [{"student_id": 11, "student_name": "张三"}]
        generation = self._batch_generation_for_roster(
            roster,
            evidence_by_student={11: ["张三今天课堂参与积极."]},
        )

        with self.assertRaises(ClassCommentaryStructuredFeedbackValidationError):
            canonicalize_class_commentary_structured_feedback(
                structured_feedback=self._batch_payload(
                    {11: "张三, 继续努力, 相信你会越来越好."}
                ),
                generation=generation,
                allowed_graph_evidence_refs_by_student={11: []},
                require_batch_graph_refs=True,
            )

    def test_batch_v4_sparse_initial_feedback_requires_twelve_lexical_characters(self):
        roster = [{"student_id": 11, "student_name": "张三"}]
        generation = self._batch_generation_for_roster(
            roster,
            evidence_by_student={11: ["张三今天课堂参与积极."]},
        )

        with self.assertRaises(
            ClassCommentaryStructuredFeedbackValidationError
        ) as caught:
            canonicalize_class_commentary_structured_feedback(
                structured_feedback=self._batch_payload(
                    {11: "张三, 今天课堂表现积极."}
                ),
                generation=generation,
                allowed_graph_evidence_refs_by_student={11: []},
                require_batch_graph_refs=True,
            )
        self.assertEqual(caught.exception.code, "student_feedback_too_short")
        self.assertEqual(caught.exception.limit, 12)

        accepted = canonicalize_class_commentary_structured_feedback(
            structured_feedback=self._batch_payload(
                {11: "张三, 今天课堂参与积极, 整体状态值得肯定."}
            ),
            generation=generation,
            allowed_graph_evidence_refs_by_student={11: []},
            require_batch_graph_refs=True,
        )
        self.assertEqual(len(accepted["student_feedback_items"]), 1)

    def test_batch_v4_single_long_evidence_requires_substantive_paragraphs(self):
        roster = [{"student_id": 11, "student_name": "张三"}]
        generation = self._batch_generation_for_roster(
            roster,
            evidence_by_student={
                11: [
                    "张三今天能够准确列出方程并解释数量关系但在移项和验算时仍需检查负号与等号两侧是否同步变化"
                ]
            },
        )
        with self.assertRaises(
            ClassCommentaryStructuredFeedbackValidationError
        ) as caught:
            canonicalize_class_commentary_structured_feedback(
                structured_feedback=self._batch_payload(
                    {
                        11: (
                            "张三, 今天列方程时思路比较清楚, 也能解释数量关系, "
                            "但移项和验算仍需检查负号与等号两侧变化, "
                            "课后请重做错题并逐步核对."
                        )
                    }
                ),
                generation=generation,
                allowed_graph_evidence_refs_by_student={11: []},
                require_batch_graph_refs=True,
            )
        self.assertEqual(
            caught.exception.code,
            "student_feedback_paragraph_count_invalid",
        )

    def test_batch_v4_single_explicit_emoji_is_classwide_while_symbols_are_ignored(self):
        roster = [{"student_id": 11, "student_name": "张三"}]
        for label, skill_content in (
            ("single_emoji", "只在结尾偶尔用一次🌱."),
            ("markdown_symbols", "# 标题\n* 先肯定\n- 再建议\n© 课程组"),
        ):
            with self.subTest(label=label):
                generation = self._batch_generation_for_roster(
                    roster,
                    evidence_by_student={11: ["张三今天计算过程稳定."]},
                    skill_content=skill_content,
                )
                feedback = "张三, 今天计算过程很稳定, 整体计算状态不错."
                if label == "single_emoji":
                    with self.assertRaises(
                        ClassCommentaryStructuredFeedbackValidationError
                    ) as caught:
                        canonicalize_class_commentary_structured_feedback(
                            structured_feedback=self._batch_payload({11: feedback}),
                            generation=generation,
                            allowed_graph_evidence_refs_by_student={11: []},
                            require_batch_graph_refs=True,
                        )
                    self.assertEqual(
                        caught.exception.code,
                        "batch_feedback_missing_skill_emoji",
                    )
                    feedback += "🌱"
                accepted = canonicalize_class_commentary_structured_feedback(
                    structured_feedback=self._batch_payload({11: feedback}),
                    generation=generation,
                    allowed_graph_evidence_refs_by_student={11: []},
                    require_batch_graph_refs=True,
                )
                self.assertEqual(len(accepted["student_feedback_items"]), 1)

    def test_batch_v4_rich_evidence_requires_substantive_paragraphs_and_action(self):
        roster = [{"student_id": 11, "student_name": "张三"}]
        generation = self._batch_generation_for_roster(
            roster,
            evidence_by_student={
                11: [
                    "张三今天能准确列出方程.",
                    "张三移项时漏写了负号.",
                ]
            },
        )
        invalid_cases = (
            (
                "one_paragraph",
                "student_feedback_paragraph_count_invalid",
                "张三, 今天列方程很准确, 移项时需要注意负号. 课后请重做这道错题并圈出负号.",
            ),
            (
                "too_short",
                "student_feedback_too_short",
                "张三, 列式不错.\n\n课后重做错题.",
            ),
            (
                "generic_advice",
                "student_feedback_missing_next_action",
                "张三, 今天列方程时思路清楚, 能够准确抓住题目中的数量关系.\n\n移项环节漏写负号, 这个细节还需要继续注意, 相信你会越来越稳.",
            ),
        )
        for label, expected_code, feedback_text in invalid_cases:
            with self.subTest(label=label):
                with self.assertRaises(
                    ClassCommentaryStructuredFeedbackValidationError
                ) as caught:
                    canonicalize_class_commentary_structured_feedback(
                        structured_feedback=self._batch_payload({11: feedback_text}),
                        generation=generation,
                        allowed_graph_evidence_refs_by_student={11: []},
                        require_batch_graph_refs=True,
                    )
                self.assertEqual(caught.exception.code, expected_code)

        accepted = canonicalize_class_commentary_structured_feedback(
            structured_feedback=self._batch_payload(
                {
                    11: (
                        "张三, 今天列方程时思路清楚, 能够准确抓住题目里的数量关系.\n\n"
                        "移项环节漏写了负号, 课后请把这道错题重做一遍, 并在每次移项后圈出负号检查."
                    )
                }
            ),
            generation=generation,
            allowed_graph_evidence_refs_by_student={11: []},
            require_batch_graph_refs=True,
        )
        self.assertEqual(len(accepted["student_feedback_items"]), 1)

    def test_batch_v4_accepts_concrete_chinese_actions_from_real_skill_styles(self):
        roster = [{"student_id": 11, "student_name": "张三"}]
        generation = self._batch_generation_for_roster(
            roster,
            evidence_by_student={
                11: [
                    "张三今天能准确列出方程.",
                    "张三移项时漏写了负号.",
                ]
            },
        )
        actions = (
            "明天我会重点看",
            "后面我会专门拿出来讲",
            "回家把这道题再做一遍",
            "需要把概念重新看几遍记一记",
            "下次把过程补完整",
        )

        for action in actions:
            with self.subTest(action=action):
                accepted = canonicalize_class_commentary_structured_feedback(
                    structured_feedback=self._batch_payload(
                        {
                            11: (
                                "张三, 今天列方程时能够准确抓住数量关系, "
                                "整体思路比较清楚.\n\n"
                                f"移项时漏写了负号, {action}."
                            )
                        }
                    ),
                    generation=generation,
                    allowed_graph_evidence_refs_by_student={11: []},
                    require_batch_graph_refs=True,
                )
                self.assertEqual(len(accepted["student_feedback_items"]), 1)

    def test_batch_v4_future_sounding_encouragement_is_not_a_concrete_action(self):
        roster = [{"student_id": 11, "student_name": "张三"}]
        generation = self._batch_generation_for_roster(
            roster,
            evidence_by_student={
                11: [
                    "张三今天能准确列出方程.",
                    "张三移项时漏写了负号.",
                ]
            },
        )

        with self.assertRaises(
            ClassCommentaryStructuredFeedbackValidationError
        ) as caught:
            canonicalize_class_commentary_structured_feedback(
                structured_feedback=self._batch_payload(
                    {
                        11: (
                            "张三, 今天列方程时能够准确抓住数量关系, "
                            "整体思路比较清楚.\n\n"
                            "移项时漏写了负号, 后面继续努力, 相信你会越来越稳."
                        )
                    }
                ),
                generation=generation,
                allowed_graph_evidence_refs_by_student={11: []},
                require_batch_graph_refs=True,
            )

        self.assertEqual(caught.exception.code, "student_feedback_missing_next_action")

    def test_batch_v4_problem_needs_action_but_low_information_praise_stays_short(self):
        roster = [
            {"student_id": 11, "student_name": "张三"},
            {"student_id": 22, "student_name": "李四"},
        ]
        generation = self._batch_generation_for_roster(
            roster,
            evidence_by_student={
                11: ["张三今天计算时需要检查符号."],
                22: ["李四今天课堂参与积极."],
            },
        )
        payload = self._batch_payload(
            {
                11: (
                    "张三, 今天计算时符号还需要检查, "
                    "这个问题仍然需要注意."
                ),
                22: (
                    "李四, 今天课堂参与很积极, "
                    "整体参与状态值得肯定."
                ),
            }
        )

        with self.assertRaises(
            ClassCommentaryStructuredFeedbackValidationError
        ) as caught:
            canonicalize_class_commentary_structured_feedback(
                structured_feedback=payload,
                generation=generation,
                allowed_graph_evidence_refs_by_student={11: [], 22: []},
                require_batch_graph_refs=True,
            )
        self.assertEqual(caught.exception.code, "student_feedback_missing_next_action")
        self.assertEqual(caught.exception.student_id, 11)

        payload["items"][0]["feedback_text"] += " 下次计算后请逐项检查每个符号."
        accepted = canonicalize_class_commentary_structured_feedback(
            structured_feedback=payload,
            generation=generation,
            allowed_graph_evidence_refs_by_student={11: [], 22: []},
            require_batch_graph_refs=True,
        )
        self.assertEqual(len(accepted["student_feedback_items"]), 2)

    def test_batch_v4_quality_gate_applies_only_to_initial_model_completion(self):
        generation = self._batch_generation_for_roster(
            [{"student_id": 11, "student_name": "张三"}],
            evidence_by_student={
                11: [
                    "张三今天能准确列出方程.",
                    "张三移项时漏写了负号.",
                ]
            },
            skill_content="常用🌱鼓励, 再用✨收尾.",
        )
        payload = self._batch_payload({11: "张三, 继续努力."})

        accepted = canonicalize_class_commentary_structured_feedback(
            structured_feedback=payload,
            generation=generation,
            allowed_graph_evidence_refs_by_student={11: []},
            require_batch_graph_refs=False,
        )

        self.assertEqual(accepted["student_feedback_items"][0]["feedback_text"], "张三, 继续努力.")

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

    def test_cross_student_validation_uses_longest_non_overlapping_name_spans(self):
        generation = self._generation_for_roster([
            {"student_id": 1, "student_name": "张三"},
            {"student_id": 2, "student_name": "张三丰"},
        ])
        accepted = canonicalize_class_commentary_structured_feedback(
            structured_feedback={
                "schema_version": SCHEMA_VERSION,
                "items": [
                    {"student_id": 1, "feedback_text": "张三今天能主动验算."},
                    {"student_id": 2, "feedback_text": "张三丰今天计算也很认真."},
                ],
            },
            generation=generation,
        )
        self.assertEqual(
            [item["student_id"] for item in accepted["student_feedback_items"]],
            [1, 2],
        )

        with self.assertRaises(
            ClassCommentaryStructuredFeedbackValidationError
        ) as caught:
            canonicalize_class_commentary_structured_feedback(
                structured_feedback={
                    "schema_version": SCHEMA_VERSION,
                    "items": [
                        {"student_id": 1, "feedback_text": "张三丰今天计算很认真."},
                        {"student_id": 2, "feedback_text": "张三丰今天也有进步."},
                    ],
                },
                generation=generation,
            )
        self.assertEqual(
            caught.exception.code,
            "student_feedback_cross_student_reference",
        )

    def test_v5_rejects_non_attending_course_roster_name_in_feedback(self):
        attending_roster = [
            {"student_id": 1, "student_name": "刘鹏鹏"},
            {"student_id": 2, "student_name": "张玉坤"},
        ]
        generation = self._generation_for_roster(attending_roster)
        course_roster = [
            *attending_roster,
            {"student_id": 3, "student_name": "王小明"},
        ]
        course_roster_json = _canonical_json(course_roster)
        generation.update(
            {
                "prompt_version": (
                    class_commentary.CLASS_COMMENTARY_BATCH_ISOLATED_PROMPT_VERSION_V5
                ),
                "student_mention_matcher_version": (
                    "class_commentary.student_evidence_fail_closed.v2"
                ),
                "student_history_memory_mode": "batch_isolated_v3",
                "attending_roster_explicit": 1,
                "privacy_roster_snapshot_json": course_roster_json,
                "privacy_roster_hash": _sha256(course_roster_json),
            }
        )
        generation["eligible_student_scope_hash"] = _sha256(
            _canonical_json(
                {
                    "attending_roster_hash": generation[
                        "attending_roster_hash"
                    ],
                    "confirmed_transcript_hash": generation[
                        "confirmed_transcript_hash"
                    ],
                    "eligible_student_ids": [1, 2],
                    "student_mention_matcher_version": (
                        "class_commentary.student_evidence_fail_closed.v2"
                    ),
                }
            )
        )

        with self.assertRaises(
            ClassCommentaryStructuredFeedbackValidationError
        ) as caught:
            canonicalize_class_commentary_structured_feedback(
                structured_feedback={
                    "schema_version": SCHEMA_VERSION,
                    "items": [
                        {
                            "student_id": 1,
                            "feedback_text": "刘鹏鹏, 你今天比王小明写得更完整.",
                        },
                        {
                            "student_id": 2,
                            "feedback_text": "张玉坤, 你今天能主动验算.",
                        },
                    ],
                },
                generation=generation,
            )
        self.assertEqual(
            caught.exception.code,
            "student_feedback_cross_student_reference",
        )

        tampered = dict(generation)
        tampered["privacy_roster_snapshot_json"] = _canonical_json(
            [*attending_roster, {"student_id": 4, "student_name": "篡改姓名"}]
        )
        with self.assertRaises(ValueError):
            validate_class_commentary_structured_generation_contract(tampered)

        missing = dict(generation)
        missing["privacy_roster_snapshot_json"] = ""
        missing["privacy_roster_hash"] = ""
        with self.assertRaises(ValueError):
            validate_class_commentary_structured_generation_contract(missing)

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
    def _batch_payload(feedback_by_student):
        return {
            "schema_version": SCHEMA_VERSION,
            "items": [
                {"student_id": student_id, "feedback_text": feedback_text}
                for student_id, feedback_text in feedback_by_student.items()
            ],
            "used_graph_evidence_refs_by_student": [
                {"student_id": student_id, "evidence_refs": []}
                for student_id in feedback_by_student
            ],
        }

    @staticmethod
    def _batch_generation_for_roster(
        roster,
        *,
        evidence_by_student,
        skill_content="按课堂事实直接沟通, 给出具体建议.",
    ):
        generation = ClassCommentaryFeedbackSchemaTest._generation_for_roster(roster)
        generation.update(
            {
                "prompt_version": "class-commentary-student-feedback-batch-isolated-v4",
                "student_mention_matcher_version": (
                    CLASS_COMMENTARY_ATTENDING_ROSTER_SCOPE_V1
                ),
                "student_history_memory_mode": "batch_isolated_v3",
                "attending_roster_explicit": 1,
                "skill_content_snapshot": skill_content,
                "skill_content_hash": _sha256(skill_content),
            }
        )
        student_ids = [item["student_id"] for item in roster]
        generation["eligible_student_scope_hash"] = _sha256(
            _canonical_json(
                {
                    "attending_roster_hash": generation["attending_roster_hash"],
                    "confirmed_transcript_hash": generation[
                        "confirmed_transcript_hash"
                    ],
                    "eligible_student_ids": student_ids,
                    "student_mention_matcher_version": (
                        CLASS_COMMENTARY_ATTENDING_ROSTER_SCOPE_V1
                    ),
                }
            )
        )
        partitions = []
        for item in roster:
            student_id = item["student_id"]
            fragments = [
                {
                    "text": text,
                    "text_hash": _sha256(text),
                }
                for text in evidence_by_student[student_id]
            ]
            partitions.append(
                {
                    "student_id": student_id,
                    "current_evidence_snapshot": {"fragments": fragments},
                }
            )
        memory_context = {
            "schema_version": "class_commentary.batch_isolated_context.v1",
            "student_history_memory_mode": "batch_isolated_v3",
            "student_contexts_by_id": partitions,
        }
        generation["memory_context_snapshot_json"] = _canonical_json(memory_context)
        generation["memory_context_hash"] = _sha256(
            generation["memory_context_snapshot_json"]
        )
        return generation

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
