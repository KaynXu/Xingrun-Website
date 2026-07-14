#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import lesson_manager


_REQUIRED_FIELDS = {
    "organization_id",
    "skill_id",
    "owner_teacher_user_id",
    "source_path",
}


class ManifestValidationError(ValueError):
    pass


def _compact_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _positive_int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field} must be a positive integer")
    return value


def load_skill_manifest(manifest_path: Path) -> list[dict]:
    resolved_manifest = manifest_path.expanduser().resolve()
    try:
        payload = json.loads(resolved_manifest.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ManifestValidationError(f"cannot read manifest: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ManifestValidationError(
            f"invalid JSON at line {exc.lineno} column {exc.colno}"
        ) from exc
    if isinstance(payload, dict):
        if set(payload) != {"skills"}:
            raise ManifestValidationError(
                'manifest object must contain only "skills"'
            )
        raw_items = payload["skills"]
    else:
        raw_items = payload
    if not isinstance(raw_items, list) or not raw_items:
        raise ManifestValidationError("manifest must contain a non-empty skills array")
    items = []
    seen = set()
    for index, raw_item in enumerate(raw_items):
        if not isinstance(raw_item, dict) or set(raw_item) != _REQUIRED_FIELDS:
            raise ManifestValidationError(
                f"skills[{index}] must contain exactly: "
                + ", ".join(sorted(_REQUIRED_FIELDS))
            )
        try:
            organization_id = _positive_int(
                raw_item["organization_id"], f"skills[{index}].organization_id"
            )
            owner_teacher_user_id = _positive_int(
                raw_item["owner_teacher_user_id"],
                f"skills[{index}].owner_teacher_user_id",
            )
        except ValueError as exc:
            raise ManifestValidationError(str(exc)) from exc
        skill_id_value = raw_item["skill_id"]
        if not isinstance(skill_id_value, str):
            raise ManifestValidationError(f"skills[{index}].skill_id is invalid")
        skill_id = skill_id_value.strip()
        if not skill_id or "/" in skill_id or "\\" in skill_id:
            raise ManifestValidationError(f"skills[{index}].skill_id is invalid")
        source_path_value = raw_item["source_path"]
        if not isinstance(source_path_value, str) or not source_path_value.strip():
            raise ManifestValidationError(f"skills[{index}].source_path is invalid")
        source_path = Path(source_path_value.strip()).expanduser()
        if source_path.is_absolute():
            normalized_source_path = source_path_value.strip()
        else:
            normalized_source_path = str((resolved_manifest.parent / source_path).resolve())
        key = (organization_id, skill_id)
        if key in seen:
            raise ManifestValidationError(
                f"duplicate organization_id and skill_id: {key}"
            )
        seen.add(key)
        items.append(
            {
                "organization_id": organization_id,
                "skill_id": skill_id,
                "owner_teacher_user_id": owner_teacher_user_id,
                "source_path": normalized_source_path,
            }
        )
    return items


def validate_skill_owners(items: list[dict]) -> None:
    with lesson_manager.get_conn() as connection:
        for item in items:
            source_path = Path(item["source_path"])
            skill_file = source_path / "SKILL.md" if source_path.is_dir() else source_path
            if not skill_file.is_file():
                raise ValueError(
                    f"source_path does not contain a skill file: {source_path}"
                )
            organization = connection.execute(
                "SELECT id FROM organizations WHERE id=?",
                (item["organization_id"],),
            ).fetchone()
            owner = connection.execute(
                "SELECT organization_id, status FROM users WHERE id=?",
                (item["owner_teacher_user_id"],),
            ).fetchone()
            if not organization:
                raise ValueError(
                    f"organization not found: {item['organization_id']}"
                )
            if (
                not owner
                or int(owner["organization_id"] or 0) != item["organization_id"]
                or str(owner["status"] or "") != "active"
            ):
                raise ValueError(
                    "skill owner must be active and belong to organization: "
                    f"{item['owner_teacher_user_id']}"
                )


def import_skill_manifest(manifest_path: Path, *, check_only: bool = False) -> dict:
    items = load_skill_manifest(manifest_path)
    validate_skill_owners(items)
    if check_only:
        return {"checked": len(items), "imported": 0, "skills": []}
    imported = [
        lesson_manager.import_class_commentary_skill_manifest(**item) for item in items
    ]
    return {
        "checked": len(items),
        "imported": len(imported),
        "skills": [
            {
                "registry_id": item["registry_id"],
                "organization_id": item["organization_id"],
                "skill_id": item["skill_id"],
                "owner_teacher_user_id": item["owner_teacher_user_id"],
                "active_version_id": item["active_version_id"],
            }
            for item in imported
        ],
    }


def _legacy_result_item(item: dict, imported: dict) -> dict:
    return {
        "organization_id": item["organization_id"],
        "skill_id": item["skill_id"],
        "owner_teacher_user_id": item["owner_teacher_user_id"],
        "registry_id": imported["registry_id"],
        "active_version_id": imported["active_version_id"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Import explicit class commentary skill ownership mappings."
    )
    parser.add_argument("manifest", type=Path)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate files, organizations, and owners without writing.",
    )
    args = parser.parse_args(argv)
    try:
        items = load_skill_manifest(args.manifest)
    except ManifestValidationError as exc:
        print(
            _compact_json(
                {"ok": False, "error": "invalid_manifest", "message": str(exc)}
            ),
            file=sys.stderr,
        )
        return 2

    try:
        with contextlib.redirect_stdout(io.StringIO()):
            lesson_manager.init_db()
        if args.check:
            validate_skill_owners(items)
            result = {"ok": True, "checked": len(items), "imported": 0, "skills": []}
        else:
            imported = [
                _legacy_result_item(
                    item,
                    lesson_manager.import_class_commentary_skill_manifest(**item),
                )
                for item in items
            ]
            result = {"ok": True, "count": len(imported), "skills": imported}
    except lesson_manager.ClassCommentarySkillImportConflict as exc:
        print(
            _compact_json({"ok": False, "error": "conflict", "message": str(exc)}),
            file=sys.stderr,
        )
        return 1
    except (OSError, ValueError) as exc:
        print(
            _compact_json(
                {"ok": False, "error": "import_failed", "message": str(exc)}
            ),
            file=sys.stderr,
        )
        return 1
    print(_compact_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
