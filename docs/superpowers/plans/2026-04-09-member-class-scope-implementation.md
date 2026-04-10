# Member Class Scope Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make member-only class-driven teacher workflows stay inside assigned class scope, and convert the member smart wrong question page into a class-scoped student notebook flow.

**Architecture:** Reuse the existing backend class-scope guards in `app.py` and keep them authoritative. Align the three affected frontend workflows around a page-local current-class selection model, then branch the smart wrong question UI by role so staff keep the current global list while `member` users get class-scoped student cards and student notebook details.

**Tech Stack:** Flask, unittest, React 19, TypeScript, tsx test runner

---

## File Map

- `app.py`
  - Existing access helpers and routes for classes, lessons, class feedback, and wrong questions.
- `tests/test_account_flow.py`
  - Existing member class-scope coverage for lessons and class-bound access rules.
- `tests/test_smart_wrong_questions_api.py`
  - Existing wrong-question API coverage; extend for member class/student notebook boundaries.
- `frontend/src/App.tsx`
  - Review-plan and class-feedback page state, class selectors, page wiring.
- `frontend/src/review-generation-async.test.tsx`
  - Source-level assertions for review-plan behavior in `App.tsx`.
- `frontend/src/class-feedback-generation.test.tsx`
  - Source-level assertions for class-feedback behavior in `App.tsx` and workspace wiring.
- `frontend/src/smartWrongQuestions.ts`
  - Wrong-question normalization and derived view-model helpers.
- `frontend/src/SmartWrongQuestionsPage.tsx`
  - Smart wrong question UI and review save flow.
- `frontend/src/smart-wrong-questions.test.ts`
  - Utility tests plus DOM-level smart wrong question page tests.

### Task 1: Lock Backend Member Scope With Red-Green Tests

**Files:**
- Modify: `tests/test_account_flow.py`
- Modify: `tests/test_smart_wrong_questions_api.py`
- Modify: `app.py`

- [ ] **Step 1: Write the failing backend tests for member-only class scope gaps**

```python
def test_member_class_feedback_task_creation_requires_owned_class(client):
    owner, member, owned_class, other_class = seed_member_scope_fixture()

    login_as(client, member)

    allowed = client.post(
        "/api/class-feedback/tasks",
        json={
            "class_id": owned_class["id"],
            "start_date": "2026-04-01",
            "end_date": "2026-04-07",
        },
    )
    assert allowed.status_code == 201

    blocked = client.post(
        "/api/class-feedback/tasks",
        json={
            "class_id": other_class["id"],
            "start_date": "2026-04-01",
            "end_date": "2026-04-07",
        },
    )
    assert blocked.status_code == 403


def test_member_wrong_question_list_only_returns_selected_class_students(client):
    member, owned_class, other_class = seed_wrong_question_scope_fixture()

    login_as(client, member)

    response = client.get("/api/wrong-questions")
    assert response.status_code == 200
    payload = response.get_json()
    assert {item["class_id"] for item in payload["items"]} == {owned_class["id"]}
    assert all(item["student_name"] in {"Alice", "Bob"} for item in payload["items"])
```

- [ ] **Step 2: Run the backend scope tests to verify the gap**

Run:

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website
python -m unittest tests.test_account_flow tests.test_smart_wrong_questions_api -v
```

Expected: at least one new member-scope assertion fails before backend changes are applied.

- [ ] **Step 3: Implement the minimal backend fix or guard tightening**

```python
def _get_accessible_class_feedback_task_or_error(user, task_id: int):
    task = get_class_feedback_task(task_id)
    if task is None:
        return None, (jsonify({"error": "反馈任务不存在"}), 404)

    class_id = task.get("class_id")
    if class_id is None:
        return None, (jsonify({"error": "反馈任务缺少班级信息"}), 400)

    _, error = _get_accessible_class_or_error(user, int(class_id))
    if error is not None:
        return None, error

    return task, None


def _filter_wrong_question_items_for_user(user, items):
    if user["role"] == "super_owner":
        return list(items)

    if user["role"] in {"owner", "admin"}:
        return [item for item in items if _item_matches_organization_scope(item, user)]

    return [item for item in items if _can_access_wrong_question_record(user, item)]
```

- [ ] **Step 4: Run the backend scope tests again**

Run:

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website
python -m unittest tests.test_account_flow tests.test_smart_wrong_questions_api -v
```

Expected: all targeted member-scope tests pass.

- [ ] **Step 5: Commit the backend scope lock-in**

```bash
git add app.py tests/test_account_flow.py tests/test_smart_wrong_questions_api.py
git commit -m "fix: lock member access to assigned classes"
```

### Task 2: Align Member Class Selection On Review-Plan And Class-Feedback Pages

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/review-generation-async.test.tsx`
- Modify: `frontend/src/class-feedback-generation.test.tsx`

- [ ] **Step 1: Write the failing source-level assertions for member class selectors**

```ts
test('App source clears stale member review-plan class selection when current class falls out of scope', () => {
  assert.match(appSource, /const syncMemberScopedClassSelection = \(/);
  assert.match(appSource, /if \(currentUser\.role !== 'member'\) return selectedClassId;/);
  assert.match(appSource, /if \(scopedClasses\.length === 1\) return scopedClasses\[0\]\.id;/);
  assert.match(appSource, /return null;/);
});

test('App source reuses member-scoped class options for class feedback and review generation', () => {
  assert.match(appSource, /const memberScopedClasses = useMemo/);
  assert.match(appSource, /const reviewPlanClassOptions = currentUser\.role === 'member' \? memberScopedClasses : classes/);
  assert.match(appSource, /const classFeedbackClassOptions = currentUser\.role === 'member' \? memberScopedClasses : classes/);
});
```

- [ ] **Step 2: Run the targeted frontend tests to verify they fail first**

Run:

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website/frontend
npx tsx --test src/review-generation-async.test.tsx src/class-feedback-generation.test.tsx
```

Expected: the new member-scope assertions fail against the current `App.tsx` source.

- [ ] **Step 3: Add the page-local class selection synchronizer in `App.tsx`**

```ts
function syncMemberScopedClassSelection(
  role: Role,
  scopedClasses: ClassItem[],
  selectedClassId: number | null,
): number | null {
  if (role !== 'member') {
    return selectedClassId;
  }

  if (scopedClasses.length === 1) {
    return scopedClasses[0]?.id ?? null;
  }

  if (selectedClassId && scopedClasses.some((item) => item.id === selectedClassId)) {
    return selectedClassId;
  }

  return null;
}
```

- [ ] **Step 4: Wire the member-scoped class options into both affected page flows**

```ts
const memberScopedClasses = useMemo(() => {
  if (currentUser.role !== 'member') {
    return classes;
  }
  return classes;
}, [classes, currentUser.role]);

const reviewPlanClassOptions = currentUser.role === 'member' ? memberScopedClasses : classes;
const classFeedbackClassOptions = currentUser.role === 'member' ? memberScopedClasses : classes;

useEffect(() => {
  setSelectedClassId((current) => syncMemberScopedClassSelection(currentUser.role, reviewPlanClassOptions, current));
}, [currentUser.role, reviewPlanClassOptions]);

useEffect(() => {
  setClassFeedbackSelectedClassId((current) => syncMemberScopedClassSelection(currentUser.role, classFeedbackClassOptions, current));
}, [currentUser.role, classFeedbackClassOptions]);
```

- [ ] **Step 5: Re-run the targeted frontend tests**

Run:

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website/frontend
npx tsx --test src/review-generation-async.test.tsx src/class-feedback-generation.test.tsx
```

Expected: both source-level test files pass.

- [ ] **Step 6: Commit the shared class-selection alignment**

```bash
git add frontend/src/App.tsx frontend/src/review-generation-async.test.tsx frontend/src/class-feedback-generation.test.tsx
git commit -m "feat: align member class selectors across teacher workflows"
```

### Task 3: Add Member Student Notebook View Models For Smart Wrong Questions

**Files:**
- Modify: `frontend/src/smartWrongQuestions.ts`
- Modify: `frontend/src/smart-wrong-questions.test.ts`

- [ ] **Step 1: Write the failing utility tests for member student-card aggregation**

```ts
test('buildMemberStudentNotebookSummaries groups current-class records by student', () => {
  const summaries = buildMemberStudentNotebookSummaries([
    makeWrongQuestionRecord({ id: 'a', classId: 101, className: '六年级 1 班', studentName: 'Alice', reviewStatus: 'pending' }),
    makeWrongQuestionRecord({ id: 'b', classId: 101, className: '六年级 1 班', studentName: 'Alice', teacherComment: '已跟进' }),
    makeWrongQuestionRecord({ id: 'c', classId: 101, className: '六年级 1 班', studentName: 'Bob' }),
  ], 101);

  assert.deepEqual(summaries, [
    {
      studentName: 'Alice',
      classId: 101,
      className: '六年级 1 班',
      totalCount: 2,
      pendingReviewCount: 1,
      hasTeacherFollowUp: true,
      latestCreatedAt: summaries[0]?.latestCreatedAt ?? '',
    },
    {
      studentName: 'Bob',
      classId: 101,
      className: '六年级 1 班',
      totalCount: 1,
      pendingReviewCount: 0,
      hasTeacherFollowUp: false,
      latestCreatedAt: summaries[1]?.latestCreatedAt ?? '',
    },
  ]);
});

test('filterWrongQuestionRecordsForMemberNotebook keeps only the selected class and student records', () => {
  const records = [
    makeWrongQuestionRecord({ id: 'a', classId: 101, studentName: 'Alice' }),
    makeWrongQuestionRecord({ id: 'b', classId: 101, studentName: 'Bob' }),
    makeWrongQuestionRecord({ id: 'c', classId: 202, studentName: 'Alice' }),
  ];

  assert.deepEqual(
    filterWrongQuestionRecordsForMemberNotebook(records, 101, 'Alice').map((item) => item.id),
    ['a'],
  );
});
```

- [ ] **Step 2: Run the smart wrong question utility tests to verify failure**

Run:

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website/frontend
npx tsx --test src/smart-wrong-questions.test.ts
```

Expected: tests fail because the new notebook aggregation helpers do not exist yet.

- [ ] **Step 3: Add the minimal member notebook helper types and functions**

```ts
export interface MemberStudentNotebookSummary {
  studentName: string;
  classId: number;
  className: string;
  totalCount: number;
  pendingReviewCount: number;
  hasTeacherFollowUp: boolean;
  latestCreatedAt: string;
}

export function filterWrongQuestionRecordsForMemberNotebook(
  records: WrongQuestionRecord[],
  classId: number | null,
  studentName: string | null,
): WrongQuestionRecord[] {
  return records
    .filter((item) => classId === null || item.classId === classId)
    .filter((item) => !studentName || item.studentName === studentName)
    .sort((left, right) => right.createdAt.localeCompare(left.createdAt));
}

export function buildMemberStudentNotebookSummaries(
  records: WrongQuestionRecord[],
  classId: number | null,
): MemberStudentNotebookSummary[] {
  const buckets = new Map<string, MemberStudentNotebookSummary>();

  for (const record of filterWrongQuestionRecordsForMemberNotebook(records, classId, null)) {
    const key = `${record.classId ?? 'none'}::${record.studentName}`;
    const current = buckets.get(key);
    const pending = record.reviewStatus.trim() === 'pending' ? 1 : 0;
    const hasTeacherFollowUp = record.teacherComment.trim().length > 0;

    if (!current) {
      buckets.set(key, {
        studentName: record.studentName,
        classId: record.classId ?? 0,
        className: record.className,
        totalCount: 1,
        pendingReviewCount: pending,
        hasTeacherFollowUp,
        latestCreatedAt: record.createdAt,
      });
      continue;
    }

    current.totalCount += 1;
    current.pendingReviewCount += pending;
    current.hasTeacherFollowUp = current.hasTeacherFollowUp || hasTeacherFollowUp;
    current.latestCreatedAt = current.latestCreatedAt > record.createdAt ? current.latestCreatedAt : record.createdAt;
  }

  return Array.from(buckets.values()).sort((left, right) => right.latestCreatedAt.localeCompare(left.latestCreatedAt));
}
```

- [ ] **Step 4: Re-run the smart wrong question utility tests**

Run:

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website/frontend
npx tsx --test src/smart-wrong-questions.test.ts
```

Expected: utility tests pass with the new member notebook helpers.

- [ ] **Step 5: Commit the smart wrong question view-model layer**

```bash
git add frontend/src/smartWrongQuestions.ts frontend/src/smart-wrong-questions.test.ts
git commit -m "feat: add member student notebook summaries"
```

### Task 4: Switch Member Smart Wrong Questions To Student Cards And Notebook Detail

**Files:**
- Modify: `frontend/src/SmartWrongQuestionsPage.tsx`
- Modify: `frontend/src/smart-wrong-questions.test.ts`
- Modify: `tests/test_smart_wrong_questions_api.py`
- Modify: `app.py` (only if the current list payload cannot support stable class/student rendering)

- [ ] **Step 1: Write the failing DOM-level smart wrong question tests for the member flow**

```ts
test('SmartWrongQuestionsPage renders member student cards for the selected class', async () => {
  const fetchCalls: string[] = [];
  const restoreFetch = mockFetch((input) => {
    const url = String(input);
    fetchCalls.push(url);
    if (url.endsWith('/api/classes')) {
      return createJsonResponse([{ id: 101, name: '六年级 1 班', subject: '数学' }]);
    }
    if (url.startsWith('/api/wrong-questions')) {
      return createJsonResponse({ items: memberNotebookFixtures, summary: { totalCount: 3, pendingReviewCount: 1, repeatedMistakeCount: 0, highPriorityCount: 0, uniqueClassCount: 1, uniqueStudentCount: 2 } });
    }
    throw new Error(`Unhandled URL: ${url}`);
  });

  const screen = await renderSmartWrongQuestionsPage({ role: 'member' });
  await waitForAssertion(() => {
    assert.match(screen.container.textContent ?? '', /Alice/);
    assert.match(screen.container.textContent ?? '', /Bob/);
    assert.doesNotMatch(screen.container.textContent ?? '', /筛选条件/);
  });

  restoreFetch();
});

test('SmartWrongQuestionsPage saves review content only for the selected member notebook record set', async () => {
  const reviewRequests: Array<{ url: string; body: string }> = [];
  const restoreFetch = mockFetch((input, init) => {
    const url = String(input);
    if (url.endsWith('/api/classes')) {
      return createJsonResponse([{ id: 101, name: '六年级 1 班', subject: '数学' }]);
    }
    if (url.startsWith('/api/wrong-questions/record-a/review')) {
      reviewRequests.push({ url, body: String(init?.body ?? '') });
      return createJsonResponse({ id: 'record-a', status: 'pending', teacher_comment: '已跟进' });
    }
    if (url.startsWith('/api/wrong-questions')) {
      return createJsonResponse({ items: memberNotebookFixtures, summary: defaultSummary });
    }
    throw new Error(`Unhandled URL: ${url}`);
  });

  const screen = await renderSmartWrongQuestionsPage({ role: 'member' });
  await clickButton(screen.container, 'Alice');
  await fillTeacherComment(screen.container, '已跟进');
  await clickButton(screen.container, '保存跟进');

  await waitForAssertion(() => {
    assert.equal(reviewRequests.length, 1);
    assert.match(reviewRequests[0]?.url ?? '', /record-a/);
  });

  restoreFetch();
});
```

- [ ] **Step 2: Run the targeted smart wrong question tests to verify the current page fails them**

Run:

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website/frontend
npx tsx --test src/smart-wrong-questions.test.ts
```

Expected: the member student-card assertions fail because the page still renders the record-first layout for all roles.

- [ ] **Step 3: Add role-branching state in `SmartWrongQuestionsPage.tsx`**

```ts
const isMemberScope = currentUser.role === 'member';
const memberScopedClassOptions = classOptions;
const [selectedClassId, setSelectedClassId] = useState<number | null>(null);
const [selectedStudentName, setSelectedStudentName] = useState<string | null>(null);

const memberNotebookSummaries = useMemo(
  () => buildMemberStudentNotebookSummaries(records, selectedClassId),
  [records, selectedClassId],
);

const memberNotebookRecords = useMemo(
  () => filterWrongQuestionRecordsForMemberNotebook(records, selectedClassId, selectedStudentName),
  [records, selectedClassId, selectedStudentName],
);
```

- [ ] **Step 4: Render member-only class summary, student cards, and notebook detail while preserving staff UI**

```tsx
if (isMemberScope) {
  return (
    <div className={`${workspacePageClass} mx-auto max-w-7xl space-y-6`}>
      <section className={`${workspaceCardClass} p-6`}>
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.3em] text-sky-600">Student Notebook</p>
            <h2 className="mt-2 text-2xl font-semibold text-slate-900 dark:text-white">智能错题</h2>
          </div>
          <select value={selectedClassId ?? ''} onChange={(event) => setSelectedClassId(Number(event.target.value) || null)}>
            <option value="">请选择班级</option>
            {memberScopedClassOptions.map((item) => (
              <option key={item.id} value={item.id}>{item.name}</option>
            ))}
          </select>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {memberNotebookSummaries.map((item) => (
          <button key={`${item.classId}-${item.studentName}`} type="button" onClick={() => setSelectedStudentName(item.studentName)}>
            <span>{item.studentName}</span>
            <span>{item.totalCount} 题</span>
            <span>{item.pendingReviewCount} 待跟进</span>
          </button>
        ))}
      </section>

      <section className={`${workspaceSoftCardClass} p-6`}>
        {memberNotebookRecords.map((record) => (
          <article key={record.id} className="space-y-3 border-b border-slate-200 pb-4 last:border-b-0">
            <h3 className="text-lg font-semibold text-slate-900 dark:text-white">{record.analysis.questionCategory || '未分类错题'}</h3>
          </article>
        ))}
      </section>
    </div>
  );
}
```

- [ ] **Step 5: Only add a backend response tweak if the current payload is insufficient**

```python
@app.get("/api/wrong-questions")
def list_wrong_questions():
    user = require_login_user()
    items = _filter_wrong_question_items_for_user(user, load_wrong_question_items())
    return jsonify({
        "items": items,
        "summary": build_wrong_question_summary(items),
    })
```

Use this step only if the page cannot build stable class/student cards from the existing payload.

- [ ] **Step 6: Re-run the wrong question frontend and backend tests**

Run:

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website/frontend
npx tsx --test src/smart-wrong-questions.test.ts

cd /Users/ark.mini/Desktop/Xingrun-Website
python -m unittest tests.test_smart_wrong_questions_api -v
```

Expected: both targeted suites pass, with staff behavior unchanged and member behavior switched to student notebooks.

- [ ] **Step 7: Commit the member notebook UI change**

```bash
git add frontend/src/SmartWrongQuestionsPage.tsx frontend/src/smart-wrong-questions.test.ts app.py tests/test_smart_wrong_questions_api.py
git commit -m "feat: switch member wrong questions to student notebooks"
```

### Task 5: Full Verification And Handoff Update

**Files:**
- Modify: `handoff.md`

- [ ] **Step 1: Run the focused backend and frontend verification set**

Run:

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website
python -m unittest tests.test_account_flow tests.test_smart_wrong_questions_api -v

cd /Users/ark.mini/Desktop/Xingrun-Website/frontend
npx tsx --test src/review-generation-async.test.tsx src/class-feedback-generation.test.tsx src/smart-wrong-questions.test.ts
npm run lint
```

Expected: all targeted tests pass and TypeScript emits no new errors.

- [ ] **Step 2: Update `handoff.md` with outcome, proof, and remaining risks**

```md
## member 班级范围与智能错题学生错题本已完成（2026-04-09）

### 已完成
- member 只能看到自己负责班级的班级选择项
- 课堂反馈与单节复习页会清理失效的 member 班级选择
- member 智能错题页改为班级下学生卡片 + 学生错题本详情

### proof
- Backend: `python -m unittest tests.test_account_flow tests.test_smart_wrong_questions_api -v`
- Frontend: `npx tsx --test src/review-generation-async.test.tsx src/class-feedback-generation.test.tsx src/smart-wrong-questions.test.ts`
- TypeScript: `npm run lint`

### 剩余问题
- 如需继续统一更多 class-select 页面，再单开一轮
```

- [ ] **Step 3: Commit the handoff update and final verification state**

```bash
git add handoff.md
git commit -m "docs: record member class scope rollout"
```

## Self-Review Notes

- Spec coverage check:
  - Member-only role scoping is covered in Task 1 and Task 2.
  - Smart wrong question student-card notebook flow is covered in Task 3 and Task 4.
  - Save behavior staying bound to selected student records is covered in Task 4.
  - Verification and handoff are covered in Task 5.
- Placeholder scan:
  - Replaced the earlier non-existent frontend filename proposal with the actual `frontend/src/smart-wrong-questions.test.ts` file.
  - Kept backend response enhancement optional and explicitly gated to payload insufficiency to avoid scope creep.
- Type consistency:
  - The plan consistently uses `selectedClassId`, `selectedStudentName`, `buildMemberStudentNotebookSummaries`, and `filterWrongQuestionRecordsForMemberNotebook` across utility and UI tasks.