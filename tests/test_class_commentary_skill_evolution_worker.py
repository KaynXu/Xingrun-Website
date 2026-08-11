import json
import unittest
from unittest.mock import Mock

from class_commentary_memory_jobs import (
    _replace_active_skill_content,
    process_class_commentary_skill_candidate_build,
)


ENABLED_CONFIG = {
    "class_commentary_memory_enabled": True,
    "skill_evolution_build_timeout": 300,
}


def _prompt_payload(base_content):
    return {
        "messages": [
            {"role": "system", "content": "system"},
            {
                "role": "user",
                "content": "\n\n".join(
                    (
                        "[CURRENT_TASK_FACTS]\n{}",
                        "[ACTIVE_SKILL]\n"
                        + json.dumps(
                            {"id": "teacher", "name": "Teacher", "content": base_content},
                            ensure_ascii=False,
                        ),
                        "[TEACHER_STYLE_MEMORIES]\n"
                        + json.dumps([{"memory_text": "frozen"}], ensure_ascii=False),
                        "[STUDENT_HISTORY_MEMORIES]\n[]",
                        "[OUTPUT_RULES]\n- plain text",
                    )
                ),
            },
        ],
        "temperature": 0.2,
    }


def _frozen_input(*, source_valid=True):
    base_content = "# Skill\n\nUse long paragraphs."
    samples = []
    evidence = []
    for index in range(1, 6):
        candidate_revision_id = 100 + index
        samples.append(
            {
                "candidate_revision_id": candidate_revision_id,
                "task_id": index,
                "revision_id": 200 + index,
                "confirmed_transcript_snapshot": f"transcript {index}",
                "attending_roster": [
                    {"student_id": 1000 + index, "student_name": f"学生{index}"}
                ],
                "generated_feedback_text": f"base output {index}",
                "final_feedback_text": f"teacher final {index}",
                "generation_diff": {"changed": True},
                "previous_revision_diff": None,
                "accepted_without_edit": False,
                "prompt_payload": _prompt_payload(base_content),
                "prompt_payload_hash": f"prompt-{index}",
            }
        )
        if index <= 3:
            evidence.append(
                {
                    "candidate_revision_id": candidate_revision_id,
                    "memory_evidence_id": 300 + index,
                    "memory_record_id": 77,
                    "memory_text": "Use short paragraphs.",
                    "memory_text_hash": "style-hash",
                }
            )
    return {
        "build": {
            "id": 9,
            "source_snapshot_hash": "source-hash",
            "min_support_tasks": 3,
            "effective_task_count": 5,
            "supporting_task_count": 3,
        },
        "base_version": {
            "id": 4,
            "content": base_content,
            "content_hash": "base-hash",
        },
        "revision_samples": samples,
        "style_evidence": evidence,
        "source_valid": source_valid,
        "stale_reason": "revision_not_effective" if not source_valid else "",
    }


class FakeCandidateStore:
    def __init__(self, frozen=None):
        self.frozen = frozen or _frozen_input()
        self.status = "queued"
        self.complete_calls = []
        self.fail_calls = []

    def claim_class_commentary_skill_candidate_build(self, build_id, **kwargs):
        if self.status != "queued":
            return None
        self.status = "running"
        return {"id": build_id, "claim_token": "claim-token", "status": "running"}

    def get_class_commentary_skill_candidate_build_input(self, build_id):
        return self.frozen

    def complete_class_commentary_skill_candidate_build(self, build_id, **kwargs):
        self.complete_calls.append((build_id, kwargs))
        self.status = "succeeded"
        return {"id": build_id, "status": "succeeded", "candidate_version_id": 12}

    def fail_class_commentary_skill_candidate_build(self, build_id, **kwargs):
        self.fail_calls.append((build_id, kwargs))
        self.status = "obsolete" if not self.frozen["source_valid"] else "retry_wait"
        return {"id": build_id, "status": self.status}


class ClassCommentarySkillEvolutionWorkerTests(unittest.TestCase):
    def test_candidate_build_uses_all_frozen_changes_and_replays_every_task(self):
        store = FakeCandidateStore()
        candidate_generator = Mock(
            return_value=(
                {
                    "candidate_content": "# Skill\n\nUse short paragraphs.",
                    "change_summary": ["Shorten paragraphs."],
                    "incorporated_memory_record_ids": [77],
                    "known_risks": ["May be too terse."],
                },
                {"input_tokens": 10, "output_tokens": 5},
            )
        )
        replay_generator = Mock(
            side_effect=lambda sample, candidate_content, config: (
                f"teacher final {sample['task_id']}",
                {"input_tokens": 3, "output_tokens": 2},
            )
        )

        def evaluate(evaluation_input, config):
            return {
                "candidate_skill_student_fact_count": 0,
                "samples": [
                    {
                        "task_id": item["task_id"],
                        "revision_id": item["revision_id"],
                        "base_roster_consistent": True,
                        "candidate_roster_consistent": True,
                        "base_unsupported_fact_count": 1,
                        "candidate_unsupported_fact_count": 0,
                        "base_plain_text_valid": True,
                        "candidate_plain_text_valid": True,
                        "base_structure_valid": False,
                        "candidate_structure_valid": True,
                        "candidate_style_memory_record_ids": [77],
                    }
                    for item in evaluation_input["samples"]
                ]
            }

        result = process_class_commentary_skill_candidate_build(
            9,
            store=store,
            candidate_generator=candidate_generator,
            replay_generator=replay_generator,
            replay_evaluator=evaluate,
            runtime_config=ENABLED_CONFIG,
        )

        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(result["candidate_version_id"], 12)
        self.assertEqual(replay_generator.call_count, 5)
        generator_input = candidate_generator.call_args.args[0]
        self.assertEqual(
            generator_input["style_rules"][0]["supporting_task_ids"], [1, 2, 3]
        )
        self.assertEqual(len(generator_input["revision_edits"]), 5)
        completed = store.complete_calls[0][1]
        evaluation = completed["evaluation_snapshot"]
        self.assertEqual(evaluation["effective_task_count"], 5)
        self.assertEqual(evaluation["supporting_task_count"], 3)
        self.assertEqual(
            evaluation["metrics"]["candidate"]["student_fact_contamination_count"],
            0,
        )
        self.assertGreater(
            evaluation["metrics"]["delta"]["normalized_edit_distance_improvement"],
            0,
        )

    def test_candidate_build_can_organize_five_changes_without_style_labels(self):
        frozen = _frozen_input()
        frozen["style_evidence"] = []
        frozen["build"]["supporting_task_count"] = 0
        store = FakeCandidateStore(frozen)

        def evaluate(evaluation_input, config):
            return {
                "candidate_skill_student_fact_count": 0,
                "samples": [
                    {
                        "task_id": item["task_id"],
                        "revision_id": item["revision_id"],
                        "base_roster_consistent": True,
                        "candidate_roster_consistent": True,
                        "base_unsupported_fact_count": 0,
                        "candidate_unsupported_fact_count": 0,
                        "base_plain_text_valid": True,
                        "candidate_plain_text_valid": True,
                        "base_structure_valid": True,
                        "candidate_structure_valid": True,
                        "candidate_style_memory_record_ids": [],
                    }
                    for item in evaluation_input["samples"]
                ],
            }

        candidate_generator = Mock(
            return_value={
                "candidate_content": "# Skill\n\nUse concise, actionable feedback.",
                "change_summary": ["Make feedback concise and actionable."],
                "incorporated_memory_record_ids": [],
                "known_risks": [],
            }
        )
        result = process_class_commentary_skill_candidate_build(
            9,
            store=store,
            candidate_generator=candidate_generator,
            replay_generator=lambda sample, candidate_content, config: (
                f"teacher final {sample['task_id']}"
            ),
            replay_evaluator=evaluate,
            runtime_config=ENABLED_CONFIG,
        )

        self.assertEqual(result["status"], "succeeded")
        generator_input = candidate_generator.call_args.args[0]
        self.assertEqual(generator_input["style_rules"], [])
        self.assertEqual(len(generator_input["revision_edits"]), 5)
        evaluation = store.complete_calls[0][1]["evaluation_snapshot"]
        self.assertEqual(
            evaluation["metrics"]["candidate"]["confirmed_style_rule_coverage_rate"],
            0.0,
        )

    def test_candidate_with_roster_name_is_rejected_before_replay(self):
        store = FakeCandidateStore()
        replay_generator = Mock()

        with self.assertRaisesRegex(ValueError, "roster name"):
            process_class_commentary_skill_candidate_build(
                9,
                store=store,
                candidate_generator=lambda candidate_input, config: {
                    "candidate_content": "# Skill\n\nAlways mention 学生1.",
                    "change_summary": ["Personalize."],
                    "incorporated_memory_record_ids": [77],
                    "known_risks": [],
                },
                replay_generator=replay_generator,
                replay_evaluator=Mock(),
                runtime_config=ENABLED_CONFIG,
            )

        replay_generator.assert_not_called()
        self.assertEqual(store.status, "retry_wait")
        self.assertEqual(len(store.fail_calls), 1)

    def test_stale_source_is_obsoleted_without_ai_calls(self):
        store = FakeCandidateStore(_frozen_input(source_valid=False))
        candidate_generator = Mock()

        result = process_class_commentary_skill_candidate_build(
            9,
            store=store,
            candidate_generator=candidate_generator,
            runtime_config=ENABLED_CONFIG,
        )

        self.assertEqual(result["status"], "obsolete")
        candidate_generator.assert_not_called()
        self.assertEqual(store.fail_calls[0][1]["error"], "revision_not_effective")

    def test_semantic_student_fact_contamination_rejects_candidate(self):
        store = FakeCandidateStore()

        with self.assertRaisesRegex(ValueError, "student fact"):
            process_class_commentary_skill_candidate_build(
                9,
                store=store,
                candidate_generator=lambda candidate_input, config: {
                    "candidate_content": "# Skill\n\nUse a hidden personal weakness.",
                    "change_summary": ["Add a hidden weakness."],
                    "incorporated_memory_record_ids": [77],
                    "known_risks": [],
                },
                replay_generator=lambda sample, content, config: "candidate output",
                replay_evaluator=lambda evaluation_input, config: {
                    "candidate_skill_student_fact_count": 1,
                    "samples": [],
                },
                runtime_config=ENABLED_CONFIG,
            )

        self.assertEqual(store.status, "retry_wait")
        self.assertEqual(len(store.complete_calls), 0)

    def test_replay_replaces_only_the_frozen_active_skill_block(self):
        original = _prompt_payload("old content")

        replay = _replace_active_skill_content(original, "new content")

        self.assertIn('"content":"new content"', replay["messages"][1]["content"])
        self.assertIn('[TEACHER_STYLE_MEMORIES]\n[{"memory_text": "frozen"}]', replay["messages"][1]["content"])
        self.assertIn('"content": "old content"', original["messages"][1]["content"])


if __name__ == "__main__":
    unittest.main()
