import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config_runtime
import lesson_manager
from app import app


class ConsultationFlowTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)

        lesson_manager.DB_PATH = self.base / "lessons.db"
        lesson_manager.CONSULTATIONS_CSV_PATH = self.base / "data" / "consultations.csv"
        lesson_manager.LEGACY_CONSULTATIONS_CSV_PATH = self.base / "legacy" / "consultations.csv"
        lesson_manager.CONSULTATION_TEACHERS_JSON_CANDIDATES = [self.base / "teachers.json"]

        config_runtime.CFG_PATH = self.base / "config.json"
        config_runtime.write_file_config({})

        lesson_manager.init_db()
        self.client = app.test_client()
        self.owner_token = self.login("Kayn", "xingrun2026")

    def tearDown(self):
        self.temp_dir.cleanup()

    @staticmethod
    def auth_headers(token: str) -> dict[str, str]:
        return {"X-Auth-Token": token}

    def login(self, username: str, password: str) -> str:
        response = self.client.post("/api/login", json={"username": username, "password": password})
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIsNotNone(payload)
        return payload["token"]

    def create_member_token(self) -> str:
        submit = self.client.post(
            "/api/register-request",
            json={
                "username": "teacher_a",
                "display_name": "Teacher A",
                "password": "secret123",
                "organization_name": "星润Starain",
            },
        )
        self.assertEqual(submit.status_code, 201)

        pending = self.client.get(
            "/api/admin/registration-requests",
            headers=self.auth_headers(self.owner_token),
        )
        self.assertEqual(pending.status_code, 200)
        request_id = pending.get_json()["items"][0]["id"]

        approve = self.client.post(
            f"/api/admin/registration-requests/{request_id}/approve",
            headers=self.auth_headers(self.owner_token),
        )
        self.assertEqual(approve.status_code, 200)
        return self.login("teacher_a", "secret123")

    def create_admin_token(self) -> str:
        member_token = self.create_member_token()

        me_response = self.client.get(
            "/api/me",
            headers=self.auth_headers(member_token),
        )
        self.assertEqual(me_response.status_code, 200)
        me_payload = me_response.get_json()
        self.assertIsNotNone(me_payload)

        promote_response = self.client.put(
            f"/api/admin/users/{me_payload['id']}/role",
            headers=self.auth_headers(self.owner_token),
            json={"role": "admin"},
        )
        self.assertEqual(promote_response.status_code, 200)
        return member_token

    def write_legacy_csv(self, rows: list[dict[str, str]]) -> None:
        lesson_manager.LEGACY_CONSULTATIONS_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
        with lesson_manager.LEGACY_CONSULTATIONS_CSV_PATH.open("w", newline="", encoding="utf-8-sig") as fh:
            writer = csv.DictWriter(fh, fieldnames=lesson_manager.CONSULTATION_FIELDNAMES)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)

    def read_project_csv_rows(self) -> list[dict[str, str]]:
        with lesson_manager.CONSULTATIONS_CSV_PATH.open("r", newline="", encoding="utf-8-sig") as fh:
            return list(csv.DictReader(fh))

    def sample_row(self, **overrides: str) -> dict[str, str]:
        row = {field: "" for field in lesson_manager.CONSULTATION_FIELDNAMES}
        row.update(
            {
                "id": "1",
                "日期": "2026-03-10",
                "家长微信名": "张妈妈",
                "孩子姓名": "张小明",
                "年级": "三年级",
                "接待老师": "王老师",
                "老师ID": "teacher-1",
                "咨询科目": "数学",
                "具体需求": "基础提升",
                "来源渠道": "转介绍",
                "来源渠道备注": "",
                "截图": "",
                "提醒时间": "2026-03-12 18:00",
                "提醒状态": "已设置",
                "提醒任务ID": "task-1",
                "跟进状态": "待邀约",
                "跟进备注": "首轮记录",
                "录入时间": "2026-03-10 10:00:00",
                "最后更新": "2026-03-10 10:00:00",
            }
        )
        row.update(overrides)
        return row

    def write_teacher_aliases(self, aliases: dict) -> None:
        lesson_manager.CONSULTATION_TEACHERS_JSON_CANDIDATES[0].write_text(
            json.dumps(aliases, ensure_ascii=False),
            encoding="utf-8",
        )

    def test_list_migrates_legacy_csv_into_project_storage(self):
        self.write_legacy_csv([self.sample_row()])

        response = self.client.get("/api/consultations", headers=self.auth_headers(self.owner_token))

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["家长微信名"], "张妈妈")
        self.assertTrue(lesson_manager.CONSULTATIONS_CSV_PATH.exists())
        self.assertFalse(lesson_manager.LEGACY_CONSULTATIONS_CSV_PATH.exists())

    def test_owner_can_create_update_and_delete_while_preserving_hidden_columns(self):
        self.write_legacy_csv([self.sample_row()])

        update_response = self.client.put(
            "/api/consultations/1",
            headers=self.auth_headers(self.owner_token),
            json={"跟进状态": "跟进中", "跟进备注": "已经回访"},
        )
        self.assertEqual(update_response.status_code, 200)

        rows_after_update = self.read_project_csv_rows()
        self.assertEqual(rows_after_update[0]["提醒时间"], "2026-03-12 18:00")
        self.assertEqual(rows_after_update[0]["提醒状态"], "已设置")
        self.assertEqual(rows_after_update[0]["提醒任务ID"], "task-1")
        self.assertEqual(rows_after_update[0]["跟进状态"], "跟进中")
        self.assertEqual(rows_after_update[0]["跟进备注"], "已经回访")

        create_response = self.client.post(
            "/api/consultations",
            headers=self.auth_headers(self.owner_token),
            json={
                "日期": "2026-03-11",
                "家长微信名": "李妈妈",
                "孩子姓名": "李小雨",
                "年级": "四年级",
                "接待老师": "陈老师",
                "老师ID": "teacher-2",
                "咨询科目": "英语",
                "具体需求": "阅读提升",
                "来源渠道": "朋友圈",
                "截图": "",
                "跟进状态": "待邀约",
                "跟进备注": "",
            },
        )
        self.assertEqual(create_response.status_code, 201)
        created = create_response.get_json()
        self.assertEqual(created["id"], 2)

        delete_response = self.client.delete(
            "/api/consultations/1",
            headers=self.auth_headers(self.owner_token),
        )
        self.assertEqual(delete_response.status_code, 200)

        remaining_rows = self.read_project_csv_rows()
        self.assertEqual(len(remaining_rows), 1)
        self.assertEqual(remaining_rows[0]["id"], "2")
        self.assertEqual(remaining_rows[0]["家长微信名"], "李妈妈")

    def test_admin_can_edit_but_only_owner_can_delete(self):
        self.write_legacy_csv([self.sample_row()])
        admin_token = self.create_admin_token()

        list_response = self.client.get("/api/consultations", headers=self.auth_headers(admin_token))
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(list_response.get_json()), 1)

        update_response = self.client.put(
            "/api/consultations/1",
            headers=self.auth_headers(admin_token),
            json={"跟进状态": "已报班", "跟进备注": "管理员已确认报班"},
        )
        self.assertEqual(update_response.status_code, 200)
        updated = update_response.get_json()
        self.assertEqual(updated["follow_up_status"], "已报班")
        self.assertEqual(updated["follow_up_note"], "管理员已确认报班")

        rows_after_update = self.read_project_csv_rows()
        self.assertEqual(rows_after_update[0]["跟进状态"], "已报班")

        delete_response = self.client.delete(
            "/api/consultations/1",
            headers=self.auth_headers(admin_token),
        )
        self.assertEqual(delete_response.status_code, 403)

    def test_members_can_view_and_create_but_not_edit_or_delete(self):
        self.write_legacy_csv([self.sample_row()])
        member_token = self.create_member_token()

        list_response = self.client.get("/api/consultations", headers=self.auth_headers(member_token))
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(list_response.get_json()), 1)

        create_response = self.client.post(
            "/api/consultations",
            headers=self.auth_headers(member_token),
            json={
                "日期": "2026-03-12",
                "家长微信名": "王妈妈",
                "孩子姓名": "王小乐",
                "年级": "五年级",
                "接待老师": "李老师",
                "老师ID": "teacher-3",
                "咨询科目": "语文",
                "具体需求": "作文提高",
                "来源渠道": "家长群",
                "截图": "",
                "跟进状态": "待邀约",
                "跟进备注": "",
            },
        )
        self.assertEqual(create_response.status_code, 201)

        update_response = self.client.put(
            "/api/consultations/1",
            headers=self.auth_headers(member_token),
            json={"跟进备注": "成员不能改"},
        )
        self.assertEqual(update_response.status_code, 403)

        delete_response = self.client.delete(
            "/api/consultations/1",
            headers=self.auth_headers(member_token),
        )
        self.assertEqual(delete_response.status_code, 403)

    def test_list_exposes_teacher_display_name_from_user_directory(self):
        self.write_legacy_csv([
            self.sample_row(
                接待老师="teacher_a",
                老师ID="teacher_a",
            )
        ])
        self.create_member_token()

        response = self.client.get("/api/consultations", headers=self.auth_headers(self.owner_token))

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload[0]["receiving_teacher"], "teacher_a")
        self.assertEqual(payload[0]["teacher_id"], "teacher_a")
        self.assertEqual(payload[0]["teacher_display_name"], "Teacher A")

    def test_list_exposes_teacher_display_name_from_teacher_alias_file(self):
        self.write_teacher_aliases({"KeChongDianDeAShiPiLing": ["雷老师", "雷文浩"]})
        self.write_legacy_csv([
            self.sample_row(
                接待老师="KeChongDianDeAShiPiLing",
                老师ID="KeChongDianDeAShiPiLing",
            )
        ])

        response = self.client.get("/api/consultations", headers=self.auth_headers(self.owner_token))

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload[0]["teacher_display_name"], "雷老师")

    def test_list_normalizes_grade_and_source_channel(self):
        self.write_legacy_csv([
            self.sample_row(
                年级="5年级",
                来源渠道="朋友介绍",
                家长微信名="秋秋",
                孩子姓名="秋秋",
            )
        ])

        response = self.client.get("/api/consultations", headers=self.auth_headers(self.owner_token))

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload[0]["grade"], "五年级")
        self.assertEqual(payload[0]["source_channel"], "转介绍")
        self.assertEqual(payload[0]["source_channel_note"], "")

    def test_list_normalizes_mixed_name_and_source_channel_phrase(self):
        self.write_legacy_csv([
            self.sample_row(
                年级="5年级",
                来源渠道="张裕空转介绍",
                家长微信名="张裕空妈妈",
                孩子姓名="张裕空",
            )
        ])

        response = self.client.get("/api/consultations", headers=self.auth_headers(self.owner_token))

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload[0]["source_channel"], "转介绍")
        self.assertEqual(payload[0]["source_channel_note"], "张裕空")

    def test_create_clears_source_channel_when_it_matches_names(self):
        create_response = self.client.post(
            "/api/consultations",
            headers=self.auth_headers(self.owner_token),
            json={
                "日期": "2026-03-12",
                "家长微信名": "张妈妈",
                "孩子姓名": "张小明",
                "年级": "2年级",
                "接待老师": "李老师",
                "老师ID": "teacher-3",
                "咨询科目": "语文",
                "具体需求": "作文提高",
                "来源渠道": "张妈妈",
                "截图": "",
                "跟进状态": "待邀约",
                "跟进备注": "",
            },
        )

        self.assertEqual(create_response.status_code, 201)
        created = create_response.get_json()
        self.assertEqual(created["grade"], "二年级")
        self.assertEqual(created["source_channel"], "")
        self.assertEqual(created["source_channel_note"], "")

    def test_consultation_teachers_endpoint_merges_aliases(self):
        self.write_teacher_aliases({"dXiaoDi": ["华奥鑫", "华老师"]})

        response = self.client.get("/api/consultation-teachers", headers=self.auth_headers(self.owner_token))

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(any(item["teacher_id"] == "dXiaoDi" and item["display_name"] == "华奥鑫" for item in payload))

    def test_create_and_list_include_source_channel_note(self):
        create_response = self.client.post(
            "/api/consultations",
            headers=self.auth_headers(self.owner_token),
            json={
                "日期": "2026-03-12",
                "家长微信名": "张妈妈",
                "孩子姓名": "张小明",
                "年级": "二年级",
                "接待老师": "李老师",
                "老师ID": "teacher-3",
                "咨询科目": "语文",
                "具体需求": "作文提高",
                "来源渠道": "转介绍",
                "来源渠道备注": "张妈妈",
                "截图": "",
                "跟进状态": "待邀约",
                "跟进备注": "",
            },
        )

        self.assertEqual(create_response.status_code, 201)
        created = create_response.get_json()
        self.assertEqual(created["source_channel_note"], "张妈妈")

        list_response = self.client.get("/api/consultations", headers=self.auth_headers(self.owner_token))
        self.assertEqual(list_response.status_code, 200)
        listed = list_response.get_json()
        self.assertEqual(listed[0]["source_channel_note"], "张妈妈")

    def test_owner_can_list_consultation_teachers_from_user_directory_and_alias_file(self):
        self.write_teacher_aliases({
            "dXiaoDi": ["华奥鑫", "华老师"],
            "KeChongDianDeAShiPiLing": ["雷文浩", "雷老师"],
        })
        self.create_member_token()

        response = self.client.get("/api/consultation-teachers", headers=self.auth_headers(self.owner_token))

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        teacher_by_id = {item["teacher_id"]: item for item in payload}
        self.assertEqual(teacher_by_id["teacher_a"]["display_name"], "Teacher A")
        self.assertEqual(teacher_by_id["dXiaoDi"]["display_name"], "华奥鑫")
        self.assertIn("华老师", teacher_by_id["dXiaoDi"]["aliases"])


if __name__ == "__main__":
    unittest.main()
