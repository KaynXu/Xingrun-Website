from __future__ import annotations

import json
from typing import Any

from config_runtime import resolve_review_plan_reviewer_temperature
from review_plan_workflow.executor import WorkflowNode
from review_plan_workflow.llm.client import generate_review_plan_json
from review_plan_workflow.llm.prompt_renderer import render_prompt
from review_plan_workflow.schemas import AgenticPlanBlueprint, PromptBundle, QualityReview, ReviewPlanInput
from review_plan_workflow.state import WorkflowContext


def _review_message(
    *,
    plan: dict[str, Any],
    local_quality: QualityReview,
    agent_blueprint: AgenticPlanBlueprint,
    review_input: ReviewPlanInput,
) -> str:
    output_contract = {
        "score": "0-100 整数。低于 85 或存在 high issue 必须 revision。",
        "passed": "是否可以直接交付给学生。",
        "must_revise": "是否必须修订。",
        "issues": [
            {
                "severity": "low|medium|high",
                "category": "schema|subject_fit|task_actionability|question_quality|factuality|review_loop|workload_sanity|style_consistency|pdf_safety",
                "description": "具体问题，必须能定位到计划内容。",
                "suggested_fix": "给 revision 节点的具体修复动作。",
                "target_path": "如 days[0].choices[1]；只有能定位到具体题目时填写。",
                "day": "如 1；只有能定位到具体复习日时填写。",
                "question_type": "choice|blank；只有能定位到具体题型时填写。",
                "question_index": "从 1 开始的题号；只有能定位到具体题目时填写。",
            }
        ],
        "revision_instructions": ["按优先级列出定向修订动作。"],
    }
    return "\n\n".join(
        [
            "你是复习计划审稿模型，只审稿，不重写计划。",
            "请像一位资深教研负责人一样判断：这份计划是否真的可打印、可执行、像老师设计的复习，而不是模板堆砌。",
            "如果本地规则已经指出问题，必须复核；如果本地规则漏掉空泛、题目不可做、错因不清，也要补充。",
            "证据边界：subject、grade、lesson_date、review_days 来自页面/班级/工作流元数据，是可信课程信息；不要因为课堂材料里没重复出现这些字段，就把 lesson_info.subject/grade/date 判为无依据。",
            "内容边界：topic、knowledge_points、example_stems、teacher quotes 必须来自课堂材料、source_brief 或老师本次要求；低置信材料下不能把推测主题伪装成课堂事实。",
            "如果 source_brief.teacher_emphasis 为空，quotes 应为空或不使用；不要接受没有课堂证据的“老师原话”。",
            "必须返回严格 JSON object，字段按 output_contract。",
            "output_contract:\n" + json.dumps(output_contract, ensure_ascii=False, indent=2),
            "trusted_workflow_metadata:\n"
            + json.dumps(
                {
                    "subject": review_input.subject,
                    "grade": review_input.grade,
                    "lesson_date": review_input.lesson_date,
                    "schedule_mode": review_input.schedule_mode,
                    "review_days": review_input.review_days,
                    "user_requirements_present": bool(review_input.user_requirements),
                },
                ensure_ascii=False,
                indent=2,
            ),
            "parent_blueprint:\n" + agent_blueprint.model_dump_json(indent=2),
            "local_quality_review:\n" + local_quality.model_dump_json(indent=2),
            "plan_json:\n" + json.dumps(plan, ensure_ascii=False, indent=2),
        ]
    )


def _quality_from_payload(payload: dict[str, Any]) -> QualityReview:
    raw = payload.get("qualityReview") if isinstance(payload.get("qualityReview"), dict) else payload
    review = QualityReview.model_validate(raw)
    has_high_issue = any(issue.severity == "high" for issue in review.issues)
    must_revise = bool(review.must_revise or review.score < 85 or has_high_issue)
    return QualityReview(
        score=max(0, min(100, int(review.score or 0))),
        passed=bool(review.passed) and not must_revise,
        issues=review.issues,
        must_revise=must_revise,
        revision_instructions=review.revision_instructions,
    )


def _run(input_data: dict[str, Any], context: WorkflowContext) -> tuple[QualityReview, dict[str, Any]]:
    plan: dict[str, Any] = input_data["plan"]
    local_quality: QualityReview = input_data["local_quality"]
    prompt_bundle: PromptBundle = input_data["prompt_bundle"]
    agent_blueprint: AgenticPlanBlueprint = input_data["agent_blueprint"]
    review_input: ReviewPlanInput = input_data["review_input"]
    temperature = resolve_review_plan_reviewer_temperature()

    rendered = render_prompt(
        system_prompt_path=prompt_bundle.system_prompt_path,
        node_prompt_path="nodes/quality-reviewer.md",
        subject_pack_path=prompt_bundle.subject_pack_path,
        style_path=prompt_bundle.style_path,
        rubric_path=prompt_bundle.rubric_path,
        variables={**prompt_bundle.variables, "stage": "quality_reviewer_llm"},
    )
    payload, usage = generate_review_plan_json(
        system_prompt=rendered["prompt"],
        user_message=_review_message(
            plan=plan,
            local_quality=local_quality,
            agent_blueprint=agent_blueprint,
            review_input=review_input,
        ),
        provider=context.provider,
        model=context.model,
        reasoning_effort=context.reasoning_effort,
        temperature=temperature,
        stage="quality_reviewer_llm",
        timeout_seconds=90.0,
        max_retries=0,
    )
    review = _quality_from_payload(payload)
    context.node_outputs["quality_reviewer_llm_model_config"] = {
        "provider": context.provider,
        "model": context.model,
        "reasoning_effort": context.reasoning_effort,
        "temperature": temperature,
        "prompt_version": rendered["prompt_version"],
        "usage": usage,
    }
    return review, usage


quality_reviewer_llm_node: WorkflowNode[dict[str, Any], tuple[QualityReview, dict[str, Any]]] = WorkflowNode(
    name="quality_reviewer_llm",
    run=_run,
)
