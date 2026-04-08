# Workspace Rules

- If the current workspace or project folder contains an `AGENTS.md`, read it before making changes.
- Every meaningful code or content change should end with a git commit after verification.
- Do not leave deployable project changes in a long-lived uncommitted state unless the user explicitly asks for WIP only.
- When a working folder is not itself a git repository, call that out clearly before assuming its files can be versioned.

## Workspace Layout

- Workspace root and main repo: `/Users/ark.mini/Desktop/Xingrun-Website`
- This folder is a git repository.
- Deploy scripts: `/Users/ark.mini/Desktop/Xingrun-Website/scripts/`
- Server cheat sheet: `/Users/ark.mini/Desktop/Xingrun-Website/server deploy.md`

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

- Before editing project code, `cd /Users/ark.mini/Desktop/Xingrun-Website`.
- Keep commits focused. Do not mix local runtime files like `config.json` or `data/*.db` into normal code commits unless explicitly intended.
- After meaningful changes, verify first, then commit.

## Branch And Contribution Strategy

- Keep `master` as the default branch for release and contribution visibility.
- Use `develop` as the integration branch.
- For very small tasks (docs, tiny low-risk changes), committing directly on `develop` is allowed.
- To avoid delayed GitHub contribution visibility, merge `develop` back into `master` frequently (for example daily or after a small batch of completed tasks).
- For medium/large or risky changes, branch from `develop` (`feature/*`), then merge back to `develop`, and finally merge `develop` to `master`.

## Multi-AI Branch Workflow

- One AI conversation can use one branch, but that branch should stay short-lived and focused on one scoped task.
- If a branch is still in progress, treat it as a draft branch and do not merge it directly just because the conversation is finished.
- Do not let multiple AI branches edit the same file set or the same business chain in parallel unless one of them is explicitly rebased or refreshed first.
- Before merging any non-trivial branch back to `develop`, first check branch freshness with `git rev-list --left-right --count develop...<branch>`.
- If the branch has fallen behind `develop` enough that a direct merge would replay old behavior or revert newer work, do not merge it directly; rebase it onto latest `develop`, or cherry-pick / manually transplant the intended commits into a fresh branch.
- After a branch is successfully integrated into `develop`, delete the merged branch and remove its worktree promptly unless the user explicitly wants to keep it.
