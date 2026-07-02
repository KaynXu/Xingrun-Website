from __future__ import annotations

import re
from typing import Any

from .schemas import QualityIssue, QualityReview, normalize_final_review_plan, validate_final_review_plan


def _contains_any(text: str, candidates: tuple[str, ...]) -> bool:
    return any(candidate in text for candidate in candidates)


GENERIC_TOPICS = {"", "课后", "本课内容", "本节课", "课堂内容", "复习计划"}
GENERIC_TOPIC_SUFFIXES = ("复习计划", "综合复习", "专题复习", "复习", "专题", "课程")
BAD_QUOTE_PATTERNS = (
    "每一个复习日",
    "完整复习整节课内容",
    "请完成以上",
    "对照答案自检",
    "完成当天",
    "完成以上填空",
    "完成标准",
    "使用说明",
    "复习计划",
    "正确率≥",
    "正确率>=",
    "填空题全部正确",
    "能独立",
)
BAD_MATH_TEXT_PATTERNS = (
    "begincases",
    "endcases",
    "sqrtlog_",
    "log_(",
)
BAD_MATH_REGEXES = (
    re.compile(r"(?<!\\)sqrt\["),
    re.compile(r"\\x0[0-8a-fA-F]"),
    re.compile(r"\\u000[0-9a-fA-F]"),
)
PLACEHOLDER_PATTERNS = (
    "（具体题目）",
    "按实际填写",
    "板块X",
    "第1天请回忆",
    "关键空格",
    "见课堂笔记",
)
MODEL_SELF_CORRECTION_PATTERNS = (
    "答案没有",
    "实际正确",
    "故修改选项",
    "检查：若",
)
BAD_BLANK_ANSWERS = {
    "方法",
    "入口",
    "边界",
    "条件",
    "过程",
    "证明",
    "范围",
    "来源",
    "意义",
    "分数",
    "先决",
    "运算",
    "动作",
    "提醒",
}
VAGUE_STEM_PATTERNS = ("某题", "这个题", "原题中", "题号")
SKELETAL_OPTION_LABELS = {
    "A",
    "B",
    "C",
    "D",
    "A.",
    "B.",
    "C.",
    "D.",
    "A．",
    "B．",
    "C．",
    "D．",
    "A、",
    "B、",
    "C、",
    "D、",
    "A)",
    "B)",
    "C)",
    "D)",
}


def _clean_text(value: object) -> str:
    return str(value or "").strip()


def _compact_text(value: str) -> str:
    return re.sub(r"[\s,，。.!！?？、:：;；《》「」“”\"'`（）()\[\]【】\-_/]+", "", value)


def _strip_topic_suffixes(value: str) -> str:
    stripped = value
    changed = True
    while changed:
        changed = False
        for suffix in GENERIC_TOPIC_SUFFIXES:
            if stripped.endswith(suffix) and len(stripped) > len(suffix):
                stripped = stripped[: -len(suffix)]
                changed = True
    return stripped


def _is_generic_coverage_topic(value: object, lesson_topic: str) -> bool:
    text = _clean_text(value)
    if text in GENERIC_TOPICS:
        return True
    compact = _compact_text(text)
    topic_compact = _compact_text(lesson_topic)
    if not compact:
        return True
    if topic_compact and compact == topic_compact:
        return True
    if topic_compact and _strip_topic_suffixes(compact) == _strip_topic_suffixes(topic_compact):
        return True
    return compact in {_compact_text(item) for item in GENERIC_TOPICS}


def _iter_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        strings: list[str] = []
        for item in value.values():
            strings.extend(_iter_strings(item))
        return strings
    if isinstance(value, list):
        strings = []
        for item in value:
            strings.extend(_iter_strings(item))
        return strings
    return []


def _collect_quotes(plan: dict[str, Any]) -> list[str]:
    quotes: list[str] = []
    for source in (plan.get("quotes"), plan.get("lesson_info", {}).get("quotes")):
        if isinstance(source, list):
            for quote in source:
                text = _clean_text(quote)
                if text and text not in quotes:
                    quotes.append(text)
    for day in plan.get("days", []) if isinstance(plan.get("days"), list) else []:
        if not isinstance(day, dict) or not isinstance(day.get("quotes"), list):
            continue
        for quote in day["quotes"]:
            text = _clean_text(quote)
            if text and text not in quotes:
                quotes.append(text)
    return quotes


def _quote_is_bad(text: str) -> bool:
    return _contains_any(text, BAD_QUOTE_PATTERNS)


def _has_bad_math_transport(text: str) -> bool:
    if _contains_any(text, BAD_MATH_TEXT_PATTERNS):
        return True
    return any(pattern.search(text) for pattern in BAD_MATH_REGEXES)


def _day_renderable_counts(day: dict[str, Any]) -> tuple[int, int, int]:
    blanks = len(day.get("blanks", [])) if isinstance(day.get("blanks"), list) else 0
    choices = len(day.get("choices", [])) if isinstance(day.get("choices"), list) else 0
    bodies = 0
    for field in ("goal", "focus", "theme", "title", "self_test_phrase"):
        if _clean_text(day.get(field)):
            bodies += 1
    for item in day.get("items", []) if isinstance(day.get("items"), list) else []:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "fill" and _clean_text(item.get("text")):
            blanks += 1
        elif _clean_text(item.get("text")):
            bodies += 1
    for step in day.get("steps", []) if isinstance(day.get("steps"), list) else []:
        if not isinstance(step, dict):
            continue
        if _clean_text(step.get("title")):
            bodies += 1
        for item in step.get("items", []) if isinstance(step.get("items"), list) else []:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "fill" and _clean_text(item.get("text")):
                blanks += 1
            elif _clean_text(item.get("text")):
                bodies += 1
    return blanks, choices, bodies


def _question_signature(value: object) -> str:
    return _compact_text(_clean_text(value))


def _collect_day_unique_question_counts(day: dict[str, Any]) -> tuple[int, int, int]:
    fill_signatures: set[str] = set()
    choice_signatures: set[str] = set()
    raw_fill_count = 0

    def add_fill(value: object) -> None:
        nonlocal raw_fill_count
        signature = _question_signature(value)
        if not signature:
            return
        raw_fill_count += 1
        fill_signatures.add(signature)

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            item_type = _clean_text(value.get("type")).lower()
            fill_text = value.get("text") or value.get("stem") or value.get("question") or value.get("label")
            if item_type == "fill" or (
                fill_text and any(key in value for key in ("answer", "answer_hint", "reference_answer"))
            ):
                add_fill(fill_text)
            for nested in value.values():
                walk(nested)
        elif isinstance(value, list):
            for nested in value:
                walk(nested)

    walk(day.get("blanks", []))
    walk(day.get("items", []))
    walk(day.get("steps", []))
    walk(day.get("active_recall", {}))
    walk(day.get("tasks", {}))
    walk(day.get("oral_cards", []))

    for choice in day.get("choices", []) if isinstance(day.get("choices"), list) else []:
        if not isinstance(choice, dict):
            continue
        signature = _question_signature(choice.get("question") or choice.get("stem"))
        if signature:
            choice_signatures.add(signature)

    return len(fill_signatures), len(choice_signatures), raw_fill_count


def _choice_answer_is_valid(choice: dict[str, Any]) -> bool:
    answer = _clean_text(choice.get("answer"))
    options = choice.get("options") if isinstance(choice.get("options"), list) else []
    if not answer or not options:
        return False
    answer_head = answer[:1].upper()
    option_heads = {_clean_text(option)[:1].upper() for option in options if _clean_text(option)}
    return answer_head in option_heads


def _choice_options_are_complete(choice: dict[str, Any]) -> bool:
    options = choice.get("options") if isinstance(choice.get("options"), list) else []
    if len(options) < 4:
        return False
    for option in options:
        text = _clean_text(option)
        if text.upper().replace(" ", "") in SKELETAL_OPTION_LABELS:
            return False
        body = re.sub(r"^[A-Da-d][\.．、\)]?\s*", "", text).strip()
        if not body or body.upper().replace(" ", "") in SKELETAL_OPTION_LABELS:
            return False
    return True


def review_single_lesson_plan(
    plan: dict[str, Any],
    *,
    subject: str = "",
    required_review_days: list[int] | None = None,
    schedule_mode: str = "standard",
) -> QualityReview:
    normalized_plan = normalize_final_review_plan(plan)
    issues: list[QualityIssue] = []
    subject_key = subject.lower()
    required_days = required_review_days or [1, 2, 7, 14, 30]
    _, schema_errors = validate_final_review_plan(normalized_plan)
    if schema_errors:
        issues.append(
            QualityIssue(
                severity="high",
                category="schema",
                description="复习计划结构未通过 schema 校验：" + "；".join(schema_errors[:3]),
                suggested_fix=f"补齐 lesson_info 与 {required_days} 复习日结构。",
            )
        )

    days = normalized_plan.get("days") if isinstance(normalized_plan.get("days"), list) else []
    day_numbers = {int(day.get("day") or 0) for day in days if isinstance(day, dict)}
    missing_days = set(required_days) - day_numbers
    extra_days = day_numbers - set(required_days)
    if missing_days or extra_days:
        issues.append(
            QualityIssue(
                severity="high",
                category="completeness",
                description="复习日没有严格匹配本次生成设置。",
                suggested_fix=f"days 必须且只能输出 {required_days}。",
            )
        )

    lesson_info = normalized_plan.get("lesson_info") if isinstance(normalized_plan.get("lesson_info"), dict) else {}
    topic = _clean_text(lesson_info.get("topic"))
    full_review_topics = normalized_plan.get("full_review_topics") if isinstance(normalized_plan.get("full_review_topics"), list) else []
    if topic in GENERIC_TOPICS:
        issues.append(
            QualityIssue(
                severity="high",
                category="pdf_readiness",
                description="lesson_info.topic 为空或退回通用“课后”，PDF 会生成空壳标题。",
                suggested_fix="把用户主题或 lesson_topic 映射为 lesson_info.topic。",
            )
        )
    granular_topics = [
        _clean_text(item)
        for item in full_review_topics
        if not _is_generic_coverage_topic(item, topic)
    ]
    if not granular_topics:
        issues.append(
            QualityIssue(
                severity="high",
                category="pdf_readiness",
                description="全课覆盖清单为空、只有通用词，或只重复课题名，首页会缺少真实复习范围。",
                suggested_fix="把 full_review_topics 拆成 5-10 个可复习知识点、方法链或错因，例如定义域限制、同一函数辨析、函数不等式同解转化。",
            )
        )
    elif len(granular_topics) < 3:
        issues.append(
            QualityIssue(
                severity="high",
                category="pdf_readiness",
                description=f"全课覆盖清单只有 {len(granular_topics)} 个颗粒化条目，容易退化成空壳复习范围。",
                suggested_fix="至少补到 5-10 个颗粒化条目；宽主题不能只写课题名或一两个大类。",
            )
        )

    quotes = _collect_quotes(normalized_plan)
    bad_quotes = [quote for quote in quotes if _quote_is_bad(quote)]
    if bad_quotes:
        issues.append(
            QualityIssue(
                severity="high",
                category="factuality",
                description="课堂金句/课堂原话中混入使用说明、完成标准或系统兜底文本。",
                suggested_fix="只保留课堂文本中老师真实强调过的方法句；没有证据时 quotes 留空，不能把“每一个复习日…”或正确率标准当金句。",
            )
        )

    for day in days:
        if not isinstance(day, dict):
            continue
        blanks_count, choices_count, bodies_count = _day_renderable_counts(day)
        if blanks_count == 0 and choices_count == 0:
            issues.append(
                QualityIssue(
                    severity="high",
                    category="pdf_readiness",
                    description=f"第 {day.get('day')} 天没有可渲染填空题或选择题，PDF 会退回兜底题目。",
                    suggested_fix="从 components、steps 或 blanks/choices 中补齐可打印题目。",
                )
            )
        if bodies_count <= 1 and blanks_count <= 1 and choices_count <= 1:
            issues.append(
                QualityIssue(
                    severity="medium",
                    category="task_actionability",
                    description=f"第 {day.get('day')} 天内容密度过低，接近空壳复习页。",
                    suggested_fix="补充执行清单、具体填空、选择诊断和主动回忆卡片。",
                )
            )
        unique_fills, unique_choices, raw_fills = _collect_day_unique_question_counts(day)
        if subject_key == "math" and unique_fills < 3 and unique_choices < 2:
            issues.append(
                QualityIssue(
                    severity="high",
                    category="task_actionability",
                    description=f"第 {day.get('day')} 天唯一可打印题目不足，容易生成半页空白的低密度 PDF。",
                    suggested_fix="每个复习日至少提供 3 个不重复填空/口述填空，或 2 道不同选择诊断题；不要只靠重复 items 凑数量。",
                )
            )
        if raw_fills >= 3 and unique_fills <= 1:
            issues.append(
                QualityIssue(
                    severity="high",
                    category="question_quality",
                    description=f"第 {day.get('day')} 天存在重复填空题凑数，唯一可打印题目不足。",
                    suggested_fix="删除重复题，改写为不同知识点、不同数字条件或不同错因的题目。",
                )
            )
        for blank in day.get("blanks", []) if isinstance(day.get("blanks"), list) else []:
            if isinstance(blank, dict) and _clean_text(blank.get("answer")) in BAD_BLANK_ANSWERS:
                issues.append(
                    QualityIssue(
                        severity="medium",
                        category="question_quality",
                        description=f"第 {day.get('day')} 天存在抽象设空答案：{blank.get('answer')}",
                        suggested_fix="把设空答案改为具体数值、符号、定义域端点、公式对象或条件。",
                    )
                )
        for choice in day.get("choices", []) if isinstance(day.get("choices"), list) else []:
            if isinstance(choice, dict) and not _choice_answer_is_valid(choice):
                issues.append(
                    QualityIssue(
                        severity="high",
                        category="question_quality",
                        description=f"第 {day.get('day')} 天选择题答案不在选项中或题目不完整。",
                        suggested_fix="确保 answer 为 A/B/C/D 且对应选项存在。",
                    )
                )
            if isinstance(choice, dict) and not _choice_options_are_complete(choice):
                issues.append(
                    QualityIssue(
                        severity="high",
                        category="question_quality",
                        description=f"第 {day.get('day')} 天选择题选项是空壳或少于 4 个完整选项。",
                        suggested_fix="把每道选择题改成 4 个完整选项字符串，例如 A. 具体表达；禁止只输出 A/B/C/D。",
                    )
                )

    if schedule_mode == "compressed" and len(required_days) == 1 and days:
        unique_fills, unique_choices, _raw_fills = _collect_day_unique_question_counts(days[0])
        if unique_fills + unique_choices < 5:
            issues.append(
                QualityIssue(
                    severity="high",
                    category="task_actionability",
                    description="压缩 1 天计划的可打印题目密度不足，无法承载整节课复习。",
                    suggested_fix="压缩 1 天时至少提供 5 个不重复的可打印填空/选择/口述任务，并覆盖主要错因。",
                )
            )

    plan_strings = _iter_strings(normalized_plan)
    bad_math_strings = [text for text in plan_strings if _has_bad_math_transport(text)]
    if bad_math_strings:
        issues.append(
            QualityIssue(
                severity="high",
                category="question_quality",
                description="数学公式文本出现 LaTeX 传输损坏或不可打印控制片段。",
                suggested_fix="把分式、根式、对数、分段函数等改成 `$...$` 包裹的 LaTeX；JSON 中反斜杠要转义，禁止 begincases/endcases/sqrt[/log_( 这类坏文本。",
            )
        )

    text_blob = str(normalized_plan)
    if _contains_any(text_blob, (*PLACEHOLDER_PATTERNS, "正确答案")):
        issues.append(
            QualityIssue(
                severity="high",
                category="style",
                description="输出中出现模板占位或元描述。",
                suggested_fix="替换为可直接印刷给学生的具体题干。",
            )
        )
    if _contains_any(text_blob, MODEL_SELF_CORRECTION_PATTERNS):
        issues.append(
            QualityIssue(
                severity="high",
                category="question_quality",
                description="输出中出现模型自我纠错痕迹，说明题目或答案尚未定稿。",
                suggested_fix="重写相关题目，确保题干、选项、答案和解析一致。",
            )
        )
    if _contains_any(text_blob, VAGUE_STEM_PATTERNS):
        issues.append(
            QualityIssue(
                severity="medium",
                category="question_quality",
                description="输出中存在“某题/这个题/原题中”等无法独立作答的模糊指代。",
                suggested_fix="补足题干条件，或改写成同知识点同错因的自洽同类题。",
            )
        )

    if subject_key == "physics" and not _contains_any(text_blob, ("公式", "单位", "实验", "图像", "适用条件")):
        issues.append(
            QualityIssue(
                severity="medium",
                category="subject_fit",
                description="物理复习计划缺少公式、单位、实验或图像解释维度。",
                suggested_fix="补充公式适用条件、单位检查、实验/图像任务。",
            )
        )
    if subject_key == "ielts" and not _contains_any(text_blob.lower(), ("reading", "listening", "writing", "speaking", "同义替换", "题型")):
        issues.append(
            QualityIssue(
                severity="medium",
                category="subject_fit",
                description="雅思复习计划缺少题型流程或四项技能/阅读策略维度。",
                suggested_fix="补充题型定位、错因分类、feedback loop。",
            )
        )
    if subject_key == "math" and not _contains_any(text_blob, ("错因", "题型", "步骤", "公式", "模型", "定义域")):
        issues.append(
            QualityIssue(
                severity="medium",
                category="subject_fit",
                description="数学复习计划缺少题型、步骤、错因或模型维度。",
                suggested_fix="补充题型入口、解题步骤和错题归因。",
            )
        )

    score = max(0, 100 - sum(25 if item.severity == "high" else 12 if item.severity == "medium" else 5 for item in issues))
    must_revise = score < 85 or any(item.severity == "high" for item in issues)
    return QualityReview(
        score=score,
        passed=not must_revise,
        issues=issues,
        must_revise=must_revise,
        revision_instructions=[item.suggested_fix for item in issues if item.suggested_fix],
    )
