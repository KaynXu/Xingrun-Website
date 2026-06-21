# 咨询页面对账收纳与二次构建 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the consultation page work from memory-driven patching into a controlled audit, cleanup, rebuild, preview, and commit workflow.

**Architecture:** Keep business rules in `frontend/src/domain/consultationFlow.ts` and small domain helpers. Keep compatibility logic in focused adapters/helpers, not scattered JSX. Keep large UI chunks as components near `frontend/src/features/consultation/` instead of continuing to grow `ConsultationModal.tsx`, `ConsultationPage.tsx`, and `consultationShared.tsx`.

**Tech Stack:** React, TypeScript, Vite, Node `tsx --test`, Python unittest, Playwright/Chrome local preview, Git.

---

## Trigger Words

- `咨询对账收纳`: start Phase A, one requirement at a time.
- `咨询节点二次构建`: start Phase B only after the relevant Phase A entry is reconciled.

## Global Rules

- Do not start feature work while the requirement ledger is unclear.
- Each requirement follows: audit, locate, judge, small cleanup, test, local preview, record.
- Do not do broad refactors. Cleanup must be directly tied to the current requirement.
- Do not silently modify historical consultation records on page load.
- Do not rely only on frontend disabled states for permission behavior.
- Do not commit `data/`, `output/`, local SQLite databases, uploaded files, screenshots, or generated PDFs.
- Do not let any hand-written source file approach a 10,000-line scale. If a consultation file crosses its redline, split before adding large new UI.

## File Responsibility Map

- `docs/superpowers/audits/2026-06-16-consultation-page-reconciliation.md`: the living audit ledger, preview log, code ledger, and risk ledger.
- `docs/superpowers/plans/2026-06-16-consultation-reconcile-and-rebuild.md`: this total execution plan.
- `frontend/src/domain/consultationFlow.ts`: pure flow state, light color, current-stage, cancel, Over rules.
- `frontend/src/features/consultation/consultationTypes.ts`: consultation record/form TypeScript contracts.
- `frontend/src/features/consultation/consultationShared.tsx`: existing shared helpers/components. During this plan, move new large UI out instead of adding more here.
- `frontend/src/features/consultation/ConsultationPage.tsx`: consultation list page, filters, card actions, page-level dialogs.
- `frontend/src/features/consultation/ConsultationModal.tsx`: create/view/edit modal. During this plan, move enter-class/status/over UI out when touched.
- `frontend/src/consultation-flow-wiring.test.ts`: source-level wiring guardrails.
- `frontend/src/consultation-enter-class-dialog.test.ts`: enter-class guardrails.
- `frontend/src/consultation-transfer-scope.test.ts`: transfer visibility/editing guardrails.
- `frontend/src/domain/consultationFlow.test.ts`: pure flow behavior tests.
- `tests/test_consultation_flow.py`: backend consultation API, permission, transfer, and persistence tests.

---

### Task 0: Engineering Guardrails And Baseline Ledger

**Files:**
- Modify: `docs/superpowers/audits/2026-06-16-consultation-page-reconciliation.md`
- Modify: `docs/superpowers/plans/2026-06-16-consultation-reconcile-and-rebuild.md`

- [x] **Step 1: Record code size redlines**

Record these redlines in the audit ledger:

```text
ConsultationModal.tsx > 1500 lines: no new large UI blocks; split components first.
consultationShared.tsx > 1000 lines: no new mixed helper/UI blocks; split helper or component first.
ConsultationPage.tsx > 1200 lines: avoid new page-local dialogs; split components first.
Any hand-written source file > 3000 lines: stop feature work and split.
Any hand-written source file approaching 10000 lines: unacceptable unless generated or fixture data.
```

- [x] **Step 2: Record safety rules**

Record these safety rules in the audit ledger:

```text
Historical data is display-compatible only; do not auto-clean database rows.
Local preview data is not production truth.
Core business tests should be pure function or API tests where possible.
Frontend disabled states are not permission enforcement.
Exclude data/output/local database files before commit.
Update the audit ledger after every node.
```

- [x] **Step 3: Run baseline commands before the first execution node**

Run:

```bash
wc -l frontend/src/features/consultation/ConsultationPage.tsx frontend/src/features/consultation/ConsultationModal.tsx frontend/src/features/consultation/consultationShared.tsx frontend/src/domain/consultationFlow.ts tests/test_consultation_flow.py
git status --short
git fetch origin develop
git rev-list --left-right --count HEAD...origin/develop
```

Expected:

```text
Line counts are recorded in the audit ledger.
Git status is understood before edits.
Fetch either succeeds or its network failure is recorded.
Ahead/behind count is recorded before pull/push decisions.
```

### Task 1: Requirement Ledger And Detail Timeline

**Files:**
- Modify: `docs/superpowers/audits/2026-06-16-consultation-page-reconciliation.md`

- [ ] **Step 1: Fill the 6月9日到6月15日 detail timeline**

Run:

```bash
git log --all --since='2026-06-09 00:00:00 +0800' --until='2026-06-15 23:59:59 +0800' --date=iso --pretty=format:'%h %ad %an %s' -- frontend/src/features/consultation frontend/src/domain/consultationFlow.ts frontend/src/domain/consultationEnterClass.ts frontend/src/domain/consultationTeacherSelection.ts frontend/src/consultation-* tests/test_consultation_flow.py docs/superpowers docs/mockups
```

Update the ledger with concrete references for:

```text
lightweight create fields
homepage filter structure
left/right click and tap/long-press rules
node dialog teacher recommendation
enter-class three-card dialog
Over success/failure behavior
transfer visibility and edit scope
historical data compatibility
visual references
```

- [ ] **Step 2: Mark each requirement state**

For each row `R1` through `R12`, set one of:

```text
已完成
部分完成
未完成
延后
```

Also fill:

```text
code location
test coverage
local preview evidence
next action
```

- [ ] **Step 3: Verify no vague ledger entries remain**

Run:

```bash
rg -n "待对账|待定位|待记录|待补最终记录" docs/superpowers/audits/2026-06-16-consultation-page-reconciliation.md
```

Expected during Task 1:

```text
Matches are allowed only for requirements not yet audited.
```

After all Phase A tasks:

```text
No matches remain for requirements that were audited.
```

### Task 2: Historical Data Compatibility Audit And Cleanup

**Files:**
- Modify: `docs/superpowers/audits/2026-06-16-consultation-page-reconciliation.md`
- Modify: `frontend/src/domain/consultationFlow.ts`
- Modify: `frontend/src/domain/consultationFlow.test.ts`
- Modify: `frontend/src/features/consultation/consultationShared.tsx`
- Test: `frontend/src/domain/consultationFlow.test.ts`
- Test: `tests/test_consultation_flow.py`

- [ ] **Step 1: Audit current behavior**

Locate all legacy/terminal flow mapping code:

```bash
rg -n "成功进班|试听失败|咨询结束|closing_result|completed_stages|flow_stage|normalizeConsultationRecord|createConsultationFlowState" frontend/src/domain frontend/src/features/consultation tests/test_consultation_flow.py
```

Record in the audit ledger:

```text
which code interprets historical flow_stage
which code writes flow_stage back
whether page load writes to backend
which tests cover legacy terminal consultations
```

- [ ] **Step 2: Write failing compatibility tests if gaps exist**

Add tests to `frontend/src/domain/consultationFlow.test.ts` for legacy terminal states:

```ts
test('legacy successful result maps to a single terminal current light without rewriting skipped process stages', () => {
  const state = createConsultationFlowState({
    flowStage: '成功进班',
    completedStages: ['已加小客服微信', '待试听', '成功进班'],
    closingResult: 'success',
  });

  const lights = calculateConsultationFlowLights(state);
  assert.equal(lights.filter((item) => item.color === 'blue').length, 1);
});
```

Run:

```bash
cd frontend && npx tsx --test src/domain/consultationFlow.test.ts
```

Expected before implementation:

```text
The new compatibility assertion fails if terminal stages can produce more than one current light.
```

- [ ] **Step 3: Implement compatibility in the smallest layer**

Keep compatibility in pure functions or shared helpers:

```text
Do not add scattered JSX checks.
Do not auto-save normalized historical records on page load.
Do not delete old terminal fields while rendering.
```

- [ ] **Step 4: Verify and preview**

Run:

```bash
cd frontend && npx tsx --test src/domain/consultationFlow.test.ts src/consultation-flow-wiring.test.ts
python3 -m unittest tests.test_consultation_flow -v
```

Open local preview:

```bash
open -a "Google Chrome" "http://127.0.0.1:3000/workspace/consultation"
```

Record:

```text
admin historical consultation preview
teacher historical/transfer consultation preview
console error result
```

### Task 3: Unique Current Light And Strong Failed Over

**Files:**
- Modify: `docs/superpowers/audits/2026-06-16-consultation-page-reconciliation.md`
- Modify: `frontend/src/domain/consultationFlow.ts`
- Modify: `frontend/src/domain/consultationFlow.test.ts`
- Modify: `frontend/src/features/consultation/consultationShared.tsx`
- Test: `frontend/src/domain/consultationFlow.test.ts`
- Test: `frontend/src/consultation-flow-wiring.test.ts`

- [ ] **Step 1: Write failing tests for one-current-light rule**

Add or update tests so these cases each have exactly one terminal/current light:

```text
ordinary process current -> one blue process light
successful result current -> one blue result light, no blue process light
successful Over -> one blue Over light, no blue process/result light
failed Over -> one red Over light, no blue process/result light
```

Run:

```bash
cd frontend && npx tsx --test src/domain/consultationFlow.test.ts src/consultation-flow-wiring.test.ts
```

Expected before implementation:

```text
At least one test fails for terminal/result rendering if two current lights are possible.
```

- [ ] **Step 2: Implement a single flow-node light source**

Refactor only the touched logic:

```text
ConsultationFlowBar should derive process, result, and Over current priority from one normalized light model.
Priority: failed Over red > successful Over blue > result blue > process blue.
If a terminal/result node is current, process nodes cannot be blue.
```

- [ ] **Step 3: Make failed Over visually obvious**

Update failed Over styling:

```text
failed Over circle: solid red
failed Over center text: "!" or "×"
failed Over label: red
inactive Over: not solid red
successful Over: solid blue
```

- [ ] **Step 4: Verify and preview**

Run:

```bash
cd frontend && npx tsx --test src/domain/consultationFlow.test.ts src/consultation-flow-wiring.test.ts
cd frontend && npm run build
```

Preview desktop and mobile:

```bash
open -a "Google Chrome" "http://127.0.0.1:3000/workspace/consultation"
```

Record in the ledger:

```text
no double-blue card found
failed Over red visibility
mobile light visibility
```

### Task 4: Homepage Over Success Enter-Class Loop

**Files:**
- Modify: `docs/superpowers/audits/2026-06-16-consultation-page-reconciliation.md`
- Prefer Create: `frontend/src/features/consultation/ConsultationEnterClassDialog.tsx`
- Modify: `frontend/src/features/consultation/ConsultationModal.tsx`
- Modify: `frontend/src/features/consultation/ConsultationPage.tsx`
- Test: `frontend/src/consultation-enter-class-dialog.test.ts`
- Test: `frontend/src/consultation-flow-wiring.test.ts`

- [ ] **Step 1: Audit existing enter-class dialog ownership**

Locate:

```bash
rg -n "ConsultationEnterClassDialog|handleOverSuccess|handleInlineOverSuccess|success_class_id|success_class_manual|快速建班|转化待进班" frontend/src/features/consultation frontend/src/consultation-enter-class-dialog.test.ts frontend/src/consultation-flow-wiring.test.ts
```

Record:

```text
whether enter-class UI is modal-local
what page-level Over success currently does
which tests cover modal success
which tests cover page success
```

- [ ] **Step 2: Write failing page-level Over success test**

In `frontend/src/consultation-flow-wiring.test.ts`, add assertions that page Over success opens or uses the shared enter-class path instead of only setting an error:

```ts
assert.match(pageSource, /enterClassDialogRecord/);
assert.match(pageSource, /setEnterClassDialogRecord\(record\)/);
assert.doesNotMatch(pageSource, /咨询成功必须先选择或填写班级/);
```

Run:

```bash
cd frontend && npx tsx --test src/consultation-flow-wiring.test.ts
```

Expected:

```text
The new assertions fail until the page has a real enter-class success path.
```

- [ ] **Step 3: Extract or share enter-class UI before adding page copy**

If `ConsultationEnterClassDialog` remains inside `ConsultationModal.tsx`, extract it to:

```text
frontend/src/features/consultation/ConsultationEnterClassDialog.tsx
```

Keep the same three card labels:

```text
已有班级
快速建班
转化待进班
```

- [ ] **Step 4: Wire page Over success to the shared dialog**

Implement:

```text
Page card Over -> choose 咨询成功 -> open enter-class dialog.
Existing class / quick class / pending success -> save successful Over immediately from the card.
Cancel -> no data write.
Failure -> save failed Over immediately.
```

- [ ] **Step 5: Verify and preview**

Run:

```bash
cd frontend && npx tsx --test src/consultation-enter-class-dialog.test.ts src/consultation-flow-wiring.test.ts
cd frontend && npm run build
```

Preview:

```text
admin card Over success opens three-card dialog
cancel does not save
failure saves red Over
```

### Task 5: Stage Status Cards In View/Edit/Card Surfaces

**Files:**
- Modify: `docs/superpowers/audits/2026-06-16-consultation-page-reconciliation.md`
- Prefer Create: `frontend/src/features/consultation/ConsultationStageStatusCards.tsx`
- Modify: `frontend/src/features/consultation/ConsultationModal.tsx`
- Modify: `frontend/src/features/consultation/ConsultationPage.tsx`
- Test: `frontend/src/consultation-flow-wiring.test.ts`

- [ ] **Step 1: Audit current status display**

Locate:

```bash
rg -n "客服微信|沟通教师|测试教师|试听教师|带课教师|CheckCircle2|stageTeacherLabels|buildConsultationFlowStageTeacherLabels" frontend/src/features/consultation frontend/src/consultation-flow-wiring.test.ts
```

Record current coverage:

```text
card list status display
read modal status display
edit modal status display
transfer badge display
```

- [ ] **Step 2: Write failing source tests for status cards**

Add tests that require these display concepts:

```text
客服微信：已添加 ✓
沟通教师：x老师 ✓
测试教师：x老师 ✓
试听教师：x老师 ✓
带课教师：x老师 ✓
```

Run:

```bash
cd frontend && npx tsx --test src/consultation-flow-wiring.test.ts
```

- [ ] **Step 3: Create a focused status card component**

Create:

```text
frontend/src/features/consultation/ConsultationStageStatusCards.tsx
```

Responsibilities:

```text
derive visible stage status cards from ConsultationFormValues or ConsultationRecord
render compact card/chip UI
avoid transfer marker duplication
do not mutate form values
```

- [ ] **Step 4: Use status cards in touched surfaces**

Use the component in:

```text
ConsultationPage list cards
ConsultationModal read view
ConsultationModal edit view
```

- [ ] **Step 5: Verify and preview**

Run:

```bash
cd frontend && npx tsx --test src/consultation-flow-wiring.test.ts
cd frontend && npm run build
```

Preview:

```text
card status cards visible
modal status cards visible
transfer badge still distinct
text fits on mobile
```

### Task 6: Device-Specific Usage Reminder

**Files:**
- Modify: `docs/superpowers/audits/2026-06-16-consultation-page-reconciliation.md`
- Modify: `frontend/src/features/consultation/ConsultationPage.tsx`
- Test: `frontend/src/consultation-flow-wiring.test.ts`

- [ ] **Step 1: Write failing source test**

Require separate desktop and mobile reminder spans/classes:

```ts
assert.match(pageSource, /电脑端：左键编辑阶段状态，右键标记为当前阶段。/);
assert.match(pageSource, /Pad\\/手机：轻点编辑阶段状态，长按标记为当前阶段。/);
assert.match(pageSource, /hidden md:inline/);
assert.match(pageSource, /md:hidden/);
assert.match(pageSource, /items-center gap-2/);
```

Run:

```bash
cd frontend && npx tsx --test src/consultation-flow-wiring.test.ts
```

- [ ] **Step 2: Implement responsive reminder copy**

Update the reminder so:

```text
desktop: only desktop copy is visible
tablet/mobile: only tap/long-press copy is visible
icon and text are vertically centered
```

- [ ] **Step 3: Verify and preview**

Run:

```bash
cd frontend && npx tsx --test src/consultation-flow-wiring.test.ts
cd frontend && npm run build
```

Preview:

```text
1366px desktop shows desktop copy only
390px mobile shows mobile copy only
```

### Task 7: Existing-Class Filter Enhancement

**Files:**
- Modify: `docs/superpowers/audits/2026-06-16-consultation-page-reconciliation.md`
- Modify: `frontend/src/features/consultation/ConsultationEnterClassDialog.tsx`
- Modify: `frontend/src/features/consultation/ConsultationModal.tsx` if extraction is not complete yet
- Test: `frontend/src/consultation-enter-class-dialog.test.ts`

- [ ] **Step 1: Audit student-center filter logic 1**

Locate:

```bash
rg -n "filter|subject|stage|grade|teacher|class_type|classFilterRules|筛选" frontend/src/features/student-center frontend/src/features/consultation
```

Record:

```text
which student-center filter helpers can be reused
which consultation filters already exist
which filter fields are recommendations, not locks
```

- [ ] **Step 2: Write failing enter-class filter test**

Require:

```text
consultation subject preselects but remains editable
consultation grade preselects but remains editable
teacher/class type filters can narrow the dropdown
results remain in a dropdown, not a list
```

Run:

```bash
cd frontend && npx tsx --test src/consultation-enter-class-dialog.test.ts
```

- [ ] **Step 3: Implement only dropdown-based filter enhancement**

Add filter controls without creating a class list:

```text
subject
stage
grade
teacher if available
class type if available
class dropdown results
```

- [ ] **Step 4: Verify and preview**

Run:

```bash
cd frontend && npx tsx --test src/consultation-enter-class-dialog.test.ts
cd frontend && npm run build
```

Preview:

```text
existing class card dropdown is usable
text is not clipped
subject and grade can be changed
```

### Task 8: Transfer Visibility And Edit Scope Reconciliation

**Files:**
- Modify: `docs/superpowers/audits/2026-06-16-consultation-page-reconciliation.md`
- Modify: `frontend/src/features/consultation/ConsultationPage.tsx` only if audit finds a gap
- Modify: `frontend/src/features/consultation/ConsultationModal.tsx` only if audit finds a gap
- Test: `frontend/src/consultation-transfer-scope.test.ts`
- Test: `tests/test_consultation_flow.py`

- [ ] **Step 1: Audit transfer behavior against the ledger**

Run:

```bash
rg -n "is_transferred_consultation|assigned_stage|assignment_note|current_responsibility|can_edit_consultation|咨询转接|转接咨询只能编辑" frontend/src/features/consultation tests/test_consultation_flow.py frontend/src/consultation-transfer-scope.test.ts
```

Record:

```text
self-created visibility
transferred visibility
current responsibility display
assignment note display
frontend edit lock
backend edit lock
```

- [ ] **Step 2: Verify current tests before editing**

Run:

```bash
cd frontend && npx tsx --test src/consultation-transfer-scope.test.ts
python3 -m unittest tests.test_consultation_flow -v
```

Expected:

```text
Tests pass before any transfer refactor.
```

- [ ] **Step 3: Only patch confirmed gaps**

If the audit finds a gap, patch only that gap. Do not implement:

```text
real message push
full historical assignment timeline
学管中心 permission changes
class sorting changes
```

- [ ] **Step 4: Verify and preview**

Run:

```bash
cd frontend && npx tsx --test src/consultation-transfer-scope.test.ts
python3 -m unittest tests.test_consultation_flow -v
cd frontend && npm run build
```

Preview:

```text
admin can see/edit full flow
何姝健 can see self-created and transferred consultation
transferred earlier stages are non-editable
```

### Task 9: Final Audit, Preview, And Safe Commit Point

**Files:**
- Modify: `docs/superpowers/audits/2026-06-16-consultation-page-reconciliation.md`

- [ ] **Step 1: Run full relevant verification**

Run:

```bash
cd frontend && npx tsx --test src/domain/consultationFlow.test.ts src/consultation-flow-wiring.test.ts src/consultation-enter-class-dialog.test.ts src/consultation-transfer-scope.test.ts
python3 -m unittest tests.test_consultation_flow -v
cd frontend && npm run build
```

Expected:

```text
All listed frontend tests pass.
Backend consultation flow tests pass.
Vite build exits 0.
Warnings are recorded if present.
```

- [ ] **Step 2: Run local preview audit**

Preview:

```text
admin consultation page
何姝健 consultation page
self-created consultation card
transferred consultation card
historical terminal consultation
manual Over success
manual Over failure
mobile viewport flow bar
```

Record:

```text
URL
account/view
what was clicked
whether data was saved
console errors
visual observations
```

- [ ] **Step 3: Check commit scope**

Run:

```bash
git status --short
git diff --name-only
```

Allowed commit paths:

```text
docs/superpowers/audits/
docs/superpowers/plans/
docs/superpowers/specs/
frontend/src/
tests/test_consultation_flow.py
app.py
lesson_manager.py
```

Excluded paths:

```text
data/
output/
*.db
*.zip
uploaded PDFs/images
```

- [ ] **Step 4: Create safe commit point after user confirmation**

Ask before committing. If confirmed:

```bash
git add docs/superpowers/audits/2026-06-16-consultation-page-reconciliation.md docs/superpowers/plans/2026-06-16-consultation-reconcile-and-rebuild.md docs/superpowers/specs frontend/src tests/test_consultation_flow.py app.py lesson_manager.py
git status --short
git commit -m "chore: reconcile consultation flow rebuild"
```

Expected:

```text
Only source, test, and docs files are staged.
No data/output/local database files are staged.
Commit succeeds.
```

---

## Deferred And Frozen For This Plan

These are recorded but not implemented in this plan:

- Real message push to teacher accounts.
- Full assignment history timeline.
- 学管中心 permission changes.
- Teacher class overview changes.
- Class/student sorting changes.
- Reintroducing a full consultation workbench.
- Large visual redesign of consultation modal layout.

## Execution Checkpoint

Before executing any task, restate which task is being started and which requirement row it updates in the audit ledger. After each task, update the ledger, run the listed verification, preview locally when required, and report the result before moving on.
