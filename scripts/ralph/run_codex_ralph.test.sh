#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RUNNER="$ROOT_DIR/scripts/ralph/run_codex_ralph.sh"
PRD_FILE="$ROOT_DIR/scripts/ralph/prd.json"

test -x "$RUNNER"
bash -n "$RUNNER"

expected_remaining="$(jq '[.userStories[] | select(.passes == false)] | length' "$PRD_FILE")"
expected_next="$(jq -r '[.userStories[] | select(.passes == false)] | sort_by(.priority) | .[0].id // "<none>"' "$PRD_FILE")"

check_output="$("$RUNNER" --check)"
printf '%s\n' "$check_output"

grep -q "Remaining stories: $expected_remaining" <<< "$check_output"
grep -q "Next story: $expected_next" <<< "$check_output"
grep -q "Codex model: ${CODEX_RALPH_MODEL:-gpt-5.5}" <<< "$check_output"

if [[ "$expected_remaining" != "0" ]]; then
  prompt_output="$("$RUNNER" --print-prompt)"
  grep -q "$expected_next" <<< "$prompt_output"
  grep -q "本轮只做一个任务" <<< "$prompt_output"
  grep -q "不要自由发挥" <<< "$prompt_output"
fi

echo "run_codex_ralph self-test passed."
