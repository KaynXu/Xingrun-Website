#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

SERVER_HOST="${SERVER_HOST:-49.234.185.86}"
SERVER_USER="${SERVER_USER:-ubuntu}"
SERVER_PORT="${SERVER_PORT:-22}"
REMOTE_REPO_PATH="${REMOTE_REPO_PATH:-/home/ubuntu/Xingrun-Website}"
REMOTE_DB_PATH="${REMOTE_DB_PATH:-}"
LOCAL_DB_PATH="${LOCAL_DB_PATH:-$ROOT_DIR/data/xingrun.db}"
LOCAL_BACKUP_DIR="${LOCAL_BACKUP_DIR:-$ROOT_DIR/data/backups}"
KEEP_REMOTE_SNAPSHOT="${KEEP_REMOTE_SNAPSHOT:-0}"
temp_dir=""
remote_snapshot=""

usage() {
  cat <<'EOF'
Usage:
  ./scripts/sync_remote_db.sh

Environment:
  SSH_PASSWORD        SSH password for the remote server.
  SERVER_HOST         Defaults to 49.234.185.86
  SERVER_USER         Defaults to ubuntu
  SERVER_PORT         Defaults to 22
  REMOTE_REPO_PATH    Defaults to /home/ubuntu/Xingrun-Website
  REMOTE_DB_PATH      Optional explicit remote SQLite path override.
  LOCAL_DB_PATH       Defaults to ./data/xingrun.db
  LOCAL_BACKUP_DIR    Defaults to ./data/backups
  KEEP_REMOTE_SNAPSHOT
                      Set to 1 to keep the remote temp snapshot file.

Examples:
  SSH_PASSWORD='***REMOVED-ROTATED-SSH-PASSWORD***' ./scripts/sync_remote_db.sh
  SSH_PASSWORD='***REMOVED-ROTATED-SSH-PASSWORD***' LOCAL_DB_PATH=/tmp/xingrun.db ./scripts/sync_remote_db.sh
EOF
}

require_local_tool() {
  local tool="$1"
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "Missing required local tool: $tool" >&2
    exit 1
  fi
}

ensure_password() {
  if [ -z "${SSH_PASSWORD:-}" ]; then
    read -r -s -p "SSH password for ${SERVER_USER}@${SERVER_HOST}: " SSH_PASSWORD
    echo
  fi
}

remote() {
  SSHPASS="$SSH_PASSWORD" sshpass -e ssh \
    -o PubkeyAuthentication=no \
    -o PreferredAuthentications=password,keyboard-interactive \
    -o StrictHostKeyChecking=accept-new \
    -p "$SERVER_PORT" \
    "${SERVER_USER}@${SERVER_HOST}" \
    "$@"
}

copy_from_remote() {
  local remote_path="$1"
  local local_path="$2"
  SSHPASS="$SSH_PASSWORD" sshpass -e scp \
    -o PubkeyAuthentication=no \
    -o PreferredAuthentications=password,keyboard-interactive \
    -o StrictHostKeyChecking=accept-new \
    -P "$SERVER_PORT" \
    "${SERVER_USER}@${SERVER_HOST}:${remote_path}" \
    "$local_path"
}

extract_value() {
  local key="$1"
  local input="$2"
  printf '%s\n' "$input" | sed -n "s/^${key}=//p" | tail -n 1
}

sha256_of_file() {
  local target="$1"
  python3 - "$target" <<'PY'
import hashlib
import sys
from pathlib import Path

path = Path(sys.argv[1])
h = hashlib.sha256()
with path.open("rb") as fh:
    for chunk in iter(lambda: fh.read(1024 * 1024), b""):
        h.update(chunk)
print(h.hexdigest())
PY
}

sqlite_integrity() {
  local target="$1"
  python3 - "$target" <<'PY'
import sqlite3
import sys

conn = sqlite3.connect(sys.argv[1])
try:
    value = conn.execute("PRAGMA integrity_check").fetchone()[0]
finally:
    conn.close()
print(value)
PY
}

cleanup() {
  if [ -n "${temp_dir:-}" ]; then
    rm -rf "$temp_dir"
  fi
  if [ "$KEEP_REMOTE_SNAPSHOT" != "1" ] && [ -n "${remote_snapshot:-}" ]; then
    remote "rm -f '$remote_snapshot'" >/dev/null 2>&1 || true
  fi
}

main() {
  case "${1:-}" in
    --help|-h)
      usage
      exit 0
      ;;
    "")
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac

  require_local_tool sshpass
  require_local_tool ssh
  require_local_tool scp
  require_local_tool python3
  ensure_password

  local timestamp
  timestamp="$(date +%Y%m%d-%H%M%S)"
  local local_db_dir
  local_db_dir="$(dirname "$LOCAL_DB_PATH")"
  mkdir -p "$local_db_dir" "$LOCAL_BACKUP_DIR"

  temp_dir="$(mktemp -d "${TMPDIR:-/tmp}/xingrun-db-sync.XXXXXX")"
  trap cleanup EXIT

  echo "==> Resolving remote database path"
  local remote_info
  remote_info="$(remote "REMOTE_REPO_PATH='$REMOTE_REPO_PATH' REMOTE_DB_PATH_OVERRIDE='$REMOTE_DB_PATH' python3 - <<'PY'
import json
import os
from pathlib import Path

repo = Path(os.environ['REMOTE_REPO_PATH'])
override = os.environ.get('REMOTE_DB_PATH_OVERRIDE', '').strip()
if override:
    db = Path(override)
else:
    db = repo / 'data/xingrun.db'
    env_path = repo / '.env.runtime'
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith('XR_DB_PATH='):
                value = line.split('=', 1)[1].strip()
                if value:
                    db = Path(value)
                break
    config_path = repo / 'config.json'
    if config_path.exists():
        try:
            value = json.loads(config_path.read_text()).get('db_path')
            if value:
                db = Path(value)
        except Exception:
            pass

print(f'RESOLVED_DB={db}')
print(f'EXISTS={db.exists()}')
if db.exists():
    print(f'SIZE={db.stat().st_size}')
PY")"

  local resolved_remote_db
  resolved_remote_db="$(extract_value "RESOLVED_DB" "$remote_info")"
  local remote_exists
  remote_exists="$(extract_value "EXISTS" "$remote_info")"
  if [ -z "$resolved_remote_db" ] || [ "$remote_exists" != "True" ]; then
    echo "$remote_info"
    echo "Remote database not found" >&2
    exit 1
  fi
  echo "$remote_info"

  remote_snapshot="/tmp/xingrun.db.sync-${timestamp}.sqlite"

  echo "==> Creating remote SQLite snapshot"
  local snapshot_info
  snapshot_info="$(remote "REMOTE_DB='$resolved_remote_db' REMOTE_SNAPSHOT='$remote_snapshot' python3 - <<'PY'
import hashlib
import os
import sqlite3
from pathlib import Path

source_path = Path(os.environ['REMOTE_DB'])
snapshot_path = Path(os.environ['REMOTE_SNAPSHOT'])
if snapshot_path.exists():
    snapshot_path.unlink()
source = sqlite3.connect(source_path)
backup = sqlite3.connect(snapshot_path)
with backup:
    source.backup(backup)
backup.close()
source.close()
h = hashlib.sha256()
with snapshot_path.open('rb') as fh:
    for chunk in iter(lambda: fh.read(1024 * 1024), b''):
        h.update(chunk)
print(f'REMOTE_SNAPSHOT={snapshot_path}')
print(f'REMOTE_SHA256={h.hexdigest()}')
print(f'REMOTE_SIZE={snapshot_path.stat().st_size}')
PY")"
  echo "$snapshot_info"

  local remote_sha
  remote_sha="$(extract_value "REMOTE_SHA256" "$snapshot_info")"
  if [ -z "$remote_sha" ]; then
    echo "Failed to read remote snapshot checksum" >&2
    exit 1
  fi

  local downloaded_snapshot
  downloaded_snapshot="$temp_dir/$(basename "$remote_snapshot")"

  echo "==> Downloading remote snapshot"
  copy_from_remote "$remote_snapshot" "$downloaded_snapshot"

  local downloaded_sha
  downloaded_sha="$(sha256_of_file "$downloaded_snapshot")"
  echo "DOWNLOADED_SHA256=$downloaded_sha"
  if [ "$downloaded_sha" != "$remote_sha" ]; then
    echo "Downloaded snapshot checksum does not match remote snapshot" >&2
    exit 1
  fi

  local downloaded_integrity
  downloaded_integrity="$(sqlite_integrity "$downloaded_snapshot")"
  echo "DOWNLOADED_INTEGRITY=$downloaded_integrity"
  if [ "$downloaded_integrity" != "ok" ]; then
    echo "Downloaded snapshot failed SQLite integrity check" >&2
    exit 1
  fi

  local local_backup="none"
  if [ -f "$LOCAL_DB_PATH" ]; then
    local_backup="$LOCAL_BACKUP_DIR/xingrun.db.local-before-remote-sync-${timestamp}.sqlite"
    cp "$LOCAL_DB_PATH" "$local_backup"
  fi
  echo "LOCAL_BACKUP=$local_backup"

  cp "$downloaded_snapshot" "$LOCAL_DB_PATH"

  local local_sha
  local_sha="$(sha256_of_file "$LOCAL_DB_PATH")"
  local local_integrity
  local_integrity="$(sqlite_integrity "$LOCAL_DB_PATH")"

  echo "LOCAL_DB=$LOCAL_DB_PATH"
  echo "LOCAL_SHA256=$local_sha"
  echo "LOCAL_INTEGRITY=$local_integrity"

  if [ "$local_sha" != "$remote_sha" ]; then
    echo "Installed local database checksum does not match remote snapshot" >&2
    exit 1
  fi
  if [ "$local_integrity" != "ok" ]; then
    echo "Installed local database failed SQLite integrity check" >&2
    exit 1
  fi

  echo "SYNC_STATUS=ok"
}

main "$@"
