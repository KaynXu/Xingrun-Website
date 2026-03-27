# Starain Homepage Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refresh the public landing and legal pages around the `Starain` brand with the approved bright AI+Edu visual direction and workflow-first messaging.

**Architecture:** Keep the landing and legal experiences inside the existing [frontend/src/App.tsx](/Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend/src/App.tsx) component tree so the refactor stays aligned with current project structure. Use [frontend/src/index.css](/Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend/src/index.css) for shared light-theme tokens and scrollbar updates, and lock the content and shell changes with server-rendered assertions in [frontend/src/landing-legal-pages.test.tsx](/Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend/src/landing-legal-pages.test.tsx).

**Tech Stack:** React 19, TypeScript, Vite, Tailwind CSS v4, Node test runner via `tsx --test`

---

## File Structure

- Modify: [frontend/src/App.tsx](/Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend/src/App.tsx) — landing hero, workflow cards, process/about sections, and legal page brand/shell refresh
- Modify: [frontend/src/index.css](/Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend/src/index.css) — shared theme tokens, global body colors, and scrollbar colors
- Modify: [frontend/src/landing-legal-pages.test.tsx](/Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend/src/landing-legal-pages.test.tsx) — regression tests for brand, copy, workflow sections, and bright-shell classes

## Notes Before Starting

- The repo already has unrelated local data changes (`data/*.db`, `.DS_Store`, `Assets/`). Do not stage them.
- Use targeted `git add` commands in every commit step.
- Run commands from `/Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend` unless a step says otherwise.

### Task 1: Rebrand the landing hero and legal surfaces to Starain

**Files:**
- Modify: [frontend/src/landing-legal-pages.test.tsx](/Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend/src/landing-legal-pages.test.tsx):8-74
- Modify: [frontend/src/App.tsx](/Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend/src/App.tsx):1578-1794
- Test: [frontend/src/landing-legal-pages.test.tsx](/Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend/src/landing-legal-pages.test.tsx)

- [ ] **Step 1: Write the failing test**

```tsx
test('landing page renders Starain hero branding and approved messaging', () => {
  const LandingPage = (AppModule as {
    LandingPage?: React.ComponentType<{
      onLogin: () => void;
      onRegister: () => void;
    }>;
  }).LandingPage;

  assert.equal(typeof LandingPage, 'function');

  const markup = renderToStaticMarkup(
    <LandingPage onLogin={() => undefined} onRegister={() => undefined} />,
  );

  assert.match(markup, /Starain/);
  assert.match(markup, /AI Edu Platform/);
  assert.match(markup, /教育工作流终于被 AI 重新组织好了/);
  assert.match(markup, /查看平台方案/);
  assert.match(markup, /申请试用/);
  assert.doesNotMatch(markup, /星润 AI 教育解决方案/);
});

test('legal pages use Starain branding in the chrome', () => {
  const LandingLegalPage = (AppModule as {
    LandingLegalPage?: React.ComponentType<{
      documentKey: 'privacy' | 'terms';
    }>;
  }).LandingLegalPage;

  assert.equal(typeof LandingLegalPage, 'function');

  const markup = renderToStaticMarkup(
    <LandingLegalPage documentKey="privacy" />,
  );

  assert.match(markup, /Starain/);
  assert.match(markup, /AI Edu Platform/);
  assert.doesNotMatch(markup, /星润 AI 教育解决方案/);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx tsx --test src/landing-legal-pages.test.tsx`

Expected: FAIL with `AssertionError` because the landing and legal pages still render `星润 AI 教育解决方案`, still use the old English hero copy, and do not expose the new CTA labels.

- [ ] **Step 3: Write minimal implementation**

Update the landing/legal brand and hero copy in [frontend/src/App.tsx](/Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend/src/App.tsx):

```tsx
<p className="text-lg font-bold tracking-tight truncate">Starain</p>
<p className="text-xs text-slate-500 tracking-[0.28em]">AI EDU PLATFORM</p>
```

```tsx
<span className="text-xl font-bold tracking-tight">Starain</span>
<span className="text-xs font-semibold uppercase tracking-[0.32em] text-sky-600">
  AI Edu Platform
</span>
```

```tsx
<span className="inline-flex items-center rounded-full border border-sky-200 bg-white/80 px-4 py-1.5 text-xs font-semibold tracking-[0.3em] text-sky-700 mb-6">
  BUILT FROM REAL TEACHING PRACTICE
</span>
<h1 className="mt-6 text-5xl md:text-7xl font-black leading-[0.95] tracking-tight text-slate-900 mb-8">
  教育工作流终于被 AI
  <br />
  重新组织好了
</h1>
<p className="text-lg md:text-xl text-slate-600 max-w-3xl mx-auto mb-12 leading-relaxed">
  Starain 起源于真实教学场景。我们先为自己的机构解决复习资料、题库沉淀、讲义生成与教学协同的问题，
  再把这套已验证的工作流产品化，帮助更多教育团队完成 AI 化升级。
</p>
<button onClick={onLogin}>查看平台方案</button>
<button onClick={onRegister}>申请试用</button>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx tsx --test src/landing-legal-pages.test.tsx`

Expected: PASS with the new `Starain`, `AI Edu Platform`, hero headline, and CTA assertions green.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.tsx frontend/src/landing-legal-pages.test.tsx
git commit -m "feat: rebrand landing hero to Starain"
```

### Task 2: Reframe feature, process, and about sections around the workflow story

**Files:**
- Modify: [frontend/src/landing-legal-pages.test.tsx](/Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend/src/landing-legal-pages.test.tsx):8-74
- Modify: [frontend/src/App.tsx](/Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend/src/App.tsx):1797-2000
- Test: [frontend/src/landing-legal-pages.test.tsx](/Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend/src/landing-legal-pages.test.tsx)

- [ ] **Step 1: Write the failing test**

Add one workflow-story regression test:

```tsx
test('landing page tells the validated workflow story', () => {
  const LandingPage = (AppModule as {
    LandingPage?: React.ComponentType<{
      onLogin: () => void;
      onRegister: () => void;
    }>;
  }).LandingPage;

  assert.equal(typeof LandingPage, 'function');

  const markup = renderToStaticMarkup(
    <LandingPage onLogin={() => undefined} onRegister={() => undefined} />,
  );

  assert.match(markup, /从课堂素材到复习交付/);
  assert.match(markup, /把错误沉淀成可追踪资产/);
  assert.match(markup, /把题目沉淀成可调用的题库系统/);
  assert.match(markup, /把课程目标转化为讲义与教研交付/);
  assert.match(markup, /教学素材进入平台/);
  assert.match(markup, /AI 完成结构化处理/);
  assert.match(markup, /输出到复习与教学协同/);
  assert.match(markup, /关于 Starain/);
  assert.match(markup, /不是从 PPT 里想出来的/);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx tsx --test src/landing-legal-pages.test.tsx`

Expected: FAIL because the page still renders the older feature labels (`课后复习系统`, `智能错题本`, `国际课程题库 / 自动组卷`) and the existing about copy does not reference the validated internal workflow story.

- [ ] **Step 3: Write minimal implementation**

Rewrite the section copy in [frontend/src/App.tsx](/Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend/src/App.tsx):

```tsx
<h2 className="text-4xl md:text-5xl font-bold mb-4">把真实教学流程整理成可复用的 AI 能力</h2>
<p className="text-slate-600 text-lg">不是堆叠功能点，而是把一条已经跑通的教育工作流产品化。</p>
```

```tsx
<h3 className="text-3xl font-bold mb-4 text-slate-900">从课堂素材到复习交付</h3>
<p className="text-slate-600 text-lg max-w-2xl">
  课堂录音、笔记与教学内容进入平台后，被整理成结构化复习资料、练习内容与可复用的交付资产。
</p>
```

```tsx
<h3 className="text-2xl font-bold mb-4 text-slate-900">把错误沉淀成可追踪资产</h3>
<p className="text-slate-600">
  不是一次性纠错，而是持续记录高频错误、薄弱点与个性化复习路径。
</p>
```

```tsx
<h3 className="text-2xl font-bold mb-4 text-slate-900">把题目沉淀成可调用的题库系统</h3>
<p className="text-slate-600">
  面向 AP、A-Level、IB 等课程，把零散题目变成可标签化、可复用、可自动组卷的题库资产。
</p>
```

```tsx
<h3 className="text-3xl font-bold mb-4 text-slate-900">把课程目标转化为讲义与教研交付</h3>
<p className="text-slate-600 text-lg">
  从课程目标到讲义、课堂提纲和教研素材，减少教师重复整理工作。
</p>
```

```tsx
[
  { step: '01', title: '教学素材进入平台', desc: '录音、笔记、题目、课件等教学资料进入统一工作台。' },
  { step: '02', title: 'AI 完成结构化处理', desc: '提炼重点、识别薄弱点、归档题目并生成讲义草稿。' },
  { step: '03', title: '输出到复习与教学协同', desc: '生成复习资料、错题沉淀、题库调用与团队复用内容。' },
]
```

```tsx
<span className="inline-flex items-center rounded-full border border-slate-200 bg-white/80 px-4 py-1.5 text-xs font-semibold tracking-[0.28em] text-slate-500">
  ABOUT STARAIN
</span>
<h2 className="text-4xl md:text-5xl font-bold mb-4 text-slate-900">关于 Starain</h2>
<p className="max-w-2xl text-lg text-slate-600 leading-relaxed">
  Starain 不是从 PPT 里想出来的，而是从真实教学现场长出来的。
</p>
<p className="max-w-2xl text-sm md:text-base text-slate-500 leading-relaxed">
  我们先在自己的教育机构中解决复习资料、题库沉淀、讲义生成与教学协同问题，再把这套已经跑通的流程产品化，服务更多同行团队。
</p>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx tsx --test src/landing-legal-pages.test.tsx`

Expected: PASS with the workflow card titles, process-stage titles, and new about-story assertions green.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.tsx frontend/src/landing-legal-pages.test.tsx
git commit -m "feat: align landing sections with workflow story"
```

### Task 3: Replace the dark shell with the approved bright Starain theme

**Files:**
- Modify: [frontend/src/landing-legal-pages.test.tsx](/Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend/src/landing-legal-pages.test.tsx):8-74
- Modify: [frontend/src/App.tsx](/Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend/src/App.tsx):1578-2000
- Modify: [frontend/src/index.css](/Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend/src/index.css):1-33
- Test: [frontend/src/landing-legal-pages.test.tsx](/Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend/src/landing-legal-pages.test.tsx)

- [ ] **Step 1: Write the failing test**

Add a shell-regression test that locks the new light wrapper:

```tsx
test('landing and legal pages use the bright Starain shell', () => {
  const LandingPage = (AppModule as {
    LandingPage?: React.ComponentType<{
      onLogin: () => void;
      onRegister: () => void;
    }>;
  }).LandingPage;
  const LandingLegalPage = (AppModule as {
    LandingLegalPage?: React.ComponentType<{
      documentKey: 'privacy' | 'terms';
    }>;
  }).LandingLegalPage;

  assert.equal(typeof LandingPage, 'function');
  assert.equal(typeof LandingLegalPage, 'function');

  const landingMarkup = renderToStaticMarkup(
    <LandingPage onLogin={() => undefined} onRegister={() => undefined} />,
  );
  const legalMarkup = renderToStaticMarkup(
    <LandingLegalPage documentKey="terms" />,
  );

  assert.doesNotMatch(landingMarkup, /min-h-screen bg-black text-white/);
  assert.doesNotMatch(legalMarkup, /min-h-screen bg-black text-white/);
  assert.match(landingMarkup, /bg-\[#F6FBFF\]/);
  assert.match(landingMarkup, /text-slate-900/);
  assert.match(legalMarkup, /bg-\[#F6FBFF\]/);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx tsx --test src/landing-legal-pages.test.tsx`

Expected: FAIL because the landing and legal wrappers still use `bg-black text-white`, and no bright-shell class such as `bg-[#F6FBFF]` is present.

- [ ] **Step 3: Write minimal implementation**

Update [frontend/src/index.css](/Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend/src/index.css):

```css
@theme {
  --font-sans: "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "Helvetica Neue", Helvetica, Arial, sans-serif;
  --color-brand-blue: #2F80ED;
  --color-brand-cyan: #22C7E8;
  --color-brand-ink: #16324F;
  --color-brand-surface: #F6FBFF;
}

@layer base {
  body {
    @apply bg-[#F6FBFF] text-slate-900 antialiased;
    font-family: var(--font-sans);
  }
}

::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 10px;
}

::-webkit-scrollbar-thumb:hover {
  background: #94a3b8;
}
```

Update the landing/legal wrappers in [frontend/src/App.tsx](/Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend/src/App.tsx):

```tsx
<div className="min-h-screen bg-[#F6FBFF] text-slate-900 selection:bg-sky-200/70">
```

```tsx
<nav className="fixed top-0 w-full z-50 border-b border-sky-100/80 bg-white/80 backdrop-blur-xl">
```

```tsx
<section className="relative min-h-screen overflow-hidden bg-[radial-gradient(circle_at_top_left,_rgba(34,199,232,0.18),_transparent_28%),radial-gradient(circle_at_85%_15%,_rgba(47,128,237,0.16),_transparent_24%),linear-gradient(180deg,_#F8FBFF_0%,_#EEF6FF_100%)]">
```

```tsx
<div className="rounded-[2rem] border border-sky-100 bg-white/85 p-8 md:p-12 shadow-[0_30px_90px_rgba(47,128,237,0.08)]">
```

- [ ] **Step 4: Run test, lint, and build to verify it passes**

Run: `npx tsx --test src/landing-legal-pages.test.tsx && npm run lint && npm run build`

Expected:

- `tsx --test` reports all landing/legal tests passing
- `npm run lint` exits cleanly
- `npm run build` finishes with a successful Vite production build

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.tsx frontend/src/index.css frontend/src/landing-legal-pages.test.tsx
git commit -m "feat: apply bright Starain landing theme"
```

### Task 4: Final verification and cleanup

**Files:**
- Modify: [frontend/src/App.tsx](/Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend/src/App.tsx)
- Modify: [frontend/src/index.css](/Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend/src/index.css)
- Modify: [frontend/src/landing-legal-pages.test.tsx](/Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend/src/landing-legal-pages.test.tsx)

- [ ] **Step 1: Run the full frontend verification suite**

Run: `npx tsx --test src/landing-legal-pages.test.tsx src/account-card.test.tsx && npm run lint && npm run build`

Expected:

- 6+ landing/account tests pass
- TypeScript exits with no errors
- Vite build completes successfully

- [ ] **Step 2: Inspect the staged diff to confirm scope**

Run: `git diff -- frontend/src/App.tsx frontend/src/index.css frontend/src/landing-legal-pages.test.tsx`

Expected: Only the public landing/legal branding, copy, and light-theme changes appear.

- [ ] **Step 3: Commit the final polish if needed**

If Task 4 required any follow-up edits:

```bash
git add frontend/src/App.tsx frontend/src/index.css frontend/src/landing-legal-pages.test.tsx
git commit -m "chore: polish Starain landing refresh"
```

If no additional edits were needed, skip this commit and keep the Task 1-3 commits as the final history.
