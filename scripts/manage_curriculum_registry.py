#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import curriculum_registry
import lesson_manager


PINNED_DOWNLOAD_URL = (
    "https://huggingface.co/datasets/lhpku20010120/K12-KGraph/resolve/"
    f"{curriculum_registry.SOURCE_DATASET_REVISION}/"
    f"{curriculum_registry.SOURCE_FILE_PATH}?download=true"
)


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)


def _download() -> bytes:
    request = urllib.request.Request(PINNED_DOWNLOAD_URL, headers={"User-Agent": "Xingrun-Curriculum-Importer/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = response.read()
    actual = hashlib.sha256(payload).hexdigest()
    if actual != curriculum_registry.SOURCE_SHA256:
        raise curriculum_registry.CurriculumValidationError(
            f"pinned upstream SHA-256 mismatch: expected {curriculum_registry.SOURCE_SHA256}, got {actual}"
        )
    return payload


def _source_bytes(path: str) -> bytes:
    return Path(path).read_bytes() if path else _download()


def _connect_read_only(db_path: str) -> sqlite3.Connection:
    path = Path(db_path).resolve()
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    return conn


def _connect_write(db_path: str) -> sqlite3.Connection:
    lesson_manager.DB_PATH = Path(db_path).resolve()
    lesson_manager.init_db()
    return lesson_manager.get_conn()


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def _database_checks(conn: sqlite3.Connection) -> dict:
    integrity = str(conn.execute("PRAGMA integrity_check").fetchone()[0])
    foreign_keys = [tuple(row) for row in conn.execute("PRAGMA foreign_key_check").fetchall()]
    if integrity != "ok" or foreign_keys:
        raise curriculum_registry.CurriculumValidationError(
            "database integrity or foreign-key check failed"
        )
    return {"integrity_check": integrity, "foreign_key_check_count": len(foreign_keys)}


def _backup_database(db_path: str) -> Path:
    source_path = Path(db_path).resolve()
    if not source_path.exists():
        raise FileNotFoundError(f"database not found: {source_path}")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup_path = source_path.with_name(f"{source_path.name}.curriculum-backup-{stamp}")
    with sqlite3.connect(source_path) as source:
        source.row_factory = sqlite3.Row
        _database_checks(source)
        with sqlite3.connect(backup_path) as backup:
            source.backup(backup)
            _database_checks(backup)
    return backup_path


def _require_super_owner(conn: sqlite3.Connection, actor_user_id: int) -> dict:
    actor = conn.execute(
        "SELECT id, role, status FROM users WHERE id=?", (int(actor_user_id),)
    ).fetchone()
    if not actor or str(actor["role"]) != "super_owner" or str(actor["status"]) != "active":
        raise PermissionError("actor must be an active super owner")
    return dict(actor)


def _installed_diff(conn: sqlite3.Connection, bundle: dict) -> dict:
    bundle_stats = curriculum_registry.validate_bundle(bundle)
    versions = curriculum_registry.list_curriculum_versions(conn)
    installed = next(
        (item for item in versions if item["version_key"] == curriculum_registry.CURRICULUM_VERSION_KEY),
        None,
    )
    if not installed:
        return {"installed": False, "action": "import", "bundle": bundle_stats}
    installed_stats = curriculum_registry.verify_installed_curriculum(conn, int(installed["id"]))
    return {
        "installed": True,
        "action": "none" if installed["content_hash"] == bundle_stats["content_hash"] else "blocked_content_conflict",
        "bundle": bundle_stats,
        "installed_version": installed,
        "installed_counts": {
            "nodes": installed_stats["node_counts"],
            "edges": installed_stats["edge_counts"],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage the pinned Xingrun curriculum registry")
    parser.add_argument("--db", default="", help="Explicit SQLite database path for database commands")
    parser.add_argument("--actor-user-id", type=int, default=0)
    parser.add_argument("--confirm", default="", help="For writes, must equal the pinned version key")
    parser.add_argument("--bundle", default=str(curriculum_registry.DEFAULT_BUNDLE_PATH))
    parser.add_argument("--receipt", default=str(curriculum_registry.DEFAULT_RECEIPT_PATH))
    subparsers = parser.add_subparsers(dest="command", required=True)

    check = subparsers.add_parser("check-upstream", help="Download or read and validate the exact pinned source")
    check.add_argument("--source", default="")

    download = subparsers.add_parser("download", help="Download the exact pinned source to an explicit path")
    download.add_argument("--output", required=True)

    build = subparsers.add_parser("build-bundle", help="Build the permitted deterministic bundle from pinned math.json")
    build.add_argument("--source", required=True)
    build.add_argument("--output", default=str(curriculum_registry.DEFAULT_BUNDLE_PATH))
    build.add_argument("--receipt-output", default=str(curriculum_registry.DEFAULT_RECEIPT_PATH))

    subparsers.add_parser("dry-run", help="Validate bundle and show the prospective operation")
    subparsers.add_parser("diff", help="Compare the deterministic bundle with installed SQLite data")
    subparsers.add_parser("apply", help="Atomically import the deterministic bundle as draft")

    review = subparsers.add_parser("review", help="Mark a draft version reviewed")
    review.add_argument("version_id", type=int)
    activate = subparsers.add_parser("activate", help="Activate a reviewed version")
    activate.add_argument("version_id", type=int)
    rollback = subparsers.add_parser("rollback", help="Rollback the active package to a reviewed version")
    rollback.add_argument("version_id", type=int)
    verify = subparsers.add_parser("verify", help="Verify installed counts and relationships")
    verify.add_argument("version_id", type=int, nargs="?")

    args = parser.parse_args()
    if args.command == "check-upstream":
        payload = _source_bytes(args.source)
        bundle = curriculum_registry.build_bundle_from_upstream(payload)
        print(_json({
            "ok": True,
            "source_revision": curriculum_registry.SOURCE_DATASET_REVISION,
            "source_sha256": hashlib.sha256(payload).hexdigest(),
            **curriculum_registry.validate_bundle(bundle),
        }))
        return 0
    if args.command == "download":
        output = Path(args.output).resolve()
        payload = _download()
        _atomic_write(output, payload)
        print(_json({"ok": True, "path": str(output), "size": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}))
        return 0
    if args.command == "build-bundle":
        payload = Path(args.source).read_bytes()
        bundle = curriculum_registry.build_bundle_from_upstream(payload)
        output = Path(args.output).resolve()
        receipt_output = Path(args.receipt_output).resolve()
        raw = (_json(bundle) + "\n").encode("utf-8")
        _atomic_write(output, raw)
        stats = curriculum_registry.validate_bundle(bundle)
        receipt = {
            "schema_version": "xingrun.curriculum-source-receipt.v1",
            "bundle_path": output.name,
            "bundle_sha256": hashlib.sha256(raw).hexdigest(),
            "content_hash": stats["content_hash"],
            "source_sha256": curriculum_registry.SOURCE_SHA256,
            "source_dataset_url": curriculum_registry.SOURCE_DATASET_URL,
            "source_dataset_revision": curriculum_registry.SOURCE_DATASET_REVISION,
            "source_file_path": curriculum_registry.SOURCE_FILE_PATH,
            "source_github_url": curriculum_registry.SOURCE_GITHUB_URL,
            "source_github_commit": curriculum_registry.SOURCE_GITHUB_COMMIT,
            "data_license": curriculum_registry.SOURCE_DATA_LICENSE,
            "code_license": curriculum_registry.SOURCE_CODE_LICENSE,
            "source_counts": bundle["source_counts"],
            "import_counts": bundle["import_counts"],
            "importer_version": curriculum_registry.CURRICULUM_IMPORTER_VERSION,
            "contains_exercises": False,
        }
        _atomic_write(receipt_output, (_json(receipt) + "\n").encode("utf-8"))
        print(_json({"ok": True, "bundle": str(output), "receipt": str(receipt_output), **receipt, **stats}))
        return 0

    if not args.db:
        parser.error("--db is required for database commands")
    bundle = curriculum_registry.load_bundle(args.bundle, args.receipt)
    if args.command in {"dry-run", "diff", "verify"}:
        with _connect_read_only(args.db) as conn:
            _database_checks(conn)
            if args.command in {"dry-run", "diff"}:
                print(_json(_installed_diff(conn, bundle)))
                return 0
            version_id = args.version_id
            if version_id is None:
                active = curriculum_registry.get_active_curriculum_version(conn)
                if not active:
                    raise LookupError("no active math curriculum version")
                version_id = int(active["id"])
            print(_json(curriculum_registry.verify_installed_curriculum(conn, version_id)))
            return 0

    if args.confirm != curriculum_registry.CURRICULUM_VERSION_KEY:
        parser.error(f"--confirm must equal {curriculum_registry.CURRICULUM_VERSION_KEY}")
    if not args.actor_user_id:
        parser.error("--actor-user-id is required for database writes")
    with _connect_read_only(args.db) as authorization_conn:
        _require_super_owner(authorization_conn, args.actor_user_id)
    backup_path = _backup_database(args.db)
    with _connect_write(args.db) as conn:
        _require_super_owner(conn, args.actor_user_id)
        checks_before = _database_checks(conn)
        if args.command == "apply":
            result = curriculum_registry.import_curriculum_bundle(
                conn,
                bundle,
                actor_user_id=args.actor_user_id,
            )
            checks_after = _database_checks(conn)
            print(_json({**result, "backup_path": str(backup_path), "checks_before": checks_before, "checks_after": checks_after}))
            return 0
        if args.command == "review":
            result = curriculum_registry.review_curriculum_version(conn, args.version_id, actor_user_id=args.actor_user_id)
        elif args.command == "activate":
            result = curriculum_registry.activate_curriculum_version(conn, args.version_id, actor_user_id=args.actor_user_id)
        elif args.command == "rollback":
            result = curriculum_registry.rollback_curriculum_version(conn, args.version_id, actor_user_id=args.actor_user_id)
        else:
            parser.error("unsupported write command")
        checks_after = _database_checks(conn)
        print(_json({"result": result, "backup_path": str(backup_path), "checks_before": checks_before, "checks_after": checks_after}))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
