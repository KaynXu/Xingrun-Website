# Workspace Tab Redesign Design

## Goal

Rewrite the 工作台 tab so it behaves like the homepage of a multi-function platform instead of a review-generation landing page.

The redesign must keep the existing shell navigation intact, but replace the current single dashboard body with a role-aware workspace home that matches the product's current scope.

## Scope

This redesign only covers the main content area of the 工作台 tab.

Included:
- Replace the current dashboard body with role-aware homepage content.
- Split the homepage into three role groups:
  - `super_owner`
  - `owner` and `admin`
  - `member` and teacher-like day-to-day operators
- Reuse existing routes, existing navigation shell, and existing real data sources.
- Reorganize existing actions and summaries so the workspace reflects the current platform.

Excluded:
- No redesign of the left sidebar navigation model.
- No redesign of non-dashboard tabs.
- No new task system.
- No fake notification center.
- No backend-first expansion that requires new APIs before the homepage can ship.

## Product Positioning

The old dashboard was designed when the product mainly generated review materials.

That is no longer the product boundary. The homepage must now act as a role-aware control surface:
- `super_owner` sees a platform-level cross-organization overview.
- `owner/admin` sees an organization operations overview.
- `member/teacher` sees a start-work surface focused on real actions they can take now.

The redesign should make the product feel like a real platform homepage, not a repainted single-tool launcher.

## Information Architecture

All three workspace homes keep the same structural rhythm:

1. `hero`
2. `metrics`
3. `primary content`
4. `secondary actions or entry panels`

This keeps the product coherent while allowing the content emphasis to differ by role.

### Super Owner Home

Purpose:
- Show cross-organization platform status at a glance.
- Surface global scale, activity, and abnormal signals.
- Provide a small number of high-value platform control entry points.

Top priorities:
- Platform-level totals rather than institution-level workflow details.
- Cross-organization comparisons and visibility.
- System-wide oversight tone.

Proposed modules:
- Hero summary with total organizations, active accounts, total generated content, recent overall trend summary.
- Metrics row for platform-wide KPIs.
- Organization observation section:
  - most active organizations
  - recently active organizations
  - organizations needing attention if existing data can support it
- Platform entry section:
  - account approval
  - organization-facing management view
  - system settings

This page should not foreground teacher actions like creating a review document.

### Owner And Admin Home

Purpose:
- Show how one organization is operating.
- Surface internal teaching operations, account status, and content production.
- Provide direct access to key management surfaces.

Top priorities:
- Organization health first.
- Internal visibility second.
- Management entry points third.

Proposed modules:
- Hero summary describing current organization status for the week or month.
- Metrics row with real organization-level stats such as:
  - class count
  - teacher or account count if available
  - recent generation volume
  - pending approvals if available
- Operations observation area:
  - class activity
  - recent generated content
  - classroom feedback coverage if real data exists
- Management entry grid:
  - class management
  - account approvals
  - classroom feedback
  - smart wrong questions

This page should no longer present review generation as the singular centerpiece.

### Member And Teacher Home

Purpose:
- Act as a practical start-work surface.
- Prioritize real actions and real personal teaching context.
- Avoid pretending there is an implemented task system when there is not.

Top priorities:
- High-frequency actions first.
- Personal teaching overview second.
- Recent work artifacts third.

Proposed modules:
- Hero summary framed as a personal workbench.
- Quick action row with real entry points only, such as:
  - review generation
  - classroom feedback
  - course calendar
  - smart wrong questions
- Personal overview metrics using real data where available, such as:
  - responsible class count
  - responsible student count if available
  - recent lesson or generation count
- Recent work section using existing real records:
  - recent lessons
  - recent generated documents
  - recent classroom feedback related entry points if data is already present

This page must not use pseudo-waiting states like “today's pending tasks” unless the underlying feature actually exists.

## Visual And Layout Rules

- Keep the existing global workspace shell, including sidebar and top header behavior.
- Apply layout differences only inside the dashboard content region.
- Preserve one recognizable product language across all three role homes.
- `super_owner` and `owner/admin` can lean more heavily on data and observation panels.
- `member/teacher` should lean more heavily on action cards and personal context.
- Every module must map to either:
  - an existing real API-backed dataset, or
  - an existing real navigation entry point.
- If a desirable panel has no trustworthy data source yet, degrade it into a simple entry card instead of inventing fake state.

## Technical Design

The current dashboard logic should not keep growing inside `/frontend/src/App.tsx`.

Recommended frontend structure:
- Keep a small dashboard entry point in `/frontend/src/App.tsx`.
- Move workspace-home rendering into dedicated components under `/frontend/src/`.
- Introduce one role-aware dispatch layer that maps the current user role to one of three homepage components.

Expected component split:
- One shared dashboard container or shared section primitives if useful.
- One component for `super_owner` homepage.
- One component for `owner/admin` homepage.
- One component for `member/teacher` homepage.

The exact filenames can be chosen during planning, but the design intent is clear: do not keep three role dashboards inline inside `App.tsx`.

## Data Constraints

The redesign should prefer existing endpoints and existing data already loaded in the frontend.

Primary rule:
- Do not make new backend APIs a prerequisite for the first delivery of this workspace rewrite.

Likely reusable sources include existing dashboard stats, review-plan history, class-related data, account-related data, and already available role checks.

If some desired panel cannot be powered by existing data:
- either omit it in v1, or
- render it as a static navigation panel without fake counts or fake alerts.

## Implementation Constraints

- This is a medium-sized change and should be done on a new branch from `develop`.
- The current working tree already contains uncommitted changes, including files that overlap with the dashboard surface.
- Branch execution should not accidentally absorb unrelated in-progress edits.
- Isolation of those dirty changes must be resolved before implementation starts.

## Testing Strategy

The redesign needs focused frontend tests that verify:
- role-based dashboard dispatch
- correct rendering of role-specific modules
- absence of fake task-oriented content for `member/teacher`
- preserved navigation behavior from quick action and management entry cards

Tests should validate real rendered content and component routing, not just string snapshots.

## Risks

### Overfitting To Nonexistent Features

Risk:
- The homepage tries to communicate operational maturity that the product does not yet implement.

Mitigation:
- Restrict modules to real data and real actions.

### App.tsx Growth Continues

Risk:
- The redesign lands visually but keeps all logic inside the main app file.

Mitigation:
- Split role homes into dedicated components as part of the rewrite.

### Dirty Working Tree Interference

Risk:
- Existing unrelated edits leak into the dashboard rewrite branch and complicate review.

Mitigation:
- Resolve branch isolation before implementation.

## Recommended Delivery Shape

The first implementation pass should deliver:
- role-aware dashboard body dispatch
- the three role-specific homepage layouts
- reuse of existing data sources only
- focused tests for role-driven rendering and key navigation actions

Anything beyond that should be treated as a follow-up, not hidden inside this rewrite.