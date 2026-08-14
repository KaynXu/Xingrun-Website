import builtins
import json
import sys
import types
import unittest
from unittest.mock import patch

from pydantic import ValidationError

from class_commentary_memory import (
    ClassCommentaryMemoryDisabledError,
    ClassCommentaryMemoryResponseError,
    ClassCommentaryMemoryService,
    EvaluationOnlyMemorySignal,
    StudentFactMemorySignal,
    TeacherStyleMemorySignal,
    load_class_commentary_memory_settings,
    parse_class_commentary_memory_extraction,
)


class FakeMem0Client:
    def __init__(self):
        self.calls = []
        self.add_response = {"results": [{"id": "memory-1", "memory": "short paragraphs", "event": "ADD"}]}
        self.get_response = {"id": "memory-1", "memory": "health probe"}
        self.get_all_response = {"results": []}
        self.search_response = {
            "results": [{"id": "memory-1", "memory": "health probe"}]
        }

    def add(self, messages, **kwargs):
        self.calls.append(("add", messages, kwargs))
        return self.add_response

    def update(self, memory_id, **kwargs):
        self.calls.append(("update", memory_id, kwargs))
        return {"message": "Memory updated successfully!"}

    def delete(self, memory_id):
        self.calls.append(("delete", memory_id))
        return {"message": "Memory deleted successfully!"}

    def get(self, memory_id):
        self.calls.append(("get", memory_id))
        return self.get_response

    def get_all(self, **kwargs):
        self.calls.append(("get_all", kwargs))
        return self.get_all_response

    def search(self, query, **kwargs):
        self.calls.append(("search", query, kwargs))
        return self.search_response


class NewUpdateSignatureMem0Client(FakeMem0Client):
    def update(self, memory_id, text=None, metadata=None):
        self.calls.append(("update", memory_id, {"text": text, "metadata": metadata}))
        return {"message": "Memory updated successfully!"}


def projection_metadata(**overrides):
    metadata = {
        "organization_id": 4,
        "scope_skill_registry_id": 8,
        "student_id": None,
        "subject_key": None,
        "memory_type": "teacher_style",
        "generation_id": 12,
        "created_from_revision_id": 13,
        "memory_record_id": 14,
        "record_version": 1,
        "evidence_count": 1,
        "operation_key": "cc-memory-14-v1-hash",
        "status": "active",
        "confidence": 0.9,
        "occurred_at": "2026-07-14T10:00:00Z",
    }
    metadata.update(overrides)
    return metadata


class ClassCommentaryMemoryExtractionSchemaTests(unittest.TestCase):
    def test_parser_accepts_only_the_three_signal_types(self):
        extraction = parse_class_commentary_memory_extraction(
            {
                "items": [
                    {
                        "memory_type": "teacher_style",
                        "memory_text": " Use short paragraphs. ",
                        "confidence": 0.9,
                        "support": [" final text uses one point per paragraph "],
                    },
                    {
                        "memory_type": "student_fact",
                        "student_name": " Lin ",
                        "student_id_hint": 7,
                        "memory_text": "Boundary cases still need attention.",
                        "confidence": 0.8,
                        "support": ["confirmed transcript"],
                    },
                    {
                        "memory_type": "evaluation_only",
                        "memory_text": "The event happened only in this lesson.",
                        "reason": "one-off lesson detail",
                        "confidence": 0.7,
                        "support": ["confirmed transcript"],
                    },
                ]
            }
        )

        self.assertIsInstance(extraction.items[0], TeacherStyleMemorySignal)
        self.assertIsInstance(extraction.items[1], StudentFactMemorySignal)
        self.assertIsInstance(extraction.items[2], EvaluationOnlyMemorySignal)
        self.assertEqual(extraction.items[0].memory_text, "Use short paragraphs.")
        self.assertEqual(extraction.items[1].student_name, "Lin")

    def test_parser_accepts_json_and_list_root(self):
        extraction = parse_class_commentary_memory_extraction(
            json.dumps(
                [
                    {
                        "memory_type": "teacher_style",
                        "memory_text": "Prefer direct actions.",
                        "confidence": 0.7,
                        "support": ["diff"],
                    }
                ]
            )
        )
        self.assertEqual(len(extraction.items), 1)

    def test_parser_rejects_unknown_type_and_extra_student_fields(self):
        with self.assertRaises(ValidationError):
            parse_class_commentary_memory_extraction(
                {"items": [{"memory_type": "unknown", "memory_text": "x", "support": ["y"]}]}
            )

        with self.assertRaises(ValidationError):
            parse_class_commentary_memory_extraction(
                {
                    "items": [
                        {
                            "memory_type": "evaluation_only",
                            "memory_text": "One-off detail.",
                            "reason": "temporary",
                            "confidence": 1.1,
                            "support": ["transcript"],
                        }
                    ]
                }
            )
        with self.assertRaises(ValidationError):
            parse_class_commentary_memory_extraction(
                {
                    "items": [
                        {
                            "memory_type": "student_fact",
                            "student_name": "Lin",
                            "student_id_hint": 7,
                            "memory_text": "Needs practice.",
                            "confidence": 0.8,
                            "support": ["diff"],
                            "subject_key": "math",
                        }
                    ]
                }
            )

    def test_student_fact_requires_a_hint_and_non_empty_support(self):
        with self.assertRaises(ValidationError):
            StudentFactMemorySignal(
                memory_type="student_fact",
                memory_text="Needs practice.",
                confidence=0.8,
                support=["diff"],
            )
        with self.assertRaises(ValidationError):
            TeacherStyleMemorySignal(
                memory_type="teacher_style",
                memory_text="Keep it short.",
                confidence=0.8,
                support=[""],
            )


class ClassCommentaryMemoryServiceTests(unittest.TestCase):
    def make_service(self, client=None):
        return ClassCommentaryMemoryService(
            client=client or FakeMem0Client(),
            runtime_config={},
            enabled=True,
        )

    def test_disabled_service_does_not_import_mem0_or_touch_client(self):
        service = ClassCommentaryMemoryService(runtime_config={}, enabled=False)
        original_import = builtins.__import__

        def guarded_import(name, *args, **kwargs):
            if name == "mem0":
                raise AssertionError("mem0 must remain lazy while disabled")
            return original_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", side_effect=guarded_import):
            self.assertEqual(
                service.healthcheck(),
                {"enabled": False, "healthy": False, "status": "disabled"},
            )
            with self.assertRaises(ClassCommentaryMemoryDisabledError):
                service.search_style("tone", organization_id=1, scope_skill_registry_id=2)

    def test_settings_use_the_shared_runtime_config_contract(self):
        runtime_config = {
            "class_commentary_memory_enabled": True,
            "mem0_vector_provider": "qdrant",
            "mem0_qdrant_url": "http://qdrant:6333",
            "mem0_collection_name": "commentary",
            "mem0_embedder_provider": "openai",
            "mem0_embedder_model": "text-embedding-3-small",
            "mem0_embedding_dims": 1536,
        }
        settings = load_class_commentary_memory_settings(runtime_config)
        self.assertTrue(settings.enabled)
        self.assertEqual(settings.qdrant_url, "http://qdrant:6333")
        self.assertEqual(settings.style_limit, 8)
        self.assertEqual(settings.student_limit, 5)
        self.assertEqual(settings.context_char_limit, 3000)

    def test_enabled_service_initializes_mem0_only_on_first_operation(self):
        fake_client = FakeMem0Client()
        fake_memory_class = type(
            "FakeMemory",
            (),
            {
                "configs": [],
                "from_config": classmethod(
                    lambda cls, config: cls.configs.append(config) or fake_client
                ),
            },
        )
        fake_mem0_module = types.ModuleType("mem0")
        fake_mem0_module.Memory = fake_memory_class
        runtime_config = {
            "class_commentary_memory_enabled": True,
            "class_commentary_provider": "openai",
            "class_commentary_model": "gpt-class-commentary",
            "mem0_qdrant_url": "http://qdrant:6333",
            "mem0_qdrant_api_key": "qdrant-key",
            "mem0_embedder_provider": "openai",
            "mem0_embedder_model": "text-embedding-3-small",
            "mem0_embedding_dims": 1536,
            "openai_api_key": "embedder-key",
            "openai_base_url": "https://embedder.example/v1",
        }
        with patch.dict(sys.modules, {"mem0": fake_mem0_module}):
            service = ClassCommentaryMemoryService(runtime_config=runtime_config)
            self.assertEqual(fake_memory_class.configs, [])
            self.assertEqual(service.healthcheck()["status"], "ready")

        self.assertEqual(len(fake_memory_class.configs), 1)
        config = fake_memory_class.configs[0]
        self.assertEqual(config["vector_store"]["provider"], "qdrant")
        self.assertEqual(config["vector_store"]["config"]["url"], "http://qdrant:6333")
        self.assertEqual(config["vector_store"]["config"]["api_key"], "qdrant-key")
        self.assertEqual(config["vector_store"]["config"]["embedding_model_dims"], 1536)
        self.assertEqual(config["embedder"]["config"]["api_key"], "embedder-key")
        self.assertEqual(
            config["embedder"]["config"]["openai_base_url"],
            "https://embedder.example/v1",
        )
        self.assertEqual(config["llm"]["provider"], "openai")
        self.assertEqual(config["llm"]["config"]["model"], "gpt-class-commentary")
        self.assertEqual(config["llm"]["config"]["api_key"], "embedder-key")
        self.assertEqual(
            config["llm"]["config"]["openai_base_url"],
            "https://embedder.example/v1",
        )

    def test_self_hosted_qdrant_does_not_require_an_api_key(self):
        fake_client = FakeMem0Client()
        fake_memory_class = type(
            "FakeMemory",
            (),
            {
                "configs": [],
                "from_config": classmethod(
                    lambda cls, config: cls.configs.append(config) or fake_client
                ),
            },
        )
        fake_mem0_module = types.ModuleType("mem0")
        fake_mem0_module.Memory = fake_memory_class
        runtime_config = {
            "class_commentary_memory_enabled": True,
            "class_commentary_provider": "openai",
            "class_commentary_model": "gpt-class-commentary",
            "class_commentary_openai_api_key": "llm-key",
            "mem0_qdrant_url": "http://127.0.0.1:6333",
            "mem0_embedder_provider": "openai",
            "mem0_embedder_model": "text-embedding-3-small",
            "mem0_embedding_dims": 1536,
            "openai_api_key": "embedder-key",
        }

        with patch.dict(sys.modules, {"mem0": fake_mem0_module}):
            service = ClassCommentaryMemoryService(runtime_config=runtime_config)
            self.assertEqual(service.healthcheck()["status"], "ready")

        vector_config = fake_memory_class.configs[0]["vector_store"]["config"]
        self.assertNotIn("api_key", vector_config)

    def test_deepseek_uses_the_openai_compatible_llm_adapter(self):
        fake_client = FakeMem0Client()
        fake_memory_class = type(
            "FakeMemory",
            (),
            {
                "configs": [],
                "from_config": classmethod(
                    lambda cls, config: cls.configs.append(config) or fake_client
                ),
            },
        )
        fake_mem0_module = types.ModuleType("mem0")
        fake_mem0_module.Memory = fake_memory_class
        runtime_config = {
            "class_commentary_memory_enabled": True,
            "class_commentary_provider": "deepseek",
            "class_commentary_model": "deepseek-class-commentary",
            "deepseek_api_key": "deepseek-secret",
            "mem0_qdrant_url": "http://qdrant:6333",
            "mem0_qdrant_api_key": "qdrant-key",
            "mem0_embedder_provider": "openai",
            "mem0_embedder_model": "text-embedding-3-small",
            "mem0_embedding_dims": 1536,
            "openai_api_key": "embedding-secret",
        }

        with patch.dict(sys.modules, {"mem0": fake_mem0_module}):
            result = ClassCommentaryMemoryService(
                runtime_config=runtime_config
            ).healthcheck()

        self.assertEqual(result["status"], "ready")
        llm_config = fake_memory_class.configs[0]["llm"]
        self.assertEqual(llm_config["provider"], "openai")
        self.assertEqual(llm_config["config"]["model"], "deepseek-class-commentary")
        self.assertEqual(llm_config["config"]["api_key"], "deepseek-secret")
        self.assertEqual(
            llm_config["config"]["openai_base_url"],
            "https://api.deepseek.com/v1",
        )

    def test_openai_uses_class_commentary_credentials_before_global_credentials(self):
        fake_client = FakeMem0Client()
        fake_memory_class = type(
            "FakeMemory",
            (),
            {
                "configs": [],
                "from_config": classmethod(
                    lambda cls, config: cls.configs.append(config) or fake_client
                ),
            },
        )
        fake_mem0_module = types.ModuleType("mem0")
        fake_mem0_module.Memory = fake_memory_class
        runtime_config = {
            "class_commentary_memory_enabled": True,
            "class_commentary_provider": "openai",
            "class_commentary_model": "gpt-class-commentary",
            "class_commentary_openai_api_key": "class-secret",
            "class_commentary_openai_base_url": "https://class.example/v1",
            "openai_api_key": "embedding-secret",
            "openai_base_url": "https://embedding.example/v1",
            "mem0_embedder_api_key": "dedicated-embedding-secret",
            "mem0_embedder_base_url": "https://dedicated-embedding.example/v1",
            "mem0_qdrant_url": "http://qdrant:6333",
            "mem0_qdrant_api_key": "qdrant-key",
            "mem0_embedder_provider": "openai",
            "mem0_embedder_model": "text-embedding-3-small",
            "mem0_embedding_dims": 1536,
        }

        with patch.dict(sys.modules, {"mem0": fake_mem0_module}):
            result = ClassCommentaryMemoryService(
                runtime_config=runtime_config
            ).healthcheck()

        self.assertEqual(result["status"], "ready")
        config = fake_memory_class.configs[0]
        self.assertEqual(config["llm"]["config"]["api_key"], "class-secret")
        self.assertEqual(
            config["llm"]["config"]["openai_base_url"],
            "https://class.example/v1",
        )
        self.assertEqual(
            config["embedder"]["config"]["api_key"],
            "dedicated-embedding-secret",
        )
        self.assertEqual(
            config["embedder"]["config"]["openai_base_url"],
            "https://dedicated-embedding.example/v1",
        )

    def test_enabled_service_fails_closed_before_mem0_init_when_llm_key_is_missing(self):
        fake_memory_class = type(
            "FakeMemory",
            (),
            {
                "configs": [],
                "from_config": classmethod(lambda cls, config: cls.configs.append(config)),
            },
        )
        fake_mem0_module = types.ModuleType("mem0")
        fake_mem0_module.Memory = fake_memory_class
        runtime_config = {
            "class_commentary_memory_enabled": True,
            "class_commentary_provider": "deepseek",
            "mem0_qdrant_url": "http://qdrant:6333",
            "mem0_qdrant_api_key": "qdrant-key",
            "mem0_embedder_provider": "openai",
            "mem0_embedder_model": "text-embedding-3-small",
            "mem0_embedding_dims": 1536,
            "openai_api_key": "embedding-secret",
        }

        with patch.dict(sys.modules, {"mem0": fake_mem0_module}):
            result = ClassCommentaryMemoryService(
                runtime_config=runtime_config
            ).healthcheck()

        self.assertEqual(
            result,
            {
                "enabled": True,
                "healthy": False,
                "status": "unavailable",
                "error_type": "ClassCommentaryMemoryConfigError",
            },
        )
        self.assertEqual(fake_memory_class.configs, [])

    def test_add_projection_uses_scope_user_id_metadata_and_infer_false(self):
        client = FakeMem0Client()
        service = self.make_service(client)
        metadata = projection_metadata()

        result = service.add_projection(memory_text="Use short paragraphs.", metadata=metadata)

        self.assertEqual(result["id"], "memory-1")
        self.assertEqual(
            client.calls,
            [
                (
                    "add",
                    "Use short paragraphs.",
                    {
                        "user_id": "cc:org:4:skill:8:teacher-style",
                        "metadata": metadata,
                        "infer": False,
                    },
                )
            ],
        )

    def test_add_projection_requires_complete_exact_scope_metadata(self):
        service = self.make_service()
        metadata = projection_metadata()
        del metadata["operation_key"]
        with self.assertRaisesRegex(ValueError, "operation_key"):
            service.add_projection(memory_text="Use short paragraphs.", metadata=metadata)

        with self.assertRaisesRegex(ValueError, "student scope"):
            service.add_projection(
                memory_text="Use short paragraphs.",
                metadata=projection_metadata(student_id=9),
            )

    def test_add_projection_normalizes_old_list_shape_and_rejects_missing_id(self):
        client = FakeMem0Client()
        client.add_response = [{"memory_id": "old-1", "text": "Use short paragraphs."}]
        service = self.make_service(client)
        result = service.add_projection(
            memory_text="Use short paragraphs.", metadata=projection_metadata()
        )
        self.assertEqual(result["id"], "old-1")

        client.add_response = {"results": []}
        with self.assertRaises(ClassCommentaryMemoryResponseError):
            service.add_projection(memory_text="Use short paragraphs.", metadata=projection_metadata())

    def test_update_delete_and_get_delegate_without_claiming_canonical_state(self):
        client = FakeMem0Client()
        client.get_response = {
            "id": "memory-1",
            "memory": "Use short paragraphs.",
            "metadata": projection_metadata(),
        }
        service = self.make_service(client)

        service.update(
            "memory-1",
            memory_text=None,
            metadata=projection_metadata(record_version=2, evidence_count=0, status="revoked"),
        )
        service.delete("memory-1")
        result = service.get("memory-1")

        self.assertEqual(result["id"], "memory-1")
        self.assertEqual(client.calls[0][0], "update")
        self.assertEqual(client.calls[0][2]["data"], None)
        self.assertEqual(client.calls[0][2]["metadata"]["record_version"], 2)
        self.assertEqual(client.calls[0][2]["metadata"]["evidence_count"], 0)
        self.assertEqual(client.calls[1], ("delete", "memory-1"))

    def test_update_supports_new_mem0_text_parameter_without_version_branching(self):
        client = NewUpdateSignatureMem0Client()
        service = self.make_service(client)
        service.update(
            "memory-1",
            memory_text="Use shorter paragraphs.",
            metadata=projection_metadata(record_version=2),
        )
        self.assertEqual(client.calls[0][2]["text"], "Use shorter paragraphs.")

    def test_style_search_uses_only_exact_style_scope_and_drops_leaked_candidates(self):
        client = FakeMem0Client()
        expected = projection_metadata()
        leaked = projection_metadata(organization_id=5)
        client.search_response = {
            "results": [
                {
                    "id": "ok",
                    "memory": "Use short paragraphs.",
                    "user_id": "cc:org:4:skill:8:teacher-style",
                    "metadata": expected,
                    "score": 0.9,
                },
                {"id": "leaked", "memory": "Wrong org", "metadata": leaked, "score": 1.0},
            ]
        }
        service = self.make_service(client)

        results = service.search_style(
            "parent feedback tone",
            organization_id=4,
            scope_skill_registry_id=8,
        )

        self.assertEqual([item["id"] for item in results], ["ok"])
        self.assertEqual(
            client.calls[0],
            (
                "search",
                "parent feedback tone",
                {
                    "filters": {
                        "user_id": "cc:org:4:skill:8:teacher-style",
                        "organization_id": 4,
                        "scope_skill_registry_id": 8,
                        "memory_type": "teacher_style",
                    },
                    "top_k": 8,
                },
            ),
        )

    def test_student_search_never_filters_by_source_skill(self):
        client = FakeMem0Client()
        metadata = projection_metadata(
            scope_skill_registry_id=None,
            student_id=21,
            subject_key="math",
            memory_type="student_fact",
        )
        client.search_response = [
            {
                "memory_id": "student-memory",
                "text": "Boundary cases need attention.",
                "metadata": metadata,
            }
        ]
        service = self.make_service(client)

        results = service.search_student(
            "absolute value",
            organization_id=4,
            student_id=21,
            subject_key="math",
        )

        self.assertEqual([item["id"] for item in results], ["student-memory"])
        filters = client.calls[0][2]["filters"]
        self.assertEqual(
            filters,
            {
                "user_id": "cc:org:4:student:21:subject:math:student-fact",
                "organization_id": 4,
                "student_id": 21,
                "subject_key": "math",
                "memory_type": "student_fact",
            },
        )
        self.assertNotIn("scope_skill_registry_id", filters)
        self.assertNotIn("source_skill_id", filters)

    def test_search_rejects_non_canonical_subject_key(self):
        service = self.make_service()
        with self.assertRaisesRegex(ValueError, "canonical"):
            service.search_student(
                "fractions",
                organization_id=4,
                student_id=21,
                subject_key="Math class",
            )

    def test_find_by_operation_key_uses_scope_and_rechecks_returned_metadata(self):
        client = FakeMem0Client()
        expected = projection_metadata()
        client.get_all_response = {
            "memories": [
                {"id": "wrong", "memory": "x", "metadata": projection_metadata(operation_key="other")},
                {"id": "right", "memory": "y", "metadata": expected},
            ]
        }
        service = self.make_service(client)

        result = service.find_by_operation_key(
            expected["operation_key"],
            organization_id=4,
            memory_type="teacher_style",
            scope_skill_registry_id=8,
        )

        self.assertEqual(result["id"], "right")
        self.assertEqual(client.calls[0][1]["top_k"], 2)
        self.assertEqual(client.calls[0][1]["filters"]["operation_key"], expected["operation_key"])

    def test_find_by_operation_key_rejects_duplicate_projection(self):
        client = FakeMem0Client()
        metadata = projection_metadata()
        client.get_all_response = {
            "results": [
                {"id": "duplicate-1", "memory": "x", "metadata": metadata},
                {"id": "duplicate-2", "memory": "x", "metadata": metadata},
            ]
        }
        service = self.make_service(client)
        with self.assertRaisesRegex(ClassCommentaryMemoryResponseError, "duplicate"):
            service.find_by_operation_key(
                metadata["operation_key"],
                organization_id=4,
                memory_type="teacher_style",
                scope_skill_registry_id=8,
            )

    def test_find_by_operation_key_supports_student_scope(self):
        client = FakeMem0Client()
        metadata = projection_metadata(
            memory_type="student_fact",
            scope_skill_registry_id=None,
            student_id=21,
            subject_key="math",
            operation_key="cc-memory-21-v1-student",
        )
        client.get_all_response = {
            "results": [{"id": "student-1", "memory": "y", "metadata": metadata}]
        }
        service = self.make_service(client)

        result = service.find_by_operation_key(
            metadata["operation_key"],
            organization_id=4,
            memory_type="student_fact",
            student_id=21,
            subject_key="math",
        )

        self.assertEqual(result["id"], "student-1")
        self.assertEqual(client.calls[0][1]["filters"]["student_id"], 21)
        self.assertEqual(client.calls[0][1]["filters"]["subject_key"], "math")

    def test_get_returns_none_for_unknown_memory(self):
        client = FakeMem0Client()
        client.get_response = None
        service = self.make_service(client)

        self.assertIsNone(service.get("missing-memory"))

    def test_empty_search_queries_return_no_results_without_touching_mem0(self):
        client = FakeMem0Client()
        service = self.make_service(client)

        self.assertEqual(
            service.search_style("   ", organization_id=1, scope_skill_registry_id=2),
            [],
        )
        self.assertEqual(
            service.search_student("", organization_id=1, student_id=2, subject_key="math"),
            [],
        )
        self.assertEqual(client.calls, [])

    def test_healthcheck_runs_an_isolated_add_get_search_delete_probe(self):
        client = FakeMem0Client()
        service = self.make_service(client)
        self.assertEqual(
            service.healthcheck(),
            {"enabled": True, "healthy": True, "status": "ready"},
        )

        self.assertEqual(
            [call[0] for call in client.calls],
            ["add", "get", "search", "delete"],
        )
        add_call = client.calls[0]
        probe_user_id = add_call[2]["user_id"]
        probe_id = add_call[2]["metadata"]["healthcheck_id"]
        self.assertEqual(
            probe_user_id,
            f"cc:class-commentary-memory-healthcheck:{probe_id}",
        )
        self.assertEqual(add_call[2]["infer"], False)
        self.assertIn(probe_id, add_call[1])
        self.assertEqual(client.calls[1], ("get", "memory-1"))
        self.assertEqual(client.calls[2][0], "search")
        self.assertEqual(
            client.calls[2][2]["filters"],
            {"user_id": f"cc:class-commentary-memory-healthcheck:{probe_id}"},
        )
        self.assertEqual(client.calls[3], ("delete", "memory-1"))

    def test_healthcheck_cleans_up_after_failure_and_exposes_only_error_type(self):
        client = FakeMem0Client()

        def fail(memory_id):
            raise ConnectionError("secret-bearing server detail")

        client.get = fail
        result = self.make_service(client).healthcheck()

        self.assertEqual(
            result,
            {
                "enabled": True,
                "healthy": False,
                "status": "unavailable",
                "error_type": "ConnectionError",
            },
        )
        self.assertEqual([call[0] for call in client.calls], ["add", "delete"])
        self.assertEqual(client.calls[-1], ("delete", "memory-1"))


class ClassCommentaryMemoryTimeoutTests(unittest.TestCase):
    def _fake_memory_class(self, fake_client):
        return type(
            "FakeMemory",
            (),
            {
                "configs": [],
                "from_config": classmethod(
                    lambda cls, config: cls.configs.append(config) or fake_client
                ),
            },
        )

    def _fake_qdrant_module(self):
        calls = []

        class FakeQdrantClient:
            def __init__(self, **kwargs):
                calls.append((self, kwargs))

        fake_module = types.ModuleType("qdrant_client")
        fake_module.QdrantClient = FakeQdrantClient
        return fake_module, calls

    def test_build_client_injects_a_timed_qdrant_client_with_an_api_key(self):
        fake_client = FakeMem0Client()
        fake_mem0_module = types.ModuleType("mem0")
        fake_mem0_module.Memory = self._fake_memory_class(fake_client)
        fake_qdrant_module, qdrant_calls = self._fake_qdrant_module()
        runtime_config = {
            "class_commentary_memory_enabled": True,
            "class_commentary_provider": "openai",
            "class_commentary_model": "gpt-class-commentary",
            "mem0_qdrant_url": "http://qdrant:6333",
            "mem0_qdrant_api_key": "qdrant-key",
            "mem0_embedder_provider": "openai",
            "mem0_embedder_model": "text-embedding-3-small",
            "mem0_embedding_dims": 1536,
            "openai_api_key": "embedder-key",
            "mem0_request_timeout_seconds": 17,
        }
        with patch.dict(
            sys.modules, {"mem0": fake_mem0_module, "qdrant_client": fake_qdrant_module}
        ):
            result = ClassCommentaryMemoryService(
                runtime_config=runtime_config
            ).healthcheck()

        self.assertEqual(result["status"], "ready")
        vector_config = fake_mem0_module.Memory.configs[0]["vector_store"]["config"]
        self.assertIs(vector_config["client"], qdrant_calls[0][0])
        self.assertEqual(len(qdrant_calls), 1)
        self.assertEqual(
            qdrant_calls[0][1],
            {"url": "http://qdrant:6333", "timeout": 17, "api_key": "qdrant-key"},
        )
        self.assertNotIn("host", vector_config)
        self.assertNotIn("port", vector_config)

    def test_build_client_satisfies_keyless_qdrant_validation_with_host_and_port(self):
        fake_client = FakeMem0Client()
        fake_mem0_module = types.ModuleType("mem0")
        fake_mem0_module.Memory = self._fake_memory_class(fake_client)
        fake_qdrant_module, qdrant_calls = self._fake_qdrant_module()
        runtime_config = {
            "class_commentary_memory_enabled": True,
            "class_commentary_provider": "openai",
            "class_commentary_model": "gpt-class-commentary",
            "mem0_qdrant_url": "http://127.0.0.1:6333",
            "mem0_embedder_provider": "openai",
            "mem0_embedder_model": "text-embedding-3-small",
            "mem0_embedding_dims": 1536,
            "openai_api_key": "embedder-key",
        }
        with patch.dict(
            sys.modules, {"mem0": fake_mem0_module, "qdrant_client": fake_qdrant_module}
        ):
            result = ClassCommentaryMemoryService(
                runtime_config=runtime_config
            ).healthcheck()

        self.assertEqual(result["status"], "ready")
        vector_config = fake_mem0_module.Memory.configs[0]["vector_store"]["config"]
        self.assertEqual(vector_config["host"], "127.0.0.1")
        self.assertEqual(vector_config["port"], 6333)
        self.assertEqual(qdrant_calls[0][1]["timeout"], 30)
        self.assertNotIn("api_key", qdrant_calls[0][1])

    def test_missing_qdrant_client_package_falls_back_to_mem0_defaults(self):
        fake_client = FakeMem0Client()
        fake_mem0_module = types.ModuleType("mem0")
        fake_mem0_module.Memory = self._fake_memory_class(fake_client)
        runtime_config = {
            "class_commentary_memory_enabled": True,
            "class_commentary_provider": "openai",
            "class_commentary_model": "gpt-class-commentary",
            "mem0_qdrant_url": "http://qdrant:6333",
            "mem0_qdrant_api_key": "qdrant-key",
            "mem0_embedder_provider": "openai",
            "mem0_embedder_model": "text-embedding-3-small",
            "mem0_embedding_dims": 1536,
            "openai_api_key": "embedder-key",
        }
        with patch.dict(sys.modules, {"mem0": fake_mem0_module}):
            result = ClassCommentaryMemoryService(
                runtime_config=runtime_config
            ).healthcheck()

        self.assertEqual(result["status"], "ready")
        vector_config = fake_mem0_module.Memory.configs[0]["vector_store"]["config"]
        self.assertNotIn("client", vector_config)

    def test_openai_clients_are_rebuilt_with_a_request_timeout(self):
        calls = []
        instances = []

        class FakeOpenAI:
            def __init__(self, api_key=None, base_url=None, timeout=None, max_retries=None):
                self.api_key = api_key
                self.base_url = base_url
                self.timeout = timeout
                self.max_retries = max_retries
                calls.append(
                    {
                        "api_key": api_key,
                        "base_url": base_url,
                        "timeout": timeout,
                        "max_retries": max_retries,
                    }
                )
                instances.append(self)

        fake_openai_module = types.ModuleType("openai")
        fake_openai_module.OpenAI = FakeOpenAI

        from class_commentary_memory import _apply_openai_http_timeouts

        class FakeComponent:
            pass

        class FakeMemory:
            def __init__(self):
                self.embedding_model = FakeComponent()
                self.embedding_model.client = FakeOpenAI(
                    api_key="embedding-secret",
                    base_url="https://embedding.example/v1",
                )
                self.llm = FakeComponent()
                self.llm.client = FakeOpenAI(
                    api_key="llm-secret", base_url="https://llm.example/v1"
                )

        memory = FakeMemory()
        original_clients = (memory.embedding_model.client, memory.llm.client)
        with patch.dict(sys.modules, {"openai": fake_openai_module}):
            _apply_openai_http_timeouts(memory, 23)

        self.assertEqual(len(calls), 4)  # two originals + two rebuilds
        rebuilt = calls[2:]
        self.assertEqual(rebuilt[0]["api_key"], "embedding-secret")
        self.assertEqual(rebuilt[0]["base_url"], "https://embedding.example/v1")
        self.assertEqual(rebuilt[0]["max_retries"], 2)
        self.assertEqual(rebuilt[0]["timeout"].read, 23)
        self.assertEqual(rebuilt[1]["api_key"], "llm-secret")
        self.assertIs(memory.embedding_model.client, instances[2])
        self.assertIs(memory.llm.client, instances[3])
        self.assertNotIn(memory.embedding_model.client, original_clients)
        self.assertNotIn(memory.llm.client, original_clients)


if __name__ == "__main__":
    unittest.main()
