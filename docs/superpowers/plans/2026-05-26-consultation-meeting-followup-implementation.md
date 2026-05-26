# Consultation Meeting Followup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the consultation meeting workbench with clearer pending/processed filters, direct local processing, OVER-only card interaction, end-time filtering, teacher picker popover, and compact sidebar tooltips.

**Architecture:** Keep the existing consultation UI in `frontend/src/App.tsx` and extend the existing Flask/SQLite consultation model in `lesson_manager.py`. Add one backend field for consultation terminal time, keep direct processed state local to the meeting workbench, and reuse existing frontend source tests plus backend consultation flow tests.

**Tech Stack:** Flask, SQLite, React, TypeScript, Framer Motion, Node `tsx --test`, Python `unittest`.

---

## File Map

- Modify `lesson_manager.py`: add `ended_at` storage, serialization, migration, and terminal-stage stamping.
- Modify `app.py`: no new routes expected; existing consultation update API should return the new field through manager serialization.
- Modify `tests/test_consultation_flow.py`: backend coverage for end time creation, preservation, legacy records, and OVER update semantics.
- Modify `frontend/src/App.tsx`: meeting workbench state, filters, direct processed button, card animation, teacher popover, OVER-only flow bar, compact sidebar tooltip.
- Modify `frontend/src/account-card.test.tsx`: source-level coverage for meeting workbench and sidebar behavior.
- Modify `frontend/src/workspace-navigation.test.ts`: source-level coverage for compact sidebar labels if needed.

## Task 1: Backend End Time Field

**Files:**
- Modify: `lesson_manager.py`
- Test: `tests/test_consultation_flow.py`

- [ ] **Step 1: Write failing backend tests**

Add tests to `tests/test_consultation_flow.py` inside `ConsultationFlowTestCase`:

```python
def test_terminal_consultation_records_ended_at_once(self):
    created = self.create_consultation_record(flow_stage="待试听", completed_stages=["已加小客服微信", "待试听"])
    first = self.client.put(
        f"/api/consultations/{created['id']}",
        headers=self.auth_headers(self.owner_token),
        json={"flow_stage": "咨询结束", "completed_stages": ["已加小客服微信", "待试听"]},
    )
    self.assertEqual(first.status_code, 200)
    first_payload = first.get_json()
    self.assertTrue(first_payload["ended_at"])
    self.assertEqual(first_payload["completed_stages"], ["已加小客服微信", "待试听", "咨询结束"])

    second = self.client.put(
        f"/api/consultations/{created['id']}",
        headers=self.auth_headers(self.owner_token),
        json={"end_note": "补充说明"},
    )
    self.assertEqual(second.status_code, 200)
    second_payload = second.get_json()
    self.assertEqual(second_payload["ended_at"], first_payload["ended_at"])

def test_legacy_terminal_consultation_without_ended_at_stays_blank(self):
    created = self.create_consultation_record(flow_stage="成功进班", completed_stages=["成功进班"])
    with lesson_manager.get_db() as conn:
        conn.execute("UPDATE consultations SET ended_at='' WHERE id=?", (created["id"],))
    response = self.client.get(f"/api/consultations/{created['id']}", headers=self.auth_headers(self.owner_token))
    self.assertEqual(response.status_code, 200)
    self.assertEqual(response.get_json()["ended_at"], "")
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
python3 -m unittest tests.test_consultation_flow.ConsultationFlowTestCase.test_terminal_consultation_records_ended_at_once tests.test_consultation_flow.ConsultationFlowTestCase.test_legacy_terminal_consultation_without_ended_at_stays_blank -v
```

Expected: fail because `ended_at` is not returned or persisted.

- [ ] **Step 3: Implement `ended_at`**

In `lesson_manager.py`:

```python
CONSULTATION_TERMINAL_STAGES = {"成功进班", "咨询结束"}
```

Add `ended_at` to `CONSULTATION_FIELD_MAP`, `CONSULTATION_STORAGE_FIELDS`, public serialization, and the `consultations` table migration:

```python
_ensure_column(conn, "consultations", "ended_at", "TEXT DEFAULT ''")
```

When normalizing storage in `_consultation_row_to_storage`, set `ended_at` only when entering a terminal stage and no end time exists:

```python
existing_ended_at = str(row.get("ended_at") or "").strip()
flow_stage = serialized["flow_stage"]
if flow_stage in CONSULTATION_TERMINAL_STAGES and not existing_ended_at:
    serialized["ended_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
else:
    serialized["ended_at"] = existing_ended_at
```

Ensure create and update SQL include `ended_at`.

- [ ] **Step 4: Verify backend tests pass**

Run the same two-test command. Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add lesson_manager.py tests/test_consultation_flow.py
git commit -m "feat: track consultation terminal time"
```

## Task 2: Workbench Filter Model

**Files:**
- Modify: `frontend/src/App.tsx`
- Test: `frontend/src/account-card.test.tsx`

- [ ] **Step 1: Write source tests**

Add a test to `frontend/src/account-card.test.tsx`:

```ts
test('consultation meeting workbench has lighter secondary filters and terminal age filters', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const workbenchBlock = source.match(/const ConsultationMeetingWorkbench = \([\s\S]*?\n};/);
  assert.ok(workbenchBlock);
  assert.match(workbenchBlock[0], /const \[pendingStatusFilter, setPendingStatusFilter\] = useState<'active' \| 'ended'>\('active'\);/);
  assert.match(workbenchBlock[0], /const \[pendingEndedAgeFilter, setPendingEndedAgeFilter\] = useState<'7' \| '30' \| 'over30'>\('over30'\);/);
  assert.match(workbenchBlock[0], /getMeetingEndedAgeBucket/);
  assert.match(workbenchBlock[0], /一周内/);
  assert.match(workbenchBlock[0], /一月内/);
  assert.match(workbenchBlock[0], /30天\+/);
});
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
cd frontend && npx tsx --test src/account-card.test.tsx
```

Expected: fail on missing state names/functions.

- [ ] **Step 3: Implement filter state and helpers**

In `ConsultationMeetingWorkbench`, add:

```tsx
const [pendingStatusFilter, setPendingStatusFilter] = useState<'active' | 'ended'>('active');
const [processedStatusFilter, setProcessedStatusFilter] = useState<'active' | 'ended'>('active');
const [pendingEndedAgeFilter, setPendingEndedAgeFilter] = useState<'7' | '30' | 'over30'>('over30');
const [processedEndedAgeFilter, setProcessedEndedAgeFilter] = useState<'7' | '30' | 'over30'>('over30');
```

Add helpers near existing consultation date helpers:

```tsx
function getMeetingEndedAgeBucket(record: ConsultationRecord, todayIso: string): '7' | '30' | 'over30' {
  const endedAt = (record.ended_at || '').trim();
  if (!endedAt) return 'over30';
  const endedDate = endedAt.slice(0, 10);
  const endedTime = Date.parse(`${endedDate}T12:00:00`);
  const todayTime = Date.parse(`${todayIso}T12:00:00`);
  if (!Number.isFinite(endedTime) || !Number.isFinite(todayTime)) return 'over30';
  const ageDays = Math.max(0, Math.floor((todayTime - endedTime) / 86_400_000));
  if (ageDays <= 7) return '7';
  if (ageDays <= 30) return '30';
  return 'over30';
}
```

Use `isConsultationEnded(record.flow_stage) || isConsultationResultStage(record.flow_stage)` for ended buckets.

- [ ] **Step 4: Replace identical secondary tab UI with lightweight chips**

Add a local render helper:

```tsx
const renderMeetingSecondaryFilters = (
  statusValue: 'active' | 'ended',
  setStatusValue: (value: 'active' | 'ended') => void,
  ageValue: '7' | '30' | 'over30',
  setAgeValue: (value: '7' | '30' | 'over30') => void,
  counts: { active: number; ended: number; ended7: number; ended30: number; endedOver30: number },
) => (
  <div className="mb-4 flex flex-col gap-2 rounded-2xl border border-[#D9EEF7] bg-[#F9FDFF] px-3 py-3 dark:border-white/10 dark:bg-white/[0.03]">
    <div className="flex flex-wrap items-center gap-2">
      {[
        { key: 'active' as const, label: '待咨询', count: counts.active },
        { key: 'ended' as const, label: '已结束', count: counts.ended },
      ].map((item) => (
        <button type="button" key={item.key} onClick={() => setStatusValue(item.key)} className={cn('h-8 rounded-full border px-3 text-xs font-bold transition', statusValue === item.key ? 'border-sky-200 bg-sky-500 text-white' : 'border-sky-100 bg-white text-slate-600 hover:bg-sky-50 dark:border-white/10 dark:bg-white/5 dark:text-slate-300')}>
          {item.label} {item.count}
        </button>
      ))}
    </div>
    {statusValue === 'ended' && (
      <div className="flex flex-wrap items-center gap-2 pl-0 sm:pl-2">
        {[
          { key: '7' as const, label: '一周内', count: counts.ended7 },
          { key: '30' as const, label: '一月内', count: counts.ended30 },
          { key: 'over30' as const, label: '30天+', count: counts.endedOver30 },
        ].map((item) => (
          <button type="button" key={item.key} onClick={() => setAgeValue(item.key)} className={cn('h-7 rounded-full border px-2.5 text-[11px] font-bold transition', ageValue === item.key ? 'border-emerald-200 bg-emerald-500 text-white' : 'border-slate-200 bg-white text-slate-500 hover:bg-slate-50 dark:border-white/10 dark:bg-white/5 dark:text-slate-300')}>
            {item.label} {item.count}
          </button>
        ))}
      </div>
    )}
  </div>
);
```

- [ ] **Step 5: Verify frontend source test passes**

Run `cd frontend && npx tsx --test src/account-card.test.tsx`. Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/App.tsx frontend/src/account-card.test.tsx
git commit -m "feat: add meeting workbench secondary filters"
```

## Task 3: Direct Local Processing and Card Animation

**Files:**
- Modify: `frontend/src/App.tsx`
- Test: `frontend/src/account-card.test.tsx`

- [ ] **Step 1: Write source test**

Add:

```ts
test('consultation meeting workbench supports direct local processing with animation', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const workbenchBlock = source.match(/const ConsultationMeetingWorkbench = \([\s\S]*?\n};/);
  assert.ok(workbenchBlock);
  assert.match(workbenchBlock[0], /const \[processingCardIds, setProcessingCardIds\] = useState<Set<number>>\(\(\) => new Set\(\)\);/);
  assert.match(workbenchBlock[0], /handleMarkMeetingRecordProcessed/);
  assert.match(workbenchBlock[0], /aria-label="标记为已处理"/);
  assert.match(workbenchBlock[0], /AnimatePresence/);
});
```

- [ ] **Step 2: Run and verify failure**

Run `cd frontend && npx tsx --test src/account-card.test.tsx`. Expected: fail.

- [ ] **Step 3: Implement local processing**

In `ConsultationMeetingWorkbench`:

```tsx
const [processingCardIds, setProcessingCardIds] = useState<Set<number>>(() => new Set());

const handleMarkMeetingRecordProcessed = (record: ConsultationRecord) => {
  setProcessingCardIds((current) => new Set(current).add(record.id));
  window.setTimeout(() => {
    setProcessedIds((current) => new Set(current).add(record.id));
    setProcessingCardIds((current) => {
      const next = new Set(current);
      next.delete(record.id);
      return next;
    });
  }, 180);
};
```

Add a button immediately after the edit button in `renderMeetingIconActions`:

```tsx
<button type="button" onClick={() => handleMarkMeetingRecordProcessed(record)} className="flex h-8 w-8 items-center justify-center rounded-full border border-emerald-200 bg-emerald-50 text-emerald-700 transition hover:bg-emerald-100 dark:border-emerald-400/20 dark:bg-emerald-500/10 dark:text-emerald-200" aria-label="标记为已处理" title="标记为已处理">
  <CheckCircle2 size={13} />
</button>
```

Wrap card articles with `motion.article` and add:

```tsx
animate={processingCardIds.has(record.id) ? { opacity: 0, height: 0, x: 24, marginTop: 0, marginBottom: 0 } : { opacity: 1, height: 'auto', x: 0 }}
transition={{ duration: 0.18 }}
```

- [ ] **Step 4: Verify**

Run `cd frontend && npx tsx --test src/account-card.test.tsx`. Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.tsx frontend/src/account-card.test.tsx
git commit -m "feat: add direct meeting card processing"
```

## Task 4: OVER-Only Meeting Flow Interaction

**Files:**
- Modify: `frontend/src/App.tsx`
- Test: `frontend/src/account-card.test.tsx`

- [ ] **Step 1: Write source test**

Add:

```ts
test('meeting workbench flow only allows double clicking over', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const workbenchBlock = source.match(/const ConsultationMeetingWorkbench = \([\s\S]*?\n};/);
  assert.ok(workbenchBlock);
  assert.match(workbenchBlock[0], /handleMeetingOverDoubleClick/);
  assert.match(workbenchBlock[0], /onOverDoubleClick/);
  assert.doesNotMatch(workbenchBlock[0], /onStageDoubleClick/);
});
```

- [ ] **Step 2: Run and verify failure**

Run `cd frontend && npx tsx --test src/account-card.test.tsx`. Expected: fail.

- [ ] **Step 3: Extend `ConsultationFlowBar` props**

Add optional prop:

```tsx
onOverDoubleClick?: () => void;
```

Attach it only to the OVER node button:

```tsx
onDoubleClick={node.key === 'over' ? onOverDoubleClick : undefined}
```

Do not add double-click handlers to other nodes in meeting mode.

- [ ] **Step 4: Implement workbench handler**

In `ConsultationMeetingWorkbench`:

```tsx
const handleMeetingOverDoubleClick = (record: ConsultationRecord) => {
  const values = endConsultationValues(toConsultationFormValues(record));
  setDraftsById((current) => ({ ...current, [record.id]: values }));
  setProcessingCardIds((current) => new Set(current).add(record.id));
  window.setTimeout(() => {
    setProcessedIds((current) => new Set(current).add(record.id));
    setProcessingCardIds((current) => {
      const next = new Set(current);
      next.delete(record.id);
      return next;
    });
  }, 180);
};
```

Pass:

```tsx
<ConsultationFlowBar mode="list" stage={record.flow_stage} completedStages={record.completed_stages} editable={false} showOver overDisabled={false} onOverDoubleClick={() => handleMeetingOverDoubleClick(record)} />
```

- [ ] **Step 5: Verify backend and frontend targeted tests**

Run:

```bash
cd frontend && npx tsx --test src/account-card.test.tsx
python3 -m unittest tests.test_consultation_flow -v
```

Expected: frontend source tests pass; backend consultation tests pass.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/App.tsx frontend/src/account-card.test.tsx
git commit -m "feat: restrict meeting flow updates to over"
```

## Task 5: Teacher Popover and Class Coupling

**Files:**
- Modify: `frontend/src/App.tsx`
- Test: `frontend/src/account-card.test.tsx`

- [ ] **Step 1: Write source test**

Add:

```ts
test('meeting teacher filter uses popover chips grouped by subject', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const workbenchBlock = source.match(/const ConsultationMeetingWorkbench = \([\s\S]*?\n};/);
  assert.ok(workbenchBlock);
  assert.match(workbenchBlock[0], /teacherFilterOpen/);
  assert.match(workbenchBlock[0], /classFilterOpen/);
  assert.match(workbenchBlock[0], /filteredMeetingClasses/);
  assert.match(workbenchBlock[0], /全部教师/);
  assert.match(workbenchBlock[0], /全部班级/);
  assert.match(workbenchBlock[0], /数学/);
  assert.match(workbenchBlock[0], /物理/);
  assert.doesNotMatch(workbenchBlock[0], /<select value=\{teacherFilter\}/);
});
```

- [ ] **Step 2: Run and verify failure**

Run `cd frontend && npx tsx --test src/account-card.test.tsx`. Expected: fail.

- [ ] **Step 3: Replace select with popover**

Add:

```tsx
const [teacherFilterOpen, setTeacherFilterOpen] = useState(false);
const [classFilterOpen, setClassFilterOpen] = useState(false);
const [classFilter, setClassFilter] = useState<number | null>(null);
const selectedTeacherLabel = teacherFilter
  ? consultationTeachers.find((item) => item.teacher_id === teacherFilter)?.display_name || teacherFilter
  : '全部教师';
const selectedClassLabel = classFilter
  ? classes.find((item) => item.id === classFilter)?.name || '已选班级'
  : '全部班级';
```

Build groups from records:

```tsx
const meetingTeacherGroups = useMemo(() => {
  const groups: Record<'数学' | '物理', ConsultationTeacherOption[]> = { 数学: [], 物理: [] };
  for (const teacher of consultationTeachers) {
    const teacherRecords = records.filter((record) => record.teacher_id === teacher.teacher_id || record.receiving_teacher === teacher.display_name);
    if (teacherRecords.some((record) => record.consultation_subject.includes('数学'))) groups.数学.push(teacher);
    if (teacherRecords.some((record) => record.consultation_subject.includes('物理'))) groups.物理.push(teacher);
  }
  return groups;
}, [consultationTeachers, records]);
```

Build class options from the selected teacher. The class list comes from `/api/classes`, whose rows already include `teacher_user_id` and teacher metadata in the current class-management flow:

```tsx
const filteredMeetingClasses = useMemo(() => {
  if (!teacherFilter) return classes;
  const selectedTeacher = consultationTeachers.find((item) => item.teacher_id === teacherFilter);
  const teacherName = selectedTeacher?.display_name || teacherFilter;
  return classes.filter((item) => item.teacher_name === teacherName || String(item.teacher_user_id || '') === teacherFilter);
}, [classes, consultationTeachers, teacherFilter]);
```

Whenever the teacher changes, clear an incompatible class filter:

```tsx
useEffect(() => {
  if (classFilter && !filteredMeetingClasses.some((item) => item.id === classFilter)) {
    setClassFilter(null);
  }
}, [classFilter, filteredMeetingClasses]);
```

Render a button and absolute popover:

```tsx
<div className="relative">
  <button type="button" onClick={() => setTeacherFilterOpen((open) => !open)} className={`${consultationInputClass} flex h-10 w-full items-center justify-between px-3 text-sm`}>
    {selectedTeacherLabel}
    <ChevronDown size={14} />
  </button>
  {teacherFilterOpen && (
    <div className="absolute right-0 top-12 z-30 w-72 rounded-2xl border border-[#D9EEF7] bg-white p-3 shadow-[0_18px_45px_rgba(31,42,68,0.14)] dark:border-white/10 dark:bg-slate-900">
      <button type="button" onClick={() => { setTeacherFilter(''); setTeacherFilterOpen(false); }} className="mb-3 h-8 rounded-full bg-sky-50 px-3 text-xs font-bold text-sky-700">全部教师</button>
      {(['数学', '物理'] as const).map((subject) => (
        <div key={subject} className="mt-2">
          <p className="text-[11px] font-bold text-slate-400">{subject}</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {meetingTeacherGroups[subject].map((teacher) => (
              <button key={`${subject}-${teacher.teacher_id}`} type="button" onClick={() => { setTeacherFilter(teacher.teacher_id); setTeacherFilterOpen(false); }} className="rounded-full border border-sky-100 bg-white px-3 py-1.5 text-xs font-bold text-slate-600 hover:bg-sky-50 dark:border-white/10 dark:bg-white/5 dark:text-slate-300">
                {teacher.display_name}
              </button>
            ))}
          </div>
        </div>
      ))}
    </div>
  )}
</div>
```

Render the class popover beside it:

```tsx
<div className="relative">
  <button type="button" onClick={() => setClassFilterOpen((open) => !open)} className={`${consultationInputClass} flex h-10 w-full items-center justify-between px-3 text-sm`}>
    {selectedClassLabel}
    <ChevronDown size={14} />
  </button>
  {classFilterOpen && (
    <div className="absolute right-0 top-12 z-30 w-80 rounded-2xl border border-[#D9EEF7] bg-white p-3 shadow-[0_18px_45px_rgba(31,42,68,0.14)] dark:border-white/10 dark:bg-slate-900">
      <button type="button" onClick={() => { setClassFilter(null); setClassFilterOpen(false); }} className="mb-3 h-8 rounded-full bg-sky-50 px-3 text-xs font-bold text-sky-700">全部班级</button>
      <div className="flex max-h-72 flex-wrap gap-2 overflow-y-auto">
        {filteredMeetingClasses.map((item) => (
          <button key={item.id} type="button" onClick={() => { setClassFilter(item.id); setClassFilterOpen(false); }} className="rounded-full border border-sky-100 bg-white px-3 py-1.5 text-xs font-bold text-slate-600 hover:bg-sky-50 dark:border-white/10 dark:bg-white/5 dark:text-slate-300">
            {item.name}
          </button>
        ))}
      </div>
    </div>
  )}
</div>
```

Apply `classFilter` after teacher filtering:

```tsx
if (classFilter && record.success_class_id !== classFilter && record.trial_class_id !== classFilter) {
  return false;
}
```

- [ ] **Step 4: Verify**

Run `cd frontend && npx tsx --test src/account-card.test.tsx`. Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.tsx frontend/src/account-card.test.tsx
git commit -m "feat: add meeting teacher popover filter"
```

## Task 6: Compact Sidebar Tooltip

**Files:**
- Modify: `frontend/src/App.tsx`
- Test: `frontend/src/account-card.test.tsx`

- [ ] **Step 1: Write source test**

Add:

```ts
test('compact sidebar shows immediate labels on hover and focus', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const sidebarBlock = source.match(/const Sidebar = \([\s\S]*?const Header = /);
  assert.ok(sidebarBlock);
  assert.match(sidebarBlock[0], /compact && !mobile &&/);
  assert.match(sidebarBlock[0], /group-hover:opacity-100/);
  assert.match(sidebarBlock[0], /group-focus-visible:opacity-100/);
  assert.match(sidebarBlock[0], /item\.label/);
});
```

- [ ] **Step 2: Run and verify failure**

Run `cd frontend && npx tsx --test src/account-card.test.tsx`. Expected: fail.

- [ ] **Step 3: Add compact tooltip**

Add `group` to the sidebar nav button base class. Inside each button, after hidden label:

```tsx
{compact && !mobile && (
  <span className="pointer-events-none absolute left-[calc(100%+0.5rem)] top-1/2 z-50 -translate-y-1/2 whitespace-nowrap rounded-xl border border-sky-100 bg-white px-3 py-2 text-xs font-bold text-slate-700 opacity-0 shadow-[0_12px_28px_rgba(15,23,42,0.14)] transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100 dark:border-white/10 dark:bg-slate-900 dark:text-slate-100">
    {item.label}
  </span>
)}
```

- [ ] **Step 4: Verify**

Run `cd frontend && npx tsx --test src/account-card.test.tsx`. Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.tsx frontend/src/account-card.test.tsx
git commit -m "feat: label compact workspace navigation"
```

## Task 7: Final Verification

**Files:**
- Verify only.

- [ ] **Step 1: Run backend consultation tests**

```bash
python3 -m unittest tests.test_consultation_flow -v
```

Expected: all tests pass.

- [ ] **Step 2: Run frontend source tests**

```bash
cd frontend && npx tsx --test src/account-card.test.tsx src/workspace-navigation.test.ts
```

Expected: all tests pass.

- [ ] **Step 3: Run frontend build**

```bash
npm --prefix frontend run build
```

Expected: build succeeds. Existing chunk-size warnings are acceptable.

- [ ] **Step 4: Commit any proof-only updates**

If no files changed, do not commit. If tests required minor source-test corrections:

```bash
git add frontend/src/account-card.test.tsx frontend/src/workspace-navigation.test.ts
git commit -m "test: cover consultation meeting followup polish"
```
