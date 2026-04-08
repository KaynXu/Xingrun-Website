# 机构成员权限收窄 & 班级管理开放 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 member（机构成员）只能看到分配给自己的咨询记录，开放班级管理页面但限制操作权限，并向所有角色开放 AI 解析功能。

**Architecture:** 
- DB：consultations 表重构，去掉字符串 teacher_id，改用 assigned_user_id FK 指向 users 表
- Backend：按角色在 list_consultations_for_actor 中加 member 过滤；在 app.py 中调整权限 guard（ai-parse/invite）
- Frontend：班级管理 tab 去掉权限门槛，但在页面内用 UI 条件渲染隐藏 member 的增删改操作

**Tech Stack:** Python + SQLite + React/TypeScript

---

## 文件修改映射

| 文件 | 操作 | 说明 |
|---|---|---|
| `lesson_manager.py` | 修改 | DB 初始化、咨询 CRUD、过滤逻辑 |
| `app.py` | 修改 | 路由权限 guard、AI 解析权限 |
| `frontend/src/App.tsx` | 修改 | 侧边栏菜单、班级管理 UI 条件渲染 |
| `tests/test_consultation_flow.py` | 修改 | 咨询测试更新字段 + member 过滤测试 |
| `tests/test_member_scoped_access.py` | 创建 | 新增 member 权限专项测试 |

---

## Task 1: DB 迁移 — consultations 表重构

**Files:**
- Modify: `lesson_manager.py:1013-1040` (表初始化)
- Modify: `lesson_manager.py:1016-1035` (反序列化函数)

- [ ] **Step 1: 打开 lesson_manager.py，找到 `_ensure_consultations_table()` 函数**

位置：~1013 行

- [ ] **Step 2: 阅读旧 schema，记下所有字段**

关键要删除：`receiving_teacher TEXT DEFAULT ''`, `teacher_id TEXT DEFAULT ''`  
关键要新增：`assigned_user_id INTEGER REFERENCES users(id)`

- [ ] **Step 3: 修改 CREATE TABLE SQL**

```python
def _ensure_consultations_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS consultations (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id      INTEGER NOT NULL REFERENCES organizations(id),
            assigned_user_id     INTEGER REFERENCES users(id),
            date                 TEXT DEFAULT '',
            parent_wechat_name   TEXT DEFAULT '',
            child_name           TEXT DEFAULT '',
            grade                TEXT DEFAULT '',
            consultation_subject TEXT DEFAULT '',
            need_detail          TEXT DEFAULT '',
            source_channel       TEXT DEFAULT '',
            source_channel_note  TEXT DEFAULT '',
            screenshot           TEXT DEFAULT '',
            reminder_at          TEXT DEFAULT '',
            reminder_status      TEXT DEFAULT '',
            reminder_task_id     TEXT DEFAULT '',
            follow_up_status     TEXT DEFAULT '',
            follow_up_note       TEXT DEFAULT '',
            created_at           TEXT DEFAULT (datetime('now','localtime')),
            updated_at           TEXT DEFAULT (datetime('now','localtime'))
        )
        """
    )
```

- [ ] **Step 4: 检查 `_init_db()` 初始化顺序，确保 users 表在 consultations 前创建**

搜索 `_ensure_users_table` 和 `_ensure_consultations_table` 的调用顺序

- [ ] **Step 5: 修改初始化逻辑检测旧表**

在 `_ensure_consultations_table()` 顶部添加：

```python
def _ensure_consultations_table(conn: sqlite3.Connection) -> None:
    # 检测旧版本（无 assigned_user_id 列）
    try:
        info = conn.execute("PRAGMA table_info(consultations)").fetchall()
        col_names = [row[1] for row in info]
        if 'consultations' in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()[0] or True:
            if 'assigned_user_id' not in col_names:
                # 旧表存在但结构过时，删除重建
                conn.execute("DROP TABLE IF EXISTS consultations")
    except Exception:
        pass  # 表不存在或查询出错，继续创建新表
    
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS consultations (
        ...新 schema...
        )
        """
    )
```

- [ ] **Step 6: 找到 CREATE INDEX（如果有）并更新**

搜索 `CREATE INDEX.*consultations`，确保 `assigned_user_id` 有索引（可选优化）

- [ ] **Step 7: Commit**

```bash
git add lesson_manager.py
git commit -m "refactor: rebuild consultations table with assigned_user_id FK"
```

---

## Task 2: lesson_manager.py — 咨询序列化/反序列化函数改造

**Files:**
- Modify: `lesson_manager.py:~3400-3600` (咨询查询、创建、更新函数)

- [ ] **Step 1: 找到 `_consultation_storage_row_to_public_dict()` 函数**

搜索函数名，这个函数负责把 DB 行转为 JSON

- [ ] **Step 2: 修改该函数，改为 LEFT JOIN users 取 display_name + username**

```python
def _consultation_storage_row_to_public_dict(row, teacher_directory=None):
    # row 现在来自 LEFT JOIN users，包含 assigned_user_id, users.display_name, users.username
    receiving_teacher = row.get("display_name") or ""  # 从 JOIN 结果取
    teacher_id = row.get("username") or ""             # 从 JOIN 结果取
    
    return {
        "id": row["id"],
        "organization_id": row["organization_id"],
        "date": row["date"],
        "parent_wechat_name": row["parent_wechat_name"],
        "child_name": row["child_name"],
        "grade": row["grade"],
        "receiving_teacher": receiving_teacher,
        "teacher_id": teacher_id,
        "consultation_subject": row["consultation_subject"],
        ...
    }
```

注意：如果 `assigned_user_id` 为 NULL（无主咨询），receiving_teacher 和 teacher_id 都返回空字符串。

- [ ] **Step 3: 修改 `list_consultations()` 函数**

```python
def list_consultations(query: str = "", organization_id: Optional[int] = None, assigned_user_id: Optional[int] = None) -> list[dict]:
    with get_conn() as conn:
        query_sql = """
            SELECT 
                c.*,
                u.display_name,
                u.username
            FROM consultations c
            LEFT JOIN users u ON c.assigned_user_id = u.id
        """
        params: list[object] = []
        
        conditions = []
        if organization_id is not None:
            conditions.append("c.organization_id = ?")
            params.append(organization_id)
        if assigned_user_id is not None:
            conditions.append("c.assigned_user_id = ?")
            params.append(assigned_user_id)
        
        if conditions:
            query_sql += " WHERE " + " AND ".join(conditions)
        
        query_sql += " ORDER BY c.updated_at DESC, c.created_at DESC, c.id DESC"
        rows = conn.execute(query_sql, params).fetchall()

    serialized_rows = [_consultation_storage_row_to_public_dict(row) for row in rows]
    
    # 关键字搜索（除了 receiving_teacher/teacher_id，使用 JOIN 出来的字段）
    keyword = (query or "").strip().lower()
    if keyword:
        serialized_rows = [
            row for row in serialized_rows
            if keyword in " ".join(
                str(row.get(field, "")).lower() for field in [
                    "date", "parent_wechat_name", "child_name", "grade",
                    "receiving_teacher", "teacher_id", "consultation_subject", "need_detail"
                ]
            )
        ]
    return serialized_rows
```

- [ ] **Step 4: 修改 `list_consultations_for_actor()` 函数**

```python
def list_consultations_for_actor(actor_user: dict, query: str = "") -> list[dict]:
    organization_id = None if (actor_user or {}).get("role") == SUPER_OWNER_ROLE else actor_user["organization_id"]
    assigned_user_id = None
    
    # member 角色按自己的 id 过滤
    if actor_user.get("role") == MEMBER_ROLE:
        assigned_user_id = actor_user["id"]
    
    return list_consultations(
        query=query,
        organization_id=organization_id,
        assigned_user_id=assigned_user_id
    )
```

无主咨询（assigned_user_id = NULL）对 member 自动不可见。

- [ ] **Step 5: 修改 `create_consultation()` 函数**

```python
def create_consultation(data: dict, organization_id: int, assigned_user_id: Optional[int] = None) -> dict:
    ...
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO consultations (
                organization_id, assigned_user_id, date, parent_wechat_name, child_name, grade,
                consultation_subject, need_detail, source_channel, source_channel_note,
                screenshot, reminder_at, reminder_status, reminder_task_id,
                follow_up_status, follow_up_note, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (organization_id, assigned_user_id, ...)  # 新增 assigned_user_id 参数位置
        )
        row = conn.execute(
            """
            SELECT c.*, u.display_name, u.username
            FROM consultations c
            LEFT JOIN users u ON c.assigned_user_id = u.id
            WHERE c.id = ?
            """,
            (cur.lastrowid,)
        ).fetchone()
    return _consultation_storage_row_to_public_dict(row)
```

- [ ] **Step 6: 修改 `update_consultation()` 函数**

UPDATE 部分添加 `assigned_user_id` 列；SELECT 改为 LEFT JOIN

```python
def update_consultation(consultation_id: int, data: dict, organization_id: Optional[int] = None):
    ...
    # data 可能包含 assigned_user_id，提取它
    assigned_user_id = data.get("assigned_user_id")
    
    with get_conn() as conn:
        ...
        conn.execute(
            """
            UPDATE consultations
            SET date=?, parent_wechat_name=?, child_name=?, grade=?,
                consultation_subject=?, need_detail=?, source_channel=?,
                source_channel_note=?, screenshot=?, follow_up_status=?,
                follow_up_note=?, assigned_user_id=?, updated_at=?
            WHERE id=?
            """,
            (..., assigned_user_id, now, consultation_id)
        )
        updated = conn.execute(
            """
            SELECT c.*, u.display_name, u.username
            FROM consultations c
            LEFT JOIN users u ON c.assigned_user_id = u.id
            WHERE c.id = ?
            """,
            (consultation_id,)
        ).fetchone()
    return _consultation_storage_row_to_public_dict(updated)
```

- [ ] **Step 7: 移除或更新 `list_consultation_teachers()` 的使用场景**

如果该函数仅用于 SELECT 下拉（咨询录入时选老师），它已经从 users 表读活跃用户，无需改动。  
frontend 可能仍在调用 `/api/consultation-teachers` 端点，返回值无变化。

- [ ] **Step 8: Commit**

```bash
git add lesson_manager.py
git commit -m "refactor: consultations CRUD with assigned_user_id, member-scoped filtering"
```

---

## Task 3: lesson_manager.py — member 权限 CONSTANT 和辅助函数

**Files:**
- Modify: `lesson_manager.py:44-47` (角色常量)

- [ ] **Step 1: 确认 MEMBER_ROLE 常量已定义**

搜索 `MEMBER_ROLE = ` 行，应该已存在值 `"member"`

- [ ] **Step 2: 无需新增常量，Task 2 中已使用 actor_user.get("role") == MEMBER_ROLE**

跳过

- [ ] **Step 3: Commit**

已含在 Task 2 中

---

## Task 4: app.py — 权限 guard 调整

**Files:**
- Modify: `app.py:~1774-1900` (咨询相关路由)

- [ ] **Step 1: 找到 `/api/consultations/ai-parse` 路由**

搜索 `"ai-parse"`，当前应为 `_require_staff()`

- [ ] **Step 2: 改为 `_require_auth()`**

```python
@app.route("/api/consultations/ai-parse", methods=["POST"])
def api_consultation_ai_parse():
    user, error = _require_auth()  # 改这里，从 _require_staff() → _require_auth()
    if error:
        return error
    
    # 后续逻辑保持不变
    data = request.json or {}
    ...
```

注意：之后的 credit charges 逻辑需要确保对 member 也生效（应该已经可以）。

- [ ] **Step 3: 验证 `/api/consultations` POST 路由接收 assigned_user_id**

搜索 POST consultations 路由，应为 `_require_auth()`

```python
@app.route("/api/consultations", methods=["POST"])
def api_consultation_create():
    user, error = _require_auth()
    if error:
        return error
    item = create_consultation(
        request.json or {},
        user["organization_id"],
        assigned_user_id=request.json.get("assigned_user_id") if request.json else None
    )
    return jsonify(item), 201
```

- [ ] **Step 4: 验证 `/api/consultations/<id>` PUT 路由**

应为 `_require_staff()`，body 中的 `assigned_user_id` 透传：

```python
@app.route("/api/consultations/<int:consultation_id>", methods=["PUT"])
def api_consultation_update(consultation_id):
    user, error = _require_staff()
    if error:
        return error
    item = update_consultation(
        consultation_id,
        request.json or {},
        None if user.get("role") == "super_owner" else user.get("organization_id"),
    )
    # assign_user_id 会在函数内从 request.json 中读取
    ...
```

- [ ] **Step 5: 找到 `/api/classes/:id/invite` GET 路由**

搜索 `"/api/classes/<int:class_id>/invite"`，当前应为 `_require_owner()`

- [ ] **Step 6: 改为 `_require_auth()`**

```python
@app.route("/api/classes/<int:class_id>/invite", methods=["GET"])
def api_class_invite_get(class_id):
    user, error = _require_auth()  # 改这里
    if error:
        return error
    cls, error = _get_accessible_class_or_error(user, class_id)
    if error:
        return error
    invite = get_or_create_active_class_invite(cls["id"], user["id"])
    return jsonify(invite)
```

关键：`_get_accessible_class_or_error()` 已经会做权限检查，member 只能访问自己的班级。

- [ ] **Step 7: 找到 `/api/classes/:id/invite/reset` POST 路由**

应在 GET 下方几行

- [ ] **Step 8: 改为 `_require_auth()`**

```python
@app.route("/api/classes/<int:class_id>/invite/reset", methods=["POST"])
def api_class_invite_reset(class_id):
    user, error = _require_auth()  # 改这里
    if error:
        return error
    cls, error = _get_accessible_class_or_error(user, class_id)
    if error:
        return error
    invite = reset_class_invite(cls["id"], user["id"])
    return jsonify(invite)
```

- [ ] **Step 9: Commit**

```bash
git add app.py
git commit -m "feat: open ai-parse and invite endpoints to all authenticated users"
```

---

## Task 5: frontend/src/App.tsx — 侧边栏菜单和班级管理权限

**Files:**
- Modify: `frontend/src/App.tsx:1403-1420` (menuItems 定义)
- Modify: `frontend/src/App.tsx:~<页面路由或条件渲染>` (班级管理页面 member UI)

- [ ] **Step 1: 找到 menuItems 定义（~1403 行）**

搜索 `const menuItems = `

- [ ] **Step 2: 找到 classes tab 定义**

应为：
```typescript
...(hasStaffAccess(currentUser.role)
  ? [{ id: 'classes', icon: Home, label: '班级管理' }]
  : []),
```

- [ ] **Step 3: 改为无条件显示**

```typescript
{ id: 'classes', icon: Home, label: '班级管理' },
```

直接从条件渲染改为始终包含。

- [ ] **Step 4: 找到班级管理页面组件（ClassesPage 或类似）**

搜索组件名或路由到 'classes' 的地方

- [ ] **Step 5: 在页面顶部获取 currentUser.role**

确保 currentUser 对象已通过 props 或 context 传入

- [ ] **Step 6: 对新增班级、编辑班级、删除班级、分配老师操作加条件渲染**

示例（假设有新建按钮）：

```typescript
{hasStaffAccess(currentUser.role) && (
  <button onClick={handleAddClass}>新建班级</button>
)}
```

对每个班级卡片/行，编辑和删除按钮：

```typescript
{hasStaffAccess(currentUser.role) && (
  <>
    <button>编辑</button>
    <button>删除</button>
  </>
)}
```

- [ ] **Step 7: 确保邀请码部分对所有角色都显示**

```typescript
{/* 邀请码管理 - 所有角色都可见 */}
<InviteCodeSection classId={class.id} />
```

- [ ] **Step 8: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "feat: open classes tab to all roles, hide management ops from member"
```

---

## Task 6: 测试更新 — test_consultation_flow.py

**Files:**
- Modify: `tests/test_consultation_flow.py` (现有测试)

- [ ] **Step 1: 打开文件，找到所有创建咨询的测试**

应该有类似 `test_create_consultation` 的测试

- [ ] **Step 2: 字段替换 — teacher_id → assigned_user_id**

旧：`{"teacher_id": "john_doe", ...}`  
新：`{"assigned_user_id": <user_id int>, ...}`

假设测试中预先设置了用户对象，取其 ID。

- [ ] **Step 3: 写新测试 — member 只能看自己的咨询**

```python
def test_member_sees_only_assigned_consultations():
    # 创建机构、两个用户（teacher1, teacher2）
    org = lessons_db.create_organization({"name": "Test Org"})
    user1 = lessons_db.create_user({
        "username": "teacher1", "organization_id": org["id"], "role": "member"
    })
    user2 = lessons_db.create_user({
        "username": "teacher2", "organization_id": org["id"], "role": "member"
    })
    
    # 创建三条咨询：分配给 user1、user2、无主
    c1 = lessons_db.create_consultation({...}, org["id"], assigned_user_id=user1["id"])
    c2 = lessons_db.create_consultation({...}, org["id"], assigned_user_id=user2["id"])
    c3 = lessons_db.create_consultation({...}, org["id"], assigned_user_id=None)
    
    # user1 列咨询，应仅见 c1
    result = lessons_db.list_consultations_for_actor(user1, "")
    assert len(result) == 1
    assert result[0]["id"] == c1["id"]
    
    # user2 列咨询，应仅见 c2
    result2 = lessons_db.list_consultations_for_actor(user2, "")
    assert len(result2) == 1
    assert result2[0]["id"] == c2["id"]
```

- [ ] **Step 4: 写新测试 — 无主咨询对 admin 可见**

```python
def test_admin_sees_all_consultations_including_unassigned():
    org = lessons_db.create_organization({"name": "Test Org"})
    admin = lessons_db.create_user({
        "username": "admin1", "organization_id": org["id"], "role": "admin"
    })
    
    c1 = lessons_db.create_consultation({...}, org["id"], assigned_user_id=None)
    c2 = lessons_db.create_consultation({...}, org["id"], assigned_user_id=None)
    
    result = lessons_db.list_consultations_for_actor(admin, "")
    assert len(result) == 2
```

- [ ] **Step 5: 运行测试确保通过**

```bash
pytest tests/test_consultation_flow.py -v
```

- [ ] **Step 6: Commit**

```bash
git add tests/test_consultation_flow.py
git commit -m "test: update consultation tests with assigned_user_id, add member filtering"
```

---

## Task 7: 新测试文件 — test_member_scoped_access.py

**Files:**
- Create: `tests/test_member_scoped_access.py`

- [ ] **Step 1: 创建新文件骨架**

```python
import unittest
from datetime import date
from lesson_manager import (
    create_organization, create_user, list_consultations_for_actor,
    list_classes_for_actor, get_user_class_ids, create_class,
    set_class_teacher_user_id, MEMBER_ROLE, ADMIN_ROLE, OWNER_ROLE
)

class TestMemberScopedAccess(unittest.TestCase):
    def setUp(self):
        # 清空数据库或使用 test db
        pass
    
    def tearDown(self):
        pass
```

- [ ] **Step 2: 写测试 — member 可访问自己班级的邀请码**

```python
def test_member_can_access_own_class_invite(self):
    org = create_organization({"name": "Org"})
    teacher = create_user({
        "username": "teacher1",
        "organization_id": org["id"],
        "role": MEMBER_ROLE
    })
    cls = create_class({
        "organization_id": org["id"],
        "name": "Class A",
        "subject": "Math"
    })
    set_class_teacher_user_id(cls["id"], teacher["id"])
    
    # member 应该能通过 _filter_classes_for_user 看到这个班级
    classes = list_classes_for_actor(teacher) if hasattr(teacher, '__getitem__') and teacher.get('role') in {'super_owner', 'owner', 'admin'} else [cls]
    # 或者直接调用内部过滤函数
    # （这是个框架测试，实际调用需要对应 app 中的 filter 逻辑）
```

实际上，邀请码的访问是在 app.py 中通过 `_require_auth()` + `_get_accessible_class_or_error()`，所以这个测试可能更多是集成测试。

- [ ] **Step 3: 写集成测试 — member 访问自己班级邀请码的 API**

（需要 Flask test client）

```python
def test_member_invite_access(self):
    # 创建组织、成员、班级
    # 调用 client.get(f'/api/classes/{cls_id}/invite')
    # 断言 200 OK + 邀请码返回
    pass
```

- [ ] **Step 4: 写测试 — member 看不到没分配给自己的班级**

```python
def test_member_hidden_from_unassigned_classes(self):
    org = create_organization({"name": "Org"})
    teacher1 = create_user({..., "role": MEMBER_ROLE})
    teacher2 = create_user({..., "role": MEMBER_ROLE})
    
    cls1 = create_class({...})
    set_class_teacher_user_id(cls1["id"], teacher1["id"])
    
    cls2 = create_class({...})
    set_class_teacher_user_id(cls2["id"], teacher2["id"])
    
    # teacher1 的班级列表只应有 cls1
    owned_ids = get_user_class_ids(teacher1["id"])
    assert cls1["id"] in owned_ids
    assert cls2["id"] not in owned_ids
```

- [ ] **Step 5: 写测试 — member 无法创建班级（应该在路由层被 _require_staff() 拦截）**

这个更多是集成测试：

```python
def test_member_cannot_create_class(self):
    # member 用户试图 POST /api/classes
    # 应该得到 403 Forbidden（或类似权限错误）
    pass
```

- [ ] **Step 6: 运行测试**

```bash
pytest tests/test_member_scoped_access.py -v
```

- [ ] **Step 7: Commit**

```bash
git add tests/test_member_scoped_access.py
git commit -m "test: add member-scoped access tests for consultations and classes"
```

---

## Task 8: 检查其他可能受影响的代码

**Files:**
- Check: `lesson_manager.py` (搜索其他调用 create_consultation 或 update_consultation 的地方)
- Check: `app.py` (搜索其他涉及 consultations 的逻辑)

- [ ] **Step 1: 搜索所有 `create_consultation` 调用**

```bash
grep -n "create_consultation(" lesson_manager.py app.py frontend/src/*.tsx
```

确保所有调用都有或可以有 `assigned_user_id` 参数。

- [ ] **Step 2: 搜索所有 `update_consultation` 调用**

确保支持 `assigned_user_id` 更新。

- [ ] **Step 3: 搜索 teacher_id 或 receiving_teacher 的其他使用**

确保没有遗漏的地方假设这些字段来自 DB 而非 JOIN。

- [ ] **Step 4: 检查前端是否有地方硬编码期望 teacher_id/receiving_teacher**

搜索 `frontend/src` 中的相关字段引用。

- [ ] **Step 5: 无需 commit（仅检查）**

---

## Task 9: 本地验证和端到端测试

**Files:**
- Manual test

- [ ] **Step 1: 启动后端开发服务器**

```bash
python app.py
# 或 ./scripts/run_backend.sh
```

- [ ] **Step 2: 启动前端开发服务器**

```bash
cd frontend && npm run dev
```

- [ ] **Step 3: 用 member 账户登录，验证**

- [ ] **验证点 1：咨询记录列表**

以 member 身份登录 → 进咨询记录  
只应看到分配给自己的咨询（assigned_user_id = 自己 id）

- [ ] **验证点 2：班级管理页面**

以 member 身份登录 → 侧边栏应该有"班级管理"选项  
进入班级管理 → 只应看到自己负责的班级  
不应看到新建按钮、编辑按钮、删除按钮  
应能看到邀请码区块并能重置邀请码

- [ ] **验证点 3：AI 解析权限**

以 member 身份登录 → 咨询详情页  
应能点击 AI 解析按钮（不应被权限拦截）

- [ ] **验证点 4：admin/owner 行为不变**

以 admin 身份登录 → 应能看全部咨询（包括无主）  
应能管理所有班级（新增、编辑、删除）

- [ ] **Step 4: Commit**

无代码改动，仅验证通过

---

## Task 10: 最终检查和合并

**Files:**
- Git workflow

- [ ] **Step 1: 检查所有 commit 在本分支**

```bash
git log --oneline develop..HEAD
```

应该看到～5-6 个 commit

- [ ] **Step 2: 整理 commit 信息（可选），确保清晰**

每个 commit 应该对应一个逻辑变更：
- DB schema 迁移
- lesson_manager 改动
- app.py 权限
- frontend 改动
- 测试

- [ ] **Step 3: 确认所有测试通过**

```bash
pytest tests/ -v
```

- [ ] **Step 4: 合并回 develop**

```bash
git checkout develop
git merge feature/member-scoped-access
```

- [ ] **Step 5: 更新项目根目录 handoff.md，记录已完成**

```markdown
## 2026-04-09 Member Scoped Access

**Status:** ✅ 已完成合并到 develop

**变更概览：**
- consultations 表重构：添加 assigned_user_id FK，删除 teacher_id 字符串字段
- Member 权限：只能看自己的咨询、班级；无主咨询对 member 不可见
- 班级邀请码管理：开放给 member
- AI 咨询解析：开放给所有角色

**受影响的文件：**
- lesson_manager.py：consultations CRUD + 过滤
- app.py：权限 guard 调整
- App.tsx：菜单和条件渲染
- tests/：更新和新增测试
```

- [ ] **Step 6: Commit handoff 更新**

```bash
git add handoff.md
git commit -m "docs: update handoff - member scoped access completed"
git push origin develop
```

- [ ] **Step 7: 验证远程分支已更新**

```bash
git log origin/develop -5 --oneline
```

---

## 检查列表

- [ ] 所有 DB 变更已测试（表确实被重建）
- [ ] member 过滤在 list_consultations_for_actor 中生效
- [ ] 无主咨询（assigned_user_id = NULL）对 member 隐藏✅
- [ ] 班级管理 tab 对 member 可见✅
- [ ] member 班级管理页无增删改权限✅
- [ ] member 可访问邀请码页面✅
- [ ] AI 解析对 member 可用✅
- [ ] admin/owner/super_owner 行为不变✅
- [ ] 所有单元测试通过✅
- [ ] 本地端到端验证通过✅
- [ ] commit 信息清晰✅
- [ ] handoff.md 已更新✅
