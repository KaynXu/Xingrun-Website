import unittest

from class_commentary_memory import ClassCommentaryMemoryService
from class_commentary_memory_retrieval import retrieve_class_commentary_memory_context


class FakeMemoryService(ClassCommentaryMemoryService):
    def __init__(self, *, style=None, students=None, failure=None):
        super().__init__(runtime_config={"mem0_context_char_limit": 3000}, enabled=True, client=object())
        self.style = style or []
        self.students = students or {}
        self.failure = failure
        self.calls = []

    def search_style(self, query, **scope):
        self.calls.append(("style", query, scope))
        if self.failure:
            raise self.failure
        return self.style

    def search_student(self, query, **scope):
        self.calls.append(("student", query, scope))
        return self.students.get(scope["student_id"], [])


def candidate(record_id, record_version, memory_type, **scope):
    return {
        "id": f"mem0-{record_id}",
        "memory": "untrusted projection text",
        "metadata": {
            "memory_record_id": record_id,
            "record_version": record_version,
            "memory_type": memory_type,
            **scope,
        },
    }


class ClassCommentaryMemoryRetrievalTest(unittest.TestCase):
    def setUp(self):
        self.generation = {
            "organization_id": 4,
            "skill_registry_id": 8,
            "subject_key": "math",
            "confirmed_transcript_snapshot": "小林这次绝对值分类讨论仍会漏边界, 小周完成得很好.",
            "attending_roster_snapshot_json": [
                {"student_id": 21, "student_name": "小林"},
                {"student_id": 22, "student_name": "小周"},
                {"student_id": 23, "student_name": "未提到"},
            ],
        }

    def test_retrieval_uses_sqlite_text_and_only_mentioned_accessible_students(self):
        service = FakeMemoryService(
            style=[candidate(10, 2, "teacher_style", scope_skill_registry_id=8)],
            students={
                21: [candidate(11, 1, "student_fact", student_id=21, subject_key="math")],
                22: [candidate(12, 1, "student_fact", student_id=22, subject_key="math")],
            },
        )
        records = {
            10: {
                "id": 10,
                "organization_id": 4,
                "memory_type": "teacher_style",
                "scope_skill_registry_id": 8,
                "student_id": None,
                "desired_status": "active",
                "record_version": 2,
                "active_evidence_count": 1,
                "confidence": 0.9,
                "memory_text": "每个重点单独成段.",
                "created_from_revision_id": 31,
            },
            11: {
                "id": 11,
                "organization_id": 4,
                "memory_type": "student_fact",
                "scope_skill_registry_id": None,
                "student_id": 21,
                "subject_key": "math",
                "desired_status": "active",
                "record_version": 1,
                "active_evidence_count": 1,
                "confidence": 0.85,
                "memory_text": "绝对值分类讨论仍会遗漏边界条件.",
                "created_from_revision_id": 32,
            },
            12: {
                "id": 12,
                "organization_id": 4,
                "memory_type": "student_fact",
                "scope_skill_registry_id": None,
                "student_id": 22,
                "subject_key": "math",
                "desired_status": "active",
                "record_version": 1,
                "active_evidence_count": 1,
                "confidence": 0.5,
                "memory_text": "low confidence",
                "created_from_revision_id": 33,
            },
        }
        marked = []

        context = retrieve_class_commentary_memory_context(
            generation=self.generation,
            live_student_ids=[21],
            memory_service=service,
            record_loader=lambda ids: [records[item] for item in ids if item in records],
            reconciliation_marker=lambda organization_id, ids, reason: marked.append(
                (organization_id, ids, reason)
            ),
        )

        self.assertEqual([call[0] for call in service.calls], ["style", "student"])
        self.assertEqual(service.calls[1][2]["student_id"], 21)
        self.assertEqual(context["teacher_style_memories"][0]["memory_text"], "每个重点单独成段.")
        self.assertEqual(
            context["student_history_memories"][0]["memory_text"],
            "绝对值分类讨论仍会遗漏边界条件.",
        )
        self.assertNotIn("untrusted projection text", context["rendered_text"])
        self.assertEqual(marked, [])

    def test_structured_retrieval_disables_student_history_memory(self):
        generation = {
            **self.generation,
            "feedback_schema_version": "class_commentary.student_feedback.v1",
            "student_history_memory_mode": "disabled_v1",
            "eligible_student_ids_json": [21, 22],
        }
        service = FakeMemoryService(
            style=[candidate(10, 2, "teacher_style", scope_skill_registry_id=8)],
            students={
                21: [candidate(11, 1, "student_fact", student_id=21, subject_key="math")],
                22: [candidate(12, 1, "student_fact", student_id=22, subject_key="math")],
            },
        )
        records = {
            10: {
                "id": 10,
                "organization_id": 4,
                "memory_type": "teacher_style",
                "scope_skill_registry_id": 8,
                "student_id": None,
                "desired_status": "active",
                "record_version": 2,
                "active_evidence_count": 1,
                "confidence": 0.9,
                "memory_text": "Each focus point gets its own paragraph.",
                "created_from_revision_id": 31,
            },
            11: {
                "id": 11,
                "organization_id": 4,
                "memory_type": "student_fact",
                "scope_skill_registry_id": None,
                "student_id": 21,
                "subject_key": "math",
                "desired_status": "active",
                "record_version": 1,
                "active_evidence_count": 1,
                "confidence": 0.9,
                "memory_text": "Student 21 history must stay out of this generation.",
                "created_from_revision_id": 32,
            },
            12: {
                "id": 12,
                "organization_id": 4,
                "memory_type": "student_fact",
                "scope_skill_registry_id": None,
                "student_id": 22,
                "subject_key": "math",
                "desired_status": "active",
                "record_version": 1,
                "active_evidence_count": 1,
                "confidence": 0.9,
                "memory_text": "Student 22 history must stay out of this generation.",
                "created_from_revision_id": 33,
            },
        }
        loaded_record_ids = []

        def load_records(record_ids):
            loaded_record_ids.extend(record_ids)
            return [records[item] for item in record_ids if item in records]

        context = retrieve_class_commentary_memory_context(
            generation=generation,
            live_student_ids=[21, 22],
            memory_service=service,
            record_loader=load_records,
        )

        self.assertEqual([call[0] for call in service.calls], ["style"])
        self.assertEqual(loaded_record_ids, [10])
        self.assertEqual(
            [item["memory_record_id"] for item in context["teacher_style_memories"]],
            [10],
        )
        self.assertEqual(context["student_history_memories"], [])
        self.assertEqual([item["memory_type"] for item in context["records"]], ["teacher_style"])
        self.assertIn("Each focus point gets its own paragraph.", context["rendered_text"])
        self.assertNotIn("Student 21 history", context["rendered_text"])
        self.assertNotIn("Student 22 history", context["rendered_text"])
        self.assertEqual(context["student_history_memory_mode"], "disabled_v1")

    def test_stale_projection_is_dropped_and_marked_for_reconciliation(self):
        service = FakeMemoryService(
            style=[candidate(10, 1, "teacher_style", scope_skill_registry_id=8)]
        )
        marked = []
        context = retrieve_class_commentary_memory_context(
            generation=self.generation,
            live_student_ids=[21, 22, 23],
            memory_service=service,
            record_loader=lambda _: [{
                "id": 10,
                "organization_id": 4,
                "memory_type": "teacher_style",
                "scope_skill_registry_id": 8,
                "student_id": None,
                "desired_status": "revoked",
                "record_version": 2,
                "active_evidence_count": 0,
                "confidence": 0.9,
                "memory_text": "revoked",
            }],
            reconciliation_marker=lambda organization_id, ids, reason: marked.append(
                (organization_id, ids, reason)
            ),
        )

        self.assertEqual(context["records"], [])
        self.assertEqual(marked, [(4, [10], "retrieval_projection_mismatch")])

    def test_mem0_failure_degrades_without_raising(self):
        context = retrieve_class_commentary_memory_context(
            generation=self.generation,
            live_student_ids=[21, 22],
            memory_service=FakeMemoryService(failure=ConnectionError("qdrant unavailable")),
            record_loader=lambda _: [],
        )

        self.assertEqual(context["retrieval_status"], "degraded")
        self.assertEqual(context["degraded_reason"], "mem0_ConnectionError")
        self.assertEqual(context["records"], [])


if __name__ == "__main__":
    unittest.main()
