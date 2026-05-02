#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PRD_FILE="$ROOT_DIR/scripts/ralph/prd.json"
PROGRESS_FILE="$ROOT_DIR/scripts/ralph/progress.txt"
CODEX_MODEL="${CODEX_RALPH_MODEL:-gpt-5.4}"

MODE="run"
MAX_ITERATIONS="${CODEX_RALPH_MAX_ITERATIONS:-}"

usage() {
  cat <<'USAGE'
Usage:
  scripts/ralph/run_codex_ralph.sh [max_iterations]
  scripts/ralph/run_codex_ralph.sh --check
  scripts/ralph/run_codex_ralph.sh --print-prompt

Runs Codex CLI in a Ralph-style loop. Each iteration asks Codex to complete
exactly one passes=false story from scripts/ralph/prd.json. The loop stops when
all stories pass, Codex fails, no progress is detected, or max_iterations is hit.

Environment:
  CODEX_RALPH_MAX_ITERATIONS  Override default max iterations.
  CODEX_RALPH_MODEL           Optional Codex model name passed with --model.
                              Defaults to gpt-5.4 to avoid older CLI failures
                              when ~/.codex/config.toml points at gpt-5.5.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --check)
      MODE="check"
      shift
      ;;
    --print-prompt)
      MODE="print-prompt"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      if [[ "$1" =~ ^[0-9]+$ ]]; then
        MAX_ITERATIONS="$1"
        shift
      else
        echo "Unknown argument: $1" >&2
        usage >&2
        exit 2
      fi
      ;;
  esac
done

require_file() {
  local path="$1"
  if [[ ! -f "$path" ]]; then
    echo "Missing required file: $path" >&2
    exit 1
  fi
}

require_command() {
  local name="$1"
  if ! command -v "$name" >/dev/null 2>&1; then
    echo "Missing required command: $name" >&2
    exit 1
  fi
}

remaining_count() {
  jq '[.userStories[] | select(.passes == false)] | length' "$PRD_FILE"
}

next_story_field() {
  local field="$1"
  jq -r --arg field "$field" '
    [.userStories[] | select(.passes == false)] | sort_by(.priority) | .[0][$field] // ""
  ' "$PRD_FILE"
}

print_status() {
  local remaining
  remaining="$(remaining_count)"
  echo "PRD: $PRD_FILE"
  echo "Progress: $PROGRESS_FILE"
  echo "Codex model: $CODEX_MODEL"
  echo "Remaining stories: $remaining"
  if [[ "$remaining" == "0" ]]; then
    echo "Next story: <none>"
    echo "<promise>COMPLETE</promise>"
  else
    echo "Next story: $(next_story_field id)"
    echo "Next title: $(next_story_field title)"
  fi
}

build_prompt() {
  local story_id="$1"
  local story_title="$2"

  cat <<PROMPT
请按 Ralph 模式工作。

当前自动循环指定 story：
- id: ${story_id}
- title: ${story_title}

规则：
1. 先读 AGENTS.md 和 handoff.md。
2. 读取 scripts/ralph/prd.json 和 scripts/ralph/progress.txt。
3. 本轮只做一个任务：优先做上面指定的 story；如果它已经 passes=true，就选择 prd.json 里 passes=false 且 priority 数字最小的 story。
4. 不要自由发挥，不要一次做多个 story。
5. 修改任何项目文件前先读当前内容。
6. 完成后必须运行可执行 proof，proof 用临时脚本执行，并在最终回复贴完整输出。
7. proof 通过后更新 scripts/ralph/prd.json，把本 story 标为 passes=true。
8. 更新 scripts/ralph/progress.txt，记录本轮有效结论和下一条 story。
9. 有实质进展时更新 handoff.md，只写当前仍有效的信息。
10. 如果有实质代码或内容改动，验证通过后提交 git commit。
11. 如果 proof 失败，不要把 story 标为 passes=true，不要提交，报告失败并停止。
12. 如果 scripts/ralph/prd.json 不存在，先告诉我缺少文件，不要自己编造需求。

自动循环约束：
- 这一轮结束后不要继续做下一条 story。
- 不要等待我确认才开始当前 story；按上面的规则直接执行。
PROMPT
}

require_command jq
require_file "$PRD_FILE"
require_file "$PROGRESS_FILE"

if [[ "$MODE" == "check" ]]; then
  print_status
  exit 0
fi

current_remaining="$(remaining_count)"
if [[ "$current_remaining" == "0" ]]; then
  print_status
  exit 0
fi

if [[ "$MODE" == "print-prompt" ]]; then
  build_prompt "$(next_story_field id)" "$(next_story_field title)"
  exit 0
fi

require_command codex

if [[ -z "$MAX_ITERATIONS" ]]; then
  MAX_ITERATIONS="$current_remaining"
fi

if ! [[ "$MAX_ITERATIONS" =~ ^[0-9]+$ ]] || [[ "$MAX_ITERATIONS" -lt 1 ]]; then
  echo "max_iterations must be a positive integer." >&2
  exit 2
fi

echo "Starting Codex Ralph loop"
echo "Root: $ROOT_DIR"
echo "Max iterations: $MAX_ITERATIONS"
print_status

for iteration in $(seq 1 "$MAX_ITERATIONS"); do
  before_remaining="$(remaining_count)"
  if [[ "$before_remaining" == "0" ]]; then
    echo "All stories complete before iteration $iteration."
    echo "<promise>COMPLETE</promise>"
    exit 0
  fi

  story_id="$(next_story_field id)"
  story_title="$(next_story_field title)"
  echo
  echo "==============================================================="
  echo "  Codex Ralph Iteration $iteration of $MAX_ITERATIONS"
  echo "  Story: $story_id - $story_title"
  echo "==============================================================="

  codex_args=(exec --cd "$ROOT_DIR" --dangerously-bypass-approvals-and-sandbox --model "$CODEX_MODEL")

  build_prompt "$story_id" "$story_title" | codex "${codex_args[@]}" -

  after_remaining="$(remaining_count)"
  echo
  echo "Remaining stories after iteration $iteration: $after_remaining"

  if [[ "$after_remaining" == "0" ]]; then
    echo "All stories complete."
    echo "<promise>COMPLETE</promise>"
    exit 0
  fi

  if [[ "$after_remaining" -ge "$before_remaining" ]]; then
    echo "No completed story was detected after iteration $iteration; stopping to avoid an infinite loop." >&2
    echo "Check the Codex output, scripts/ralph/prd.json, and scripts/ralph/progress.txt." >&2
    exit 1
  fi
done

remaining="$(remaining_count)"
echo
echo "Reached max iterations ($MAX_ITERATIONS)."
echo "Remaining stories: $remaining"
if [[ "$remaining" == "0" ]]; then
  echo "<promise>COMPLETE</promise>"
  exit 0
fi
exit 1
