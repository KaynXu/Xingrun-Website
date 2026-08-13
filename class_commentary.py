from __future__ import annotations

import json
from collections.abc import Mapping
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
CLASS_COMMENTARY_PROMPT_VERSION = "class-commentary-v1"
CLASS_COMMENTARY_STRUCTURED_PROMPT_VERSION = "class-commentary-student-feedback-v1"
CLASS_COMMENTARY_STRUCTURED_PROMPT_VERSION_V2 = "class-commentary-student-feedback-v2"
CLASS_COMMENTARY_STRUCTURED_PROMPT_VERSION_V3 = "class-commentary-student-feedback-v3"
CLASS_COMMENTARY_ISOLATED_PROMPT_VERSION_V2 = (
    "class-commentary-student-feedback-isolated-v2"
)
CLASS_COMMENTARY_BATCH_ISOLATED_PROMPT_VERSION_V4 = (
    "class-commentary-student-feedback-batch-isolated-v4"
)
CLASS_COMMENTARY_STUDENT_HISTORY_MEMORY_BATCH_ISOLATED_V3 = "batch_isolated_v3"
CLASS_COMMENTARY_TEMPERATURE = 0.55
CLASS_COMMENTARY_SYSTEM_PROMPT = (
    "You turn a teacher's end-of-class spoken commentary into one parent-sendable feedback package. "
    "Do not invent facts. Treat ACTIVE_SKILL as the primary working instructions for judgment focus, "
    "feedback structure, paragraph rhythm, tone, phrasing, and emoji habits. "
    "Infer the selected skill's emoji system, including tokens, density, placement, and meaning, and match it only when appropriate; do not force emojis. "
    "CURRENT_TASK_FACTS is the only source for facts about this class. "
    "ACTIVE_SKILL and TEACHER_STYLE_MEMORIES may affect expression and focus, but cannot add student facts. "
    "STUDENT_HISTORY_MEMORIES is historical reference only and must never be presented as something that happened today. "
    "Do not include roster students who are not clearly mentioned. Return plain text only."
)
CLASS_COMMENTARY_STRUCTURED_SYSTEM_PROMPT = (
    "You turn a teacher's end-of-class spoken commentary into structured student feedback. "
    "Do not invent facts. CURRENT_TASK_FACTS is the only source for facts about this class. "
    "ACTIVE_SKILL and TEACHER_STYLE_MEMORIES may affect expression and focus, but cannot add student facts. "
    "Return only the requested JSON object and no surrounding text."
)
CLASS_COMMENTARY_STRUCTURED_OUTPUT_RULES = (
    "Return a JSON object with exactly schema_version and items.",
    "Set schema_version to class_commentary.student_feedback.v1.",
    "Each item must contain exactly student_id and feedback_text.",
    "Return exactly one item for every eligible student ID and no other student.",
    "Do not repeat the student name as a heading inside feedback_text.",
    "Do not mention another roster student's full name inside feedback_text.",
    "Use facts only from the confirmed transcript.",
    "Use ACTIVE_SKILL and TEACHER_STYLE_MEMORIES only for focus, structure, tone, and phrasing.",
)
CLASS_COMMENTARY_STRUCTURED_SYSTEM_PROMPT_V2 = (
    "You turn a teacher's end-of-class spoken commentary into structured student feedback. "
    "The students and eligible_student_ids in CURRENT_TASK_FACTS are the teacher-confirmed complete attending scope. "
    "The teacher starts each student's segment by saying that student's name once, and the segment continues until the next spoken student name. "
    "ASR may render a spoken name with homophones, near-sounding syllables, or similar characters instead of the official roster spelling. "
    "Map each spoken name and its segment to the best unique official roster student using pronunciation and context, then return the official student_id. "
    "Do not invent facts or transfer facts between student segments. "
    "CURRENT_TASK_FACTS is the only source for facts about this class. "
    "ACTIVE_SKILL and TEACHER_STYLE_MEMORIES may affect expression and focus, but cannot add student facts. "
    "Return only the requested JSON object and no surrounding text."
)
CLASS_COMMENTARY_STRUCTURED_OUTPUT_RULES_V2 = (
    "Return a JSON object with exactly schema_version and items.",
    "Set schema_version to class_commentary.student_feedback.v1.",
    "Each item must contain exactly student_id and feedback_text.",
    "Treat students and eligible_student_ids as the complete teacher-confirmed attending scope.",
    "Each student's segment starts when the teacher says that student's name and ends when the next student's name is spoken.",
    "A spoken name may be transcribed with homophones, near-sounding syllables, or similar characters; it does not need to contain the official roster name exactly.",
    "Map each spoken name variant to the best unique roster student by pronunciation and context, and use the official student_id.",
    "Return exactly one item for every eligible student ID and no other student.",
    "Never omit a student only because the transcript spelling differs from the official name.",
    "If no unique roster match can be made, do not invent, copy, or assign another student's facts; omit that item so the response is rejected for teacher review.",
    "Do not repeat the student name as a heading inside feedback_text.",
    "Do not mention another roster student's full name inside feedback_text.",
    "Use facts only from the confirmed transcript.",
    "Use ACTIVE_SKILL and TEACHER_STYLE_MEMORIES only for focus, structure, tone, and phrasing.",
)
CLASS_COMMENTARY_STRUCTURED_SYSTEM_PROMPT_V3 = (
    "You turn a teacher's end-of-class spoken commentary into structured student feedback. "
    "The students and eligible_student_ids in CURRENT_TASK_FACTS are the teacher-confirmed complete attending scope. "
    "The teacher starts each student's segment by saying that student's name once, and the segment continues until the next spoken student name. "
    "ASR may render a spoken name with homophones, near-sounding syllables, or similar characters instead of the official roster spelling. "
    "Map each spoken name and its segment to the best unique official roster student using pronunciation and context, then return the official student_id. "
    "Write every feedback_text as the teacher speaking directly to that student, not as a narrator reporting about the student. "
    "Use the student's official name once as a natural opening address, then address the student as '你'; use '我' or '我们' when the teacher refers to themself. "
    "Do not invent facts or transfer facts between student segments. "
    "CURRENT_TASK_FACTS is the only source for facts about this class. "
    "ACTIVE_SKILL and TEACHER_STYLE_MEMORIES may affect expression and focus, but cannot add student facts or override the direct-address perspective. "
    "Return only the requested JSON object and no surrounding text."
)
CLASS_COMMENTARY_STRUCTURED_OUTPUT_RULES_V3 = (
    "Return a JSON object with exactly schema_version and items.",
    "Set schema_version to class_commentary.student_feedback.v1.",
    "Each item must contain exactly student_id and feedback_text.",
    "Treat students and eligible_student_ids as the complete teacher-confirmed attending scope.",
    "Each student's segment starts when the teacher says that student's name and ends when the next student's name is spoken.",
    "A spoken name may be transcribed with homophones, near-sounding syllables, or similar characters; it does not need to contain the official roster name exactly.",
    "Map each spoken name variant to the best unique roster student by pronunciation and context, and use the official student_id.",
    "Return exactly one item for every eligible student ID and no other student.",
    "Never omit a student only because the transcript spelling differs from the official name.",
    "If no unique roster match can be made, do not invent, copy, or assign another student's facts; omit that item so the response is rejected for teacher review.",
    "Write feedback_text as the teacher speaking directly to the target student, never as a third-person report about the student.",
    "Begin with the target student's official name as a natural form of address, not a standalone heading; then use '你' for the student and '我' or '我们' for the teacher when needed.",
    "Never refer to the target student as '他', '她', '该生', '这位同学', or '学生' from a narrator's viewpoint.",
    "Keep advice conversational and specific instead of repeatedly starting sentences with '你要'. For example: '代子翔, 你下去多复习一下函数', not '他要多做题'.",
    "Do not mention another roster student's full name inside feedback_text.",
    "Use facts only from the confirmed transcript.",
    "The direct-address perspective is mandatory even if ACTIVE_SKILL or TEACHER_STYLE_MEMORIES uses a different narrative perspective.",
    "Use ACTIVE_SKILL and TEACHER_STYLE_MEMORIES only for focus, structure, tone, and phrasing.",
)
CLASS_COMMENTARY_BATCH_ISOLATED_SYSTEM_PROMPT_V4 = (
    "You turn a teacher's end-of-class spoken commentary into structured student feedback. "
    "The students and eligible_student_ids in CURRENT_TASK_FACTS are the teacher-confirmed complete attending scope. "
    "CURRENT_TASK_FACTS contains class and attendance scope only. "
    "For facts newly observed in this lesson, each output item may use only the verified current_student_evidence in its matching STUDENT_CONTEXTS_BY_ID partition. "
    "Write every feedback_text as the teacher speaking directly to that student, not as a narrator reporting about the student. "
    "Use the student's official name once as a natural opening address, then address the student as '你'; use '我' or '我们' when the teacher refers to themself. "
    "Do not invent facts, infer ownership from surrounding text, or transfer facts between student partitions. "
    "Treat ACTIVE_SKILL as the primary writing contract for judgment focus, feedback structure, paragraph rhythm, tone, phrasing, and emoji habits. "
    "Infer the selected skill's emoji tokens, density, placement, and purpose, and match them when appropriate without forcing emojis for a low-emoji skill. "
    "ACTIVE_SKILL and TEACHER_STYLE_MEMORIES cannot add student facts or override the direct-address perspective. "
    "TEACHER_STYLE_MEMORIES are secondary style hints and cannot override ACTIVE_SKILL. "
    "STUDENT_CONTEXTS_BY_ID contains verified current evidence plus historical Mem0 and learning-graph context partitioned by student_id. "
    "For each feedback item, use only the context whose student_id matches that item; never transfer, compare, or reveal context across students. "
    "Treat student history and learning-graph context as historical reference, never as something newly observed in this lesson, and let verified current_student_evidence override history. "
    "Return only the requested JSON object and no surrounding text."
)
CLASS_COMMENTARY_BATCH_ISOLATED_OUTPUT_RULES_V4 = (
    "Return a JSON object with exactly schema_version, items, and used_graph_evidence_refs_by_student.",
    "Set schema_version to class_commentary.student_feedback.v1.",
    "Each item must contain exactly student_id and feedback_text.",
    "Set used_graph_evidence_refs_by_student to one object per eligible student, each with exactly student_id and evidence_refs.",
    "For each student, evidence_refs must contain only evidence_ref values actually used from that student's matching learning_graph allowlist; otherwise use an empty array.",
    "Treat students and eligible_student_ids as the complete teacher-confirmed attending scope.",
    "Return exactly one item for every eligible student ID and no other student.",
    "Write feedback_text as the teacher speaking directly to the target student, never as a third-person report about the student.",
    "Begin with the target student's official name as a natural form of address, not a standalone heading; then use '你' for the student and '我' or '我们' for the teacher when needed.",
    "Never refer to the target student as '他', '她', '该生', '这位同学', or '学生' from a narrator's viewpoint.",
    "Keep advice conversational and specific instead of repeatedly starting sentences with '你要'. For example: '代子翔, 你下去多复习一下函数', not '他要多做题'.",
    "Do not mention another roster student's full name inside feedback_text.",
    "For current-lesson facts, use only current_student_evidence from the matching student_id partition.",
    "The direct-address perspective is mandatory even if ACTIVE_SKILL or TEACHER_STYLE_MEMORIES uses a different narrative perspective.",
    "Use ACTIVE_SKILL as the primary writing contract for focus, structure, paragraph rhythm, tone, phrasing, and emoji habits; use TEACHER_STYLE_MEMORIES only as secondary style hints.",
    "When current_student_evidence supports multiple useful points, write 2-4 short paragraphs in feedback_text instead of compressing everything into one short paragraph.",
    "Let each paragraph focus on one supported idea, such as current performance, a concrete problem, the next action, or parent cooperation when relevant.",
    "For a specific problem supported by current_student_evidence, state the problem clearly and give a concrete next action instead of a generic reminder.",
    "Even when current_student_evidence is sparse, write at least one useful complete observation rather than empty encouragement such as only '继续努力' or '加油'.",
    "Keep sparse-evidence feedback concise, usually 1-2 short paragraphs; use 2-4 short paragraphs when the evidence supports multiple useful points.",
    "Infer the selected skill's emoji tokens, density, placement, and purpose from ACTIVE_SKILL, then match that emoji system when it fits the feedback.",
    "If ACTIVE_SKILL uses emojis as part of its normal parent-group voice, use comparable emoji frequency and placement in every student's feedback; do not drop emojis merely because the output is structured.",
    "If ACTIVE_SKILL explicitly names a low-density emoji family, preserve at least one matching emoji somewhere in the complete class response; it need not appear in every student's feedback.",
    "Do not force emojis when ACTIVE_SKILL rarely uses them, and do not hard-code a different colleague's emoji set.",
    "Keep the selected colleague's conversational parent-group voice; do not over-polish the feedback into formal report language.",
    "For each output item, use only the matching student_id partition in STUDENT_CONTEXTS_BY_ID; never use another student's current evidence, history, or learning graph.",
    "Treat only student_history_memories and learning_graph as historical reference. Do not describe them as observed today unless matching current_student_evidence independently supports it.",
)


def get_class_commentary_structured_prompt_contract(
    prompt_version: str,
) -> tuple[str, tuple[str, ...]]:
    normalized_version = str(prompt_version or "").strip()
    if normalized_version == CLASS_COMMENTARY_STRUCTURED_PROMPT_VERSION:
        return (
            CLASS_COMMENTARY_STRUCTURED_SYSTEM_PROMPT,
            CLASS_COMMENTARY_STRUCTURED_OUTPUT_RULES,
        )
    if normalized_version == CLASS_COMMENTARY_STRUCTURED_PROMPT_VERSION_V2:
        return (
            CLASS_COMMENTARY_STRUCTURED_SYSTEM_PROMPT_V2,
            CLASS_COMMENTARY_STRUCTURED_OUTPUT_RULES_V2,
        )
    if normalized_version == CLASS_COMMENTARY_STRUCTURED_PROMPT_VERSION_V3:
        return (
            CLASS_COMMENTARY_STRUCTURED_SYSTEM_PROMPT_V3,
            CLASS_COMMENTARY_STRUCTURED_OUTPUT_RULES_V3,
        )
    if normalized_version == CLASS_COMMENTARY_BATCH_ISOLATED_PROMPT_VERSION_V4:
        return (
            CLASS_COMMENTARY_BATCH_ISOLATED_SYSTEM_PROMPT_V4,
            CLASS_COMMENTARY_BATCH_ISOLATED_OUTPUT_RULES_V4,
        )
    raise ValueError("structured class commentary prompt version is invalid")


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


def _colleague_skill_sort_key(name: str) -> tuple[str, str]:
    return name.casefold(), name


def _read_skill_package_name(path: Path) -> str:
    meta_path = path / "meta.json"
    if not meta_path.is_file() or meta_path.is_symlink():
        return path.name
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return path.name
    name = str(meta.get("name") or "").strip() if isinstance(meta, dict) else ""
    return name or path.name


def _skill_package_updated_at(path: Path) -> str:
    mtimes = [path.stat().st_mtime]
    for file_path in _class_commentary_skill_package_markdown_files(path):
        mtimes.append(file_path.stat().st_mtime)
    meta_path = path / "meta.json"
    if meta_path.is_file() and not meta_path.is_symlink():
        mtimes.append(meta_path.stat().st_mtime)
    return str(int(max(mtimes)))


def _class_commentary_skill_package_markdown_files(path: Path) -> list[Path]:
    files = [
        file_path
        for file_path in (path / "SKILL.md", path / "work.md", path / "persona.md")
        if file_path.is_file()
        and not file_path.is_symlink()
        and not file_path.name.startswith("._")
    ]
    knowledge_path = path / "knowledge"
    if knowledge_path.is_dir():
        def has_symlinked_package_parent(file_path: Path) -> bool:
            relative_path = file_path.relative_to(path)
            current_path = path
            for part in relative_path.parts[:-1]:
                current_path = current_path / part
                if current_path.is_symlink():
                    return True
            return False

        files.extend(
            sorted(
                (
                    file_path
                    for file_path in knowledge_path.rglob("*.md")
                    if file_path.is_file()
                    and not file_path.is_symlink()
                    and not file_path.name.startswith("._")
                    and not has_symlinked_package_parent(file_path)
                ),
                key=lambda file_path: (
                    file_path.relative_to(path).as_posix().casefold(),
                    file_path.relative_to(path).as_posix(),
                ),
            )
        )
    return files


def read_class_commentary_skill_package_content(path: Path) -> str:
    parts = []
    included_contents = []
    for file_path in _class_commentary_skill_package_markdown_files(path):
        content = file_path.read_text(encoding="utf-8").strip()
        if not content or any(content in included for included in included_contents):
            continue
        relative_path = file_path.relative_to(path).as_posix()
        parts.append(f"## {relative_path}\n{content}")
        included_contents.append(content)
    return "\n\n".join(parts).strip()


def _colleague_skill_roots(root: Path) -> list[Path]:
    roots = [root]
    colleagues_root = root / "colleagues"
    if colleagues_root.is_dir() and not colleagues_root.is_symlink():
        roots.append(colleagues_root)
    return roots


def list_colleague_skills(skill_dir: str) -> list[dict]:
    root = Path(str(skill_dir or "")).expanduser()
    if not skill_dir or not root.exists() or not root.is_dir():
        return []
    skills_by_id = {}
    for scan_root in _colleague_skill_roots(root):
        for path in sorted(
            scan_root.iterdir(), key=lambda item: _colleague_skill_sort_key(item.name)
        ):
            if (
                path.is_dir()
                and not path.is_symlink()
                and (path / "SKILL.md").is_file()
                and not (path / "SKILL.md").is_symlink()
            ):
                skills_by_id[path.name] = {
                    "id": path.name,
                    "name": _read_skill_package_name(path),
                    "filename": f"{path.name}/SKILL.md",
                    "updated_at": _skill_package_updated_at(path),
                }
            elif (
                path.is_file()
                and not path.is_symlink()
                and path.suffix == ".skill"
                and path.stem not in skills_by_id
            ):
                stat = path.stat()
                skills_by_id[path.stem] = {
                    "id": path.stem,
                    "name": path.stem,
                    "filename": path.name,
                    "updated_at": str(int(stat.st_mtime)),
                }
    return [
        skills_by_id[key]
        for key in sorted(skills_by_id, key=_colleague_skill_sort_key)
    ]


def load_colleague_skill(skill_dir: str, skill_id: str) -> dict:
    normalized_id = _safe_skill_id(skill_id)
    root = Path(str(skill_dir or "")).expanduser()
    if not root.exists() or not root.is_dir():
        raise FileNotFoundError("skill not found")
    for scan_root in _colleague_skill_roots(root):
        package_path = scan_root / normalized_id
        if (
            package_path.is_dir()
            and not package_path.is_symlink()
            and (package_path / "SKILL.md").is_file()
            and not (package_path / "SKILL.md").is_symlink()
        ):
            return {
                "id": package_path.name,
                "name": _read_skill_package_name(package_path),
                "filename": f"{package_path.name}/SKILL.md",
                "path": str(package_path / "SKILL.md"),
                "content": read_class_commentary_skill_package_content(package_path),
            }
    path = root / _safe_skill_filename(normalized_id)
    if path.is_file() and not path.is_symlink():
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
            "Infer the selected skill's emoji tokens, density, placement, and meaning from the supplied skill content, then match that emoji system when it fits the transcript.",
            "If the selected skill uses emojis as part of its normal parent-group voice, use comparable emoji frequency across the opening, transitions, encouragement, softened criticism, and student-specific feedback.",
            "Do not force emojis when the selected skill rarely uses them. Do not hard-code a different colleague's emoji set into this output.",
            "Do not over-polish into formal report language; keep the selected colleague's live parent-group speaking style.",
        ],
    }


def build_class_commentary_chat_request(
    *,
    class_record: dict,
    students: list[dict],
    transcript_text: str,
    skill: dict,
    teacher_style_memories: list[dict] | None = None,
    student_history_memories: list[dict] | None = None,
    feedback_schema_version: str = "",
    eligible_student_ids: list[int] | None = None,
    prompt_version: str = "",
    response_format: dict | None = None,
    student_history_memory_mode: str = "",
    student_contexts_by_id: list[dict] | None = None,
) -> dict:
    payload = build_class_commentary_generation_payload(
        class_record=class_record,
        students=students,
        transcript_text=transcript_text,
        skill=skill,
    )
    current_task_facts = {
        "class": payload["class"],
        "students": payload["students"],
        "transcript": payload["transcript"],
    }
    normalized_schema_version = str(feedback_schema_version or "")
    normalized_prompt_version = str(prompt_version or "").strip()
    if normalized_schema_version:
        batch_context_mode = (
            student_history_memory_mode
            == CLASS_COMMENTARY_STUDENT_HISTORY_MEMORY_BATCH_ISOLATED_V3
        )
        if (
            normalized_schema_version != "class_commentary.student_feedback.v1"
            or student_history_memory_mode
            not in {
                "disabled_v1",
                CLASS_COMMENTARY_STUDENT_HISTORY_MEMORY_BATCH_ISOLATED_V3,
            }
            or student_history_memories
            or not eligible_student_ids
            or response_format != {"type": "json_object"}
            or (batch_context_mode and not student_contexts_by_id)
            or (not batch_context_mode and student_contexts_by_id)
            or (
                batch_context_mode
                != (
                    normalized_prompt_version
                    == CLASS_COMMENTARY_BATCH_ISOLATED_PROMPT_VERSION_V4
                )
            )
        ):
            raise ValueError("structured class commentary prompt contract is invalid")
        if batch_context_mode:
            normalized_context_ids = [
                item.get("student_id")
                for item in student_contexts_by_id
                if isinstance(item, Mapping)
            ]
            if (
                normalized_context_ids != eligible_student_ids
                or len(normalized_context_ids) != len(student_contexts_by_id or [])
                or len(normalized_context_ids) != len(set(normalized_context_ids))
            ):
                raise ValueError("structured class commentary batch scope is invalid")
        structured_system_prompt, structured_output_rules = (
            get_class_commentary_structured_prompt_contract(
                normalized_prompt_version
            )
        )
        if batch_context_mode:
            current_task_facts.pop("transcript", None)
        current_task_facts["eligible_student_ids"] = eligible_student_ids
        prompt_sections = [
            "[CURRENT_TASK_FACTS]\n" + payload_to_json(current_task_facts),
            "[ACTIVE_SKILL]\n" + payload_to_json(payload["skill"]),
            "[TEACHER_STYLE_MEMORIES]\n"
            + payload_to_json(teacher_style_memories or []),
        ]
        if batch_context_mode:
            prompt_sections.append(
                "[STUDENT_CONTEXTS_BY_ID]\n"
                + payload_to_json(student_contexts_by_id or [])
            )
        prompt_sections.append(
            "[OUTPUT_RULES]\n"
            + "\n".join(f"- {rule}" for rule in structured_output_rules)
        )
        system_prompt = structured_system_prompt
    else:
        prompt_sections = (
            "[CURRENT_TASK_FACTS]\n" + payload_to_json(current_task_facts),
            "[ACTIVE_SKILL]\n" + payload_to_json(payload["skill"]),
            "[TEACHER_STYLE_MEMORIES]\n"
            + payload_to_json(teacher_style_memories or []),
            "[STUDENT_HISTORY_MEMORIES]\n"
            + payload_to_json(student_history_memories or []),
            "[OUTPUT_RULES]\n" + "\n".join(f"- {rule}" for rule in payload["output_rules"]),
        )
        system_prompt = CLASS_COMMENTARY_SYSTEM_PROMPT
    user_prompt = "\n\n".join(prompt_sections)
    request_payload = {
        "prompt_version": normalized_prompt_version or CLASS_COMMENTARY_PROMPT_VERSION,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": CLASS_COMMENTARY_TEMPERATURE,
    }
    if normalized_schema_version:
        request_payload.update(
            {
                "response_format": dict(response_format or {}),
                "student_history_memory_mode": student_history_memory_mode,
            }
        )
    return request_payload


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
