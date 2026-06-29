from __future__ import annotations

import json
from pathlib import Path


CLASS_COMMENTARY_TRANSCRIPT_POLISH_MATH_TERMS = (
    "绝对值",
    "整式",
    "单项式",
    "多项式",
    "方程",
    "不等式",
    "计算",
    "推理",
    "分类讨论",
    "流程图",
    "取值无关",
    "解题过程",
)


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


def sanitize_class_commentary_roster(students: list[dict]) -> list[dict]:
    roster = []
    for item in students:
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        try:
            student_id = int(item.get("id") or 0)
        except (TypeError, ValueError):
            student_id = 0
        if student_id <= 0:
            continue
        roster.append({"id": student_id, "name": name})
    return roster


def build_class_commentary_generation_payload(
    *,
    class_record: dict,
    students: list[dict],
    transcript_text: str,
    skill: dict,
) -> dict:
    roster = sanitize_class_commentary_roster(students)
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
            "Use the selected skill as the primary working contract for judgment focus, feedback structure, tone, and phrasing.",
            "Use facts only from the transcript and roster; do not treat the skill as a source of student facts.",
            "Output one plain text block.",
            "Format each block exactly as: student name, colon, newline, one sendable paragraph.",
        ],
    }


def build_class_commentary_transcript_polish_payload(
    *,
    class_record: dict,
    students: list[dict],
    raw_transcript_text: str,
    math_terms: list[str] | tuple[str, ...] | None = None,
) -> dict:
    terms = [str(item).strip() for item in (math_terms or CLASS_COMMENTARY_TRANSCRIPT_POLISH_MATH_TERMS) if str(item).strip()]
    return {
        "class": {"id": int(class_record["id"]), "name": str(class_record.get("name") or "")},
        "students": sanitize_class_commentary_roster(students),
        "math_terms": terms,
        "raw_transcript": str(raw_transcript_text or "").strip(),
        "rules": [
            "Only correct ASR recognition errors, punctuation, and light sentence boundaries.",
            "Only correct student names to names in students.",
            "If a likely name cannot be confidently mapped to one listed student, keep the raw wording.",
            "Do not add students who are not clearly mentioned.",
            "Do not rewrite this into parent feedback.",
            "Do not change meaning, tone, praise, criticism, reminders, or factual claims.",
            "Use math_terms only to correct obvious ASR mistakes; do not add topics.",
            "Return plain text only.",
        ],
    }


def normalize_class_commentary_feedback_text(text: str) -> str:
    return "\n".join(line.rstrip() for line in str(text or "").strip().splitlines()).strip()


def payload_to_json(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)
