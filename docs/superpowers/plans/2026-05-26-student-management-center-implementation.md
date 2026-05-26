# Student Management Center Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename class management to 学管中心 and add structured class lifecycle management, student management filters, yearly promotion, and class/student history.

**Architecture:** Extend the existing class/student SQLite model instead of replacing it. Keep `classes.name` as a generated compatibility display field, add structured fields and history tables in `lesson_manager.py`, then update `frontend/src/App.tsx` to render the new 学管中心 tabs and click-based filters.

**Tech Stack:** Flask, SQLite, React, TypeScript, Node `tsx --test`, Python `unittest`.

---

## File Map

- Modify `lesson_manager.py`: class structured fields, display-name generation, cohort-year inference, promotion logic, history tables.
- Modify `app.py`: expose promotion preview/confirm endpoints if needed and return structured class fields through existing class APIs.
- Modify `tests/test_account_flow.py`: backend class create/update, filters, promotion, and history coverage.
- Modify `tests/test_master_data_store.py`: compatibility coverage for class aliases and class display names if existing assertions need updating.
- Modify `frontend/src/App.tsx`: navigation label, 学管中心 tabs, structured class form, filters, student management view, history panels.
- Modify `frontend/src/workspace-navigation.test.ts`: navigation rename/source coverage.
- Modify `frontend/src/account-card.test.tsx`: 学管中心 UI source coverage.

## Task 1: Structured Class Domain Helpers

**Files:**
- Modify: `lesson_manager.py`
- Test: `tests/test_account_flow.py`

- [ ] **Step 1: Write failing tests**

Add tests:

```python
def test_structured_class_name_and_cohort_are_generated(self):
    class_id = lesson_manager.save_class(
        "",
        subject="数学",
        grade="7年级",
        stage="初中",
        class_number="3",
        teacher_user_id=self.owner["id"],
        is_bridge=False,
        today="2026-05-26",
    )
    cls = lesson_manager.get_class(class_id)
    self.assertEqual(cls["cohort_year"], 2025)
    self.assertEqual(cls["name"], "2025级7年级3班")
    self.assertEqual(cls["current_grade"], "7年级")

def test_bridge_class_display_name_keeps_bridge_marker_before_target_stage(self):
    class_id = lesson_manager.save_class(
        "",
        subject="数学",
        grade="5年级",
        stage="小奥",
        class_number="1",
        teacher_user_id=self.owner["id"],
        is_bridge=True,
        bridge_target="高中衔接",
        today="2026-05-26",
    )
    cls = lesson_manager.get_class(class_id)
    self.assertEqual(cls["name"], "2021级5年级1班·衔接")
    self.assertEqual(cls["content_track"], "高中衔接")
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
python3 -m unittest tests.test_account_flow.AccountFlowTestCase.test_structured_class_name_and_cohort_are_generated tests.test_account_flow.AccountFlowTestCase.test_bridge_class_display_name_keeps_bridge_marker_before_target_stage -v
```

Expected: fail because `save_class` does not accept structured fields.

- [ ] **Step 3: Add helpers**

In `lesson_manager.py`, add:

```python
CLASS_STAGES = ("小奥", "初中", "高中")
CLASS_GRADE_ORDER = ("1年级", "2年级", "3年级", "4年级", "5年级", "6年级", "7年级", "8年级", "9年级", "高一", "高二", "高三")
CLASS_STAGE_GRADES = {
    "小奥": ("1年级", "2年级", "3年级", "4年级", "5年级", "6年级"),
    "初中": ("7年级", "8年级", "9年级"),
    "高中": ("高一", "高二", "高三"),
}

def normalize_class_grade(value: str) -> str:
    raw = str(value or "").strip()
    aliases = {"一年级": "1年级", "二年级": "2年级", "三年级": "3年级", "四年级": "4年级", "五年级": "5年级", "六年级": "6年级", "初一": "7年级", "初二": "8年级", "初三": "9年级", "高1": "高一", "高2": "高二", "高3": "高三"}
    return aliases.get(raw, raw)

def infer_class_stage(grade: str) -> str:
    normalized = normalize_class_grade(grade)
    for stage, grades in CLASS_STAGE_GRADES.items():
      if normalized in grades:
          return stage
    return ""

def current_school_year_start(today: str | None = None) -> int:
    date_value = datetime.strptime(today, "%Y-%m-%d").date() if today else date.today()
    return date_value.year if (date_value.month, date_value.day) >= (6, 30) else date_value.year - 1

def infer_cohort_year(grade: str, today: str | None = None) -> int:
    normalized = normalize_class_grade(grade)
    stage = infer_class_stage(normalized)
    grades = CLASS_STAGE_GRADES.get(stage, ())
    offset = grades.index(normalized) if normalized in grades else 0
    return current_school_year_start(today) - offset

def build_structured_class_name(cohort_year: int, current_grade: str, class_number: str, is_bridge: bool) -> str:
    suffix = "·衔接" if is_bridge else ""
    return f"{cohort_year}级{current_grade}{class_number}班{suffix}"
```

- [ ] **Step 4: Add table columns and save/get serialization**

Add columns in schema migration:

```python
_ensure_column(conn, "classes", "stage", "TEXT DEFAULT ''")
_ensure_column(conn, "classes", "current_grade", "TEXT DEFAULT ''")
_ensure_column(conn, "classes", "class_number", "TEXT DEFAULT ''")
_ensure_column(conn, "classes", "cohort_year", "INTEGER DEFAULT 0")
_ensure_column(conn, "classes", "is_bridge", "INTEGER DEFAULT 0")
_ensure_column(conn, "classes", "bridge_target", "TEXT DEFAULT ''")
_ensure_column(conn, "classes", "content_track", "TEXT DEFAULT ''")
_ensure_column(conn, "classes", "last_promoted_at", "TEXT DEFAULT ''")
```

Extend `save_class`, `update_class`, `_class_row_to_dict` to accept and return these fields. Generate `name` when structured fields are present:

```python
current_grade = normalize_class_grade(grade or current_grade)
stage = stage or infer_class_stage(current_grade)
cohort_year = cohort_year or infer_cohort_year(current_grade, today)
display_name = build_structured_class_name(cohort_year, current_grade, str(class_number).strip(), bool(is_bridge)) if class_number else name
```

- [ ] **Step 5: Verify tests pass**

Run the two-test command. Expected: `OK`.

- [ ] **Step 6: Commit**

```bash
git add lesson_manager.py tests/test_account_flow.py
git commit -m "feat: add structured class fields"
```

## Task 2: Class and Student History Tables

**Files:**
- Modify: `lesson_manager.py`
- Test: `tests/test_account_flow.py`

- [ ] **Step 1: Write failing tests**

Add:

```python
def test_class_history_records_create_teacher_change_and_student_moves(self):
    class_id = lesson_manager.save_class("", subject="数学", grade="7年级", stage="初中", class_number="3", teacher_user_id=self.owner["id"], today="2026-05-26")
    student = lesson_manager.create_student_for_class(class_id, "Alice")
    lesson_manager.remove_student_from_class(class_id, student["id"])
    history = lesson_manager.list_class_history(class_id)
    actions = [item["action"] for item in history]
    self.assertIn("created", actions)
    self.assertIn("student_added", actions)
    self.assertIn("student_removed", actions)
    student_history = lesson_manager.list_student_class_history(student["id"])
    self.assertEqual([item["action"] for item in student_history], ["joined", "left"])
```

- [ ] **Step 2: Run and verify failure**

Run:

```bash
python3 -m unittest tests.test_account_flow.AccountFlowTestCase.test_class_history_records_create_teacher_change_and_student_moves -v
```

Expected: fail because history functions do not exist.

- [ ] **Step 3: Add history schema**

In `lesson_manager.py` schema:

```python
CREATE TABLE IF NOT EXISTS class_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    class_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    before_json TEXT NOT NULL DEFAULT '{}',
    after_json TEXT NOT NULL DEFAULT '{}',
    note TEXT NOT NULL DEFAULT '',
    actor_user_id INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)
```

```python
CREATE TABLE IF NOT EXISTS student_class_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    class_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    before_json TEXT NOT NULL DEFAULT '{}',
    after_json TEXT NOT NULL DEFAULT '{}',
    note TEXT NOT NULL DEFAULT '',
    actor_user_id INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)
```

- [ ] **Step 4: Add history functions**

```python
def record_class_history(class_id: int, action: str, before: dict | None = None, after: dict | None = None, note: str = "", actor_user_id: int | None = None) -> None:
    cls = get_class(class_id)
    if not cls:
        return
    with get_db() as conn:
        conn.execute(
            "INSERT INTO class_history (organization_id, class_id, action, before_json, after_json, note, actor_user_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (cls["organization_id"], class_id, action, json.dumps(before or {}, ensure_ascii=False), json.dumps(after or {}, ensure_ascii=False), note, actor_user_id),
        )

def list_class_history(class_id: int) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM class_history WHERE class_id=? ORDER BY created_at DESC, id DESC", (class_id,)).fetchall()
    return [dict(row) for row in rows]

def record_student_class_history(student_id: int, class_id: int, action: str, before: dict | None = None, after: dict | None = None, note: str = "", actor_user_id: int | None = None) -> None:
    cls = get_class(class_id)
    if not cls:
        return
    with get_db() as conn:
        conn.execute(
            "INSERT INTO student_class_history (organization_id, student_id, class_id, action, before_json, after_json, note, actor_user_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (cls["organization_id"], student_id, class_id, action, json.dumps(before or {}, ensure_ascii=False), json.dumps(after or {}, ensure_ascii=False), note, actor_user_id),
        )

def list_student_class_history(student_id: int) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM student_class_history WHERE student_id=? ORDER BY created_at DESC, id DESC", (student_id,)).fetchall()
    return [dict(row) for row in rows]
```

Call history functions from `save_class`, `update_class`, `set_class_teacher_user_id`, `create_student_for_class`, and `remove_student_from_class`.

- [ ] **Step 5: Verify tests pass**

Run the one-test command. Expected: `OK`.

- [ ] **Step 6: Commit**

```bash
git add lesson_manager.py tests/test_account_flow.py
git commit -m "feat: record class and student history"
```

## Task 3: Promotion Engine

**Files:**
- Modify: `lesson_manager.py`
- Test: `tests/test_account_flow.py`

- [ ] **Step 1: Write failing tests**

Add:

```python
def test_promote_classes_advances_regular_and_bridge_classes(self):
    regular_id = lesson_manager.save_class("", subject="数学", grade="5年级", stage="小奥", class_number="1", teacher_user_id=self.owner["id"], today="2026-05-26")
    bridge_id = lesson_manager.save_class("", subject="数学", grade="6年级", stage="小奥", class_number="2", teacher_user_id=self.owner["id"], is_bridge=True, bridge_target="默认下一学段", today="2026-05-26")
    result = lesson_manager.promote_classes_for_academic_year(today="2026-06-30")
    self.assertIn(regular_id, result["promoted_ids"])
    self.assertIn(bridge_id, result["promoted_ids"])
    self.assertEqual(lesson_manager.get_class(regular_id)["name"], "2021级6年级1班")
    promoted_bridge = lesson_manager.get_class(bridge_id)
    self.assertEqual(promoted_bridge["name"], "2020级7年级2班")
    self.assertFalse(promoted_bridge["is_bridge"])

def test_promote_classes_marks_graduation_regular_classes_pending(self):
    class_id = lesson_manager.save_class("", subject="数学", grade="6年级", stage="小奥", class_number="1", teacher_user_id=self.owner["id"], today="2026-05-26")
    result = lesson_manager.promote_classes_for_academic_year(today="2026-06-30")
    self.assertIn(class_id, result["pending_ids"])
    self.assertEqual(lesson_manager.get_class(class_id)["current_grade"], "6年级")
```

- [ ] **Step 2: Run and verify failure**

Run:

```bash
python3 -m unittest tests.test_account_flow.AccountFlowTestCase.test_promote_classes_advances_regular_and_bridge_classes tests.test_account_flow.AccountFlowTestCase.test_promote_classes_marks_graduation_regular_classes_pending -v
```

Expected: fail because promotion does not exist.

- [ ] **Step 3: Add promotion helpers**

```python
PROMOTION_NEXT_GRADE = {
    "1年级": "2年级", "2年级": "3年级", "3年级": "4年级", "4年级": "5年级", "5年级": "6年级",
    "6年级": "7年级", "7年级": "8年级", "8年级": "9年级", "9年级": "高一",
    "高一": "高二", "高二": "高三",
}
GRADUATION_GRADES = {"6年级", "9年级", "高三"}

def bridge_crosses_target_stage(current_grade: str, next_grade: str, bridge_target: str) -> bool:
    if current_grade == "6年级" and next_grade == "7年级":
        return bridge_target in {"", "默认下一学段", "初中衔接"}
    if current_grade == "9年级" and next_grade == "高一":
        return bridge_target in {"", "默认下一学段", "高中衔接"}
    return False
```

Add:

```python
def promote_classes_for_academic_year(today: str | None = None) -> dict:
    today_value = today or date.today().isoformat()
    promoted_ids: list[int] = []
    pending_ids: list[int] = []
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM classes WHERE status IS NULL OR status!='deleted'").fetchall()
        for row in rows:
            item = _class_row_to_dict(row)
            if item.get("last_promoted_at", "").startswith(today_value):
                continue
            current_grade = normalize_class_grade(item.get("current_grade") or item.get("grade") or "")
            next_grade = PROMOTION_NEXT_GRADE.get(current_grade)
            if not next_grade:
                pending_ids.append(item["id"])
                continue
            is_bridge = bool(item.get("is_bridge"))
            if current_grade in GRADUATION_GRADES and not is_bridge:
                pending_ids.append(item["id"])
                record_class_history(item["id"], "promotion_pending", after={"reason": "graduation_grade", "grade": current_grade})
                continue
            next_is_bridge = is_bridge and not bridge_crosses_target_stage(current_grade, next_grade, item.get("bridge_target") or "")
            next_stage = infer_class_stage(next_grade)
            next_name = build_structured_class_name(item["cohort_year"], next_grade, item.get("class_number") or "", next_is_bridge)
            conn.execute(
                "UPDATE classes SET grade=?, current_grade=?, stage=?, name=?, is_bridge=?, last_promoted_at=? WHERE id=?",
                (next_grade, next_grade, next_stage, next_name, 1 if next_is_bridge else 0, today_value, item["id"]),
            )
            promoted_ids.append(item["id"])
            record_class_history(item["id"], "promoted", before=item, after={"current_grade": next_grade, "name": next_name, "is_bridge": next_is_bridge})
    return {"promoted_ids": promoted_ids, "pending_ids": pending_ids}
```

- [ ] **Step 4: Verify tests pass**

Run the two-test command. Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add lesson_manager.py tests/test_account_flow.py
git commit -m "feat: promote classes annually"
```

## Task 4: 学管中心 Navigation and Tabs

**Files:**
- Modify: `frontend/src/App.tsx`
- Test: `frontend/src/workspace-navigation.test.ts`, `frontend/src/account-card.test.tsx`

- [ ] **Step 1: Write failing source tests**

Add navigation assertion:

```ts
assert.match(sidebarBlock, /id: 'classes'[\s\S]*label: '学管中心'/);
assert.match(appSource, /classes: '学管中心'/);
```

Add account-card test:

```ts
test('student management center exposes class and student tabs', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const classManagementBlock = source.match(/const ClassManagementPage = \([\s\S]*?\n};/);
  assert.ok(classManagementBlock);
  assert.match(classManagementBlock[0], /const \[studentCenterTab, setStudentCenterTab\] = useState<'classes' \| 'students'>\('classes'\);/);
  assert.match(classManagementBlock[0], /班级管理/);
  assert.match(classManagementBlock[0], /学员管理/);
});
```

- [ ] **Step 2: Run and verify failure**

```bash
cd frontend && npx tsx --test src/workspace-navigation.test.ts src/account-card.test.tsx
```

Expected: fail on label/tab assertions.

- [ ] **Step 3: Rename navigation and add tabs**

In `Sidebar` menu item, change `{ id: 'classes', icon: Home, label: '班级管理' }` to label `学管中心`. Update `pageTitle.classes`.

In `ClassManagementPage`:

```tsx
const [studentCenterTab, setStudentCenterTab] = useState<'classes' | 'students'>('classes');
```

Render tabs before existing content:

```tsx
<div className="grid grid-cols-2 gap-2 rounded-2xl bg-sky-50 p-1 dark:bg-white/5">
  {[
    { key: 'classes' as const, label: '班级管理' },
    { key: 'students' as const, label: '学员管理' },
  ].map((item) => (
    <button type="button" key={item.key} onClick={() => setStudentCenterTab(item.key)} className={cn('h-10 rounded-xl text-sm font-bold transition', studentCenterTab === item.key ? 'bg-white text-sky-700 shadow-sm dark:bg-sky-400/15 dark:text-sky-100' : 'text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white')}>
      {item.label}
    </button>
  ))}
</div>
```

Keep existing class management body under `studentCenterTab === 'classes'`; add a minimal `students` branch that lists students from loaded classes.

- [ ] **Step 4: Verify**

Run the frontend source test command. Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.tsx frontend/src/workspace-navigation.test.ts frontend/src/account-card.test.tsx
git commit -m "feat: rename class management to student center"
```

## Task 5: Structured Class Form and Filters

**Files:**
- Modify: `frontend/src/App.tsx`
- Test: `frontend/src/account-card.test.tsx`

- [ ] **Step 1: Write source tests**

Add:

```ts
test('student center class form uses structured class fields and click filters', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const classManagementBlock = source.match(/const ClassManagementPage = \([\s\S]*?\n};/);
  assert.ok(classManagementBlock);
  assert.match(classManagementBlock[0], /stage/);
  assert.match(classManagementBlock[0], /class_number/);
  assert.match(classManagementBlock[0], /is_bridge/);
  assert.match(classManagementBlock[0], /cohort_year/);
  assert.match(classManagementBlock[0], /教师/);
  assert.match(classManagementBlock[0], /学段/);
  assert.match(classManagementBlock[0], /年级/);
  assert.doesNotMatch(classManagementBlock[0], /placeholder="班级名称"/);
});
```

- [ ] **Step 2: Run and verify failure**

Run `cd frontend && npx tsx --test src/account-card.test.tsx`. Expected: fail.

- [ ] **Step 3: Add structured form state**

Extend class form state with:

```tsx
stage: '小奥',
current_grade: '1年级',
class_number: '1',
teacher_user_id: '',
is_bridge: false,
bridge_target: '默认下一学段',
content_track: '',
```

On submit, send these fields to `/api/classes`. Remove manual full-name input from create/edit; show generated preview:

```tsx
const previewClassName = `${estimatedCohortYear}级${form.current_grade}${form.class_number}班${form.is_bridge ? '·衔接' : ''}`;
```

- [ ] **Step 4: Add click filters**

Add filter state:

```tsx
const [classTeacherFilter, setClassTeacherFilter] = useState<number | null>(null);
const [classStageFilter, setClassStageFilter] = useState('');
const [classGradeFilter, setClassGradeFilter] = useState('');
const [classIdFilter, setClassIdFilter] = useState<number | null>(null);
```

Render teacher popover first, then stage chips, grade chips, class chips. Filter class list in that order.

- [ ] **Step 5: Verify**

Run `cd frontend && npx tsx --test src/account-card.test.tsx`. Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/App.tsx frontend/src/account-card.test.tsx
git commit -m "feat: add structured class management filters"
```

## Task 6: 学员管理 View and History Panels

**Files:**
- Modify: `frontend/src/App.tsx`, `app.py`
- Test: `frontend/src/account-card.test.tsx`, `tests/test_account_flow.py`

- [ ] **Step 1: Write backend API tests**

Add tests for:

```python
def test_class_and_student_history_endpoints_return_items(self):
    class_id = lesson_manager.save_class("", subject="数学", grade="7年级", stage="初中", class_number="3", teacher_user_id=self.owner["id"], today="2026-05-26")
    student = lesson_manager.create_student_for_class(class_id, "Alice")
    class_history = self.client.get(f"/api/classes/{class_id}/history", headers=self.auth_headers(self.owner_token))
    self.assertEqual(class_history.status_code, 200)
    self.assertTrue(class_history.get_json()["items"])
    student_history = self.client.get(f"/api/students/{student['id']}/class-history", headers=self.auth_headers(self.owner_token))
    self.assertEqual(student_history.status_code, 200)
    self.assertTrue(student_history.get_json()["items"])
```

- [ ] **Step 2: Implement history endpoints**

In `app.py`, add:

```python
@app.route("/api/classes/<int:class_id>/history", methods=["GET"])
def api_class_history(class_id):
    user = require_auth()
    cls = _require_accessible_class(user, class_id)
    if not cls:
        return jsonify({"error": "class not found"}), 404
    return jsonify({"items": list_class_history(class_id)})

@app.route("/api/students/<int:student_id>/class-history", methods=["GET"])
def api_student_class_history(student_id):
    user = require_auth()
    items = [item for item in list_student_class_history(student_id) if _require_accessible_class(user, int(item["class_id"]))]
    return jsonify({"items": items})
```

Import `list_class_history` and `list_student_class_history`.

- [ ] **Step 3: Add frontend source test**

```ts
test('student management tab renders student filters and history affordance', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const classManagementBlock = source.match(/const ClassManagementPage = \([\s\S]*?\n};/);
  assert.ok(classManagementBlock);
  assert.match(classManagementBlock[0], /studentTeacherFilter/);
  assert.match(classManagementBlock[0], /studentStageFilter/);
  assert.match(classManagementBlock[0], /studentGradeFilter/);
  assert.match(classManagementBlock[0], /studentClassFilter/);
  assert.match(classManagementBlock[0], /班级进出历史/);
});
```

- [ ] **Step 4: Implement student tab**

Flatten students from classes loaded through `/api/classes/<id>/students` or existing class-student load path. Add filters teacher -> stage -> grade -> class -> student. Render cards with name, current class, stage, grade, teacher, and a `班级进出历史` action that fetches `/api/students/:id/class-history`.

- [ ] **Step 5: Verify**

Run:

```bash
python3 -m unittest tests.test_account_flow.AccountFlowTestCase.test_class_and_student_history_endpoints_return_items -v
cd frontend && npx tsx --test src/account-card.test.tsx
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add app.py lesson_manager.py frontend/src/App.tsx tests/test_account_flow.py frontend/src/account-card.test.tsx
git commit -m "feat: add student management history view"
```

## Task 7: Final Verification

**Files:**
- Verify only.

- [ ] **Step 1: Run backend targeted suites**

```bash
python3 -m unittest tests.test_account_flow tests.test_master_data_store -v
```

Expected: pass. If unrelated historical failures appear, record exact failures and run targeted new tests separately.

- [ ] **Step 2: Run frontend source tests**

```bash
cd frontend && npx tsx --test src/account-card.test.tsx src/workspace-navigation.test.ts
```

Expected: pass.

- [ ] **Step 3: Run frontend build**

```bash
npm --prefix frontend run build
```

Expected: build succeeds. Existing chunk-size warnings are acceptable.

- [ ] **Step 4: Commit proof fixes only if files changed**

```bash
git status --short
```

If no files changed, do not commit. If final verification required source/test fixes:

```bash
git add <changed-files>
git commit -m "test: verify student management center"
```
