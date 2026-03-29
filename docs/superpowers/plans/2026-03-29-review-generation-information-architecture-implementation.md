# Review Generation Information Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the separate `添加课程` and `课程列表` lesson shell entries with one `复习生成` module that defaults to `历史文档`, expands an inline `生成复习文档` form from a `新建复习文档` CTA, and collapses back to refreshed history after success.

**Architecture:** Keep the existing lesson-generation backend flow and most of the current `LessonInput` and `LibraryPage` UI intact. Limit the change to the React shell in `frontend/src/App.tsx` and the source-level navigation tests by introducing one unified page entry, a local expanded/collapsed state for the inline form, and the approved label remapping.

**Tech Stack:** React 19, TypeScript, Vite, Tailwind CSS, Node `test`

---

## File Structure

- Modify: `frontend/src/App.tsx`
  - Replace the dual page model (`input` + `library`) with one review-generation page state.
  - Keep the existing `LessonInput` form logic and lesson-history table, but compose them into one page with an inline expansion toggle.
- Modify: `frontend/src/workspace-navigation.test.ts`
  - Lock the new shell/navigation contract with source-level assertions.

### Task 1: Lock The Approved Information Architecture With Failing Frontend Tests

**Files:**
- Modify: `frontend/src/workspace-navigation.test.ts`

- [ ] **Step 1: Add a source-level assertion that the workspace shell now exposes one `复习生成` page instead of separate `input` and `library` pages**

```ts
test('review generation source replaces separate lesson input and library pages with one review-generation workspace page', () => {
  assert.match(appSource, /type Page = 'dashboard' \| 'review-generation' \| 'consultation' \| 'calendar' \| 'classes' \| 'accounts' \| 'settings';/);
  assert.match(appSource, /id: 'review-generation'[\s\S]*label: '复习生成'/);
  assert.match(appSource, /review-generation: '复习生成'/);
  assert.match(appSource, /activePage === 'review-generation'[\s\S]*<ReviewGenerationPage onSuccess=\{handleReviewGenerationSuccess\} \/>/);
  assert.doesNotMatch(appSource, /id: 'input'[\s\S]*label: '添加课程'/);
  assert.doesNotMatch(appSource, /id: 'library'[\s\S]*label: '课程列表'/);
  assert.doesNotMatch(appSource, /activePage === 'input'/);
  assert.doesNotMatch(appSource, /activePage === 'library'/);
});
```

- [ ] **Step 2: Add a source-level assertion that the unified page defaults to `历史文档` and exposes the approved CTA and form title**

```ts
test('review generation source defaults to 历史文档 and expands 生成复习文档 from 新建复习文档 CTA', () => {
  const reviewGenerationBlock = appSource.match(/const ReviewGenerationPage = \(\{ onSuccess \}: \{ onSuccess: \(\) => void \}\) => \{[\s\S]*?\n};/);

  assert.ok(reviewGenerationBlock);
  assert.match(reviewGenerationBlock[0], /const \[composerOpen, setComposerOpen\] = useState\(false\);/);
  assert.match(reviewGenerationBlock[0], /<h3 className=\{workspaceSectionTitleClass\}>历史文档<\/h3>/);
  assert.match(reviewGenerationBlock[0], /新建复习文档/);
  assert.match(reviewGenerationBlock[0], /生成复习文档/);
});
```

- [ ] **Step 3: Add a source-level assertion that successful generation collapses the inline form and returns the user to history instead of navigating to a second tab**

```ts
test('review generation source collapses the inline composer after successful generation', () => {
  const reviewGenerationBlock = appSource.match(/const ReviewGenerationPage = \(\{ onSuccess \}: \{ onSuccess: \(\) => void \}\) => \{[\s\S]*?\n};/);

  assert.ok(reviewGenerationBlock);
  assert.match(reviewGenerationBlock[0], /const handleComposerSuccess = \(\) => \{\s*setComposerOpen\(false\);\s*onSuccess\(\);\s*\};/);
  assert.doesNotMatch(reviewGenerationBlock[0], /setActivePage\('library'\)/);
});
```

- [ ] **Step 4: Run the focused source-level test to verify the new assertions fail for the expected reasons**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend && npx tsx --test src/workspace-navigation.test.ts`

Expected: FAIL because the current source still defines `input` and `library`, still labels them `添加课程` and `课程列表`, and has no `ReviewGenerationPage` inline-composer wrapper.

- [ ] **Step 5: Commit only the red test change**

```bash
cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary
git add frontend/src/workspace-navigation.test.ts
git commit -m "test: lock review generation IA"
```

### Task 2: Implement The Unified Review Generation Workspace

**Files:**
- Modify: `frontend/src/App.tsx`
- Test: `frontend/src/workspace-navigation.test.ts`

- [ ] **Step 1: Replace the page type and shell title mapping with the single `review-generation` page key**

```ts
type Page = 'dashboard' | 'review-generation' | 'consultation' | 'calendar' | 'classes' | 'accounts' | 'settings';
```

```ts
const pageTitle: Record<Page, string> = {
  dashboard: '工作台',
  'review-generation': '复习生成',
  consultation: '咨询记录',
  calendar: '课程日历',
  classes: '班级管理',
  accounts: '账号审批',
  settings: '系统设置',
};
```

- [ ] **Step 2: Replace the sidebar and dashboard entry points so all lesson-generation navigation points to `复习生成`**

```ts
{ id: 'review-generation', icon: Library, label: '复习生成' },
```

```tsx
<button onClick={() => setActivePage('review-generation')} className={workspacePrimaryButtonClass}>
  <PlusCircle size={20} />
  新建复习文档
</button>
<button onClick={() => setActivePage('review-generation')} className={workspaceSecondaryButtonClass}>
  <Library size={20} />
  查看历史文档
</button>
```

- [ ] **Step 3: Rename the lesson-success callback so it refreshes the unified page instead of routing to the removed `library` page**

```ts
const handleReviewGenerationSuccess = () => {
  setActivePage('review-generation');
};
```

- [ ] **Step 4: Extract the current library body into a loadable history component with configurable heading and empty-state copy**

```tsx
const ReviewDocumentHistory = ({
  title = '历史文档',
  description = '查看已生成的复习文档，支持下载、预览与删除。',
  emptyMessage = '还没有复习文档，点击「新建复习文档」开始生成',
}: {
  title?: string;
  description?: string;
  emptyMessage?: string;
}) => {
  // reuse the current LibraryPage loading, fetch, delete, table, and PDF actions
};
```

Use the current `LibraryPage` behavior as the implementation base rather than rewriting the data flow.

- [ ] **Step 5: Keep the existing lesson form logic but remap the visible copy to the approved terminology**

Inside the current `LessonInput` component, update the visible strings:

```tsx
<h3 className={`${workspaceSectionTitleClass} mt-3`}>生成复习文档</h3>
```

```tsx
<button onClick={handleGenerate} className={`${workspacePrimaryButtonClass} mt-6 w-full py-4 text-lg font-bold`}>
  生成复习文档
  <ArrowRight size={20} />
</button>
```

Leave the underlying request logic and fields unchanged.

- [ ] **Step 6: Add the new unified page wrapper that shows history by default and expands the form inline when requested**

```tsx
const ReviewGenerationPage = ({ onSuccess }: { onSuccess: () => void }) => {
  const [composerOpen, setComposerOpen] = useState(false);

  const handleComposerSuccess = () => {
    setComposerOpen(false);
    onSuccess();
  };

  return (
    <div className={`${workspacePageClass} space-y-6`}>
      <div className="flex items-center justify-between gap-4">
        <div>
          <h3 className={workspaceSectionTitleClass}>历史文档</h3>
          <p className={`${workspaceSectionTextClass} mt-2`}>查看已生成的复习文档，支持下载、预览与删除。</p>
        </div>
        <button onClick={() => setComposerOpen((current) => !current)} className={workspacePrimaryButtonClass}>
          <PlusCircle size={20} />
          新建复习文档
        </button>
      </div>

      {composerOpen && (
        <div className={`${workspaceCardClass} overflow-hidden`}>
          <LessonInput onSuccess={handleComposerSuccess} />
        </div>
      )}

      <ReviewDocumentHistory />
    </div>
  );
};
```

Keep the wrapper focused on composition. Do not add new API calls.

- [ ] **Step 7: Render the new page from the shell and remove the old `input` and `library` render branches**

```tsx
{activePage === 'review-generation' && <ReviewGenerationPage onSuccess={handleReviewGenerationSuccess} />}
```

- [ ] **Step 8: Run the focused source-level navigation test and confirm it passes**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend && npx tsx --test src/workspace-navigation.test.ts`

Expected: PASS with the new `复习生成` navigation contract locked in.

- [ ] **Step 9: Run the frontend proof covering typecheck and production build**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend && npm run lint && npm run build`

Expected: `tsc --noEmit` passes and Vite build succeeds, with only the existing chunk-size warning if present.

- [ ] **Step 10: Commit the implementation**

```bash
cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary
git add frontend/src/App.tsx frontend/src/workspace-navigation.test.ts
git commit -m "feat: unify review generation workspace"
```

## Self-Review

- **Spec coverage:** The plan covers every approved decision from the spec: one `复习生成` module, `历史文档` as the default landing area, `新建复习文档` as the CTA, `生成复习文档` as the inline form title, and collapse-back-to-history success behavior.
- **Placeholder scan:** No `TODO`, `TBD`, or vague “handle this later” language remains. Each task includes exact files, commands, and target code shapes.
- **Type consistency:** The plan keeps the existing `LessonInput` request flow, introduces the single page key `review-generation`, renames the success callback consistently to `handleReviewGenerationSuccess`, and defines one wrapper component `ReviewGenerationPage` plus one history component `ReviewDocumentHistory`.