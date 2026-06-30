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


def _safe_skill_id(skill_id: str) -> str:
    normalized = str(skill_id or "").strip()
    if normalized.endswith(".skill"):
        normalized = normalized[:-6]
    if not normalized or "/" in normalized or "\\" in normalized or normalized in {".", ".."}:
        raise ValueError("invalid skill_id")
    return normalized


def _read_skill_package_name(path: Path) -> str:
    meta_path = path / "meta.json"
    if not meta_path.is_file():
        return path.name
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return path.name
    name = str(meta.get("name") or "").strip() if isinstance(meta, dict) else ""
    return name or path.name


def _skill_package_updated_at(path: Path) -> str:
    mtimes = [path.stat().st_mtime]
    for filename in ("SKILL.md", "work.md", "persona.md", "meta.json"):
        file_path = path / filename
        if file_path.is_file():
            mtimes.append(file_path.stat().st_mtime)
    return str(int(max(mtimes)))


def _read_skill_package_content(path: Path) -> str:
    parts = []
    for filename in ("SKILL.md", "work.md", "persona.md"):
        file_path = path / filename
        if not file_path.is_file():
            continue
        content = file_path.read_text(encoding="utf-8").strip()
        if content:
            parts.append(f"## {filename}\n{content}")
    return "\n\n".join(parts).strip()


def _colleague_skill_roots(root: Path) -> list[Path]:
    roots = [root]
    colleagues_root = root / "colleagues"
    if colleagues_root.is_dir():
        roots.append(colleagues_root)
    return roots


def list_colleague_skills(skill_dir: str) -> list[dict]:
    root = Path(str(skill_dir or "")).expanduser()
    if not skill_dir or not root.exists() or not root.is_dir():
        return []
    skills_by_id = {}
    for scan_root in _colleague_skill_roots(root):
        for path in sorted(scan_root.iterdir(), key=lambda item: item.name.lower()):
            if path.is_dir() and (path / "SKILL.md").is_file():
                skills_by_id[path.name] = {
                    "id": path.name,
                    "name": _read_skill_package_name(path),
                    "filename": f"{path.name}/SKILL.md",
                    "updated_at": _skill_package_updated_at(path),
                }
            elif path.is_file() and path.suffix == ".skill" and path.stem not in skills_by_id:
                stat = path.stat()
                skills_by_id[path.stem] = {
                    "id": path.stem,
                    "name": path.stem,
                    "filename": path.name,
                    "updated_at": str(int(stat.st_mtime)),
                }
    return [skills_by_id[key] for key in sorted(skills_by_id, key=str.lower)]


def load_colleague_skill(skill_dir: str, skill_id: str) -> dict:
    normalized_id = _safe_skill_id(skill_id)
    root = Path(str(skill_dir or "")).expanduser()
    if not root.exists() or not root.is_dir():
        raise FileNotFoundError("skill not found")
    for scan_root in _colleague_skill_roots(root):
        package_path = scan_root / normalized_id
        if package_path.is_dir() and (package_path / "SKILL.md").is_file():
            return {
                "id": package_path.name,
                "name": _read_skill_package_name(package_path),
                "filename": f"{package_path.name}/SKILL.md",
                "path": str(package_path / "SKILL.md"),
                "content": _read_skill_package_content(package_path),
            }
    path = root / _safe_skill_filename(normalized_id)
    if path.is_file():
        return {
            "id": path.stem,
            "name": path.stem,
            "filename": path.name,
            "path": str(path),
            "content": path.read_text(encoding="utf-8"),
        }
    raise FileNotFoundError("skill not found")


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
            "Use the selected skill as the primary working contract for judgment focus, feedback structure, paragraph rhythm, tone, phrasing, and emoji habits.",
            "Use facts only from the transcript and roster; do not treat the skill as a source of student facts.",
            "Output plain text only.",
            "Use each mentioned student name as a visible section label, but do not force a single long paragraph.",
            "When a student has multiple feedback points, write 2-4 short paragraphs instead of squeezing everything into one paragraph.",
            "Each paragraph should focus on one idea, such as current state, concrete problem, next action, or parent cooperation.",
            "If the selected skill uses bracket-style emojis such as [呲牙] or [破涕为笑], preserve that emoji style and use it as the skill would, especially to soften direct criticism or mark good news.",
            "Do not over-polish into formal report language; keep the selected colleague's live parent-group speaking style.",
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
