# 设计文档：机构成员（member）权限收窄 & 班级管理开放

**日期：** 2026-04-09  
**状态：** 待实现  
**分支策略：** 从 `develop` 新开 `feature/member-scoped-access`

---

## 背景与目标

目前机构成员（`member` 角色）可以看到机构内所有咨询记录，并且无法进入班级管理页面。目标：

1. **咨询记录**：member 只能看到分配给自己的咨询，无主咨询不可见。
2. **班级管理**：开放给 member，但只能看自己负责的班级 + 管理邀请码，不能增删班级或分配老师。
3. **其他 tab**（课堂反馈、复习生成、课程日历、智能错题）：通过已有的 `user_classes` 过滤，member 只看自己班级的数据（后端已部分实现，本次补全咨询侧逻辑）。
4. **AI 解析**（`/api/consultations/ai-parse`）：开放给所有角色（含 member）。

---

## 数据库变更

### consultations 表重构

**操作：DROP + RECREATE（清空旧数据，无需迁移）**

移除字段：`receiving_teacher`（字符串）、`teacher_id`（字符串）  
新增字段：`assigned_user_id INTEGER REFERENCES users(id)`（nullable，未分配时为 NULL）

新 schema：

```sql
CREATE TABLE consultations (
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
```

**迁移策略：**  
`_ensure_consultations_table()` 启动时检测列是否包含 `assigned_user_id`，若不存在则 DROP + 重建。

**公开 API 的向后兼容：**  
返回 JSON 时仍然输出 `receiving_teacher`（从 JOIN users 取 `display_name`）和 `teacher_id`（从 JOIN users 取 `username`），前端无需修改字段名引用。

---

## 后端变更 — lesson_manager.py

### `_ensure_consultations_table()`
- 检测 `assigned_user_id` 列是否存在
- 不存在则 DROP TABLE + 以新 schema 重建

### `list_consultations()`
- SQL 改为 `LEFT JOIN users ON consultations.assigned_user_id = users.id`
- 新增可选参数 `assigned_user_id: Optional[int] = None`
- 当传入时，SQL 加 `WHERE consultations.assigned_user_id = ?`

### `list_consultations_for_actor()`
- `super_owner`：不加任何过滤（已有）
- `owner` / `admin`：按 `organization_id` 过滤（已有）
- `member`：按 `organization_id` + `assigned_user_id = actor["id"]` 双重过滤 → 无主咨询对 member 不可见

### `_consultation_storage_row_to_public_dict()`
- 从 JOIN 结果填充 `receiving_teacher`（users.display_name）和 `teacher_id`（users.username）
- 若 `assigned_user_id` 为 NULL，两字段返回空字符串

### `create_consultation()`
- 接收 `assigned_user_id`（int 或 None）
- INSERT 时写入该列

### `update_consultation()`
- 接收 `assigned_user_id`（int 或 None）
- UPDATE 时写入该列

### `list_consultation_teachers()`
- 无变更（已经是从 `users` 表读活跃用户）

### `CONSULTATION_FIELDNAMES` 常量
- 移除 `receiving_teacher`、`teacher_id` 两个字段名（如果该常量用于字段白名单/序列化）
- 文本搜索的 keyword 匹配改为用 JOIN 出来的 display_name + username

---

## 后端变更 — app.py

| 路由 | 旧 guard | 新 guard | 说明 |
|---|---|---|---|
| `POST /api/consultations/ai-parse` | `_require_staff()` | `_require_auth()` | member 可用 AI 解析 |
| `GET /api/classes/:id/invite` | `_require_owner()` | `_require_auth()` | member 可读自己班级的邀请码 |
| `POST /api/classes/:id/invite/reset` | `_require_owner()` | `_require_auth()` | member 可重置自己班级的邀请码 |

其余路由不变：
- `POST /api/consultations`：`_require_auth()`，body 增加 `assigned_user_id` 字段透传
- `PUT /api/consultations/:id`：`_require_staff()`，body 增加 `assigned_user_id` 透传
- `DELETE /api/consultations/:id`：`_require_staff()`（不变）
- `GET /api/consultations`：`_require_auth()`（不变，过滤逻辑在 lesson_manager）

---

## 前端变更 — App.tsx

### 侧边栏 menuItems
- `classes`（班级管理）的条件：从 `hasStaffAccess(currentUser.role)` → 移除条件（所有已登录用户可见）

### 班级管理页（`ClassesPage` 或相关组件）
member 角色隐藏以下 UI 元素：
- 新建班级按钮
- 编辑班级按钮/操作
- 删除班级按钮/操作
- 分配老师下拉/操作

member 角色显示：
- 邀请码区块（调用 `GET /api/classes/:id/invite` 和 `POST /api/classes/:id/invite/reset`）

判断方式：使用现有的 `hasStaffAccess(currentUser.role)` 控制管理性操作，`!hasStaffAccess` 时只显示邀请码。

### 咨询记录页
- 无需改动（backend 过滤后前端渲染什么就显示什么）
- `canManage`（`hasStaffAccess`）继续控制编辑/删除 UI 可见性

---

## 不在本次范围

- 复习生成、课程日历、课堂反馈、智能错题：后端已通过 `user_classes` 在 class 级别过滤，member 只能访问自己班级数据，本次不额外改动
- `DELETE /api/consultations/:id`：维持 `_require_staff()`
- 账号审批、积分中心：维持 `hasOwnerAccess`

---

## 受影响的测试文件

需同步更新 / 新增：
- `tests/test_consultation_flow.py` — 咨询 CRUD 测试需更新字段名，新增 member 过滤断言
- `tests/test_class_feedback_api.py` — 可能需要新增 member invite 访问测试
- 新增 `tests/test_member_scoped_access.py` — 专项测试 member 权限收窄行为

---

## 验收标准

1. member 登录后，咨询记录只看到 `assigned_user_id = 自己 id` 的记录
2. `assigned_user_id = NULL` 的咨询对 member 不可见，对 admin/owner 可见
3. member 可进入班级管理页，只看到自己负责的班级
4. member 可查看并重置自己班级的邀请码
5. member 无法看到新建/编辑/删除班级的 UI 操作
6. member 可使用 AI 解析咨询（`/api/consultations/ai-parse`）
7. admin/owner 行为不受影响，仍可看到全机构所有咨询和班级
