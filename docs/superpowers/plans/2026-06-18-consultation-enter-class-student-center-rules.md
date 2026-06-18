# 咨询进班接轨学管中心班级规则 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the consultation `成功进班` dialog reuse student-center class filtering and class creation rules for `已有班级` and `快速建班`, while keeping the compact consultation UI.

**Architecture:** Add a small consultation-to-student-center adapter layer instead of copying student-center logic into the dialog. The dialog owns only UI state and callbacks; domain helpers convert consultation values into editable class filters and quick-create class form payloads. Existing student-center `resolveFilteredClasses`, `createEmptyClassForm`, and `buildClassSavePayload` remain the source of truth.

**Tech Stack:** React, TypeScript, Vite, Node test runner, Flask API, SQLite local data.

---

## File Structure

- Create `frontend/src/domain/consultationStudentCenterClassAdapter.ts`
  - Owns conversion between consultation records and student-center class filters/forms.
  - Reuses `resolveFilteredClasses`, `createEmptyClassForm`, `buildClassSavePayload`, and academic naming helpers.
  - Keeps this logic out of `ConsultationEnterClassDialog.tsx`.

- Modify `frontend/src/domain/consultationEnterClass.ts`
  - Keep existing payload builder for `/api/consultations/<id>/enter-class`.
  - Remove or narrow duplicated quick-create naming logic if the new adapter covers it.

- Modify `frontend/src/features/consultation/ConsultationEnterClassDialog.tsx`
  - Use adapter-generated defaults for filters and quick-create draft.
  - Add teacher filter and class-type filter for `已有班级`.
  - Keep `转化待进班` unchanged.

- Modify `frontend/src/features/consultation/ConsultationModal.tsx`
  - Use the adapter to build a student-center class save payload for quick-created classes.
  - Keep the existing edit-modal success flow.

- Modify `frontend/src/features/consultation/ConsultationPage.tsx`
  - Use the same adapter for inline page quick-create payloads.
  - Keep `/api/consultations/<id>/enter-class` as the final success-join API.

- Modify tests:
  - `frontend/src/domain/consultationEnterClass.test.ts`
  - `frontend/src/consultation-enter-class-dialog.test.ts`
  - `tests/test_consultation_flow.py`

- Update audit ledger:
  - `docs/superpowers/audits/2026-06-16-consultation-page-reconciliation.md`
  - Append one dated note with completed behavior and any remaining gaps.

---

### Task 1: Add The Adapter Layer

**Files:**
- Create: `frontend/src/domain/consultationStudentCenterClassAdapter.ts`
- Modify: `frontend/src/domain/consultationEnterClass.test.ts`

- [ ] **Step 1: Write the failing adapter tests**

Add these imports to `frontend/src/domain/consultationEnterClass.test.ts`:

```ts
import {
  buildConsultationClassFilterDefaults,
  buildConsultationQuickClassForm,
  buildConsultationQuickClassSavePayload,
  filterConsultationStudentCenterClasses,
} from './consultationStudentCenterClassAdapter';
```

Add these tests:

```ts
test('consultation class filter defaults recommend subject grade and teacher without locking them', () => {
  assert.deepEqual(buildConsultationClassFilterDefaults({
    consultationSubject: '数学',
    consultationGrade: '六年级',
    teachingTeacherUserId: 8,
    subjectOptions: ['数学', '物理'],
  }), {
    subjectFilter: '数学',
    teacherFilter: 8,
    stageFilter: '小奥',
    gradeFilter: '六年级',
    classTypeFilter: 'all',
  });
});

test('consultation class filter defaults stay editable when consultation fields are missing', () => {
  assert.deepEqual(buildConsultationClassFilterDefaults({
    consultationSubject: '',
    consultationGrade: '',
    subjectOptions: ['数学', '物理'],
  }), {
    subjectFilter: '全部学科',
    teacherFilter: 'all',
    stageFilter: '全部学段',
    gradeFilter: '全部',
    classTypeFilter: 'all',
  });
});

test('consultation existing class filter reuses student-center class ordering and class type filter', () => {
  const classes = [
    { id: 3, name: '数学·七年级·3班', class_type: 'group', subject: '数学', grade: '七年级', stage: '初中', current_grade: '七年级', class_number: '3', teacher_user_id: 8 },
    { id: 2, name: '数学·三年级·1班', class_type: 'group', subject: '数学', grade: '三年级', stage: '小学', current_grade: '三年级', class_number: '1', teacher_user_id: 8 },
    { id: 1, name: '数学·七年级·1v1', class_type: '1v1', subject: '数学', grade: '七年级', stage: '初中', current_grade: '七年级', class_number: '', teacher_user_id: 8 },
    { id: 4, name: '数学·七年级·2班', class_type: 'group', subject: '数学', grade: '七年级', stage: '初中', current_grade: '七年级', class_number: '2', teacher_user_id: 9 },
  ];

  const filtered = filterConsultationStudentCenterClasses({
    classes,
    subjectOptions: ['数学'],
    teacherBindingByClassId: {},
    filters: {
      subjectFilter: '数学',
      teacherFilter: 8,
      stageFilter: '初中',
      gradeFilter: '七年级',
      classTypeFilter: 'all',
    },
  });

  assert.deepEqual(filtered.map((item) => item.id), [1, 3]);
});

test('consultation quick class form starts from student-center empty form and consultation recommendations', () => {
  assert.deepEqual(buildConsultationQuickClassForm({
    consultationSubject: '数学',
    consultationGrade: '六年级',
    subjectOptions: ['数学', '物理'],
  }), {
    name: '',
    class_type: 'group',
    subject: '数学',
    grade: '六年级',
    teacher_name: '',
    stage: '小奥',
    current_grade: '六年级',
    class_number: '1',
    cohort_year: '',
    show_cohort_year: false,
    is_bridge: false,
    bridge_target: '小学->初中',
    content_track: '',
    selected_student_ids: [],
  });
});

test('consultation quick class payload is generated by student-center save rules', () => {
  const form = buildConsultationQuickClassForm({
    consultationSubject: '数学',
    consultationGrade: '七年级',
    subjectOptions: ['数学'],
  });

  const payload = buildConsultationQuickClassSavePayload({
    form: {
      ...form,
      stage: '初中',
      class_number: '2',
      is_bridge: true,
      bridge_target: '初中->高中',
    },
    selectedTeacher: { id: 8, name: '何老师', username: 'he', role: 'member', org: '星润' },
    selectedTeacherUserId: 8,
  });

  assert.equal(payload.subject, '数学');
  assert.equal(payload.stage, '初中');
  assert.equal(payload.current_grade, '七年级');
  assert.equal(payload.class_number, '2');
  assert.equal(payload.teacher_user_id, 8);
  assert.equal(payload.teacher_name, '何老师');
  assert.equal(payload.is_bridge, true);
  assert.equal(payload.bridge_target, '初中->高中');
});
```

- [ ] **Step 2: Run the tests to verify RED**

Run:

```bash
cd frontend
node --test src/domain/consultationEnterClass.test.ts
```

Expected:

```text
ERR_MODULE_NOT_FOUND
```

or failures showing `consultationStudentCenterClassAdapter` exports are missing.

- [ ] **Step 3: Implement the adapter**

Create `frontend/src/domain/consultationStudentCenterClassAdapter.ts`:

```ts
import { normalizeAcademicGradeLabel, getAcademicStageFromGrade } from './classNaming';
import {
  resolveFilteredClasses,
  type ClassFilterState,
} from '../features/student-center/classFilterRules';
import {
  buildClassSavePayload,
  type ClassSavePayload,
} from '../features/student-center/classSaveRules';
import {
  createEmptyClassForm,
  type ClassFormValues,
  type UserItem,
} from '../features/student-center/model';

type ConsultationClassFilterState = ClassFilterState & {
  classTypeFilter: 'all' | 'small' | 'group';
};

type AdapterClassItem = {
  id: number;
  name: string;
  class_type?: string;
  subject?: string;
  grade?: string;
  stage?: string;
  current_grade?: string;
  class_number?: string;
  teacher_user_id?: number | null;
  teacher_name?: string;
};

export function buildConsultationClassFilterDefaults({
  consultationSubject,
  consultationGrade,
  teachingTeacherUserId,
  subjectOptions,
}: {
  consultationSubject: string;
  consultationGrade: string;
  teachingTeacherUserId?: number | null;
  subjectOptions: string[];
}): ConsultationClassFilterState {
  const normalizedGrade = normalizeAcademicGradeLabel(consultationGrade || '');
  const stage = getAcademicStageFromGrade(normalizedGrade);
  return {
    subjectFilter: consultationSubject && subjectOptions.includes(consultationSubject) ? consultationSubject : '全部学科',
    teacherFilter: teachingTeacherUserId ?? 'all',
    stageFilter: stage || '全部学段',
    gradeFilter: normalizedGrade || '全部',
    classTypeFilter: 'all',
  };
}

export function filterConsultationStudentCenterClasses<TClass extends AdapterClassItem>({
  classes,
  subjectOptions,
  teacherBindingByClassId,
  filters,
}: {
  classes: TClass[];
  subjectOptions: string[];
  teacherBindingByClassId: Record<number, number | null>;
  filters: ConsultationClassFilterState;
}): TClass[] {
  const classTypeFiltered = classes.filter((item) => {
    if (filters.classTypeFilter === 'small') return item.class_type && item.class_type !== 'group';
    if (filters.classTypeFilter === 'group') return !item.class_type || item.class_type === 'group';
    return true;
  });
  return resolveFilteredClasses({
    classes: classTypeFiltered,
    subjectLookupClasses: classes,
    teacherBindingByClassId,
    subjectOptions,
    filters,
  }) as TClass[];
}

export function buildConsultationQuickClassForm({
  consultationSubject,
  consultationGrade,
  subjectOptions,
}: {
  consultationSubject: string;
  consultationGrade: string;
  subjectOptions: string[];
}): ClassFormValues {
  const normalizedGrade = normalizeAcademicGradeLabel(consultationGrade || '');
  return {
    ...createEmptyClassForm(),
    subject: consultationSubject && subjectOptions.includes(consultationSubject) ? consultationSubject : subjectOptions[0] || '',
    grade: normalizedGrade || '一年级',
    current_grade: normalizedGrade || '一年级',
    stage: getAcademicStageFromGrade(normalizedGrade) || '小奥',
  };
}

export function buildConsultationQuickClassSavePayload({
  form,
  selectedTeacher,
  selectedTeacherUserId,
}: {
  form: ClassFormValues;
  selectedTeacher?: UserItem;
  selectedTeacherUserId: number | null;
}): ClassSavePayload {
  return buildClassSavePayload({
    classId: 'new',
    form,
    selectedTeacher,
    selectedTeacherUserId,
  });
}
```

- [ ] **Step 4: Run the tests to verify GREEN**

Run:

```bash
cd frontend
node --test src/domain/consultationEnterClass.test.ts
```

Expected:

```text
# pass
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/domain/consultationStudentCenterClassAdapter.ts frontend/src/domain/consultationEnterClass.test.ts
git commit -m "feat: add consultation class rule adapter"
```

---

### Task 2: Wire Existing-Class Filtering Into The Dialog

**Files:**
- Modify: `frontend/src/features/consultation/ConsultationEnterClassDialog.tsx`
- Modify: `frontend/src/consultation-enter-class-dialog.test.ts`

- [ ] **Step 1: Write the failing source-structure test**

Add to `frontend/src/consultation-enter-class-dialog.test.ts`:

```ts
test('consultation enter class dialog exposes student-center style filters for existing classes', () => {
  assert.match(enterClassDialogSource, /buildConsultationClassFilterDefaults/);
  assert.match(enterClassDialogSource, /filterConsultationStudentCenterClasses/);
  assert.match(enterClassDialogSource, /teacherFilter/);
  assert.match(enterClassDialogSource, /classTypeFilter/);
  assert.match(enterClassDialogSource, /全部老师/);
  assert.match(enterClassDialogSource, /全部类型/);
  assert.match(enterClassDialogSource, /小课/);
  assert.match(enterClassDialogSource, /班课/);
});
```

- [ ] **Step 2: Run the test to verify RED**

Run:

```bash
cd frontend
node --test src/consultation-enter-class-dialog.test.ts
```

Expected: FAIL because adapter functions and new filters are not referenced in the dialog yet.

- [ ] **Step 3: Update dialog props and filtering state**

In `frontend/src/features/consultation/ConsultationEnterClassDialog.tsx`, replace the local `resolveConsultationAssignableClasses` helper with imports:

```ts
import {
  buildConsultationClassFilterDefaults,
  buildConsultationQuickClassForm,
  filterConsultationStudentCenterClasses,
} from '../../domain/consultationStudentCenterClassAdapter';
import type { UserItem } from '../student-center/model';
```

Extend props:

```ts
users: UserItem[];
teacherBindingByClassId?: Record<number, number | null>;
teachingTeacherUserId?: number | null;
```

Add state:

```ts
const [teacherFilter, setTeacherFilter] = useState<number | 'all'>('all');
const [classTypeFilter, setClassTypeFilter] = useState<'all' | 'small' | 'group'>('all');
```

In the `useEffect` reset block, calculate defaults:

```ts
const defaults = buildConsultationClassFilterDefaults({
  consultationSubject: values.consultation_subject || '',
  consultationGrade: values.grade || '',
  teachingTeacherUserId,
  subjectOptions: academicSubjectOptions,
});
setSubjectFilter(defaults.subjectFilter);
setTeacherFilter(defaults.teacherFilter);
setStageFilter(defaults.stageFilter);
setGradeFilter(defaults.gradeFilter);
setClassTypeFilter(defaults.classTypeFilter);
setCreateDraft(buildConsultationQuickClassForm({
  consultationSubject: values.consultation_subject || '',
  consultationGrade: values.grade || '',
  subjectOptions: academicSubjectOptions,
}));
```

Build filtered classes:

```ts
const filteredClasses = filterConsultationStudentCenterClasses({
  classes,
  subjectOptions: academicSubjectOptions,
  teacherBindingByClassId: teacherBindingByClassId || {},
  filters: {
    subjectFilter,
    teacherFilter,
    stageFilter,
    gradeFilter,
    classTypeFilter,
  },
});
```

- [ ] **Step 4: Add the two missing filter controls**

In the existing-class section, change the grid from three fields to five fields:

```tsx
<div className="grid gap-2 sm:grid-cols-5">
  <select value={subjectFilter} onChange={(event) => setSubjectFilter(event.target.value)} className={smallSelectClass}>
    <option value="全部学科">全部学科</option>
    {academicSubjectOptions.map((item) => <option key={item} value={item}>{item}</option>)}
  </select>
  <select value={teacherFilter} onChange={(event) => setTeacherFilter(event.target.value === 'all' ? 'all' : Number(event.target.value))} className={smallSelectClass}>
    <option value="all">全部老师</option>
    {users.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
  </select>
  <select value={stageFilter} onChange={(event) => setStageFilter(event.target.value)} className={smallSelectClass}>
    <option value="全部学段">全部学段</option>
    {consultationStageOptions.map((item) => <option key={item} value={item}>{item}</option>)}
  </select>
  <select value={gradeFilter} onChange={(event) => setGradeFilter(event.target.value)} className={smallSelectClass}>
    <option value="全部">全部年级</option>
    {consultationGradeOptions.map((item) => <option key={item} value={item}>{item}</option>)}
  </select>
  <select value={classTypeFilter} onChange={(event) => setClassTypeFilter(event.target.value as 'all' | 'small' | 'group')} className={smallSelectClass}>
    <option value="all">全部类型</option>
    <option value="small">小课</option>
    <option value="group">班课</option>
  </select>
</div>
```

- [ ] **Step 5: Pass the new props from both callers**

In `frontend/src/features/consultation/ConsultationModal.tsx`, pass:

```tsx
users={users}
teacherBindingByClassId={{}}
teachingTeacherUserId={currentUser.id}
```

In `frontend/src/features/consultation/ConsultationPage.tsx`, pass:

```tsx
users={users}
teacherBindingByClassId={{}}
teachingTeacherUserId={inlineEnterClassRecord.teaching_teacher_user_id ?? null}
```

If `ConsultationPage.tsx` does not currently load `users`, keep the prop optional in the dialog and pass `users={[]}` for this task. Add a follow-up note to the audit ledger that inline page teacher filtering needs staff user data if it is not already available.

- [ ] **Step 6: Run the tests to verify GREEN**

Run:

```bash
cd frontend
node --test src/consultation-enter-class-dialog.test.ts src/domain/consultationEnterClass.test.ts
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/features/consultation/ConsultationEnterClassDialog.tsx frontend/src/features/consultation/ConsultationModal.tsx frontend/src/features/consultation/ConsultationPage.tsx frontend/src/consultation-enter-class-dialog.test.ts
git commit -m "feat: filter consultation enter classes with student-center rules"
```

---

### Task 3: Rework Quick-Create To Use Student-Center Class Forms

**Files:**
- Modify: `frontend/src/features/consultation/ConsultationEnterClassDialog.tsx`
- Modify: `frontend/src/features/consultation/ConsultationModal.tsx`
- Modify: `frontend/src/features/consultation/ConsultationPage.tsx`
- Modify: `frontend/src/domain/consultationEnterClass.ts`
- Modify: `frontend/src/domain/consultationEnterClass.test.ts`
- Modify: `tests/test_consultation_flow.py`

- [ ] **Step 1: Write failing tests for quick-create source of truth**

In `frontend/src/domain/consultationEnterClass.test.ts`, replace the old quick-create naming test assertion with:

```ts
test('quick-create payload no longer owns student-center class naming rules', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/domain/consultationEnterClass.ts'), 'utf8');
  assert.doesNotMatch(source, /buildClassDisplayName/);
  assert.match(source, /mode: 'quick_new_class'/);
});
```

In `frontend/src/consultation-enter-class-dialog.test.ts`, add:

```ts
test('consultation quick-create UI uses student-center class form field names', () => {
  assert.match(enterClassDialogSource, /createDraft\.class_type/);
  assert.match(enterClassDialogSource, /createDraft\.current_grade/);
  assert.match(enterClassDialogSource, /createDraft\.class_number/);
  assert.match(enterClassDialogSource, /createDraft\.is_bridge/);
  assert.match(enterClassDialogSource, /createDraft\.bridge_target/);
  assert.doesNotMatch(enterClassDialogSource, /currentGrade/);
  assert.doesNotMatch(enterClassDialogSource, /classType/);
  assert.doesNotMatch(enterClassDialogSource, /classNumber/);
});
```

- [ ] **Step 2: Run frontend tests to verify RED**

Run:

```bash
cd frontend
node --test src/domain/consultationEnterClass.test.ts src/consultation-enter-class-dialog.test.ts
```

Expected: FAIL because the dialog still uses `currentGrade`, `classType`, and `classNumber`, and `consultationEnterClass.ts` still imports `buildClassDisplayName`.

- [ ] **Step 3: Change dialog quick-create draft type to `ClassFormValues`**

In `ConsultationEnterClassDialog.tsx`, import:

```ts
import type { ClassFormValues } from '../student-center/model';
```

Change `onCreateClass` prop:

```ts
onCreateClass: (form: ClassFormValues) => Promise<void>;
```

Change all quick-create state references:

```tsx
createDraft.subject
createDraft.stage
createDraft.current_grade
createDraft.class_type
createDraft.class_number
createDraft.is_bridge
createDraft.bridge_target
```

For class type controls, use:

```tsx
<select value={createDraft.class_type} onChange={(event) => setCreateDraft((current) => ({ ...current, class_type: event.target.value }))} className={smallSelectClass}>
  <option value="group">班课</option>
  <option value="1v1">1v1</option>
  <option value="1v2">1v2</option>
  <option value="1v3">1v3</option>
</select>
```

For class number:

```tsx
<select value={createDraft.class_number} onChange={(event) => setCreateDraft((current) => ({ ...current, class_number: event.target.value }))} className={smallSelectClass} disabled={createDraft.class_type !== 'group'}>
  {['1', '2', '3', '4', '5', '6'].map((item) => <option key={item} value={item}>{item}班</option>)}
</select>
```

- [ ] **Step 4: Use adapter payload in edit modal quick-create**

In `ConsultationModal.tsx`, replace the manual class form construction with:

```ts
const selectedTeacher = buildConsultationClassUser(currentUser, form.teaching_teacher || form.trial_teacher || form.receiving_teacher);
const payload = buildConsultationQuickClassSavePayload({
  form: draft,
  selectedTeacher,
  selectedTeacherUserId: currentUser.id,
});
```

Keep:

```ts
const createdClass = await apiFetch<ClassItem>('/api/classes', {
  method: 'POST',
  body: JSON.stringify(payload),
});
setLocalClasses((current) => [createdClass, ...current.filter((item) => item.id !== createdClass.id)]);
handleConfirmExistingClass(createdClass.id);
```

- [ ] **Step 5: Use adapter payload shape for inline page quick-create**

In `ConsultationPage.tsx`, build quick-create payload from the student-center form:

```ts
await postInlineEnterClass(buildConsultationEnterClassPayload({
  mode: 'quick-create',
  quickClassDraft: {
    class_type: draft.class_type,
    subject: draft.subject,
    stage: draft.stage,
    current_grade: draft.current_grade,
    class_number: draft.class_type === 'group' ? draft.class_number : '',
    cohort_year: draft.cohort_year,
    show_cohort_year: draft.show_cohort_year,
    is_bridge: draft.is_bridge,
    bridge_target: draft.bridge_target,
  },
}));
```

If inline quick-create should also create through `/api/classes` instead of `/enter-class` quick mode, record that as a gap in the audit ledger. Do not change backend behavior in this task unless tests require it.

- [ ] **Step 6: Simplify `buildConsultationEnterClassPayload` quick naming**

In `consultationEnterClass.ts`, remove `buildClassDisplayName` import and set quick payload class name from an explicit draft field only if backend still requires it:

```ts
class_name: '',
```

If backend tests require a generated name, keep the existing backend-generated behavior and record this as a gap: `enter-class quick_new_class still accepts class_name for API compatibility, but UI creation uses student-center payload in edit modal`.

- [ ] **Step 7: Run frontend tests to verify GREEN**

Run:

```bash
cd frontend
node --test src/domain/consultationEnterClass.test.ts src/consultation-enter-class-dialog.test.ts
```

Expected: PASS.

- [ ] **Step 8: Run backend enter-class tests**

Run:

```bash
python3 -m unittest tests.test_consultation_flow.ConsultationFlowTestCase.test_consultation_enter_quick_new_class_uses_structured_class_fields -v
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/features/consultation/ConsultationEnterClassDialog.tsx frontend/src/features/consultation/ConsultationModal.tsx frontend/src/features/consultation/ConsultationPage.tsx frontend/src/domain/consultationEnterClass.ts frontend/src/domain/consultationEnterClass.test.ts frontend/src/consultation-enter-class-dialog.test.ts tests/test_consultation_flow.py
git commit -m "feat: align consultation quick class creation"
```

---

### Task 4: Verify Preview And Update The Function Ledger

**Files:**
- Modify: `docs/superpowers/audits/2026-06-16-consultation-page-reconciliation.md`

- [ ] **Step 1: Run the focused frontend test set**

Run:

```bash
cd frontend
node --test src/domain/consultationEnterClass.test.ts src/consultation-enter-class-dialog.test.ts src/consultation-flow-wiring.test.ts
```

Expected: PASS.

- [ ] **Step 2: Run build**

Run:

```bash
cd frontend
npm run build
```

Expected: PASS. The existing chunk-size warning is acceptable.

- [ ] **Step 3: Run backend consultation tests**

Run:

```bash
python3 -m unittest tests.test_consultation_flow -v
```

Expected: PASS.

- [ ] **Step 4: Start local preview**

Run:

```bash
npm run dev
```

Expected:

```text
VITE ... ready
Running on http://127.0.0.1:5001
```

- [ ] **Step 5: Manual preview checklist**

Open:

```text
http://localhost:3000/workspace/consultation
```

Check:

1. Open a consultation card.
2. Click `成功进班`.
3. Confirm the three cards are visible.
4. In `已有班级`, change subject, teacher, stage, grade, and type filters.
5. Confirm the class dropdown updates and remains a dropdown.
6. In `快速建班`, confirm compact fields match current page style.
7. Create one test class and confirm the consultation enters success.
8. Open `http://localhost:3000/workspace/classes` and confirm the new class appears.
9. Check browser console has no error.

- [ ] **Step 6: Update the audit ledger**

Append this section to `docs/superpowers/audits/2026-06-16-consultation-page-reconciliation.md`:

```md
## 2026-06-18 咨询进班接轨学管中心规则

- 已有班级：接入学管中心班级筛选与排序，筛选仍在进班弹窗内以下拉方式选择。
- 快速建班：编辑弹窗快速建班使用学管中心班级表单和保存 payload 规则。
- 保持不动：转化待进班、Over 成功/失败、流程图蓝绿灯。
- 验证：记录本次通过的 frontend/backend/build 命令。
- 缺口：记录 inline 主页快速建班是否仍走 `/enter-class` quick mode；如果保留兼容，后续要不要统一到 `/api/classes` 创建后再进班。
```

- [ ] **Step 7: Commit**

```bash
git add docs/superpowers/audits/2026-06-16-consultation-page-reconciliation.md
git commit -m "docs: record consultation enter-class alignment"
```

---

## Self-Review

- Spec coverage:
  - `已有班级` 筛选逻辑: Task 1 adapter + Task 2 dialog wiring.
  - `快速建班` 学管中心规则: Task 1 adapter + Task 3 quick-create wiring.
  - 保持 UI 轻量: Task 2/3 modify existing dialog only.
  - 记录功能与缺口: Task 4 audit ledger.

- Placeholder scan:
  - No unfinished placeholders or placeholder-only steps.

- Type consistency:
  - `ClassFormValues` is the single quick-create draft shape after Task 3.
  - `ConsultationClassFilterState` extends student-center `ClassFilterState` with `classTypeFilter`.
  - Existing `/enter-class` API remains the final consultation success endpoint.
