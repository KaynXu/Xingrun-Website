# WeChat Parent Wrong Question MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a lightweight WeChat mini program parent upload flow that writes canonically scoped wrong-question records into the website `智能错题` workspace.

**Architecture:** The Flask + SQLite website repo remains the source of truth for class, student, teacher, invite, binding, and wrong-question metadata. The existing Node/TypeScript mini-program backend becomes a thin WeChat BFF that exchanges `wx.login` codes for `openid`, uploads files, and forwards canonical operations to the website over a shared service token. The WeChat mini program itself stays intentionally small: bind class, choose student, upload image, show success.

**Tech Stack:** Flask, SQLite, Python `unittest`, Vite + React + `tsx --test`, Node.js + TypeScript + Express, native WeChat mini program JavaScript

---

## Working Context

- Website repo: `/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary`
- Mini-program repo: `/Users/ark.mini/Desktop/Xingrun-MiniProgram`
- These are separate git repositories and must be committed independently.
- Existing website student APIs already live in [app.py](/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/app.py) and [lesson_manager.py](/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/lesson_manager.py).
- Existing mini backend already exposes WeChat login helpers in `/Users/ark.mini/Desktop/Xingrun-MiniProgram/backend/src/wechat.ts`.

## File Map

### Website Repo

- Modify: `/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/lesson_manager.py`
  - Add class invite, parent WeChat account, binding, and local wrong-question submission persistence helpers.
- Modify: `/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/config_runtime.py`
  - Add shared service-token runtime config for mini backend -> website calls.
- Modify: `/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/.env.runtime.example`
  - Document new runtime env vars.
- Modify: `/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/app.py`
  - Add class invite APIs, WeChat service endpoints, and local wrong-question record handling.
- Modify: `/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/smart_wrong_questions.py`
  - Add list/detail merge helpers for local `wechat_mp` records and downstream proxy data.
- Modify: `/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/frontend/src/App.tsx`
  - Add class invite UI inside class management.
- Modify: `/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/frontend/src/smartWrongQuestions.ts`
  - Extend record typing for `source`, local-review metadata, and source badge helpers.
- Modify: `/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/frontend/src/SmartWrongQuestionsPage.tsx`
  - Surface `wechat_mp` source badges and local-record review affordances.
- Create: `/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/tests/test_wechat_parent_upload_data.py`
  - Focused data-layer tests for new persistence helpers.
- Create: `/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/tests/test_wechat_parent_upload_api.py`
  - Flask API tests for invite, binding, service auth, and upload entrypoints.
- Modify: `/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/tests/test_smart_wrong_questions_api.py`
  - Cover merged local + downstream record behavior.
- Create: `/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/frontend/src/class-management-invite.test.tsx`
  - UI test for class invite card.
- Modify: `/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/frontend/src/smart-wrong-questions.test.ts`
  - Cover source badge and local-record normalization.

### Mini-Program Repo

- Create: `/Users/ark.mini/Desktop/Xingrun-MiniProgram/backend/src/website-client.ts`
  - Shared HTTP client for calling website WeChat APIs.
- Modify: `/Users/ark.mini/Desktop/Xingrun-MiniProgram/backend/src/index.ts`
  - Add parent login, bind, list bindings, and upload bridge endpoints.
- Create: `/Users/ark.mini/Desktop/Xingrun-MiniProgram/backend/src/parent-wechat-bridge.test.ts`
  - Integration tests for the new mini backend bridge routes.
- Modify: `/Users/ark.mini/Desktop/Xingrun-MiniProgram/miniprogram/app.json`
  - Register the new lightweight pages.
- Modify: `/Users/ark.mini/Desktop/Xingrun-MiniProgram/miniprogram/app.js`
  - Store parent session and binding cache in `globalData`.
- Create: `/Users/ark.mini/Desktop/Xingrun-MiniProgram/miniprogram/utils/parentApi.js`
  - Shared request helpers for new parent flow.
- Create: `/Users/ark.mini/Desktop/Xingrun-MiniProgram/miniprogram/utils/parentApi.test.js`
  - Node tests for parent request/normalization helpers.
- Create: `/Users/ark.mini/Desktop/Xingrun-MiniProgram/miniprogram/pages/parent-bind/index.js`
- Create: `/Users/ark.mini/Desktop/Xingrun-MiniProgram/miniprogram/pages/parent-bind/index.wxml`
- Create: `/Users/ark.mini/Desktop/Xingrun-MiniProgram/miniprogram/pages/parent-bind/index.wxss`
  - Bind class invite and choose students.
- Create: `/Users/ark.mini/Desktop/Xingrun-MiniProgram/miniprogram/pages/parent-home/index.js`
- Create: `/Users/ark.mini/Desktop/Xingrun-MiniProgram/miniprogram/pages/parent-home/index.wxml`
- Create: `/Users/ark.mini/Desktop/Xingrun-MiniProgram/miniprogram/pages/parent-home/index.wxss`
  - Show bound students and entry to upload.
- Create: `/Users/ark.mini/Desktop/Xingrun-MiniProgram/miniprogram/pages/parent-upload/index.js`
- Create: `/Users/ark.mini/Desktop/Xingrun-MiniProgram/miniprogram/pages/parent-upload/index.wxml`
- Create: `/Users/ark.mini/Desktop/Xingrun-MiniProgram/miniprogram/pages/parent-upload/index.wxss`
  - Choose image, preview, submit, and render success state.
- Modify: `/Users/ark.mini/Desktop/Xingrun-MiniProgram/miniprogram/pages/index/index.js`
  - Redirect into the new parent flow instead of the old roster-first flow.

### Runtime Config

- Website config keys:
  - `XR_WECHAT_SERVICE_TOKEN`
- Mini backend env keys:
  - `WEBSITE_API_BASE_URL`
  - `WEBSITE_API_TOKEN`

---

### Task 1: Add Website Persistence Primitives

**Files:**
- Modify: `/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/lesson_manager.py`
- Test: `/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/tests/test_wechat_parent_upload_data.py`

- [ ] **Step 1: Write the failing data-layer tests**

```python
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import lesson_manager


class WeChatParentUploadDataTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        lesson_manager.DB_PATH = Path(self.temp_dir.name) / "lessons.db"
        lesson_manager.init_db()
        self.organization_id = 1
        self.owner_id = 1
        self.class_id = lesson_manager.save_class(
            "六年级 1 班",
            subject="数学",
            grade="六年级",
            organization_id=self.organization_id,
        )
        lesson_manager.set_class_teacher_user_id(self.class_id, self.owner_id)
        self.student = lesson_manager.create_student_for_class(self.class_id, "Alice")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_class_invite_is_reused_until_reset(self):
        first = lesson_manager.get_or_create_active_class_invite(self.class_id, self.owner_id)
        second = lesson_manager.get_or_create_active_class_invite(self.class_id, self.owner_id)
        reset = lesson_manager.reset_class_invite(self.class_id, self.owner_id)

        self.assertEqual(first["id"], second["id"])
        self.assertEqual(first["class_id"], self.class_id)
        self.assertNotEqual(first["invite_code"], reset["invite_code"])
        self.assertEqual(reset["status"], "active")

    def test_parent_binding_and_submission_store_canonical_ids(self):
        account = lesson_manager.upsert_parent_wechat_account(
            openid="openid-parent-1",
            nickname_snapshot="Alice 妈妈",
            avatar_url_snapshot="https://example.com/avatar.png",
        )
        binding = lesson_manager.bind_parent_to_student(
            parent_wechat_account_id=account["id"],
            class_id=self.class_id,
            student_id=self.student["id"],
        )
        submission = lesson_manager.create_wechat_wrong_question_submission(
            binding_id=binding["id"],
            image_url="https://files.example.com/wrong-question.png",
            parent_note="请老师看一下这题",
        )

        self.assertEqual(binding["teacher_user_id"], self.owner_id)
        self.assertEqual(submission["class_id"], self.class_id)
        self.assertEqual(submission["student_id"], self.student["id"])
        self.assertEqual(submission["teacher_user_id"], self.owner_id)
        self.assertEqual(submission["source"], "wechat_mp")
        self.assertEqual(submission["status"], "pending")
```

- [ ] **Step 2: Run the data-layer tests to verify they fail**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary && /Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/.venv/bin/python -m unittest tests.test_wechat_parent_upload_data -v`

Expected: FAIL with `AttributeError` for missing functions like `get_or_create_active_class_invite` and `upsert_parent_wechat_account`.

- [ ] **Step 3: Add schema and helper functions in `lesson_manager.py`**

```python
def get_or_create_active_class_invite(class_id: int, actor_user_id: int) -> dict:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT ci.*, c.organization_id
            FROM class_invite_codes ci
            JOIN classes c ON c.id = ci.class_id
            WHERE ci.class_id=? AND ci.status='active'
            ORDER BY ci.id DESC
            LIMIT 1
            """,
            (class_id,),
        ).fetchone()
        if row:
            return dict(row)

        invite_code = secrets.token_hex(3).upper()
        conn.execute(
            """
            INSERT INTO class_invite_codes (
                organization_id, class_id, invite_code, status, created_by_user_id, created_at
            ) VALUES (?, ?, ?, 'active', ?, datetime('now','localtime'))
            """,
            (get_class(class_id)["organization_id"], class_id, invite_code, actor_user_id),
        )
        created = conn.execute(
            "SELECT * FROM class_invite_codes WHERE class_id=? ORDER BY id DESC LIMIT 1",
            (class_id,),
        ).fetchone()
    return dict(created)


def upsert_parent_wechat_account(
    *,
    openid: str,
    nickname_snapshot: str = "",
    avatar_url_snapshot: str = "",
) -> dict:
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT * FROM parent_wechat_accounts WHERE openid=?",
            (openid,),
        ).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE parent_wechat_accounts
                SET nickname_snapshot=?, avatar_url_snapshot=?, updated_at=datetime('now','localtime')
                WHERE id=?
                """,
                (nickname_snapshot, avatar_url_snapshot, existing["id"]),
            )
            row = conn.execute(
                "SELECT * FROM parent_wechat_accounts WHERE id=?",
                (existing["id"],),
            ).fetchone()
            return dict(row)

        conn.execute(
            """
            INSERT INTO parent_wechat_accounts (
                openid, nickname_snapshot, avatar_url_snapshot, status, created_at, updated_at
            ) VALUES (?, ?, ?, 'active', datetime('now','localtime'), datetime('now','localtime'))
            """,
            (openid, nickname_snapshot, avatar_url_snapshot),
        )
        row = conn.execute(
            "SELECT * FROM parent_wechat_accounts WHERE openid=?",
            (openid,),
        ).fetchone()
    return dict(row)


def bind_parent_to_student(*, parent_wechat_account_id: int, class_id: int, student_id: int) -> dict:
    teacher_user_id = get_class_teacher_user_id(class_id)
    if teacher_user_id is None:
        raise ValueError("class teacher is required")

    with get_conn() as conn:
        existing = conn.execute(
            """
            SELECT * FROM parent_student_bindings
            WHERE parent_wechat_account_id=? AND class_id=? AND student_id=? AND status='active'
            """,
            (parent_wechat_account_id, class_id, student_id),
        ).fetchone()
        if existing:
            return dict(existing)
        conn.execute(
            """
            INSERT INTO parent_student_bindings (
                organization_id, parent_wechat_account_id, class_id, student_id, teacher_user_id,
                status, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, 'active', datetime('now','localtime'), datetime('now','localtime'))
            """,
            (get_class(class_id)["organization_id"], parent_wechat_account_id, class_id, student_id, teacher_user_id),
        )
        row = conn.execute(
            "SELECT * FROM parent_student_bindings WHERE parent_wechat_account_id=? ORDER BY id DESC LIMIT 1",
            (parent_wechat_account_id,),
        ).fetchone()
    return dict(row)
```

- [ ] **Step 4: Re-run the data-layer tests**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary && /Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/.venv/bin/python -m unittest tests.test_wechat_parent_upload_data -v`

Expected: PASS for invite reuse/reset and canonical binding/submission tests.

- [ ] **Step 5: Commit the website persistence layer**

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary
git add lesson_manager.py tests/test_wechat_parent_upload_data.py
git commit -m "feat: add wechat parent upload persistence"
```

### Task 2: Add Website Service and Teacher APIs

**Files:**
- Modify: `/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/config_runtime.py`
- Modify: `/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/.env.runtime.example`
- Modify: `/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/app.py`
- Test: `/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/tests/test_wechat_parent_upload_api.py`

- [ ] **Step 1: Write the failing Flask API tests**

```python
class WeChatParentUploadApiTestCase(unittest.TestCase):
    def test_owner_can_view_and_reset_class_invite(self):
        owner = self.login_owner()
        create_class = self.client.post(
            "/api/classes",
            headers=self.auth_headers(owner["token"]),
            json={"name": "六年级 2 班", "subject": "数学", "grade": "六年级"},
        )
        class_id = create_class.get_json()["id"]
        self.client.put(
            f"/api/classes/{class_id}/teacher",
            headers=self.auth_headers(owner["token"]),
            json={"teacher_user_id": owner["user"]["id"]},
        )

        invite = self.client.get(
            f"/api/classes/{class_id}/invite",
            headers=self.auth_headers(owner["token"]),
        )
        reset = self.client.post(
            f"/api/classes/{class_id}/invite/reset",
            headers=self.auth_headers(owner["token"]),
        )

        self.assertEqual(invite.status_code, 200)
        self.assertEqual(reset.status_code, 200)
        self.assertNotEqual(invite.get_json()["invite_code"], reset.get_json()["invite_code"])

    def test_wechat_service_can_login_bind_and_upload(self):
        headers = {"X-Wechat-Service-Token": "wechat-service-token"}
        login = self.client.post(
            "/api/wechat/login",
            headers=headers,
            json={"open_id": "openid-1", "nickname_snapshot": "Alice 妈妈"},
        )
        self.assertEqual(login.status_code, 200)

        bind_preview = self.client.post(
            "/api/wechat/bind-class",
            headers=headers,
            json={"open_id": "openid-1", "invite_code": self.invite_code},
        )
        self.assertEqual(bind_preview.status_code, 200)
        self.assertEqual(bind_preview.get_json()["students"][0]["name"], "Alice")

        bind = self.client.post(
            "/api/wechat/bind-student",
            headers=headers,
            json={"open_id": "openid-1", "class_id": self.class_id, "student_id": self.student_id},
        )
        upload = self.client.post(
            "/api/wechat/wrong-questions",
            headers=headers,
            json={
                "open_id": "openid-1",
                "binding_id": bind.get_json()["binding"]["id"],
                "image_url": "https://files.example.com/record.png",
                "parent_note": "今天订正后还是错",
            },
        )

        self.assertEqual(upload.status_code, 201)
        self.assertEqual(upload.get_json()["record"]["source"], "wechat_mp")
        self.assertEqual(upload.get_json()["record"]["teacher_user_id"], self.owner_id)
```

- [ ] **Step 2: Run the Flask API tests to verify they fail**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary && /Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/.venv/bin/python -m unittest tests.test_wechat_parent_upload_api -v`

Expected: FAIL with `404` for missing class invite and `/api/wechat/*` routes.

- [ ] **Step 3: Add service-token config and new routes**

```python
# config_runtime.py
ENV_VAR_MAP.update({
    "wechat_service_token": "XR_WECHAT_SERVICE_TOKEN",
})
DEFAULTS.update({
    "wechat_service_token": "",
})


# app.py
def _require_wechat_service():
    expected = str(get_runtime_config().get("wechat_service_token", "")).strip()
    provided = request.headers.get("X-Wechat-Service-Token", "").strip()
    if not expected or provided != expected:
        return None, (jsonify({"error": "unauthorized"}), 401)
    return {"service": "wechat"}, None


@app.route("/api/classes/<int:class_id>/invite", methods=["GET"])
def api_class_invite_get(class_id):
    user, error = _require_owner()
    if error:
        return error
    cls, error = _get_accessible_class_or_error(user, class_id)
    if error:
        return error
    invite = get_or_create_active_class_invite(class_id=cls["id"], actor_user_id=user["id"])
    return jsonify(invite)


@app.route("/api/wechat/login", methods=["POST"])
def api_wechat_login():
    _, error = _require_wechat_service()
    if error:
        return error
    data, error = _get_json_object_payload()
    if error:
        return error
    account = upsert_parent_wechat_account(
        openid=(data.get("open_id") or "").strip(),
        nickname_snapshot=(data.get("nickname_snapshot") or "").strip(),
        avatar_url_snapshot=(data.get("avatar_url_snapshot") or "").strip(),
    )
    return jsonify({"account": account})
```

- [ ] **Step 4: Re-run the Flask API tests**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary && XR_WECHAT_SERVICE_TOKEN=wechat-service-token /Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/.venv/bin/python -m unittest tests.test_wechat_parent_upload_api -v`

Expected: PASS for owner invite management and service-authenticated bind/upload flow.

- [ ] **Step 5: Commit the website API layer**

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary
git add config_runtime.py .env.runtime.example app.py tests/test_wechat_parent_upload_api.py
git commit -m "feat: add wechat parent upload api"
```

### Task 3: Merge Local `wechat_mp` Records Into Website Wrong-Question APIs

**Files:**
- Modify: `/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/smart_wrong_questions.py`
- Modify: `/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/app.py`
- Modify: `/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/tests/test_smart_wrong_questions_api.py`

- [ ] **Step 1: Write the failing merged-record tests**

```python
    @patch("smart_wrong_questions.fetch_wrong_question_records")
    def test_local_wechat_records_are_merged_into_workspace_list(self, fetch_wrong_question_records):
        owner_payload = self.login_owner()
        owner_id = owner_payload["user"]["id"]
        class_id = lesson_manager.save_class("六年级 1 班", subject="数学", grade="六年级")
        lesson_manager.set_class_teacher_user_id(class_id, owner_id)
        student = lesson_manager.create_student_for_class(class_id, "Alice")
        account = lesson_manager.upsert_parent_wechat_account(openid="openid-1")
        binding = lesson_manager.bind_parent_to_student(
            parent_wechat_account_id=account["id"],
            class_id=class_id,
            student_id=student["id"],
        )
        lesson_manager.create_wechat_wrong_question_submission(
            binding_id=binding["id"],
            image_url="https://files.example.com/local.png",
            parent_note="本地记录",
        )
        fetch_wrong_question_records.return_value = {"items": [], "total": 0}

        response = self.client.get(
            "/api/wrong-questions",
            headers=self.auth_headers(owner_payload["token"]),
        )

        self.assertEqual(response.status_code, 200)
        item = response.get_json()["items"][0]
        self.assertEqual(item["source"], "wechat_mp")
        self.assertEqual(item["student_id"], student["id"])
        self.assertEqual(item["class_id"], class_id)

    def test_local_wechat_records_support_detail_and_review(self):
        owner_payload = self.login_owner()
        record = self.create_local_wechat_record(owner_payload["user"]["id"])

        detail = self.client.get(
            f"/api/wrong-questions/{record['id']}",
            headers=self.auth_headers(owner_payload["token"]),
        )
        review = self.client.put(
            f"/api/wrong-questions/{record['id']}/review",
            headers=self.auth_headers(owner_payload["token"]),
            json={"teacher_note": "下节课复讲", "status": "reviewed"},
        )

        self.assertEqual(detail.status_code, 200)
        self.assertEqual(review.status_code, 200)
        self.assertEqual(review.get_json()["record"]["status"], "reviewed")
```

- [ ] **Step 2: Run the wrong-question API tests to verify they fail**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary && /Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/.venv/bin/python -m unittest tests.test_smart_wrong_questions_api -v`

Expected: FAIL because local `wechat_mp` records are not yet listed, read, or reviewable.

- [ ] **Step 3: Implement list/detail/review branching for local submissions**

```python
# smart_wrong_questions.py
def merge_wrong_question_items(
    downstream_items: list[dict[str, Any]],
    local_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged = [*local_items, *downstream_items]
    return sorted(
        merged,
        key=lambda item: str(item.get("created_at") or ""),
        reverse=True,
    )


# app.py
@app.route("/api/wrong-questions", methods=["GET"])
def api_wrong_questions_list():
    user, error = _require_auth()
    if error:
        return error

    downstream_payload = smart_wrong_questions.fetch_wrong_question_records(request.args)
    local_items = lesson_manager.list_wechat_wrong_question_submissions_for_actor(user)
    payload = dict(downstream_payload)
    payload["items"] = smart_wrong_questions.merge_wrong_question_items(
        downstream_payload.get("items", []),
        local_items,
    )
    payload["total"] = len(payload["items"])
    scoped_items = _filter_wrong_question_items_for_user(user, payload["items"])
    payload["items"] = scoped_items
    return jsonify(payload)


@app.route("/api/wrong-questions/<record_id>", methods=["GET"])
def api_wrong_question_detail(record_id):
    user, error = _require_auth()
    if error:
        return error
    local_record = lesson_manager.get_wechat_wrong_question_submission(record_id)
    if local_record:
        if not _can_access_wrong_question_record(user, local_record):
            return jsonify({"error": "not found"}), 404
        return jsonify(local_record)
    record = smart_wrong_questions.fetch_wrong_question_record(record_id, request.args)
    if not _can_access_wrong_question_record(user, record):
        return jsonify({"error": "not found"}), 404
    return jsonify(record)
```

- [ ] **Step 4: Re-run the wrong-question API tests**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary && /Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/.venv/bin/python -m unittest tests.test_smart_wrong_questions_api -v`

Expected: PASS, including the new local-record list/detail/review coverage.

- [ ] **Step 5: Commit the merged workspace record support**

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary
git add app.py smart_wrong_questions.py tests/test_smart_wrong_questions_api.py
git commit -m "feat: merge wechat uploads into wrong question workspace"
```

### Task 4: Add Website Frontend Support For Class Invites and Source Badges

**Files:**
- Modify: `/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/frontend/src/App.tsx`
- Modify: `/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/frontend/src/smartWrongQuestions.ts`
- Modify: `/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/frontend/src/SmartWrongQuestionsPage.tsx`
- Create: `/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/frontend/src/class-management-invite.test.tsx`
- Modify: `/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/frontend/src/smart-wrong-questions.test.ts`

- [ ] **Step 1: Write the failing frontend tests**

```ts
import assert from 'node:assert/strict';
import test from 'node:test';
import fs from 'node:fs';

const appSource = fs.readFileSync(new URL('./App.tsx', import.meta.url), 'utf8');

test('class management fetches and resets class invite codes', () => {
  assert.match(appSource, /apiFetch\\(`\\/api\\/classes\\/\\$\\{item\\.id\\}\\/invite`\\)/);
  assert.match(appSource, /apiFetch\\(`\\/api\\/classes\\/\\$\\{item\\.id\\}\\/invite\\/reset`/);
  assert.match(appSource, /当前邀请码/);
});

test('smart wrong question page shows wechat mini-program source badge', () => {
  const source = fs.readFileSync(new URL('./SmartWrongQuestionsPage.tsx', import.meta.url), 'utf8');
  assert.match(source, /record\\.source === 'wechat_mp'/);
  assert.match(source, /微信小程序/);
});
```

- [ ] **Step 2: Run the frontend tests to verify they fail**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/frontend && npm test`

Expected: FAIL because invite fetch/reset UI and `wechat_mp` source badge strings are missing.

- [ ] **Step 3: Implement the minimal frontend affordances**

```tsx
// App.tsx inside ClassManagementPage
const [inviteByClassId, setInviteByClassId] = useState<Record<number, string>>({});

const handleLoadClassInvite = async (classId: number) => {
  const payload = await apiFetch<{ invite_code: string }>(`/api/classes/${classId}/invite`);
  setInviteByClassId((current) => ({ ...current, [classId]: payload.invite_code }));
};

const handleResetClassInvite = async (classId: number) => {
  const payload = await apiFetch<{ invite_code: string }>(`/api/classes/${classId}/invite/reset`, {
    method: 'POST',
  });
  setInviteByClassId((current) => ({ ...current, [classId]: payload.invite_code }));
};

// SmartWrongQuestionsPage.tsx
{selectedRecord?.source === 'wechat_mp' ? (
  <span className="inline-flex items-center rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700">
    微信小程序
  </span>
) : null}
```

- [ ] **Step 4: Re-run the frontend tests**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/frontend && npm test`

Expected: PASS for class invite UI and source badge coverage.

- [ ] **Step 5: Commit the website frontend changes**

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary
git add frontend/src/App.tsx frontend/src/smartWrongQuestions.ts frontend/src/SmartWrongQuestionsPage.tsx frontend/src/class-management-invite.test.tsx frontend/src/smart-wrong-questions.test.ts
git commit -m "feat: add class invite and wechat source ui"
```

### Task 5: Add Mini Backend Website Bridge Routes

**Files:**
- Create: `/Users/ark.mini/Desktop/Xingrun-MiniProgram/backend/src/website-client.ts`
- Modify: `/Users/ark.mini/Desktop/Xingrun-MiniProgram/backend/src/index.ts`
- Test: `/Users/ark.mini/Desktop/Xingrun-MiniProgram/backend/src/parent-wechat-bridge.test.ts`

- [ ] **Step 1: Write the failing mini backend bridge tests**

```ts
import assert from 'node:assert/strict';
import test from 'node:test';
import { once } from 'node:events';

import { createApp } from './index';

test('wechat parent login exchanges code and proxies to website', async (t) => {
  let websiteBody: Record<string, unknown> | null = null;
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (input, init) => {
    const url = String(input);
    if (url.includes('jscode2session')) {
      return new Response(JSON.stringify({ openid: 'openid-1' }), { status: 200 });
    }
    websiteBody = JSON.parse(String(init?.body || '{}'));
    return new Response(JSON.stringify({ account: { id: 1, openid: 'openid-1' } }), { status: 200 });
  };
  t.after(() => {
    globalThis.fetch = originalFetch;
  });

  const app = createApp();
  const server = app.listen(0);
  t.after(() => server.close());
  await once(server, 'listening');
  const address = server.address();
  assert.ok(address && typeof address === 'object');

  const response = await fetch(`http://127.0.0.1:${address.port}/wechat/parent-login`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ code: 'wx-code-1', nickname: 'Alice 妈妈' }),
  });

  assert.equal(response.status, 200);
  assert.equal(websiteBody?.open_id, 'openid-1');
});
```

- [ ] **Step 2: Run the mini backend tests to verify they fail**

Run: `cd /Users/ark.mini/Desktop/Xingrun-MiniProgram/backend && node --import tsx --test src/parent-wechat-bridge.test.ts`

Expected: FAIL because the new bridge routes and website client do not exist.

- [ ] **Step 3: Add the website client and bridge endpoints**

```ts
// website-client.ts
const WEBSITE_API_BASE_URL = process.env.WEBSITE_API_BASE_URL?.trim() || '';
const WEBSITE_API_TOKEN = process.env.WEBSITE_API_TOKEN?.trim() || '';

async function websiteRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${WEBSITE_API_BASE_URL}${path}`, {
    ...init,
    headers: {
      'content-type': 'application/json',
      'X-Wechat-Service-Token': WEBSITE_API_TOKEN,
      ...(init?.headers || {}),
    },
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json() as Promise<T>;
}

export async function loginParentWithCode(input: {
  code: string;
  nicknameSnapshot?: string;
  avatarUrlSnapshot?: string;
}) {
  const session = await exchangeCodeForOpenId(input.code);
  return websiteRequest('/api/wechat/login', {
    method: 'POST',
    body: JSON.stringify({
      open_id: session.openId,
      nickname_snapshot: input.nicknameSnapshot || '',
      avatar_url_snapshot: input.avatarUrlSnapshot || '',
    }),
  });
}

// index.ts
app.post('/wechat/parent-login', async (req, res) => {
  try {
    const payload = await loginParentWithCode({
      code: String(req.body?.code || ''),
      nicknameSnapshot: String(req.body?.nickname || ''),
      avatarUrlSnapshot: String(req.body?.avatarUrl || ''),
    });
    res.json(payload);
  } catch (error) {
    res.status(400).json({ error: error instanceof Error ? error.message : String(error) });
  }
});
```

- [ ] **Step 4: Re-run the mini backend tests**

Run: `cd /Users/ark.mini/Desktop/Xingrun-MiniProgram/backend && node --import tsx --test src/teacher-records.test.ts src/parent-wechat-bridge.test.ts`

Expected: PASS for both the existing teacher-record tests and the new parent bridge tests.

- [ ] **Step 5: Commit the mini backend bridge**

```bash
cd /Users/ark.mini/Desktop/Xingrun-MiniProgram
git add backend/src/website-client.ts backend/src/index.ts backend/src/parent-wechat-bridge.test.ts
git commit -m "feat: add website bridge for parent wechat flow"
```

### Task 6: Build The Lightweight WeChat Mini Program Parent Flow

**Files:**
- Modify: `/Users/ark.mini/Desktop/Xingrun-MiniProgram/miniprogram/app.json`
- Modify: `/Users/ark.mini/Desktop/Xingrun-MiniProgram/miniprogram/app.js`
- Modify: `/Users/ark.mini/Desktop/Xingrun-MiniProgram/miniprogram/pages/index/index.js`
- Create: `/Users/ark.mini/Desktop/Xingrun-MiniProgram/miniprogram/utils/parentApi.js`
- Create: `/Users/ark.mini/Desktop/Xingrun-MiniProgram/miniprogram/utils/parentApi.test.js`
- Create: `/Users/ark.mini/Desktop/Xingrun-MiniProgram/miniprogram/pages/parent-bind/index.js`
- Create: `/Users/ark.mini/Desktop/Xingrun-MiniProgram/miniprogram/pages/parent-bind/index.wxml`
- Create: `/Users/ark.mini/Desktop/Xingrun-MiniProgram/miniprogram/pages/parent-bind/index.wxss`
- Create: `/Users/ark.mini/Desktop/Xingrun-MiniProgram/miniprogram/pages/parent-home/index.js`
- Create: `/Users/ark.mini/Desktop/Xingrun-MiniProgram/miniprogram/pages/parent-home/index.wxml`
- Create: `/Users/ark.mini/Desktop/Xingrun-MiniProgram/miniprogram/pages/parent-home/index.wxss`
- Create: `/Users/ark.mini/Desktop/Xingrun-MiniProgram/miniprogram/pages/parent-upload/index.js`
- Create: `/Users/ark.mini/Desktop/Xingrun-MiniProgram/miniprogram/pages/parent-upload/index.wxml`
- Create: `/Users/ark.mini/Desktop/Xingrun-MiniProgram/miniprogram/pages/parent-upload/index.wxss`

- [ ] **Step 1: Write the failing miniprogram utility tests**

```js
const test = require('node:test');
const assert = require('node:assert/strict');

const {
  normalizeBindings,
  buildUploadRequest,
} = require('./parentApi');

test('normalizeBindings keeps binding_id and display labels', () => {
  const bindings = normalizeBindings([
    {
      binding_id: 7,
      class_id: 11,
      class_name: '六年级 1 班',
      student_id: 22,
      student_name: 'Alice',
      teacher_display_name: 'Kayn',
    },
  ]);

  assert.deepEqual(bindings[0], {
    id: 7,
    classId: 11,
    classLabel: '六年级 1 班',
    studentId: 22,
    studentLabel: 'Alice',
    teacherLabel: 'Kayn',
  });
});

test('buildUploadRequest sends binding id and optional parent note', () => {
  assert.deepEqual(
    buildUploadRequest({ bindingId: 7, imageUrl: 'https://files/x.png', parentNote: '请老师看' }),
    { binding_id: 7, image_url: 'https://files/x.png', parent_note: '请老师看' },
  );
});
```

- [ ] **Step 2: Run the miniprogram utility tests to verify they fail**

Run: `cd /Users/ark.mini/Desktop/Xingrun-MiniProgram/miniprogram && node utils/parentApi.test.js`

Expected: FAIL because `parentApi.js` does not exist yet.

- [ ] **Step 3: Implement the new parent pages and request helpers**

```js
// miniprogram/utils/parentApi.js
function normalizeBindings(items = []) {
  return items.map((item) => ({
    id: item.binding_id,
    classId: item.class_id,
    classLabel: item.class_name,
    studentId: item.student_id,
    studentLabel: item.student_name,
    teacherLabel: item.teacher_display_name,
  }));
}

function buildUploadRequest({ bindingId, imageUrl, parentNote }) {
  return {
    binding_id: bindingId,
    image_url: imageUrl,
    parent_note: parentNote || '',
  };
}

module.exports = {
  normalizeBindings,
  buildUploadRequest,
};

// miniprogram/pages/parent-home/index.js
Page({
  data: {
    bindings: [],
    selectedBindingId: null,
  },

  onShow() {
    const bindings = getApp().globalData.parentBindings || [];
    this.setData({
      bindings,
      selectedBindingId: bindings[0]?.id ?? null,
    });
  },

  goToUpload() {
    if (!this.data.selectedBindingId) return;
    wx.navigateTo({
      url: `/pages/parent-upload/index?bindingId=${this.data.selectedBindingId}`,
    });
  },
});
```

- [ ] **Step 4: Re-run the miniprogram utility tests**

Run: `cd /Users/ark.mini/Desktop/Xingrun-MiniProgram/miniprogram && node utils/parentApi.test.js`

Expected: PASS for binding normalization and upload request shaping.

- [ ] **Step 5: Manually verify the mini program flow in WeChat DevTools**

Run:

```text
1. Open /Users/ark.mini/Desktop/Xingrun-MiniProgram/miniprogram in WeChat DevTools
2. Launch the app and confirm pages/index redirects into the new parent flow
3. Enter a valid class invite code and choose a student
4. Confirm the home page lists the bound students
5. Upload one image and verify the success message appears
```

Expected: The UI completes bind -> home -> upload without using the old roster/chat flow.

- [ ] **Step 6: Commit the mini program UI**

```bash
cd /Users/ark.mini/Desktop/Xingrun-MiniProgram
git add miniprogram/app.json miniprogram/app.js miniprogram/pages/index/index.js miniprogram/utils/parentApi.js miniprogram/utils/parentApi.test.js miniprogram/pages/parent-bind miniprogram/pages/parent-home miniprogram/pages/parent-upload
git commit -m "feat: add lightweight parent upload miniprogram flow"
```

### Task 7: Run End-To-End Verification Across Both Repos

**Files:**
- Modify: `/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/README.md`
- Modify: `/Users/ark.mini/Desktop/Xingrun-MiniProgram/README.md`

- [ ] **Step 1: Add failing doc assertions as a checklist in the READMEs**

```md
## WeChat Parent Upload MVP

- Website owner can read/reset class invite codes
- Mini backend must set `WEBSITE_API_BASE_URL` and `WEBSITE_API_TOKEN`
- Website runtime must set `XR_WECHAT_SERVICE_TOKEN`
- Mini program bind flow uses website student rosters, not free-text names
```

- [ ] **Step 2: Run the full automated verification suites**

Run:

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary
/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/.venv/bin/python -m unittest tests.test_wechat_parent_upload_data tests.test_wechat_parent_upload_api tests.test_smart_wrong_questions_api -v
cd /Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/frontend
npm test
cd /Users/ark.mini/Desktop/Xingrun-MiniProgram/backend
node --import tsx --test src/teacher-records.test.ts src/parent-wechat-bridge.test.ts
cd /Users/ark.mini/Desktop/Xingrun-MiniProgram/miniprogram
node utils/parentApi.test.js
```

Expected: All suites PASS with no missing-route, missing-type, or unauthorized-token failures.

- [ ] **Step 3: Update the READMEs with the actual configuration and smoke-test commands**

```md
## Parent Upload Smoke Test

1. In the website repo set `XR_WECHAT_SERVICE_TOKEN=...`
2. In the mini backend set `WEBSITE_API_BASE_URL=http://<website-host>` and `WEBSITE_API_TOKEN=...`
3. Start the Flask app and the mini backend
4. In WeChat DevTools bind a student with a class invite code
5. Upload one image and verify it appears in website `智能错题`
```

- [ ] **Step 4: Re-run the targeted verification after docs update**

Run:

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary
/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/.venv/bin/python -m unittest tests.test_wechat_parent_upload_api -v
cd /Users/ark.mini/Desktop/Xingrun-MiniProgram/backend
node --import tsx --test src/parent-wechat-bridge.test.ts
```

Expected: PASS, confirming the documentation edits did not disturb the working code.

- [ ] **Step 5: Commit the final docs and verification notes in both repos**

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary
git add README.md
git commit -m "docs: document parent upload mvp rollout"

cd /Users/ark.mini/Desktop/Xingrun-MiniProgram
git add README.md
git commit -m "docs: document parent upload bridge setup"
```

---

## Self-Review

### Spec Coverage

- Website as source of truth: covered in Tasks 1-3 via canonical binding and local submission storage.
- Teacher class invite flow: covered in Tasks 2 and 4.
- Parent WeChat login, class binding, and multiple child binding: covered in Tasks 2, 5, and 6.
- Website `智能错题` workspace visibility for uploaded records: covered in Tasks 3 and 4.
- Separate website and mini-program repos with explicit commits: covered in every task’s commit step.

### Placeholder Scan

- No `TODO`, `TBD`, or “handle later” placeholders remain.
- Every task names exact files, tests, commands, and commit messages.
- Cross-repo commands are explicit so execution order is unambiguous.

### Type Consistency

- Canonical identity fields use one naming family throughout: `class_id`, `student_id`, `teacher_user_id`, `binding_id`, `source`.
- Website service auth uses one header name throughout: `X-Wechat-Service-Token`.
- Mini-program bridge consistently forwards `open_id` to website and `binding_id` for uploads.

