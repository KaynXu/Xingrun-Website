import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from scripts import check_class_commentary_graph_deploy as deploy_check


class ClassCommentaryGraphDeployCheckTests(unittest.TestCase):
    def test_rejects_disabled_graph_and_enabled_explorer(self):
        with mock.patch.object(
            deploy_check.config_runtime,
            "get_runtime_config",
            return_value={"class_commentary_graph_enabled": False},
        ):
            with self.assertRaisesRegex(SystemExit, "GRAPH_ENABLED"):
                deploy_check.main()

        with mock.patch.object(
            deploy_check.config_runtime,
            "get_runtime_config",
            return_value={
                "class_commentary_graph_enabled": True,
                "class_commentary_graph_explorer_enabled": True,
            },
        ):
            with self.assertRaisesRegex(SystemExit, "EXPLORER_ENABLED"):
                deploy_check.main()

    def test_rejects_relative_store_path(self):
        with mock.patch.object(
            deploy_check.config_runtime,
            "get_runtime_config",
            return_value={
                "class_commentary_graph_enabled": True,
                "class_commentary_graph_explorer_enabled": False,
                "class_commentary_graph_store_path": "relative/graph.json",
            },
        ):
            with self.assertRaisesRegex(SystemExit, "absolute path"):
                deploy_check.main()

    def test_rebuild_health_requires_exact_counts_and_store_hash(self):
        rebuild = {
            "event_count": 2,
            "node_count": 2250,
            "edge_count": 4020,
            "curriculum_node_count": 2237,
            "curriculum_edge_count": 4007,
            "store_hash": "expected",
        }
        deploy_check.validate_rebuild_health(rebuild, dict(rebuild, healthy=True))
        with self.assertRaisesRegex(SystemExit, "curriculum_edge_count"):
            deploy_check.validate_rebuild_health(
                rebuild,
                dict(rebuild, healthy=True, curriculum_edge_count=4006),
            )
        with self.assertRaisesRegex(SystemExit, "store hash"):
            deploy_check.validate_rebuild_health(
                rebuild,
                dict(rebuild, healthy=True, store_hash="partial"),
            )

    def test_happy_path_rebuilds_and_schedules_reconciliation(self):
        rebuild = {
            "event_count": 2,
            "node_count": 2250,
            "edge_count": 4020,
            "curriculum_node_count": 2237,
            "curriculum_edge_count": 4007,
            "store_hash": "expected",
        }

        class FakeAdapter:
            def health(self):
                return {**rebuild, "healthy": True, "semantica_version": "0.6.0"}

            def store_hash(self):
                return "expected"

        with tempfile.TemporaryDirectory() as temp_dir:
            config = {
                "class_commentary_graph_enabled": True,
                "class_commentary_graph_explorer_enabled": False,
                "class_commentary_graph_store_path": str(Path(temp_dir) / "graph.json"),
                "class_commentary_graph_timeout": 10,
            }
            with (
                mock.patch.object(
                    deploy_check.config_runtime,
                    "get_runtime_config",
                    return_value=config,
                ),
                mock.patch.object(
                    deploy_check,
                    "SemanticaGraphAdapter",
                    return_value=FakeAdapter(),
                ),
                mock.patch.object(
                    deploy_check,
                    "rebuild_semantica_graph",
                    return_value=rebuild,
                ) as rebuild_mock,
                mock.patch.object(
                    deploy_check,
                    "get_class_commentary_memory_redis_connection",
                    return_value=object(),
                ),
                mock.patch.object(
                    deploy_check,
                    "get_class_commentary_memory_queue",
                    return_value=object(),
                ),
                mock.patch.object(
                    deploy_check,
                    "class_commentary_memory_queue_healthcheck",
                    return_value={"healthy": True, "worker_count": 1},
                ),
                mock.patch.object(
                    deploy_check,
                    "ensure_class_commentary_graph_reconciliation_scheduled",
                    return_value={"job_id": "cc-graph-reconcile-1"},
                ) as schedule_mock,
                contextlib.redirect_stdout(io.StringIO()) as stdout,
            ):
                self.assertEqual(deploy_check.main(), 0)

        rebuild_mock.assert_called_once()
        schedule_mock.assert_called_once()
        self.assertIn('"curriculum_node_count": 2237', stdout.getvalue())
        self.assertIn('"explorer_enabled": false', stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
