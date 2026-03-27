# Landing Legal Pages Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add standalone privacy-policy and terms-of-service landing pages that are reachable from the homepage footer and keep the current single-page app architecture lightweight.

**Architecture:** Reuse `frontend/src/App.tsx` instead of introducing a router. Add a small hash-driven legal-page layer so `#privacy-policy` and `#terms-of-service` render dedicated full-page views, while the default landing page remains unchanged for the main homepage path.

**Tech Stack:** React 19, TypeScript, Vite, Tailwind CSS v4, Motion, Lucide React, `node:test`, `tsx`

---

## File Map

- Modify: `frontend/src/App.tsx`
- Create: `frontend/src/landing-legal-pages.test.tsx`
- Modify: `docs/superpowers/plans/2026-03-27-landing-legal-pages-implementation.md`

## Verification Strategy

- Targeted TDD run: `npx tsx --test src/landing-legal-pages.test.tsx`
- TypeScript check: `npm run lint`
- Production build: `npm run build`

### Task 1: Add Failing Tests For Landing Legal Page Rendering

**Files:**
- Create: `frontend/src/landing-legal-pages.test.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
import test from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

import * as AppModule from './App';

test('landing page footer exposes standalone legal page links', () => {
  const LandingPage = (AppModule as { LandingPage?: React.ComponentType<{
    onLogin: () => void;
    onRegister: () => void;
  }> }).LandingPage;

  assert.equal(typeof LandingPage, 'function');

  const markup = renderToStaticMarkup(
    <LandingPage onLogin={() => undefined} onRegister={() => undefined} />,
  );

  assert.match(markup, /href="#privacy-policy"/);
  assert.match(markup, /href="#terms-of-service"/);
});

test('privacy policy page renders privacy-specific sections', () => {
  const LandingLegalPage = (AppModule as { LandingLegalPage?: React.ComponentType<{
    documentKey: 'privacy' | 'terms';
  }> }).LandingLegalPage;

  assert.equal(typeof LandingLegalPage, 'function');

  const markup = renderToStaticMarkup(<LandingLegalPage documentKey="privacy" />);

  assert.match(markup, /隐私政策/);
  assert.match(markup, /我们如何收集和使用信息/);
  assert.match(markup, /课堂录音、笔记、PDF/);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx tsx --test src/landing-legal-pages.test.tsx`

Expected: FAIL because `LandingPage` or `LandingLegalPage` is not exported yet, and the footer still points to `#`.

- [ ] **Step 3: Write minimal implementation**

Add exports for the landing components and replace placeholder footer links with hash-based standalone page links.

- [ ] **Step 4: Run test to verify it passes**

Run: `npx tsx --test src/landing-legal-pages.test.tsx`

Expected: PASS with both tests green.

### Task 2: Implement Standalone Privacy Policy and Terms Views

**Files:**
- Modify: `frontend/src/App.tsx`
- Test: `frontend/src/landing-legal-pages.test.tsx`

- [ ] **Step 1: Write the next failing test**

```tsx
test('terms page renders service-boundary sections', () => {
  const LandingLegalPage = (AppModule as { LandingLegalPage?: React.ComponentType<{
    documentKey: 'privacy' | 'terms';
  }> }).LandingLegalPage;

  assert.equal(typeof LandingLegalPage, 'function');

  const markup = renderToStaticMarkup(<LandingLegalPage documentKey="terms" />);

  assert.match(markup, /服务条款/);
  assert.match(markup, /账号注册与使用/);
  assert.match(markup, /AI 生成内容说明/);
  assert.match(markup, /争议解决/);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx tsx --test src/landing-legal-pages.test.tsx`

Expected: FAIL because the terms content has not been added yet.

- [ ] **Step 3: Write minimal implementation**

Create a shared legal-document data structure in `frontend/src/App.tsx` and render two standalone article pages with:

- page title
- update date
- back-to-home link
- sections tailored to the actual product behavior

- [ ] **Step 4: Run test to verify it passes**

Run: `npx tsx --test src/landing-legal-pages.test.tsx`

Expected: PASS with the terms assertions green.

### Task 3: Wire Hash-Based Navigation Into The Landing Experience

**Files:**
- Modify: `frontend/src/App.tsx`
- Test: `frontend/src/landing-legal-pages.test.tsx`

- [ ] **Step 1: Write the next failing test**

```tsx
test('landing app hash helper maps legal hashes to standalone pages', () => {
  const getLandingLegalPageFromHash = (AppModule as {
    getLandingLegalPageFromHash?: (hash: string) => 'privacy' | 'terms' | null;
  }).getLandingLegalPageFromHash;

  assert.equal(typeof getLandingLegalPageFromHash, 'function');
  assert.equal(getLandingLegalPageFromHash('#privacy-policy'), 'privacy');
  assert.equal(getLandingLegalPageFromHash('#terms-of-service'), 'terms');
  assert.equal(getLandingLegalPageFromHash('#features'), null);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx tsx --test src/landing-legal-pages.test.tsx`

Expected: FAIL because the helper does not exist yet.

- [ ] **Step 3: Write minimal implementation**

Add a small hash parser and use it inside the landing page so:

- homepage footer links open standalone legal pages
- direct visits to `#privacy-policy` and `#terms-of-service` render those pages
- returning home clears back to the regular landing content

- [ ] **Step 4: Run test to verify it passes**

Run: `npx tsx --test src/landing-legal-pages.test.tsx`

Expected: PASS with all legal-page tests green.

### Task 4: Run Full Verification And Commit

**Files:**
- Modify: `frontend/src/App.tsx`
- Create: `frontend/src/landing-legal-pages.test.tsx`
- Modify: `docs/superpowers/plans/2026-03-27-landing-legal-pages-implementation.md`

- [ ] **Step 1: Run full verification**

Run:

```bash
npx tsx --test src/account-card.test.tsx src/landing-legal-pages.test.tsx
npm run lint
npm run build
```

Expected:

- all node tests pass
- TypeScript exits cleanly
- Vite build completes successfully

- [ ] **Step 2: Review focused diff**

Run: `git diff -- frontend/src/App.tsx frontend/src/landing-legal-pages.test.tsx docs/superpowers/plans/2026-03-27-landing-legal-pages-implementation.md`

Expected: diff is limited to landing legal page behavior, tests, and the new plan doc.

- [ ] **Step 3: Commit the implementation**

Run:

```bash
git add frontend/src/App.tsx frontend/src/landing-legal-pages.test.tsx docs/superpowers/plans/2026-03-27-landing-legal-pages-implementation.md
git commit -m "feat: add landing legal pages"
```
