# Consultation Flow Selective Rollback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Roll back the over-complex consultation flow UI and interaction layers while preserving the accepted consultation page structure, student-center permission work, and ordering work.

**Architecture:** Treat this as a selective rollback, not a repository reset. Use commit `43c082b` as the reference for the pre-complex-flow frontend state, then re-apply only the accepted consultation list/filter structure from current `HEAD`. Do not touch local data files, uploaded PDFs, or unrelated student-center/class-management code.

**Tech Stack:** React/TypeScript in `frontend/src/App.tsx`, Node test runner via `npx tsx --test`, Vite build via `npm run build`, Python/Flask backend left unchanged in the first rollback pass.

---

### Task 1: Freeze The Rollback Boundary

**Files:**
- Modify: `frontend/src/account-card.test.tsx`
- Reference only: `frontend/src/App.tsx`

- [x] **Step 1: Write tests that define what must be removed**

Add or update source-level tests in `frontend/src/account-card.test.tsx` so the consultation page no longer contains the complex 2/3/6 layers:

```ts
test('consultation page removes complex flow card interactions for rollback', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const consultationPageBlock = source.match(/const ConsultationPage = \([\s\S]*?\n};/);

  assert.ok(consultationPageBlock);
  assert.doesNotMatch(source, /const ConsultationFlowBar = \(/);
  assert.doesNotMatch(source, /flowNodeActionRecord/);
  assert.doesNotMatch(source, /flowNodeActionKey/);
  assert.doesNotMatch(source, /flowNodeActionRecommendedTeacherId/);
  assert.doesNotMatch(source, /enterClassRecord/);
  assert.doesNotMatch(source, /overResultDialogRecord/);
  assert.doesNotMatch(source, /ConsultationTeacherStatusPill/);
  assert.doesNotMatch(consultationPageBlock[0], /renderInlineFlow\(record, busy\)/);
});
```

- [x] **Step 2: Write tests that define what must remain**

Keep tests that assert accepted structure:

```ts
test('consultation rollback keeps accepted filter structure and default pending list', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const consultationPageBlock = source.match(/const ConsultationPage = \([\s\S]*?\n};/);

  assert.ok(consultationPageBlock);
  assert.match(consultationPageBlock[0], /useState<ConsultationFilterKey>\('pending'\)/);
  assert.match(source, /const consultationFilterGroups/);
  assert.match(source, /待咨询/);
  assert.match(source, /已结束/);
  assert.match(source, /咨询成功/);
  assert.match(source, /咨询失败/);
  assert.match(consultationPageBlock[0], /当前暂无待处理咨询。/);
});
```

- [x] **Step 3: Run the tests to verify they fail for the right reason**

Run:

```bash
cd frontend
npx tsx --test src/account-card.test.tsx 2>&1 | rg "complex flow card|accepted filter|not ok|# fail|# pass|# tests"
```

Expected: the removal test fails because current `App.tsx` still contains `ConsultationFlowBar`, `flowNodeAction...`, `enterClassRecord`, `overResultDialogRecord`, and `ConsultationTeacherStatusPill`.

### Task 2: Remove Complex Flow Card UI And Node Dialogs

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/account-card.test.tsx`

- [x] **Step 1: Remove flow card component and helpers**

In `frontend/src/App.tsx`, remove the complex flow card layer introduced after `43c082b`:

```ts
// Remove these definitions entirely:
const ConsultationFlowBar = (...)
const ConsultationResultCapsule = (...)
function getLastConsultationFlowStage(...)
function consultationStageHasExplicitEvidence(...)
function filterExplicitConsultationCompletedStages(...)
function markConsultationFlowStageDone(...)
function setConsultationFlowCurrentStage(...)
function unsetConsultationFlowStage(...)
function applyConsultationFlowNodeAction(...)
```

Keep the basic existing consultation form fields and generic helpers if still used by the edit modal:

```ts
toggleConsultationStage
toggleConsultationStageLight
moveConsultationStage
setConsultationResultStage
clearConsultationResultStage
deriveConsultationFlowFromFields
```

- [x] **Step 2: Remove consultation page flow-node state**

In `ConsultationPage`, remove these states and related functions:

```ts
const [flowNodeActionRecord, setFlowNodeActionRecord] = useState<ConsultationRecord | null>(null);
const [flowNodeActionKey, setFlowNodeActionKey] = useState<ConsultationFlowCardNodeKey | null>(null);
const [flowNodeActionNote, setFlowNodeActionNote] = useState('');
const [flowNodeActionTeacherId, setFlowNodeActionTeacherId] = useState('');
const [flowNodeActionRecommendedTeacherId, setFlowNodeActionRecommendedTeacherId] = useState('');
const [flowNodeActionTeacherTouched, setFlowNodeActionTeacherTouched] = useState(false);
const [flowNodeActionMoveCurrent, setFlowNodeActionMoveCurrent] = useState(false);
```

Remove all functions that exist only for those states:

```ts
addCompletedStage
getFlowNodeActionNote
findConsultationTeacherOption
getTeacherSelectValue
getFlowNodeTeacherLabel
getFlowNodeConfirmedTeacherValue
getFlowNodeRecommendedTeacherValue
getFlowNodeSelectedTeacherName
getFlowNodeRecommendedTeacherName
flowNodeActionTeacherIsListed
flowNodeActionRecommendedTeacherIsListed
consultationStageToFlowNodeKey
openConsultationFlowNode
closeFlowNodeActionDialog
handleSaveFlowNodeAction
```

- [x] **Step 3: Remove flow-node dialog JSX**

Delete the `<AnimatePresence>` branch guarded by:

```tsx
{flowNodeActionRecord && flowNodeActionKey && (...)}
```

- [x] **Step 4: Replace card flow surfaces with simple status text**

In `renderDesktopConsultationCard`, `renderPadConsultationCard`, and `renderMobileConsultationCard`, remove:

```tsx
{renderInlineFlow(record, busy)}
```

Replace with a compact status badge using existing record fields:

```tsx
<span className="inline-flex items-center rounded-full bg-sky-50 px-2.5 py-1 text-xs font-bold text-sky-700 dark:bg-sky-400/10 dark:text-sky-100">
  {record.flow_stage || '待跟进'}
</span>
```

- [x] **Step 5: Run frontend source tests**

Run:

```bash
cd frontend
npx tsx --test src/account-card.test.tsx 2>&1 | rg "complex flow card|accepted filter|not ok|# fail|# pass|# tests"
```

Expected: the rollback tests from Task 1 pass. Existing unrelated class-management source tests may still fail; note them separately.

### Task 3: Roll Back Flow Status Display Sync In View/Edit Cards

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/account-card.test.tsx`

- [x] **Step 1: Remove teacher status pill component**

Delete:

```ts
const ConsultationTeacherStatusPill = (...)
```

- [x] **Step 2: Remove status pill usage from read-only report**

In `ConsultationReadOnlyReport`, remove status pill rows such as:

```tsx
<ConsultationTeacherStatusPill label="客服老师" teacher={form.customer_service_teacher} />
<ConsultationTeacherStatusPill label="沟通教师" teacher={form.receiving_teacher} />
<ConsultationTeacherStatusPill label="测试教师" teacher={form.test_teacher} />
<ConsultationTeacherStatusPill label="试听教师" teacher={form.trial_teacher} />
<ConsultationTeacherStatusPill label="带教教师" teacher={form.teaching_teacher} />
```

Keep the plain textual consultation fields that existed before the sync work.

- [x] **Step 3: Remove status pill usage from edit modal**

In `ConsultationModal`, remove the same `ConsultationTeacherStatusPill` usages. Keep the base assignment fields such as:

```tsx
接待教师：
aria-label="选择接待教师"
```

- [x] **Step 4: Update tests**

Remove or replace tests that assert:

```ts
assert.match(source, /const ConsultationTeacherStatusPill = \(/);
assert.match(reportBlock[0], /客服老师[\s\S]*form\.customer_service_teacher/);
assert.match(modalBlock[0], /测试教师[\s\S]*form\.test_teacher/);
```

Add the replacement assertion:

```ts
assert.doesNotMatch(source, /ConsultationTeacherStatusPill/);
assert.match(modalBlock[0], /接待教师：/);
```

### Task 4: Roll Back Enter-Class And Over Dialog UI For Now

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/account-card.test.tsx`

- [x] **Step 1: Remove enter-class dialog state and UI**

Remove:

```ts
const [enterClassRecord, setEnterClassRecord] = useState<ConsultationRecord | null>(null);
const [enterClassMode, setEnterClassMode] = useState(...)
const [enterClassId, setEnterClassId] = useState(...)
const [enterClassNewType, setEnterClassNewType] = useState(...)
...
openEnterClassDialog
closeEnterClassDialog
handleConfirmEnterClass
```

Remove the JSX branch:

```tsx
{enterClassRecord && (...)}
```

- [x] **Step 2: Remove over result dialog state and UI**

Remove:

```ts
const [overResultDialogRecord, setOverResultDialogRecord] = useState<ConsultationRecord | null>(null);
handleCloseConsultationWithResult
```

Remove the JSX branch:

```tsx
{overResultDialogRecord && (...)}
```

- [x] **Step 3: Restore simple end consultation action**

Keep or restore the simple end action:

```ts
const handleInlineEndConsultation = async (record: ConsultationRecord) => {
  if (!canEditConsultations || isBusy || isConsultationEnded(record.flow_stage)) return;
  setError('');
  const values = endConsultationValues(toConsultationFormValues(record));
  await saveInlineConsultationUpdate(record, values, '结束咨询失败');
};
```

Cards can continue to show the existing edit/view/delete controls. Do not add a new Over button in this rollback pass unless it already existed outside the complex flow card.

- [x] **Step 4: Leave backend enter-class API unchanged in this pass**

Do not edit:

```text
lesson_manager.py
tests/test_consultation_flow.py
```

Reason: frontend rollback can be verified independently; backend conversion endpoints can be kept dormant until the redesigned enter-class UI returns.

### Task 5: Preserve Accepted Consultation Page Structure

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/account-card.test.tsx`

- [x] **Step 1: Keep filter groups and default pending state**

Ensure `ConsultationPage` still has:

```ts
const [activeFilter, setActiveFilter] = useState<ConsultationFilterKey>('pending');
```

Keep the accepted top filter labels:

```text
待咨询
一周内
一月内
30天+
已结束
咨询成功
咨询失败
```

- [x] **Step 2: Keep usage reminder copy**

Keep the device-specific usage reminder if it still makes sense after flow rollback, or simplify it to avoid referencing removed left/right flow behavior:

```tsx
<span>使用提醒：点击卡片可查看或编辑咨询记录。</span>
```

If the flow graph is removed, do not keep copy that says "左键编辑状态，右键备注正在此阶段".

- [x] **Step 3: Keep consultation list layouts**

Keep the accepted responsive list split:

```tsx
<div className="grid gap-4 p-4 sm:p-5 md:hidden">
<div className="hidden md:block xl:hidden">
<div className="hidden xl:block">
```

### Task 6: Verify And Preview

**Files:**
- Verify only: `frontend/src/App.tsx`
- Verify only: `frontend/src/account-card.test.tsx`

- [x] **Step 1: Run focused frontend tests**

Run:

```bash
cd frontend
npx tsx --test src/account-card.test.tsx 2>&1 | rg "consultation|not ok|# fail|# pass|# tests"
```

Expected: consultation rollback tests pass. If the existing class-management source tests still fail, report them as unrelated existing failures.

- [x] **Step 2: Run production build**

Run:

```bash
cd frontend
npm run build
```

Expected:

```text
✓ built
```

Vite chunk-size warnings are acceptable if no build error occurs.

- [x] **Step 3: Refresh local preview**

Run:

```bash
open http://localhost:3001/
```

Expected: local preview opens. Consultation page should show the accepted list/filter structure without complex flow graph, node popovers, enter-class modal, Over result modal, or teacher status pills.

- [x] **Step 4: Commit only relevant files**

Run:

```bash
git status --short
git add frontend/src/App.tsx frontend/src/account-card.test.tsx
git commit --amend --no-edit
```

Expected: only `frontend/src/App.tsx` and `frontend/src/account-card.test.tsx` are amended. Leave untracked local data/PDF files untouched.

---

## Self-Review

**Spec coverage:** This plan rolls back items 2, 3, and 6 on the frontend, and disables current frontend implementations of items 4 and 5 without touching backend conversion endpoints. It preserves items 1, 7, and 8 by avoiding unrelated page, permission, and ordering code.

**Placeholder scan:** No TBD/TODO placeholders remain. Each task names exact files, symbols, and verification commands.

**Type consistency:** All named symbols are current `frontend/src/App.tsx` symbols from `HEAD` unless explicitly marked as removal targets.
