# Organization Scope And Account Admin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enforce per-organization data visibility across backend and frontend, migrate legacy records into `星润Starain`, expose registered organizations to the super owner, and let account approvers edit member display names.

**Architecture:** Add organization ownership to classes, lessons, and consultations at the data layer, then route all account, class, lesson, consultation, and summary queries through actor-scoped helpers. Keep the UI changes concentrated in `ApprovalPage`, with backend APIs remaining the real security boundary. Migrate legacy consultation CSV data into SQLite during schema init so older data lands in `星润Starain` once and future reads/writes stay scoped.

**Tech Stack:** Flask, SQLite, Python unittest, React, TypeScript, Vite test runner

---

### Task 1: Lock Down Organization Scoping With Failing Backend Tests

**Files:**
- Modify: `tests/test_account_flow.py`

- [ ] **Step 1: Write failing backend tests for organization-scoped visibility and profile editing**

Add test coverage for:

```python
def test_owner_only_sees_members_and_requests_from_own_organization(self):
    ...

def test_super_owner_can_list_registered_organizations(self):
    ...

def test_owner_can_update_member_display_name_in_own_organization(self):
    ...

def test_owner_cannot_update_member_display_name_in_other_organization(self):
    ...
```

- [ ] **Step 2: Run the targeted backend tests to verify they fail**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/.worktrees/feature-org-scope-and-account-admin && /Users/ark.mini/Desktop/Xingrun-Review/.venv/bin/python -m unittest tests.test_account_flow.AccountFlowTestCase.test_owner_only_sees_members_and_requests_from_own_organization tests.test_account_flow.AccountFlowTestCase.test_super_owner_can_list_registered_organizations tests.test_account_flow.AccountFlowTestCase.test_owner_can_update_member_display_name_in_own_organization tests.test_account_flow.AccountFlowTestCase.test_owner_cannot_update_member_display_name_in_other_organization`

Expected: FAIL because actor-scoped listing, organization listing, and display-name update endpoints do not exist yet.

- [ ] **Step 3: Commit the failing-test checkpoint**

```bash
git add tests/test_account_flow.py
git commit -m "test: cover org-scoped account admin behavior"
```

### Task 2: Add Organization Ownership Columns And Consultation Table Migration

**Files:**
- Modify: `lesson_manager.py`
- Test: `tests/test_account_flow.py`

- [ ] **Step 1: Add schema helpers for organization-owned classes, lessons, and consultations**

Implement schema upgrades in `lesson_manager.py` to:

```python
def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    ...

def _ensure_consultations_table(conn: sqlite3.Connection) -> None:
    ...

def _migrate_legacy_organization_scope(conn: sqlite3.Connection) -> None:
    ...
```

- [ ] **Step 2: Backfill legacy rows into `星润Starain`**

Backfill rules:

```python
starain = _ensure_organization(conn, DEFAULT_ORGANIZATION_NAME)
conn.execute("UPDATE classes SET organization_id=? WHERE organization_id IS NULL", (starain["id"],))
conn.execute("UPDATE lessons SET organization_id=? WHERE organization_id IS NULL", (starain["id"],))
```

For consultations, read legacy CSV rows once and insert them into SQLite with `organization_id=starain["id"]` when the new table is empty.

- [ ] **Step 3: Run the targeted backend tests again**

Run: same command from Task 1 Step 2

Expected: still FAIL, but now on missing scoped-query behavior rather than missing schema.

- [ ] **Step 4: Commit the migration groundwork**

```bash
git add lesson_manager.py
git commit -m "feat: add organization-owned core data migration"
```

### Task 3: Scope User, Request, Class, Lesson, Consultation, And Summary Queries By Actor

**Files:**
- Modify: `lesson_manager.py`
- Modify: `app.py`
- Modify: `master_data.py`
- Test: `tests/test_account_flow.py`

- [ ] **Step 1: Add actor-scoped data access helpers in `lesson_manager.py`**

Implement helpers shaped like:

```python
def list_users_for_actor(actor_user: dict) -> list[dict]:
    ...

def list_registration_requests_for_actor(actor_user: dict, status: str = "pending") -> list[dict]:
    ...

def list_organizations() -> list[dict]:
    ...

def actor_can_manage_user(actor_user: dict, target_user: dict) -> bool:
    ...
```

- [ ] **Step 2: Add scoped class, lesson, and consultation helpers**

Implement:

```python
def list_classes_for_actor(actor_user: dict) -> list[dict]:
    ...

def list_lessons_for_actor(actor_user: dict, month_str: str = "", class_id: int = 0) -> list[dict]:
    ...

def list_consultations_for_actor(actor_user: dict, query: str = "") -> list[dict]:
    ...
```

Use `organization_id` filtering for non-`super_owner` actors.

- [ ] **Step 3: Route Flask APIs through actor-scoped helpers**

Update `app.py` endpoints including:

```python
@app.route("/api/admin/users", methods=["GET"])
@app.route("/api/admin/registration-requests", methods=["GET"])
@app.route("/api/admin/organizations", methods=["GET"])
@app.route("/api/classes", methods=["GET"])
@app.route("/api/classes/<int:class_id>", methods=["GET"])
@app.route("/api/consultations", methods=["GET"])
@app.route("/api/consultations/<int:consultation_id>", methods=["GET"])
@app.route("/api/stats")
```

and ensure detail/write endpoints reject cross-organization access for non-`super_owner`.

- [ ] **Step 4: Make master-data summaries respect actor scope**

Add actor-aware filtering so member binding summaries and related account-admin summaries only include the current organization unless the actor is `super_owner`.

- [ ] **Step 5: Run the targeted backend tests and then the broader account flow suite**

Run:

```bash
cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/.worktrees/feature-org-scope-and-account-admin
/Users/ark.mini/Desktop/Xingrun-Review/.venv/bin/python -m unittest tests.test_account_flow.AccountFlowTestCase.test_owner_only_sees_members_and_requests_from_own_organization tests.test_account_flow.AccountFlowTestCase.test_super_owner_can_list_registered_organizations
/Users/ark.mini/Desktop/Xingrun-Review/.venv/bin/python -m unittest tests.test_account_flow
```

Expected: the new visibility tests pass; full account flow remains green.

- [ ] **Step 6: Commit scoped backend behavior**

```bash
git add lesson_manager.py app.py master_data.py tests/test_account_flow.py
git commit -m "feat: scope account and core data by organization"
```

### Task 4: Add Member Display-Name Editing APIs And UI

**Files:**
- Modify: `app.py`
- Modify: `lesson_manager.py`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/account-card.test.tsx`
- Modify: `frontend/src/organization-auth.test.tsx`
- Test: `tests/test_account_flow.py`

- [ ] **Step 1: Add failing frontend source assertions for organization list and display-name editing**

Add source-based tests that assert `ApprovalPage` contains:

```tsx
apiFetch<{ items: OrganizationSummaryItem[] }>('/api/admin/organizations')
apiFetch(`/api/admin/users/${userId}/profile`, { method: 'PUT', ... })
编辑姓名
已注册机构
```

- [ ] **Step 2: Add backend profile update endpoint**

Implement:

```python
@app.route("/api/admin/users/<int:user_id>/profile", methods=["PUT"])
def api_admin_user_profile_update():
    ...
```

and a matching `lesson_manager.py` helper that updates only `display_name` with actor permission checks.

- [ ] **Step 3: Add ApprovalPage UI for registered organizations and member name editing**

In `frontend/src/App.tsx`:

```tsx
const [organizations, setOrganizations] = useState<OrganizationSummaryItem[]>([]);
const [editingDisplayNameUserId, setEditingDisplayNameUserId] = useState<number | null>(null);
const [pendingDisplayName, setPendingDisplayName] = useState('');
```

Render:

- super-owner-only registered organization cards
- per-user `编辑姓名` action
- inline name edit field and save/cancel controls

- [ ] **Step 4: Run targeted frontend and backend tests**

Run:

```bash
cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/.worktrees/feature-org-scope-and-account-admin/frontend
npx tsx --test src/organization-auth.test.tsx src/account-card.test.tsx
cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/.worktrees/feature-org-scope-and-account-admin
/Users/ark.mini/Desktop/Xingrun-Review/.venv/bin/python -m unittest tests.test_account_flow.AccountFlowTestCase.test_owner_can_update_member_display_name_in_own_organization tests.test_account_flow.AccountFlowTestCase.test_owner_cannot_update_member_display_name_in_other_organization
```

Expected: PASS.

- [ ] **Step 5: Commit account admin UI and profile editing**

```bash
git add app.py lesson_manager.py frontend/src/App.tsx frontend/src/account-card.test.tsx frontend/src/organization-auth.test.tsx tests/test_account_flow.py
git commit -m "feat: add org-aware account admin tools"
```

### Task 5: Final Verification And Integration

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `app.py`
- Modify: `lesson_manager.py`
- Modify: `master_data.py`
- Modify: `tests/test_account_flow.py`
- Modify: `frontend/src/account-card.test.tsx`
- Modify: `frontend/src/organization-auth.test.tsx`

- [ ] **Step 1: Run final backend verification**

Run:

```bash
cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/.worktrees/feature-org-scope-and-account-admin
/Users/ark.mini/Desktop/Xingrun-Review/.venv/bin/python -m unittest tests.test_account_flow
```

- [ ] **Step 2: Run final frontend verification**

Run:

```bash
cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/.worktrees/feature-org-scope-and-account-admin/frontend
npx tsx --test src/organization-auth.test.tsx src/account-card.test.tsx src/workspace-navigation.test.ts
npm run build
```

- [ ] **Step 3: Review diff before merge**

```bash
git status --short
git diff --stat master...HEAD
```

- [ ] **Step 4: Commit any final integration fixups**

```bash
git add <final files>
git commit -m "fix: finalize organization scoping integration"
```
