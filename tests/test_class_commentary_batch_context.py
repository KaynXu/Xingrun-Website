from __future__ import annotations

import copy
import hashlib
import json
import unittest
from unittest.mock import Mock, patch

import class_commentary_batch_context as batch_context
from class_commentary import (
    CLASS_COMMENTARY_BATCH_ISOLATED_PROMPT_VERSION_V5,
    CLASS_COMMENTARY_STUDENT_HISTORY_MEMORY_BATCH_ISOLATED_V3,
)
from class_commentary_graph_retrieval import (
    GRAPH_CONTEXT_SCHEMA_VERSION,
    ClassCommentaryStudentGraphRetrievalError,
)
from class_commentary_learning_graph import canonical_json as graph_canonical_json
from class_commentary_learning_graph import content_hash as graph_content_hash
from class_commentary_memory_retrieval import (
    ClassCommentaryStudentMemoryRetrievalError,
)


class ClassCommentaryBatchContextTest(unittest.TestCase):
    def setUp(self) -> None:
        self.student_ids = [101, 202]
        self.roster = [
            {"student_id": 101, "student_name": "Student A"},
            {"student_id": 202, "student_name": "Student B"},
        ]
        transcript = "Student A reviewed equations. Student B checked signs."
        self.generation = {
            "id": 41,
            "organization_id": 7,
            "task_id": 31,
            "class_id": 21,
            "skill_registry_id": 11,
            "subject_key": "math",
            "confirmed_transcript_snapshot": transcript,
            "confirmed_transcript_hash": hashlib.sha256(
                transcript.encode("utf-8")
            ).hexdigest(),
            "eligible_student_ids_json": json.dumps(self.student_ids),
        }
        self.database_records = {}

    def _snapshot_memory_item(
        self,
        *,
        record_id: int,
        memory_type: str,
        memory_text: str,
        student_id: int | None = None,
    ) -> dict:
        evidence = [{"evidence_id": f"memory-evidence-{record_id}"}]
        item = {
            "memory_record_id": record_id,
            "mem0_memory_id": f"mem0-{record_id}",
            "memory_text": memory_text,
            "confidence": 0.95,
            "record_version": 1,
            "created_from_revision_id": record_id + 1000,
            "created_at": "2026-08-12T10:00:00Z",
            "active_evidence": evidence,
            "memory_type": memory_type,
        }
        database_record = {
            **item,
            "id": record_id,
            "organization_id": self.generation["organization_id"],
            "desired_status": "active",
            "applied_status": "active",
            "active_evidence_count": len(evidence),
        }
        if memory_type == "student_fact":
            item.update(
                {
                    "student_id": int(student_id or 0),
                    "subject_key": "math",
                }
            )
            database_record.update(
                {
                    "student_id": int(student_id or 0),
                    "subject_key": "math",
                    "scope_skill_registry_id": None,
                }
            )
        else:
            item["scope_skill_registry_id"] = self.generation[
                "skill_registry_id"
            ]
            database_record.update(
                {
                    "student_id": None,
                    "subject_key": None,
                    "scope_skill_registry_id": self.generation[
                        "skill_registry_id"
                    ],
                }
            )
        self.database_records[record_id] = database_record
        return item

    def _memory_context(self, student_id: int) -> dict:
        shared_style = self._snapshot_memory_item(
            record_id=501,
            memory_type="teacher_style",
            memory_text="Keep the teacher's warm style.",
        )
        teacher_style = [shared_style]
        if student_id == self.student_ids[1]:
            teacher_style.append(
                self._snapshot_memory_item(
                    record_id=502,
                    memory_type="teacher_style",
                    memory_text="End with one concrete next action.",
                )
            )
        student_history = [
            self._snapshot_memory_item(
                record_id=600 + student_id,
                memory_type="student_fact",
                memory_text=f"history-only-for-{student_id}",
                student_id=student_id,
            )
        ]
        return {
            "records": [*teacher_style, *student_history],
            "rendered_text": "",
            "student_history_memories": student_history,
            "teacher_style_memories": teacher_style,
            "retrieval_status": "ready",
            "degraded_reason": "",
            "student_history_memory_mode": (
                CLASS_COMMENTARY_STUDENT_HISTORY_MEMORY_BATCH_ISOLATED_V3
            ),
        }

    def _graph_context(self, student_id: int) -> dict:
        evidence_ref = f"graph-ref-{student_id}"
        semantica_snapshot_hash = f"semantica-snapshot-{student_id}"
        snapshot = {
            "schema_version": GRAPH_CONTEXT_SCHEMA_VERSION,
            "organization_id": self.generation["organization_id"],
            "student_id": student_id,
            "subject_key": "math",
            "retrieval_status": "ready",
            "current_states": [
                {
                    "knowledge_point_key": f"knowledge-{student_id}",
                    "knowledge_point_name": f"graph-only-for-{student_id}",
                    "state": "improving",
                    "observed_at": "2026-08-12T10:00:00Z",
                }
            ],
            "recent_changes": [
                {
                    "knowledge_point_key": f"knowledge-{student_id}",
                    "knowledge_point_name": f"graph-only-for-{student_id}",
                    "state": "improving",
                    "previous_state": "weak",
                    "trend": "improving",
                    "observed_at": "2026-08-12T10:00:00Z",
                    "evidence": {
                        "evidence_ref": evidence_ref,
                        "quote": f"graph-quote-only-for-{student_id}",
                        "confirmed_at": "2026-08-12T10:00:00Z",
                    },
                    "teaching_methods": [],
                    "next_steps": [],
                }
            ],
            "allowed_evidence_refs": [evidence_ref],
            "semantica_snapshot_hash": semantica_snapshot_hash,
        }
        return {
            **snapshot,
            "snapshot_hash": graph_content_hash(graph_canonical_json(snapshot)),
        }

    def _record_loader(self, record_ids: list[int]) -> list[dict]:
        return [copy.deepcopy(self.database_records[record_id]) for record_id in record_ids]

    def _graph_summary_loader(self, **scope) -> dict:
        student_id = int(scope["student_id"])
        return {
            **scope,
            "current_states": [],
            "timeline": [
                {
                    "evidence": {
                        "evidence_ref": f"graph-ref-{student_id}",
                    }
                }
            ],
        }

    def _graph_adapter(self) -> Mock:
        return Mock(
            scoped_snapshot=Mock(
                side_effect=lambda **scope: {
                    **scope,
                    "hash": f"semantica-snapshot-{int(scope['student_id'])}",
                }
            )
        )

    def _build_context(self) -> tuple[dict, Mock, Mock]:
        memory_retrieval = Mock(
            side_effect=lambda **kwargs: self._memory_context(
                int(kwargs["student_id"])
            )
        )
        graph_retrieval = Mock(
            side_effect=lambda **kwargs: self._graph_context(
                int(kwargs["student_id"])
            )
        )
        with patch.object(
            batch_context,
            "retrieve_isolated_student_memory_context",
            memory_retrieval,
        ), patch.object(
            batch_context,
            "retrieve_isolated_student_graph_context",
            graph_retrieval,
        ):
            context = batch_context.build_batch_isolated_memory_context(
                generation=self.generation,
                attending_roster=self.roster,
                record_loader=self._record_loader,
                memory_service=object(),
                runtime_config={"class_commentary_graph_enabled": True},
                graph_adapter=self._graph_adapter(),
                graph_summary_loader=self._graph_summary_loader,
            )
        return context, memory_retrieval, graph_retrieval

    def test_retrieves_each_student_once_in_roster_order_and_keeps_partitions_isolated(
        self,
    ) -> None:
        context, memory_retrieval, graph_retrieval = self._build_context()

        self.assertEqual(memory_retrieval.call_count, len(self.student_ids))
        self.assertEqual(graph_retrieval.call_count, len(self.student_ids))
        self.assertEqual(
            [call.kwargs["student_id"] for call in memory_retrieval.call_args_list],
            self.student_ids,
        )
        self.assertEqual(
            [call.kwargs["student_id"] for call in graph_retrieval.call_args_list],
            self.student_ids,
        )
        self.assertTrue(
            all(
                call.kwargs["student_history_memory_mode"]
                == CLASS_COMMENTARY_STUDENT_HISTORY_MEMORY_BATCH_ISOLATED_V3
                for call in memory_retrieval.call_args_list
            )
        )
        self.assertEqual(
            [item["student_id"] for item in context["student_contexts_by_id"]],
            self.student_ids,
        )

        prompt_partitions = (
            batch_context.build_batch_isolated_prompt_student_contexts(context)
        )
        self.assertEqual(
            [item["student_id"] for item in prompt_partitions], self.student_ids
        )
        for partition in prompt_partitions:
            student_id = partition["student_id"]
            other_id = next(
                candidate for candidate in self.student_ids if candidate != student_id
            )
            serialized = json.dumps(
                partition, ensure_ascii=False, sort_keys=True
            )
            self.assertIn(f"history-only-for-{student_id}", serialized)
            self.assertIn(f"graph-only-for-{student_id}", serialized)
            self.assertIn(f"graph-ref-{student_id}", serialized)
            evidence = partition["current_student_evidence"]["verified_fragments"]
            self.assertTrue(evidence)
            self.assertEqual(
                set(evidence[0]), {"start", "end", "text", "text_hash"}
            )
            self.assertIn(
                self.roster[self.student_ids.index(student_id)]["student_name"],
                evidence[0]["text"],
            )
            self.assertEqual(
                partition["learning_graph"]["allowed_evidence_refs"],
                [f"graph-ref-{student_id}"],
            )
            self.assertNotIn(f"history-only-for-{other_id}", serialized)
            self.assertNotIn(f"graph-only-for-{other_id}", serialized)
            self.assertNotIn(f"graph-ref-{other_id}", serialized)

        self.assertEqual(
            context["teacher_style_memories"],
            [
                {"style_rule": "Keep the teacher's warm style."},
                {"style_rule": "End with one concrete next action."},
            ],
        )

    def test_v5_builds_empty_unassigned_evidence_without_exact_name_matching(self):
        self.generation["prompt_version"] = (
            CLASS_COMMENTARY_BATCH_ISOLATED_PROMPT_VERSION_V5
        )
        self.generation["confirmed_transcript_snapshot"] = (
            "Stoodent Eh reviewed equations. Stoodent Bee checked signs."
        )
        self.generation["confirmed_transcript_hash"] = hashlib.sha256(
            self.generation["confirmed_transcript_snapshot"].encode("utf-8")
        ).hexdigest()
        memory_retrieval = Mock(
            side_effect=lambda **kwargs: self._memory_context(
                int(kwargs["student_id"])
            )
        )
        graph_retrieval = Mock(
            side_effect=lambda **kwargs: self._graph_context(
                int(kwargs["student_id"])
            )
        )
        with patch.object(
            batch_context,
            "build_student_evidence_assignment",
        ) as exact_assignment, patch.object(
            batch_context,
            "retrieve_isolated_student_memory_context",
            memory_retrieval,
        ), patch.object(
            batch_context,
            "retrieve_isolated_student_graph_context",
            graph_retrieval,
        ):
            context = batch_context.build_batch_isolated_memory_context(
                generation=self.generation,
                attending_roster=self.roster,
                record_loader=self._record_loader,
                memory_service=object(),
                runtime_config={"class_commentary_graph_enabled": True},
                graph_adapter=self._graph_adapter(),
                graph_summary_loader=self._graph_summary_loader,
            )

        exact_assignment.assert_not_called()
        for partition in context["student_contexts_by_id"]:
            evidence = partition["current_evidence_snapshot"]
            self.assertEqual(
                evidence["matcher_version"],
                "class_commentary.student_evidence_fail_closed.v2",
            )
            self.assertEqual(
                evidence["attribution"],
                "fail_closed_no_structured_ownership",
            )
            self.assertEqual(evidence["fragments"], [])
        self.assertTrue(
            all(
                call.kwargs["evidence_snapshot"]["fragments"] == []
                for call in memory_retrieval.call_args_list
            )
        )

    def test_build_fails_closed_for_cross_student_memory_or_graph_scope(self) -> None:
        cases = ("memory", "graph")
        for contamination in cases:
            with self.subTest(contamination=contamination):
                def memory_result(**kwargs):
                    student_id = int(kwargs["student_id"])
                    result = self._memory_context(student_id)
                    if contamination == "memory" and student_id == self.student_ids[0]:
                        result["student_history_memories"][0]["student_id"] = (
                            self.student_ids[1]
                        )
                    return result

                def graph_result(**kwargs):
                    student_id = int(kwargs["student_id"])
                    result = self._graph_context(student_id)
                    if contamination == "graph" and student_id == self.student_ids[0]:
                        result["student_id"] = self.student_ids[1]
                        without_hash = {
                            key: value
                            for key, value in result.items()
                            if key != "snapshot_hash"
                        }
                        result["snapshot_hash"] = graph_content_hash(
                            graph_canonical_json(without_hash)
                        )
                    return result

                with patch.object(
                    batch_context,
                    "retrieve_isolated_student_memory_context",
                    side_effect=memory_result,
                ), patch.object(
                    batch_context,
                    "retrieve_isolated_student_graph_context",
                    side_effect=graph_result,
                ):
                    with self.assertRaises(
                        batch_context.ClassCommentaryBatchContextError
                    ) as raised:
                        batch_context.build_batch_isolated_memory_context(
                            generation=self.generation,
                            attending_roster=self.roster,
                            record_loader=self._record_loader,
                            memory_service=object(),
                            runtime_config={
                                "class_commentary_graph_enabled": True
                            },
                            graph_adapter=self._graph_adapter(),
                            graph_summary_loader=self._graph_summary_loader,
                        )
                self.assertTrue(raised.exception.code.startswith("batch_"))

    def test_retrieval_errors_fail_the_whole_batch(self) -> None:
        cases = (
            (
                "memory",
                ClassCommentaryStudentMemoryRetrievalError("memory_disabled"),
            ),
            (
                "graph",
                ClassCommentaryStudentGraphRetrievalError(
                    "graph_scope_mismatch"
                ),
            ),
        )
        for failure_source, retrieval_error in cases:
            with self.subTest(failure_source=failure_source):
                memory_retrieval = Mock(
                    side_effect=(
                        retrieval_error
                        if failure_source == "memory"
                        else lambda **kwargs: self._memory_context(
                            int(kwargs["student_id"])
                        )
                    )
                )
                graph_retrieval = Mock(
                    side_effect=(
                        retrieval_error
                        if failure_source == "graph"
                        else lambda **kwargs: self._graph_context(
                            int(kwargs["student_id"])
                        )
                    )
                )
                with patch.object(
                    batch_context,
                    "retrieve_isolated_student_memory_context",
                    memory_retrieval,
                ), patch.object(
                    batch_context,
                    "retrieve_isolated_student_graph_context",
                    graph_retrieval,
                ):
                    with self.assertRaises(
                        batch_context.ClassCommentaryBatchContextError
                    ) as raised:
                        batch_context.build_batch_isolated_memory_context(
                            generation=self.generation,
                            attending_roster=self.roster,
                            record_loader=self._record_loader,
                            memory_service=object(),
                            runtime_config={
                                "class_commentary_graph_enabled": True
                            },
                            graph_summary_loader=self._graph_summary_loader,
                        )
                self.assertEqual(
                    raised.exception.code, "batch_context_retrieval_failed"
                )

    def test_snapshot_validation_fails_closed_for_scope_or_snapshot_tampering(
        self,
    ) -> None:
        context, _, _ = self._build_context()
        cases = []

        cross_memory = copy.deepcopy(context)
        cross_memory["student_contexts_by_id"][0]["memory_context"][
            "student_history_memories"
        ][0]["student_id"] = self.student_ids[1]
        cases.append(("cross_student_memory", cross_memory))

        cross_graph = copy.deepcopy(context)
        graph = cross_graph["student_contexts_by_id"][0]["learning_graph"]
        graph["student_id"] = self.student_ids[1]
        graph_without_hash = {
            key: value for key, value in graph.items() if key != "snapshot_hash"
        }
        graph["snapshot_hash"] = graph_content_hash(
            graph_canonical_json(graph_without_hash)
        )
        cases.append(("cross_student_graph", cross_graph))

        invalid_evidence = copy.deepcopy(context)
        invalid_evidence["student_contexts_by_id"][0][
            "current_evidence_snapshot"
        ]["snapshot_hash"] = "0" * 64
        cases.append(("invalid_evidence_snapshot", invalid_evidence))

        for label, candidate in cases:
            with self.subTest(label=label):
                with self.assertRaises(
                    batch_context.ClassCommentaryBatchContextError
                ) as raised:
                    batch_context.validate_batch_isolated_memory_context_snapshot(
                        generation=self.generation,
                        memory_context=candidate,
                        record_loader=self._record_loader,
                        runtime_config={
                            "class_commentary_graph_enabled": True
                        },
                        graph_adapter=self._graph_adapter(),
                        graph_summary_loader=self._graph_summary_loader,
                    )
                self.assertTrue(raised.exception.code.startswith("batch_"))

    def test_lower_level_snapshot_error_is_wrapped_and_never_accepted(self) -> None:
        context, _, _ = self._build_context()
        with patch.object(
            batch_context,
            "validate_isolated_student_memory_context_snapshot",
            side_effect=ClassCommentaryStudentMemoryRetrievalError(
                "memory_snapshot_stale"
            ),
        ):
            with self.assertRaises(
                batch_context.ClassCommentaryBatchContextError
            ) as raised:
                batch_context.validate_batch_isolated_memory_context_snapshot(
                    generation=self.generation,
                    memory_context=context,
                    record_loader=self._record_loader,
                    runtime_config={"class_commentary_graph_enabled": True},
                    graph_adapter=self._graph_adapter(),
                    graph_summary_loader=self._graph_summary_loader,
                )
        self.assertEqual(
            raised.exception.code, "batch_context_snapshot_invalid"
        )

    def test_serialized_utf8_budget_overflow_fails_closed(self) -> None:
        self.assertGreater(
            batch_context.BATCH_ISOLATED_CONTEXT_MAX_UTF8_BYTES, 0
        )
        memory_retrieval = Mock(
            side_effect=lambda **kwargs: self._memory_context(
                int(kwargs["student_id"])
            )
        )
        graph_retrieval = Mock(
            side_effect=lambda **kwargs: self._graph_context(
                int(kwargs["student_id"])
            )
        )
        with patch.object(
            batch_context,
            "BATCH_ISOLATED_CONTEXT_MAX_UTF8_BYTES",
            64,
        ), patch.object(
            batch_context,
            "retrieve_isolated_student_memory_context",
            memory_retrieval,
        ), patch.object(
            batch_context,
            "retrieve_isolated_student_graph_context",
            graph_retrieval,
        ):
            with self.assertRaises(
                batch_context.ClassCommentaryBatchContextError
            ) as raised:
                batch_context.build_batch_isolated_memory_context(
                    generation=self.generation,
                    attending_roster=self.roster,
                    record_loader=self._record_loader,
                    memory_service=object(),
                    runtime_config={"class_commentary_graph_enabled": True},
                    graph_adapter=self._graph_adapter(),
                    graph_summary_loader=self._graph_summary_loader,
                )
        self.assertEqual(raised.exception.code, "batch_context_too_large")

    def test_graph_service_disabled_or_degraded_fails_before_batch_prompt(self) -> None:
        memory_retrieval = Mock(
            side_effect=lambda **kwargs: self._memory_context(
                int(kwargs["student_id"])
            )
        )
        for status in ("disabled", "degraded"):
            with self.subTest(status=status), patch.object(
                batch_context,
                "retrieve_isolated_student_memory_context",
                memory_retrieval,
            ), patch.object(
                batch_context,
                "retrieve_isolated_student_graph_context",
                side_effect=ClassCommentaryStudentGraphRetrievalError(
                    f"graph_{status}"
                ),
            ):
                with self.assertRaises(
                    batch_context.ClassCommentaryBatchContextError
                ) as raised:
                    batch_context.build_batch_isolated_memory_context(
                        generation=self.generation,
                        attending_roster=self.roster,
                        record_loader=self._record_loader,
                        memory_service=object(),
                        runtime_config={"class_commentary_graph_enabled": True},
                        graph_adapter=self._graph_adapter(),
                        graph_summary_loader=self._graph_summary_loader,
                    )
            self.assertEqual(
                raised.exception.code, "batch_context_retrieval_failed"
            )


if __name__ == "__main__":
    unittest.main()
