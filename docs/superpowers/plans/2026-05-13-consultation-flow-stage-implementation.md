# Consultation Flow Stage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add editable consultation flow stages with compact list lighting, full modal flow editing, automatic follow-up status, stage-specific fields, and multi-image test evidence.

**Architecture:** Extend the existing `consultations` SQLite table in place, keeping old `follow_up_status` compatible while returning a derived display status from the new flow stage. Reuse the existing consultation CRUD endpoints for most fields, add one focused image-upload endpoint, and keep AI batch parsing untouched. Do not upgrade AI batch parsing in this implementation.

**Tech Stack:** Flask, SQLite, unittest, Vite + React + TypeScript, Node source-level frontend tests.

---

## File Structure

- Modify `lesson_manager.py`: stage constants, schema columns, serialization, validation, legacy status mapping, actor-scoped update helper.
- Modify `app.py`: consultation update permission, test-image upload endpoint, class list reuse for dropdowns.
- Modify `tests/test_consultation_flow.py`: backend coverage for new fields, validation, permissions, legacy mapping, image upload.
- Modify `frontend/src/App.tsx`: `ConsultationRecord` fields, form defaults, stage helpers, compact list flow, modal full flow, class dropdown loading, image upload UI.
- Modify `frontend/src/account-card.test.tsx`: source-level assertions for the new consultation UI and unchanged AI batch behavior.
- Modify `handoff.md`: record completed implementation and next steps after verification.

Implementation should happen on a focused branch from current `develop`, because this is medium-sized and touches backend plus frontend.

---

### Task 1: Add Backend Stage Model And Legacy Mapping

**Files:**
- Modify: `lesson_manager.py`
- Test: `tests/test_consultation_flow.py`

- [ ] **Step 1: Write failing backend tests for stage fields, derived status, success validation, and legacy mapping**

Add these tests to `ConsultationFlowTestCase` in `tests/test_consultation_flow.py`:

```python
    def test_consultation_flow_stage_fields_round_trip_and_derive_follow_up_status(self):
        response = self.client.post(
            "/api/consultations",
            headers=self.auth_headers(self.owner_token),
            json={
                "parent_wechat_name": "赵妈妈",
                "child_name": "赵小星",
                "grade": "三年级",
                "consultation_subject": "数学",
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

    def test_success_stage_requires_existing_or_manual_class(self):
        missing_class = self.client.post(
            "/api/consultations",
            headers=self.auth_headers(self.owner_token),
            json={
                "parent_wechat_name": "钱妈妈",
                "child_name": "钱小满",
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

        response = self.client.get(f"/api/consultations/{legacy['id']}", headers=self.auth_headers(self.owner_token))

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["flow_stage"], "成功进班")
        self.assertEqual(payload["follow_up_status"], "完成")
        self.assertEqual(payload["completed_stages"], ["成功进班"])
        self.assertEqual(payload["test_images"], [])
```

- [ ] **Step 2: Run backend tests to verify they fail**

Run:

```bash
/usr/bin/python3 -m unittest \
  tests.test_consultation_flow.ConsultationFlowTestCase.test_consultation_flow_stage_fields_round_trip_and_derive_follow_up_status \
  tests.test_consultation_flow.ConsultationFlowTestCase.test_success_stage_requires_existing_or_manual_class \
  tests.test_consultation_flow.ConsultationFlowTestCase.test_legacy_follow_up_status_maps_to_new_flow_stage_without_lighting_unknown_steps
```

Expected: FAIL because `flow_stage`, `completed_stages`, and stage-specific fields are not implemented.

- [ ] **Step 3: Add constants, normalizers, and derived status helpers in `lesson_manager.py`**

Place these near the existing consultation constants:

```python
CONSULTATION_FLOW_STAGES = (
    "已加小客服微信",
    "已加对应教师微信",
    "正在沟通细节",
    "待测试",
    "待试听",
    "成功进班",
    "试听失败",
)
CONSULTATION_DEFAULT_FLOW_STAGE = "已加小客服微信"
CONSULTATION_FLOW_STAGE_DERIVED_STATUS = {
    "已加小客服微信": "待跟进",
    "已加对应教师微信": "待跟进",
    "正在沟通细节": "正在跟进",
    "待测试": "正在跟进",
    "待试听": "正在跟进",
    "试听失败": "正在跟进",
    "成功进班": "完成",
}
CONSULTATION_LEGACY_STATUS_STAGE_MAP = {
    "待邀约": "已加小客服微信",
    "跟进中": "正在沟通细节",
    "已报班": "成功进班",
}
CONSULTATION_LEGACY_ENDED_STATUSES = {"已劝退"}
CONSULTATION_STAGE_API_FIELDS = {
    "flow_stage",
    "completed_stages",
    "test_taken",
    "test_images",
    "trial_taken",
    "trial_time_slot",
    "trial_class_id",
    "trial_class_manual",
    "trial_teacher",
    "trial_feedback",
    "success_class_id",
    "success_class_manual",
    "end_note",
}
```

Add helpers near `_extract_consultation_updates`:

```python
def _json_list(value: object) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
        return parsed if isinstance(parsed, list) else []
    return []


def _normalize_consultation_flow_stage(value: object, legacy_status: str = "") -> str:
    stage = str(value or "").strip()
    if stage in CONSULTATION_FLOW_STAGES:
        return stage
    mapped = CONSULTATION_LEGACY_STATUS_STAGE_MAP.get((legacy_status or "").strip())
    return mapped or CONSULTATION_DEFAULT_FLOW_STAGE


def _normalize_consultation_completed_stages(value: object, current_stage: str) -> list[str]:
    seen = set()
    stages = []
    for raw_stage in _json_list(value):
        stage = str(raw_stage or "").strip()
        if stage in CONSULTATION_FLOW_STAGES and stage not in seen:
            seen.add(stage)
            stages.append(stage)
    if current_stage and current_stage not in seen:
        stages.append(current_stage)
    return stages


def _derive_consultation_follow_up_status(flow_stage: str) -> str:
    return CONSULTATION_FLOW_STAGE_DERIVED_STATUS.get(flow_stage, "待跟进")


def _normalize_optional_int(value: object) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
```

- [ ] **Step 4: Extend the consultations table in `_ensure_consultations_table`**

After the `CREATE TABLE IF NOT EXISTS consultations` statement, add `_ensure_column` calls:

```python
    _ensure_column(conn, "consultations", "flow_stage", "TEXT DEFAULT ''")
    _ensure_column(conn, "consultations", "completed_stages_json", "TEXT DEFAULT '[]'")
    _ensure_column(conn, "consultations", "test_taken", "TEXT DEFAULT ''")
    _ensure_column(conn, "consultations", "test_images_json", "TEXT DEFAULT '[]'")
    _ensure_column(conn, "consultations", "trial_taken", "TEXT DEFAULT ''")
    _ensure_column(conn, "consultations", "trial_time_slot", "TEXT DEFAULT ''")
    _ensure_column(conn, "consultations", "trial_class_id", "INTEGER")
    _ensure_column(conn, "consultations", "trial_class_manual", "TEXT DEFAULT ''")
    _ensure_column(conn, "consultations", "trial_teacher", "TEXT DEFAULT ''")
    _ensure_column(conn, "consultations", "trial_feedback", "TEXT DEFAULT ''")
    _ensure_column(conn, "consultations", "success_class_id", "INTEGER")
    _ensure_column(conn, "consultations", "success_class_manual", "TEXT DEFAULT ''")
    _ensure_column(conn, "consultations", "end_note", "TEXT DEFAULT ''")
```

- [ ] **Step 5: Store and serialize the new fields**

Update `_consultation_row_to_storage`, `create_consultation`, `update_consultation`, and `_consultation_storage_row_to_public_dict` so records include the new fields. Use `json.dumps(..., ensure_ascii=False)` for list columns.

The public payload must include:

```python
serialized["flow_stage"] = flow_stage
serialized["completed_stages"] = completed_stages
serialized["follow_up_status"] = _derive_consultation_follow_up_status(flow_stage)
serialized["test_taken"] = payload.get("test_taken", "") or ""
serialized["test_images"] = _json_list(payload.get("test_images_json", "[]"))
serialized["trial_taken"] = payload.get("trial_taken", "") or ""
serialized["trial_time_slot"] = payload.get("trial_time_slot", "") or ""
serialized["trial_class_id"] = payload.get("trial_class_id")
serialized["trial_class_manual"] = payload.get("trial_class_manual", "") or ""
serialized["trial_teacher"] = payload.get("trial_teacher", "") or ""
serialized["trial_feedback"] = payload.get("trial_feedback", "") or ""
serialized["success_class_id"] = payload.get("success_class_id")
serialized["success_class_manual"] = payload.get("success_class_manual", "") or ""
serialized["end_note"] = payload.get("end_note", "") or ""
```

When no stored `flow_stage` exists, map from legacy `follow_up_status` and set `completed_stages` to `[flow_stage]`.

Before inserting or updating, if `flow_stage == "成功进班"` and both `success_class_id` and `success_class_manual` are empty, raise `ValueError("成功进班必须选择或填写班级")`.

- [ ] **Step 6: Return API 400 for validation errors**

In `app.py`, wrap `create_consultation` and `update_consultation` calls:

```python
    try:
        item = create_consultation(...)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
```

and the same pattern for update.

- [ ] **Step 7: Run backend tests**

Run:

```bash
/usr/bin/python3 -m unittest tests.test_consultation_flow
```

Expected: PASS.

- [ ] **Step 8: Commit backend model**

Run:

```bash
git add lesson_manager.py app.py tests/test_consultation_flow.py
git commit -m "feat: add consultation flow stage model"
```

---

### Task 2: Allow Assigned Teachers To Edit Their Own Consultations

**Files:**
- Modify: `lesson_manager.py`
- Modify: `app.py`
- Test: `tests/test_consultation_flow.py`

- [ ] **Step 1: Write failing permission tests**

Replace the old assertion in `test_members_can_view_and_create_but_not_edit_or_delete` that expects member update `403`, or add a new focused test:

```python
    def test_member_can_update_assigned_consultation_but_not_unassigned_or_other_teacher_record(self):
        member_token = self.create_member_token(username="teacher_a", display_name="Teacher A")
        other_token = self.create_member_token(username="teacher_b", display_name="Teacher B")
        member_user = self.user_for_token(member_token)
        other_user = self.user_for_token(other_token)
        assigned = self.create_consultation_record(assigned_user_id=member_user["id"])
        other_assigned = self.create_consultation_record(assigned_user_id=other_user["id"], **{"孩子姓名": "另一个学生"})

        update_assigned = self.client.put(
            f"/api/consultations/{assigned['id']}",
            headers=self.auth_headers(member_token),
            json={
                "flow_stage": "正在沟通细节",
                "completed_stages": ["已加小客服微信", "正在沟通细节"],
                "follow_up_note": "老师已联系家长",
            },
        )
        self.assertEqual(update_assigned.status_code, 200)
        self.assertEqual(update_assigned.get_json()["follow_up_status"], "正在跟进")

        update_other = self.client.put(
            f"/api/consultations/{other_assigned['id']}",
            headers=self.auth_headers(member_token),
            json={"flow_stage": "正在沟通细节"},
        )
        self.assertEqual(update_other.status_code, 404)
```

- [ ] **Step 2: Run the focused permission test to verify it fails**

Run:

```bash
/usr/bin/python3 -m unittest tests.test_consultation_flow.ConsultationFlowTestCase.test_member_can_update_assigned_consultation_but_not_unassigned_or_other_teacher_record
```

Expected: FAIL because `PUT /api/consultations/<id>` currently requires staff.

- [ ] **Step 3: Add actor-scoped update permission**

In `app.py`, change `api_consultation_update` from `_require_staff()` to `_require_auth()`. Compute scope:

```python
    organization_id = None if user.get("role") == "super_owner" else user.get("organization_id")
    assigned_user_id = user["id"] if user.get("role") == "member" else None
```

Update `lesson_manager.update_consultation` signature to accept `assigned_user_id: Optional[int] = None` and add `AND assigned_user_id=?` to the lookup query when provided.

Do not loosen delete permissions; delete should still require staff.

- [ ] **Step 4: Run consultation tests**

Run:

```bash
/usr/bin/python3 -m unittest tests.test_consultation_flow
```

Expected: PASS.

- [ ] **Step 5: Commit permission change**

Run:

```bash
git add app.py lesson_manager.py tests/test_consultation_flow.py
git commit -m "feat: let assigned teachers update consultations"
```

---

### Task 3: Add Consultation Test Image Upload

**Files:**
- Modify: `app.py`
- Modify: `lesson_manager.py`
- Test: `tests/test_consultation_flow.py`

- [ ] **Step 1: Write failing image upload test**

Add to `ConsultationFlowTestCase.setUp`:

```python
        import app as app_module
        self.original_upload_dir = app_module.UPLOAD_DIR
        app_module.UPLOAD_DIR = self.base / "uploads"
        app_module.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        self.app_module = app_module
```

Add to `tearDown` before cleanup:

```python
        self.app_module.UPLOAD_DIR = self.original_upload_dir
```

Add test:

```python
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
```

Also add `import io` at the top of the test file.

- [ ] **Step 2: Run the image upload test to verify it fails**

Run:

```bash
/usr/bin/python3 -m unittest tests.test_consultation_flow.ConsultationFlowTestCase.test_owner_uploads_multiple_consultation_test_images
```

Expected: FAIL because the upload endpoint is missing.

- [ ] **Step 3: Add image append helper**

In `lesson_manager.py`, add:

```python
def append_consultation_test_image(consultation_id: int, image: dict, organization_id: Optional[int] = None, assigned_user_id: Optional[int] = None) -> Optional[dict]:
    with get_conn() as conn:
        query = "SELECT * FROM consultations WHERE id=?"
        params: list[object] = [consultation_id]
        if organization_id is not None:
            query += " AND organization_id=?"
            params.append(organization_id)
        if assigned_user_id is not None:
            query += " AND assigned_user_id=?"
            params.append(assigned_user_id)
        row = conn.execute(query, params).fetchone()
        if not row:
            return None
        images = _json_list(row["test_images_json"])
        images.append(image)
        conn.execute(
            "UPDATE consultations SET test_images_json=?, updated_at=datetime('now','localtime') WHERE id=?",
            (json.dumps(images, ensure_ascii=False), consultation_id),
        )
    return get_consultation(consultation_id, organization_id)
```

- [ ] **Step 4: Add upload and read endpoints**

In `app.py`, import `secure_filename` from `werkzeug.utils`. Add:

```python
@app.route("/api/consultations/<int:consultation_id>/test-images", methods=["POST"])
def api_consultation_test_image_upload(consultation_id):
    user, error = _require_auth()
    if error:
        return error
    image = request.files.get("image")
    if image is None or not image.filename:
        return jsonify({"error": "image is required"}), 400
    suffix = Path(image.filename).suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
        return jsonify({"error": "只支持 png、jpg、jpeg、webp 图片"}), 400
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"consultation-test-{consultation_id}-{int(time.time() * 1000)}-{secure_filename(image.filename)}"
    path = UPLOAD_DIR / filename
    image.save(path)
    image_payload = {"url": f"/api/consultation-test-images/{filename}", "filename": image.filename}
    item = append_consultation_test_image(
        consultation_id,
        image_payload,
        None if user.get("role") == "super_owner" else user.get("organization_id"),
        user["id"] if user.get("role") == "member" else None,
    )
    if not item:
        path.unlink(missing_ok=True)
        return jsonify({"error": "not found"}), 404
    return jsonify({"image": image_payload, "item": item}), 201


@app.route("/api/consultation-test-images/<path:filename>", methods=["GET"])
def api_consultation_test_image_file(filename):
    return send_from_directory(UPLOAD_DIR, filename)
```

Add `append_consultation_test_image` to the `lesson_manager` imports.

- [ ] **Step 5: Run image and consultation tests**

Run:

```bash
/usr/bin/python3 -m unittest tests.test_consultation_flow
```

Expected: PASS.

- [ ] **Step 6: Commit upload endpoint**

Run:

```bash
git add app.py lesson_manager.py tests/test_consultation_flow.py
git commit -m "feat: upload consultation test images"
```

---

### Task 4: Add Frontend Flow Stage UI

**Files:**
- Modify: `frontend/src/App.tsx`
- Test: `frontend/src/account-card.test.tsx`

- [ ] **Step 1: Write failing source-level frontend tests**

Add tests to `frontend/src/account-card.test.tsx`:

```ts
test('consultation source renders compact and full flow stage bars', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  assert.match(source, /consultationFlowStages/);
  assert.match(source, /ConsultationFlowBar/);
  assert.match(source, /compact/);
  assert.match(source, /full/);
  assert.match(source, /title=\{item\}/);
  assert.match(source, /已加小客服微信/);
  assert.doesNotMatch(source, /'咨询结束'\]/);
  assert.match(source, /成功进班/);
  assert.match(source, /试听失败/);
});

test('consultation modal source includes stage-specific test and trial fields', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const modalBlock = source.match(/const ConsultationModal = \([\s\S]*?\n};/);
  assert.ok(modalBlock);
  assert.match(modalBlock[0], /是否测试/);
  assert.match(modalBlock[0], /测试情况图片/);
  assert.match(modalBlock[0], /是否试听/);
  assert.match(modalBlock[0], /试听时间段/);
  assert.match(modalBlock[0], /若没找到对应班级，可以直接手动输入/);
  assert.match(modalBlock[0], /试听教师/);
  assert.match(modalBlock[0], /试听反馈/);
  assert.match(modalBlock[0], /成功进班必须选择或填写班级/);
});

test('consultation source keeps ai batch parse endpoint unchanged', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const batchModalBlock = source.match(/const ConsultationBatchModal = \([\s\S]*?\n};/);
  assert.ok(batchModalBlock);
  assert.match(batchModalBlock[0], /apiFetch<ConsultationBatchParseResponse>\('\/api\/consultations\/ai-parse'/);
  assert.doesNotMatch(batchModalBlock[0], /flow_stage/);
});
```

- [ ] **Step 2: Run source tests to verify they fail**

Run:

```bash
npm --prefix frontend test -- account-card.test.tsx
```

Expected: FAIL because the flow bar and fields do not exist.

- [ ] **Step 3: Extend TypeScript types and defaults**

In `frontend/src/App.tsx`, extend `ConsultationRecord`:

```ts
  flow_stage: string;
  completed_stages: string[];
  test_taken: string;
  test_images: Array<{ url: string; filename: string }>;
  trial_taken: string;
  trial_time_slot: string;
  trial_class_id: number | null;
  trial_class_manual: string;
  trial_teacher: string;
  trial_feedback: string;
  success_class_id: number | null;
  success_class_manual: string;
  end_note: string;
```

Add matching defaults in `consultationFormDefaults`, normalize in `normalizeConsultationRecord`, and preserve in `toConsultationFormValues`.

- [ ] **Step 4: Add stage constants and click behavior**

Near `consultationStatusOptions`, add:

```ts
const consultationFlowStages = ['已加小客服微信', '已加对应教师微信', '正在沟通细节', '待测试', '待试听', '成功进班'];
const consultationResultOptions = ['成功进班', '试听失败'];

function deriveConsultationDisplayStatus(stage: string, ended = false): string {
  if (ended || stage === '成功进班') return '完成';
  if (stage === '已加小客服微信' || stage === '已加对应教师微信') return '待跟进';
  return '正在跟进';
}

function toggleConsultationStage(form: ConsultationFormValues, stage: string): ConsultationFormValues {
  const currentStages = Array.isArray(form.completed_stages) ? form.completed_stages : [];
  const exists = currentStages.includes(stage);
  if (form.flow_stage === stage) return form;
  const nextStages = exists ? currentStages : [...currentStages, stage];
  return { ...form, flow_stage: stage, completed_stages: nextStages };
}
```

Export `toggleConsultationStage` if a direct unit test is added later.

- [ ] **Step 5: Add `ConsultationFlowBar` component**

Create a local component in `App.tsx` above `ConsultationModal`:

```tsx
const ConsultationFlowBar = ({
  stage,
  completedStages,
  mode = 'compact',
  editable = false,
  onStageClick,
}: {
  stage: string;
  completedStages: string[];
  mode?: 'compact' | 'full';
  editable?: boolean;
  onStageClick?: (stage: string) => void;
}) => {
  const currentStage = stage || consultationFlowStages[0];
  const completedSet = new Set(completedStages || []);
  completedSet.add(currentStage);
  return (
    <div className={mode === 'compact' ? 'flex min-w-[280px] items-center gap-2' : 'flex flex-wrap items-center gap-3'}>
      {consultationFlowStages.map((item) => {
        const isCurrent = item === currentStage;
        const isCompleted = completedSet.has(item);
        const className = isCurrent
          ? 'bg-sky-500 shadow-[0_0_0_3px_rgba(14,165,233,0.20),0_8px_24px_rgba(14,165,233,0.28)] scale-[1.04]'
          : isCompleted
            ? 'bg-emerald-500 shadow-[0_0_0_1px_rgba(16,185,129,0.20)] dark:bg-emerald-400'
            : 'bg-slate-300 dark:bg-white/10';
        return (
          <React.Fragment key={item}>
            <button
              key={item}
              type="button"
              title={item}
              disabled={!editable}
              onClick={() => onStageClick?.(item)}
              className={`h-3.5 w-3.5 shrink-0 rounded-full transition ${mode === 'full' ? 'h-4 w-4' : ''} ${className}`}
            />
            {item !== consultationFlowStages[consultationFlowStages.length - 1] && (
              <span className={`h-[2px] min-w-3 flex-1 rounded-full ${isCompleted ? 'bg-emerald-300 dark:bg-emerald-500/60' : 'bg-slate-200 dark:bg-white/10'}`} />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
};
```

- [ ] **Step 6: Load classes for consultation modal dropdowns**

In `ConsultationPage`, add `classes` state and load it alongside `consultationTeachers`:

```ts
const [classes, setClasses] = useState<ClassItem[]>([]);

useEffect(() => {
  let active = true;
  apiFetch<ClassItem[]>('/api/classes')
    .then((items) => active && setClasses(items))
    .catch(() => active && setClasses([]));
  return () => { active = false; };
}, []);
```

Pass `classes={classes}` into `ConsultationModal`.

- [ ] **Step 7: Render full flow and stage fields in modal**

Add `classes` and `onImageUploaded` props to `ConsultationModal`. At the top of the form, render:

```tsx
<section className={`${workspaceSoftCardClass} mb-5 space-y-4 p-4 sm:p-5`}>
  <div className="flex items-center justify-between gap-3">
    <div>
      <h4 className="font-semibold text-slate-900 dark:text-white">咨询流程</h4>
      <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">点击阶段框更新当前流程；未经历阶段保持灰色。</p>
    </div>
    <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600 dark:bg-white/10 dark:text-slate-200">
      {deriveConsultationDisplayStatus(form.flow_stage)}
    </span>
  </div>
  <ConsultationFlowBar
    mode="full"
    stage={form.flow_stage}
    completedStages={form.completed_stages}
    editable={!readOnly}
    onStageClick={(stage) => setForm((current) => toggleConsultationStage(current, stage))}
  />
</section>
```

Below existing detail textareas, render fields for `待测试`, `待试听`, and the `成功进班` result capsule. The flow bar itself should use dots with `title={item}` hover names in both compact and full modes. The `成功进班` capsule contains the result dropdown (`成功进班` / `试听失败`) and the class dropdown/manual class controls; do not render a separate `咨询结束` flow capsule. Keep saved end note/status fields available in the edit area when a consultation has been ended, but not as a stage in the flow bar.

For success validation in `handleSubmit`, before `await onSubmit(form)`:

```ts
if (form.flow_stage === '成功进班' && !form.success_class_id && !form.success_class_manual.trim()) {
  setParseFeedback('成功进班必须选择或填写班级。');
  return;
}
```

- [ ] **Step 8: Render compact flow in list**

In mobile cards and desktop table, replace the old status-only badge with:

```tsx
<ConsultationFlowBar
  mode="compact"
  stage={record.flow_stage}
  completedStages={record.completed_stages}
/>
<span className={`inline-flex shrink-0 items-center justify-center whitespace-nowrap rounded-full px-3 py-1 text-[11px] font-semibold ${consultationStatusClass(deriveConsultationDisplayStatus(record.flow_stage))}`}>
  {deriveConsultationDisplayStatus(record.flow_stage)}
</span>
```

For the desktop table, change the header from `跟进状态` to `咨询流程` and give that column enough width for the compact flow bar.

- [ ] **Step 9: Wire image upload**

In the `待测试` field area, add:

```tsx
<input
  type="file"
  accept="image/png,image/jpeg,image/webp"
  disabled={readOnly || !record}
  onChange={async (event) => {
    const file = event.target.files?.[0];
    if (!file || !record) return;
    const payload = new FormData();
    payload.append('image', file);
    const uploaded = await apiFetch<{ item: ConsultationRecord }>(`/api/consultations/${record.id}/test-images`, {
      method: 'POST',
      body: payload,
    });
    setForm(toConsultationFormValues(uploaded.item));
  }}
  className={workspaceFieldClass}
/>
```

Render `form.test_images.map((image) => <a href={image.url} target="_blank" rel="noreferrer">查看图片</a>)`.

- [ ] **Step 10: Run frontend tests**

Run:

```bash
npm --prefix frontend test -- account-card.test.tsx
```

Expected: PASS.

- [ ] **Step 11: Commit frontend UI**

Run:

```bash
git add frontend/src/App.tsx frontend/src/account-card.test.tsx
git commit -m "feat: show consultation flow stages"
```

---

### Task 5: Final Verification, Handoff, And Integration

**Files:**
- Modify: `handoff.md`

- [ ] **Step 1: Run full focused proof script**

Create and run `/tmp/xingrun_consultation_flow_stage_impl_proof.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "/Users/macosduan/VS code program/xingrun.online/Xingrun-Website"
/usr/bin/python3 -m unittest tests.test_consultation_flow
npm --prefix frontend test -- account-card.test.tsx
npm --prefix frontend run build
git diff --check
echo "consultation flow stage implementation proof passed"
```

Expected: all commands pass and the final line prints.

- [ ] **Step 2: Update `handoff.md`**

Add one current-status bullet:

```markdown
- 2026-05-13 已完成咨询流程阶段第一版实现：后端新增流程阶段、已经历阶段、测试图片、试听字段、成功进班班级校验和历史状态映射；普通老师可编辑分配给自己的咨询；前端列表显示超紧凑短标签流程条，详情/编辑窗口顶部显示完整流程图；待测试支持多图上传查看，待试听和成功进班支持系统班级下拉与手动输入；AI 批量整理未改。latest proof 已通过临时脚本 `/tmp/xingrun_consultation_flow_stage_impl_proof.sh`。
```

Add one next-step bullet:

```markdown
- 最值得继续做的是用真实老师账号打开咨询记录页，手工编辑一条分配给自己的咨询：点亮阶段、上传两张测试图片、选择一个试听班级、再改为成功进班，确认列表和详情的亮灯效果符合预期。
```

- [ ] **Step 3: Commit handoff**

Run:

```bash
git add handoff.md
git commit -m "docs: update consultation flow stage handoff"
```

- [ ] **Step 4: Report proof output**

Final response must lead with whether implementation passed proof, include the full proof output, mention the commits created, and note that `data/xingrun.db` remains untracked and intentionally uncommitted.

---

## Self-Review

Spec coverage:

- Flow stages, clicked lighting, skipped stages, terminal states: Task 1 and Task 4.
- Automatic follow-up status: Task 1 and Task 4.
- List compact bar and modal full flow: Task 4.
- Assigned teacher edit permission: Task 2.
- Test image multi-upload: Task 3 and Task 4.
- Trial fields and class dropdown plus manual input: Task 4.
- Success class required: Task 1 and Task 4.
- Legacy mapping: Task 1.
- AI batch unchanged: Task 4 source test and final proof.

Placeholder scan: no open placeholder markers or open-ended implementation steps remain.

Type consistency: backend field names and frontend field names match the spec and each other.
