#!/bin/bash
set -euo pipefail

SERVER_HOST="${SERVER_HOST:-49.234.185.86}"
SERVER_USER="${SERVER_USER:-ubuntu}"
SERVER_PORT="${SERVER_PORT:-22}"
OPENCLAW_PORT="${OPENCLAW_PORT:-18789}"
OPENCLAW_PROCESS_NAME="${OPENCLAW_PROCESS_NAME:-openclaw}"
OPENCLAW_CWD="${OPENCLAW_CWD:-/home/ubuntu}"
TARGET_VERSION="${TARGET_VERSION:-latest}"

usage() {
  cat <<'EOF'
Usage:
  ./scripts/manage_remote_openclaw.sh status
  ./scripts/manage_remote_openclaw.sh backup
  ./scripts/manage_remote_openclaw.sh update [version]

Environment:
  SSH_PASSWORD     SSH password for the remote server.
  SUDO_PASSWORD    Optional sudo password. Defaults to SSH_PASSWORD.
  SERVER_HOST      Defaults to 49.234.185.86
  SERVER_USER      Defaults to ubuntu
  SERVER_PORT      Defaults to 22
  OPENCLAW_CWD     Defaults to /home/ubuntu
  TARGET_VERSION   Defaults to latest
EOF
}

require_local_tool() {
  local tool="$1"
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "Missing required local tool: $tool" >&2
    exit 1
  fi
}

ensure_passwords() {
  if [ -z "${SSH_PASSWORD:-}" ]; then
    read -r -s -p "SSH password for ${SERVER_USER}@${SERVER_HOST}: " SSH_PASSWORD
    echo
  fi

  if [ -z "${SUDO_PASSWORD:-}" ]; then
    SUDO_PASSWORD="$SSH_PASSWORD"
  fi
}

remote() {
  sshpass -p "$SSH_PASSWORD" ssh \
    -o StrictHostKeyChecking=accept-new \
    -p "$SERVER_PORT" \
    "${SERVER_USER}@${SERVER_HOST}" \
    "$@"
}

show_status() {
  remote "
set -euo pipefail
echo '==> openclaw version'
openclaw --version
echo
echo '==> gateway help probe'
openclaw gateway --help | sed -n '1,20p'
echo
echo '==> pm2 show ${OPENCLAW_PROCESS_NAME}'
pm2 show ${OPENCLAW_PROCESS_NAME} | sed -n '1,80p'
echo
echo '==> listening ports'
ss -ltnp | grep ${OPENCLAW_PORT} || true
echo
echo '==> config keys'
jq -r '.channels.wecom | keys' ~/.openclaw/openclaw.json
"
}

backup_config() {
  remote "
set -euo pipefail
ts=\$(date +%Y%m%d-%H%M%S)
backup_path=/home/ubuntu/openclaw-backup-\$ts.tgz
tar -czf \"\$backup_path\" -C /home/ubuntu .openclaw
echo \"\$backup_path\"
"
}

recreate_pm2_process() {
  remote "
set -euo pipefail
pm2 delete ${OPENCLAW_PROCESS_NAME} >/dev/null 2>&1 || true
cd ${OPENCLAW_CWD}
pm2 start bash --name ${OPENCLAW_PROCESS_NAME} -- -lc 'cd ${OPENCLAW_CWD} && openclaw gateway run --port ${OPENCLAW_PORT}'
sleep 2
pm2 show ${OPENCLAW_PROCESS_NAME} | sed -n '1,40p'
"
}

update_openclaw() {
  local version="${1:-$TARGET_VERSION}"
  local remote_version

  if [ "$version" = "latest" ]; then
    remote_version="$(remote "npm view openclaw version")"
    version="$(printf '%s' "$remote_version" | tail -n 1 | tr -d '\r')"
  fi

  echo "Updating remote OpenClaw to ${version}"
  local backup_path
  backup_path="$(backup_config)"
  echo "Backup created at ${backup_path}"

  remote "
set -euo pipefail
printf '%s\n' '${SUDO_PASSWORD}' | sudo -S npm install -g openclaw@${version}
openclaw --version
"
  recreate_pm2_process
  remote "
set -euo pipefail
pm2 save
ss -ltnp | grep ${OPENCLAW_PORT} || true
"
}

main() {
  require_local_tool sshpass
  require_local_tool jq
  ensure_passwords

  case "${1:-}" in
    status)
      show_status
      ;;
    backup)
      backup_config
      ;;
    update)
      update_openclaw "${2:-}"
      ;;
    --help|-h|"")
      usage
      ;;
    *)
      echo "Unknown command: $1" >&2
      usage
      exit 1
      ;;
  esac
}

main "$@"
