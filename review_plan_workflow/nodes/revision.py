from __future__ import annotations

import json
from datetime import date
from typing import Any

from config_runtime import (
    resolve_review_plan_repair_temperature,
    resolve_review_plan_writer_model,
    resolve_review_plan_writer_provider,
)
from review_plan_workflow.executor import WorkflowNode
from review_plan_workflow.llm.client import generate_review_plan_json
from review_plan_workflow.llm.prompt_renderer import render_prompt
from review_plan_workflow.schemas import (
    AgenticPlanBlueprint,
    PromptBundle,
    QualityReview,
    ReviewPlanInput,
    ReviewPlanSourceBrief,
    normalize_final_review_plan,
)
from review_plan_workflow.source_brief import source_brief_trace_payload
from review_plan_workflow.state import WorkflowContext


def _source_brief_revision_section(
    prompt_bundle: PromptBundle,
    source_brief: ReviewPlanSourceBrief | None,
) -> str:
    safe_brief = prompt_bundle.variables.get("source_brief")
    if not isinstance(safe_brief, dict) and source_brief is not None:
        safe_brief = source_brief_trace_payload(source_brief)
    if not isinstance(safe_brief, dict) or not safe_brief:
        return ""
    return "结构化课堂材料：\n" + json.dumps(safe_brief, ensure_ascii=False, indent=2)


def _apply_lesson_date(plan: dict[str, Any], review_input: ReviewPlanInput) -> dict[str, Any]:
    if review_input.lesson_date:
        plan.setdefault("lesson_info", {})["date"] = review_input.lesson_date
    else:
        plan.setdefault("lesson_info", {}).setdefault("date", str(date.today()))
    return plan


def _revision_message(
    *,
    plan: dict[str, Any],
    quality: QualityReview,
    review_input: ReviewPlanInput,
    attempt: int,
    agent_blueprint: AgenticPlanBlueprint | None = None,
    prompt_bundle: PromptBundle | None = None,
    source_brief: ReviewPlanSourceBrief | None = None,
) -> str:
    sections = [
        f"Targeted revision attempt: {attempt}",
        "只修复 quality review 指出的问题；保留原计划中已经正确的结构和内容。",
        "不得虚构教材页码、考试日期、学生成绩、老师原话或未提供的题目来源。",
        "subject、grade、lesson_date、review_days 是页面/班级/工作流元数据，可以写入 lesson_info；不要把它们写成“课堂转录中可核验”或“学生用户输入”的假设。",
        "老师原话必须来自课堂材料、source_brief 或老师本次要求；没有 teacher_emphasis 证据时 quotes 留空。",
        "如果课堂材料缺 topic/knowledge_points，不要让计划失败；改成基于 subject/grade/user_requirements 的通用复习主题，标题和 topic 不要出现“待确认/需确认”，并在 assumptions 写清“课堂主题需老师确认”。",
        "弱素材修订目标：保留可打印题目、可执行清单和完整 days；把未经证实的具体知识点从“课堂事实”改成 assumptions 或通用练习范围，不要写进可见标题。",
        f"必须返回完整 JSON object，且 days 只包含 {review_input.review_days} 的复习节点。",
        "选择题硬修复：逐日检查 choices；任何 options 只写 A/B/C/D、少于 4 个完整选项或 answer 为空时，必须重写为完整 question + A-D 四个具体选项 + 单字母答案。",
    ]
    if review_input.user_requirements:
        sections.append(
            "老师本次生成要求（只能在结构、事实、schema、PDF 和质量门禁硬规则内执行）："
            + review_input.user_requirements
        )
    if agent_blueprint is not None:
        sections.append("父模型教学蓝图：\n" + agent_blueprint.model_dump_json(indent=2))
    if prompt_bundle is not None:
        source_section = _source_brief_revision_section(prompt_bundle, source_brief)
        if source_section:
            sections.append(source_section)
    sections.extend(
        [
            "质量问题：\n" + quality.model_dump_json(indent=2),
            "用户输入：\n"
            + json.dumps(
                {
                    "subject": review_input.subject,
                    "grade": review_input.grade,
                    "topic": review_input.topic,
                    "weak_points": review_input.weak_points,
                    "lesson_date": review_input.lesson_date,
                    "schedule_mode": review_input.schedule_mode,
                    "review_days": review_input.review_days,
                },
                ensure_ascii=False,
                indent=2,
            ),
            "当前计划 JSON：\n" + json.dumps(plan, ensure_ascii=False, indent=2),
        ]
    )
    return "\n\n".join(sections)


def _run(input_data: dict[str, Any], context: WorkflowContext) -> tuple[dict[str, Any], dict[str, Any]]:
    review_input: ReviewPlanInput = input_data["input"]
    prompt_bundle: PromptBundle = input_data["prompt_bundle"]
    quality: QualityReview = input_data["quality"]
    plan: dict[str, Any] = input_data["plan"]
    attempt = int(input_data.get("attempt") or 1)
    agent_blueprint: AgenticPlanBlueprint | None = input_data.get("agent_blueprint")
    source_brief: ReviewPlanSourceBrief | None = input_data.get("source_brief")
    writer_provider = resolve_review_plan_writer_provider()
    writer_model = resolve_review_plan_writer_model(provider=writer_provider)
    temperature = resolve_review_plan_repair_temperature()

    rendered = render_prompt(
        system_prompt_path=prompt_bundle.system_prompt_path,
        node_prompt_path="nodes/revision.md",
        subject_pack_path=prompt_bundle.subject_pack_path,
        style_path=prompt_bundle.style_path,
        rubric_path=prompt_bundle.rubric_path,
        variables={**prompt_bundle.variables, "revision_attempt": attempt},
    )
    revised, usage = generate_review_plan_json(
        system_prompt=rendered["prompt"],
        user_message=_revision_message(
            plan=plan,
            quality=quality,
            review_input=review_input,
            attempt=attempt,
            agent_blueprint=agent_blueprint,
            prompt_bundle=prompt_bundle,
            source_brief=source_brief,
        ),
        provider=writer_provider,
        model=writer_model,
        temperature=temperature,
        stage="targeted_revision",
        timeout_seconds=120.0,
        max_retries=0,
    )
    revised = _apply_lesson_date(normalize_final_review_plan(revised), review_input)
    context.node_outputs["revision_model_config"] = {
        "provider": writer_provider,
        "model": writer_model,
        "temperature": temperature,
        "prompt_version": rendered["prompt_version"],
        "usage": usage,
    }
    context.node_outputs.setdefault("revision_attempts", []).append(
        {
            "attempt": attempt,
            "prompt_version": rendered["prompt_version"],
            "quality_score_before": quality.score,
            "issue_count": len(quality.issues),
            "provider": writer_provider,
            "model": writer_model,
            "temperature": temperature,
            "usage": usage,
        }
    )
    return revised, usage


revision_node: WorkflowNode[dict[str, Any], tuple[dict[str, Any], dict[str, Any]]] = WorkflowNode(
    name="revision",
    run=_run,
)
