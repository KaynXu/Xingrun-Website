import csv
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config_runtime
import credit_manager
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

    def seed_owner_credits(self, amount: int = 20) -> None:
        me_response = self.client.get(
            "/api/me",
            headers=self.auth_headers(self.owner_token),
        )
        self.assertEqual(me_response.status_code, 200)
        user = me_response.get_json()
        self.assertIsNotNone(user)
        credit_manager.apply_manual_adjustment(
            organization_id=user["organization_id"],
            actor_user_id=user["id"],
            amount=amount,
            note="seed consultation ai credits",
        )

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

    def test_admin_can_edit_and_delete(self):
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
        self.assertEqual(delete_response.status_code, 200)

        remaining_rows = self.read_project_csv_rows()
        self.assertEqual(remaining_rows, [])

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

    @patch("app.parse_consultation_batch_text")
    def test_members_can_access_ai_parse_endpoint(self, mock_parse):
        member_token = self.create_member_token()
        self.seed_owner_credits()
        mock_parse.return_value = (
            {"items": [], "warnings": []},
            {
                "provider": "openai",
                "model": "gpt-4o",
                "input_tokens": 120,
                "output_tokens": 40,
            },
        )

        response = self.client.post(
            "/api/consultations/ai-parse",
            headers=self.auth_headers(member_token),
            json={"raw_text": "新增：张妈妈，五年级数学。"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"items": [], "warnings": []})
        mock_parse.assert_called_once()

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

    @patch("app.parse_consultation_batch_text")
    def test_ai_parse_endpoint_returns_create_and_explicit_id_update_drafts(self, mock_parse):
        self.seed_owner_credits()
        self.write_teacher_aliases({"teacher-1": ["雷文浩"]})
        mock_parse.return_value = {
            "items": [
                {
                    "action": "create",
                    "target_id": None,
                    "reason": "未检测到显式记录ID，按新增处理",
                    "fields": {
                        "date": "2026-03-31",
                        "parent_wechat_name": "张妈妈",
                        "grade": "5年级",
                        "receiving_teacher": "雷文浩",
                        "consultation_subject": "数学",
                        "need_detail": "想补基础",
                        "source_channel": "朋友介绍",
                        "source_channel_note": "张裕空",
                        "follow_up_status": "待邀约",
                    },
                    "warnings": [],
                },
                {
                    "action": "update",
                    "target_id": 182,
                    "reason": "文本显式提到记录 ID 182",
                    "fields": {
                        "follow_up_status": "跟进中",
                        "follow_up_note": "已约周四试听",
                    },
                    "warnings": [],
                },
            ],
            "warnings": [],
        }

        response = self.client.post(
            "/api/consultations/ai-parse",
            headers=self.auth_headers(self.owner_token),
            json={"raw_text": "新增：张妈妈，五年级数学。修改 ID 182：改成跟进中。"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual([item["action"] for item in payload["items"]], ["create", "update"])
        self.assertEqual(payload["items"][0]["fields"]["grade"], "五年级")
        self.assertEqual(payload["items"][0]["fields"]["source_channel"], "转介绍")
        self.assertEqual(payload["items"][0]["fields"]["teacher_id"], "teacher-1")
        self.assertEqual(payload["items"][1]["target_id"], 182)

    @patch("app.parse_consultation_batch_text")
    def test_ai_parse_endpoint_cleans_wechat_forwarded_text_before_parsing(self, mock_parse):
        self.seed_owner_credits()
        captured = {}

        def fake_parse(cleaned_text):
            captured["cleaned_text"] = cleaned_text
            return {
                "items": [
                    {
                        "action": "create",
                        "target_id": None,
                        "reason": "未检测到显式记录ID，按新增处理",
                        "fields": {
                            "parent_wechat_name": "李妈妈",
                            "consultation_subject": "英语",
                            "need_detail": "想先测评",
                        },
                        "warnings": [],
                    },
                    {
                        "action": "create",
                        "target_id": None,
                        "reason": "未检测到显式记录ID，按新增处理",
                        "fields": {
                            "parent_wechat_name": "王爸爸",
                            "consultation_subject": "数学",
                            "need_detail": "想补计算",
                        },
                        "warnings": [],
                    },
                ],
                "warnings": [],
            }

        mock_parse.side_effect = fake_parse

        response = self.client.post(
            "/api/consultations/ai-parse",
            headers=self.auth_headers(self.owner_token),
            json={
                "raw_text": "[聊天记录]\n张老师 2026-03-31 10:22\n李妈妈：孩子英语想先测评\n\n张老师 2026-03-31 10:25\n王爸爸：数学计算总错，想补基础"
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("2026-03-31 10:22", captured["cleaned_text"])
        self.assertIn("李妈妈", captured["cleaned_text"])
        self.assertIn("王爸爸", captured["cleaned_text"])
        self.assertEqual(len(response.get_json()["items"]), 2)

    @patch("app.parse_consultation_batch_text")
    def test_ai_parse_endpoint_returns_502_for_malformed_model_items(self, mock_parse):
        self.seed_owner_credits()
        mock_parse.return_value = {
            "items": [
                "not-a-dict-item"
            ],
            "warnings": ["top-level"],
        }

        response = self.client.post(
            "/api/consultations/ai-parse",
            headers=self.auth_headers(self.owner_token),
            json={"raw_text": "新增：张妈妈，五年级数学。"},
        )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.get_json()["error"], "AI 解析返回了无效结果")

    def test_normalize_batch_parse_result_skips_explicit_id_update_when_no_valid_fields_remain(self):
        payload = lesson_manager.normalize_consultation_batch_parse_result(
            {
                "items": [
                    {
                        "action": "update",
                        "target_id": 182,
                        "reason": "文本显式提到记录 ID 182",
                        "fields": {
                            "parent_wechat_name": "   ",
                            "consultation_subject": "\n\t",
                        },
                        "warnings": [],
                    }
                ],
                "warnings": [],
            }
        )

        self.assertEqual(payload["items"], [])
        self.assertEqual(
            payload["warnings"],
            ["显式记录 ID 182 的更新草稿已跳过，因为清洗后没有剩余有效字段。"],
        )

    def test_normalize_batch_parse_result_drops_blank_string_fields_from_update_draft(self):
        payload = lesson_manager.normalize_consultation_batch_parse_result(
            {
                "items": [
                    {
                        "action": "update",
                        "target_id": 182,
                        "reason": "文本显式提到记录 ID 182",
                        "fields": {
                            "follow_up_status": "跟进中",
                            "parent_wechat_name": "   ",
                            "consultation_subject": "\n\t",
                        },
                        "warnings": [],
                    }
                ],
                "warnings": [],
            }
        )

        draft = payload["items"][0]
        self.assertEqual(draft["action"], "update")
        self.assertEqual(draft["target_id"], 182)
        self.assertEqual(draft["fields"], {"follow_up_status": "跟进中"})

    def test_member_sees_only_assigned_consultations(self):
        """Member should only see consultations assigned to them via assigned_user_id"""
        # Create organization and two members
        org_id = lesson_manager.create_organization({"name": "Test Org"})["id"]
        member1_row = lesson_manager.create_user({
            "username": "member1",
            "password": "test",
            "organization_id": org_id,
            "role": "member",
            "display_name": "Member 1"
        })
        member2_row = lesson_manager.create_user({
            "username": "member2",
            "password": "test",
            "organization_id": org_id,
            "role": "member",
            "display_name": "Member 2"
        })
        
        # Get tokens
        member1_token = self.login("member1", "test")
        member2_token = self.login("member2", "test")
        owner_token = self.owner_token
        
        # Owner creates 3 consultations: one for member1, one for member2, one unassigned
        c1_response = self.client.post(
            "/api/consultations",
            headers=self.auth_headers(owner_token),
            json={
                "日期": "2026-03-12",
                "家长微信名": "家长1",
                "孩子姓名": "学生1",
                "年级": "一年级",
                "咨询科目": "数学",
                "具体需求": "基础",
                "assigned_user_id": member1_row["id"],
            },
        )
        self.assertEqual(c1_response.status_code, 201)
        c1_id = c1_response.get_json()["id"]
        
        c2_response = self.client.post(
            "/api/consultations",
            headers=self.auth_headers(owner_token),
            json={
                "日期": "2026-03-12",
                "家长微信名": "家长2",
                "孩子姓名": "学生2",
                "年级": "二年级",
                "咨询科目": "语文",
                "具体需求": "阅读",
                "assigned_user_id": member2_row["id"],
            },
        )
        self.assertEqual(c2_response.status_code, 201)
        c2_id = c2_response.get_json()["id"]
        
        # Unassigned consultation
        c3_response = self.client.post(
            "/api/consultations",
            headers=self.auth_headers(owner_token),
            json={
                "日期": "2026-03-12",
                "家长微信名": "家长3",
                "孩子姓名": "学生3",
                "年级": "三年级",
                "咨询科目": "英语",
                "具体需求": "口语",
                "assigned_user_id": None,
            },
        )
        self.assertEqual(c3_response.status_code, 201)
        c3_id = c3_response.get_json()["id"]
        
        # Member1 lists consultations - should only see c1
        member1_list = self.client.get(
            "/api/consultations",
            headers=self.auth_headers(member1_token)
        ).get_json()
        member1_ids = [c["id"] for c in member1_list]
        self.assertIn(c1_id, member1_ids, "Member1 should see their assigned consultation")
        self.assertNotIn(c2_id, member1_ids, "Member1 should not see consultation assigned to member2")
        self.assertNotIn(c3_id, member1_ids, "Member1 should not see unassigned consultation")
        
        # Member2 lists consultations - should only see c2
        member2_list = self.client.get(
            "/api/consultations",
            headers=self.auth_headers(member2_token)
        ).get_json()
        member2_ids = [c["id"] for c in member2_list]
        self.assertIn(c2_id, member2_ids, "Member2 should see their assigned consultation")
        self.assertNotIn(c1_id, member2_ids, "Member2 should not see consultation assigned to member1")
        self.assertNotIn(c3_id, member2_ids, "Member2 should not see unassigned consultation")
        
        # Owner lists consultations - should see all three
        owner_list = self.client.get(
            "/api/consultations",
            headers=self.auth_headers(owner_token)
        ).get_json()
        owner_ids = [c["id"] for c in owner_list]
        self.assertIn(c1_id, owner_ids)
        self.assertIn(c2_id, owner_ids)
        self.assertIn(c3_id, owner_ids)


if __name__ == "__main__":
    unittest.main()
