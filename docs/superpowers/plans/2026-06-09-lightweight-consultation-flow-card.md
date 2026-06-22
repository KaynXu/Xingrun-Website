# Lightweight Consultation Flow Card Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the consultation page visibly change into a lightweight teacher-facing flow card system with low-friction creation, clickable non-linear process nodes, class-entry handoff, and explicit success/failure closing.

**Architecture:** Extend the existing SQLite-backed consultation model rather than replacing it. Keep the main page in `frontend/src/App.tsx` for now because consultation UI already lives there, but add small pure helper functions and source tests before UI wiring. Add backend fields and a focused enter-class endpoint that reuses existing class/student helpers.

**Tech Stack:** Flask, SQLite data helpers in `lesson_manager.py`, React/Vite/TypeScript in `frontend/src/App.tsx`, Python unittest, Node `tsx --test` static/source tests.

---

## File Structure

- Modify `lesson_manager.py`: add consultation columns, serialize new fields, validate required create fields, persist stage notes and closing result.
- Modify `app.py`: add endpoint for consultation enter-class handoff, keep existing CRUD behavior compatible.
- Modify `frontend/src/App.tsx`: add lightweight create validation, card flow display, node action dialogs, Over dialog, enter-class panel.
- Modify `tests/test_consultation_flow.py`: backend regression tests for required fields, optional stage notes, closing result, and enter-class handoff.
- Modify `frontend/src/account-card.test.tsx`: source-level regression tests for visible card flow, required create fields, Over dialog, and enter-class actions.
- Modify `handoff.md`: record implementation proof and remaining risks after completion.

---

### Task 1: Consultation Data Model

**Files:**
- Modify: `lesson_manager.py`
- Test: `tests/test_consultation_flow.py`

- [ ] **Step 1: Write failing backend tests for new consultation fields**

Add tests near the existing consultation create/update tests:

```python
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
            "customer_service_note": "已加客服，家长发了校内成绩",
            "communication_teacher_note": "老师已初步沟通",
            "closing_result": "success",
        },
    )
    self.assertEqual(created.status_code, 201)
    payload = created.get_json()
    self.assertEqual(payload["customer_service_note"], "已加客服，家长发了校内成绩")
    self.assertEqual(payload["communication_teacher_note"], "老师已初步沟通")
    self.assertEqual(payload["closing_result"], "success")
```

- [ ] **Step 2: Run tests to confirm failure**

Run:

```bash
.venv/bin/python -m unittest tests.test_consultation_flow.ConsultationFlowTestCase.test_consultation_create_requires_lightweight_fields tests.test_consultation_flow.ConsultationFlowTestCase.test_consultation_stage_notes_and_closing_result_round_trip -v
```

Expected: FAIL because fields are not yet required/serialized.

- [ ] **Step 3: Implement schema and serialization**

In `_ensure_consultations_table`, add columns:

```python
_ensure_column(conn, "consultations", "customer_service_added", "TEXT DEFAULT ''")
_ensure_column(conn, "consultations", "customer_service_note", "TEXT DEFAULT ''")
_ensure_column(conn, "consultations", "communication_teacher_added", "TEXT DEFAULT ''")
_ensure_column(conn, "consultations", "communication_teacher_note", "TEXT DEFAULT ''")
_ensure_column(conn, "consultations", "test_note", "TEXT DEFAULT ''")
_ensure_column(conn, "consultations", "trial_teacher_added", "TEXT DEFAULT ''")
_ensure_column(conn, "consultations", "trial_teacher_note", "TEXT DEFAULT ''")
_ensure_column(conn, "consultations", "teaching_teacher_added", "TEXT DEFAULT ''")
_ensure_column(conn, "consultations", "teaching_teacher", "TEXT DEFAULT ''")
_ensure_column(conn, "consultations", "teaching_teacher_note", "TEXT DEFAULT ''")
_ensure_column(conn, "consultations", "enrollment_handoff_note", "TEXT DEFAULT ''")
_ensure_column(conn, "consultations", "student_profile_status", "TEXT DEFAULT ''")
_ensure_column(conn, "consultations", "student_profile_note", "TEXT DEFAULT ''")
_ensure_column(conn, "consultations", "failure_reason", "TEXT DEFAULT ''")
_ensure_column(conn, "consultations", "failure_note", "TEXT DEFAULT ''")
_ensure_column(conn, "consultations", "closing_result", "TEXT DEFAULT ''")
_ensure_column(conn, "consultations", "closed_by_user_id", "INTEGER")
```

Extend consultation row payloads and create/update field lists with the same names.

Validate create required fields in `create_consultation`:

```python
required = {
    "child_name": "学生姓名",
    "consultation_subject": "咨询科目",
    "grade": "咨询年级",
    "need_detail": "家长诉求",
    "receiving_teacher": "接待教师",
}
for key, label in required.items():
    if not str(data.get(key) or "").strip():
        raise ValueError(f"{label}不能为空")
```

- [ ] **Step 4: Run backend tests**

Run the same two-test command. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lesson_manager.py tests/test_consultation_flow.py
git commit -m "feat: add lightweight consultation fields"
```

---

### Task 2: Enter-Class Handoff Endpoint

**Files:**
- Modify: `app.py`
- Modify: `lesson_manager.py`
- Test: `tests/test_consultation_flow.py`

- [ ] **Step 1: Write failing tests for enter-class paths**

Add tests:

```python
def test_consultation_enter_existing_class_marks_success_and_student_profile(self):
    created = self.create_consultation_record(**{
        "学生姓名": "进班学生",
        "咨询科目": "数学",
        "年级": "七年级",
    })
    class_id = lesson_manager.create_class({
        "name": "数学七年级1班",
        "subject": "数学",
        "grade": "七年级",
        "class_type": "group",
    }, organization_id=self.organization_id)["id"]
    response = self.client.post(
        f"/api/consultations/{created['id']}/enter-class",
        headers=self.auth_headers(self.owner_token),
        json={"mode": "existing", "class_id": class_id},
    )
    self.assertEqual(response.status_code, 200)
    payload = response.get_json()
    self.assertEqual(payload["item"]["closing_result"], "success")
    self.assertEqual(payload["item"]["success_class_id"], class_id)
    self.assertEqual(payload["item"]["student_profile_status"], "created")

def test_consultation_enter_class_allows_converted_without_class(self):
    created = self.create_consultation_record(**{"学生姓名": "暂未定班学生"})
    response = self.client.post(
        f"/api/consultations/{created['id']}/enter-class",
        headers=self.auth_headers(self.owner_token),
        json={"mode": "converted_without_class"},
    )
    self.assertEqual(response.status_code, 200)
    payload = response.get_json()
    self.assertEqual(payload["item"]["closing_result"], "success")
    self.assertEqual(payload["item"]["success_class_id"], None)
    self.assertEqual(payload["item"]["student_profile_status"], "needs_completion")
```

- [ ] **Step 2: Run tests to confirm failure**

Run:

```bash
.venv/bin/python -m unittest tests.test_consultation_flow.ConsultationFlowTestCase.test_consultation_enter_existing_class_marks_success_and_student_profile tests.test_consultation_flow.ConsultationFlowTestCase.test_consultation_enter_class_allows_converted_without_class -v
```

Expected: FAIL with 404 for missing endpoint.

- [ ] **Step 3: Implement endpoint**

Add route:

```python
@app.route("/api/consultations/<int:consultation_id>/enter-class", methods=["POST"])
def api_consultation_enter_class(consultation_id):
    user, error = _require_auth()
    if error:
        return error
    payload = request.get_json(silent=True) or {}
    try:
        result = enter_consultation_class(
            consultation_id=consultation_id,
            payload=payload,
            organization_id=None if user.get("role") == "super_owner" else user.get("organization_id"),
            actor_user_id=user["id"],
            member_user_id=user["id"] if user.get("role") == "member" else None,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    if not result:
        return jsonify({"error": "not found"}), 404
    return jsonify(result)
```

Implement `enter_consultation_class` in `lesson_manager.py` by updating `success_class_id`, `closing_result='success'`, `ended_at`, `student_profile_status`, and by creating/adding a student when a class is selected.

- [ ] **Step 4: Run backend tests**

Run the same two-test command. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app.py lesson_manager.py tests/test_consultation_flow.py
git commit -m "feat: connect consultation conversion to classes"
```

---

### Task 3: Frontend Types And Source Tests

**Files:**
- Modify: `frontend/src/App.tsx`
- Test: `frontend/src/account-card.test.tsx`

- [ ] **Step 1: Write failing source tests**

Add assertions:

```ts
test('consultation records expose lightweight flow card fields', () => {
  assert.match(source, /customer_service_note: string;/);
  assert.match(source, /communication_teacher_note: string;/);
  assert.match(source, /teaching_teacher_note: string;/);
  assert.match(source, /failure_reason: string;/);
  assert.match(source, /closing_result: string;/);
});

test('consultation create form requires only lightweight fields', () => {
  const modalBlock = source.match(/const ConsultationModal = \([\s\S]*?\n};/);
  assert.ok(modalBlock);
  assert.match(modalBlock[0], /学生姓名/);
  assert.match(modalBlock[0], /咨询科目/);
  assert.match(modalBlock[0], /咨询年级/);
  assert.match(modalBlock[0], /家长诉求/);
  assert.match(modalBlock[0], /接待教师/);
  assert.doesNotMatch(modalBlock[0], /失败原因[\s\S]*required/);
});
```

- [ ] **Step 2: Run tests to confirm failure**

Run:

```bash
frontend/node_modules/.bin/tsx --test frontend/src/account-card.test.tsx
```

Expected: FAIL for missing fields/source strings.

- [ ] **Step 3: Extend frontend record model**

Add the new fields to `ConsultationRecord`, `toConsultationFormValues`, and `normalizeConsultationRecord` with empty-string defaults.

- [ ] **Step 4: Run test**

Run the same frontend command. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.tsx frontend/src/account-card.test.tsx
git commit -m "feat: expose consultation flow fields"
```

---

### Task 4: Consultation Card Flow UI

**Files:**
- Modify: `frontend/src/App.tsx`
- Test: `frontend/src/account-card.test.tsx`

- [ ] **Step 1: Write failing source tests**

Add:

```ts
test('consultation cards render clickable non-linear flow nodes', () => {
  assert.match(source, /const consultationFlowCardNodes = \[/);
  assert.match(source, /加客服/);
  assert.match(source, /加沟通教师/);
  assert.match(source, /教师沟通/);
  assert.match(source, /测试/);
  assert.match(source, /加试听教师/);
  assert.match(source, /试听/);
  assert.match(source, /加带课教师/);
  assert.match(source, /进班/);
  assert.match(source, /Over/);
  assert.match(source, /onClick=\{\(\) => openConsultationFlowNode\(record, node\.key\)\}/);
});
```

- [ ] **Step 2: Run test to confirm failure**

Run:

```bash
frontend/node_modules/.bin/tsx --test frontend/src/account-card.test.tsx
```

Expected: FAIL for missing flow node list.

- [ ] **Step 3: Implement compact card flow**

Add node config and `renderConsultationFlowCard(record)` that renders a compact row of icon/text buttons. Wire it into desktop, pad, and mobile card renderers below the title/meta row.

- [ ] **Step 4: Run frontend source tests**

Run same command. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.tsx frontend/src/account-card.test.tsx
git commit -m "feat: show consultation flow on cards"
```

---

### Task 5: Node Action Dialogs And Over Dialog

**Files:**
- Modify: `frontend/src/App.tsx`
- Test: `frontend/src/account-card.test.tsx`

- [ ] **Step 1: Write failing tests**

Add:

```ts
test('consultation flow nodes open matching action dialogs', () => {
  assert.match(source, /flowNodeActionRecord/);
  assert.match(source, /flowNodeActionKey/);
  assert.match(source, /选择沟通教师/);
  assert.match(source, /选择试听教师/);
  assert.match(source, /选择带课教师/);
  assert.match(source, /客服沟通情况/);
  assert.match(source, /测试情况/);
});

test('consultation over opens success failure dialog with emotional backgrounds', () => {
  assert.match(source, /overResultDialogRecord/);
  assert.match(source, /咨询成功/);
  assert.match(source, /咨询失败/);
  assert.match(source, /bg-emerald/);
  assert.match(source, /bg-rose|bg-orange/);
  assert.match(source, /closing_result/);
});
```

- [ ] **Step 2: Run test to confirm failure**

Run:

```bash
frontend/node_modules/.bin/tsx --test frontend/src/account-card.test.tsx
```

Expected: FAIL for missing dialogs.

- [ ] **Step 3: Implement dialogs**

Add state:

```ts
const [flowNodeActionRecord, setFlowNodeActionRecord] = useState<ConsultationRecord | null>(null);
const [flowNodeActionKey, setFlowNodeActionKey] = useState<ConsultationFlowCardNodeKey | null>(null);
const [overResultDialogRecord, setOverResultDialogRecord] = useState<ConsultationRecord | null>(null);
```

Implement `openConsultationFlowNode`; route `enter-class` to enter-class panel and `over` to Over dialog. Other nodes open a small modal with the matching note field and optional teacher dropdown, then save through existing `saveInlineConsultationUpdate`.

- [ ] **Step 4: Run frontend tests**

Run same command. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.tsx frontend/src/account-card.test.tsx
git commit -m "feat: add consultation flow actions"
```

---

### Task 6: Enter-Class Panel UI

**Files:**
- Modify: `frontend/src/App.tsx`
- Test: `frontend/src/account-card.test.tsx`

- [ ] **Step 1: Write failing tests**

Add:

```ts
test('consultation enter class panel supports existing class quick new class and no class yet', () => {
  assert.match(source, /enterClassRecord/);
  assert.match(source, /选择已有班级/);
  assert.match(source, /快速新建班级/);
  assert.match(source, /暂不选班/);
  assert.match(source, /\/api\/consultations\/\$\{enterClassRecord\.id\}\/enter-class/);
});
```

- [ ] **Step 2: Run test to confirm failure**

Run:

```bash
frontend/node_modules/.bin/tsx --test frontend/src/account-card.test.tsx
```

Expected: FAIL.

- [ ] **Step 3: Implement panel**

Add `enterClassRecord`, existing class select, quick new class fields, and converted-without-class action. POST to `/api/consultations/${id}/enter-class`, refresh the record from response, and close panel.

- [ ] **Step 4: Run frontend tests**

Run same command. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.tsx frontend/src/account-card.test.tsx
git commit -m "feat: add consultation enter class panel"
```

---

### Task 7: Local Preview And Final Verification

**Files:**
- Modify: `handoff.md`

- [ ] **Step 1: Run focused backend and frontend tests**

```bash
.venv/bin/python -m unittest tests.test_consultation_flow -v
frontend/node_modules/.bin/tsx --test frontend/src/account-card.test.tsx
```

Expected: all tests pass.

- [ ] **Step 2: Run whitespace check**

```bash
git diff --check
```

Expected: no output and exit 0.

- [ ] **Step 3: Preview locally**

Start services if needed:

```bash
.venv/bin/python app.py
npm --prefix frontend run dev
```

Open `http://localhost:3000/`, go to `咨询记录`, create a minimal consultation, confirm the card shows the flow row, click a teacher node, click `进班`, and click `Over`.

- [ ] **Step 4: Update handoff**

Append the implemented state, proof commands, preview result, and remaining risks.

- [ ] **Step 5: Commit final handoff if needed**

```bash
git add handoff.md
git commit -m "docs: record consultation flow preview proof"
```

---

## Self-Review

- Spec coverage: create required fields, optional stage notes, non-linear flow card, teacher selectors, enter-class paths, Over success/failure dialog, and analysis hooks are mapped to tasks.
- Placeholder scan: no unfinished placeholder markers are used.
- Type consistency: new frontend fields match backend field names, and the enter-class endpoint is consistently named `/api/consultations/<id>/enter-class`.
