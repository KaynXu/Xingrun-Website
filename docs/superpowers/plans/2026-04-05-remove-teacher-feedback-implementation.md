# Remove Teacher Feedback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Completely remove the abandoned teacher feedback workflow from the review-generation product surface, backend API, data layer, tests, and runtime schema.

**Architecture:** Delete the feature end-to-end instead of hiding it. Remove the dedicated frontend modules and `LessonInput` branches, delete the Flask feedback endpoints and helper functions, remove the `lesson_feedbacks` data-layer code and schema management, update tests to assert absence, then verify with frontend and backend checks.

**Tech Stack:** React 19, TypeScript, Vite, Flask, SQLite, Python unittest, Node source-based tests

---

## File Structure

- Modify: `/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/frontend/src/App.tsx`
  - Remove teacher feedback imports, state, branches, actions, labels, and history-entry UI.
- Delete: `/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/frontend/src/TeacherFeedbackWorkspace.tsx`
  - Dedicated abandoned feedback editor UI.
- Delete: `/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/frontend/src/reviewGenerationTeacherFeedback.ts`
  - Feedback-specific frontend helpers and API wrappers.
- Modify: `/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/frontend/src/workspace-navigation.test.ts`
  - Replace feedback-presence assertions with feedback-removal assertions.
- Delete: `/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/frontend/src/review-generation-teacher-feedback.test.tsx`
  - Obsolete feedback-specific frontend regression suite.
- Modify: `/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/app.py`
  - Remove feedback routes, helper functions, imports, and feedback-specific credit labels.
- Modify: `/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/lesson_manager.py`
  - Remove `lesson_feedbacks` schema logic and feedback persistence helpers; drop the table during init/migration.
- Modify: `/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/tests/test_account_flow.py`
  - Add regression coverage confirming removed feedback endpoints are gone or inaccessible.

## Task 1: Lock In Removal Expectations In Tests

**Files:**
- Modify: `/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/frontend/src/workspace-navigation.test.ts`
- Modify: `/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/tests/test_account_flow.py`
- Delete: `/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/frontend/src/review-generation-teacher-feedback.test.tsx`

- [ ] **Step 1: Write the failing frontend removal assertions**

Replace teacher-feedback-presence assertions in `frontend/src/workspace-navigation.test.ts` with absence checks:

```ts
assert.doesNotMatch(reviewGenerationBlock, /selectedLessonForFeedback/);
assert.doesNotMatch(historyBlock, /继续编辑反馈/);
assert.doesNotMatch(historyBlock, /Pencil/);
assert.doesNotMatch(appSource, /TeacherFeedbackWorkspace/);
assert.doesNotMatch(appSource, /reviewGenerationTeacherFeedback/);
assert.doesNotMatch(appSource, /teacher_feedback_draft/);
assert.doesNotMatch(appSource, /继续编辑课后反馈/);
assert.doesNotMatch(appSource, /课后反馈/);
```

Delete the obsolete `frontend/src/review-generation-teacher-feedback.test.tsx` file entirely.

- [ ] **Step 2: Write the failing backend removal test**

Add a backend regression test in `tests/test_account_flow.py` that proves the feedback endpoints are gone:

```python
def test_feedback_endpoints_are_removed(self):
    owner = self._create_owner_and_login()
    lesson_id = self._create_lesson_for_owner(owner)

    for method, path in [
        ("get", f"/api/review-plans/{lesson_id}/feedback"),
        ("put", f"/api/review-plans/{lesson_id}/feedback"),
        ("post", f"/api/review-plans/{lesson_id}/feedback/draft"),
    ]:
        response = getattr(self.client, method)(path, json={})
        self.assertEqual(response.status_code, 404)
```

Use the repo’s actual fixture helpers and lesson creation helpers already present in this file rather than inventing new setup patterns.

- [ ] **Step 3: Run tests to verify they fail**

Run: `npx tsx --test frontend/src/workspace-navigation.test.ts`

Expected: FAIL because the feedback code still exists.

Run: `.venv/bin/python -m unittest tests.test_account_flow.AccountFlowTestCase.test_feedback_endpoints_are_removed -v`

Expected: FAIL because the feedback routes still respond.

- [ ] **Step 4: Commit the red test setup only if executed in isolated commit flow**

If using granular commits, commit only after implementation makes the suite green. Otherwise skip this interim commit.

## Task 2: Remove Teacher Feedback From Frontend Review Generation

**Files:**
- Modify: `/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/frontend/src/App.tsx`
- Delete: `/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/frontend/src/TeacherFeedbackWorkspace.tsx`
- Delete: `/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/frontend/src/reviewGenerationTeacherFeedback.ts`

- [ ] **Step 1: Remove feedback imports and types from `App.tsx`**

Delete the dedicated imports:

```tsx
import { TeacherFeedbackWorkspace } from './TeacherFeedbackWorkspace';
import {
  buildTeacherFeedbackSavePayload,
  createClassStudent,
  defaultTeacherFeedbackTemplates,
  deleteClassStudent,
  generateLessonFeedbackDraft,
  listClassStudents,
  loadLessonFeedback,
  mergeRosterWithFeedbackDraft,
  saveLessonFeedback,
  type TeacherFeedbackStudentDraft,
  type TeacherFeedbackTemplate,
} from './reviewGenerationTeacherFeedback';
```

Also remove any feedback-specific feature labels:

```tsx
teacher_feedback_draft: '教师反馈草稿',
teacher_feedback: '教师反馈',
```

- [ ] **Step 2: Remove `LessonInput` feedback state and behavior**

Delete feedback-specific state and callbacks from `LessonInput`, including patterns like:

```tsx
const [feedbackStudents, setFeedbackStudents] = useState<TeacherFeedbackStudentDraft[]>([]);
const [feedbackTemplates, setFeedbackTemplates] = useState<TeacherFeedbackTemplate[]>(defaultTeacherFeedbackTemplates);
const [feedbackText, setFeedbackText] = useState('');
const [isLoadingFeedbackStudents, setIsLoadingFeedbackStudents] = useState(false);
const [isGeneratingFeedback, setIsGeneratingFeedback] = useState(false);
const [isSavingFeedback, setIsSavingFeedback] = useState(false);
const [feedbackStatusMessage, setFeedbackStatusMessage] = useState(...);
const isContinuingFeedback = initialLesson !== null;
const loadFeedbackWorkspace = useCallback(...);
const saveFeedbackWorkspace = useCallback(...);
const handleGenerateFeedbackDraft = async () => { ... };
const handleCopyAllFeedback = async () => { ... };
```

Remove the autosave effect and all feedback-only branches.

- [ ] **Step 3: Simplify the review-generation UI**

Change the composer header and body back to a single document-generation flow. Remove history-to-feedback reopen behavior:

```tsx
const handleFormSuccess = () => {
  setComposerOpen(false);
  setHistoryRefreshToken((current) => current + 1);
  onSuccess();
};
```

Refactor `ReviewGenerationPage` and `ReviewDocumentHistory` to remove:

```tsx
onContinueFeedback?: ...
selectedLessonForFeedback
handleStartEditingFeedback
继续编辑课后反馈
继续编辑反馈
<Pencil ... />
```

Keep only preview, download, and delete actions in history.

- [ ] **Step 4: Delete the dedicated frontend files**

Delete:

```bash
frontend/src/TeacherFeedbackWorkspace.tsx
frontend/src/reviewGenerationTeacherFeedback.ts
frontend/src/review-generation-teacher-feedback.test.tsx
```

- [ ] **Step 5: Run frontend removal regression tests**

Run: `npx tsx --test frontend/src/workspace-navigation.test.ts`

Expected: PASS with feedback-removal assertions green.

## Task 3: Remove Backend Feedback Routes And Data Layer

**Files:**
- Modify: `/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/app.py`
- Modify: `/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/lesson_manager.py`

- [ ] **Step 1: Remove feedback imports and feature-accounting branches from `app.py`**

Delete imports that only exist for teacher feedback, such as:

```python
from ai_processor import generate_teacher_feedback_draft
from lesson_manager import build_lesson_feedback_editor_state, save_lesson_feedback
```

Also remove feedback-specific label or accounting branches tied to:

```python
teacher_feedback_draft
lesson_feedback
generate_teacher_feedback_draft
```

- [ ] **Step 2: Delete feedback helper functions and routes from `app.py`**

Remove the whole set of feedback-only helpers and endpoints, including patterns like:

```python
def _validate_lesson_feedback_access(...):
def _build_teacher_feedback_template_lookup(...):
def _normalize_feedback_custom_templates(...):
def _normalize_feedback_students_for_draft(...):
def _normalize_feedback_editor_students(...):
def _build_feedback_student_index(...):

@app.route("/api/review-plans/<int:lesson_id>/feedback/draft", methods=["POST"])
@app.route("/api/review-plans/<int:lesson_id>/feedback", methods=["GET"])
@app.route("/api/review-plans/<int:lesson_id>/feedback", methods=["PUT"])
```

Do not leave dead helper code behind.

- [ ] **Step 3: Remove feedback persistence and schema logic from `lesson_manager.py`**

Delete:

```python
CREATE TABLE IF NOT EXISTS lesson_feedbacks ...
ALTER TABLE lesson_feedbacks ...
def save_lesson_feedback(...):
def get_lesson_feedback(...):
def build_lesson_feedback_editor_state(...):
```

Also remove any organization cleanup code that deletes from `lesson_feedbacks`.

- [ ] **Step 4: Add destructive schema cleanup**

In database initialization/migration, explicitly drop the abandoned table if it exists:

```python
conn.execute("DROP TABLE IF EXISTS lesson_feedbacks")
```

Place it in the initialization path that runs consistently for app startup and test DB setup so the schema is truly removed.

- [ ] **Step 5: Run backend regression tests**

Run: `.venv/bin/python -m unittest tests.test_account_flow.AccountFlowTestCase.test_feedback_endpoints_are_removed -v`

Expected: PASS with removed endpoints returning 404.

Run: `.venv/bin/python -m unittest tests.test_account_flow -v`

Expected: PASS for the full backend regression suite.

## Task 4: Full Verification And Cleanup

**Files:**
- Modify: `/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/frontend/src/App.tsx`
- Modify: `/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/frontend/src/workspace-navigation.test.ts`
- Modify: `/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/app.py`
- Modify: `/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/lesson_manager.py`
- Modify: `/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/tests/test_account_flow.py`
- Delete: `/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/frontend/src/TeacherFeedbackWorkspace.tsx`
- Delete: `/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/frontend/src/reviewGenerationTeacherFeedback.ts`
- Delete: `/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/frontend/src/review-generation-teacher-feedback.test.tsx`

- [ ] **Step 1: Run the focused frontend regression**

Run: `npx tsx --test frontend/src/workspace-navigation.test.ts`

Expected: PASS.

- [ ] **Step 2: Run the full frontend suite**

Run: `npm --prefix frontend test`

Expected: PASS with no teacher-feedback test file remaining.

- [ ] **Step 3: Run frontend typecheck and build**

Run: `npm --prefix frontend run lint`

Expected: PASS with `tsc --noEmit` exit code 0.

Run: `npm --prefix frontend run build`

Expected: PASS with Vite build output and no hard errors.

- [ ] **Step 4: Run full backend regression**

Run: `./.venv/bin/python -m unittest tests.test_account_flow -v`

Expected: PASS for the full account-flow suite.

- [ ] **Step 5: Inspect diff and commit**

Run: `git diff -- frontend/src/App.tsx frontend/src/workspace-navigation.test.ts app.py lesson_manager.py tests/test_account_flow.py`

Expected: Only teacher-feedback-removal changes plus file deletions appear.

Commit:

```bash
git add frontend/src/App.tsx frontend/src/workspace-navigation.test.ts app.py lesson_manager.py tests/test_account_flow.py
git add -u frontend/src/TeacherFeedbackWorkspace.tsx frontend/src/reviewGenerationTeacherFeedback.ts frontend/src/review-generation-teacher-feedback.test.tsx
git commit -m "refactor: remove abandoned teacher feedback workflow"
```

## Task 5: Deployment

**Files:**
- No additional code changes

- [ ] **Step 1: Confirm clean working tree for tracked files**

Run: `git status --short`

Expected: No tracked code changes remain after the removal commit.

- [ ] **Step 2: Deploy with existing script**

Run:

```bash
SSH_PASSWORD='***REMOVED-ROTATED-SSH-PASSWORD***' ./deploy.sh --skip-commit
```

Expected sequence:
- Backend tests pass
- Frontend typecheck passes
- Frontend build passes
- `git push origin master` succeeds
- Remote repo pulls cleanly
- Remote frontend build succeeds
- PM2 restarts succeed

- [ ] **Step 3: If remote pull is blocked, capture evidence before touching remote state**

Run:

```bash
sshpass -p '***REMOVED-ROTATED-SSH-PASSWORD***' ssh -o StrictHostKeyChecking=accept-new ubuntu@49.234.185.86 'cd /home/ubuntu/Xingrun-Website && git status --short && printf "\n---\n" && git diff --stat'
```

Expected: a clear report of any remote local modifications. Do not overwrite them silently; surface the exact file list and size of changes before deciding the next step.

## Self-Review

- Spec coverage:
  - Frontend UI removal is covered by Task 2.
  - Backend/API/data-layer deletion is covered by Task 3.
  - Table drop and destructive schema cleanup are covered by Task 3.
  - Verification and deployment are covered by Tasks 4 and 5.
- Placeholder scan:
  - Tasks include exact files, exact commands, and concrete code targets.
- Type consistency:
  - Removed symbols are referenced consistently across the plan: `TeacherFeedbackWorkspace`, `reviewGenerationTeacherFeedback`, feedback endpoints, and `lesson_feedbacks`.
