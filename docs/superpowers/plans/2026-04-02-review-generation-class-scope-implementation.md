# Review Generation Class Scope Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make class selection mandatory when generating review records, and restrict `member` users so they can only create, list, view, download, and delete review records for classes they are responsible for, while `owner`/`admin`/`super_owner` retain full access.

**Architecture:** Reuse the existing `lessons.class_id -> user_classes` relationship as the single source of truth for lesson access. Add shared backend lesson-scope helpers in `app.py`, cover them with Flask tests in `tests/test_account_flow.py`, and tighten the review-generation UI in `frontend/src/App.tsx` with focused TSX tests that prove the new required-class behavior for members.

**Tech Stack:** Flask, SQLite, unittest, React 19, TypeScript, tsx test runner, Vite

---

## File Structure

- Modify: `app.py`
  - Add shared lesson access helpers.
  - Apply lesson-scope checks to list/detail/delete/PDF routes and lesson creation.
- Modify: `tests/test_account_flow.py`
  - Add backend access-control and required-class regression tests.
- Modify: `frontend/src/App.tsx`
  - Make class selection required in `LessonInput`.
  - Surface “no assigned classes” guidance for `member`.
- Modify: `frontend/src/workspace-navigation.test.ts`
  - Add focused source-level assertions for required class handling in `LessonInput`.
- Optional verify-only reads:
  - `lesson_manager.py`
  - `frontend/package.json`

### Task 1: Lock Backend Lesson Scope With Failing Tests

**Files:**
- Modify: `tests/test_account_flow.py`
- Verify context: `app.py`

- [ ] **Step 1: Write the failing backend tests**

Add these tests near the other auth and scope tests in `tests/test_account_flow.py`:

```python
    def test_member_lessons_list_only_returns_owned_class_records(self):
        owner_token, invite = self.create_approved_organization_with_invite(
            organization_name="Lesson Scope School",
            owner_username="lesson_scope_owner",
            owner_display_name="Lesson Scope Owner",
            owner_password="ownerpass123",
        )
        owner_me = self.client.get("/api/me", headers=self.auth_headers(owner_token)).get_json()
        owner_id = owner_me["id"]

        member_login = self.client.post(
            "/api/join-organization",
            json={
                "invite_code": invite["invite_code"],
                "username": "lesson_scope_member",
                "display_name": "Lesson Scope Member",
                "password": "memberpass123",
            },
        )
        self.assertEqual(member_login.status_code, 201)
        member_token = member_login.get_json()["token"]
        member_id = self.client.get("/api/me", headers=self.auth_headers(member_token)).get_json()["id"]

        owned_class_id = lesson_manager.save_class("六年级 1 班", subject="数学", grade="六年级")
        other_class_id = lesson_manager.save_class("六年级 2 班", subject="数学", grade="六年级")
        lesson_manager.set_class_teacher_user_id(owned_class_id, member_id)
        lesson_manager.set_class_teacher_user_id(other_class_id, owner_id)

        owned_lesson_id = lesson_manager.save_lesson(
            "2026-04-02",
            "数学",
            "六年级",
            "分数四则运算",
            "summary",
            "weak",
            {"questions": []},
            "",
            owned_class_id,
        )
        lesson_manager.save_lesson(
            "2026-04-02",
            "数学",
            "六年级",
            "分数应用题",
            "summary",
            "weak",
            {"questions": []},
            "",
            other_class_id,
        )
        lesson_manager.save_lesson(
            "2026-04-02",
            "数学",
            "六年级",
            "无班级旧记录",
            "summary",
            "weak",
            {"questions": []},
            "",
            0,
        )

        response = self.client.get("/api/review-plans", headers=self.auth_headers(member_token))

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual([item["id"] for item in payload], [owned_lesson_id])

    def test_member_cannot_access_unowned_lesson_detail_delete_or_pdf(self):
        owner_token, invite = self.create_approved_organization_with_invite(
            organization_name="Lesson Detail School",
            owner_username="lesson_detail_owner",
            owner_display_name="Lesson Detail Owner",
            owner_password="ownerpass123",
        )
        owner_id = self.client.get("/api/me", headers=self.auth_headers(owner_token)).get_json()["id"]

        member_login = self.client.post(
            "/api/join-organization",
            json={
                "invite_code": invite["invite_code"],
                "username": "lesson_detail_member",
                "display_name": "Lesson Detail Member",
                "password": "memberpass123",
            },
        )
        self.assertEqual(member_login.status_code, 201)
        member_token = member_login.get_json()["token"]
        member_id = self.client.get("/api/me", headers=self.auth_headers(member_token)).get_json()["id"]

        owned_class_id = lesson_manager.save_class("初一 1 班", subject="英语", grade="初一")
        other_class_id = lesson_manager.save_class("初一 2 班", subject="英语", grade="初一")
        lesson_manager.set_class_teacher_user_id(owned_class_id, member_id)
        lesson_manager.set_class_teacher_user_id(other_class_id, owner_id)

        pdf_path = self.base / "restricted.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\n%fake pdf\n")

        lesson_id = lesson_manager.save_lesson(
            "2026-04-02",
            "英语",
            "初一",
            "一般现在时",
            "summary",
            "weak",
            {"questions": []},
            str(pdf_path),
            other_class_id,
        )

        detail = self.client.get(f"/api/review-plans/{lesson_id}", headers=self.auth_headers(member_token))
        preview = self.client.get(f"/api/pdf/{lesson_id}", headers=self.auth_headers(member_token))
        download = self.client.get(f"/api/pdf/download/{lesson_id}", headers=self.auth_headers(member_token))
        delete = self.client.delete(f"/api/review-plans/{lesson_id}", headers=self.auth_headers(member_token))

        self.assertEqual(detail.status_code, 404)
        self.assertEqual(preview.status_code, 404)
        self.assertEqual(download.status_code, 404)
        self.assertEqual(delete.status_code, 404)

    def test_member_lesson_creation_requires_owned_class(self):
        owner_token, invite = self.create_approved_organization_with_invite(
            organization_name="Lesson Create School",
            owner_username="lesson_create_owner",
            owner_display_name="Lesson Create Owner",
            owner_password="ownerpass123",
        )
        owner_id = self.client.get("/api/me", headers=self.auth_headers(owner_token)).get_json()["id"]

        member_login = self.client.post(
            "/api/join-organization",
            json={
                "invite_code": invite["invite_code"],
                "username": "lesson_create_member",
                "display_name": "Lesson Create Member",
                "password": "memberpass123",
            },
        )
        self.assertEqual(member_login.status_code, 201)
        member_token = member_login.get_json()["token"]
        member_id = self.client.get("/api/me", headers=self.auth_headers(member_token)).get_json()["id"]

        owned_class_id = lesson_manager.save_class("高一 1 班", subject="物理", grade="高一")
        other_class_id = lesson_manager.save_class("高一 2 班", subject="物理", grade="高一")
        lesson_manager.set_class_teacher_user_id(owned_class_id, member_id)
        lesson_manager.set_class_teacher_user_id(other_class_id, owner_id)

        missing_class = self.client.post(
            "/api/review-plans",
            headers=self.auth_headers(member_token),
            json={
                "subject": "物理",
                "topic": "匀变速直线运动",
                "date": "2026-04-02",
                "weak_points": "速度图像",
                "summary_text": "课堂总结",
            },
        )
        forbidden_class = self.client.post(
            "/api/review-plans",
            headers=self.auth_headers(member_token),
            json={
                "subject": "物理",
                "class_id": other_class_id,
                "topic": "匀变速直线运动",
                "date": "2026-04-02",
                "weak_points": "速度图像",
                "summary_text": "课堂总结",
            },
        )

        self.assertEqual(missing_class.status_code, 400)
        self.assertEqual(forbidden_class.status_code, 403)

    def test_owner_and_admin_still_have_full_lesson_visibility(self):
        owner_token, invite = self.create_approved_organization_with_invite(
            organization_name="Lesson Staff School",
            owner_username="lesson_staff_owner",
            owner_display_name="Lesson Staff Owner",
            owner_password="ownerpass123",
        )
        owner_id = self.client.get("/api/me", headers=self.auth_headers(owner_token)).get_json()["id"]

        admin_login = self.client.post(
            "/api/join-organization",
            json={
                "invite_code": invite["invite_code"],
                "username": "lesson_staff_admin",
                "display_name": "Lesson Staff Admin",
                "password": "adminpass123",
            },
        )
        self.assertEqual(admin_login.status_code, 201)
        admin_token = admin_login.get_json()["token"]
        admin_id = self.client.get("/api/me", headers=self.auth_headers(admin_token)).get_json()["id"]
        self.client.put(
            f"/api/admin/users/{admin_id}/role",
            headers=self.auth_headers(owner_token),
            json={"role": "admin"},
        )

        class_a = lesson_manager.save_class("九年级 1 班", subject="化学", grade="九年级")
        class_b = lesson_manager.save_class("九年级 2 班", subject="化学", grade="九年级")
        lesson_manager.set_class_teacher_user_id(class_a, owner_id)
        lesson_manager.set_class_teacher_user_id(class_b, admin_id)

        lesson_manager.save_lesson("2026-04-02", "化学", "九年级", "酸碱盐", "summary", "weak", {"questions": []}, "", class_a)
        lesson_manager.save_lesson("2026-04-02", "化学", "九年级", "溶液", "summary", "weak", {"questions": []}, "", class_b)

        owner_payload = self.client.get("/api/review-plans", headers=self.auth_headers(owner_token)).get_json()
        admin_payload = self.client.get("/api/review-plans", headers=self.auth_headers(admin_token)).get_json()

        self.assertEqual(len(owner_payload), 2)
        self.assertEqual(len(admin_payload), 2)
```

- [ ] **Step 2: Run backend tests to verify they fail**

Run:

```bash
python -m unittest tests.test_account_flow.AccountFlowTestCase.test_member_lessons_list_only_returns_owned_class_records tests.test_account_flow.AccountFlowTestCase.test_member_cannot_access_unowned_lesson_detail_delete_or_pdf tests.test_account_flow.AccountFlowTestCase.test_member_lesson_creation_requires_owned_class tests.test_account_flow.AccountFlowTestCase.test_owner_and_admin_still_have_full_lesson_visibility -v
```

Expected: FAIL because `/api/review-plans` still returns all records, lesson create still accepts missing/unowned class IDs, and lesson detail/PDF/delete routes do not yet enforce lesson scope.

- [ ] **Step 3: Commit the red tests**

```bash
git add tests/test_account_flow.py
git commit -m "test: lock lesson class scope rules"
```

### Task 2: Implement Backend Lesson Scope And Creation Validation

**Files:**
- Modify: `app.py`
- Verify context: `lesson_manager.py`
- Test: `tests/test_account_flow.py`

- [ ] **Step 1: Add shared lesson-scope helpers in `app.py`**

Add helper logic near the existing wrong-question access helpers:

```python
def _can_access_lesson(user, lesson: object, owned_class_ids: Optional[Set[int]] = None) -> bool:
    if not isinstance(lesson, dict):
        return False
    if user.get("role") in {"super_owner", "owner", "admin"}:
        return True

    class_id = lesson.get("class_id")
    if not isinstance(class_id, int):
        return False

    member_class_ids = owned_class_ids
    if member_class_ids is None:
        member_class_ids = set(get_user_class_ids(user["id"]))
    return class_id in member_class_ids


def _filter_lessons_for_user(user, lessons: object) -> list[dict]:
    if not isinstance(lessons, list):
        return []
    if user.get("role") in {"super_owner", "owner", "admin"}:
        return [item for item in lessons if isinstance(item, dict)]

    owned_class_ids = set(get_user_class_ids(user["id"]))
    return [
        item
        for item in lessons
        if isinstance(item, dict) and _can_access_lesson(user, item, owned_class_ids)
    ]
```

- [ ] **Step 2: Apply lesson-scope checks to list/detail/delete/PDF routes**

Update the route bodies in `app.py` like this:

```python
@app.route("/api/review-plans", methods=["GET"])
def api_lessons_list():
    user, error = _require_auth()
    if error:
        return error
    month = request.args.get("month", "")
    class_id = request.args.get("class_id", 0, type=int)
    lessons = list_lessons(
        month_str=month if month else None,
        class_id=class_id if class_id else None,
    )
    return jsonify(_filter_lessons_for_user(user, lessons))


@app.route("/api/review-plans/<int:lesson_id>", methods=["GET"])
def api_lesson_get(lesson_id):
    user, error = _require_auth()
    if error:
        return error
    lesson = get_lesson(lesson_id)
    if not lesson or not _can_access_lesson(user, lesson):
        return jsonify({"error": "not found"}), 404
    questions = get_questions(lesson_id=lesson_id)
    return jsonify({**lesson, "questions": questions})


@app.route("/api/review-plans/<int:lesson_id>", methods=["DELETE"])
def api_lesson_delete(lesson_id):
    user, error = _require_auth()
    if error:
        return error
    lesson = get_lesson(lesson_id)
    if not lesson or not _can_access_lesson(user, lesson):
        return jsonify({"error": "not found"}), 404
    ...


@app.route("/api/pdf/<int:lesson_id>")
def api_pdf_view(lesson_id):
    user, error = _require_auth()
    if error:
        return error
    lesson = get_lesson(lesson_id)
    if not lesson or not _can_access_lesson(user, lesson):
        return jsonify({"error": "not found"}), 404
    ...


@app.route("/api/pdf/download/<int:lesson_id>")
def download_pdf(lesson_id):
    user, error = _require_auth()
    if error:
        return error
    lesson = get_lesson(lesson_id)
    if not lesson or not _can_access_lesson(user, lesson):
        return jsonify({"error": "not found"}), 404
    ...
```

- [ ] **Step 3: Make lesson creation require a valid, authorized class**

Update `api_lesson_create` in `app.py`:

```python
@app.route("/api/review-plans", methods=["POST"])
def api_lesson_create():
    user, error = _require_auth()
    if error:
        return error
    ...
    class_id = int(data.get("class_id") or 0)
    if not class_id:
        return jsonify({"error": "请选择班级后再生成复习记录"}), 400

    cls = get_class(class_id)
    if not cls:
        return jsonify({"error": "class not found"}), 404
    if not _can_access_lesson(user, {"class_id": class_id}):
        return jsonify({"error": "forbidden"}), 403

    subject = data.get("subject", "").strip() or (cls["subject"] if cls else "")
    grade = data.get("grade", "").strip() or (cls["grade"] if cls else "")
    ...
```

Keep the existing text/file branching logic unchanged after the new validation gate.

- [ ] **Step 4: Run backend tests to verify they pass**

Run:

```bash
python -m unittest tests.test_account_flow.AccountFlowTestCase.test_member_lessons_list_only_returns_owned_class_records tests.test_account_flow.AccountFlowTestCase.test_member_cannot_access_unowned_lesson_detail_delete_or_pdf tests.test_account_flow.AccountFlowTestCase.test_member_lesson_creation_requires_owned_class tests.test_account_flow.AccountFlowTestCase.test_owner_and_admin_still_have_full_lesson_visibility -v
```

Expected: PASS

- [ ] **Step 5: Commit backend implementation**

```bash
git add app.py tests/test_account_flow.py
git commit -m "feat: scope lesson access by class ownership"
```

### Task 3: Lock Frontend Required-Class Behavior With Failing Tests

**Files:**
- Modify: `frontend/src/workspace-navigation.test.ts`
- Verify context: `frontend/src/App.tsx`

- [ ] **Step 1: Write the failing frontend tests**

Add source assertions like these to `frontend/src/workspace-navigation.test.ts`:

```typescript
test('review generation source requires class selection before generation', () => {
  const lessonInputBlock = appSource.match(/const LessonInput = \(\{ onSuccess \}: \{ onSuccess: \(\) => void \}\) => \{[\s\S]*?\n};/);
  assert.ok(lessonInputBlock);
  assert.match(lessonInputBlock[0], /if \(!classId\) \{\s*setError\('请选择班级后再生成复习记录'\);\s*return;\s*\}/);
});

test('review generation source surfaces member no-class guidance', () => {
  const lessonInputBlock = appSource.match(/const LessonInput = \(\{ onSuccess \}: \{ onSuccess: \(\) => void \}\) => \{[\s\S]*?\n};/);
  assert.ok(lessonInputBlock);
  assert.match(lessonInputBlock[0], /const hasNoAssignableClasses = classes\.length === 0;/);
  assert.match(lessonInputBlock[0], /当前账号未分配负责班级/);
});
```

- [ ] **Step 2: Run frontend tests to verify they fail**

Run:

```bash
cd frontend && npm test -- --test-name-pattern "review generation source requires class selection before generation|review generation source surfaces member no-class guidance"
```

Expected: FAIL because `LessonInput` currently allows empty class submission and does not render the member no-class guidance.

- [ ] **Step 3: Commit the red tests**

```bash
git add frontend/src/workspace-navigation.test.ts
git commit -m "test: lock required class selection in review generation"
```

### Task 4: Implement Frontend Required-Class UX

**Files:**
- Modify: `frontend/src/App.tsx`
- Test: `frontend/src/workspace-navigation.test.ts`

- [ ] **Step 1: Add minimal required-class checks to `LessonInput`**

Update the component signature and validation in `frontend/src/App.tsx`:

```typescript
const LessonInput = ({ onSuccess, currentUser }: { onSuccess: () => void; currentUser: CurrentUser }) => {
  ...
  const hasNoAssignableClasses = classes.length === 0;

  const handleGenerate = async () => {
    setError('');
    if (!classId) {
      setError('请选择班级后再生成复习记录');
      return;
    }
    if (hasNoAssignableClasses) {
      setError('当前账号未分配负责班级，请先联系管理员分配班级');
      return;
    }
    ...
  };
```

- [ ] **Step 2: Render the no-class guidance and keep owner/admin flows unchanged**

Add a focused guidance block near the class selector:

```tsx
                <select
                  value={classId ?? ''}
                  onChange={(e) => handleClassChange(Number(e.target.value))}
                  className={`${workspaceFieldClass} w-full`}
                >
                  <option value="">选择班级</option>
                  {classes.map((c) => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </select>
                {currentUser.role === 'member' && hasNoAssignableClasses && (
                  <p className="text-sm text-amber-600 dark:text-amber-300">
                    当前账号未分配负责班级，请先联系管理员分配班级后再生成复习记录。
                  </p>
                )}
```

Keep the existing “class selects subject” behavior intact.

- [ ] **Step 3: Thread `currentUser` into `LessonInput`**

Update the caller in `ReviewGenerationPage`:

```tsx
const ReviewGenerationPage = ({ onSuccess, currentUser }: { onSuccess: () => void; currentUser: CurrentUser }) => {
  ...
  {composerOpen && (
    ...
    <LessonInput onSuccess={handleFormSuccess} currentUser={currentUser} />
  )}
}
```

And update the page render site:

```tsx
{activePage === 'review-generation' && <ReviewGenerationPage onSuccess={handleReviewGenerationSuccess} currentUser={currentUser} />}
```

- [ ] **Step 4: Run frontend tests to verify they pass**

Run:

```bash
cd frontend && npm test -- --test-name-pattern "review generation source requires class selection before generation|review generation source surfaces member no-class guidance"
```

Expected: PASS

- [ ] **Step 5: Commit frontend implementation**

```bash
git add frontend/src/App.tsx frontend/src/workspace-navigation.test.ts
git commit -m "feat: require class selection in review generation"
```

### Task 5: End-To-End Verification

**Files:**
- Verify: `app.py`
- Verify: `tests/test_account_flow.py`
- Verify: `frontend/src/App.tsx`
- Verify: `frontend/src/workspace-navigation.test.ts`

- [ ] **Step 1: Run the focused backend suite**

```bash
python -m unittest tests.test_account_flow -v
```

Expected: PASS

- [ ] **Step 2: Run the focused frontend suite**

```bash
cd frontend && npm test -- --test-name-pattern "review generation|class"
```

Expected: PASS

- [ ] **Step 3: Run frontend typecheck/build verification**

```bash
cd frontend && npm run lint && npm run build
```

Expected: PASS

- [ ] **Step 4: Review the plan against the approved spec**

Checklist:

```text
- Class selection required on create
- Member list scoped by owned classes
- Member detail/delete/PDF scoped by owned classes
- Owner/admin full visibility retained
- No new lesson teacher snapshot field introduced
```

- [ ] **Step 5: Final commit**

```bash
git add app.py tests/test_account_flow.py frontend/src/App.tsx frontend/src/workspace-navigation.test.ts
git commit -m "feat: scope review generation by responsible class"
```

## Self-Review

- **Spec coverage:** The plan covers required class selection, member-only class options, backend lesson list/detail/delete/PDF scope, create validation, retained owner/admin visibility, and the explicit non-goal of avoiding a redundant `teacher_user_id` snapshot on lessons.
- **Placeholder scan:** Each task names exact files, concrete tests, concrete route changes, and explicit verification commands; no `TODO`/`TBD` placeholders remain.
- **Type consistency:** The plan consistently uses `class_id`, `LessonInput`, `ReviewGenerationPage`, `_can_access_lesson`, and `_filter_lessons_for_user` across backend and frontend tasks.
