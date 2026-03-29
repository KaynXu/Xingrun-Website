# Class Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a dedicated `班级管理` workspace tab where `owner` and `admin` can both manage classes and assign class access, while `账号审批` returns to approval-focused responsibilities.

**Architecture:** Keep the existing Flask + SQLite backend and React single-file workspace shell, but tighten role guards around class-management APIs and move class-assignment state out of `ApprovalPage` into a dedicated `ClassManagementPage`. Reuse the current class model, `user_classes` join table, and workspace visual primitives so the new tab fits the existing app without introducing a second admin system.

**Tech Stack:** Flask, SQLite, Python `unittest`, React 19, TypeScript, Vite, Tailwind CSS

---

### Task 1: Lock Down The Backend Role Contract With Failing Tests

**Files:**
- Modify: `tests/test_account_flow.py`

- [ ] **Step 1: Expand the test fixture with approval helpers and a class-management scenario**

```python
class AccountFlowTestCase(unittest.TestCase):
  def setUp(self):
    self.temp_dir = tempfile.TemporaryDirectory()
    self.base = Path(self.temp_dir.name)
    lesson_manager.DB_PATH = self.base / "lessons.db"
    config_runtime.CFG_PATH = self.base / "config.json"
    config_runtime.write_file_config({})
    lesson_manager.init_db()
    self.client = app.test_client()

    def approve_user(self, owner_token: str, username: str, display_name: str, password: str) -> dict:
        submit = self.client.post(
            "/api/register-request",
            json={
                "username": username,
                "display_name": display_name,
                "password": password,
                "organization_name": "星润Starain",
            },
        )
        self.assertEqual(submit.status_code, 201)

        pending = self.client.get(
            "/api/admin/registration-requests",
            headers=self.auth_headers(owner_token),
        )
        item = next(row for row in pending.get_json()["items"] if row["username"] == username)
        approve = self.client.post(
            f"/api/admin/registration-requests/{item['id']}/approve",
            headers=self.auth_headers(owner_token),
        )
        self.assertEqual(approve.status_code, 200)

        login = self.client.post("/api/login", json={"username": username, "password": password})
        self.assertEqual(login.status_code, 200)
        return login.get_json()

    def test_admin_can_manage_classes_and_assign_member_assignments(self):
        owner_login = self.client.post(
            "/api/login",
            json={"username": "Kayn", "password": "xingrun2026"},
        )
        owner_token = owner_login.get_json()["token"]

        admin_login = self.approve_user(owner_token, "admin_a", "Admin A", "secret123")
        admin_user = admin_login["user"]
        admin_token = admin_login["token"]

        promote = self.client.put(
            f"/api/admin/users/{admin_user['id']}/role",
            json={"role": "admin"},
            headers=self.auth_headers(owner_token),
        )
        self.assertEqual(promote.status_code, 200)

        member_login = self.approve_user(owner_token, "member_a", "Member A", "secret123")
        member_user = member_login["user"]

        create_class = self.client.post(
            "/api/classes",
            json={"name": "六年级数学冲刺班", "subject": "数学", "grade": "六年级"},
            headers=self.auth_headers(admin_token),
        )
        self.assertEqual(create_class.status_code, 201)
        class_id = create_class.get_json()["id"]

        assign = self.client.put(
            f"/api/admin/users/{member_user['id']}/classes",
            json={"class_ids": [class_id]},
            headers=self.auth_headers(admin_token),
        )
        self.assertEqual(assign.status_code, 200)

        assigned = self.client.get(
            f"/api/admin/users/{member_user['id']}/classes",
            headers=self.auth_headers(admin_token),
        )
        self.assertEqual(assigned.status_code, 200)
        self.assertEqual(assigned.get_json()["class_ids"], [class_id])

        admin_pending = self.client.get(
            "/api/admin/registration-requests",
            headers=self.auth_headers(admin_token),
        )
        self.assertEqual(admin_pending.status_code, 403)

        admin_promote = self.client.put(
            f"/api/admin/users/{member_user['id']}/role",
            json={"role": "admin"},
            headers=self.auth_headers(admin_token),
        )
        self.assertEqual(admin_promote.status_code, 403)

    def test_member_cannot_write_class_management_apis(self):
        owner_login = self.client.post(
            "/api/login",
            json={"username": "Kayn", "password": "xingrun2026"},
        )
        owner_token = owner_login.get_json()["token"]
        member_login = self.approve_user(owner_token, "member_b", "Member B", "secret123")
        member_token = member_login["token"]

        create_class = self.client.post(
            "/api/classes",
            json={"name": "测试班级"},
            headers=self.auth_headers(member_token),
        )
        self.assertEqual(create_class.status_code, 403)

        users = self.client.get(
            "/api/admin/users",
            headers=self.auth_headers(member_token),
        )
        self.assertEqual(users.status_code, 403)
```

- [ ] **Step 2: Run the targeted backend suite to verify the new tests fail for the right reason**

Run: `python3 -m unittest tests.test_account_flow -v`

Expected: FAIL because `admin` is still blocked from `/api/admin/users` and `/api/admin/users/<id>/classes`, while `member` can still write `/api/classes`.

- [ ] **Step 3: Re-run once after fixing any test typo until the failure is behavior-level**

Run: `python3 -m unittest tests.test_account_flow -v`

Expected: same failing assertions, not import errors or malformed fixture errors.

- [ ] **Step 4: Commit the red test state only if your workflow requires it; otherwise keep working tree local**

```bash
git add tests/test_account_flow.py
# Optional in strict red/green workflows; most teams can skip this commit and continue locally.
```

### Task 2: Implement Staff-Only Class Management And Clean Class Deletion Semantics

**Files:**
- Modify: `app.py`
- Modify: `lesson_manager.py`
- Test: `tests/test_account_flow.py`

- [ ] **Step 1: Add a reusable `owner or admin` auth helper in the Flask API layer**

```python
def _require_staff():
    user, error = _require_auth()
    if error:
        return None, error
    if user.get("role") not in {"owner", "admin"}:
        return None, (jsonify({"error": "无权限"}), 403)
    return user, None
```

- [ ] **Step 2: Tighten class CRUD endpoints so only staff can write classes**

```python
@app.route("/api/classes", methods=["POST"])
def api_class_create():
    _, error = _require_staff()
    if error:
        return error
  data = request.json or {}
  name = (data.get("name") or "").strip()
  if not name:
    return jsonify({"error": "班级名称不能为空"}), 400
  cid = save_class(
    name=name,
    subject=data.get("subject", "").strip(),
    grade=data.get("grade", "").strip(),
    teacher_name=data.get("teacher_name", "").strip(),
    teacher_email=data.get("teacher_email", "").strip(),
  )
  return jsonify({"id": cid, "name": name}), 201


@app.route("/api/classes/<int:class_id>", methods=["PUT"])
def api_class_update(class_id):
    _, error = _require_staff()
    if error:
        return error
  cls = get_class(class_id)
  if not cls:
    return jsonify({"error": "not found"}), 404
  data = request.json or {}
  name = (data.get("name") or "").strip()
  if not name:
    return jsonify({"error": "班级名称不能为空"}), 400
  update_class(
    class_id=class_id,
    name=name,
    subject=data.get("subject", "").strip(),
    grade=data.get("grade", "").strip(),
    teacher_name=data.get("teacher_name", "").strip(),
    teacher_email=data.get("teacher_email", "").strip(),
  )
  return jsonify({"ok": True})


@app.route("/api/classes/<int:class_id>", methods=["DELETE"])
def api_class_delete(class_id):
    _, error = _require_staff()
    if error:
        return error
  cls = get_class(class_id)
  if not cls:
    return jsonify({"error": "not found"}), 404
  db_delete_class(class_id)
  return jsonify({"ok": True})
```

- [ ] **Step 3: Allow `admin` to access member lists and class assignments, but keep role changes owner-only**

```python
@app.route("/api/admin/users", methods=["GET"])
def api_admin_users():
    _, error = _require_staff()
    if error:
        return error
    users = list_all_users()
    return jsonify([
        {"id": u["id"], "name": u["display_name"], "org": u["organization_name"], "role": u["role"]}
        for u in users
    ])


@app.route("/api/admin/users/<int:user_id>/classes", methods=["PUT"])
def api_admin_user_classes_set(user_id):
    _, error = _require_staff()
    if error:
        return error
    data = request.json or {}
    set_user_class_ids(user_id, data.get("class_ids", []))
    return jsonify({"ok": True})
```

- [ ] **Step 4: Remove dangling class assignments when a class is deleted**

```python
def delete_class(class_id: int):
    with get_conn() as conn:
        conn.execute("UPDATE lessons SET class_id=NULL WHERE class_id=?", (class_id,))
        conn.execute("DELETE FROM user_classes WHERE class_id=?", (class_id,))
        conn.execute("DELETE FROM classes WHERE id=?", (class_id,))
```

- [ ] **Step 5: Run the backend suite to verify the permission contract now passes**

Run: `python3 -m unittest tests.test_account_flow -v`

Expected: PASS for owner seeding, admin class management, admin class assignment, and member denial cases.

- [ ] **Step 6: Commit the backend permission slice**

```bash
git add app.py lesson_manager.py tests/test_account_flow.py
git commit -m "feat: allow admins to manage classes and assignments"
```

### Task 3: Lock Down Workspace Navigation And Page Ownership With Failing Frontend Tests

**Files:**
- Modify: `frontend/src/workspace-navigation.test.ts`
- Modify: `frontend/src/account-card.test.tsx`

- [ ] **Step 1: Add source-level navigation assertions for the new `班级管理` tab**

```ts
test('workspace navigation adds a class management tab for owner and admin only', () => {
  assert.match(appSource, /type Page = 'dashboard' \| 'input' \| 'library' \| 'consultation' \| 'calendar' \| 'classes' \| 'accounts' \| 'settings';/);
  assert.match(appSource, /currentUser\.role === 'owner' \|\| currentUser\.role === 'admin'/);
  assert.match(appSource, /id: 'classes'[\s\S]*label: '班级管理'/);
  assert.match(appSource, /classes: '班级管理'/);
  assert.match(appSource, /activePage === 'classes'[\s\S]*<ClassManagementPage currentUser=\{currentUser\}/);
});
```

- [ ] **Step 2: Replace the old approval-page expectation so tests enforce the page split**

```ts
test('approval page source no longer renders class assignment controls', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');

  assert.match(source, /账号审批/);
  assert.doesNotMatch(source, /ApprovalPage[\s\S]*班级分配/);
  assert.match(source, /ClassManagementPage[\s\S]*成员班级分配/);
  assert.doesNotMatch(source, /ClassManagementPage[\s\S]*升为管理员/);
});
```

- [ ] **Step 3: Run the focused frontend tests to confirm they fail before implementation**

Run: `cd frontend && npx tsx --test src/workspace-navigation.test.ts src/account-card.test.tsx`

Expected: FAIL because `Page` does not include `classes`, the nav item is missing, and `ApprovalPage` still contains `班级分配`.

- [ ] **Step 4: Re-run after fixing any broken regex so the failures are only about missing product behavior**

Run: `cd frontend && npx tsx --test src/workspace-navigation.test.ts src/account-card.test.tsx`

Expected: same behavior-level failures, not syntax or regex parse errors.

### Task 4: Add The `班级管理` Tab And Move Class Assignment Out Of `ApprovalPage`

**Files:**
- Modify: `frontend/src/App.tsx`
- Test: `frontend/src/workspace-navigation.test.ts`
- Test: `frontend/src/account-card.test.tsx`

- [ ] **Step 1: Extend the page union, nav label map, and active-page fallback logic**

```tsx
type Page = 'dashboard' | 'input' | 'library' | 'consultation' | 'calendar' | 'classes' | 'accounts' | 'settings';

const navItems = [
  { id: 'dashboard', icon: LayoutDashboard, label: '数据看板' },
  { id: 'input', icon: PlusCircle, label: '添加课程' },
  { id: 'library', icon: Library, label: '课程资料库' },
  { id: 'consultation', icon: MessageSquare, label: '咨询记录' },
  { id: 'calendar', icon: CalendarDays, label: '课程日历' },
  ...((currentUser.role === 'owner' || currentUser.role === 'admin')
    ? [{ id: 'classes', icon: Database, label: '班级管理' }]
    : []),
  ...(currentUser.role === 'owner' ? [{ id: 'accounts', icon: User, label: '账号审批' }] : []),
  { id: 'settings', icon: Settings, label: '系统设置' },
];

setActivePage((page) => {
  if (page === 'accounts' && user.role !== 'owner') return 'dashboard';
  if (page === 'classes' && user.role !== 'owner' && user.role !== 'admin') return 'dashboard';
  return page;
});
```

- [ ] **Step 2: Create a dedicated `ClassManagementPage` shell in `App.tsx` using existing workspace card styles**

```tsx
const ClassManagementPage = ({ currentUser }: { currentUser: CurrentUser }) => {
  return (
    <div className={`${workspacePageClass} space-y-8`}>
      <section className={`${workspaceCardClass} p-6`}>
        <div>
          <p className="text-sm uppercase tracking-[0.25em] text-sky-600">Class Management</p>
          <h3 className="mt-3 text-2xl font-bold text-slate-900 dark:text-white">班级管理</h3>
          <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">维护班级资料，并为机构成员配置可访问班级。</p>
        </div>
      </section>

      <section className={`${workspaceCardClass} p-6`}>
        <h4 className="text-xl font-semibold text-slate-900 dark:text-white">班级列表</h4>
      </section>

      <section className={`${workspaceCardClass} p-6`}>
        <h4 className="text-xl font-semibold text-slate-900 dark:text-white">成员班级分配</h4>
      </section>
    </div>
  );
};
```

- [ ] **Step 3: Strip assignment state and assignment markup out of `ApprovalPage`**

```tsx
const ApprovalPage = ({ currentUser }: { currentUser: CurrentUser }) => {
  const [items, setItems] = useState<RegistrationRequestItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actingId, setActingId] = useState<number | null>(null);
  const [users, setUsers] = useState<UserItem[]>([]);
  const [changingRoleId, setChangingRoleId] = useState<number | null>(null);

  useEffect(() => {
    loadItems().catch(() => undefined);
    apiFetch<UserItem[]>('/api/admin/users').then(setUsers).catch(() => undefined);
  }, [loadItems]);

  const handleRoleChange = async (userId: number, newRole: 'admin' | 'member') => {
    setChangingRoleId(userId);
    setError('');
    try {
      await apiFetch(`/api/admin/users/${userId}/role`, {
        method: 'PUT',
        body: JSON.stringify({ role: newRole }),
      });
      setUsers((current) => current.map((user) => (user.id === userId ? { ...user, role: newRole } : user)));
    } catch (err) {
      setError(err instanceof Error ? err.message : '权限修改失败');
    } finally {
      setChangingRoleId(null);
    }
  };

  return (
    <div className={`${workspacePageClass} space-y-8`}>
      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,320px)_minmax(0,1fr)] gap-6">
        <section className={`${workspaceCardClass} space-y-5 p-6`}>
          <div>
            <p className="text-sm uppercase tracking-[0.25em] text-sky-600">Owner</p>
            <h3 className="mt-3 text-2xl font-bold text-slate-900 dark:text-white">账号审批</h3>
          </div>
        </section>
        <section className={`${workspaceCardClass} p-6`}>
          <h4 className="text-xl font-semibold text-slate-900 dark:text-white">待审批申请</h4>
        </section>
      </div>
    </div>
  );
};
```

- [ ] **Step 4: Render the new page in the workspace shell**

```tsx
{activePage === 'classes' && (currentUser.role === 'owner' || currentUser.role === 'admin') && (
  <ClassManagementPage currentUser={currentUser} />
)}
{activePage === 'accounts' && currentUser.role === 'owner' && <ApprovalPage currentUser={currentUser} />}
```

- [ ] **Step 5: Re-run the focused frontend tests to verify the shell rewire passes**

Run: `cd frontend && npx tsx --test src/workspace-navigation.test.ts src/account-card.test.tsx`

Expected: PASS for nav visibility, page routing, and removal of `班级分配` from `ApprovalPage`.

- [ ] **Step 6: Commit the page split before wiring data mutations**

```bash
git add frontend/src/App.tsx frontend/src/workspace-navigation.test.ts frontend/src/account-card.test.tsx
git commit -m "feat: add class management workspace tab"
```

### Task 5: Wire Class CRUD, Member Assignment, And Owner Role Controls To The New Layout

**Files:**
- Modify: `frontend/src/App.tsx`
- Test: `frontend/src/workspace-navigation.test.ts`
- Test: `frontend/src/account-card.test.tsx`
- Test: `tests/test_account_flow.py`

- [ ] **Step 1: Add class-management state loaders and a shared form model inside `ClassManagementPage`**

```tsx
const emptyClassForm = {
  name: '',
  subject: '',
  grade: '',
  teacher_name: '',
  teacher_email: '',
};

const [classes, setClasses] = useState<ClassItem[]>([]);
const [users, setUsers] = useState<UserItem[]>([]);
const [userClassIds, setUserClassIds] = useState<Record<number, number[]>>({});
const [selectedClassId, setSelectedClassId] = useState<number | null>(null);
const [form, setForm] = useState(emptyClassForm);
const [savingClass, setSavingClass] = useState(false);
const [deletingClass, setDeletingClass] = useState(false);
const [savingUserId, setSavingUserId] = useState<number | null>(null);
```

- [ ] **Step 2: Load classes, users, and class assignments with staff-only UI gating**

```tsx
const loadClassManagement = useCallback(async () => {
  const [classList, userList] = await Promise.all([
    apiFetch<ClassItem[]>('/api/classes'),
    apiFetch<UserItem[]>('/api/admin/users'),
  ]);
  setClasses(classList);
  setUsers(userList);

  const assignments = await Promise.all(
    userList.map((user) =>
      apiFetch<{ class_ids: number[] }>(`/api/admin/users/${user.id}/classes`).then((payload) => ({
        id: user.id,
        class_ids: payload.class_ids,
      })),
    ),
  );

  setUserClassIds(Object.fromEntries(assignments.map((row) => [row.id, row.class_ids])));
}, []);
```

- [ ] **Step 3: Implement create / update / delete handlers against the existing class APIs**

```tsx
const handleClassSave = async (event: React.FormEvent) => {
  event.preventDefault();
  setSavingClass(true);
  try {
    if (selectedClassId) {
      await apiFetch(`/api/classes/${selectedClassId}`, {
        method: 'PUT',
        body: JSON.stringify(form),
      });
    } else {
      await apiFetch('/api/classes', {
        method: 'POST',
        body: JSON.stringify(form),
      });
    }
    await loadClassManagement();
    setSelectedClassId(null);
    setForm(emptyClassForm);
  } finally {
    setSavingClass(false);
  }
};

const handleClassDelete = async () => {
  if (!selectedClassId || !window.confirm('确定删除当前班级吗？')) return;
  setDeletingClass(true);
  try {
    await apiFetch(`/api/classes/${selectedClassId}`, { method: 'DELETE' });
    await loadClassManagement();
    setSelectedClassId(null);
    setForm(emptyClassForm);
  } finally {
    setDeletingClass(false);
  }
};
```

- [ ] **Step 4: Implement per-user checkbox assignment with optimistic update and rollback**

```tsx
const handleClassToggle = async (userId: number, classId: number, checked: boolean) => {
  const prev = userClassIds[userId] ?? [];
  const next = checked ? [...prev, classId] : prev.filter((id) => id !== classId);
  setUserClassIds((current) => ({ ...current, [userId]: next }));
  setSavingUserId(userId);
  try {
    await apiFetch(`/api/admin/users/${userId}/classes`, {
      method: 'PUT',
      body: JSON.stringify({ class_ids: next }),
    });
  } catch (error) {
    setUserClassIds((current) => ({ ...current, [userId]: prev }));
    throw error;
  } finally {
    setSavingUserId(null);
  }
};
```

- [ ] **Step 5: Keep owner-only role toggles on the approval page in a separate member-permissions card**

```tsx
{currentUser.role === 'owner' && users.length > 0 && (
  <section className={`${workspaceCardClass} space-y-5 p-6`}>
    <div>
      <h4 className="text-xl font-semibold text-slate-900 dark:text-white">成员权限</h4>
      <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">仅最高权限账号可以调整管理员身份。</p>
    </div>
    {users.map((user) => (
      <div key={user.id} className={`${workspaceSoftCardClass} p-5`}>
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="font-semibold text-slate-900 dark:text-white">{user.name}</p>
            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{user.org}</p>
          </div>
          {user.role !== 'owner' && (
            <button
              disabled={changingRoleId === user.id}
              onClick={() => handleRoleChange(user.id, user.role === 'admin' ? 'member' : 'admin')}
              className="text-[11px] text-sky-600 hover:text-sky-500 disabled:opacity-50 dark:text-sky-400 dark:hover:text-sky-300"
            >
              {changingRoleId === user.id ? '处理中...' : user.role === 'admin' ? '降为成员' : '升为管理员'}
            </button>
          )}
        </div>
      </div>
    ))}
  </section>
)}
```

- [ ] **Step 6: Update frontend source assertions so they lock in the final layout and permissions**

```ts
assert.match(appSource, /ClassManagementPage[\s\S]*班级列表/);
assert.match(appSource, /ClassManagementPage[\s\S]*成员班级分配/);
assert.match(appSource, /apiFetch<ClassItem\[]>\('\/api\/classes'\)/);
assert.match(appSource, /apiFetch<UserItem\[]>\('\/api\/admin\/users'\)/);
assert.match(appSource, /apiFetch\(`\/api\/admin\/users\/\$\{userId\}\/classes`/);
assert.doesNotMatch(appSource, /ClassManagementPage[\s\S]*升为管理员/);
assert.match(appSource, /ApprovalPage[\s\S]*成员权限/);
```

- [ ] **Step 7: Run backend and focused frontend tests for the new data flow**

Run: `python3 -m unittest tests.test_account_flow -v`

Expected: PASS.

Run: `cd frontend && npx tsx --test src/workspace-navigation.test.ts src/account-card.test.tsx`

Expected: PASS.

- [ ] **Step 8: Commit the data-wired UI slice**

```bash
git add frontend/src/App.tsx frontend/src/workspace-navigation.test.ts frontend/src/account-card.test.tsx tests/test_account_flow.py
git commit -m "feat: move class management into dedicated workspace tab"
```

### Task 6: Run The Full Verification Suite And Capture The Release-Ready State

**Files:**
- Modify: `handoff.md` only if execution notes or follow-ups changed

- [ ] **Step 1: Run the backend regression suite**

Run: `python3 -m unittest tests.test_account_flow -v`

Expected: all account and class-management tests pass.

- [ ] **Step 2: Run the focused frontend tests plus static checks**

Run: `cd frontend && npx tsx --test src/workspace-navigation.test.ts src/account-card.test.tsx`

Expected: PASS.

Run: `cd frontend && npm run lint`

Expected: exit 0.

Run: `cd frontend && npm run build`

Expected: Vite production build succeeds.

- [ ] **Step 3: Manually verify the product behavior in the browser**

```text
1. owner sees both 账号审批 and 班级管理.
2. admin sees 班级管理 but not 账号审批.
3. member sees neither management entry.
4. owner and admin can create, edit, and delete classes.
5. owner and admin can assign classes to members.
6. ApprovalPage no longer contains 班级分配.
7. Owner can still change member roles from the owner-only permissions area.
```

- [ ] **Step 4: Commit any final polish or handoff-only notes**

```bash
git add handoff.md
git commit -m "docs: capture class management implementation handoff"
```