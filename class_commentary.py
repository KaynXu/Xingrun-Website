from __future__ import annotations

import json
from pathlib import Path


def _safe_skill_filename(skill_id: str) -> str:
    normalized = str(skill_id or "").strip()
    if normalized.endswith(".skill"):
        normalized = normalized[:-6]
    if not normalized or "/" in normalized or "\\" in normalized or normalized in {".", ".."}:
        raise ValueError("invalid skill_id")
    return f"{normalized}.skill"


def list_colleague_skills(skill_dir: str) -> list[dict]:
    root = Path(str(skill_dir or "")).expanduser()
    if not skill_dir or not root.exists() or not root.is_dir():
        return []
    skills = []
    for path in sorted(root.iterdir(), key=lambda item: item.name.lower()):
        if not path.is_file() or path.suffix != ".skill":
            continue
        stat = path.stat()
        skills.append(
            {
                "id": path.stem,
                "name": path.stem,
                "filename": path.name,
                "updated_at": str(int(stat.st_mtime)),
            }
        )
    return skills


def load_colleague_skill(skill_dir: str, skill_id: str) -> dict:
    filename = _safe_skill_filename(skill_id)
    root = Path(str(skill_dir or "")).expanduser()
    path = root / filename
    if not root.exists() or not root.is_dir() or not path.is_file():
        raise FileNotFoundError("skill not found")
    content = path.read_text(encoding="utf-8")
    return {
        "id": path.stem,
        "name": path.stem,
        "filename": path.name,
        "path": str(path),
        "content": content,
    }


def build_class_commentary_generation_payload(
    *,
    class_record: dict,
    students: list[dict],
    transcript_text: str,
    skill: dict,
) -> dict:
    roster = [
        {"id": int(item["id"]), "name": str(item.get("name") or "").strip()}
        for item in students
        if str(item.get("name") or "").strip()
    ]
    return {
        "class": {"id": int(class_record["id"]), "name": str(class_record.get("name") or "")},
        "students": roster,
        "transcript": str(transcript_text or "").strip(),
        "skill": {
            "id": str(skill.get("id") or ""),
            "name": str(skill.get("name") or ""),
            "content": str(skill.get("content") or ""),
        },
        "output_rules": [
            "Only include students from the roster who are clearly mentioned in the transcript.",
            "Do not include unmentioned students.",
            "Feedback can include praise, problem, reminder, next action, or suggestion.",
            "Do not invent facts not supported by the transcript.",
            "Use the selected skill only as expression style and feedback framing, not as a source of student facts.",
            "Output one plain text block.",
            "Format each block exactly as: student name, colon, newline, one sendable paragraph.",
        ],
    }


def normalize_class_commentary_feedback_text(text: str) -> str:
    return "\n".join(line.rstrip() for line in str(text or "").strip().splitlines()).strip()


def payload_to_json(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)
