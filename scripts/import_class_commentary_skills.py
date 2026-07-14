#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import lesson_manager


REQUIRED_FIELDS = (
    "organization_id",
    "skill_id",
    "owner_teacher_user_id",
    "source_path",
)


class ManifestValidationError(ValueError):
    pass


def _compact_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _load_manifest(manifest_path: Path) -> list[dict]:
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ManifestValidationError(f"cannot read manifest: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ManifestValidationError(
            f"invalid JSON at line {exc.lineno} column {exc.colno}"
        ) from exc

    if isinstance(payload, list):
        entries = payload
    elif isinstance(payload, dict) and set(payload) == {"skills"}:
        entries = payload["skills"]
        if not isinstance(entries, list):
            raise ManifestValidationError("manifest skills must be an array")
    else:
        raise ManifestValidationError(
            'manifest must be a JSON array or an object containing only "skills"'
        )

    validated: list[dict] = []
    for index, entry in enumerate(entries):
        label = f"skills[{index}]"
        if not isinstance(entry, dict):
            raise ManifestValidationError(f"{label} must be an object")
        missing = [field for field in REQUIRED_FIELDS if field not in entry]
        if missing:
            raise ManifestValidationError(f"{label} missing fields: {','.join(missing)}")

        organization_id = entry["organization_id"]
        owner_teacher_user_id = entry["owner_teacher_user_id"]
        if (
            isinstance(organization_id, bool)
            or not isinstance(organization_id, int)
            or organization_id <= 0
        ):
            raise ManifestValidationError(f"{label}.organization_id must be a positive integer")
        if (
            isinstance(owner_teacher_user_id, bool)
            or not isinstance(owner_teacher_user_id, int)
            or owner_teacher_user_id <= 0
        ):
            raise ManifestValidationError(
                f"{label}.owner_teacher_user_id must be a positive integer"
            )

        skill_id = entry["skill_id"]
        source_path = entry["source_path"]
        if not isinstance(skill_id, str) or not skill_id.strip():
            raise ManifestValidationError(f"{label}.skill_id must be a non-empty string")
        if not isinstance(source_path, str) or not source_path.strip():
            raise ManifestValidationError(f"{label}.source_path must be a non-empty string")

        source_path = source_path.strip()
        parsed_source_path = Path(source_path).expanduser()
        if parsed_source_path.is_absolute():
            resolved_source_path = source_path if Path(source_path).is_absolute() else str(parsed_source_path)
        else:
            resolved_source_path = str((manifest_path.parent / parsed_source_path).resolve())

        validated.append(
            {
                "organization_id": organization_id,
                "skill_id": skill_id.strip(),
                "owner_teacher_user_id": owner_teacher_user_id,
                "source_path": resolved_source_path,
            }
        )
    return validated


def _result_item(entry: dict, imported: dict) -> dict:
    return {
        "organization_id": entry["organization_id"],
        "skill_id": entry["skill_id"],
        "owner_teacher_user_id": entry["owner_teacher_user_id"],
        "registry_id": imported["registry_id"],
        "active_version_id": imported["active_version_id"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Import class commentary skills from an explicit owner manifest."
    )
    parser.add_argument("manifest", type=Path, help="Path to the JSON manifest")
    args = parser.parse_args(argv)
    manifest_path = args.manifest.expanduser().absolute()

    try:
        entries = _load_manifest(manifest_path)
    except ManifestValidationError as exc:
        print(_compact_json({"ok": False, "error": "invalid_manifest", "message": str(exc)}), file=sys.stderr)
        return 2

    try:
        with contextlib.redirect_stdout(io.StringIO()):
            lesson_manager.init_db()
        imported = [
            _result_item(entry, lesson_manager.import_class_commentary_skill_manifest(**entry))
            for entry in entries
        ]
    except lesson_manager.ClassCommentarySkillImportConflict as exc:
        print(_compact_json({"ok": False, "error": "conflict", "message": str(exc)}), file=sys.stderr)
        return 1
    except (OSError, ValueError) as exc:
        print(_compact_json({"ok": False, "error": "import_failed", "message": str(exc)}), file=sys.stderr)
        return 1

    print(_compact_json({"ok": True, "count": len(imported), "skills": imported}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
