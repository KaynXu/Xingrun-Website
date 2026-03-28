# Account Approval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a database-backed account system where `Kayn` is the seeded highest-privilege owner, new users submit registration requests for `星润Starain`, only approved users can log in, and only logged-in users can access the backend.

**Architecture:** Keep the existing Flask + SQLite stack and add a focused account layer beside the lesson data. Move authentication from `config.json` tokens to database sessions, expose a small admin approval API, and wire the React app to current-user state so the new flows fit the existing visual language.

**Tech Stack:** Flask, SQLite, Python `unittest`, React 19, TypeScript, Vite, Tailwind CSS

---

### Task 1: Lock Down The Backend Contract With Failing Tests

**Files:**
- Create: `tests/test_account_flow.py`
- Modify: `requirements.txt`

- [ ] **Step 1: Write the failing integration tests**

```python
import json
import tempfile
import unittest
from pathlib import Path

import config_runtime
import lesson_manager
from app import app


class AccountFlowTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        lesson_manager.DB_PATH = self.base / "test.db"
        config_runtime.CFG_PATH = self.base / "config.json"
        config_runtime.write_file_config({})
        lesson_manager.init_db()
        self.client = app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_owner_seed_and_approval_flow(self):
        login = self.client.post("/api/login", json={"username": "Kayn", "password": "xingrun2026"})
        self.assertEqual(login.status_code, 200)

        submit = self.client.post("/api/register-request", json={
            "username": "teacher_a",
            "display_name": "Teacher A",
            "password": "secret123",
            "organization_name": "星润Starain",
        })
        self.assertEqual(submit.status_code, 201)

        pending_login = self.client.post("/api/login", json={"username": "teacher_a", "password": "secret123"})
        self.assertEqual(pending_login.status_code, 401)
```

- [ ] **Step 2: Run the targeted test to verify it fails**

Run: `python3 -m unittest tests.test_account_flow -v`

Expected: FAIL because the new register / approval behavior and `Kayn` login do not exist yet.

- [ ] **Step 3: Add test runner dependency only if needed**

```text
pytest is not required; keep the suite on stdlib unittest so no new dependency is needed.
```

- [ ] **Step 4: Re-run the test after the file exists**

Run: `python3 -m unittest tests.test_account_flow -v`

Expected: same failing assertions, proving the test is exercising missing behavior instead of import errors.

### Task 2: Implement Database-Backed Accounts And Approval APIs

**Files:**
- Create: `account_manager.py`
- Modify: `app.py`
- Modify: `lesson_manager.py`

- [ ] **Step 1: Add the account data model and bootstrap helpers**

```python
def init_account_db() -> None:
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS organizations (...);
            CREATE TABLE IF NOT EXISTS users (...);
            CREATE TABLE IF NOT EXISTS registration_requests (...);
            CREATE TABLE IF NOT EXISTS auth_sessions (...);
            """
        )
```

- [ ] **Step 2: Seed `星润Starain` and the `Kayn` owner account**

```python
def ensure_owner_account() -> None:
    password_hash = runtime_cfg.get("admin_password_hash") or hashlib.sha256("xingrun2026".encode()).hexdigest()
    upsert_owner(username="Kayn", display_name="Kayn", role="owner", organization_name="星润Starain", password_hash=password_hash)
```

- [ ] **Step 3: Replace config-file token auth with database sessions**

```python
def create_session(user_id: int) -> str:
    token = secrets.token_hex(32)
    ...
    return token
```

- [ ] **Step 4: Add public register-request and login endpoints**

```python
@app.route("/api/register-request", methods=["POST"])
def api_register_request():
    ...


@app.route("/api/login", methods=["POST"])
def api_login():
    ...
```

- [ ] **Step 5: Add authenticated `me` and owner-only approval endpoints**

```python
@app.route("/api/me", methods=["GET"])
def api_me():
    ...


@app.route("/api/admin/registration-requests", methods=["GET"])
def api_admin_registration_requests():
    ...
```

- [ ] **Step 6: Protect all backend-only APIs with authenticated users**

```python
def require_auth():
    user = get_current_user(request.headers.get("X-Auth-Token", ""))
    if not user:
        return jsonify({"error": "未授权"}), 401
```

- [ ] **Step 7: Run the test suite to verify the backend passes**

Run: `python3 -m unittest tests.test_account_flow -v`

Expected: PASS for seeded owner login, request submission, approval, and post-approval member login.

### Task 3: Wire The React App To Account State And Approval UI

**Files:**
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Add typed account models and current-user bootstrap**

```tsx
interface CurrentUser {
  id: number;
  username: string;
  display_name: string;
  role: 'owner' | 'member';
  organization_name: string;
}
```

- [ ] **Step 2: Update login handling to fetch `/api/me`**

```tsx
const bootstrapUser = async (token: string) => {
  localStorage.setItem('xr_token', token);
  const me = await apiFetch<CurrentUser>('/api/me');
  setCurrentUser(me);
};
```

- [ ] **Step 3: Add a registration-request modal matching the existing style**

```tsx
const RegisterRequestModal = (...) => {
  // username, display name, password, confirm password, organization display
};
```

- [ ] **Step 4: Add an owner-only approval page/card and dynamic sidebar identity**

```tsx
{currentUser?.role === 'owner' && <ApprovalPage currentUser={currentUser} />}
```

- [ ] **Step 5: Ensure unauthenticated visitors only see landing, login, and register-request flows**

```tsx
if (!token || !currentUser || showLanding) {
  return <LandingPage ... />;
}
```

- [ ] **Step 6: Run frontend typecheck**

Run: `npm --prefix frontend run lint`

Expected: exit 0.

### Task 4: Verify The Full Stack Behavior

**Files:**
- Modify: `README.md` only if runtime behavior needs user-facing notes

- [ ] **Step 1: Run backend account tests**

Run: `python3 -m unittest tests.test_account_flow -v`

Expected: all tests pass.

- [ ] **Step 2: Run frontend typecheck and production build**

Run: `npm --prefix frontend run lint`

Expected: exit 0.

Run: `npm --prefix frontend run build`

Expected: Vite production build succeeds.

- [ ] **Step 3: Manually verify the required product flows**

```text
1. Kayn can log in.
2. A new user can submit a registration request for 星润Starain.
3. Pending users cannot log in.
4. Kayn can approve or reject requests.
5. Approved users can log in and reach the backend.
6. Anonymous users cannot access backend data APIs.
```
