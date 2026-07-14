import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ClassCommentaryMemoryDependencyContractTests(unittest.TestCase):
    def _copy_script(self, temp_root, relative_path):
        destination = temp_root / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative_path, destination)
        return destination

    def _write_fake_python(self, path, version, accepts_python_312, marker):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "#!/bin/sh\n"
            "if [ \"${1:-}\" = \"--version\" ]; then\n"
            f"  echo \"Python {version}\"\n"
            "  exit 0\n"
            "fi\n"
            "if [ \"${1:-}\" = \"-c\" ]; then\n"
            f"  exit {0 if accepts_python_312 else 1}\n"
            "fi\n"
            f"echo \"$*\" >> \"{marker}\"\n"
            "exit 89\n",
            encoding="utf-8",
        )
        path.chmod(0o755)

    def _run_script(self, script, temp_root, python_bin=None):
        env = os.environ.copy()
        if python_bin is not None:
            env["XR_PYTHON_BIN"] = str(python_bin)
        return subprocess.run(
            ["bash", str(script)],
            cwd=temp_root,
            env=env,
            input="\n",
            capture_output=True,
            text=True,
            check=False,
        )

    def test_python_and_memory_dependencies_are_pinned(self):
        requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()

        self.assertEqual((ROOT / ".python-version").read_text(encoding="utf-8").strip(), "3.12.13")
        self.assertIn("openai>=1.90.0", requirements)
        self.assertIn("pydantic>=2.7.3", requirements)
        self.assertIn("mem0ai==2.0.12", requirements)
        self.assertIn("qdrant-client==1.18.0", requirements)

    def test_readme_rejects_embedded_qdrant_for_production(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("Python 3.12.x", readme)
        self.assertIn("Qdrant embedded `path` 模式只用于单进程本地测试", readme)
        self.assertIn("生产环境必须运行独立的 Qdrant server", readme)

    def test_launchers_reject_non_312_base_interpreter(self):
        for relative_path in ("start.command", "scripts/deploy_backend.sh"):
            with self.subTest(script=relative_path), tempfile.TemporaryDirectory() as temp_dir:
                temp_root = Path(temp_dir)
                script = self._copy_script(temp_root, relative_path)
                marker = temp_root / "unexpected-python-invocation"
                python_bin = temp_root / "python3"
                self._write_fake_python(python_bin, "3.9.18", False, marker)

                result = self._run_script(script, temp_root, python_bin)
                output = result.stdout + result.stderr

                self.assertNotEqual(result.returncode, 0, output)
                self.assertIn("Python 3.12.x", output)
                self.assertIn("Python 3.9.18", output)
                self.assertFalse((temp_root / ".venv").exists())
                self.assertFalse(marker.exists())

    def test_launchers_reject_existing_python_39_venv(self):
        relative_paths = (
            "start.command",
            "scripts/deploy_backend.sh",
            "scripts/run_class_commentary_memory_worker.sh",
        )
        for relative_path in relative_paths:
            with self.subTest(script=relative_path), tempfile.TemporaryDirectory() as temp_dir:
                temp_root = Path(temp_dir)
                script = self._copy_script(temp_root, relative_path)
                marker = temp_root / "unexpected-python-invocation"
                python_bin = temp_root / "python3"
                venv_python = temp_root / ".venv" / "bin" / "python"
                self._write_fake_python(python_bin, "3.12.13", True, marker)
                self._write_fake_python(venv_python, "3.9.18", False, marker)

                result = self._run_script(script, temp_root, python_bin)
                output = result.stdout + result.stderr

                self.assertNotEqual(result.returncode, 0, output)
                self.assertIn("Existing .venv uses Python 3.9.18", output)
                self.assertIn("Python 3.12.x is required", output)
                self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()
