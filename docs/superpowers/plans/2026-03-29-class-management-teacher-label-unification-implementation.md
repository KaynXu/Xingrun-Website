# Class Management Teacher Label Unification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Update `班级管理` so the page uses a single `负责老师` concept everywhere and the class `年级` field is chosen from the same fixed 12-option set used by the top grade filter.

**Architecture:** Keep all existing backend routes, teacher-binding state, optimistic update logic, and class-card structure intact. Limit the change to `frontend/src/App.tsx` and the two source-level frontend test files by removing duplicate teacher wording, replacing the freeform grade inputs with a shared grade-select control, and tightening the wording assertions around the class-management block.

**Tech Stack:** React 19, TypeScript, Vite, Tailwind CSS, Node `test`

---

### Task 1: Lock The New UX Contract With Failing Frontend Tests

**Files:**
- Modify: `frontend/src/account-card.test.tsx`
- Modify: `frontend/src/workspace-navigation.test.ts`

- [ ] **Step 1: Add a source-level assertion that the page no longer exposes `班级老师分配` as a separate concept**

```ts
test('class management source uses one 负责老师 concept instead of separate 班级老师分配 wording', () => {
  const classManagementBlock = appSource.match(/const ClassManagementPage = \([\s\S]*?\n};/);

  assert.ok(classManagementBlock);
  assert.match(classManagementBlock[0], /<h4 className="text-xl font-semibold text-slate-900 dark:text-white">负责老师<\/h4>/);
  assert.doesNotMatch(classManagementBlock[0], /班级老师分配/);
  assert.doesNotMatch(classManagementBlock[0], /<span className="text-slate-500 dark:text-slate-400">负责老师<\/span>[\s\S]*<div className=\{`\$\{workspaceFieldClass\} flex min-h-12 items-center`\}>/);
});
```

- [ ] **Step 2: Add a source-level assertion that class forms use a fixed grade option list instead of freeform text inputs**

```ts
test('class management source reuses fixed grade options for form selection', () => {
  const classManagementBlock = appSource.match(/const ClassManagementPage = \([\s\S]*?\n};/);

  assert.ok(classManagementBlock);
  assert.match(classManagementBlock[0], /const gradeOptions = \['一年级', '二年级', '三年级', '四年级', '五年级', '六年级', '初一', '初二', '初三', '高一', '高二', '高三'\];/);
  assert.match(classManagementBlock[0], /const gradeFilterOptions = \['全部', \.\.\.gradeOptions\];/);
  assert.match(classManagementBlock[0], /<select[\s\S]*value=\{newClassForm\.grade\}[\s\S]*onChange=\{\(e\) => handleFieldChange\('new', 'grade', e\.target\.value\)\}/);
  assert.match(classManagementBlock[0], /<select[\s\S]*value=\{formState\.grade\}[\s\S]*onChange=\{\(e\) => handleFieldChange\(item\.id, 'grade', e\.target\.value\)\}/);
  assert.doesNotMatch(classManagementBlock[0], /placeholder="如：六年级"/);
});
```

- [ ] **Step 3: Add a source-level assertion that the selected grade is validated from the shared option set before saving**

```ts
test('class management source rejects class saves when grade is not selected from fixed options', () => {
  const classManagementBlock = appSource.match(/const ClassManagementPage = \([\s\S]*?\n};/);

  assert.ok(classManagementBlock);
  assert.match(classManagementBlock[0], /if \(!payload\.grade \|\| !gradeOptions\.includes\(payload\.grade\)\) \{\s*setFormError\('请选择年级'\);\s*return;\s*\}/);
});
```

- [ ] **Step 4: Run the focused frontend tests to verify the new assertions fail for the expected reasons**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend && npx tsx --test src/workspace-navigation.test.ts src/account-card.test.tsx`

Expected: FAIL on the new wording and grade-select assertions because the current source still contains `班级老师分配`, a read-only `负责老师` field, and `input type="text"` for grade.

- [ ] **Step 5: Stage only the red frontend tests**

```bash
cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary
git add frontend/src/account-card.test.tsx frontend/src/workspace-navigation.test.ts
```

### Task 2: Implement The Unified Teacher Wording And Fixed Grade Select

**Files:**
- Modify: `frontend/src/App.tsx`
- Test: `frontend/src/account-card.test.tsx`
- Test: `frontend/src/workspace-navigation.test.ts`

- [ ] **Step 1: Introduce a shared fixed grade option list and derive the filter options from it**

```ts
const gradeOptions = ['一年级', '二年级', '三年级', '四年级', '五年级', '六年级', '初一', '初二', '初三', '高一', '高二', '高三'];
const gradeFilterOptions = ['全部', ...gradeOptions];
```

Place these inside `ClassManagementPage` where `gradeFilterOptions` is currently declared so both the filter pills and form controls use the same values.

- [ ] **Step 2: Replace the new-class grade text input with a `<select>` bound to the fixed options**

```tsx
<label className="space-y-2 text-sm">
  <span className="text-slate-500 dark:text-slate-400">年级</span>
  <select
    value={newClassForm.grade}
    onChange={(e) => handleFieldChange('new', 'grade', e.target.value)}
    className={workspaceFieldClass}
  >
    <option value="">请选择年级</option>
    {gradeOptions.map((option) => (
      <option key={option} value={option}>{option}</option>
    ))}
  </select>
</label>
```

- [ ] **Step 3: Replace the existing-class grade text input with the same fixed `<select>` control**

```tsx
<label className="space-y-2 text-sm">
  <span className="text-slate-500 dark:text-slate-400">年级</span>
  <select
    value={formState.grade}
    onChange={(e) => handleFieldChange(item.id, 'grade', e.target.value)}
    className={workspaceFieldClass}
  >
    <option value="">请选择年级</option>
    {gradeOptions.map((option) => (
      <option key={option} value={option}>{option}</option>
    ))}
  </select>
</label>
```

- [ ] **Step 4: Validate grade selection before save so invalid or blank values cannot be submitted**

```ts
if (!payload.grade || !gradeOptions.includes(payload.grade)) {
  setFormError('请选择年级');
  return;
}
```

Insert this in `handleSaveClass` after the existing name-empty guard and before the request starts.

- [ ] **Step 5: Remove the duplicate read-only teacher field from expanded class cards**

Delete this block from the existing-class form grid:

```tsx
<label className="space-y-2 text-sm">
  <span className="text-slate-500 dark:text-slate-400">负责老师</span>
  <div className={`${workspaceFieldClass} flex min-h-12 items-center`}>{teacherSummary}</div>
</label>
```

This keeps the editable teacher selector as the only teacher-management surface.

- [ ] **Step 6: Rename the editable teacher section so the page only uses `负责老师` wording**

Replace the existing heading block:

```tsx
<div>
  <h4 className="text-xl font-semibold text-slate-900 dark:text-white">负责老师</h4>
  <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">当前负责老师：{teacherSummary}，可直接更换。</p>
</div>
```

Also update the surrounding static copy so these strings no longer use `班级老师分配`:

```tsx
<p className="mt-2 max-w-3xl text-sm text-slate-500 dark:text-slate-400">
  在这里维护 {currentUser.organization_name} 的班级台账，并直接维护每个班级的负责老师，不再与账号审批页面混用。
</p>
```

```tsx
<p className="mt-1 text-sm text-slate-500 dark:text-slate-400">每次只展开一个班级卡片，在卡片内部完成基础信息维护和负责老师设置。</p>
```

```ts
setAssignmentError(err instanceof Error ? err.message : '负责老师保存失败');
```

- [ ] **Step 7: Run the focused frontend tests and confirm they now pass**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend && npx tsx --test src/workspace-navigation.test.ts src/account-card.test.tsx`

Expected: PASS with the updated wording and grade-select assertions.

- [ ] **Step 8: Run the frontend typecheck/build proof for the shipped UI**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend && npm run lint && npm run build`

Expected: `tsc --noEmit` passes and Vite build succeeds, with only the existing chunk-size warning.

- [ ] **Step 9: Commit the front-end implementation**

```bash
cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary
git add frontend/src/App.tsx frontend/src/account-card.test.tsx frontend/src/workspace-navigation.test.ts
git commit -m "feat: unify class teacher wording and grade select"
```

## Self-Review

- **Spec coverage:** The plan covers both approved requirements: one unified `负责老师` concept and fixed grade selection aligned to the top filter options. No backend changes are proposed, matching the spec boundary.
- **Placeholder scan:** No `TODO`, `TBD`, or hand-wavy “handle appropriately” instructions remain. Each task includes exact files, code, commands, and expected outcomes.
- **Type consistency:** The plan reuses existing `ClassManagementPage`, `handleSaveClass`, `handleFieldChange`, `gradeFilterOptions`, `formState`, and `newClassForm` names from the current source, and introduces only one new local constant name: `gradeOptions`.
