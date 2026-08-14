import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import config_runtime


class ClassCommentaryMemoryRuntimeTest(unittest.TestCase):
    def test_memory_runtime_is_disabled_and_uses_safe_defaults(self):
        with tempfile.TemporaryDirectory() as tmpdir, patch.object(
            config_runtime,
            "CFG_PATH",
            Path(tmpdir) / "config.json",
        ), patch.dict(os.environ, {}, clear=True):
            cfg = config_runtime.get_runtime_config()

        self.assertFalse(cfg["class_commentary_memory_enabled"])
        self.assertEqual(cfg["class_commentary_memory_queue"], "class_commentary_memory")
        self.assertEqual(cfg["class_commentary_memory_extraction_timeout"], 300)
        self.assertEqual(cfg["class_commentary_memory_operation_timeout"], 120)
        self.assertEqual(cfg["class_commentary_memory_reconcile_interval"], 600)
        self.assertEqual(cfg["class_commentary_memory_reconcile_timeout"], 300)
        self.assertEqual(cfg["mem0_style_limit"], 8)
        self.assertEqual(cfg["mem0_student_limit"], 5)
        self.assertEqual(cfg["mem0_context_char_limit"], 3000)
        self.assertEqual(cfg["mem0_request_timeout_seconds"], 30)

    def test_memory_runtime_uses_the_shared_environment_contract(self):
        environment = {
            "XR_CLASS_COMMENTARY_MEMORY_ENABLED": "true",
            "XR_REDIS_URL": "redis://memory.test:6380/3",
            "XR_CLASS_COMMENTARY_MEMORY_QUEUE": "commentary-test",
            "XR_CLASS_COMMENTARY_MEMORY_EXTRACTION_TIMEOUT": "420",
            "XR_CLASS_COMMENTARY_MEMORY_OPERATION_TIMEOUT": "150",
            "XR_CLASS_COMMENTARY_MEMORY_RECONCILE_INTERVAL": "900",
            "XR_CLASS_COMMENTARY_MEMORY_RECONCILE_TIMEOUT": "240",
            "XR_MEM0_VECTOR_PROVIDER": "qdrant",
            "XR_MEM0_QDRANT_URL": "http://qdrant.test:6333",
            "XR_MEM0_QDRANT_API_KEY": "qdrant-secret",
            "XR_MEM0_COLLECTION_NAME": "commentary-test",
            "XR_MEM0_EMBEDDER_PROVIDER": "openai",
            "XR_MEM0_EMBEDDER_MODEL": "text-embedding-3-small",
            "XR_MEM0_EMBEDDER_API_KEY": "embedding-secret",
            "XR_MEM0_EMBEDDER_BASE_URL": "https://embedding.test/v1",
            "XR_MEM0_EMBEDDING_DIMS": "1536",
            "XR_MEM0_STYLE_LIMIT": "9",
            "XR_MEM0_STUDENT_LIMIT": "6",
            "XR_MEM0_CONTEXT_CHAR_LIMIT": "3600",
            "XR_MEM0_REQUEST_TIMEOUT_SECONDS": "45",
            "XR_SKILL_EVOLUTION_MIN_EFFECTIVE_TASKS": "7",
            "XR_SKILL_EVOLUTION_MIN_SUPPORT_TASKS": "4",
            "XR_SKILL_EVOLUTION_BUILD_TIMEOUT": "360",
        }
        with tempfile.TemporaryDirectory() as tmpdir, patch.object(
            config_runtime,
            "CFG_PATH",
            Path(tmpdir) / "config.json",
        ), patch.dict(os.environ, environment, clear=True):
            cfg = config_runtime.get_runtime_config()

        self.assertTrue(cfg["class_commentary_memory_enabled"])
        self.assertEqual(cfg["redis_url"], "redis://memory.test:6380/3")
        self.assertEqual(cfg["class_commentary_memory_queue"], "commentary-test")
        self.assertEqual(cfg["class_commentary_memory_extraction_timeout"], 420)
        self.assertEqual(cfg["class_commentary_memory_operation_timeout"], 150)
        self.assertEqual(cfg["class_commentary_memory_reconcile_interval"], 900)
        self.assertEqual(cfg["class_commentary_memory_reconcile_timeout"], 240)
        self.assertEqual(cfg["mem0_qdrant_url"], "http://qdrant.test:6333")
        self.assertEqual(cfg["mem0_qdrant_api_key"], "qdrant-secret")
        self.assertEqual(cfg["mem0_collection_name"], "commentary-test")
        self.assertEqual(cfg["mem0_embedder_provider"], "openai")
        self.assertEqual(cfg["mem0_embedder_model"], "text-embedding-3-small")
        self.assertEqual(cfg["mem0_embedder_api_key"], "embedding-secret")
        self.assertEqual(cfg["mem0_embedder_base_url"], "https://embedding.test/v1")
        self.assertEqual(cfg["mem0_embedding_dims"], 1536)
        self.assertEqual(cfg["mem0_style_limit"], 9)
        self.assertEqual(cfg["mem0_student_limit"], 6)
        self.assertEqual(cfg["mem0_context_char_limit"], 3600)
        self.assertEqual(cfg["mem0_request_timeout_seconds"], 45)
        self.assertEqual(cfg["skill_evolution_min_effective_tasks"], 7)
        self.assertEqual(cfg["skill_evolution_min_support_tasks"], 4)
        self.assertEqual(cfg["skill_evolution_build_timeout"], 360)


if __name__ == "__main__":
    unittest.main()
