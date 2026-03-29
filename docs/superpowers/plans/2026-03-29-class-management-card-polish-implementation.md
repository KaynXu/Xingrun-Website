# Class Management Card Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refine the `班级管理` tab so it removes teacher-email input, compresses long class lists into single-expand management cards, moves teacher assignment into each class card, and standardizes saved class names.

**Architecture:** Keep the existing Flask + SQLite API contract and focus the change in the React workspace shell. Reuse the current `/api/classes` and `/api/admin/users/*/classes` endpoints, but reorganize `ClassManagementPage` around one expanded class card at a time, with class-editing state and teacher-assignment state scoped to that card. Name normalization remains a small frontend helper so this change does not require a database migration.

**Tech Stack:** React 19, TypeScript, Vite, Tailwind CSS, Node `test`, Python `unittest`

---

### Task 1: Lock The New Card-Based UX With Failing Source-Level Tests

**Files:**
- Modify: `frontend/src/account-card.test.tsx`
- Modify: `frontend/src/workspace-navigation.test.ts`

- [ ] **Step 1: Add a failing test that removes teacher-email UI and the bottom assignment section**

```ts
test('class management source removes teacher email fields and the standalone bottom assignment section', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const classManagementBlock = source.match(/const ClassManagementPage = \([\s\S]*?\n};/);

  assert.ok(classManagementBlock);
  assert.doesNotMatch(classManagementBlock[0], /老师邮箱/);
  assert.doesNotMatch(classManagementBlock[0], /teacher_email/);
  assert.doesNotMatch(classManagementBlock[0], /<section className=\{\`\$\{workspaceCardClass\} space-y-5 p-6\`\}>[\s\S]*班级分配/);
  assert.match(classManagementBlock[0], /班级老师分配/);
});
```

- [ ] **Step 2: Add a failing test that requires card compaction and single-expand behavior**

```ts
test('class management source uses one expanded class card at a time', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const classManagementBlock = source.match(/const ClassManagementPage = \([\s\S]*?\n};/);

  assert.ok(classManagementBlock);
  assert.match(classManagementBlock[0], /const \[expandedClassId, setExpandedClassId\] = useState<number \| 'new' \| null>/);
  assert.match(classManagementBlock[0], /const isExpanded = expandedClassId === item\.id/);
  assert.match(classManagementBlock[0], /setExpandedClassId\(\(current\) => current === classId \? null : classId\)/);
});
```

- [ ] **Step 3: Add a failing test that requires embedded teacher assignment and class-name normalization helpers**

```ts
test('class management source embeds teacher assignment inside each class card and normalizes common class names', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const classManagementBlock = source.match(/const ClassManagementPage = \([\s\S]*?\n};/);

  assert.ok(classManagementBlock);
  assert.match(source, /const normalizeClassNameInput = \(value: string\): string =>/);
  assert.match(source, /\['6年级2班', '六年级 2 班'\]/);
  assert.match(classManagementBlock[0], /placeholder="搜索老师"/);
  assert.match(classManagementBlock[0], /已分配 \{selectedTeacherIds.length\} 位老师/);
  assert.match(classManagementBlock[0], /classes\.map\(\(item\) => \{[\s\S]*班级老师分配/);
});
```

- [ ] **Step 4: Run the focused frontend tests to verify the new assertions fail for the right reason**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend && npx tsx --test src/workspace-navigation.test.ts src/account-card.test.tsx`

Expected: FAIL because `App.tsx` still references `teacher_email`, still renders a standalone bottom assignment section, and does not have the new `expandedClassId` / `normalizeClassNameInput` helpers.

- [ ] **Step 5: Commit the red test state**

```bash
cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary
git add frontend/src/account-card.test.tsx frontend/src/workspace-navigation.test.ts
git commit -m "test: cover compact class management cards"
```

### Task 2: Simplify The Class Form Model And Add Frontend Name Normalization

**Files:**
- Modify: `frontend/src/App.tsx`
- Test: `frontend/src/account-card.test.tsx`

- [ ] **Step 1: Trim the class form model so it no longer stores teacher email in editable UI state**

```ts
type ClassFormValues = {
  name: string;
  subject: string;
  grade: string;
  teacher_name: string;
};

const createEmptyClassForm = (): ClassFormValues => ({
  name: '',
  subject: '',
  grade: '',
  teacher_name: '',
});

const toClassFormValues = (item: ClassItem): ClassFormValues => ({
  name: item.name || '',
  subject: item.subject || '',
  grade: item.grade || '',
  teacher_name: item.teacher_name || '',
});
```

- [ ] **Step 2: Add a small normalization helper for common school class naming variants**

```ts
const GRADE_NORMALIZATION_RULES: Array<[string, string]> = [
  ['一年级', '一年级'],
  ['二年级', '二年级'],
  ['三年级', '三年级'],
  ['四年级', '四年级'],
  ['五年级', '五年级'],
  ['六年级', '六年级'],
  ['初一', '初一'],
  ['初二', '初二'],
  ['初三', '初三'],
  ['高一', '高一'],
  ['高二', '高二'],
  ['高三', '高三'],
];

const normalizeClassNameInput = (value: string): string => {
  const trimmed = value.trim();
  if (!trimmed) return '';

  const normalized = trimmed
    .replace(/\s+/g, '')
    .replace(/^6年级/, '六年级')
    .replace(/^5年级/, '五年级')
    .replace(/^4年级/, '四年级')
    .replace(/^3年级/, '三年级')
    .replace(/^2年级/, '二年级')
    .replace(/^1年级/, '一年级')
    .replace(/一班$/, '1班')
    .replace(/二班$/, '2班')
    .replace(/三班$/, '3班')
    .replace(/四班$/, '4班')
    .replace(/五班$/, '5班')
    .replace(/六班$/, '6班');

  const match = normalized.match(/^(一年级|二年级|三年级|四年级|五年级|六年级|初一|初二|初三|高一|高二|高三)(\d+)班$/);
  if (!match) return trimmed;
  return `${match[1]} ${match[2]} 班`;
};

const NORMALIZATION_EXAMPLES: Array<[string, string]> = [
  ['6年级2班', '六年级 2 班'],
  ['六年级二班', '六年级 2 班'],
  ['六年2班', '六年级 2 班'],
];
```

- [ ] **Step 3: Use the helper when saving classes, while keeping API compatibility by still sending an empty `teacher_email`**

```ts
const payload = {
  name: normalizeClassNameInput(form.name),
  subject: form.subject.trim(),
  grade: form.grade.trim(),
  teacher_name: form.teacher_name.trim(),
  teacher_email: '',
};
```

- [ ] **Step 4: Remove the teacher-email input and rewrite the helper copy to reflect the new contract**

```tsx
<label className="space-y-2 text-sm">
  <span className="text-slate-500 dark:text-slate-400">负责老师</span>
  <input
    type="text"
    value={form.teacher_name}
    onChange={(e) => handleFieldChange('teacher_name', e.target.value)}
    className={workspaceFieldClass}
    placeholder="如：张老师"
  />
</label>

<div className={`${workspaceSoftCardClass} space-y-3 p-4`}>
  <p className="text-sm font-semibold text-slate-900 dark:text-white">命名统一规则</p>
  <p className="text-sm text-slate-500 dark:text-slate-400">新建或编辑班级时会优先统一成“六年级 2 班 / 初一 3 班 / 高二 1 班”的格式。</p>
</div>
```

- [ ] **Step 5: Run the focused tests to verify the helper and form-model changes pass**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend && npx tsx --test src/workspace-navigation.test.ts src/account-card.test.tsx`

Expected: PASS for the new `teacher_email` removal and normalization assertions; still FAIL on the card-layout assertions that Task 3 has not implemented yet.

- [ ] **Step 6: Commit the form-model and normalization helper changes**

```bash
cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary
git add frontend/src/App.tsx frontend/src/account-card.test.tsx frontend/src/workspace-navigation.test.ts
git commit -m "feat: normalize class names in management form"
```

### Task 3: Refactor ClassManagementPage Into Single-Expand Management Cards

**Files:**
- Modify: `frontend/src/App.tsx`
- Test: `frontend/src/account-card.test.tsx`
- Test: `frontend/src/workspace-navigation.test.ts`

- [ ] **Step 1: Replace selected-class editing with one expanded card state and per-card assignment search**

```ts
const [expandedClassId, setExpandedClassId] = useState<number | 'new' | null>('new');
const [formByClassId, setFormByClassId] = useState<Record<string, ClassFormValues>>({ new: createEmptyClassForm() });
const [teacherSearchByClassId, setTeacherSearchByClassId] = useState<Record<string, string>>({});

const getClassFormKey = (classId: number | 'new') => String(classId);

const getFormForClass = (classId: number | 'new', item?: ClassItem | null): ClassFormValues => {
  if (classId === 'new') return formByClassId.new || createEmptyClassForm();
  return formByClassId[getClassFormKey(classId)] || toClassFormValues(item || null);
};
```

- [ ] **Step 2: Build the compact card summary and embedded expand/collapse behavior**

```tsx
{classes.map((item) => {
  const isExpanded = expandedClassId === item.id;
  const selectedTeacherIds = users
    .filter((user) => (userClassIdsByUserId[user.id] || []).includes(item.id))
    .map((user) => user.id);

  return (
    <div key={item.id} className={`${workspaceSoftCardClass} overflow-hidden p-5`}>
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-lg font-semibold text-slate-900 dark:text-white">{item.name}</span>
            <span className="rounded-full border border-sky-200 bg-sky-50 px-2.5 py-1 text-xs font-medium text-sky-700 dark:border-sky-500/30 dark:bg-sky-500/10 dark:text-sky-300">
              {item.subject || '未填写科目'}
            </span>
          </div>
          <p className="text-sm text-slate-500 dark:text-slate-400">负责老师：{item.teacher_name || '未填写负责老师'}</p>
          <p className="text-sm text-slate-500 dark:text-slate-400">已分配 {selectedTeacherIds.length} 位老师</p>
        </div>
        <button
          type="button"
          onClick={() => setExpandedClassId((current) => (current === item.id ? null : item.id))}
          className={workspaceSecondaryButtonClass}
        >
          {isExpanded ? '收起管理' : '展开管理'}
        </button>
      </div>
```

- [ ] **Step 3: Move basic-info editing and teacher assignment into the expanded portion of each class card**

```tsx
      {isExpanded && (
        <div className="mt-5 grid gap-6 border-t border-sky-100/80 pt-5 dark:border-white/10 xl:grid-cols-[minmax(0,0.92fr)_minmax(0,1.08fr)]">
          <div className="space-y-4">
            <h5 className="text-base font-semibold text-slate-900 dark:text-white">基本信息</h5>
            {/* class form fields bound to getFormForClass(item.id, item) */}
            <div className="flex flex-wrap gap-3">
              <button type="button" onClick={() => handleSaveClass(item.id)} className={workspacePrimaryButtonClass}>保存班级</button>
              <button type="button" onClick={() => handleDeleteClass(item.id)} className="...rose button classes...">删除班级</button>
            </div>
          </div>

          <div className="space-y-4">
            <div className="flex items-center justify-between gap-3">
              <h5 className="text-base font-semibold text-slate-900 dark:text-white">班级老师分配</h5>
              <input
                type="text"
                value={teacherSearchByClassId[getClassFormKey(item.id)] || ''}
                onChange={(e) => setTeacherSearchByClassId((current) => ({ ...current, [getClassFormKey(item.id)]: e.target.value }))}
                className={workspaceFieldClass}
                placeholder="搜索老师"
              />
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              {filteredTeachers.map((user) => (
                <label key={`${item.id}-${user.id}`} className="flex items-start gap-3 rounded-2xl border border-sky-100 bg-white/75 p-4 text-sm dark:border-white/10 dark:bg-slate-950/55">
                  <input
                    type="checkbox"
                    checked={(userClassIdsByUserId[user.id] || []).includes(item.id)}
                    onChange={(e) => handleToggleAssignment(user.id, item.id, e.target.checked)}
                    disabled={Boolean(assignmentSavingByUserId[user.id]) || classInteractionLocked}
                  />
                  <div>
                    <p className="font-medium text-slate-900 dark:text-white">{user.name}</p>
                    <p className="text-xs text-slate-500 dark:text-slate-400">{getRoleLabel(user.role)}</p>
                  </div>
                </label>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
})}
```

- [ ] **Step 4: Remove the standalone bottom assignment section and rewrite copy from `成员班级分配` to `班级老师分配`**

```tsx
<p className="mt-2 max-w-3xl text-sm text-slate-500 dark:text-slate-400">
  在这里维护 {currentUser.organization_name} 的班级资料，并直接在对应班级内完成老师分配。
</p>
```

- [ ] **Step 5: Run the focused frontend suite to verify all class-management source tests now pass**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend && npx tsx --test src/workspace-navigation.test.ts src/account-card.test.tsx`

Expected: PASS with the new card-layout, embedded-assignment, and naming-normalization assertions all green.

- [ ] **Step 6: Commit the card-layout refactor**

```bash
cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary
git add frontend/src/App.tsx frontend/src/account-card.test.tsx frontend/src/workspace-navigation.test.ts
git commit -m "feat: embed teacher assignment into class cards"
```

### Task 4: Final Verification And Deployment-Ready Wrap-Up

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/account-card.test.tsx`
- Modify: `frontend/src/workspace-navigation.test.ts`
- Optional notes: `handoff.md`

- [ ] **Step 1: Run the exact merged verification commands on the updated workspace branch**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary && /Users/ark.mini/Desktop/Xingrun-Review/.venv/bin/python -m unittest tests.test_account_flow -v`

Expected: `Ran 8 tests`, `OK`

- [ ] **Step 2: Run the frontend source-level regression suite**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend && npx tsx --test src/workspace-navigation.test.ts src/account-card.test.tsx`

Expected: PASS with 0 failures.

- [ ] **Step 3: Run TypeScript lint/typecheck**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend && npm run lint`

Expected: `tsc --noEmit` exits 0.

- [ ] **Step 4: Run the production build**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend && npm run build`

Expected: Vite build succeeds; chunk-size warning is acceptable unless a new hard failure appears.

- [ ] **Step 5: Update handoff with the delivered UX changes and verification counts**

```md
补充记录（2026-03-29，班级管理卡片收纳落地）
- 去掉前端 `teacher_email` 输入与展示
- `班级管理` 改为单展开卡片式管理
- `班级老师分配` 收进每个班级卡片内部
- 新建/编辑班级时前端统一常见名称格式为 `六年级 2 班`
- proof：backend 8 tests pass；frontend focused tests pass；lint/build pass
```

- [ ] **Step 6: Create the delivery commit**

```bash
cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary
git add frontend/src/App.tsx frontend/src/account-card.test.tsx frontend/src/workspace-navigation.test.ts handoff.md
git commit -m "feat: compact class management cards"
```