from __future__ import annotations

import json
import sqlite3

import lesson_manager

CREDIT_PRICING_RULES = {
    "consultation_ai_parse": {"base_credits": 3, "extra_token_threshold": 4000, "extra_credits": 2},
    "lesson_plan_generate": {"base_credits": 8, "extra_token_threshold": 5000, "extra_credits": 2},
    "audio_transcription": {"base_credits": 4, "extra_token_threshold": 0, "extra_credits": 0},
    "monthly_plan_generate": {"base_credits": 10, "extra_token_threshold": 6000, "extra_credits": 2},
    "wrong_question_practice_generate": {"base_credits": 8, "extra_token_threshold": 5000, "extra_credits": 2},
    "wrong_question_recognize": {"base_credits": 2, "extra_token_threshold": 0, "extra_credits": 0},
    "wrong_question_classify_reason": {"base_credits": 1, "extra_token_threshold": 0, "extra_credits": 0},
    "child_reason_audio_transcribe": {"base_credits": 3, "extra_token_threshold": 0, "extra_credits": 0},
    "class_commentary_transcribe": {"base_credits": 4, "extra_token_threshold": 0, "extra_credits": 0},
    "class_commentary_transcript_polish": {"base_credits": 4, "extra_token_threshold": 0, "extra_credits": 0},
    "class_commentary_generate": {"base_credits": 8, "extra_token_threshold": 5000, "extra_credits": 2},
    "class_feedback_generate": {"base_credits": 8, "extra_token_threshold": 5000, "extra_credits": 2},
}


class CreditBalanceError(ValueError):
    pass


def _pricing_for_feature(feature_key: str) -> dict:
    pricing = CREDIT_PRICING_RULES.get(feature_key)
    if not pricing:
        raise ValueError(f"unknown feature_key: {feature_key}")
    return pricing


def max_configured_charge_for_feature(feature_key: str) -> int:
    pricing = _pricing_for_feature(feature_key)
    return int(pricing["base_credits"] or 0) + int(pricing["extra_credits"] or 0)


def get_credit_overview(organization_id: int) -> dict:
    account = lesson_manager.ensure_credit_account(organization_id)
    reserved_credits = lesson_manager.get_active_credit_hold_total(organization_id)
    return {
        "organization_id": organization_id,
        "credit_balance": account["credit_balance"],
        "reserved_credits": reserved_credits,
        "available_credits": max(
            0,
            int(account["credit_balance"] or 0) - reserved_credits,
        ),
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
    request_payload_hash: str = "",
    credit_hold_student_run_id: int | None = None,
) -> dict:
    _pricing_for_feature(feature_key)
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
        request_payload_hash=request_payload_hash,
        credit_hold_student_run_id=credit_hold_student_run_id,
    )


def ensure_feature_credits_available(*, organization_id: int, feature_key: str) -> None:
    overview = get_credit_overview(organization_id)
    minimum = max_configured_charge_for_feature(feature_key)
    if int(overview["available_credits"] or 0) < minimum:
        raise CreditBalanceError("机构积分不足，请先充值后再使用 AI 功能")


def ensure_feature_credits_available_for_count(
    *,
    organization_id: int,
    feature_key: str,
    call_count: int,
) -> None:
    normalized_count = max(0, int(call_count))
    overview = get_credit_overview(organization_id)
    maximum = max_configured_charge_for_feature(feature_key) * normalized_count
    if int(overview["available_credits"] or 0) < maximum:
        raise CreditBalanceError("机构积分不足，请先充值后再使用 AI 功能")


def finalize_ai_charge(
    *,
    organization_id: int,
    user_id: int,
    feature_key: str,
    usage: dict,
    source_record_type: str,
    source_record_id: int | str,
    request_id: str,
    request_payload_hash: str = "",
    credit_hold_student_run_id: int | None = None,
) -> dict:
    pricing = _pricing_for_feature(feature_key)
    normalized_usage = usage if isinstance(usage, dict) else {}
    input_tokens = max(0, int(normalized_usage.get("input_tokens", 0) or 0))
    output_tokens = max(0, int(normalized_usage.get("output_tokens", 0) or 0))
    total_tokens = input_tokens + output_tokens
    credit_cost_final = int(pricing["base_credits"] or 0)
    threshold = int(pricing["extra_token_threshold"] or 0)
    if threshold and total_tokens > threshold:
        credit_cost_final += int(pricing["extra_credits"] or 0)
    try:
        return record_ai_charge(
            organization_id=organization_id,
            user_id=user_id,
            feature_key=feature_key,
            provider=str(normalized_usage.get("provider", "") or ""),
            model=str(normalized_usage.get("model", "") or ""),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            credit_cost_final=credit_cost_final,
            source_record_type=source_record_type,
            source_record_id=source_record_id,
            request_id=request_id,
            request_payload_hash=request_payload_hash,
            credit_hold_student_run_id=credit_hold_student_run_id,
        )
    except ValueError as exc:
        if str(exc) == "insufficient credit balance":
            raise CreditBalanceError("机构积分不足，请先充值后再使用 AI 功能") from exc
        raise


def list_member_usage_summary(organization_id: int) -> list[dict]:
    return lesson_manager.list_member_usage_summary_rows(organization_id)


def get_ai_usage_by_request_id(*, organization_id: int, request_id: str) -> dict | None:
    normalized_request_id = str(request_id or "").strip()
    if not normalized_request_id:
        return None
    with lesson_manager.get_conn() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM ai_usage_ledger
            WHERE organization_id=? AND request_id=?
            ORDER BY id DESC
            LIMIT 1
            """,
            (organization_id, normalized_request_id),
        ).fetchone()
    return dict(row) if row else None


def list_credit_ledger(organization_id: int, *, limit: int = 100) -> list[dict]:
    normalized_limit = max(1, min(int(limit), 500))
    with lesson_manager.get_conn() as conn:
        rows = conn.execute(
            """
            SELECT
                id,
                organization_id,
                direction,
                amount,
                balance_after,
                source_type,
                source_id,
                note,
                operator_user_id,
                created_at
            FROM organization_credit_ledger
            WHERE organization_id=?
            ORDER BY id DESC
            LIMIT ?
            """,
            (organization_id, normalized_limit),
        ).fetchall()
    return [dict(row) for row in rows]


def list_member_usage_detail(organization_id: int, user_id: int, *, limit: int = 200) -> list[dict]:
    normalized_limit = max(1, min(int(limit), 500))
    with lesson_manager.get_conn() as conn:
        belongs_to_org = conn.execute(
            "SELECT 1 FROM users WHERE id=? AND organization_id=? LIMIT 1",
            (user_id, organization_id),
        ).fetchone()
        if not belongs_to_org:
            return []
        rows = conn.execute(
            """
            SELECT
                id,
                user_id,
                feature_key,
                provider,
                model,
                input_tokens,
                output_tokens,
                total_tokens,
                credit_cost_final,
                source_record_type,
                source_record_id,
                request_id,
                created_at
            FROM ai_usage_ledger
            WHERE organization_id=? AND user_id=?
            ORDER BY id DESC
            LIMIT ?
            """,
            (organization_id, user_id, normalized_limit),
        ).fetchall()
    return [dict(row) for row in rows]


def redeem_xhs_order(
    *,
    organization_id: int,
    actor_user_id: int,
    platform_order_id: str,
    phone_suffix: str,
    order_payload: dict,
) -> dict:
    normalized_order_id = (platform_order_id or "").strip()
    normalized_suffix = (phone_suffix or "").strip()
    if not normalized_order_id or not normalized_suffix:
        raise ValueError("platform_order_id and phone_suffix are required")
    if not isinstance(order_payload, dict):
        raise ValueError("order payload is invalid")

    buyer_phone = str(order_payload.get("buyer_masked_phone") or "").strip()
    if not buyer_phone or not buyer_phone.endswith(normalized_suffix):
        raise ValueError("order verification does not match phone suffix")

    order_status = str(order_payload.get("order_status") or "").strip().lower()
    if order_status != "paid":
        raise ValueError("order is not paid")

    credit_amount = int(order_payload.get("credit_amount") or 0)
    if credit_amount <= 0:
        raise ValueError("credit_amount must be positive")

    product_id = str(order_payload.get("product_id") or "").strip()
    sku_id = str(order_payload.get("sku_id") or "").strip()
    product_name = str(order_payload.get("product_name") or "").strip()
    paid_amount = int(order_payload.get("paid_amount") or 0)
    currency = str(order_payload.get("currency") or "CNY").strip() or "CNY"
    raw_order_payload = order_payload.get("raw_order_payload", order_payload)

    with lesson_manager.get_conn() as conn:
        existing = conn.execute(
            """
            SELECT *
            FROM xhs_order_redemptions
            WHERE platform='xiaohongshu' AND platform_order_id=?
            LIMIT 1
            """,
            (normalized_order_id,),
        ).fetchone()
        if existing and existing["redeem_status"] == "redeemed":
            raise ValueError("order already redeemed")

        raw_payload_json = json.dumps(raw_order_payload, ensure_ascii=False)

        if existing:
            redemption_id = int(existing["id"])
            conn.execute(
                """
                UPDATE xhs_order_redemptions
                SET product_id=?,
                    sku_id=?,
                    product_name=?,
                    paid_amount=?,
                    currency=?,
                    buyer_masked_phone=?,
                    order_status=?,
                    redeem_status='redeemed',
                    credit_amount=?,
                    redeemed_organization_id=?,
                    redeemed_by_user_id=?,
                    redeemed_at=datetime('now','localtime'),
                    raw_order_payload=?,
                    updated_at=datetime('now','localtime')
                WHERE id=?
                """,
                (
                    product_id,
                    sku_id,
                    product_name,
                    paid_amount,
                    currency,
                    buyer_phone,
                    order_status,
                    credit_amount,
                    organization_id,
                    actor_user_id,
                    raw_payload_json,
                    redemption_id,
                ),
            )
        else:
            try:
                cur = conn.execute(
                    """
                    INSERT INTO xhs_order_redemptions
                        (platform, platform_order_id, product_id, sku_id, product_name, paid_amount, currency,
                         buyer_masked_phone, order_status, redeem_status, credit_amount, redeemed_organization_id,
                         redeemed_by_user_id, redeemed_at, raw_order_payload)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'redeemed', ?, ?, ?, datetime('now','localtime'), ?)
                    """,
                    (
                        "xiaohongshu",
                        normalized_order_id,
                        product_id,
                        sku_id,
                        product_name,
                        paid_amount,
                        currency,
                        buyer_phone,
                        order_status,
                        credit_amount,
                        organization_id,
                        actor_user_id,
                        raw_payload_json,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError("order already redeemed") from exc
            redemption_id = int(cur.lastrowid)

        row = conn.execute(
            "SELECT * FROM xhs_order_redemptions WHERE id=?",
            (redemption_id,),
        ).fetchone()
        if not row:
            raise LookupError("redemption not found")
        redemption = dict(row)

        lesson_manager._insert_credit_ledger_entry_with_conn(
            conn,
            organization_id=organization_id,
            direction="credit",
            amount=credit_amount,
            source_type="xhs_order_redeem",
            source_id=str(redemption_id),
            note=normalized_order_id,
            operator_user_id=actor_user_id,
        )

    return {
        "redemption": redemption,
        "overview": get_credit_overview(organization_id),
    }
