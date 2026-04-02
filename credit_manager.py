from __future__ import annotations

import lesson_manager

CREDIT_PRICING_RULES = {
    "consultation_ai_parse": {"base_credits": 3, "extra_token_threshold": 4000, "extra_credits": 2},
    "teacher_feedback_draft": {"base_credits": 2, "extra_token_threshold": 0, "extra_credits": 0},
    "lesson_plan_generate": {"base_credits": 8, "extra_token_threshold": 5000, "extra_credits": 2},
    "audio_transcription": {"base_credits": 4, "extra_token_threshold": 0, "extra_credits": 0},
    "monthly_plan_generate": {"base_credits": 10, "extra_token_threshold": 6000, "extra_credits": 2},
}


def get_credit_overview(organization_id: int) -> dict:
    account = lesson_manager.ensure_credit_account(organization_id)
    return {
        "organization_id": organization_id,
        "credit_balance": account["credit_balance"],
        "total_recharged": account["total_recharged"],
        "total_consumed": account["total_consumed"],
        "updated_at": account["updated_at"],
    }


def apply_manual_adjustment(*, organization_id: int, actor_user_id: int, amount: int, note: str) -> dict:
    if amount == 0:
        raise ValueError("amount must not be zero")
    return lesson_manager.insert_credit_ledger_entry(
        organization_id=organization_id,
        direction="credit" if amount > 0 else "debit",
        amount=abs(int(amount)),
        source_type="manual_adjustment",
        source_id="manual",
        note=note,
        operator_user_id=actor_user_id,
    )


def record_ai_charge(
    *,
    organization_id: int,
    user_id: int,
    feature_key: str,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    credit_cost_final: int,
    source_record_type: str,
    source_record_id: int | str,
    request_id: str,
) -> dict:
    if int(credit_cost_final) <= 0:
        raise ValueError("credit_cost_final must be positive")
    return lesson_manager.insert_ai_usage_and_debit(
        organization_id=organization_id,
        user_id=user_id,
        feature_key=feature_key,
        provider=provider,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        credit_cost_final=int(credit_cost_final),
        source_record_type=source_record_type,
        source_record_id=str(source_record_id),
        request_id=request_id,
    )


def list_member_usage_summary(organization_id: int) -> list[dict]:
    return lesson_manager.list_member_usage_summary_rows(organization_id)
