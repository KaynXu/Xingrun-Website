# Organization Application And Invite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the hard-coded `星润Starain` public registration flow with institution creation requests plus single-active invite code / invite link joining.

**Architecture:** Keep the existing Flask + SQLite account system, extend it with two new persistence models (`organization_requests`, `organization_invites`), and keep the seeded `Kayn` super-owner flow intact. Public entry moves from `/api/register-request` to two new flows: institution application and join-by-invite, while institution owners get invite management in the existing React workspace shell.

**Tech Stack:** Flask, SQLite, Python `unittest`, React 19, TypeScript, Vite, `tsx --test`

---

## File Structure

- Modify: `app.py`
  - Add institution request, invite lookup, join-by-invite, and invite reset endpoints.
- Modify: `lesson_manager.py`
  - Add schema changes, invite generation helpers, institution request persistence, and join/reset business logic.
- Modify: `tests/test_account_flow.py`
  - Cover institution application approval, owner bootstrap, join-by-code, join-by-link, and invite reset invalidation.
- Modify: `frontend/src/App.tsx`
  - Replace the current register modal with institution application and join-by-invite flows, and add admin/owner workspace panels.
- Modify: `frontend/src/account-card.test.tsx`
  - Assert the public shell exposes the two new entry points and the owner invite management strings.

### Task 1: Backend Institution Application And Invite APIs

**Files:**
- Modify: `tests/test_account_flow.py`
- Modify: `lesson_manager.py`
- Modify: `app.py`

- [ ] **Step 1: Write the failing backend tests**

```python
    def test_super_owner_approves_organization_request_and_bootstraps_owner_and_invite(self):
        owner_login = self.client.post(
            "/api/login",
            json={"username": "Kayn", "password": "xingrun2026"},
        )
        kayn_token = owner_login.get_json()["token"]

        submit = self.client.post(
            "/api/organization-requests",
            json={
                "organization_name": "北辰实验学校",
                "username": "beichen_owner",
                "display_name": "北辰校长",
                "password": "secret123",
            },
        )
        self.assertEqual(submit.status_code, 201)

        pending = self.client.get(
            "/api/admin/organization-requests",
            headers=self.auth_headers(kayn_token),
        )
        self.assertEqual(pending.status_code, 200)
        request_id = pending.get_json()["items"][0]["id"]

        approve = self.client.post(
            f"/api/admin/organization-requests/{request_id}/approve",
            headers=self.auth_headers(kayn_token),
        )
        self.assertEqual(approve.status_code, 200)
        approved_user = approve.get_json()["user"]
        self.assertEqual(approved_user["role"], "owner")
        self.assertEqual(approved_user["organization_name"], "北辰实验学校")

        owner_login = self.client.post(
            "/api/login",
            json={"username": "beichen_owner", "password": "secret123"},
        )
        self.assertEqual(owner_login.status_code, 200)
        owner_token = owner_login.get_json()["token"]

        invite = self.client.get(
            "/api/organization/invite",
            headers=self.auth_headers(owner_token),
        )
        self.assertEqual(invite.status_code, 200)
        payload = invite.get_json()
        self.assertEqual(payload["organization_name"], "北辰实验学校")
        self.assertTrue(payload["invite_code"])
        self.assertTrue(payload["invite_link"])
```

```python
    def test_members_can_join_by_invite_code_and_old_invites_fail_after_reset(self):
        kayn_login = self.client.post(
            "/api/login",
            json={"username": "Kayn", "password": "xingrun2026"},
        )
        kayn_token = kayn_login.get_json()["token"]

        submit = self.client.post(
            "/api/organization-requests",
            json={
                "organization_name": "星河中学",
                "username": "xinghe_owner",
                "display_name": "星河负责人",
                "password": "ownerpass123",
            },
        )
        request_id = submit.get_json()["id"]
        self.client.post(
            f"/api/admin/organization-requests/{request_id}/approve",
            headers=self.auth_headers(kayn_token),
        )

        owner_login = self.client.post(
            "/api/login",
            json={"username": "xinghe_owner", "password": "ownerpass123"},
        )
        owner_token = owner_login.get_json()["token"]
        invite_payload = self.client.get(
            "/api/organization/invite",
            headers=self.auth_headers(owner_token),
        ).get_json()

        join = self.client.post(
            "/api/join-by-invite-code",
            json={
                "invite_code": invite_payload["invite_code"],
                "username": "teacher_joined",
                "display_name": "Teacher Joined",
                "password": "joinpass123",
            },
        )
        self.assertEqual(join.status_code, 201)
        self.assertEqual(join.get_json()["user"]["organization_name"], "星河中学")

        reset = self.client.post(
            "/api/organization/invite/reset",
            headers=self.auth_headers(owner_token),
        )
        self.assertEqual(reset.status_code, 200)

        stale_join = self.client.post(
            "/api/join-by-invite-code",
            json={
                "invite_code": invite_payload["invite_code"],
                "username": "teacher_old_code",
                "display_name": "Teacher Old Code",
                "password": "joinpass123",
            },
        )
        self.assertEqual(stale_join.status_code, 404)
```

- [ ] **Step 2: Run the backend tests to verify they fail for the right reason**

Run: `python -m unittest tests.test_account_flow.AccountFlowTestCase.test_super_owner_approves_organization_request_and_bootstraps_owner_and_invite tests.test_account_flow.AccountFlowTestCase.test_members_can_join_by_invite_code_and_old_invites_fail_after_reset -v`

Expected: FAIL with `404` or missing route / missing storage assertions because the new institution request and invite endpoints do not exist yet.

- [ ] **Step 3: Write the minimal backend implementation**

```python
# lesson_manager.py
def create_organization_request(organization_name: str, username: str, display_name: str, password: str):
    normalized_username = _normalize_username(username)
    organization_name = organization_name.strip()
    if not organization_name:
        raise ValueError("organization name required")
    with get_conn() as conn:
        _ensure_organization_request_tables(conn)
        if _organization_exists(conn, organization_name) or _pending_organization_request_exists(conn, organization_name):
            raise ValueError("organization already exists")
        if _is_owner_username(normalized_username) or _user_exists_with_username(conn, normalized_username):
            raise ValueError("username already exists")
        if _pending_registration_exists(conn, normalized_username) or _pending_organization_request_username_exists(conn, normalized_username):
            raise ValueError("username already pending")
        cur = conn.execute(
            """
            INSERT INTO organization_requests (organization_name, username, password_hash, display_name, status)
            VALUES (?, ?, ?, ?, 'pending')
            """,
            (organization_name, normalized_username, hash_password(password), display_name),
        )
        row = conn.execute("SELECT * FROM organization_requests WHERE id=?", (cur.lastrowid,)).fetchone()
    return dict(row)

def approve_organization_request(request_id: int, reviewer_id: int):
    with get_conn() as conn:
        req = conn.execute("SELECT * FROM organization_requests WHERE id=?", (request_id,)).fetchone()
        if not req or req["status"] != "pending":
            raise LookupError("organization request not found")
        org = _ensure_organization(conn, req["organization_name"])
        cur = conn.execute(
            """
            INSERT INTO users (username, password_hash, display_name, role, status, organization_id)
            VALUES (?, ?, ?, ?, 'active', ?)
            """,
            (req["username"], req["password_hash"], req["display_name"], OWNER_ROLE, org["id"]),
        )
        _revoke_active_invites(conn, org["id"])
        invite = _create_organization_invite(conn, org["id"], reviewer_id)
        conn.execute(
            """
            UPDATE organization_requests
            SET status='approved', reviewed_by=?, reviewed_at=datetime('now','localtime')
            WHERE id=?
            """,
            (reviewer_id, request_id),
        )
        user_row = _fetch_user_row_by_id(conn, cur.lastrowid)
    return _public_user_dict(user_row), invite
```

```python
# app.py
@app.route("/api/organization-requests", methods=["POST"])
def api_organization_requests_create():
    data = request.json or {}
    try:
        item = create_organization_request(
            organization_name=(data.get("organization_name") or "").strip(),
            username=(data.get("username") or "").strip(),
            display_name=(data.get("display_name") or "").strip(),
            password=(data.get("password") or "").strip(),
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 409
    return jsonify({"id": item["id"], "status": item["status"]}), 201

@app.route("/api/join-by-invite-code", methods=["POST"])
def api_join_by_invite_code():
    data = request.json or {}
    try:
        user = join_organization_by_invite_code(
            invite_code=(data.get("invite_code") or "").strip(),
            username=(data.get("username") or "").strip(),
            display_name=(data.get("display_name") or "").strip(),
            password=(data.get("password") or "").strip(),
        )
    except LookupError as exc:
        return jsonify({"error": str(exc)}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 409
    return jsonify({"user": user}), 201
```

- [ ] **Step 4: Run the backend tests to verify they pass**

Run: `python -m unittest tests.test_account_flow -v`

Expected: PASS for the new institution request / invite tests, with the existing account flow tests updated to the new behavior where necessary.

- [ ] **Step 5: Commit**

```bash
git add tests/test_account_flow.py lesson_manager.py app.py
git commit -m "feat: add institution application and invite APIs"
```

### Task 2: Frontend Public Entry Points And Invite Join UX

**Files:**
- Modify: `frontend/src/account-card.test.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Write the failing frontend tests**

```tsx
test('public shell source replaces the default 星润 register flow with institution apply and invite join actions', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');

  assert.match(source, /申请开通机构/);
  assert.match(source, /加入已有机构/);
  assert.doesNotMatch(source, /所有新账号默认加入机构 星润Starain/);
  assert.doesNotMatch(source, /organization_name:\s*'星润Starain'/);
  assert.match(source, /\/api\/organization-requests/);
  assert.match(source, /\/api\/join-by-invite-code/);
});

test('workspace source exposes institution invite management for owners', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');

  assert.match(source, /机构邀请设置/);
  assert.match(source, /当前邀请码/);
  assert.match(source, /邀请链接/);
  assert.match(source, /重置邀请码/);
  assert.match(source, /\/api\/organization\/invite/);
  assert.match(source, /\/api\/organization\/invite\/reset/);
});
```

- [ ] **Step 2: Run the frontend tests to verify they fail**

Run: `npm test -- account-card.test.tsx`

Workdir: `c:\Users\Administrator\Desktop\1\Xingrun-Summary\frontend`

Expected: FAIL because `App.tsx` still renders the single register-request modal and hard-coded `星润Starain` registration payload.

- [ ] **Step 3: Write the minimal frontend implementation**

```tsx
type OrganizationInviteInfo = {
  organization_name: string;
  invite_code: string;
  invite_link: string;
};

const OrganizationApplyModal = ({ onClose }: { onClose: () => void }) => {
  // organization_name + username + display_name + password + confirmPassword
  // submit POST /api/organization-requests
};

const JoinOrganizationModal = ({ onClose }: { onClose: () => void }) => {
  // invite_code + username + display_name + password + confirmPassword
  // submit POST /api/join-by-invite-code
};

const InviteManagementCard = ({ currentUser }: { currentUser: User }) => {
  const [inviteInfo, setInviteInfo] = useState<OrganizationInviteInfo | null>(null);

  useEffect(() => {
    if (currentUser.role === 'owner') {
      apiFetch<OrganizationInviteInfo>('/api/organization/invite').then(setInviteInfo);
    }
  }, [currentUser.role]);

  const handleResetInvite = async () => {
    const next = await apiFetch<OrganizationInviteInfo>('/api/organization/invite/reset', { method: 'POST' });
    setInviteInfo(next);
  };

  return inviteInfo ? (
    <section className={`${workspaceCardClass} p-6`}>
      <h4 className="text-xl font-semibold text-slate-900 dark:text-white">机构邀请设置</h4>
      <p className="mt-4 text-sm text-slate-500 dark:text-slate-400">当前邀请码</p>
      <p className="mt-1 text-lg font-semibold text-slate-900 dark:text-white">{inviteInfo.invite_code}</p>
      <p className="mt-4 text-sm text-slate-500 dark:text-slate-400">邀请链接</p>
      <p className="mt-1 break-all text-slate-700 dark:text-slate-200">{inviteInfo.invite_link}</p>
      <button onClick={() => void handleResetInvite()} className={workspaceSecondaryButtonClass}>重置邀请码</button>
    </section>
  ) : null;
};
```

- [ ] **Step 4: Run the frontend tests to verify they pass**

Run: `npm test -- account-card.test.tsx`

Workdir: `c:\Users\Administrator\Desktop\1\Xingrun-Summary\frontend`

Expected: PASS with the new public entry points and owner invite management strings present in `App.tsx`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/account-card.test.tsx frontend/src/App.tsx
git commit -m "feat: add institution application and invite join UI"
```

### Task 3: Frontend Admin Institution Review Panel

**Files:**
- Modify: `frontend/src/account-card.test.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Write the failing admin UI test**

```tsx
test('workspace source adds a super-owner institution request review panel', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');

  assert.match(source, /机构开通审批/);
  assert.match(source, /\/api\/admin\/organization-requests/);
  assert.match(source, /\/api\/admin\/organization-requests\/\$\{item\.id\}\/approve/);
  assert.match(source, /\/api\/admin\/organization-requests\/\$\{item\.id\}\/reject/);
});
```

- [ ] **Step 2: Run the targeted frontend test to verify it fails**

Run: `npm test -- account-card.test.tsx`

Workdir: `c:\Users\Administrator\Desktop\1\Xingrun-Summary\frontend`

Expected: FAIL because the approval page only manages member registration requests today.

- [ ] **Step 3: Write the minimal admin panel implementation**

```tsx
type OrganizationRequestItem = {
  id: number;
  organization_name: string;
  username: string;
  display_name: string;
  status: string;
  created_at: string;
};

const ApprovalPage = ({ currentUser }: { currentUser: User }) => {
  const [organizationRequests, setOrganizationRequests] = useState<OrganizationRequestItem[]>([]);

  const loadOrganizationRequests = useCallback(async () => {
    if (currentUser.role !== 'super_owner') return;
    const payload = await apiFetch<{ items: OrganizationRequestItem[] }>('/api/admin/organization-requests');
    setOrganizationRequests(payload.items);
  }, [currentUser.role]);

  const handleOrganizationDecision = async (item: OrganizationRequestItem, action: 'approve' | 'reject') => {
    await apiFetch(`/api/admin/organization-requests/${item.id}/${action}`, { method: 'POST' });
    await loadOrganizationRequests();
  };

  // render the existing member approval section plus a super-owner-only institution review card
};
```

- [ ] **Step 4: Run the frontend tests to verify they pass**

Run: `npm test -- account-card.test.tsx`

Workdir: `c:\Users\Administrator\Desktop\1\Xingrun-Summary\frontend`

Expected: PASS with the super-owner institution review strings and routes present.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/account-card.test.tsx frontend/src/App.tsx
git commit -m "feat: add institution review workspace panel"
```

## Self-Review

- Spec coverage:
  - Institution application: Task 1 backend + Task 2 public modal
  - `Kayn` approval and owner bootstrap: Task 1 backend + Task 3 workspace UI
  - Single active invite and reset invalidation: Task 1 backend + Task 2 owner UI
  - Removal of hard-coded `星润Starain` public registration: Task 2
- Placeholder scan:
  - No `TODO`, `TBD`, or “implement later” placeholders remain in tasks.
- Type consistency:
  - Backend uses `organization_requests`, `organization_invites`, `OrganizationInviteInfo`, and `OrganizationRequestItem` consistently across tasks.
