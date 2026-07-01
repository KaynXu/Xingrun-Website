from __future__ import annotations

import json
from datetime import date
from typing import Any

from config_runtime import (
    resolve_review_plan_repair_temperature,
    resolve_review_plan_writer_model,
    resolve_review_plan_writer_provider,
    resolve_review_plan_writer_temperature,
)
from review_plan_workflow.executor import WorkflowNode
from review_plan_workflow.llm.client import generate_review_plan_json, merge_usage
from review_plan_workflow.schemas import (
    AgenticPlanBlueprint,
    PromptBundle,
    ReviewPlanInput,
    normalize_final_review_plan,
    validate_final_review_plan,
)
from review_plan_workflow.state import WorkflowContext


def _user_message(
    review_input: ReviewPlanInput,
    prompt_bundle: PromptBundle,
    agent_blueprint: AgenticPlanBlueprint | None = None,
) -> str:
    meta_parts = [f"生成日期（第0天）：{date.today().isoformat()}"]
    if review_input.subject:
        meta_parts.append(f"科目：{review_input.subject}")
    if review_input.grade:
        meta_parts.append(f"年级：{review_input.grade}")
    if review_input.topic:
        meta_parts.append(f"本节课主题：{review_input.topic}")
    if review_input.weak_points:
        meta_parts.append(f"学生薄弱点：{review_input.weak_points}")
    if review_input.lesson_date:
        meta_parts.append(f"上课日期：{review_input.lesson_date}")
    meta_parts.append(f"生成节奏：{review_input.schedule_mode}；复习日必须且只能覆盖 {review_input.review_days}")
    if review_input.user_requirements:
        meta_parts.append(
            "老师本次生成要求（优先于默认偏好，但不得覆盖结构、事实、schema、PDF 和质量门禁硬规则）："
            + review_input.user_requirements
        )

    sections = [
        "\n".join(meta_parts),
        "已校验工作流上下文：\n" + str(prompt_bundle.variables),
    ]
    if agent_blueprint is not None:
        sections.append(
            "父模型教学蓝图（必须优先执行；如果课堂信息不足，只能把假设写进 assumptions，不能伪装成事实）：\n"
            + agent_blueprint.model_dump_json(indent=2)
        )
    sections.extend(
        [
            "课堂总结：\n" + review_input.summary_text,
            "硬性选择题契约：所有 choices 必须有完整 question、4 个完整 options 和 answer；options 不能只写 A/B/C/D，必须写成 A. 具体选项内容；answer 只能是 A/B/C/D。",
            f"硬性复习日契约：days 必须且只能覆盖 {review_input.review_days}；不得额外生成 1/2/7/14/30 中未被指定的日期。",
            "硬性覆盖清单契约：full_review_topics 必须是 5-10 条颗粒化知识点/方法链/错因；不能只写本节课标题，不能只写“本节课内容/综合复习”。",
            "硬性课堂金句契约：quotes 只保留课堂文本中老师真实强调过的方法句；没有证据就返回空数组，禁止把使用说明、完成标准、正确率要求或“每一个复习日都要完整复习整节课内容”写成金句。",
            "硬性数学公式契约：数学公式、分式、根式、对数、分段函数、区间和不等式链必须写成 `$...$` LaTeX；JSON 反斜杠要正确转义，禁止 begincases/endcases/sqrt[/log_( 等坏文本。",
            "请返回可直接进入现有 PDF 渲染链路的 JSON object，不要输出 Markdown 包裹。",
        ]
    )
    return "\n\n".join(sections)


def _apply_lesson_date(plan: dict[str, Any], review_input: ReviewPlanInput) -> dict[str, Any]:
    if review_input.lesson_date:
        plan.setdefault("lesson_info", {})["date"] = review_input.lesson_date
    else:
        plan.setdefault("lesson_info", {}).setdefault("date", str(date.today()))
    return plan


def _apply_lesson_metadata(plan: dict[str, Any], review_input: ReviewPlanInput) -> dict[str, Any]:
    lesson_info = plan.setdefault("lesson_info", {})
    if not isinstance(lesson_info, dict):
        lesson_info = {}
        plan["lesson_info"] = lesson_info
    if review_input.subject and not str(lesson_info.get("subject") or "").strip():
        lesson_info["subject"] = review_input.subject
    if review_input.grade and not str(lesson_info.get("grade") or "").strip():
        lesson_info["grade"] = review_input.grade
    if review_input.topic and not str(lesson_info.get("topic") or "").strip():
        lesson_info["topic"] = review_input.topic
    return plan


def _schema_errors(plan: dict[str, Any]) -> list[str]:
    _, errors = validate_final_review_plan(plan)
    return errors


def _normalize_plan(plan: dict[str, Any], review_input: ReviewPlanInput) -> dict[str, Any]:
    return _apply_lesson_metadata(
        _apply_lesson_date(normalize_final_review_plan(plan), review_input),
        review_input,
    )


def _repair_message(
    *,
    original_message: str,
    invalid_plan: dict[str, Any] | None,
    errors: list[str],
    review_input: ReviewPlanInput,
    parse_error: str = "",
) -> str:
    sections = [
        "上一轮复习计划 JSON 未通过结构检查。请只修复 JSON/schema 问题，不扩写未提供的信息。",
        "必须返回完整 JSON object，不要 Markdown，不要解释。",
        f"days 必须且只能覆盖 {review_input.review_days}；每个 day 必须有可打印的复习任务。",
        "所有 choices 必须包含完整 question、4 个完整 options 和 answer；禁止 options 只写 A/B/C/D。",
    ]
    if parse_error:
        sections.append("JSON 解析错误：\n" + parse_error)
    if errors:
        sections.append("Schema 错误：\n" + "\n".join(f"- {error}" for error in errors))
    if invalid_plan is not None:
        sections.append("上一轮已解析 JSON：\n" + json.dumps(invalid_plan, ensure_ascii=False, indent=2))
    sections.append("原始生成请求：\n" + original_message)
    return "\n\n".join(sections)


def _run(input_data: dict[str, Any], context: WorkflowContext) -> tuple[dict[str, Any], dict[str, Any]]:
    review_input: ReviewPlanInput = input_data["input"]
    prompt_bundle: PromptBundle = input_data["prompt_bundle"]
    agent_blueprint: AgenticPlanBlueprint | None = input_data.get("agent_blueprint")
    user_message = _user_message(review_input, prompt_bundle, agent_blueprint)
    attempts: list[dict[str, Any]] = []
    plan: dict[str, Any] | None = None
    usage: dict[str, Any] = {}
    parse_error = ""
    errors: list[str] = []
    writer_provider = resolve_review_plan_writer_provider()
    writer_model = resolve_review_plan_writer_model(provider=writer_provider)
    writer_temperature = resolve_review_plan_writer_temperature()
    repair_temperature = resolve_review_plan_repair_temperature()
    context.node_outputs["plan_generator_model_config"] = {
        "provider": writer_provider,
        "model": writer_model,
        "temperature": writer_temperature,
        "repair_temperature": repair_temperature,
    }

    try:
        plan, usage = generate_review_plan_json(
            system_prompt=prompt_bundle.prompt,
            user_message=user_message,
            provider=writer_provider,
            model=writer_model,
            temperature=writer_temperature,
            stage="plan_generator",
        )
        plan = _normalize_plan(plan, review_input)
        errors = _schema_errors(plan)
        attempts.append(
            {
                "attempt": 1,
                "stage": "generate",
                "provider": writer_provider,
                "model": writer_model,
                "schema_errors": errors,
            }
        )
    except ValueError as exc:
        parse_error = str(exc)
        attempts.append(
            {
                "attempt": 1,
                "stage": "generate",
                "provider": writer_provider,
                "model": writer_model,
                "error": parse_error,
            }
        )

    if parse_error or errors:
        try:
            repaired, repair_usage = generate_review_plan_json(
                system_prompt=prompt_bundle.prompt
                + "\n\n# Schema Repair\n只修复 JSON 和 schema 结构问题，保留已正确的教学内容。",
                user_message=_repair_message(
                    original_message=user_message,
                    invalid_plan=plan,
                    errors=errors,
                    review_input=review_input,
                    parse_error=parse_error,
                ),
                provider=writer_provider,
                model=writer_model,
                temperature=repair_temperature,
                stage="plan_generator_schema_repair",
            )
            plan = _normalize_plan(repaired, review_input)
            usage = merge_usage(usage, repair_usage)
            repair_errors = _schema_errors(plan)
            attempts.append(
                {
                    "attempt": 2,
                    "stage": "schema_repair",
                    "provider": writer_provider,
                    "model": writer_model,
                    "schema_errors": repair_errors,
                }
            )
        except Exception as exc:
            if plan is None:
                raise
            repair_errors = errors
            attempts.append(
                {
                    "attempt": 2,
                    "stage": "schema_repair",
                    "provider": writer_provider,
                    "model": writer_model,
                    "error": str(exc),
                }
            )
        if repair_errors:
            context.add_warning(
                "plan_generator_schema_repair_failed",
                "结构修复后仍未完全通过 schema，后续质量门禁将继续处理。",
                "high",
            )
        else:
            context.node_outputs["plan_generator_schema_repaired"] = True

    context.node_outputs["plan_generator_attempts"] = attempts
    if plan is None:
        raise ValueError("plan_generator did not produce a review plan")
    return plan, usage


plan_generator_node: WorkflowNode[dict[str, Any], tuple[dict[str, Any], dict[str, Any]]] = WorkflowNode(
    name="plan_generator",
    run=_run,
)
