from __future__ import annotations

from typing import Any

from .schemas import QualityIssue, QualityReview, validate_final_review_plan


def _contains_any(text: str, candidates: tuple[str, ...]) -> bool:
    return any(candidate in text for candidate in candidates)


def review_single_lesson_plan(plan: dict[str, Any], *, subject: str = "") -> QualityReview:
    issues: list[QualityIssue] = []
    _, schema_errors = validate_final_review_plan(plan)
    if schema_errors:
        issues.append(
            QualityIssue(
                severity="high",
                category="schema",
                description="复习计划结构未通过 schema 校验：" + "；".join(schema_errors[:3]),
                suggested_fix="补齐 lesson_info 与 1/2/7/14/30 复习日结构。",
            )
        )

    days = plan.get("days") if isinstance(plan.get("days"), list) else []
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

    text_blob = str(plan)
    if _contains_any(text_blob, ("（具体题目）", "按实际填写", "板块X", "正确答案")):
        issues.append(
            QualityIssue(
                severity="high",
                category="style",
                description="输出中出现模板占位或元描述。",
                suggested_fix="替换为可直接印刷给学生的具体题干。",
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
