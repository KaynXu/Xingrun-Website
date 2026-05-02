#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

run_step() {
  local label="$1"
  shift

  printf '\n==> %s\n' "$label"
  (cd "$ROOT_DIR" && "$@")
}

run_step "npm --prefix frontend test" npm --prefix frontend test
run_step "npm --prefix frontend run build" npm --prefix frontend run build
run_step "git diff --check" git diff --check

printf '\nFrontend stability proof passed.\n'
