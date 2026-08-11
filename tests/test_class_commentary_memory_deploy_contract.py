import ast
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import textwrap
import unittest

from scripts.check_class_commentary_graph_deploy import validate_rebuild_health


ROOT = Path(__file__).resolve().parents[1]


class ClassCommentaryMemoryDeployContractTests(unittest.TestCase):
    def _write_executable(self, path, content):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")
        path.chmod(0o755)

    def _make_deploy_fixture(
        self,
        temp_root,
        *,
        existing_processes,
        memory_enabled=True,
        graph_enabled=False,
    ):
        script = temp_root / "scripts" / "deploy_backend.sh"
        script.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / "scripts" / "deploy_backend.sh", script)
        script.chmod(0o755)

        python = temp_root / ".venv" / "bin" / "python"
        self._write_executable(
            python,
            """
            #!/bin/sh
            if [ "${1:-}" = "--version" ]; then
              echo "Python 3.12.13"
              exit 0
            fi
            if [ "${1:-}" = "-c" ]; then
              case "${2:-}" in
                *class_commentary_memory_enabled*)
                  if [ "$FAKE_MEMORY_ENABLED" = "1" ]; then exit 0; else exit 1; fi
                  ;;
                *class_commentary_graph_enabled*)
                  if [ "$FAKE_GRAPH_ENABLED" = "1" ]; then exit 0; else exit 1; fi
                  ;;
              esac
              cat >/dev/null || true
              exit 0
            fi
            if [ "${1:-}" = "-" ]; then
              cat >/dev/null || true
              echo '{"memory":"ready","redis":"ready"}'
              exit 0
            fi
            exit 0
            """,
        )

        fake_bin = temp_root / "fake-bin"
        pm2_log = temp_root / "pm2.log"
        pm2_state = temp_root / "pm2-worker-state"
        pm2_state.write_text("online", encoding="utf-8")
        self._write_executable(
            fake_bin / "pm2",
            """
            #!/bin/sh
            echo "$*" >> "$PM2_LOG"
            case "${1:-}" in
              describe)
                if [ "$PM2_EXISTING" = "1" ]; then exit 0; else exit 1; fi
                ;;
              stop)
                printf 'stopped' > "$PM2_STATE"
                ;;
              start|restart)
                case "$*" in
                  *xingrun-class-commentary-memory-worker*)
                    printf 'online' > "$PM2_STATE"
                    ;;
                esac
                ;;
              jlist)
                worker_status="$(cat "$PM2_STATE")"
                printf '[{"name":"xingrun","pm2_env":{"status":"online","kill_timeout":1600}},{"name":"xingrun-class-commentary-memory-worker","pm2_env":{"status":"%s","kill_timeout":330000}}]\n' "$worker_status"
                ;;
            esac
            exit 0
            """,
        )
        self._write_executable(
            fake_bin / "curl",
            """
            #!/bin/sh
            printf '302'
            """,
        )

        env = os.environ.copy()
        env.update(
            {
                "PATH": f"{fake_bin}:{env['PATH']}",
                "PM2_LOG": str(pm2_log),
                "PM2_STATE": str(pm2_state),
                "PM2_EXISTING": "1" if existing_processes else "0",
                "FAKE_MEMORY_ENABLED": "1" if memory_enabled else "0",
                "FAKE_GRAPH_ENABLED": "1" if graph_enabled else "0",
                "XR_PYTHON_BIN": str(python),
                "XR_SKIP_GIT_SYNC": "1",
                "XR_CLASS_COMMENTARY_MEMORY_ENABLED": "1" if memory_enabled else "0",
                "XR_CLASS_COMMENTARY_GRAPH_ENABLED": "1" if graph_enabled else "0",
            }
        )
        return script, env, pm2_log

    def test_deploy_uses_pm2_for_existing_and_first_release_processes(self):
        for existing_processes in (True, False):
            with self.subTest(existing_processes=existing_processes), tempfile.TemporaryDirectory() as temp_dir:
                temp_root = Path(temp_dir)
                script, env, pm2_log = self._make_deploy_fixture(
                    temp_root,
                    existing_processes=existing_processes,
                )
                result = subprocess.run(
                    ["bash", str(script)],
                    cwd=temp_root,
                    env=env,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                output = result.stdout + result.stderr

                self.assertEqual(result.returncode, 0, output)
                commands = pm2_log.read_text(encoding="utf-8")
                if existing_processes:
                    self.assertIn("restart xingrun --update-env", commands)
                    self.assertIn(
                        "restart xingrun-class-commentary-memory-worker --update-env --kill-timeout 330000",
                        commands,
                    )
                else:
                    self.assertIn("start " + str(temp_root / "scripts" / "run_backend.sh"), commands)
                    self.assertIn(
                        "--name xingrun-class-commentary-memory-worker --interpreter bash --kill-timeout 330000",
                        commands,
                    )
                self.assertIn("save", commands)
                self.assertIn("Deploy complete", output)

    def test_deploy_with_memory_disabled_stops_existing_worker_and_skips_capability_gate(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            script, env, pm2_log = self._make_deploy_fixture(
                temp_root,
                existing_processes=True,
                memory_enabled=False,
            )
            env["XR_CLASS_COMMENTARY_MEMORY_WORKER_KILL_TIMEOUT"] = "1"
            result = subprocess.run(
                ["bash", str(script)],
                cwd=temp_root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            output = result.stdout + result.stderr

            self.assertEqual(result.returncode, 0, output)
            commands = pm2_log.read_text(encoding="utf-8")
            self.assertIn("restart xingrun --update-env", commands)
            self.assertIn("stop xingrun-class-commentary-memory-worker", commands)
            self.assertNotIn("restart xingrun-class-commentary-memory-worker", commands)
            self.assertIn("skipping Mem0, Qdrant, Redis, and RQ checks", output)
            self.assertIn("class commentary memory is disabled", output)
            self.assertIn("save", commands)

    def test_deploy_with_graph_only_keeps_shared_worker_online(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            script, env, pm2_log = self._make_deploy_fixture(
                temp_root,
                existing_processes=True,
                memory_enabled=False,
                graph_enabled=True,
            )
            result = subprocess.run(
                ["bash", str(script)],
                cwd=temp_root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            output = result.stdout + result.stderr

            self.assertEqual(result.returncode, 0, output)
            commands = pm2_log.read_text(encoding="utf-8")
            self.assertIn(
                "restart xingrun-class-commentary-memory-worker --update-env",
                commands,
            )
            self.assertNotIn("stop xingrun-class-commentary-memory-worker", commands)
            self.assertIn("skipping Mem0, Qdrant, Redis, and RQ checks", output)
            self.assertIn("Checking class commentary graph capability", output)
            self.assertIn("class commentary worker are healthy", output)

    def test_graph_deploy_gate_rejects_partial_rebuild_health(self):
        rebuild = {
            "event_count": 2,
            "node_count": 2250,
            "edge_count": 4020,
            "curriculum_node_count": 2237,
            "curriculum_edge_count": 4007,
            "store_hash": "expected-store-hash",
        }
        validate_rebuild_health(rebuild, dict(rebuild, healthy=True))

        with self.assertRaisesRegex(SystemExit, "curriculum_node_count"):
            validate_rebuild_health(
                rebuild,
                dict(rebuild, healthy=True, curriculum_node_count=2236),
            )

    def test_deploy_rejects_short_worker_kill_timeout_before_pm2(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            script, env, pm2_log = self._make_deploy_fixture(
                temp_root,
                existing_processes=True,
            )
            env["XR_CLASS_COMMENTARY_MEMORY_WORKER_KILL_TIMEOUT"] = "329999"
            result = subprocess.run(
                ["bash", str(script)],
                cwd=temp_root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            output = result.stdout + result.stderr

            self.assertNotEqual(result.returncode, 0, output)
            self.assertIn("at least 330000 ms", output)
            self.assertFalse(pm2_log.exists())

    def test_deploy_script_has_no_second_process_manager_path(self):
        deploy = (ROOT / "scripts" / "deploy_backend.sh").read_text(encoding="utf-8")

        self.assertTrue(os.access(ROOT / "scripts" / "deploy_backend.sh", os.X_OK))
        self.assertNotIn("nohup", deploy)
        self.assertNotIn("backend.pid", deploy)
        self.assertIn("ClassCommentaryMemoryService", deploy)
        self.assertIn("课堂点评中文检索部署探针", deploy)
        self.assertIn("ScheduledJobRegistry", deploy)
        self.assertIn("desired_status=applied_status", deploy)
        self.assertIn('[[ "$HTTP_STATUS" == "302" ]]', deploy)
        self.assertIn("if (( MEMORY_ENABLED )); then", deploy)
        self.assertIn('pm2 stop "$MEMORY_PROCESS_NAME"', deploy)
        self.assertIn("skipping Mem0, Qdrant, Redis, and RQ checks", deploy)

        inline_python = re.findall(
            r"\.venv/bin/python - <<'PY'\n(.*?)\nPY",
            deploy,
            flags=re.DOTALL,
        )
        self.assertEqual(len(inline_python), 2)
        for source in inline_python:
            ast.parse(source)

    def test_deploy_runbook_covers_dual_process_health_and_rollback(self):
        runbook = (ROOT / "deploy-release.md").read_text(encoding="utf-8")

        self.assertNotIn("***REMOVED-ROTATED-SSH-PASSWORD***", runbook)
        self.assertIn("Python 3.12", runbook)
        self.assertIn("scripts/deploy_backend.sh", runbook)
        self.assertIn("xingrun-class-commentary-memory-worker", runbook)
        self.assertIn("302", runbook)
        self.assertIn("回滚", runbook)
        self.assertIn("migration-first", runbook)
        self.assertIn("stopped", runbook)


if __name__ == "__main__":
    unittest.main()
