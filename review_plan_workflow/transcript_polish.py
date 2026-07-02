from __future__ import annotations

import hashlib


REVIEW_PLAN_TRANSCRIPT_POLISH_SCHEMA_VERSION = "2026-07-01"
DEFAULT_REVIEW_PLAN_MATH_TERMS = (
    "动点",
    "定点",
    "轨迹",
    "球面",
    "截面",
    "垂直",
    "平行",
    "全等",
    "相似",
    "角度",
)
REVIEW_PLAN_TRANSCRIPT_POLISH_SYSTEM_PROMPT = (
    "You correct ASR transcript text for review-plan source understanding. "
    "Only correct ASR recognition errors, punctuation, and light sentence boundaries. "
    "Do not change meaning. "
    "Do not invent facts, topics, students, formulas, or examples. "
    "Do not rewrite this into parent feedback. "
    "Do not create review tasks. "
    "Do not compress or expand content to satisfy teacher requirements. "
    "Return polished transcript text only."
)


def build_review_plan_transcript_polish_payload(
    *,
    raw_transcript_text: str,
    subject: str = "",
    grade: str = "",
    topic: str = "",
    teacher_requirements: str = "",
    math_terms: list[str] | tuple[str, ...] | None = None,
) -> dict:
    terms = [str(item).strip() for item in (math_terms or DEFAULT_REVIEW_PLAN_MATH_TERMS) if str(item).strip()]
    return {
        "schema_version": REVIEW_PLAN_TRANSCRIPT_POLISH_SCHEMA_VERSION,
        "task": "review_plan_transcript_polish",
        "lesson": {"subject": subject, "grade": grade, "topic": topic},
        "teacher_requirements": str(teacher_requirements or "").strip(),
        "math_terms": terms,
        "raw_transcript": str(raw_transcript_text or "").strip(),
        "rules": [
            "Only correct ASR recognition errors, punctuation, and light sentence boundaries.",
            "Use math_terms only to correct obvious recognition mistakes.",
            "Do not add topics, examples, formulas, students, or teacher claims.",
            "Do not create review tasks",
            "Do not rewrite this into parent feedback",
            "Do not compress or expand content to satisfy teacher_requirements.",
            "Return polished transcript text only.",
        ],
    }


def normalize_review_plan_transcript_polish_text(text: str) -> str:
    cleaned = str(text or "").strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    return "\n".join(line.rstrip() for line in cleaned.splitlines()).strip()


def review_plan_transcript_source_text_hash(text: str) -> str:
    digest = hashlib.sha256(str(text or "").encode("utf-8")).hexdigest()
    return f"sha256:{digest}"
