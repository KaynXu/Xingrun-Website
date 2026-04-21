import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class RuntimeConfigHygieneTestCase(unittest.TestCase):
    def git_ls_files(self, path: str) -> list[str]:
        result = subprocess.run(
            ["git", "ls-files", path],
            cwd=ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        return [line for line in result.stdout.splitlines() if line.strip()]

    def test_runtime_config_file_is_not_tracked_by_git(self):
        self.assertEqual(self.git_ls_files("config.json"), [])

    def test_runtime_config_example_uses_placeholder_secrets(self):
        example = (ROOT / ".env.runtime.example").read_text(encoding="utf-8")

        self.assertIn("N1N_API_KEY=your_n1n_api_key", example)
        self.assertNotRegex(example, r"sk-[A-Za-z0-9]{20,}")


if __name__ == "__main__":
    unittest.main()
