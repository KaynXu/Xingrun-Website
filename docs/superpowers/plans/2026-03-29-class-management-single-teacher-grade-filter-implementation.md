# Class Management Single-Teacher Grade Filter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Update `班级管理` so each class is bound to exactly one teacher account, `teacher_name` stays synchronized with that teacher, and the class-card area can be filtered by specific grade values.

**Architecture:** Keep the current Flask + SQLite backend and React workspace shell, but stop treating teacher assignment as a per-user multi-checkbox matrix. Introduce a small class-centric teacher-binding path in the backend so rebinding is atomic and one-to-one at the business-logic level, while preserving `user_classes` for compatibility. On the frontend, keep the current single-expand card structure in `ClassManagementPage`, add a top-level grade filter, derive `filteredClasses`, and replace multi-teacher UI with single-select teacher binding.

**Tech Stack:** Flask, SQLite, Python `unittest`, React 19, TypeScript, Vite, Tailwind CSS, Node `test`

---

### Task 1: Lock The One-Teacher Backend Contract With Failing Tests

**Files:**
- Modify: `tests/test_account_flow.py`

- [ ] **Step 1: Add a failing regression that binds one teacher to one class and verifies `teacher_name` sync**

```python
def test_staff_can_bind_single_teacher_to_class_and_sync_teacher_name(self):
    owner_login = self.client.post(
        "/api/login",
        json={"username": "Kayn", "password": "xingrun2026"},
    )
    self.assertEqual(owner_login.status_code, 200)
    owner_token = owner_login.get_json()["token"]

    admin_payload = self.approve_user(
        owner_token=owner_token,
        username="admin_teacher_bind",
        display_name="Admin Teacher Bind",
        password="adminteacher123",
    )
    admin_token = admin_payload["token"]
    admin_id = self.client.get(
        "/api/me",
        headers=self.auth_headers(admin_token),
    ).get_json()["id"]
    promote = self.client.put(
        f"/api/admin/users/{admin_id}/role",
        headers=self.auth_headers(owner_token),
        json={"role": "admin"},
    )
    self.assertEqual(promote.status_code, 200)

    teacher_payload = self.approve_user(
        owner_token=owner_token,
        username="teacher_bind_a",
        display_name="Teacher Bind A",
        password="teacherbind123",
    )
    teacher_id = self.client.get(
        "/api/me",
        headers=self.auth_headers(teacher_payload["token"]),
    ).get_json()["id"]

    create_class = self.client.post(
        "/api/classes",
        headers=self.auth_headers(admin_token),
        json={
            "name": "六年级 2 班",
            "subject": "数学",
            "grade": "六年级",
            "teacher_name": "",
            "teacher_email": "",
        },
    )
    self.assertEqual(create_class.status_code, 201)
    class_id = create_class.get_json()["id"]

    bind_teacher = self.client.put(
        f"/api/classes/{class_id}/teacher",
        headers=self.auth_headers(admin_token),
        json={"teacher_user_id": teacher_id},
    )
    self.assertEqual(bind_teacher.status_code, 200)

    class_detail = self.client.get(
        f"/api/classes/{class_id}",
        headers=self.auth_headers(admin_token),
    )
    self.assertEqual(class_detail.status_code, 200)
    class_payload = class_detail.get_json()
    self.assertEqual(class_payload["teacher_name"], "Teacher Bind A")
    self.assertEqual(class_payload["teacher_user_id"], teacher_id)
```

- [ ] **Step 2: Add a failing regression that rebinds a class and proves the old teacher relation is removed instead of appended**

```python
def test_rebinding_class_replaces_previous_teacher_relation(self):
    owner_login = self.client.post(
        "/api/login",
        json={"username": "Kayn", "password": "xingrun2026"},
    )
    self.assertEqual(owner_login.status_code, 200)
    owner_token = owner_login.get_json()["token"]

    admin_payload = self.approve_user(
        owner_token=owner_token,
        username="admin_teacher_swap",
        display_name="Admin Teacher Swap",
        password="adminswap123",
    )
    admin_token = admin_payload["token"]
    admin_id = self.client.get(
        "/api/me",
        headers=self.auth_headers(admin_token),
    ).get_json()["id"]
    promote = self.client.put(
        f"/api/admin/users/{admin_id}/role",
        headers=self.auth_headers(owner_token),
        json={"role": "admin"},
    )
    self.assertEqual(promote.status_code, 200)

    teacher_a = self.approve_user(owner_token, "teacher_swap_a", "Teacher Swap A", "teacherA123")
    teacher_b = self.approve_user(owner_token, "teacher_swap_b", "Teacher Swap B", "teacherB123")
    teacher_a_id = self.client.get("/api/me", headers=self.auth_headers(teacher_a["token"])).get_json()["id"]
    teacher_b_id = self.client.get("/api/me", headers=self.auth_headers(teacher_b["token"])).get_json()["id"]

    create_class = self.client.post(
        "/api/classes",
        headers=self.auth_headers(admin_token),
        json={"name": "初一 1 班", "subject": "英语", "grade": "初一", "teacher_name": "", "teacher_email": ""},
    )
    self.assertEqual(create_class.status_code, 201)
    class_id = create_class.get_json()["id"]

    first_bind = self.client.put(
        f"/api/classes/{class_id}/teacher",
        headers=self.auth_headers(admin_token),
        json={"teacher_user_id": teacher_a_id},
    )
    self.assertEqual(first_bind.status_code, 200)

    second_bind = self.client.put(
        f"/api/classes/{class_id}/teacher",
        headers=self.auth_headers(admin_token),
        json={"teacher_user_id": teacher_b_id},
    )
    self.assertEqual(second_bind.status_code, 200)

    teacher_a_classes = self.client.get(
        f"/api/admin/users/{teacher_a_id}/classes",
        headers=self.auth_headers(admin_token),
    )
    teacher_b_classes = self.client.get(
        f"/api/admin/users/{teacher_b_id}/classes",
        headers=self.auth_headers(admin_token),
    )
    self.assertEqual(teacher_a_classes.status_code, 200)
    self.assertEqual(teacher_b_classes.status_code, 200)
    self.assertEqual(teacher_a_classes.get_json()["class_ids"], [])
    self.assertEqual(teacher_b_classes.get_json()["class_ids"], [class_id])
```

- [ ] **Step 3: Run the backend regression file and confirm the new assertions fail because the class-centric teacher endpoint and payload do not exist yet**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary && /Users/ark.mini/Desktop/Xingrun-Review/.venv/bin/python -m unittest tests.test_account_flow -v`

Expected: FAIL with new class-teacher binding assertions, ideally 404 or missing-key failures around `/api/classes/<class_id>/teacher` and missing `teacher_user_id` in class payload.

- [ ] **Step 4: Keep the failing backend test file staged only after the red state is cleanly attributable to missing behavior, not test typos**

```bash
cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary
git add tests/test_account_flow.py
```

### Task 2: Lock The Grade Filter And Single-Teacher UI With Failing Frontend Tests

**Files:**
- Modify: `frontend/src/account-card.test.tsx`
- Modify: `frontend/src/workspace-navigation.test.ts`

- [ ] **Step 1: Add a source-level assertion for grade filter state and filtered list derivation**

```ts
test('class management source adds a specific grade filter and filtered class list', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const classManagementBlock = source.match(/const ClassManagementPage = \([\s\S]*?\n};/);

  assert.ok(classManagementBlock);
  assert.match(classManagementBlock[0], /const \[selectedGradeFilter, setSelectedGradeFilter\] = useState<string>\('全部'\)/);
  assert.match(classManagementBlock[0], /const gradeFilterOptions = \[/);
  assert.match(classManagementBlock[0], /const filteredClasses = classes\.filter\(/);
  assert.match(classManagementBlock[0], /selectedGradeFilter === '全部'/);
});
```

- [ ] **Step 2: Add a source-level assertion that the card summary is single-teacher and no longer shows teacher-count copy or checkbox assignment**

```ts
test('class management source uses single-teacher summary and removes multi-teacher checkbox copy', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const classManagementBlock = source.match(/const ClassManagementPage = \([\s\S]*?\n};/);

  assert.ok(classManagementBlock);
  assert.doesNotMatch(classManagementBlock[0], /已分配 \{selectedTeacherIds.length\} 位老师/);
  assert.doesNotMatch(classManagementBlock[0], /type="checkbox"/);
  assert.match(classManagementBlock[0], /当前老师：/);
  assert.match(classManagementBlock[0], /teacher_user_id/);
  assert.match(classManagementBlock[0], /type="radio"|handleSelectTeacherForClass/);
});
```

- [ ] **Step 3: Add a structural assertion for class-centric teacher binding requests**

```ts
test('class management source binds teachers through class-centric API calls', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const classManagementBlock = source.match(/const ClassManagementPage = \([\s\S]*?\n};/);

  assert.ok(classManagementBlock);
  assert.match(classManagementBlock[0], /apiFetch<\{ teacher_bindings: Record<number, number \| null> \}>\('\/api\/classes\/teacher-bindings'\)/);
  assert.match(classManagementBlock[0], /apiFetch\(`\/api\/classes\/\$\{classId\}\/teacher`/);
  assert.match(classManagementBlock[0], /teacherBindingSavingByClassId/);
});
```

- [ ] **Step 4: Run the focused frontend tests to confirm they fail because the filter state and class-centric teacher binding flow are missing**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend && npx tsx --test src/workspace-navigation.test.ts src/account-card.test.tsx`

Expected: FAIL on the new grade-filter and teacher-binding assertions, not on test syntax.

- [ ] **Step 5: Stage the red frontend tests after they fail for the intended reasons**

```bash
cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary
git add frontend/src/account-card.test.tsx frontend/src/workspace-navigation.test.ts
```

### Task 3: Add Atomic Class-Centric Teacher Binding In The Backend

**Files:**
- Modify: `lesson_manager.py`
- Modify: `app.py`
- Test: `tests/test_account_flow.py`

- [ ] **Step 1: Add lesson-manager helpers that read and write one teacher per class while preserving `user_classes`**

```python
def get_class_teacher_user_id(class_id: int) -> int | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT user_id FROM user_classes WHERE class_id=? ORDER BY user_id LIMIT 1",
            (class_id,),
        ).fetchone()
        return row["user_id"] if row else None


def list_class_teacher_bindings() -> dict[int, int | None]:
    with get_conn() as conn:
        class_rows = conn.execute("SELECT id FROM classes ORDER BY id").fetchall()
        binding_rows = conn.execute("SELECT class_id, user_id FROM user_classes ORDER BY class_id, user_id").fetchall()
        bindings = {row["id"]: None for row in class_rows}
        for row in binding_rows:
            bindings[row["class_id"]] = row["user_id"]
        return bindings


def set_class_teacher_user_id(class_id: int, teacher_user_id: int | None):
    with get_conn() as conn:
        class_row = conn.execute("SELECT * FROM classes WHERE id=?", (class_id,)).fetchone()
        if not class_row:
            raise LookupError("class not found")

        teacher_row = None
        if teacher_user_id is not None:
            teacher_row = _fetch_user_row_by_id(conn, teacher_user_id)
            if not teacher_row:
                raise LookupError("user not found")
            if teacher_row["status"] != "active":
                raise ValueError("teacher must be active")

        conn.execute("DELETE FROM user_classes WHERE class_id=?", (class_id,))
        if teacher_row:
            conn.execute(
                "INSERT OR IGNORE INTO user_classes (user_id, class_id) VALUES (?, ?)",
                (teacher_user_id, class_id),
            )
            conn.execute(
                "UPDATE classes SET teacher_name=?, teacher_email='' WHERE id=?",
                (teacher_row["display_name"], class_id),
            )
        else:
            conn.execute(
                "UPDATE classes SET teacher_name='', teacher_email='' WHERE id=?",
                (class_id,),
            )
```

- [ ] **Step 2: Expose staff-only class-centric teacher APIs in Flask**

```python
@app.route("/api/classes/teacher-bindings", methods=["GET"])
def api_class_teacher_bindings():
    _, error = _require_staff()
    if error:
        return error
    return jsonify({"teacher_bindings": list_class_teacher_bindings()})


@app.route("/api/classes/<int:class_id>/teacher", methods=["PUT"])
def api_class_teacher_bind(class_id):
    _, error = _require_staff()
    if error:
        return error
    data = request.json or {}
    teacher_user_id = data.get("teacher_user_id")
    if teacher_user_id is not None and (isinstance(teacher_user_id, bool) or not isinstance(teacher_user_id, int)):
        return jsonify({"error": "teacher_user_id must be an integer or null"}), 400
    try:
        set_class_teacher_user_id(class_id, teacher_user_id)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except LookupError as exc:
        return jsonify({"error": str(exc)}), 404
    return jsonify({"ok": True})
```

- [ ] **Step 3: Extend class detail payload so the frontend can render the current bound teacher without inferring from checkbox selections**

```python
@app.route("/api/classes/<int:class_id>", methods=["GET"])
def api_class_get(class_id):
    _, error = _require_auth()
    if error:
        return error
    cls = get_class(class_id)
    if not cls:
        return jsonify({"error": "not found"}), 404
    lessons = list_lessons(class_id=class_id)
    return jsonify({
        **cls,
        "teacher_user_id": get_class_teacher_user_id(class_id),
        "lessons": lessons,
    })
```

- [ ] **Step 4: Re-run the backend tests until the new single-teacher regressions pass**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary && /Users/ark.mini/Desktop/Xingrun-Review/.venv/bin/python -m unittest tests.test_account_flow -v`

Expected: PASS with the new class-binding scenarios green and the summary ending in `OK`.

- [ ] **Step 5: Commit the backend part once the class-centric teacher contract is stable**

```bash
cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary
git add app.py lesson_manager.py tests/test_account_flow.py
git commit -m "feat: enforce single teacher class bindings"
```

### Task 4: Refactor ClassManagementPage To Grade Filtering And Single-Teacher Selection

**Files:**
- Modify: `frontend/src/App.tsx`
- Test: `frontend/src/account-card.test.tsx`
- Test: `frontend/src/workspace-navigation.test.ts`

- [ ] **Step 1: Add grade-filter state, canonical options, and filtered class derivation above the card list**

```ts
const GRADE_FILTER_OPTIONS = ['全部', '一年级', '二年级', '三年级', '四年级', '五年级', '六年级', '初一', '初二', '初三', '高一', '高二', '高三'] as const;

const [selectedGradeFilter, setSelectedGradeFilter] = useState<string>('全部');

const filteredClasses = classes.filter((item) => {
  if (selectedGradeFilter === '全部') {
    return true;
  }
  return (item.grade || '').trim() === selectedGradeFilter;
});

useEffect(() => {
  if (expandedClassId === 'new') {
    return;
  }
  if (typeof expandedClassId === 'number' && !filteredClasses.some((item) => item.id === expandedClassId)) {
    setExpandedClassId(null);
  }
}, [expandedClassId, filteredClasses]);
```

- [ ] **Step 2: Replace user-centric multi-teacher state with class-centric single-teacher binding state**

```ts
const [teacherUserIdByClassId, setTeacherUserIdByClassId] = useState<Record<number, number | null>>({});
const [teacherBindingSavingByClassId, setTeacherBindingSavingByClassId] = useState<Record<number, boolean>>({});

const loadPage = useCallback(async (preferredExpandedClassId?: number | 'new' | null) => {
  const requestVersion = ++loadPageRequestVersionRef.current;
  setLoading(true);
  setPageError('');
  try {
    const [classItems, userItems, teacherBindingPayload] = await Promise.all([
      apiFetch<ClassItem[]>('/api/classes'),
      apiFetch<UserItem[]>('/api/admin/users'),
      apiFetch<{ teacher_bindings: Record<number, number | null> }>('/api/classes/teacher-bindings'),
    ]);

    if (requestVersion !== loadPageRequestVersionRef.current) {
      return;
    }

    setClasses(classItems);
    setUsers(userItems);
    setTeacherUserIdByClassId(
      Object.fromEntries(
        Object.entries(teacherBindingPayload.teacher_bindings).map(([classId, userId]) => [Number(classId), userId]),
      ),
    );
    // keep existing form hydration
  } catch (err) {
    // keep existing error path
  } finally {
    // keep existing request-version guard
  }
}, []);
```

- [ ] **Step 3: Add a class-level teacher selection handler with optimistic rollback**

```ts
const handleSelectTeacherForClass = async (classId: number, teacherUserId: number | null) => {
  if (classInteractionLocked || teacherBindingSavingByClassId[classId]) {
    return;
  }

  const previousTeacherUserId = teacherUserIdByClassId[classId] ?? null;

  setAssignmentError('');
  setTeacherBindingSavingByClassId((current) => ({ ...current, [classId]: true }));
  setTeacherUserIdByClassId((current) => ({ ...current, [classId]: teacherUserId }));

  try {
    await apiFetch(`/api/classes/${classId}/teacher`, {
      method: 'PUT',
      body: JSON.stringify({ teacher_user_id: teacherUserId }),
    });
    await loadPage(classId);
  } catch (err) {
    setTeacherUserIdByClassId((current) => ({ ...current, [classId]: previousTeacherUserId }));
    setAssignmentError(err instanceof Error ? err.message : '班级老师绑定保存失败');
  } finally {
    setTeacherBindingSavingByClassId((current) => {
      const nextState = { ...current };
      delete nextState[classId];
      return nextState;
    });
  }
};
```

- [ ] **Step 4: Rewrite the card summary and expanded teacher section around one current teacher**

```tsx
<div className="flex flex-wrap items-center gap-3 text-sm text-slate-500 dark:text-slate-400">
  <span>{item.grade || '未填写年级'}</span>
  <span>{item.subject || '未填写科目'}</span>
  <span>当前老师：{item.teacher_name || '未绑定老师'}</span>
</div>
```

```tsx
<div className={`${workspaceCardClass} space-y-5 p-5`}>
  <div>
    <h4 className="text-xl font-semibold text-slate-900 dark:text-white">班级老师绑定</h4>
    <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">当前老师：{item.teacher_name || '未绑定老师'}</p>
  </div>

  <label className="relative block">
    <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-sky-500 dark:text-sky-400" size={18} />
    <input
      type="text"
      value={teacherSearch}
      onChange={(e) => handleTeacherSearchChange(item.id, e.target.value)}
      placeholder="搜索老师"
      className={`${workspaceFieldClass} rounded-full py-2.5 pl-11 pr-4`}
    />
  </label>

  <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
    {filteredUsers.map((user) => {
      const checked = teacherUserIdByClassId[item.id] === user.id;
      const rowSaving = Boolean(teacherBindingSavingByClassId[item.id]);
      return (
        <label key={`${item.id}-${user.id}`} className="flex items-start gap-3 rounded-2xl border border-sky-100 bg-white/75 p-4 text-sm dark:border-white/10 dark:bg-slate-950/55">
          <input
            type="radio"
            name={`class-teacher-${item.id}`}
            checked={checked}
            disabled={rowSaving || classInteractionLocked}
            onChange={() => handleSelectTeacherForClass(item.id, user.id)}
            className="mt-1 h-4 w-4 border-slate-300 text-sky-600 focus:ring-sky-500"
          />
          <span className="min-w-0">
            <span className="font-semibold text-slate-900 dark:text-white">{user.name}</span>
            <span className="mt-1 block text-slate-500 dark:text-slate-400">{getRoleLabel(user.role)}</span>
          </span>
        </label>
      );
    })}
  </div>
  <button
    type="button"
    onClick={() => handleSelectTeacherForClass(item.id, null)}
    disabled={Boolean(teacherBindingSavingByClassId[item.id]) || classInteractionLocked}
    className={workspaceSecondaryButtonClass}
  >
    清空老师绑定
  </button>
</div>
```

- [ ] **Step 5: Insert the grade filter bar above the cards and switch rendering from `classes` to `filteredClasses`**

```tsx
<div className="flex flex-col gap-3 rounded-2xl border border-sky-100 bg-sky-50/70 p-4 dark:border-white/10 dark:bg-white/5">
  <div className="flex flex-wrap items-center gap-2">
    {GRADE_FILTER_OPTIONS.map((grade) => {
      const active = selectedGradeFilter === grade;
      return (
        <button
          key={grade}
          type="button"
          onClick={() => setSelectedGradeFilter(grade)}
          className={cn(
            'rounded-full border px-3 py-1.5 text-sm font-medium transition',
            active
              ? 'border-sky-500 bg-sky-500 text-white'
              : 'border-sky-200 bg-white text-slate-600 dark:border-white/10 dark:bg-slate-950/50 dark:text-slate-300',
          )}
        >
          {grade}
        </button>
      );
    })}
  </div>
  <p className="text-sm text-slate-500 dark:text-slate-400">当前筛选：{selectedGradeFilter}，共 {filteredClasses.length} 个班级</p>
</div>

{filteredClasses.length === 0 ? (
  <div className="rounded-2xl border border-dashed border-sky-200 p-10 text-center text-slate-500 dark:border-white/10 dark:text-slate-400">
    {selectedGradeFilter === '全部' ? '暂无班级，展开上方新建卡片开始创建。' : `当前没有 ${selectedGradeFilter} 的班级。`}
  </div>
) : null}

{filteredClasses.map((item) => {
  // existing card rendering
})}
```

- [ ] **Step 6: Require a teacher selection before creating a new class and sync `teacher_name` from the chosen account**

```ts
const [newClassTeacherUserId, setNewClassTeacherUserId] = useState<number | null>(null);

if (classId === 'new' && newClassTeacherUserId === null) {
  setFormError('新建班级时必须选择负责老师');
  return;
}

const selectedTeacher = users.find((user) => user.id === newClassTeacherUserId) || null;
const payload = {
  name: normalizeClassNameInput(currentForm.name),
  subject: currentForm.subject.trim(),
  grade: currentForm.grade.trim(),
  teacher_name: selectedTeacher?.name || '',
  teacher_email: '',
};
```

After class creation:

```ts
const created = await apiFetch<{ id: number; name: string }>('/api/classes', {
  method: 'POST',
  body: JSON.stringify(payload),
});

await apiFetch(`/api/classes/${created.id}/teacher`, {
  method: 'PUT',
  body: JSON.stringify({ teacher_user_id: newClassTeacherUserId }),
});
```

- [ ] **Step 7: Re-run the focused frontend tests until the new grade-filter and single-teacher assertions pass**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend && npx tsx --test src/workspace-navigation.test.ts src/account-card.test.tsx`

Expected: PASS with the grade-filter state, filtered list, single-teacher summary, and class-centric binding assertions all green.

- [ ] **Step 8: Commit the frontend part once the focused tests are green**

```bash
cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary
git add frontend/src/App.tsx frontend/src/account-card.test.tsx frontend/src/workspace-navigation.test.ts
git commit -m "feat: add grade filter to class management"
```

### Task 5: Final Verification, Handoff Update, And Delivery Commit

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/account-card.test.tsx`
- Modify: `frontend/src/workspace-navigation.test.ts`
- Modify: `app.py`
- Modify: `lesson_manager.py`
- Modify: `tests/test_account_flow.py`
- Modify: `handoff.md`

- [ ] **Step 1: Run backend regression after both backend and frontend work are merged locally**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary && /Users/ark.mini/Desktop/Xingrun-Review/.venv/bin/python -m unittest tests.test_account_flow -v`

Expected: PASS with the summary ending in `OK`.

- [ ] **Step 2: Run the focused frontend regression suite**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend && npx tsx --test src/workspace-navigation.test.ts src/account-card.test.tsx`

Expected: PASS with 0 failures.

- [ ] **Step 3: Run TypeScript check and build**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend && npm run lint`

Expected: `tsc --noEmit` exits 0.

Run: `cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend && npm run build`

Expected: Vite build succeeds. A chunk-size warning is acceptable if no hard error is introduced.

- [ ] **Step 4: Update handoff with the delivered behavior and verification proof**

```md
补充记录（2026-03-29，班级管理单老师 + 年级筛选实施）
- `班级管理` 已切换为每班单老师绑定，`teacher_name` 与绑定老师账号保持同步
- 班级卡片区新增具体年级筛选：`全部 / 一年级-六年级 / 初一-初三 / 高一-高三`
- 班级摘要不再显示多老师数量，改为显示当前老师
- 后端保留 `user_classes` 表，但通过 class-centric binding API 保证每班只有一条老师关系
- proof：backend account flow pass；frontend focused tests pass；lint pass；build pass
```

- [ ] **Step 5: Create the final delivery commit**

```bash
cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary
git add app.py lesson_manager.py frontend/src/App.tsx frontend/src/account-card.test.tsx frontend/src/workspace-navigation.test.ts tests/test_account_flow.py handoff.md
git commit -m "feat: enforce single teacher class management"
```

### Self-Review Checklist

- [ ] Plan covers both approved requirements: single teacher per class and specific-grade filtering.
- [ ] All touched files are explicitly listed.
- [ ] Commands are runnable from the current workspace and include expected outcomes.
- [ ] No placeholder sections remain.
- [ ] Backend plan keeps `user_classes` instead of forcing a schema migration.
- [ ] Frontend plan preserves existing request-version guard and interaction-lock patterns.