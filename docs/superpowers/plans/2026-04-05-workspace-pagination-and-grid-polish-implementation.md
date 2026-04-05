# Workspace Pagination And Grid Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Shorten the credit center, class management, and review history pages by adding client-side pagination where needed and converting long single-column layouts into responsive grids without changing core business behavior.

**Architecture:** Keep the existing backend APIs intact and implement the page-length fixes at the authenticated workspace presentation layer in `frontend/src/App.tsx`. Preserve the backend lesson ordering contract, surface `created_at` as the visible generation timestamp, and add source-based regression tests in `frontend/src/workspace-navigation.test.ts` so the layout and pagination logic stay pinned.

**Tech Stack:** React 19, TypeScript, Vite, source-based node tests with `tsx --test`

---

## File Structure

- Modify: `/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/frontend/src/App.tsx`
  - Add paginated credit ledger rendering.
  - Change class card container from a single-column stack to a responsive grid.
  - Refactor review document history from a table into paginated cards that show generation time.
- Modify: `/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/frontend/src/workspace-navigation.test.ts`
  - Add or update assertions that pin the new pagination state, page slicing, grid classes, and generation-time rendering.

## Task 1: Credit Ledger Pagination

**Files:**
- Modify: `/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/frontend/src/workspace-navigation.test.ts`
- Modify: `/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/frontend/src/App.tsx`

- [ ] **Step 1: Write the failing test**

Add assertions inside the existing `credit center page source supports member drilldown and ledger filtering` test so the source must define pagination state, page slicing, and page-reset behavior:

```ts
assert.match(creditBlock, /const CREDIT_LEDGER_PAGE_SIZE = 10;/);
assert.match(creditBlock, /const \[ledgerPage, setLedgerPage\] = useState\(1\);/);
assert.match(creditBlock, /const totalLedgerPages = Math\.max\(1, Math\.ceil\(filteredLedger\.length \/ CREDIT_LEDGER_PAGE_SIZE\)\);/);
assert.match(creditBlock, /const paginatedLedger = filteredLedger\.slice\(\(ledgerPage - 1\) \* CREDIT_LEDGER_PAGE_SIZE, ledgerPage \* CREDIT_LEDGER_PAGE_SIZE\);/);
assert.match(creditBlock, /useEffect\(\(\) => \{\s*setLedgerPage\(1\);\s*\}, \[ledgerFilter, creditLedger\]\);/);
assert.match(creditBlock, /paginatedLedger\.map\(\(item\) => \{/);
assert.match(creditBlock, /上一页/);
assert.match(creditBlock, /下一页/);
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- workspace-navigation.test.ts`

Expected: FAIL with missing `CREDIT_LEDGER_PAGE_SIZE`, `ledgerPage`, or `paginatedLedger` assertions.

- [ ] **Step 3: Write minimal implementation**

Update `CreditCenterPage` in `frontend/src/App.tsx` with client-side pagination after the existing filter:

```tsx
const CREDIT_LEDGER_PAGE_SIZE = 10;
const [ledgerPage, setLedgerPage] = useState(1);

const filteredLedger = creditLedger.filter((item) => ledgerFilter === 'all' || item.direction === ledgerFilter);
const totalLedgerPages = Math.max(1, Math.ceil(filteredLedger.length / CREDIT_LEDGER_PAGE_SIZE));
const currentLedgerPage = Math.min(ledgerPage, totalLedgerPages);
const paginatedLedger = filteredLedger.slice(
  (currentLedgerPage - 1) * CREDIT_LEDGER_PAGE_SIZE,
  currentLedgerPage * CREDIT_LEDGER_PAGE_SIZE,
);

useEffect(() => {
  setLedgerPage(1);
}, [ledgerFilter, creditLedger]);
```

Render `paginatedLedger` instead of `filteredLedger`, and append compact previous/next controls:

```tsx
{totalLedgerPages > 1 && (
  <div className="flex items-center justify-between border-t border-sky-100/80 pt-3 text-sm dark:border-white/10">
    <button type="button" onClick={() => setLedgerPage((page) => Math.max(1, page - 1))} disabled={currentLedgerPage === 1} className={workspaceSecondaryButtonClass}>
      上一页
    </button>
    <span className="text-slate-500 dark:text-slate-400">
      第 {currentLedgerPage} / {totalLedgerPages} 页
    </span>
    <button type="button" onClick={() => setLedgerPage((page) => Math.min(totalLedgerPages, page + 1))} disabled={currentLedgerPage === totalLedgerPages} className={workspaceSecondaryButtonClass}>
      下一页
    </button>
  </div>
)}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- workspace-navigation.test.ts`

Expected: PASS for the updated credit center source test.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.tsx frontend/src/workspace-navigation.test.ts
git commit -m "feat: paginate credit ledger list"
```

## Task 2: Class Card Three-Column Grid

**Files:**
- Modify: `/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/frontend/src/workspace-navigation.test.ts`
- Modify: `/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/frontend/src/App.tsx`

- [ ] **Step 1: Write the failing test**

Add assertions in the class-management source tests so the card list must use a responsive grid for both collapsed cards and the inline new-card form:

```ts
assert.match(classManagementBlock, /<div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">/);
assert.match(classManagementBlock, /className=\{`\$\{workspaceSoftCardClass\} overflow-hidden p-5`\}/);
```

If needed, split the assertion across the existing single-expand card test so it specifically checks the list container now includes `xl:grid-cols-3`.

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- workspace-navigation.test.ts`

Expected: FAIL because the current class list still renders with `className="grid gap-4"` only.

- [ ] **Step 3: Write minimal implementation**

Change the list wrapper inside `ClassManagementPage` from:

```tsx
<div className="grid gap-4">
```

to:

```tsx
<div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
```

Keep each card’s current expand/collapse behavior intact. Do not split card editing into a separate drawer or modal.

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- workspace-navigation.test.ts`

Expected: PASS for the updated class-management grid assertion.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.tsx frontend/src/workspace-navigation.test.ts
git commit -m "feat: show class cards in a responsive grid"
```

## Task 3: Review History Generation Time, Card Grid, And Pagination

**Files:**
- Modify: `/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/frontend/src/workspace-navigation.test.ts`
- Modify: `/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/frontend/src/App.tsx`

- [ ] **Step 1: Write the failing test**

Add or extend the existing review-generation tests so the history component must define pagination state, visible generation time, and a grid card layout:

```ts
const historyBlock = requireMatch(/const ReviewDocumentHistory = \(\{[\s\S]*?\n};/);

assert.match(historyBlock, /const REVIEW_HISTORY_PAGE_SIZE = 12;/);
assert.match(historyBlock, /const \[historyPage, setHistoryPage\] = useState\(1\);/);
assert.match(historyBlock, /const totalHistoryPages = Math\.max\(1, Math\.ceil\(lessons\.length \/ REVIEW_HISTORY_PAGE_SIZE\)\);/);
assert.match(historyBlock, /const paginatedLessons = lessons\.slice\(\(historyPage - 1\) \* REVIEW_HISTORY_PAGE_SIZE, historyPage \* REVIEW_HISTORY_PAGE_SIZE\);/);
assert.match(historyBlock, /useEffect\(\(\) => \{\s*setHistoryPage\(1\);\s*\}, \[lessons\]\);/);
assert.match(historyBlock, /生成时间/);
assert.match(historyBlock, /new Date\(lesson\.created_at\)\.toLocaleString\('zh-CN'\)/);
assert.match(historyBlock, /<div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">/);
assert.doesNotMatch(historyBlock, /<table className="w-full border-collapse text-left">/);
assert.match(historyBlock, /上一页/);
assert.match(historyBlock, /下一页/);
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- workspace-navigation.test.ts`

Expected: FAIL because `ReviewDocumentHistory` still uses a table and has no `historyPage` or `生成时间` output.

- [ ] **Step 3: Write minimal implementation**

Refactor `ReviewDocumentHistory` to keep the existing fetch and action handlers but change the view layer:

```tsx
const REVIEW_HISTORY_PAGE_SIZE = 12;
const [historyPage, setHistoryPage] = useState(1);

const totalHistoryPages = Math.max(1, Math.ceil(lessons.length / REVIEW_HISTORY_PAGE_SIZE));
const currentHistoryPage = Math.min(historyPage, totalHistoryPages);
const paginatedLessons = lessons.slice(
  (currentHistoryPage - 1) * REVIEW_HISTORY_PAGE_SIZE,
  currentHistoryPage * REVIEW_HISTORY_PAGE_SIZE,
);

useEffect(() => {
  setHistoryPage(1);
}, [lessons]);
```

Replace the table with cards:

```tsx
<div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
  {paginatedLessons.map((lesson) => (
    <div key={lesson.id} className={`${workspaceSoftCardClass} flex h-full flex-col justify-between p-5`}>
      <div className="space-y-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="font-semibold text-slate-900 dark:text-white">{lesson.topic || `${lesson.subject} 课程`}</p>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">课程日期：{lesson.date || '未填写'}</p>
          </div>
          <div className={cn('h-2.5 w-2.5 rounded-full', lesson.pdf_path ? 'bg-emerald-500' : 'bg-slate-300 dark:bg-slate-600')} />
        </div>
        <div className="flex flex-wrap gap-2">
          {lesson.subject && <span className="rounded-full bg-sky-50 px-2.5 py-1 text-[10px] font-bold tracking-[0.16em] text-sky-700 dark:bg-sky-900/40 dark:text-sky-300">{lesson.subject}</span>}
          {lesson.grade && <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[10px] font-bold tracking-[0.16em] text-slate-500 dark:bg-white/5 dark:text-slate-400">{lesson.grade}</span>}
        </div>
        <div className="grid gap-2 text-sm text-slate-500 dark:text-slate-400">
          <p>生成时间：{new Date(lesson.created_at).toLocaleString('zh-CN')}</p>
          <p>PDF 状态：{lesson.pdf_path ? '已生成' : '无'}</p>
        </div>
      </div>
      <div className="mt-5 flex justify-end gap-2">
        {/* keep continue feedback / preview / download / delete actions */}
      </div>
    </div>
  ))}
</div>
```

Append pagination controls similar to the credit ledger section and keep all existing button handlers unchanged.

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- workspace-navigation.test.ts`

Expected: PASS for the updated review-generation history source assertions.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.tsx frontend/src/workspace-navigation.test.ts
git commit -m "feat: paginate review history cards"
```

## Task 4: Full Frontend Verification

**Files:**
- Modify: `/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/frontend/src/App.tsx`
- Modify: `/Users/ark.mini/Desktop/Xingrun-Website/Xingrun-Summary/frontend/src/workspace-navigation.test.ts`

- [ ] **Step 1: Run the targeted regression suite**

Run: `npm test -- workspace-navigation.test.ts`

Expected: PASS with all workspace-navigation assertions green.

- [ ] **Step 2: Run the full frontend suite**

Run: `npm test`

Expected: PASS with all `src/*.test.ts` and `src/*.test.tsx` files green.

- [ ] **Step 3: Run TypeScript verification**

Run: `npm run lint`

Expected: PASS with `tsc --noEmit` exit code 0.

- [ ] **Step 4: Inspect the diff before the final commit**

Run: `git diff -- frontend/src/App.tsx frontend/src/workspace-navigation.test.ts`

Expected: Only the planned pagination, grid, and history-rendering changes appear.

- [ ] **Step 5: Commit the integrated implementation**

If the task commits above were created independently by subagents, create no extra code commit here. If the work was executed inline without per-task commits, commit the final integrated diff:

```bash
git add frontend/src/App.tsx frontend/src/workspace-navigation.test.ts
git commit -m "feat: shorten workspace pages with pagination and grids"
```

## Self-Review

- Spec coverage:
  - Credit ledger pagination is covered by Task 1.
  - Class card three-column desktop layout is covered by Task 2.
  - Review history generation-time visibility plus newest-first presentation is covered by Task 3.
  - Full-suite verification is covered by Task 4.
- Placeholder scan:
  - All tasks include exact files, commands, expected outcomes, and concrete code snippets.
- Type consistency:
  - `ledgerPage`, `historyPage`, `paginatedLedger`, and `paginatedLessons` are named consistently across tests and implementation.
