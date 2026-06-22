import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import config_runtime
import lesson_manager


LEGACY_ARTIFACT_COLUMNS = {
    "plan_json",
    "pdf_path",
    "record_status",
    "generation_error",
    "review_audio_path",
    "review_audio_request_key",
    "review_request_key",
    "review_request_id",
    "review_chat_provider",
    "review_chat_model",
    "review_same_lesson_materials_json",
}


def _legacy_conn(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE lessons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER,
            date TEXT NOT NULL,
            subject TEXT,
            grade TEXT,
            topic TEXT,
            summary TEXT,
            weak_points TEXT,
            plan_json TEXT,
            pdf_path TEXT,
            class_id INTEGER,
            record_status TEXT NOT NULL DEFAULT 'ready',
            generation_error TEXT NOT NULL DEFAULT '',
            created_by_user_id INTEGER NOT NULL DEFAULT 0,
            review_audio_path TEXT NOT NULL DEFAULT '',
            review_audio_request_key TEXT NOT NULL DEFAULT '',
            review_request_key TEXT NOT NULL DEFAULT '',
            review_request_id TEXT NOT NULL DEFAULT '',
            review_chat_provider TEXT NOT NULL DEFAULT '',
            review_chat_model TEXT NOT NULL DEFAULT '',
            review_same_lesson_materials_json TEXT NOT NULL DEFAULT '[]',
            created_at TEXT DEFAULT '2026-04-09 10:00:00'
        );
        """
    )
    return conn


class ReviewPlanVersionMigrationTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        lesson_manager.DB_PATH = self.base / "xingrun.db"
        config_runtime.CFG_PATH = self.base / "config.json"
        config_runtime.write_file_config({})

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_migrates_ready_legacy_lesson_to_current_version_and_removes_columns(self):
        conn = _legacy_conn(lesson_manager.DB_PATH)
        plan = {"lesson_info": {"topic": "旧计划"}, "days": []}
        conn.execute(
            """
            INSERT INTO lessons (
                organization_id, date, subject, grade, topic, summary, weak_points,
                plan_json, pdf_path, record_status, generation_error, created_by_user_id,
                review_audio_path, review_audio_request_key,
                review_request_key, review_request_id, review_chat_provider, review_chat_model,
                review_same_lesson_materials_json
            )
            VALUES (1, '2026-04-09', '数学', '初二', '一次函数', '课堂总结', '斜率',
                    ?, '/tmp/legacy-ready.pdf', 'ready', '', 7,
                    '/tmp/legacy-audio.m4a', 'legacy-audio-key',
                    'legacy-key', 'legacy-id', 'openai', 'gpt-5.4', ?)
            """,
            (
                json.dumps(plan, ensure_ascii=False),
                json.dumps(["补充材料"], ensure_ascii=False),
            ),
        )
        conn.commit()

        lesson_manager._ensure_review_plan_versions_schema(conn)
        lesson_manager._migrate_legacy_review_plan_columns(conn)
        lesson_manager._rebuild_lessons_without_review_plan_artifact_columns(conn)
        conn.commit()

        lesson_cols = {row["name"] for row in conn.execute("PRAGMA table_info(lessons)").fetchall()}
        self.assertFalse(LEGACY_ARTIFACT_COLUMNS & lesson_cols)
        self.assertIn("current_review_plan_version_id", lesson_cols)

        lesson = conn.execute("SELECT * FROM lessons WHERE id=1").fetchone()
        version = conn.execute("SELECT * FROM review_plan_versions WHERE lesson_id=1").fetchone()
        self.assertIsNotNone(version)
        self.assertEqual(version["version_no"], 1)
        self.assertEqual(version["status"], "ready")
        self.assertEqual(json.loads(version["plan_json"]), plan)
        self.assertEqual(version["pdf_path"], "/tmp/legacy-ready.pdf")
        self.assertEqual(version["audio_path"], "/tmp/legacy-audio.m4a")
        self.assertEqual(version["audio_request_key"], "legacy-audio-key")
        self.assertEqual(version["request_key"], "legacy-key")
        self.assertEqual(version["request_id"], "legacy-id")
        self.assertEqual(version["chat_provider"], "openai")
        self.assertEqual(version["chat_model"], "gpt-5.4")
        self.assertEqual(json.loads(version["same_lesson_materials_json"]), ["补充材料"])
        self.assertEqual(lesson["current_review_plan_version_id"], version["id"])

    def test_migrates_failed_legacy_lesson_without_current_pointer(self):
        conn = _legacy_conn(lesson_manager.DB_PATH)
        conn.execute(
            """
            INSERT INTO lessons (
                organization_id, date, subject, grade, topic, summary, weak_points,
                plan_json, pdf_path, record_status, generation_error, created_by_user_id
            )
            VALUES (1, '2026-04-09', '数学', '初二', '一次函数', '课堂总结', '斜率',
                    '', '', 'failed', 'AI 生成失败', 7)
            """
        )
        conn.commit()

        lesson_manager._ensure_review_plan_versions_schema(conn)
        lesson_manager._migrate_legacy_review_plan_columns(conn)
        lesson_manager._rebuild_lessons_without_review_plan_artifact_columns(conn)
        conn.commit()

        lesson = conn.execute("SELECT * FROM lessons WHERE id=1").fetchone()
        version = conn.execute("SELECT * FROM review_plan_versions WHERE lesson_id=1").fetchone()
        self.assertIsNotNone(version)
        self.assertEqual(version["status"], "failed")
        self.assertEqual(version["generation_error"], "AI 生成失败")
        self.assertIsNone(lesson["current_review_plan_version_id"])

    def test_does_not_migrate_empty_ready_legacy_lesson_to_bogus_version(self):
        conn = _legacy_conn(lesson_manager.DB_PATH)
        conn.execute(
            """
            INSERT INTO lessons (
                organization_id, date, subject, grade, topic, summary, weak_points,
                plan_json, pdf_path, record_status, generation_error, created_by_user_id
            )
            VALUES (1, '2026-04-09', '数学', '初二', '一次函数', '课堂总结', '斜率',
                    '', '', 'ready', '', 7)
            """
        )
        conn.commit()

        lesson_manager._ensure_review_plan_versions_schema(conn)
        lesson_manager._migrate_legacy_review_plan_columns(conn)
        lesson_manager._rebuild_lessons_without_review_plan_artifact_columns(conn)
        conn.commit()

        lesson = conn.execute("SELECT * FROM lessons WHERE id=1").fetchone()
        version_count = conn.execute(
            "SELECT COUNT(*) AS count FROM review_plan_versions WHERE lesson_id=1"
        ).fetchone()["count"]
        self.assertEqual(version_count, 0)
        self.assertIsNone(lesson["current_review_plan_version_id"])

    def test_migration_is_idempotent(self):
        conn = _legacy_conn(lesson_manager.DB_PATH)
        conn.execute(
            """
            INSERT INTO lessons (
                organization_id, date, subject, grade, topic, summary, weak_points,
                plan_json, pdf_path, record_status, generation_error, created_by_user_id
            )
            VALUES (1, '2026-04-09', '数学', '初二', '一次函数', '课堂总结', '斜率',
                    '{"days":[]}', '/tmp/legacy-ready.pdf', 'ready', '', 7)
            """
        )
        conn.commit()

        for _ in range(2):
            lesson_manager._ensure_review_plan_versions_schema(conn)
            lesson_manager._migrate_legacy_review_plan_columns(conn)
            lesson_manager._rebuild_lessons_without_review_plan_artifact_columns(conn)
            conn.commit()

        count = conn.execute("SELECT COUNT(*) AS count FROM review_plan_versions").fetchone()["count"]
        lesson = conn.execute("SELECT * FROM lessons WHERE id=1").fetchone()
        version = conn.execute("SELECT * FROM review_plan_versions WHERE lesson_id=1").fetchone()
        self.assertEqual(count, 1)
        self.assertEqual(lesson["current_review_plan_version_id"], version["id"])

    def test_init_db_runs_legacy_review_plan_version_migration(self):
        conn = _legacy_conn(lesson_manager.DB_PATH)
        ready_plan = {"lesson_info": {"topic": "旧计划"}, "days": []}
        conn.execute(
            """
            INSERT INTO lessons (
                organization_id, date, subject, grade, topic, summary, weak_points,
                plan_json, pdf_path, record_status, generation_error, created_by_user_id
            )
            VALUES (1, '2026-04-09', '数学', '初二', '一次函数', '课堂总结', '斜率',
                    ?, '/tmp/init-ready.pdf', 'ready', '', 7)
            """,
            (json.dumps(ready_plan, ensure_ascii=False),),
        )
        ready_lesson_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
        conn.execute(
            """
            INSERT INTO lessons (
                organization_id, date, subject, grade, topic, summary, weak_points,
                plan_json, pdf_path, record_status, generation_error, created_by_user_id
            )
            VALUES (1, '2026-04-10', '数学', '初二', '二次函数', '课堂总结', '顶点式',
                    '', '', 'failed', 'AI 生成失败', 7)
            """
        )
        failed_lesson_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
        conn.execute(
            """
            INSERT INTO lessons (
                organization_id, date, subject, grade, topic, summary, weak_points,
                plan_json, pdf_path, record_status, generation_error, created_by_user_id
            )
            VALUES (1, '2026-04-11', '数学', '初二', '空记录', '课堂总结', '待补充',
                    '', '', 'ready', '', 7)
            """
        )
        empty_lesson_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
        conn.commit()
        conn.close()

        lesson_manager.init_db()

        with lesson_manager.get_conn() as fresh:
            versions = fresh.execute("SELECT * FROM review_plan_versions ORDER BY lesson_id").fetchall()
            self.assertEqual(len(versions), 2)

            lesson_cols = {row["name"] for row in fresh.execute("PRAGMA table_info(lessons)").fetchall()}
            self.assertFalse(LEGACY_ARTIFACT_COLUMNS & lesson_cols)
            self.assertIn("current_review_plan_version_id", lesson_cols)

            ready_version = fresh.execute(
                "SELECT * FROM review_plan_versions WHERE lesson_id=?",
                (ready_lesson_id,),
            ).fetchone()
            failed_version = fresh.execute(
                "SELECT * FROM review_plan_versions WHERE lesson_id=?",
                (failed_lesson_id,),
            ).fetchone()
            ready_lesson = fresh.execute("SELECT * FROM lessons WHERE id=?", (ready_lesson_id,)).fetchone()
            failed_lesson = fresh.execute("SELECT * FROM lessons WHERE id=?", (failed_lesson_id,)).fetchone()
            empty_lesson = fresh.execute("SELECT * FROM lessons WHERE id=?", (empty_lesson_id,)).fetchone()
            empty_version = fresh.execute(
                "SELECT * FROM review_plan_versions WHERE lesson_id=?",
                (empty_lesson_id,),
            ).fetchone()

            self.assertEqual(ready_version["status"], "ready")
            self.assertEqual(json.loads(ready_version["plan_json"]), ready_plan)
            self.assertEqual(ready_version["pdf_path"], "/tmp/init-ready.pdf")
            self.assertEqual(ready_lesson["current_review_plan_version_id"], ready_version["id"])
            self.assertEqual(failed_version["status"], "failed")
            self.assertEqual(failed_version["generation_error"], "AI 生成失败")
            self.assertIsNone(failed_lesson["current_review_plan_version_id"])
            self.assertIsNone(empty_version)
            self.assertIsNone(empty_lesson["current_review_plan_version_id"])


class ReviewPlanVersionLifecycleTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        base = Path(self.temp_dir.name)
        lesson_manager.DB_PATH = base / "xingrun.db"
        config_runtime.CFG_PATH = base / "config.json"
        config_runtime.write_file_config({})
        lesson_manager.init_db()
        self.class_id = lesson_manager.save_class("版本测试班", subject="数学", grade="初二")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_version_lifecycle_keeps_current_until_new_version_is_ready(self):
        lesson_id = lesson_manager.create_pending_lesson(
            date_str="2026-04-09",
            subject="数学",
            grade="初二",
            topic="一次函数",
            summary="课堂总结",
            weak_points="斜率判断",
            class_id=self.class_id,
            created_by_user_id=7,
        )
        first = lesson_manager.create_review_plan_version(
            lesson_id=lesson_id,
            status="generating",
            request_key="request-1",
            request_id="request-id-1",
            chat_provider="openai",
            chat_model="gpt-5.4",
            created_by_user_id=7,
        )
        lesson_manager.complete_review_plan_version(
            first["id"],
            plan={"lesson_info": {"topic": "第一版"}, "days": []},
            pdf_path="/tmp/v1.pdf",
        )

        second = lesson_manager.create_review_plan_version(
            lesson_id=lesson_id,
            status="generating",
            request_key="request-2",
            request_id="request-id-2",
            chat_provider="openai",
            chat_model="gpt-5.4",
            created_by_user_id=7,
        )
        lesson = lesson_manager.get_lesson(lesson_id)
        self.assertEqual(lesson["current_review_plan_version_id"], first["id"])
        self.assertEqual(lesson["current_version"]["id"], first["id"])
        self.assertEqual(lesson["pdf_path"], "/tmp/v1.pdf")
        self.assertTrue(lesson["has_version_generating"])

        lesson_manager.fail_review_plan_version(second["id"], "第二版失败")
        lesson = lesson_manager.get_lesson(lesson_id)
        self.assertEqual(lesson["current_review_plan_version_id"], first["id"])
        self.assertEqual(lesson["latest_generation_error"], "第二版失败")
        self.assertFalse(lesson["has_version_generating"])

        third = lesson_manager.create_review_plan_version(
            lesson_id=lesson_id,
            status="generating",
            request_key="request-3",
            request_id="request-id-3",
            chat_provider="openai",
            chat_model="gpt-5.4",
            created_by_user_id=7,
        )
        lesson_manager.complete_review_plan_version(
            third["id"],
            plan={"lesson_info": {"topic": "第三版"}, "days": []},
            pdf_path="/tmp/v3.pdf",
        )
        lesson = lesson_manager.get_lesson(lesson_id)
        self.assertEqual(lesson["current_review_plan_version_id"], third["id"])
        self.assertEqual(lesson["current_version_no"], 3)
        self.assertEqual(lesson["pdf_path"], "/tmp/v3.pdf")
        self.assertFalse(lesson["has_version_generating"])

    def test_make_current_requires_ready_version_from_same_lesson(self):
        lesson_id = lesson_manager.create_pending_lesson(
            date_str="2026-04-09",
            subject="数学",
            grade="初二",
            topic="一次函数",
            summary="课堂总结",
            weak_points="斜率判断",
            class_id=self.class_id,
            created_by_user_id=7,
        )
        ready = lesson_manager.create_review_plan_version(lesson_id=lesson_id, status="generating")
        failed = lesson_manager.create_review_plan_version(lesson_id=lesson_id, status="generating")
        lesson_manager.complete_review_plan_version(ready["id"], plan={"days": []}, pdf_path="/tmp/ready.pdf")
        lesson_manager.fail_review_plan_version(failed["id"], "失败")

        other_lesson_id = lesson_manager.create_pending_lesson(
            date_str="2026-04-10",
            subject="数学",
            grade="初二",
            topic="二次函数",
            summary="课堂总结",
            weak_points="顶点式",
            class_id=self.class_id,
            created_by_user_id=7,
        )
        other_ready = lesson_manager.create_review_plan_version(lesson_id=other_lesson_id, status="generating")
        lesson_manager.complete_review_plan_version(
            other_ready["id"],
            plan={"days": []},
            pdf_path="/tmp/other-ready.pdf",
        )

        with self.assertRaisesRegex(ValueError, "ready"):
            lesson_manager.set_current_review_plan_version(lesson_id, failed["id"])

        lesson_manager.set_current_review_plan_version(lesson_id, ready["id"])
        lesson = lesson_manager.get_lesson(lesson_id)
        self.assertEqual(lesson["current_review_plan_version_id"], ready["id"])

        with self.assertRaisesRegex(LookupError, "review plan version not found"):
            lesson_manager.set_current_review_plan_version(lesson_id, other_ready["id"])

        lesson = lesson_manager.get_lesson(lesson_id)
        self.assertEqual(lesson["current_review_plan_version_id"], ready["id"])
