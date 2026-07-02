from __future__ import annotations

from typing import Any, Optional, Tuple, Union

from config_runtime import (
    get_runtime_config,
    normalize_chat_provider,
    resolve_review_plan_model,
    resolve_review_plan_provider,
    resolve_review_plan_reasoning_effort,
)

from .executor import run_workflow_node
from .evaluator import build_review_plan_evaluation
from .generation_options import normalize_generation_options
from .nodes import (
    intake_normalizer_node,
    parent_planner_node,
    plan_generator_node,
    prompt_bundle_builder_node,
    question_repair_node,
    quality_reviewer_llm_node,
    revision_node,
    scope_planner_node,
    source_analyzer_node,
    source_brief_builder_node,
    subject_router_node,
    task_blueprint_node,
    time_allocator_node,
)
from .quality_gate import review_single_lesson_plan
from .quality_policy import (
    can_soft_pass_after_revision,
    max_revision_attempts_for_quality,
    should_run_llm_quality_review,
    soften_quality_after_revision,
    soft_pass_warning_for_quality,
)
from .printable_questions import collect_day_printable_question_counts
from .nodes.question_repair import can_repair_questions
from .llm.client import merge_usage
from .observability import (
    build_workflow_runtime_summary,
    flush,
    record_quality_score,
    record_workflow_failure,
    record_workflow_result,
    workflow_trace,
)
from .schemas import (
    AgenticPlanBlueprint,
    LessonSourcePack,
    QualityIssue,
    QualityReview,
    ReviewPlanInput,
    ReviewPlanSourceBrief,
    normalize_final_review_plan,
)
from .state import WorkflowContext
from .validator import ReviewPlanValidationResult, validate_review_plan_delivery


def _record_run(
    *,
    lesson_id: int,
    version_id: int = 0,
    organization_id: int,
    context: WorkflowContext,
    status: str,
    quality_review: Optional[dict[str, Any]] = None,
) -> None:
    if not lesson_id or not organization_id:
        return
    try:
        from lesson_manager import save_review_plan_run

        save_review_plan_run(
            lesson_id=lesson_id,
            version_id=version_id,
            organization_id=organization_id,
            trace_id=context.trace_id,
            status=status,
            subject=context.subject,
            provider=context.provider,
            model=context.model,
            prompt_version=context.prompt_version,
            style_version=context.style_version,
            schema_version=context.schema_version,
            warnings=context.warnings_as_dicts(),
            quality_review=quality_review or {},
            node_outputs=context.node_outputs,
            logs=context.logs_as_dicts(),
        )
    except Exception:
        # Trace storage must never make the existing generation path fail.
        return


def _score_quality(
    plan: dict[str, Any],
    *,
    subject: str,
    review_input: ReviewPlanInput,
    context: WorkflowContext,
    node_key: str,
) -> QualityReview:
    quality = review_single_lesson_plan(
        plan,
        subject=subject,
        required_review_days=review_input.review_days,
        schedule_mode=review_input.schedule_mode,
        constraints=review_input.constraints,
    )
    context.node_outputs[node_key] = quality.model_dump()
    context.node_outputs["quality_reviewer"] = quality.model_dump()
    return quality


def _validate_delivery(
    plan: dict[str, Any],
    *,
    review_input: ReviewPlanInput,
    context: WorkflowContext,
    node_key: str,
) -> ReviewPlanValidationResult:
    validation = validate_review_plan_delivery(
        plan,
        required_review_days=review_input.review_days,
        constraints=review_input.constraints,
        source_pack=review_input.source_pack,
    )
    context.node_outputs[node_key] = validation.model_dump()
    context.node_outputs["review_plan_validator"] = validation.model_dump()
    return validation


def _fallback_agent_blueprint(
    *,
    review_input: ReviewPlanInput,
    subject: str,
    source: Any,
    task_blueprint: Any,
) -> AgenticPlanBlueprint:
    confirmed_topics = getattr(source, "confirmed_topics", []) or []
    required_components = getattr(task_blueprint, "required_components", []) or []
    if not required_components and str(subject or "").lower() == "math":
        required_components = [
            "worked_example",
            "targeted_practice",
            "error_log",
            "timed_practice",
            "spiral_review",
            "checkpoint_quiz",
        ]
    compressed_single_day = review_input.schedule_mode == "compressed" and review_input.review_days == [1]
    writer_instructions = [
        "每一天必须绑定本节课主题和学生薄弱点，不能输出模板化任务。",
        "题目必须自洽可作答；课堂原题信息不足时改成同知识点同错因的同类题。",
        "严格保留本次输入指定的 review_days 结构。",
        "每个复习日直接输出可打印 blanks 与 choices；不要只输出执行说明或 checklist。",
        "填空题答案必须是具体数值、符号、条件、公式对象或方法名，不能留空。",
    ]
    if compressed_single_day:
        writer_instructions.extend(
            [
                "当前是当天课后复习模式：只输出 day=1，把本节课内容压缩成当天可完成的复习。",
                "当天课后复习必须包含 worked_example、targeted_practice、error_log、timed_practice/checkpoint_quiz、spiral_review 对应内容。",
                "spiral_review 只做本课内部交叉回收：把本节课 2-3 个关键点混在一起隔题复现，不要写成长期第7天/第30天安排。",
                "当天课后复习至少提供 5 个不重复的可打印题目，其中填空不少于 3 个，选择诊断不少于 2 个。",
            ]
        )
    return AgenticPlanBlueprint(
        strategy_summary=(
            "父模型蓝图不可用，退回本地规则：围绕课堂主题、薄弱点和固定间隔复习日生成。"
        ),
        student_diagnosis=[
            item
            for item in (
                str(review_input.weak_points or "").strip(),
                f"主题：{review_input.topic}" if review_input.topic else "",
            )
            if item
        ],
        knowledge_map=[
            {"name": str(topic), "role": "课堂确认复习范围", "evidence": "source_analyzer"}
            for topic in confirmed_topics[:6]
            if str(topic or "").strip()
        ],
        writer_instructions=writer_instructions,
        quality_risks=[
            "父模型蓝图缺失时，writer 更容易泛化或机械重复。",
            "必须特别检查题目是否只是结构完整但没有学科诊断价值。",
        ],
        success_criteria=[
            "每天有可打印填空、完整选择题、主动回忆和完成标准。",
            "复习任务能对应课堂主题、错因和薄弱点。",
            *[f"包含组件：{component}" for component in required_components[:7]],
        ],
        assumptions=["parent_planner_failed_or_disabled"],
        confidence=0.45,
    )


def _is_compressed_single_day(review_input: ReviewPlanInput) -> bool:
    return review_input.schedule_mode == "compressed" and list(review_input.review_days or []) == [1]


def _has_spiral_review(day: dict[str, Any]) -> bool:
    value = day.get("spiral_review")
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return any(str(item or "").strip() for item in value)
    if isinstance(value, dict):
        return any(str(item or "").strip() for item in value.values())
    return False


def _ensure_single_day_spiral_review(plan: dict[str, Any], review_input: ReviewPlanInput) -> None:
    if not _is_compressed_single_day(review_input):
        return
    days = plan.get("days") if isinstance(plan.get("days"), list) else []
    if len(days) != 1 or not isinstance(days[0], dict) or _has_spiral_review(days[0]):
        return
    day = days[0]
    counts = collect_day_printable_question_counts(day)
    if counts.visible_question_count < 5:
        return

    lesson_info = plan.get("lesson_info") if isinstance(plan.get("lesson_info"), dict) else {}
    topic_candidates = []
    for source in (
        plan.get("full_review_topics"),
        lesson_info.get("key_categories") if isinstance(lesson_info, dict) else None,
    ):
        if isinstance(source, list):
            topic_candidates.extend(str(item).strip() for item in source if str(item or "").strip())
    topic = str(lesson_info.get("topic") or review_input.topic or "本课内容").strip() if isinstance(lesson_info, dict) else "本课内容"
    if not topic_candidates and topic:
        topic_candidates.append(topic)
    focus_text = "、".join(topic_candidates[:3]) or topic or "本课关键点"

    day["spiral_review"] = [
        f"交叉回收：把{focus_text}混在同一轮练习中检查，做题时标出每题对应的知识点。",
        "隔题复现：每完成 2 道题，用一句话复述本题用到的公式、条件或错因。",
    ]


def _has_runtime_key_for_provider(provider: str) -> bool:
    cfg = get_runtime_config()
    provider_name = normalize_chat_provider(provider)
    if provider_name == "deepseek":
        return bool(str(cfg.get("deepseek_api_key") or "").strip())
    return bool(str(cfg.get("openai_api_key") or "").strip())


def _run_parent_planner_with_fallback(
    *,
    review_input: ReviewPlanInput,
    normalized: Any,
    route: Any,
    source: Any,
    scope: Any,
    time_allocation: Any,
    task_blueprint: Any,
    source_brief: ReviewPlanSourceBrief | None = None,
    context: WorkflowContext,
) -> tuple[AgenticPlanBlueprint, dict[str, Any]]:
    if not _has_runtime_key_for_provider(context.provider):
        fallback = _fallback_agent_blueprint(
            review_input=review_input,
            subject=getattr(route, "selected_subject", ""),
            source=source,
            task_blueprint=task_blueprint,
        )
        context.node_outputs["parent_planner"] = fallback.model_dump()
        context.node_outputs["parent_planner_skipped"] = {
            "reason": "missing_runtime_key_for_direct_service_call",
            "provider": context.provider,
        }
        return fallback, {}
    try:
        return run_workflow_node(
            parent_planner_node,
            {
                "input": review_input,
                "normalized": normalized,
                "route": route,
                "source": source,
                "scope": scope,
                "time_allocation": time_allocation,
                "task_blueprint": task_blueprint,
                "source_brief": source_brief,
            },
            context,
        )
    except Exception as exc:
        context.add_warning(
            "parent_planner_failed",
            f"父模型蓝图生成失败，已退回本地规则蓝图继续生成：{exc}",
            "medium",
        )
        fallback = _fallback_agent_blueprint(
            review_input=review_input,
            subject=getattr(route, "selected_subject", ""),
            source=source,
            task_blueprint=task_blueprint,
        )
        context.node_outputs["parent_planner"] = fallback.model_dump()
        return fallback, {}


def _dedupe_quality_issues(*issue_groups: list[QualityIssue]) -> list[QualityIssue]:
    seen: set[tuple[str, str, str]] = set()
    merged: list[QualityIssue] = []
    for issues in issue_groups:
        for issue in issues:
            key = (issue.severity, issue.category, issue.description)
            if key in seen:
                continue
            seen.add(key)
            merged.append(issue)
    return merged


def _merge_quality_reviews(local_quality: QualityReview, llm_quality: QualityReview | None) -> QualityReview:
    if llm_quality is None:
        return local_quality
    issues = _dedupe_quality_issues(local_quality.issues, llm_quality.issues)
    has_high_issue = any(issue.severity == "high" for issue in issues)
    score = min(max(0, int(local_quality.score or 0)), max(0, int(llm_quality.score or 0)))
    must_revise = bool(local_quality.must_revise or llm_quality.must_revise or score < 85 or has_high_issue)
    instructions: list[str] = []
    for value in [*local_quality.revision_instructions, *llm_quality.revision_instructions]:
        text = str(value or "").strip()
        if text and text not in instructions:
            instructions.append(text)
    return QualityReview(
        score=score,
        passed=bool(local_quality.passed and llm_quality.passed) and not must_revise,
        issues=issues,
        must_revise=must_revise,
        revision_instructions=instructions,
    )


def _review_with_llm_quality_gate(
    *,
    plan: dict[str, Any],
    local_quality: QualityReview,
    review_input: ReviewPlanInput,
    prompt_bundle: Any,
    agent_blueprint: AgenticPlanBlueprint,
    source_brief: ReviewPlanSourceBrief | None = None,
    validation: ReviewPlanValidationResult | None = None,
    context: WorkflowContext,
    node_key: str,
) -> tuple[QualityReview, dict[str, Any]]:
    validator_passed = validation.passed if validation is not None else True
    if not should_run_llm_quality_review(
        local_quality=local_quality,
        source_brief=source_brief,
        validator_passed=validator_passed,
    ):
        skipped = {
            "mode": "skipped",
            "reason": "validator_blocked_llm_review" if not validator_passed else "local_quality_passed_with_high_source_confidence",
            "score": local_quality.score,
            "source_confidence": source_brief.confidence if source_brief is not None else None,
            "validator_passed": validator_passed,
        }
        context.node_outputs[node_key] = skipped
        context.node_outputs["quality_reviewer_llm_skipped"] = skipped
        context.node_outputs["quality_reviewer"] = local_quality.model_dump()
        context.node_outputs["review_plan_evaluator"] = build_review_plan_evaluation(
            local_quality=local_quality,
            validator_result=validation,
        ).model_dump()
        return local_quality, {}

    if not _has_runtime_key_for_provider(context.provider):
        context.node_outputs["quality_reviewer_llm_skipped"] = {
            "reason": "missing_runtime_key_for_direct_service_call",
            "provider": context.provider,
        }
        context.node_outputs[node_key] = local_quality.model_dump()
        context.node_outputs["quality_reviewer"] = local_quality.model_dump()
        context.node_outputs["review_plan_evaluator"] = build_review_plan_evaluation(
            local_quality=local_quality,
            validator_result=validation,
        ).model_dump()
        return local_quality, {}
    try:
        llm_quality, usage = run_workflow_node(
            quality_reviewer_llm_node,
            {
                "plan": plan,
                "local_quality": local_quality,
                "review_input": review_input,
                "prompt_bundle": prompt_bundle,
                "agent_blueprint": agent_blueprint,
                "source_brief": source_brief,
            },
            context,
        )
    except Exception as exc:
        context.add_warning(
            "quality_reviewer_llm_failed",
            f"LLM 审稿失败，已仅使用本地质量门禁：{exc}",
            "medium",
        )
        context.node_outputs[node_key] = local_quality.model_dump()
        context.node_outputs["quality_reviewer"] = local_quality.model_dump()
        context.node_outputs["review_plan_evaluator"] = build_review_plan_evaluation(
            local_quality=local_quality,
            validator_result=validation,
        ).model_dump()
        return local_quality, {}

    merged = _merge_quality_reviews(local_quality, llm_quality)
    context.node_outputs[node_key] = merged.model_dump()
    context.node_outputs["quality_reviewer"] = merged.model_dump()
    context.node_outputs["review_plan_evaluator"] = build_review_plan_evaluation(
        local_quality=local_quality,
        validator_result=validation,
        llm_quality=llm_quality,
    ).model_dump()
    return merged, usage


def _assumption_mentions_trusted_metadata(value: object) -> bool:
    text = str(value or "")
    if not text:
        return False
    return any(marker in text for marker in ("年级", "科目", "上课日期", "复习日", "review_days")) and any(
        marker in text for marker in ("用户输入", "学生用户输入", "课堂材料", "转录", "可核验")
    )


def _sanitize_unsupported_teacher_claim_text(value: str) -> str:
    replacements = (
        ("老师在课堂上强调的", "本课需要掌握的"),
        ("课堂上老师强调的", "本课需要掌握的"),
        ("课堂中老师强调的", "本课需要掌握的"),
        ("老师特别强调的", "本课需要掌握的"),
        ("老师强调的", "本课需要掌握的"),
        ("老师在课堂上强调", "本课需要掌握"),
        ("课堂上老师强调", "本课需要掌握"),
        ("课堂中老师强调", "本课需要掌握"),
        ("老师特别强调", "本课需要掌握"),
        ("老师强调", "本课需要掌握"),
        ("老师说的", "本课提到的"),
        ("老师说", "本课提到"),
        ("老师要求的", "本次需要完成的"),
        ("老师要求", "本次需要完成"),
        ("老师提醒的", "本课需要注意的"),
        ("老师提醒", "本课需要注意"),
        ("课堂原话回放：", "复习要点："),
        ("课堂原话回放:", "复习要点："),
        ("课堂原话：", "复习要点："),
        ("课堂原话:", "复习要点："),
        ("老师原话：", "复习要点："),
        ("老师原话:", "复习要点："),
    )
    text = value
    for old, new in replacements:
        text = text.replace(old, new)
    return text


def _remove_unsupported_teacher_claims(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            if key == "quotes" and isinstance(item, list):
                cleaned[key] = []
            else:
                cleaned[key] = _remove_unsupported_teacher_claims(item)
        return cleaned
    if isinstance(value, list):
        return [_remove_unsupported_teacher_claims(item) for item in value]
    if isinstance(value, str):
        return _sanitize_unsupported_teacher_claim_text(value)
    return value


def _normalize_output_plan(
    plan: dict[str, Any],
    review_input: ReviewPlanInput,
    source_brief: ReviewPlanSourceBrief | None = None,
) -> dict[str, Any]:
    normalized = normalize_final_review_plan(plan)
    lesson_info = normalized.setdefault("lesson_info", {})
    if not isinstance(lesson_info, dict):
        lesson_info = {}
        normalized["lesson_info"] = lesson_info
    if review_input.subject:
        lesson_info["subject"] = review_input.subject
    if review_input.grade:
        lesson_info["grade"] = review_input.grade
    if review_input.lesson_date:
        lesson_info["date"] = review_input.lesson_date
    if isinstance(lesson_info.get("assumptions"), list):
        lesson_info["assumptions"] = [
            item for item in lesson_info["assumptions"] if not _assumption_mentions_trusted_metadata(item)
        ]
    if source_brief is not None and not source_brief.teacher_emphasis:
        normalized = _remove_unsupported_teacher_claims(normalized)
        lesson_info = normalized.setdefault("lesson_info", {})
        if not isinstance(lesson_info, dict):
            lesson_info = {}
            normalized["lesson_info"] = lesson_info
    _ensure_single_day_spiral_review(normalized, review_input)
    return normalized


def _maybe_revise_plan(
    *,
    plan: dict[str, Any],
    quality: QualityReview,
    usage: dict[str, Any],
    review_input: ReviewPlanInput,
    prompt_bundle: Any,
    agent_blueprint: AgenticPlanBlueprint,
    source_brief: ReviewPlanSourceBrief | None = None,
    subject: str,
    context: WorkflowContext,
) -> tuple[dict[str, Any], QualityReview, dict[str, Any]]:
    if not quality.must_revise:
        return plan, quality, usage

    best_plan = plan
    best_quality = quality
    current_plan = plan
    current_quality = quality
    total_usage = usage
    max_attempts = max_revision_attempts_for_quality(quality=quality, source_brief=source_brief)
    if max_attempts <= 0:
        return plan, quality, usage
    question_repair_attempts_before = len(context.node_outputs.get("question_repair_attempts") or [])

    for attempt in range(1, max_attempts + 1):
        try:
            revision_input = {
                "input": review_input,
                "prompt_bundle": prompt_bundle,
                "plan": current_plan,
                "quality": current_quality,
                "attempt": attempt,
                "agent_blueprint": agent_blueprint,
                "source_brief": source_brief,
            }
            if can_repair_questions(current_plan, current_quality):
                try:
                    revised_plan, revision_usage = run_workflow_node(
                        question_repair_node,
                        revision_input,
                        context,
                    )
                except Exception as exc:
                    context.add_warning(
                        "question_repair_fallback",
                        f"第 {attempt} 次题目级修复失败，已改用完整修订：{exc}",
                        "medium",
                    )
                    revised_plan, revision_usage = run_workflow_node(
                        revision_node,
                        revision_input,
                        context,
                    )
            else:
                revised_plan, revision_usage = run_workflow_node(
                    revision_node,
                    revision_input,
                    context,
                )
        except Exception as exc:
            context.add_warning(
                "quality_revision_failed",
                f"第 {attempt} 次质量修订失败，已返回当前最优结果：{exc}",
                "high",
            )
            break

        total_usage = merge_usage(total_usage, revision_usage)
        current_plan = _normalize_output_plan(revised_plan, review_input, source_brief)
        current_validation = _validate_delivery(
            current_plan,
            review_input=review_input,
            context=context,
            node_key=f"review_plan_validator_after_revision_{attempt}",
        )
        local_quality = _score_quality(
            current_plan,
            subject=subject,
            review_input=review_input,
            context=context,
            node_key=f"quality_reviewer_rules_after_revision_{attempt}",
        )
        current_quality, reviewer_usage = _review_with_llm_quality_gate(
            plan=current_plan,
            local_quality=local_quality,
            review_input=review_input,
            prompt_bundle=prompt_bundle,
            agent_blueprint=agent_blueprint,
            source_brief=source_brief,
            validation=current_validation,
            context=context,
            node_key=f"quality_reviewer_after_revision_{attempt}",
        )
        total_usage = merge_usage(total_usage, reviewer_usage)
        if current_quality.score >= best_quality.score:
            best_plan = current_plan
            best_quality = current_quality
        if not current_quality.must_revise:
            return current_plan, current_quality, total_usage

    question_repair_attempts_after = len(context.node_outputs.get("question_repair_attempts") or [])
    if (
        best_quality.must_revise
        and question_repair_attempts_after == question_repair_attempts_before
        and can_repair_questions(best_plan, best_quality)
    ):
        attempt = max_attempts + 1
        try:
            repaired_plan, repair_usage = run_workflow_node(
                question_repair_node,
                {
                    "input": review_input,
                    "prompt_bundle": prompt_bundle,
                    "plan": best_plan,
                    "quality": best_quality,
                    "attempt": attempt,
                    "agent_blueprint": agent_blueprint,
                    "source_brief": source_brief,
                },
                context,
            )
            total_usage = merge_usage(total_usage, repair_usage)
            repaired_plan = _normalize_output_plan(repaired_plan, review_input, source_brief)
            repaired_validation = _validate_delivery(
                repaired_plan,
                review_input=review_input,
                context=context,
                node_key=f"review_plan_validator_after_question_repair_{attempt}",
            )
            repaired_local_quality = _score_quality(
                repaired_plan,
                subject=subject,
                review_input=review_input,
                context=context,
                node_key=f"quality_reviewer_rules_after_question_repair_{attempt}",
            )
            repaired_quality, reviewer_usage = _review_with_llm_quality_gate(
                plan=repaired_plan,
                local_quality=repaired_local_quality,
                review_input=review_input,
                prompt_bundle=prompt_bundle,
                agent_blueprint=agent_blueprint,
                source_brief=source_brief,
                validation=repaired_validation,
                context=context,
                node_key=f"quality_reviewer_after_question_repair_{attempt}",
            )
            total_usage = merge_usage(total_usage, reviewer_usage)
            if repaired_quality.score >= best_quality.score:
                best_plan = repaired_plan
                best_quality = repaired_quality
            if not repaired_quality.must_revise:
                return repaired_plan, repaired_quality, total_usage
        except Exception as exc:
            context.add_warning(
                "question_repair_after_revision_failed",
                f"完整修订后剩余题目级问题，但定点修复失败：{exc}",
                "high",
            )

    if best_quality.must_revise and can_soft_pass_after_revision(best_quality):
        softened_quality = soften_quality_after_revision(best_quality)
        warning_code, warning_message = soft_pass_warning_for_quality(best_quality)
        context.add_warning(
            warning_code,
            warning_message,
            "medium",
        )
        return best_plan, softened_quality, total_usage

    if best_quality.must_revise:
        context.add_warning(
            "quality_revision_required",
            f"质量门禁在 {max_attempts} 次 revision 后仍建议人工复核；已返回当前最高分版本。",
            "high",
        )
    return best_plan, best_quality, total_usage


def generate_single_lesson_review_plan(
    *,
    summary_text: str,
    subject: str = "",
    grade: str = "",
    topic: str = "",
    weak_points: str = "",
    lesson_date: str = "",
    provider: str = "",
    model: str = "",
    lesson_id: int = 0,
    version_id: int = 0,
    organization_id: int = 0,
    generation_options: object | None = None,
    source_pack: object | None = None,
    include_usage: bool = False,
) -> Union[dict[str, Any], Tuple[dict[str, Any], dict[str, Any]]]:
    resolved_provider = provider or resolve_review_plan_provider()
    resolved_model = model or resolve_review_plan_model(provider=resolved_provider)
    options = normalize_generation_options(generation_options)
    context = WorkflowContext(
        provider=resolved_provider,
        model=resolved_model,
        reasoning_effort=resolve_review_plan_reasoning_effort(provider=resolved_provider),
    )
    review_input = ReviewPlanInput(
        summary_text=summary_text,
        subject=subject,
        grade=grade,
        topic=topic,
        weak_points=weak_points,
        lesson_date=lesson_date,
        schedule_mode=str(options["schedule_mode"]),
        review_days=list(options["review_days"]),
        daily_count=options.get("daily_count") if isinstance(options.get("daily_count"), int) else None,
        user_requirements=str(options.get("user_requirements") or ""),
        constraints=options.get("constraints") if isinstance(options.get("constraints"), dict) else {},
        source_pack=LessonSourcePack.model_validate(source_pack) if source_pack else None,
    )
    _record_run(lesson_id=lesson_id, version_id=version_id, organization_id=organization_id, context=context, status="running")

    try:
        with workflow_trace(
            context=context,
            review_input=review_input,
            lesson_id=lesson_id,
            organization_id=organization_id,
        ):
            normalized = run_workflow_node(intake_normalizer_node, review_input, context)
            source_brief = run_workflow_node(
                source_brief_builder_node,
                {"input": review_input, "normalized": normalized},
                context,
            )
            route = run_workflow_node(subject_router_node, normalized, context)
            source = run_workflow_node(
                source_analyzer_node,
                {"normalized": normalized, "source_brief": source_brief},
                context,
            )
            scope = run_workflow_node(
                scope_planner_node,
                {
                    "input": review_input,
                    "normalized": normalized,
                    "route": route,
                    "source": source,
                    "source_brief": source_brief,
                },
                context,
            )
            time_allocation = run_workflow_node(
                time_allocator_node,
                {"normalized": normalized, "scope": scope},
                context,
            )
            task_blueprint = run_workflow_node(
                task_blueprint_node,
                {
                    "normalized": normalized,
                    "route": route,
                    "source": source,
                    "source_brief": source_brief,
                    "scope": scope,
                    "time_allocation": time_allocation,
                },
                context,
            )
            agent_blueprint, planner_usage = _run_parent_planner_with_fallback(
                review_input=review_input,
                normalized=normalized,
                route=route,
                source=source,
                scope=scope,
                time_allocation=time_allocation,
                task_blueprint=task_blueprint,
                source_brief=source_brief,
                context=context,
            )
            prompt_bundle = run_workflow_node(
                prompt_bundle_builder_node,
                {
                    "input": review_input,
                    "route": route,
                    "source": source,
                    "scope": scope,
                    "time_allocation": time_allocation,
                    "task_blueprint": task_blueprint,
                    "agent_blueprint": agent_blueprint,
                    "source_brief": source_brief,
                },
                context,
            )
            plan, usage = run_workflow_node(
                plan_generator_node,
                {
                    "input": review_input,
                    "normalized": normalized,
                    "route": route,
                    "source": source,
                    "scope": scope,
                    "time_allocation": time_allocation,
                    "task_blueprint": task_blueprint,
                    "prompt_bundle": prompt_bundle,
                    "agent_blueprint": agent_blueprint,
                    "source_brief": source_brief,
                },
                context,
            )
            plan = _normalize_output_plan(plan, review_input, source_brief)
            validation = _validate_delivery(
                plan,
                review_input=review_input,
                context=context,
                node_key="review_plan_validator_initial",
            )
            local_quality = _score_quality(
                plan,
                subject=route.selected_subject,
                review_input=review_input,
                context=context,
                node_key="quality_reviewer_rules_initial",
            )
            quality, reviewer_usage = _review_with_llm_quality_gate(
                plan=plan,
                local_quality=local_quality,
                review_input=review_input,
                prompt_bundle=prompt_bundle,
                agent_blueprint=agent_blueprint,
                source_brief=source_brief,
                validation=validation,
                context=context,
                node_key="quality_reviewer_initial",
            )
            usage = merge_usage(planner_usage, usage, reviewer_usage)
            plan, quality, usage = _maybe_revise_plan(
                plan=plan,
                quality=quality,
                usage=usage,
                review_input=review_input,
                prompt_bundle=prompt_bundle,
                agent_blueprint=agent_blueprint,
                source_brief=source_brief,
                subject=route.selected_subject,
                context=context,
            )
            plan = _normalize_output_plan(plan, review_input, source_brief)
            context.node_outputs["workflow_runtime"] = build_workflow_runtime_summary(
                context,
                usage=usage,
                review_input=review_input,
            )
            record_quality_score(context=context, quality=quality)
            record_workflow_result(context=context, plan=plan, quality=quality, usage=usage, status="succeeded")

            _record_run(
                lesson_id=lesson_id,
                version_id=version_id,
                organization_id=organization_id,
                context=context,
                status="succeeded",
                quality_review=quality.model_dump(),
            )
            if include_usage:
                return plan, usage
            return plan
    except Exception as exc:
        record_workflow_failure(context=context, error=exc)
        _record_run(lesson_id=lesson_id, version_id=version_id, organization_id=organization_id, context=context, status="failed")
        raise
    finally:
        flush()
