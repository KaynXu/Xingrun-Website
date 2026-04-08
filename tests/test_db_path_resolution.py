import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import lesson_manager


class DatabasePathResolutionTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        self.data_dir = self.base / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_prefers_explicit_runtime_config_path(self):
        resolved = lesson_manager.resolve_db_path(
            runtime_config={"db_path": "custom/runtime.sqlite3"},
            base_dir=self.base,
            data_dir=self.data_dir,
        )

        self.assertEqual(resolved, self.base / "custom" / "runtime.sqlite3")

    def test_uses_xingrun_db_when_present(self):
        preferred_path = self.data_dir / "xingrun.db"
        preferred_path.write_text("", encoding="utf-8")
        (self.data_dir / "lessons.db").write_text("", encoding="utf-8")

        resolved = lesson_manager.resolve_db_path(
            runtime_config={},
            base_dir=self.base,
            data_dir=self.data_dir,
        )

        self.assertEqual(resolved, preferred_path)

    def test_falls_back_to_legacy_lessons_db_when_needed(self):
        legacy_path = self.data_dir / "lessons.db"
        legacy_path.write_text("", encoding="utf-8")

        resolved = lesson_manager.resolve_db_path(
            runtime_config={},
            base_dir=self.base,
            data_dir=self.data_dir,
        )

        self.assertEqual(resolved, legacy_path)

    def test_uses_xingrun_db_for_fresh_install(self):
        resolved = lesson_manager.resolve_db_path(
            runtime_config={},
            base_dir=self.base,
            data_dir=self.data_dir,
        )

        self.assertEqual(resolved, self.data_dir / "xingrun.db")


if __name__ == "__main__":
    unittest.main()
