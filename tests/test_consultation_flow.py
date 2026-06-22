from __future__ import annotations

import io
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
import app as app_module
from app import app


class ConsultationFlowTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)

        lesson_manager.DB_PATH = self.base / "xingrun.db"
        lesson_manager.CONSULTATION_TEACHERS_JSON_CANDIDATES = [self.base / "teachers.json"]
        self.original_upload_dir = app_module.UPLOAD_DIR
        app_module.UPLOAD_DIR = self.base / "uploads"
        app_module.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

        config_runtime.CFG_PATH = self.base / "config.json"
        config_runtime.write_file_config({})

        lesson_manager.init_db()
        self.client = app.test_client()
        self.owner_token = self.login("Kayn", "xingrun2026")

    def tearDown(self):
        app_module.UPLOAD_DIR = self.original_upload_dir
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

    def create_member_token(
        self,
        username: str = "teacher_a",
        display_name: str = "Teacher A",
        password: str = "secret123",
    ) -> str:
        submit = self.client.post(
            "/api/register-request",
            json={
                "username": username,
                "display_name": display_name,
                "password": password,
                "organization_name": "星润Starain",
                "recovery_phone": "13800000000",
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
        return self.login(username, password)

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
        user = self.owner_user()
        credit_manager.apply_manual_adjustment(
            organization_id=user["organization_id"],
            actor_user_id=user["id"],
            amount=amount,
            note="seed consultation ai credits",
        )

    def owner_user(self) -> dict:
        me_response = self.client.get(
            "/api/me",
            headers=self.auth_headers(self.owner_token),
        )
        self.assertEqual(me_response.status_code, 200)
        user = me_response.get_json()
        self.assertIsNotNone(user)
        return user

    def user_for_token(self, token: str) -> dict:
        me_response = self.client.get(
            "/api/me",
            headers=self.auth_headers(token),
        )
        self.assertEqual(me_response.status_code, 200)
        user = me_response.get_json()
        self.assertIsNotNone(user)
        return user

    def create_consultation_record(self, assigned_user_id: int | None = None, **overrides: str) -> dict:
        owner = self.owner_user()
        payload = self.sample_row(**overrides)
        stored = lesson_manager._consultation_row_to_storage(payload, owner["organization_id"])
        with lesson_manager.get_conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO consultations (
                    organization_id, assigned_user_id, date, parent_wechat_name, child_name, grade,
                    consultation_subject, need_detail,
                    source_channel, source_channel_note, screenshot, reminder_at,
                    reminder_status, reminder_task_id, follow_up_status, follow_up_note,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    owner["organization_id"],
                    assigned_user_id,
                    stored["date"],
                    stored["parent_wechat_name"],
                    stored["child_name"],
                    stored["grade"],
                    stored["consultation_subject"],
                    stored["need_detail"],
                    stored["source_channel"],
                    stored["source_channel_note"],
                    stored["screenshot"],
                    stored["reminder_at"],
                    stored["reminder_status"],
                    stored["reminder_task_id"],
                    stored["follow_up_status"],
                    stored["follow_up_note"],
                    stored["created_at"],
                    stored["updated_at"],
                ),
            )
            row = conn.execute(
                """
                SELECT c.*, u.display_name, u.username
                FROM consultations c
                LEFT JOIN users u ON c.assigned_user_id = u.id
                WHERE c.id=?
                """,
                (cur.lastrowid,),
            ).fetchone()
        return lesson_manager._consultation_storage_row_to_public_dict(row)

    def read_consultation_storage_rows(self) -> list[dict]:
        with lesson_manager.get_conn() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM consultations
                ORDER BY id ASC
                """
            ).fetchall()
        return [dict(row) for row in rows]

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

    def test_list_uses_sqlite_without_consultations_csv(self):
        self.create_consultation_record()

        response = self.client.get("/api/consultations", headers=self.auth_headers(self.owner_token))

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["家长微信名"], "张妈妈")
        self.assertFalse((self.base / "data" / "consultations.csv").exists())
        self.assertFalse((self.base / "legacy" / "consultations.csv").exists())

    def test_owner_can_create_update_and_delete_while_preserving_hidden_columns(self):
        self.create_consultation_record()

        update_response = self.client.put(
            "/api/consultations/1",
            headers=self.auth_headers(self.owner_token),
            json={"跟进状态": "跟进中", "跟进备注": "已经回访"},
        )
        self.assertEqual(update_response.status_code, 200)

        rows_after_update = self.read_consultation_storage_rows()
        self.assertEqual(rows_after_update[0]["reminder_at"], "2026-03-12 18:00")
        self.assertEqual(rows_after_update[0]["reminder_status"], "已设置")
        self.assertEqual(rows_after_update[0]["reminder_task_id"], "task-1")
        self.assertEqual(rows_after_update[0]["follow_up_status"], "正在跟进")
        self.assertEqual(rows_after_update[0]["flow_stage"], "正在沟通细节")
        self.assertEqual(rows_after_update[0]["follow_up_note"], "已经回访")

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

        remaining_rows = self.read_consultation_storage_rows()
        self.assertEqual(len(remaining_rows), 1)
        self.assertEqual(remaining_rows[0]["id"], 2)
        self.assertEqual(remaining_rows[0]["parent_wechat_name"], "李妈妈")

    def test_consultation_create_requires_lightweight_fields(self):
        response = self.client.post(
            "/api/consultations",
            headers=self.auth_headers(self.owner_token),
            json={
                "child_name": "轻量学生",
                "consultation_subject": "数学",
                "grade": "七年级",
                "receiving_teacher": "何姝健",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("家长诉求", response.get_json()["error"])

    def test_consultation_stage_notes_and_closing_result_round_trip(self):
        created = self.client.post(
            "/api/consultations",
            headers=self.auth_headers(self.owner_token),
            json={
                "child_name": "流程学生",
                "consultation_subject": "数学",
                "grade": "七年级",
                "need_detail": "想看看七年级数学衔接",
                "receiving_teacher": "何姝健",
                "source_channel": "转介绍",
                "customer_service_teacher": "客服老师",
                "customer_service_note": "已加客服，家长发了校内成绩",
                "communication_teacher_note": "老师已初步沟通",
                "test_teacher": "测试老师",
                "closing_result": "success",
            },
        )
        self.assertEqual(created.status_code, 201)
        payload = created.get_json()
        self.assertEqual(payload["customer_service_teacher"], "客服老师")
        self.assertEqual(payload["customer_service_note"], "已加客服，家长发了校内成绩")
        self.assertEqual(payload["communication_teacher_note"], "老师已初步沟通")
        self.assertEqual(payload["test_teacher"], "测试老师")
        self.assertEqual(payload["closing_result"], "success")

    def test_consultation_stage_teacher_ids_round_trip(self):
        created = self.client.post(
            "/api/consultations",
            headers=self.auth_headers(self.owner_token),
            json={
                "child_name": "派单口子学生",
                "consultation_subject": "数学",
                "grade": "七年级",
                "need_detail": "需要试听",
                "receiving_teacher": "何姝健",
                "stage_teacher_ids": {
                    "已加对应教师微信": "hua",
                    "待测试": "lei",
                    "待试听": "trial-a",
                },
            },
        )

        self.assertEqual(created.status_code, 201)
        payload = created.get_json()
        self.assertEqual(payload["stage_teacher_ids"]["待测试"], "lei")

        updated = self.client.put(
            f"/api/consultations/{payload['id']}",
            headers=self.auth_headers(self.owner_token),
            json={
                "stage_teacher_ids": {
                    "已加对应教师微信": "hua",
                    "待测试": "lei-2",
                    "待试听": "trial-a",
                },
            },
        )

        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.get_json()["stage_teacher_ids"]["待测试"], "lei-2")

    def test_admin_can_edit_and_delete(self):
        self.create_consultation_record()
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
        self.assertEqual(updated["follow_up_status"], "完成")
        self.assertEqual(updated["follow_up_note"], "管理员已确认报班")

        rows_after_update = self.read_consultation_storage_rows()
        self.assertEqual(rows_after_update[0]["follow_up_status"], "完成")
        self.assertEqual(rows_after_update[0]["flow_stage"], "成功进班")

        delete_response = self.client.delete(
            "/api/consultations/1",
            headers=self.auth_headers(admin_token),
        )
        self.assertEqual(delete_response.status_code, 200)

        remaining_rows = self.read_consultation_storage_rows()
        self.assertEqual(remaining_rows, [])

    def test_consultation_flow_stage_fields_round_trip_and_derive_follow_up_status(self):
        response = self.client.post(
            "/api/consultations",
            headers=self.auth_headers(self.owner_token),
            json={
                "parent_wechat_name": "赵妈妈",
                "child_name": "赵小星",
                "grade": "三年级",
                "receiving_teacher": "何姝健",
                "consultation_subject": "数学",
                "need_detail": "想确认三年级数学试听安排",
                "flow_stage": "待试听",
                "completed_stages": ["已加小客服微信", "已加对应教师微信", "正在沟通细节", "待试听"],
                "trial_taken": "是",
                "trial_time_slot": "周六 10:00-12:00",
                "trial_class_manual": "三年级数学临时试听班",
                "trial_teacher": "王老师",
                "trial_feedback": "愿意试听，但需要确认时间",
            },
        )
        self.assertEqual(response.status_code, 201)
        created = response.get_json()
        self.assertEqual(created["flow_stage"], "待试听")
        self.assertEqual(created["follow_up_status"], "正在跟进")
        self.assertEqual(created["completed_stages"], ["已加小客服微信", "已加对应教师微信", "正在沟通细节", "待试听"])
        self.assertEqual(created["trial_time_slot"], "周六 10:00-12:00")
        self.assertEqual(created["trial_class_manual"], "三年级数学临时试听班")
        self.assertEqual(created["trial_teacher"], "王老师")
        self.assertEqual(created["trial_feedback"], "愿意试听，但需要确认时间")

        stored = self.read_consultation_storage_rows()[0]
        self.assertEqual(stored["flow_stage"], "待试听")
        self.assertIn("待试听", stored["completed_stages_json"])

    def test_consultation_search_fuzzy_covers_flow_and_detail_fields(self):
        matched = self.client.post(
            "/api/consultations",
            headers=self.auth_headers(self.owner_token),
            json={
                "parent_wechat_name": "CaseParentA",
                "child_name": "搜索学生A",
                "grade": "七年级",
                "receiving_teacher": "何姝健",
                "consultation_subject": "数学",
                "need_detail": "家长主要咨询试听安排和班课节奏",
                "flow_stage": "待试听",
                "completed_stages": ["已加小客服微信", "待试听"],
                "trial_feedback": "孩子试听反馈非常积极",
                "end_note": "后续继续跟进",
                "follow_up_note": "内部提醒：周二面对面核对",
            },
        )
        self.assertEqual(matched.status_code, 201)
        other = self.client.post(
            "/api/consultations",
            headers=self.auth_headers(self.owner_token),
            json={
                "parent_wechat_name": "CaseParentB",
                "child_name": "搜索学生B",
                "grade": "七年级",
                "receiving_teacher": "何姝健",
                "consultation_subject": "英语",
                "need_detail": "只了解寒假课程",
                "flow_stage": "正在沟通细节",
            },
        )
        self.assertEqual(other.status_code, 201)

        response = self.client.get(
            "/api/consultations?q=试听反馈",
            headers=self.auth_headers(self.owner_token),
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual([item["child_name"] for item in payload], ["搜索学生A"])

    def test_consultation_search_exact_matches_full_fields_and_long_text_contains(self):
        exact = self.client.post(
            "/api/consultations",
            headers=self.auth_headers(self.owner_token),
            json={
                "date": "2026-05-19",
                "parent_wechat_name": "ExactParent",
                "child_name": "王小明",
                "grade": "七年级",
                "receiving_teacher": "何姝健",
                "consultation_subject": "数学",
                "need_detail": "这是一段完整咨询内容，包含精准片段ABC。",
            },
        )
        self.assertEqual(exact.status_code, 201)
        partial_name = self.client.post(
            "/api/consultations",
            headers=self.auth_headers(self.owner_token),
            json={
                "date": "2026-05-20",
                "parent_wechat_name": "OtherParent",
                "child_name": "王小明同学",
                "grade": "七年级",
                "receiving_teacher": "何姝健",
                "consultation_subject": "数学",
                "need_detail": "普通咨询内容",
            },
        )
        self.assertEqual(partial_name.status_code, 201)

        exact_name = self.client.get(
            "/api/consultations?q=王小明&search_mode=exact",
            headers=self.auth_headers(self.owner_token),
        )
        self.assertEqual(exact_name.status_code, 200)
        self.assertEqual([item["child_name"] for item in exact_name.get_json()], ["王小明"])

        exact_long_text = self.client.get(
            "/api/consultations?q=精准片段ABC&search_mode=exact",
            headers=self.auth_headers(self.owner_token),
        )
        self.assertEqual(exact_long_text.status_code, 200)
        self.assertEqual([item["child_name"] for item in exact_long_text.get_json()], ["王小明"])

    def test_consultation_search_orders_exact_matches_before_fuzzy_matches(self):
        exact = self.client.post(
            "/api/consultations",
            headers=self.auth_headers(self.owner_token),
            json={
                "parent_wechat_name": "OrderExactParent",
                "child_name": "排序学生",
                "grade": "七年级",
                "receiving_teacher": "何姝健",
                "consultation_subject": "数学",
                "need_detail": "普通咨询内容",
            },
        )
        self.assertEqual(exact.status_code, 201)
        fuzzy = self.client.post(
            "/api/consultations",
            headers=self.auth_headers(self.owner_token),
            json={
                "parent_wechat_name": "OrderFuzzyParent",
                "child_name": "排序学生延伸",
                "grade": "七年级",
                "receiving_teacher": "何姝健",
                "consultation_subject": "语文",
                "need_detail": "普通咨询内容",
            },
        )
        self.assertEqual(fuzzy.status_code, 201)

        response = self.client.get(
            "/api/consultations?q=排序学生",
            headers=self.auth_headers(self.owner_token),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["child_name"] for item in response.get_json()],
            ["排序学生", "排序学生延伸"],
        )

    def test_success_stage_requires_existing_or_manual_class(self):
        missing_class = self.client.post(
            "/api/consultations",
            headers=self.auth_headers(self.owner_token),
            json={
                "parent_wechat_name": "钱妈妈",
                "child_name": "钱小满",
                "grade": "三年级",
                "receiving_teacher": "何姝健",
                "consultation_subject": "数学",
                "need_detail": "准备进班",
                "flow_stage": "成功进班",
                "completed_stages": ["已加小客服微信", "成功进班"],
            },
        )
        self.assertEqual(missing_class.status_code, 400)
        self.assertIn("成功进班必须选择或填写班级", missing_class.get_json()["error"])

        class_id = lesson_manager.save_class("三年级数学A班", subject="数学", grade="三年级")
        with_class = self.client.post(
            "/api/consultations",
            headers=self.auth_headers(self.owner_token),
            json={
                "parent_wechat_name": "钱妈妈",
                "child_name": "钱小满",
                "grade": "三年级",
                "receiving_teacher": "何姝健",
                "consultation_subject": "数学",
                "need_detail": "准备进班",
                "flow_stage": "成功进班",
                "completed_stages": ["已加小客服微信", "成功进班"],
                "success_class_id": class_id,
            },
        )
        self.assertEqual(with_class.status_code, 201)
        payload = with_class.get_json()
        self.assertEqual(payload["follow_up_status"], "完成")
        self.assertEqual(payload["success_class_id"], class_id)

    def test_legacy_follow_up_status_maps_to_new_flow_stage_without_lighting_unknown_steps(self):
        legacy = self.create_consultation_record(**{"跟进状态": "已报班"})
        with lesson_manager.get_conn() as conn:
            conn.execute(
                "UPDATE consultations SET flow_stage='', completed_stages_json='[]', follow_up_status='已报班' WHERE id=?",
                (legacy["id"],),
            )

        response = self.client.get(f"/api/consultations/{legacy['id']}", headers=self.auth_headers(self.owner_token))

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["flow_stage"], "成功进班")
        self.assertEqual(payload["follow_up_status"], "完成")
        self.assertEqual(payload["completed_stages"], ["成功进班"])
        self.assertEqual(payload["test_images"], [])

    def test_ended_consultation_freezes_stage_fields_but_allows_end_note_update(self):
        created = self.client.post(
            "/api/consultations",
            headers=self.auth_headers(self.owner_token),
            json={
                "parent_wechat_name": "周妈妈",
                "child_name": "周小安",
                "grade": "七年级",
                "receiving_teacher": "何姝健",
                "consultation_subject": "数学",
                "need_detail": "沟通后暂时结束",
                "flow_stage": "咨询结束",
                "completed_stages": ["已加小客服微信", "正在沟通细节", "咨询结束"],
                "end_note": "首次关闭",
            },
        )
        self.assertEqual(created.status_code, 201)
        consultation_id = created.get_json()["id"]

        update = self.client.put(
            f"/api/consultations/{consultation_id}",
            headers=self.auth_headers(self.owner_token),
            json={
                "flow_stage": "待试听",
                "completed_stages": ["已加小客服微信", "待试听"],
                "trial_taken": "是",
                "trial_feedback": "结束后不应再改流程",
                "end_note": "补充结束原因",
            },
        )

        self.assertEqual(update.status_code, 200)
        payload = update.get_json()
        self.assertEqual(payload["flow_stage"], "咨询结束")
        self.assertEqual(payload["follow_up_status"], "完成")
        self.assertEqual(payload["completed_stages"], ["已加小客服微信", "正在沟通细节", "咨询结束"])
        self.assertEqual(payload["trial_taken"], "")
        self.assertEqual(payload["trial_feedback"], "")
        self.assertEqual(payload["end_note"], "补充结束原因")

    def test_ended_consultation_can_be_restored_with_explicit_restore_flag(self):
        created = self.client.post(
            "/api/consultations",
            headers=self.auth_headers(self.owner_token),
            json={
                "parent_wechat_name": "林妈妈",
                "child_name": "林小贝",
                "grade": "七年级",
                "receiving_teacher": "何姝健",
                "consultation_subject": "数学",
                "need_detail": "误触结束后恢复",
                "flow_stage": "咨询结束",
                "completed_stages": ["已加小客服微信", "正在沟通细节", "咨询结束"],
                "end_note": "误触结束",
            },
        )
        self.assertEqual(created.status_code, 201)
        consultation_id = created.get_json()["id"]

        restored = self.client.put(
            f"/api/consultations/{consultation_id}",
            headers=self.auth_headers(self.owner_token),
            json={
                "restore_from_end": True,
                "flow_stage": "正在沟通细节",
                "completed_stages": ["已加小客服微信", "正在沟通细节"],
            },
        )

        self.assertEqual(restored.status_code, 200)
        payload = restored.get_json()
        self.assertEqual(payload["flow_stage"], "正在沟通细节")
        self.assertEqual(payload["follow_up_status"], "正在跟进")
        self.assertEqual(payload["completed_stages"], ["已加小客服微信", "正在沟通细节"])
        self.assertEqual(payload["end_note"], "误触结束")

    def test_terminal_consultation_records_ended_at_once(self):
        created = self.client.post(
            "/api/consultations",
            headers=self.auth_headers(self.owner_token),
            json={
                "parent_wechat_name": "吴妈妈",
                "child_name": "吴小同",
                "grade": "七年级",
                "receiving_teacher": "何姝健",
                "consultation_subject": "数学",
                "need_detail": "试听后再决定",
                "flow_stage": "待试听",
                "completed_stages": ["已加小客服微信", "待试听"],
            },
        )
        self.assertEqual(created.status_code, 201)
        consultation_id = created.get_json()["id"]

        first = self.client.put(
            f"/api/consultations/{consultation_id}",
            headers=self.auth_headers(self.owner_token),
            json={
                "flow_stage": "咨询结束",
                "completed_stages": ["已加小客服微信", "待试听"],
            },
        )

        self.assertEqual(first.status_code, 200)
        first_payload = first.get_json()
        self.assertTrue(first_payload["ended_at"])
        self.assertEqual(first_payload["flow_stage"], "咨询结束")
        self.assertEqual(first_payload["completed_stages"], ["已加小客服微信", "待试听", "咨询结束"])

        second = self.client.put(
            f"/api/consultations/{consultation_id}",
            headers=self.auth_headers(self.owner_token),
            json={"end_note": "补充结束说明"},
        )

        self.assertEqual(second.status_code, 200)
        second_payload = second.get_json()
        self.assertEqual(second_payload["ended_at"], first_payload["ended_at"])
        self.assertEqual(second_payload["end_note"], "补充结束说明")

    def test_legacy_terminal_consultation_without_ended_at_stays_blank(self):
        created = self.client.post(
            "/api/consultations",
            headers=self.auth_headers(self.owner_token),
            json={
                "parent_wechat_name": "郑妈妈",
                "child_name": "郑小同",
                "grade": "七年级",
                "receiving_teacher": "何姝健",
                "consultation_subject": "数学",
                "need_detail": "已进班旧记录",
                "flow_stage": "成功进班",
                "completed_stages": ["成功进班"],
                "success_class_manual": "七年级数学班",
            },
        )
        self.assertEqual(created.status_code, 201)
        consultation_id = created.get_json()["id"]
        with lesson_manager.get_conn() as conn:
            conn.execute("UPDATE consultations SET ended_at='' WHERE id=?", (consultation_id,))

        response = self.client.get(f"/api/consultations/{consultation_id}", headers=self.auth_headers(self.owner_token))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["ended_at"], "")

    def test_consultation_enter_existing_class_marks_success_and_student_profile(self):
        created = self.create_consultation_record(**{
            "孩子姓名": "进班学生",
            "咨询科目": "数学",
            "年级": "七年级",
            "流程阶段": "已加小客服微信",
            "completed_stages": ["已加小客服微信"],
        })
        class_id = lesson_manager.save_class(
            "数学七年级1班",
            subject="数学",
            grade="七年级",
            class_type="group",
            organization_id=self.owner_user()["organization_id"],
        )
        response = self.client.post(
            f"/api/consultations/{created['id']}/enter-class",
            headers=self.auth_headers(self.owner_token),
            json={"mode": "existing", "class_id": class_id},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["item"]["closing_result"], "success")
        self.assertEqual(payload["item"]["flow_stage"], "咨询结束")
        self.assertEqual(payload["item"]["completed_stages"], ["已加小客服微信", "成功进班", "咨询结束"])
        self.assertEqual(payload["item"]["success_class_id"], class_id)
        self.assertEqual(payload["item"]["student_profile_status"], "created")
        class_students = lesson_manager.list_students_for_class(class_id)
        self.assertEqual([student["name"] for student in class_students], ["进班学生"])

    def test_consultation_enter_class_allows_converted_without_class(self):
        created = self.create_consultation_record(**{"孩子姓名": "暂未定班学生"})
        response = self.client.post(
            f"/api/consultations/{created['id']}/enter-class",
            headers=self.auth_headers(self.owner_token),
            json={"mode": "converted_without_class"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["item"]["closing_result"], "success")
        self.assertIsNone(payload["item"]["success_class_id"])
        self.assertEqual(payload["item"]["student_profile_status"], "needs_completion")

    def test_consultation_enter_quick_new_class_uses_structured_class_fields(self):
        teacher_token = self.create_member_token(username="teaching_teacher", display_name="带课老师")
        teacher_user = self.user_for_token(teacher_token)
        created = self.create_consultation_record(**{
            "孩子姓名": "快速建班学生",
            "咨询科目": "数学",
            "年级": "七年级",
        })
        response = self.client.post(
            f"/api/consultations/{created['id']}/enter-class",
            headers=self.auth_headers(self.owner_token),
            json={
                "mode": "quick_new_class",
                "class_name": "数学·七年级·2班",
                "subject": "数学",
                "grade": "七年级",
                "class_type": "group",
                "stage": "初中",
                "current_grade": "七年级",
                "class_number": "2",
                "cohort_year": 2026,
                "teaching_teacher_id": "teaching_teacher",
                "teaching_teacher": "带课老师",
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        class_id = payload["class_id"]
        created_class = lesson_manager.get_class(class_id)
        self.assertIsNotNone(created_class)
        self.assertEqual(created_class["class_type"], "group")
        self.assertEqual(created_class["subject"], "数学")
        self.assertEqual(created_class["stage"], "初中")
        self.assertEqual(created_class["current_grade"], "七年级")
        self.assertEqual(created_class["class_number"], "2")
        self.assertEqual(created_class["cohort_year"], 2026)
        self.assertEqual(created_class["teacher_name"], "带课老师")
        self.assertEqual(created_class["teacher_user_id"], teacher_user["id"])
        self.assertEqual(payload["item"]["success_class_id"], class_id)
        self.assertEqual(payload["item"]["teaching_teacher_added"], "已添加")
        self.assertEqual(payload["item"]["teaching_teacher"], "带课老师")
        self.assertEqual(payload["item"]["stage_teacher_ids"]["成功进班"], "teaching_teacher")
        class_students = lesson_manager.list_students_for_class(class_id)
        self.assertEqual([student["name"] for student in class_students], ["快速建班学生"])
        listed_classes = self.client.get("/api/classes", headers=self.auth_headers(self.owner_token))
        self.assertEqual(listed_classes.status_code, 200)
        self.assertIn(class_id, [item["id"] for item in listed_classes.get_json()])

    def test_consultation_enter_class_backfills_missing_subject_and_grade_from_selection(self):
        created = self.create_consultation_record(**{
            "孩子姓名": "补科目学生",
            "咨询科目": "",
            "年级": "",
        })
        class_id = lesson_manager.save_class(
            "物理八年级1班",
            subject="物理",
            grade="八年级",
            current_grade="八年级",
            class_type="group",
            organization_id=self.owner_user()["organization_id"],
        )
        response = self.client.post(
            f"/api/consultations/{created['id']}/enter-class",
            headers=self.auth_headers(self.owner_token),
            json={"mode": "existing", "class_id": class_id, "consultation_subject": "物理", "grade": "八年级"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["item"]["consultation_subject"], "物理")
        self.assertEqual(payload["item"]["grade"], "八年级")

    def test_transferred_member_can_enter_class_from_assigned_stage(self):
        teacher_token = self.create_member_token(username="trial_teacher", display_name="试听老师")
        created = self.client.post(
            "/api/consultations",
            headers=self.auth_headers(self.owner_token),
            json={
                "日期": "2026-03-12",
                "家长微信名": "转接进班家长",
                "孩子姓名": "转接进班学生",
                "年级": "七年级",
                "接待老师": "前台老师",
                "咨询科目": "数学",
                "具体需求": "试听后进班",
                "flow_stage": "待试听",
                "completed_stages": ["待试听"],
                "stage_teacher_ids": {"待试听": "trial_teacher"},
            },
        )
        self.assertEqual(created.status_code, 201)
        class_id = lesson_manager.save_class(
            "数学七年级2班",
            subject="数学",
            grade="七年级",
            class_type="group",
            organization_id=self.owner_user()["organization_id"],
        )

        response = self.client.post(
            f"/api/consultations/{created.get_json()['id']}/enter-class",
            headers=self.auth_headers(teacher_token),
            json={"mode": "existing", "class_id": class_id},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["item"]["closing_result"], "success")
        self.assertEqual(payload["item"]["success_class_id"], class_id)

    def test_owner_uploads_multiple_consultation_test_images(self):
        created = self.create_consultation_record()

        first = self.client.post(
            f"/api/consultations/{created['id']}/test-images",
            headers=self.auth_headers(self.owner_token),
            data={"image": (io.BytesIO(b"first-image"), "first.png")},
            content_type="multipart/form-data",
        )
        self.assertEqual(first.status_code, 201)
        second = self.client.post(
            f"/api/consultations/{created['id']}/test-images",
            headers=self.auth_headers(self.owner_token),
            data={"image": (io.BytesIO(b"second-image"), "second.jpg")},
            content_type="multipart/form-data",
        )
        self.assertEqual(second.status_code, 201)

        refreshed = self.client.get(f"/api/consultations/{created['id']}", headers=self.auth_headers(self.owner_token))
        images = refreshed.get_json()["test_images"]
        self.assertEqual(len(images), 2)
        self.assertTrue(images[0]["url"].startswith("/api/consultation-test-images/"))
        self.assertEqual(images[0]["filename"], "first.png")

    def test_owner_deletes_consultation_test_image_by_index(self):
        created = self.create_consultation_record()
        for filename in ("first.png", "second.jpg", "third.webp"):
            response = self.client.post(
                f"/api/consultations/{created['id']}/test-images",
                headers=self.auth_headers(self.owner_token),
                data={"image": (io.BytesIO(filename.encode("utf-8")), filename)},
                content_type="multipart/form-data",
            )
            self.assertEqual(response.status_code, 201)

        deleted = self.client.delete(
            f"/api/consultations/{created['id']}/test-images/1",
            headers=self.auth_headers(self.owner_token),
        )

        self.assertEqual(deleted.status_code, 200)
        images = deleted.get_json()["item"]["test_images"]
        self.assertEqual([image["filename"] for image in images], ["first.png", "third.webp"])

        missing = self.client.delete(
            f"/api/consultations/{created['id']}/test-images/5",
            headers=self.auth_headers(self.owner_token),
        )
        self.assertEqual(missing.status_code, 404)

    def test_members_can_view_and_create_but_not_edit_or_delete(self):
        member_token = self.create_member_token()
        member_user = self.user_for_token(member_token)
        self.create_consultation_record(assigned_user_id=member_user["id"])

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
            json={"跟进备注": "成员可改自己的咨询", "flow_stage": "正在沟通细节"},
        )
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.get_json()["follow_up_status"], "正在跟进")

        delete_response = self.client.delete(
            "/api/consultations/1",
            headers=self.auth_headers(member_token),
        )
        self.assertEqual(delete_response.status_code, 403)

    def test_member_sees_consultations_they_created_without_assignment(self):
        member_token = self.create_member_token(username="creator_teacher", display_name="创建老师")

        created = self.client.post(
            "/api/consultations",
            headers=self.auth_headers(member_token),
            json={
                "日期": "2026-03-12",
                "家长微信名": "自建家长",
                "孩子姓名": "自建学生",
                "年级": "五年级",
                "接待老师": "创建老师",
                "老师ID": "creator_teacher",
                "咨询科目": "数学",
                "具体需求": "老师自己接到的咨询",
            },
        )
        self.assertEqual(created.status_code, 201)

        listed = self.client.get("/api/consultations", headers=self.auth_headers(member_token))

        self.assertEqual(listed.status_code, 200)
        payload = listed.get_json()
        self.assertEqual([item["id"] for item in payload], [created.get_json()["id"]])
        self.assertFalse(payload[0]["is_transferred_consultation"])

    def test_member_self_assigned_created_consultation_is_not_marked_as_transfer(self):
        member_token = self.create_member_token(username="creator_teacher", display_name="创建老师")

        created = self.client.post(
            "/api/consultations",
            headers=self.auth_headers(member_token),
            json={
                "日期": "2026-03-12",
                "家长微信名": "自派家长",
                "孩子姓名": "自派学生",
                "年级": "五年级",
                "接待老师": "创建老师",
                "老师ID": "creator_teacher",
                "咨询科目": "数学",
                "具体需求": "老师自己创建并自己跟进试听",
                "flow_stage": "待试听",
                "completed_stages": ["待试听"],
                "assigned_stage": "待试听",
                "stage_teacher_ids": {"待试听": "creator_teacher"},
            },
        )
        self.assertEqual(created.status_code, 201)

        listed = self.client.get("/api/consultations", headers=self.auth_headers(member_token))

        self.assertEqual(listed.status_code, 200)
        payload = listed.get_json()
        self.assertEqual([item["id"] for item in payload], [created.get_json()["id"]])
        self.assertFalse(payload[0]["is_transferred_consultation"])
        self.assertEqual(payload[0]["transfer_marker"], "")
        self.assertEqual(payload[0]["current_responsibility"], "")
        self.assertTrue(payload[0]["can_edit_consultation"])

    def test_member_created_consultation_stays_self_owned_after_assigning_current_stage_to_self(self):
        member_token = self.create_member_token(username="cao_teacher", display_name="曹老师")
        created = self.client.post(
            "/api/consultations",
            headers=self.auth_headers(member_token),
            json={
                "日期": "2026-03-12",
                "家长微信名": "自转家长",
                "孩子姓名": "自转学生",
                "年级": "五年级",
                "接待老师": "曹老师",
                "老师ID": "cao_teacher",
                "咨询科目": "数学",
                "具体需求": "老师自己创建，后续自己沟通",
            },
        )
        self.assertEqual(created.status_code, 201)
        consultation_id = created.get_json()["id"]

        updated = self.client.put(
            f"/api/consultations/{consultation_id}",
            headers=self.auth_headers(member_token),
            json={
                "flow_stage": "正在沟通细节",
                "completed_stages": ["已加对应教师微信", "正在沟通细节"],
                "assigned_stage": "正在沟通细节",
                "stage_teacher_ids": {"正在沟通细节": "cao_teacher"},
                "follow_up_note": "曹老师自己继续沟通",
            },
        )
        self.assertEqual(updated.status_code, 200)

        listed = self.client.get("/api/consultations", headers=self.auth_headers(member_token))

        self.assertEqual(listed.status_code, 200)
        payload = listed.get_json()
        self.assertEqual([item["id"] for item in payload], [consultation_id])
        self.assertFalse(payload[0]["is_transferred_consultation"])
        self.assertEqual(payload[0]["transfer_marker"], "")
        self.assertEqual(payload[0]["current_responsibility"], "")
        self.assertTrue(payload[0]["can_edit_consultation"])

    def test_member_created_consultation_transferred_away_is_history_only_and_readonly(self):
        creator_token = self.create_member_token(username="creator_teacher", display_name="创建老师")
        assignee_token = self.create_member_token(username="trial_teacher", display_name="试听老师")
        self.user_for_token(assignee_token)

        created = self.client.post(
            "/api/consultations",
            headers=self.auth_headers(creator_token),
            json={
                "日期": "2026-03-12",
                "家长微信名": "创建转出家长",
                "孩子姓名": "创建转出学生",
                "年级": "五年级",
                "接待老师": "创建老师",
                "老师ID": "creator_teacher",
                "咨询科目": "数学",
                "具体需求": "创建后转给试听老师处理",
            },
        )
        self.assertEqual(created.status_code, 201)
        consultation_id = created.get_json()["id"]

        reassigned = self.client.put(
            f"/api/consultations/{consultation_id}",
            headers=self.auth_headers(self.owner_token),
            json={
                "flow_stage": "待试听",
                "assigned_stage": "待试听",
                "completed_stages": ["待试听"],
                "stage_teacher_ids": {"待试听": "trial_teacher"},
                "assignment_note": "创建老师转出，试听老师当前处理",
            },
        )
        self.assertEqual(reassigned.status_code, 200)

        current = self.client.get("/api/consultations", headers=self.auth_headers(creator_token))
        self.assertEqual(current.status_code, 200)
        self.assertEqual([item["id"] for item in current.get_json()], [])

        history = self.client.get("/api/consultations?scope=history", headers=self.auth_headers(creator_token))
        self.assertEqual(history.status_code, 200)
        history_payload = history.get_json()
        self.assertEqual([item["id"] for item in history_payload], [consultation_id])
        self.assertFalse(history_payload[0]["can_edit_consultation"])
        self.assertEqual(history_payload[0]["current_responsibility"], "试听教师：试听老师")

        stale_update = self.client.put(
            f"/api/consultations/{consultation_id}",
            headers=self.auth_headers(creator_token),
            json={"trial_teacher_note": "创建老师不应继续编辑转出咨询"},
        )
        self.assertEqual(stale_update.status_code, 403)

    def test_member_sees_stage_teacher_transfer_with_marker_and_note(self):
        teacher_token = self.create_member_token(username="trial_teacher", display_name="试听老师")
        self.user_for_token(teacher_token)

        created = self.client.post(
            "/api/consultations",
            headers=self.auth_headers(self.owner_token),
            json={
                "日期": "2026-03-12",
                "家长微信名": "转接家长",
                "孩子姓名": "转接学生",
                "年级": "五年级",
                "接待老师": "前台老师",
                "咨询科目": "数学",
                "具体需求": "需要试听",
                "flow_stage": "待试听",
                "completed_stages": ["已加小客服微信", "待试听"],
                "stage_teacher_ids": {"待试听": "trial_teacher"},
                "assignment_note": "请试听老师跟进周六试听",
            },
        )
        self.assertEqual(created.status_code, 201)

        listed = self.client.get("/api/consultations", headers=self.auth_headers(teacher_token))

        self.assertEqual(listed.status_code, 200)
        payload = listed.get_json()
        self.assertEqual([item["id"] for item in payload], [created.get_json()["id"]])
        self.assertTrue(payload[0]["is_transferred_consultation"])
        self.assertEqual(payload[0]["transfer_marker"], "咨询转接")
        self.assertEqual(payload[0]["assigned_stage"], "待试听")
        self.assertEqual(payload[0]["assignment_note"], "请试听老师跟进周六试听")
        self.assertEqual(payload[0]["current_responsibility"], "试听教师：试听老师")

    def test_member_sees_stage_teacher_transfer_through_linked_wecom_alias(self):
        teacher_token = self.create_member_token(username="site_teacher_a", display_name="网站老师A")
        self.user_for_token(teacher_token)
        create_alias = self.client.post(
            "/api/teacher-aliases",
            headers=self.auth_headers(self.owner_token),
            json={
                "wecom_userid": "wecom_external_a",
                "display_name": "企微老师A",
                "linked_username": "site_teacher_a",
                "aliases": ["A老师"],
            },
        )
        self.assertEqual(create_alias.status_code, 201)

        created = self.client.post(
            "/api/consultations",
            headers=self.auth_headers(self.owner_token),
            json={
                "日期": "2026-03-12",
                "家长微信名": "企微转接家长",
                "孩子姓名": "企微转接学生",
                "年级": "五年级",
                "接待老师": "前台老师",
                "咨询科目": "数学",
                "具体需求": "需要测试",
                "flow_stage": "待测试",
                "completed_stages": ["待测试"],
                "stage_teacher_ids": {"待测试": "wecom_external_a"},
                "assignment_note": "请测试老师接一下",
            },
        )
        self.assertEqual(created.status_code, 201)

        listed = self.client.get("/api/consultations", headers=self.auth_headers(teacher_token))

        self.assertEqual(listed.status_code, 200)
        payload = listed.get_json()
        self.assertEqual([item["id"] for item in payload], [created.get_json()["id"]])
        self.assertTrue(payload[0]["is_transferred_consultation"])
        self.assertEqual(payload[0]["assigned_stage"], "待测试")
        self.assertEqual(payload[0]["current_responsibility"], "测试教师：网站老师A")
        self.assertEqual(payload[0]["assignment_note"], "请测试老师接一下")

    def test_member_can_update_transferred_consultation_from_assigned_stage_only(self):
        teacher_token = self.create_member_token(username="trial_teacher", display_name="试听老师")
        self.user_for_token(teacher_token)
        created = self.client.post(
            "/api/consultations",
            headers=self.auth_headers(self.owner_token),
            json={
                "日期": "2026-03-12",
                "家长微信名": "转接家长",
                "孩子姓名": "转接学生",
                "年级": "五年级",
                "接待老师": "前台老师",
                "咨询科目": "数学",
                "具体需求": "需要试听",
                "flow_stage": "待试听",
                "completed_stages": ["已加小客服微信", "待试听"],
                "stage_teacher_ids": {"待试听": "trial_teacher"},
            },
        )
        consultation_id = created.get_json()["id"]

        earlier_update = self.client.put(
            f"/api/consultations/{consultation_id}",
            headers=self.auth_headers(teacher_token),
            json={"customer_service_note": "回头改前面客服内容"},
        )
        self.assertEqual(earlier_update.status_code, 403)

        flow_state_update = self.client.put(
            f"/api/consultations/{consultation_id}",
            headers=self.auth_headers(teacher_token),
            json={
                "completed_stages": ["已加小客服微信", "已加对应教师微信", "待试听"],
                "stage_teacher_ids": {
                    "已加对应教师微信": "trial_teacher",
                    "待试听": "trial_teacher",
                },
            },
        )
        self.assertEqual(flow_state_update.status_code, 403)

        basic_info_update = self.client.put(
            f"/api/consultations/{consultation_id}",
            headers=self.auth_headers(teacher_token),
            json={"child_name": "改掉学生名", "consultation_subject": "英语"},
        )
        self.assertEqual(basic_info_update.status_code, 403)

        stage_update = self.client.put(
            f"/api/consultations/{consultation_id}",
            headers=self.auth_headers(teacher_token),
            json={"trial_teacher_note": "试听老师已沟通时间"},
        )
        self.assertEqual(stage_update.status_code, 200)
        self.assertEqual(stage_update.get_json()["trial_teacher_note"], "试听老师已沟通时间")

    def test_member_can_update_current_communication_stage_with_partial_teacher_map(self):
        teacher_token = self.create_member_token(username="cao_teacher", display_name="曹老师")
        self.user_for_token(teacher_token)
        created = self.client.post(
            "/api/consultations",
            headers=self.auth_headers(self.owner_token),
            json={
                "日期": "2026-03-12",
                "家长微信名": "沟通家长",
                "孩子姓名": "沟通学生",
                "年级": "五年级",
                "接待老师": "前台老师",
                "咨询科目": "数学",
                "具体需求": "已经加教师微信，正在沟通",
                "flow_stage": "正在沟通细节",
                "completed_stages": ["已加对应教师微信", "正在沟通细节"],
                "assigned_stage": "正在沟通细节",
                "stage_teacher_ids": {
                    "已加对应教师微信": "cao_teacher",
                    "正在沟通细节": "cao_teacher",
                },
                "communication_teacher_added": "曹老师",
            },
        )
        self.assertEqual(created.status_code, 201)
        consultation_id = created.get_json()["id"]

        updated = self.client.put(
            f"/api/consultations/{consultation_id}",
            headers=self.auth_headers(teacher_token),
            json={
                "stage_teacher_ids": {"正在沟通细节": "cao_teacher"},
                "follow_up_note": "曹老师确认继续沟通",
            },
        )

        self.assertEqual(updated.status_code, 200)
        payload = updated.get_json()
        self.assertEqual(payload["follow_up_note"], "曹老师确认继续沟通")
        self.assertEqual(payload["stage_teacher_ids"]["已加对应教师微信"], "cao_teacher")
        self.assertEqual(payload["stage_teacher_ids"]["正在沟通细节"], "cao_teacher")

    def test_member_transferred_to_test_can_edit_test_and_later_stages_only(self):
        teacher_token = self.create_member_token(username="test_teacher", display_name="测试老师")
        self.user_for_token(teacher_token)
        created = self.client.post(
            "/api/consultations",
            headers=self.auth_headers(self.owner_token),
            json={
                "日期": "2026-03-12",
                "家长微信名": "测试转接家长",
                "孩子姓名": "测试转接学生",
                "年级": "六年级",
                "接待老师": "前台老师",
                "咨询科目": "数学",
                "具体需求": "先测试再试听",
                "flow_stage": "待测试",
                "completed_stages": ["已加小客服微信", "已加对应教师微信", "待测试"],
                "stage_teacher_ids": {"待测试": "test_teacher"},
                "communication_teacher_note": "前面老师已经沟通过",
            },
        )
        consultation_id = created.get_json()["id"]

        prior_stage_update = self.client.put(
            f"/api/consultations/{consultation_id}",
            headers=self.auth_headers(teacher_token),
            json={"communication_teacher_note": "测试老师不该改前面的沟通内容"},
        )
        self.assertEqual(prior_stage_update.status_code, 403)

        allowed_update = self.client.put(
            f"/api/consultations/{consultation_id}",
            headers=self.auth_headers(teacher_token),
            json={
                "test_taken": "是",
                "test_note": "测试完成，建议试听七年级班",
                "trial_teacher_note": "已和家长约试听",
                "teaching_teacher_note": "如果进班，提醒带课老师关注计算细节",
            },
        )
        self.assertEqual(allowed_update.status_code, 200)
        payload = allowed_update.get_json()
        self.assertEqual(payload["test_note"], "测试完成，建议试听七年级班")
        self.assertEqual(payload["trial_teacher_note"], "已和家长约试听")
        self.assertEqual(payload["teaching_teacher_note"], "如果进班，提醒带课老师关注计算细节")

        uploaded = self.client.post(
            f"/api/consultations/{consultation_id}/test-images",
            headers=self.auth_headers(self.owner_token),
            data={"image": (io.BytesIO(b"test-image"), "test.png")},
            content_type="multipart/form-data",
        )
        self.assertEqual(uploaded.status_code, 201)

        deleted = self.client.delete(
            f"/api/consultations/{consultation_id}/test-images/0",
            headers=self.auth_headers(teacher_token),
        )
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(deleted.get_json()["item"]["test_images"], [])

    def test_member_transferred_after_test_cannot_delete_test_images(self):
        teacher_token = self.create_member_token(username="trial_teacher_after_test", display_name="试听老师")
        self.user_for_token(teacher_token)
        created = self.client.post(
            "/api/consultations",
            headers=self.auth_headers(self.owner_token),
            json={
                "日期": "2026-03-12",
                "家长微信名": "试听转接家长",
                "孩子姓名": "试听转接学生",
                "年级": "六年级",
                "接待老师": "前台老师",
                "咨询科目": "数学",
                "具体需求": "测试后试听",
                "flow_stage": "待试听",
                "completed_stages": ["已加小客服微信", "待测试", "待试听"],
                "stage_teacher_ids": {"待试听": "trial_teacher_after_test"},
            },
        )
        consultation_id = created.get_json()["id"]
        uploaded = self.client.post(
            f"/api/consultations/{consultation_id}/test-images",
            headers=self.auth_headers(self.owner_token),
            data={"image": (io.BytesIO(b"test-image"), "test.png")},
            content_type="multipart/form-data",
        )
        self.assertEqual(uploaded.status_code, 201)

        deleted = self.client.delete(
            f"/api/consultations/{consultation_id}/test-images/0",
            headers=self.auth_headers(teacher_token),
        )
        self.assertEqual(deleted.status_code, 403)

    def test_previous_stage_teacher_can_view_same_stage_transfer_in_history_but_cannot_edit(self):
        first_token = self.create_member_token(username="trial_teacher_a", display_name="试听甲")
        self.user_for_token(first_token)
        second_token = self.create_member_token(username="trial_teacher_b", display_name="试听乙")
        self.user_for_token(second_token)
        created = self.client.post(
            "/api/consultations",
            headers=self.auth_headers(self.owner_token),
            json={
                "日期": "2026-03-12",
                "家长微信名": "转交家长",
                "孩子姓名": "转交学生",
                "年级": "五年级",
                "接待老师": "前台老师",
                "咨询科目": "数学",
                "具体需求": "试听老师需要换人",
                "flow_stage": "待试听",
                "completed_stages": ["待试听"],
                "assigned_stage": "待试听",
                "stage_teacher_ids": {"待试听": "trial_teacher_b"},
                "assignment_note": "原试听甲已转交给试听乙",
            },
        )
        self.assertEqual(created.status_code, 201)
        consultation_id = created.get_json()["id"]
        with lesson_manager.get_conn() as conn:
            conn.execute(
                "UPDATE consultations SET assigned_user_id=? WHERE id=?",
                (self.user_for_token(first_token)["id"], consultation_id),
            )

        listed = self.client.get("/api/consultations", headers=self.auth_headers(first_token))
        self.assertEqual(listed.status_code, 200)
        self.assertEqual([item["id"] for item in listed.get_json()], [])

        history = self.client.get("/api/consultations?scope=history", headers=self.auth_headers(first_token))
        self.assertEqual(history.status_code, 200)
        self.assertEqual([item["id"] for item in history.get_json()], [consultation_id])
        self.assertFalse(history.get_json()[0]["can_edit_consultation"])
        self.assertEqual(history.get_json()[0]["current_responsibility"], "试听教师：试听乙")

        stale_update = self.client.put(
            f"/api/consultations/{consultation_id}",
            headers=self.auth_headers(first_token),
            json={"trial_teacher_note": "甲老师不该继续改试听内容"},
        )
        self.assertEqual(stale_update.status_code, 403)

    def test_current_stage_teacher_can_transfer_same_stage_to_another_teacher(self):
        first_token = self.create_member_token(username="trial_teacher_a", display_name="试听甲")
        self.user_for_token(first_token)
        second_token = self.create_member_token(username="trial_teacher_b", display_name="试听乙")
        self.user_for_token(second_token)
        created = self.client.post(
            "/api/consultations",
            headers=self.auth_headers(self.owner_token),
            json={
                "日期": "2026-03-12",
                "家长微信名": "转交家长",
                "孩子姓名": "转交学生",
                "年级": "五年级",
                "接待老师": "前台老师",
                "咨询科目": "数学",
                "具体需求": "试听老师需要换人",
                "flow_stage": "待试听",
                "completed_stages": ["待试听"],
                "assigned_stage": "待试听",
                "stage_teacher_ids": {"待试听": "trial_teacher_a"},
            },
        )
        self.assertEqual(created.status_code, 201)
        consultation_id = created.get_json()["id"]

        transfer = self.client.put(
            f"/api/consultations/{consultation_id}",
            headers=self.auth_headers(first_token),
            json={
                "stage_teacher_ids": {"待试听": "trial_teacher_b"},
                "assignment_note": "试听甲转交给试听乙",
            },
        )
        self.assertEqual(transfer.status_code, 200)
        self.assertEqual(transfer.get_json()["stage_teacher_ids"]["待试听"], "trial_teacher_b")
        self.assertEqual(
            transfer.get_json()["responsibility_history"],
            [
                {
                    "stage": "待试听",
                    "from_teacher_id": "trial_teacher_a",
                    "from_teacher_name": "试听甲",
                    "to_teacher_id": "trial_teacher_b",
                    "to_teacher_name": "试听乙",
                    "note": "试听甲转交给试听乙",
                    "change_kind": "transfer",
                }
            ],
        )

        listed_for_second = self.client.get("/api/consultations", headers=self.auth_headers(second_token))
        self.assertEqual(listed_for_second.status_code, 200)
        payload = listed_for_second.get_json()
        self.assertEqual([item["id"] for item in payload], [consultation_id])
        self.assertEqual(payload[0]["current_responsibility"], "试听教师：试听乙")
        self.assertEqual(payload[0]["responsibility_history"][0]["from_teacher_name"], "试听甲")
        self.assertTrue(payload[0]["can_edit_consultation"])

        listed_for_first = self.client.get("/api/consultations", headers=self.auth_headers(first_token))
        self.assertEqual(listed_for_first.status_code, 200)
        first_payload = listed_for_first.get_json()
        self.assertEqual([item["id"] for item in first_payload], [])

        history_for_first = self.client.get("/api/consultations?scope=history", headers=self.auth_headers(first_token))
        self.assertEqual(history_for_first.status_code, 200)
        history_payload = history_for_first.get_json()
        self.assertEqual([item["id"] for item in history_payload], [consultation_id])
        self.assertFalse(history_payload[0]["can_edit_consultation"])
        self.assertEqual(history_payload[0]["transfer_marker"], "咨询转接")

    def test_member_history_scope_includes_historical_transfer_but_current_scope_does_not(self):
        first_token = self.create_member_token(username="test_teacher_a", display_name="小姝老师测试")
        second_token = self.create_member_token(username="trial_teacher_b", display_name="何天兰试听")
        self.user_for_token(first_token)
        self.user_for_token(second_token)
        created = self.client.post(
            "/api/consultations",
            headers=self.auth_headers(self.owner_token),
            json={
                "日期": "2026-03-12",
                "家长微信名": "历史转接家长",
                "孩子姓名": "历史转接学生",
                "年级": "五年级",
                "接待老师": "前台老师",
                "咨询科目": "数学",
                "具体需求": "先测试再试听",
                "flow_stage": "待试听",
                "completed_stages": ["待测试", "待试听"],
                "assigned_stage": "待试听",
                "stage_teacher_ids": {"待测试": "test_teacher_a", "待试听": "trial_teacher_b"},
                "assignment_note": "测试完成，转给何天兰试听",
            },
        )
        self.assertEqual(created.status_code, 201)
        consultation_id = created.get_json()["id"]

        current = self.client.get("/api/consultations", headers=self.auth_headers(first_token))
        self.assertEqual(current.status_code, 200)
        self.assertEqual([item["id"] for item in current.get_json()], [])

        history = self.client.get("/api/consultations?scope=history", headers=self.auth_headers(first_token))
        self.assertEqual(history.status_code, 200)
        history_payload = history.get_json()
        self.assertEqual([item["id"] for item in history_payload], [consultation_id])
        self.assertEqual(history_payload[0]["current_responsibility"], "试听教师：何天兰试听")
        self.assertFalse(history_payload[0]["can_edit_consultation"])

    def test_member_history_scope_excludes_current_transfer_assignment(self):
        transfer_token = self.create_member_token(username="trial_teacher_current", display_name="当前试听老师")
        self.user_for_token(transfer_token)
        created = self.client.post(
            "/api/consultations",
            headers=self.auth_headers(self.owner_token),
            json={
                "日期": "2026-03-12",
                "家长微信名": "当前转接家长",
                "孩子姓名": "当前转接学生",
                "年级": "五年级",
                "接待老师": "前台老师",
                "咨询科目": "数学",
                "具体需求": "当前需要试听老师处理",
                "flow_stage": "待试听",
                "completed_stages": ["待试听"],
                "assigned_stage": "待试听",
                "stage_teacher_ids": {"待试听": "trial_teacher_current"},
            },
        )
        self.assertEqual(created.status_code, 201)
        consultation_id = created.get_json()["id"]

        current = self.client.get("/api/consultations", headers=self.auth_headers(transfer_token))
        self.assertEqual(current.status_code, 200)
        self.assertEqual([item["id"] for item in current.get_json()], [consultation_id])
        self.assertTrue(current.get_json()[0]["can_edit_consultation"])

        history = self.client.get("/api/consultations?scope=history", headers=self.auth_headers(transfer_token))
        self.assertEqual(history.status_code, 200)
        self.assertEqual(history.get_json(), [])

    def test_member_ownership_filter_distinguishes_created_and_transferred_consultations(self):
        creator_token = self.create_member_token(username="creator_teacher", display_name="创建老师")
        transfer_token = self.create_member_token(username="transfer_teacher", display_name="转接老师")
        creator_user = self.user_for_token(creator_token)
        self.user_for_token(transfer_token)
        created_by_member = self.client.post(
            "/api/consultations",
            headers=self.auth_headers(creator_token),
            json={
                "日期": "2026-03-12",
                "家长微信名": "自创家长",
                "孩子姓名": "自创学生",
                "年级": "五年级",
                "接待老师": "创建老师",
                "老师ID": "creator_teacher",
                "咨询科目": "数学",
                "具体需求": "老师自己创建",
            },
        )
        self.assertEqual(created_by_member.status_code, 201)
        transferred = self.client.post(
            "/api/consultations",
            headers=self.auth_headers(self.owner_token),
            json={
                "日期": "2026-03-13",
                "家长微信名": "转接家长",
                "孩子姓名": "转接学生",
                "年级": "五年级",
                "接待老师": "前台老师",
                "咨询科目": "数学",
                "具体需求": "需要试听",
                "flow_stage": "待试听",
                "assigned_stage": "待试听",
                "stage_teacher_ids": {"待试听": "transfer_teacher"},
            },
        )
        self.assertEqual(transferred.status_code, 201)
        own_assigned = self.create_consultation_record(
            assigned_user_id=creator_user["id"],
            **{"家长微信名": "旧派单家长", "孩子姓名": "旧派单学生"},
        )

        created_only = self.client.get(
            "/api/consultations?ownership=created",
            headers=self.auth_headers(creator_token),
        )
        self.assertEqual(created_only.status_code, 200)
        self.assertEqual([item["id"] for item in created_only.get_json()], [created_by_member.get_json()["id"]])

        transferred_only = self.client.get(
            "/api/consultations?ownership=transferred",
            headers=self.auth_headers(transfer_token),
        )
        self.assertEqual(transferred_only.status_code, 200)
        self.assertEqual([item["id"] for item in transferred_only.get_json()], [transferred.get_json()["id"]])

        creator_transferred_only = self.client.get(
            "/api/consultations?ownership=transferred",
            headers=self.auth_headers(creator_token),
        )
        self.assertEqual(creator_transferred_only.status_code, 200)
        self.assertEqual([item["id"] for item in creator_transferred_only.get_json()], [own_assigned["id"]])

    def test_owner_can_reassign_current_stage_teacher_without_leaving_old_teacher_visibility(self):
        first_token = self.create_member_token(username="trial_teacher_a", display_name="试听甲")
        self.user_for_token(first_token)
        second_token = self.create_member_token(username="trial_teacher_b", display_name="试听乙")
        self.user_for_token(second_token)
        created = self.client.post(
            "/api/consultations",
            headers=self.auth_headers(self.owner_token),
            json={
                "日期": "2026-03-12",
                "家长微信名": "负责人改派家长",
                "孩子姓名": "负责人改派学生",
                "年级": "五年级",
                "接待老师": "前台老师",
                "咨询科目": "数学",
                "具体需求": "试听老师临时换人",
                "flow_stage": "待试听",
                "completed_stages": ["待试听"],
                "assigned_stage": "待试听",
                "stage_teacher_ids": {"待试听": "trial_teacher_a"},
            },
        )
        self.assertEqual(created.status_code, 201)
        consultation_id = created.get_json()["id"]

        reassigned = self.client.put(
            f"/api/consultations/{consultation_id}",
            headers=self.auth_headers(self.owner_token),
            json={
                "stage_teacher_ids": {"待试听": "trial_teacher_b"},
                "assignment_note": "负责人改派给试听乙",
            },
        )

        self.assertEqual(reassigned.status_code, 200)
        self.assertEqual(reassigned.get_json()["stage_teacher_ids"]["待试听"], "trial_teacher_b")
        self.assertEqual(
            reassigned.get_json()["responsibility_history"],
            [
                {
                    "stage": "待试听",
                    "from_teacher_id": "trial_teacher_a",
                    "from_teacher_name": "试听甲",
                    "to_teacher_id": "trial_teacher_b",
                    "to_teacher_name": "试听乙",
                    "note": "负责人改派给试听乙",
                    "change_kind": "reassign",
                }
            ],
        )

        listed_for_second = self.client.get("/api/consultations", headers=self.auth_headers(second_token))
        self.assertEqual(listed_for_second.status_code, 200)
        second_payload = listed_for_second.get_json()
        self.assertEqual([item["id"] for item in second_payload], [consultation_id])
        self.assertEqual(second_payload[0]["current_responsibility"], "试听教师：试听乙")
        self.assertTrue(second_payload[0]["can_edit_consultation"])

        listed_for_first = self.client.get("/api/consultations", headers=self.auth_headers(first_token))
        self.assertEqual(listed_for_first.status_code, 200)
        first_payload = listed_for_first.get_json()
        self.assertEqual([item["id"] for item in first_payload], [])

        history_for_first = self.client.get("/api/consultations?scope=history", headers=self.auth_headers(first_token))
        self.assertEqual(history_for_first.status_code, 200)
        first_history_payload = history_for_first.get_json()
        self.assertEqual([item["id"] for item in first_history_payload], [consultation_id])
        self.assertFalse(first_history_payload[0]["can_edit_consultation"])
        self.assertEqual(first_history_payload[0]["current_responsibility"], "试听教师：试听乙")

    def test_member_cannot_update_other_teacher_record(self):
        member_token = self.create_member_token(username="teacher_a", display_name="Teacher A")
        other_token = self.create_member_token(username="teacher_b", display_name="Teacher B")
        other_user = self.user_for_token(other_token)
        other_assigned = self.create_consultation_record(assigned_user_id=other_user["id"])

        update_other = self.client.put(
            f"/api/consultations/{other_assigned['id']}",
            headers=self.auth_headers(member_token),
            json={"flow_stage": "正在沟通细节"},
        )

        self.assertEqual(update_other.status_code, 404)

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
        member_token = self.create_member_token()
        member_user = self.user_for_token(member_token)
        self.create_consultation_record(assigned_user_id=member_user["id"])

        response = self.client.get("/api/consultations", headers=self.auth_headers(self.owner_token))

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload[0]["receiving_teacher"], "Teacher A")
        self.assertEqual(payload[0]["teacher_id"], "teacher_a")
        self.assertEqual(payload[0]["teacher_display_name"], "Teacher A")

    def test_list_exposes_teacher_display_name_from_teacher_alias_file(self):
        self.write_teacher_aliases({"teacher_a": ["雷老师", "雷文浩"]})
        member_token = self.create_member_token()
        member_user = self.user_for_token(member_token)
        self.create_consultation_record(assigned_user_id=member_user["id"])

        response = self.client.get("/api/consultations", headers=self.auth_headers(self.owner_token))

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload[0]["teacher_display_name"], "Teacher A")

    def test_list_normalizes_grade_and_source_channel(self):
        self.create_consultation_record(
            年级="5年级",
            来源渠道="朋友介绍",
            家长微信名="秋秋",
            孩子姓名="秋秋",
        )

        response = self.client.get("/api/consultations", headers=self.auth_headers(self.owner_token))

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload[0]["grade"], "五年级")
        self.assertEqual(payload[0]["source_channel"], "转介绍")
        self.assertEqual(payload[0]["source_channel_note"], "")

    def test_list_normalizes_mixed_name_and_source_channel_phrase(self):
        self.create_consultation_record(
            年级="5年级",
            来源渠道="张裕空转介绍",
            家长微信名="张裕空妈妈",
            孩子姓名="张裕空",
        )

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

    def test_teacher_alias_endpoint_links_external_id_to_website_member(self):
        member_token = self.create_member_token(username="site_teacher_a", display_name="网站老师A")
        member_user = self.user_for_token(member_token)

        create_alias = self.client.post(
            "/api/teacher-aliases",
            headers=self.auth_headers(self.owner_token),
            json={
                "wecom_userid": "wecom_external_a",
                "display_name": "企微老师A",
                "linked_username": "site_teacher_a",
                "aliases": ["A老师"],
            },
        )

        self.assertEqual(create_alias.status_code, 201)
        created_alias = create_alias.get_json()
        self.assertEqual(created_alias["linked_username"], "site_teacher_a")

        teacher_options = self.client.get(
            "/api/consultation-teachers",
            headers=self.auth_headers(self.owner_token),
        )
        self.assertEqual(teacher_options.status_code, 200)
        teacher_by_id = {item["teacher_id"]: item for item in teacher_options.get_json()}
        self.assertIn("site_teacher_a", teacher_by_id)
        self.assertNotIn("wecom_external_a", teacher_by_id)
        self.assertIn("wecom_external_a", teacher_by_id["site_teacher_a"]["aliases"])

        consultation = self.client.post(
            "/api/consultations",
            headers=self.auth_headers(self.owner_token),
            json={
                "date": "2026-04-22",
                "parent_wechat_name": "张妈妈",
                "child_name": "张小明",
                "grade": "五年级",
                "receiving_teacher": "企微老师A",
                "teacher_id": "wecom_external_a",
                "consultation_subject": "数学",
                "need_detail": "想补基础",
                "source_channel": "朋友介绍",
                "follow_up_status": "待邀约",
            },
        )

        self.assertEqual(consultation.status_code, 201)
        payload = consultation.get_json()
        self.assertEqual(payload["assigned_user_id"], member_user["id"])
        self.assertEqual(payload["teacher_id"], "site_teacher_a")

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

    def test_normalize_batch_parse_result_drops_unknown_follow_up_status_with_warning(self):
        payload = lesson_manager.normalize_consultation_batch_parse_result(
            {
                "items": [
                    {
                        "action": "create",
                        "target_id": None,
                        "reason": "新增咨询记录",
                        "fields": {
                            "parent_wechat_name": "张妈妈",
                            "follow_up_status": "待开课缴费",
                            "follow_up_note": "模型误写了不存在的状态",
                        },
                        "warnings": [],
                    }
                ],
                "warnings": [],
            }
        )

        draft = payload["items"][0]
        self.assertEqual(draft["action"], "create")
        self.assertIsNone(draft["target_id"])
        self.assertEqual(
            draft["fields"],
            {
                "parent_wechat_name": "张妈妈",
                "follow_up_note": "模型误写了不存在的状态",
            },
        )
        self.assertEqual(
            draft["warnings"],
            ["已忽略不存在的跟进状态：待开课缴费。可选值仅支持：待邀约、跟进中、已报班、已劝退。"],
        )

    def test_member_sees_only_assigned_consultations(self):
        """Member should only see consultations assigned to them via assigned_user_id"""
        member1_token = self.create_member_token("member1", "Member 1", "test123")
        member2_token = self.create_member_token("member2", "Member 2", "test123")
        member1_row = self.user_for_token(member1_token)
        member2_row = self.user_for_token(member2_token)
        owner_token = self.owner_token

        c1_response = self.client.post(
            "/api/consultations",
            headers=self.auth_headers(owner_token),
            json={
                "日期": "2026-03-12",
                "家长微信名": "家长1",
                "孩子姓名": "学生1",
                "年级": "一年级",
                "接待老师": "何姝健",
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
                "接待老师": "何姝健",
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
                "接待老师": "何姝健",
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
