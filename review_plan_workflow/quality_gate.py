from __future__ import annotations

from typing import Any

from .schemas import QualityIssue, QualityReview, normalize_final_review_plan, validate_final_review_plan


def _contains_any(text: str, candidates: tuple[str, ...]) -> bool:
    return any(candidate in text for candidate in candidates)


GENERIC_TOPICS = {"", "课后", "本课内容"}
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


def _clean_text(value: object) -> str:
    return str(value or "").strip()


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


def _choice_answer_is_valid(choice: dict[str, Any]) -> bool:
    answer = _clean_text(choice.get("answer"))
    options = choice.get("options") if isinstance(choice.get("options"), list) else []
    if not answer or not options:
        return False
    answer_head = answer[:1].upper()
    option_heads = {_clean_text(option)[:1].upper() for option in options if _clean_text(option)}
    return answer_head in option_heads


def review_single_lesson_plan(plan: dict[str, Any], *, subject: str = "") -> QualityReview:
    normalized_plan = normalize_final_review_plan(plan)
    issues: list[QualityIssue] = []
    _, schema_errors = validate_final_review_plan(normalized_plan)
    if schema_errors:
        issues.append(
            QualityIssue(
                severity="high",
                category="schema",
                description="复习计划结构未通过 schema 校验：" + "；".join(schema_errors[:3]),
                suggested_fix="补齐 lesson_info 与 1/2/7/14/30 复习日结构。",
            )
        )

    days = normalized_plan.get("days") if isinstance(normalized_plan.get("days"), list) else []
    day_numbers = {int(day.get("day") or 0) for day in days if isinstance(day, dict)}
    if {1, 2, 7, 14, 30} - day_numbers:
        issues.append(
            QualityIssue(
                severity="high",
                category="completeness",
                description="缺少固定 5 个复习日中的一个或多个。",
                suggested_fix="输出 day=1,2,7,14,30 的完整数组。",
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
    if not [item for item in full_review_topics if _clean_text(item) not in GENERIC_TOPICS]:
        issues.append(
            QualityIssue(
                severity="high",
                category="pdf_readiness",
                description="全课覆盖清单为空或只有通用“课后”，首页会缺少真实复习范围。",
                suggested_fix="补齐 full_review_topics 或 lesson_info.key_categories。",
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

    subject_key = subject.lower()
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
