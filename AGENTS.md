# Workspace Rules

- If the current workspace or project folder contains an `AGENTS.md`, read it before making changes.
- Every meaningful code or content change should end with a git commit after verification.
- Do not leave deployable project changes in a long-lived uncommitted state unless the user explicitly asks for WIP only.
- When a working folder is not itself a git repository, call that out clearly before assuming its files can be versioned.

## Strict Git Development Workflow

Follow this Git workflow unless the user explicitly says otherwise.

### Branch Strategy

- All daily development, fixes, and small changes must start from a new feature branch based on `develop`.
- Do not develop directly on `master` or `develop`.
- New branch names should clearly describe the task.

### Pre-Work Checks

- Before each development task, confirm the local code is current with the remote repository.
- Fetch the latest remote metadata and verify local `develop` is synchronized with `origin/develop`.
- If local `develop` is not synchronized with `origin/develop`, synchronize it before creating a new branch or making changes.

### Development And Merge Flow

- After the task is complete, merge the changes back into `develop` first.
- The default target branch is always `develop`, not `master`.
- Merges to `master` must never be automated; they require manual human confirmation and action.

### Master Rules

- Do not automatically merge a feature branch into `master`.
- Do not modify, push, or merge `master` without explicit human confirmation.
- If the workflow reaches a `master` step, stop and wait for human handling.

### Worktree Rules

- If the task uses a `worktree`, close and clean up that worktree after the branch is complete and merged back into `develop`.
- Do not leave unused worktrees behind at the end of a task.

### Execution Checklist

- Check remote freshness before starting development.
- Create a new branch from `develop`.
- Merge completed work back into `develop`.
- Leave `master` for manual human merges only.
- Close any worktree after the merge.
- Before any development operation, self-check this workflow. If an action would violate these rules, stop and warn the user first.

## Global Collaboration Rules

### Working Habits

- At the start of each project, check whether `AGENTS.md` and `handoff.md` exist. If they do, read them first.
- If `AGENTS.md` is missing, ask the user whether they want one created.
- After each round, update the project-root `handoff.md` with completed work, remaining problems, and next steps.
- If this round produces a reusable method or pattern, show the user a short draft first and wait for confirmation before writing it into `~/.ai-config/skill.md`.

### `wrap up`

When the user says `wrap up`, do this in order:

1. Update the project-root `handoff.md` with completed work, remaining problems, and next steps.
2. If there is a reusable method worth collecting, include a short draft and ask whether it should be written into `~/.ai-config/skill.md`.
3. Output one sentence summarizing what was finished, then stop.

Do not be verbose and do not generate a long report.

### Code Modification Preferences

- Use the smallest possible edit. Do not refactor nearby code, add comments, or add type hints unless the user asked for them.
- Do not add features, abstractions, or defensive code the user did not request.
- Read the current file before editing it. Never patch from stale memory.
- Do one task per round. If the user gives multiple tasks, finish and verify one before starting the next.

### Verification Requirements

- Do not say "should be fine". Every change needs runnable proof.
- Proof must be executed through a temporary script, and the full output must be shown back to the user.

### Reporting Style

- Lead with the result: whether it was changed successfully and whether proof passed.
- Do not output long markdown reports unless the user explicitly asks for one.

## Workspace Layout

- Workspace root and main repo: the directory containing this `AGENTS.md`.
- This folder is a git repository.
- Deploy scripts: `scripts/`
- Server cheat sheet: `server deploy.md`

## Production Server

- Public production server: `49.234.185.86`
- SSH: `ubuntu@49.234.185.86`
- Password: `***REMOVED-ROTATED-SSH-PASSWORD***`
- Remote repo path: `/home/ubuntu/Xingrun-Website`
- PM2 service name: `xingrun`
- `47.108.29.108` is an old secondary server reference only; do not use it as the default production target.

## Project Structure

`Xingrun-Website/`

```text
Xingrun-Website/
├── app.py                         # Flask API server entry
├── lesson_manager.py              # SQLite data layer and account/org/session logic
├── ai_processor.py                # AI processing and extraction
├── config_runtime.py              # Runtime config loader
├── requirements.txt               # Python dependencies
├── frontend/                      # Vite + React frontend
│   ├── package.json
│   └── src/
│       ├── App.tsx
│       ├── main.tsx
│       └── index.css
├── tests/                         # Backend and integration tests
├── scripts/
│   ├── run_backend.sh             # Backend startup helper
│   ├── deploy_backend.sh          # Backend deploy helper
│   └── manage_remote_openclaw.sh
├── docs/                          # Specs, plans, and runbooks
├── review_plan_templates/         # Review plan template workspace
├── data/                          # Runtime SQLite db and generated files
└── start.command / start.bat      # Local backend startup scripts
```

## Fast Context

- Frontend and backend live in the same repo under `Xingrun-Website/`.
- Backend listens on `127.0.0.1:5001` by default.
- Root route `/` redirects to frontend URL from `XR_BROWSER_URL` (default `http://127.0.0.1:3000`).
- Account approval, owner login, and registration flow are implemented in:
  - `app.py`
  - `lesson_manager.py`
  - `frontend/src/App.tsx`
  - `tests/test_account_flow.py`

## Working Rules

- Before editing project code, `cd` to the project root, which is the directory containing this `AGENTS.md`.
- Keep commits focused. Do not mix local runtime files like `config.json` or `data/*.db` into normal code commits unless explicitly intended.
- After meaningful changes, verify first, then commit.
- The user has very low tolerance for a messy workspace. Keep branches, worktrees, staged files, runtime noise, and uncommitted state as clean and short-lived as possible.

## Branch And Contribution Strategy

- `master` is the main release branch and must only be updated by a manual merge from `develop`.
- `develop` is the default integration branch.
- All daily development, fixes, and small changes must branch from `develop`; do not commit directly on `develop` or `master` unless the user explicitly overrides this rule.
- Before creating a branch, fetch remote metadata and confirm local `develop` is synchronized with `origin/develop`. If it is not synchronized, synchronize it first.
- Complete and verify work on the short-lived feature branch, then merge the branch back into `develop`.
- Large changes must branch from `develop` in a dedicated worktree. After the branch is merged back into `develop`, delete the branch and close the worktree promptly.
- Only merge `develop` back into `master` manually when the user is ready. Do not auto-merge or directly commit feature work onto `master`.
- If the goal is to preserve real commit counts such as `+4` on the feature branch, still `+4` after merging into `develop`, and still `+4` after `develop` is merged into `master`, do not squash those commits. Use a merge flow that keeps the original feature commits in history.

## Multi-AI Branch Workflow

- One AI conversation can use one branch, but that branch should stay short-lived and focused on one scoped task.
- If a branch is still in progress, treat it as a draft branch and do not merge it directly just because the conversation is finished.
- Do not let multiple AI branches edit the same file set or the same business chain in parallel unless one of them is explicitly rebased or refreshed first.
- For all scoped changes, including small changes, create a focused branch from `develop`, finish the work there, then merge it back into `develop`.
- For large changes, create a focused branch from `develop` and do the work in a separate worktree so the main workspace stays clean.
- Before merging any non-trivial branch back to `develop`, first check branch freshness with `git rev-list --left-right --count develop...<branch>`.
- If the branch has fallen behind `develop` enough that a direct merge would replay old behavior or revert newer work, do not merge it directly; rebase it onto latest `develop`, or cherry-pick / manually transplant the intended commits into a fresh branch.
- After a branch is successfully integrated into `develop`, delete the merged branch and remove its worktree promptly unless the user explicitly wants to keep it.
- Prefer a merge strategy that preserves the original feature commits when commit-count visibility matters. Avoid squash merges in that case.
