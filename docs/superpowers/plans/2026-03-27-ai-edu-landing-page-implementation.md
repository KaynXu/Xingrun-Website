# AI Edu Landing Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refresh the landing page so it presents Xingrun as a B-end AI education solutions provider while keeping the existing visual language and leaving the internal workspace unchanged.

**Architecture:** Keep the current single-file landing page implementation inside `frontend/src/App.tsx`, updating only landing-page-specific copy, icon choices, and CTA behavior. Reuse the existing section structure and motion system so the visual identity stays consistent and the change remains low-risk.

**Tech Stack:** React 19, TypeScript, Vite, Tailwind CSS v4, Motion, Lucide React

---

## File Map

- Modify: `frontend/src/App.tsx`
- Verify: `frontend/package.json` scripts `lint` and `build`

## Verification Strategy

This repo does not include a dedicated frontend UI test framework such as Vitest or Playwright. For this content-focused landing page refresh, verification will use:

- TypeScript check: `npm run lint`
- Production build: `npm run build`
- Visual sanity check by reviewing the rendered landing page structure in code and build output

### Task 1: Refresh Landing Page Brand Framing

**Files:**
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Update landing page branding and navigation copy**

Change the landing-page navbar and footer brand wording from a narrow review-system identity to `星润 AI 教育解决方案`, and update nav labels to match the approved IA:

- `核心方案`
- `落地流程`
- `关于星润`

- [ ] **Step 2: Update hero copy and CTA wording**

Replace the current teacher-facing hero copy with the approved B-end positioning:

- eyebrow: `AI EDU SOLUTION FOR TEAMS`
- headline focused on schools / institutions
- body copy anchored in the existing review system plus broader solution map
- secondary CTA changed from video wording to solution-map wording

Keep the existing hero layout, video background, and motion entrance pattern.

- [ ] **Step 3: Run TypeScript verification**

Run: `npm run lint`

Expected: command exits successfully with no type errors.

### Task 2: Convert Feature Cards Into Solution Modules

**Files:**
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Replace feature-section heading and subheading**

Update the section to describe the broader AI teaching delivery story rather than a single review workflow.

- [ ] **Step 2: Replace the four card titles, descriptions, tags, and icons**

Map the existing card structure to the approved solution modules:

- `课后复习系统`
- `智能错题本`
- `国际课程题库 / 自动组卷`
- `教案与讲义生成`

Preserve the current card composition and color hierarchy. Only change icon semantics where needed.

- [ ] **Step 3: Keep module wording credible**

Ensure only the review system reads like an implemented flagship product. The other modules should read as capability areas / solution expansion, not as fully shipped in-product features.

- [ ] **Step 4: Run TypeScript verification**

Run: `npm run lint`

Expected: command exits successfully with no type errors.

### Task 3: Update Process and Footer Copy

**Files:**
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Replace the process section heading and three steps**

Change the section so it reflects a B-end AI teaching delivery pipeline:

- `教学素材接入`
- `AI 模块处理`
- `面向团队交付`

- [ ] **Step 2: Update footer supporting text**

Keep the existing footer layout but change the short description to emphasize schools, institutions, and teaching teams.

- [ ] **Step 3: Run full production verification**

Run:

```bash
npm run lint
npm run build
```

Expected:

- TypeScript check exits successfully
- Vite production build completes successfully

### Task 4: Review Final Diff and Commit

**Files:**
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Review the final landing-page-only diff**

Run: `git diff -- frontend/src/App.tsx`

Expected: only landing page branding, copy, CTA, icon, and section wording changes appear.

- [ ] **Step 2: Commit the implementation**

Run:

```bash
git add frontend/src/App.tsx docs/superpowers/plans/2026-03-27-ai-edu-landing-page-implementation.md
git commit -m "feat: refresh AI edu landing page positioning"
```

- [ ] **Step 3: Report verification evidence**

Include the exact commands run and whether they passed, with no unverified completion claims.
