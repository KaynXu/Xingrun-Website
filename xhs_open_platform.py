from __future__ import annotations

import json
import os
from typing import Any
from urllib import error, request

from config_runtime import get_runtime_config

DEFAULT_XHS_BASE_URL = "https://ark.xiaohongshu.com"


def fetch_xhs_order_for_redemption(*, platform_order_id: str, phone_suffix: str) -> dict:
    normalized_order_id = (platform_order_id or "").strip()
    normalized_suffix = (phone_suffix or "").strip()
    if not normalized_order_id or not normalized_suffix:
        raise ValueError("platform_order_id and phone_suffix are required")

    cfg = get_runtime_config()
    app_id = str(cfg.get("xhs_app_id") or os.environ.get("XHS_APP_ID", "")).strip()
    app_secret = str(cfg.get("xhs_app_secret") or os.environ.get("XHS_APP_SECRET", "")).strip()
    base_url = str(cfg.get("xhs_base_url") or DEFAULT_XHS_BASE_URL).strip() or DEFAULT_XHS_BASE_URL
    if not app_id or not app_secret:
        raise RuntimeError("xiaohongshu credentials are not configured")

    payload = _fetch_order_detail_from_xhs(
        platform_order_id=normalized_order_id,
        app_id=app_id,
        app_secret=app_secret,
        base_url=base_url,
    )
    normalized = _normalize_xhs_paid_order(payload, fallback_platform_order_id=normalized_order_id)
    if not str(normalized.get("buyer_masked_phone", "")).strip().endswith(normalized_suffix):
        raise ValueError("order verification does not match phone suffix")
    return normalized


def _fetch_order_detail_from_xhs(*, platform_order_id: str, app_id: str, app_secret: str, base_url: str) -> dict:
    endpoint = f"{base_url.rstrip('/')}/api/open/order/detail"
    body = json.dumps({"platform_order_id": platform_order_id}).encode("utf-8")
    req = request.Request(
        endpoint,
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-App-Id": app_id,
            "X-App-Secret": app_secret,
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8")
    except error.HTTPError as exc:
        raise RuntimeError(f"xiaohongshu order lookup failed: HTTP {exc.code}") from exc
    except error.URLError as exc:
        raise RuntimeError("xiaohongshu order lookup failed") from exc

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("xiaohongshu order lookup returned invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("xiaohongshu order lookup returned invalid payload")
    return parsed


def _normalize_xhs_paid_order(payload: dict, *, fallback_platform_order_id: str) -> dict:
    source: dict[str, Any] = payload
    if isinstance(payload.get("data"), dict):
        source = payload["data"]

    order_status = _read_string(source, "order_status", "status", "orderState").lower()
    if order_status in {"success", "completed", "settled"}:
        order_status = "paid"
    if order_status != "paid":
        raise ValueError("order is not paid")

    credit_amount = _read_int(source, "credit_amount", "credits", "points", "quantity")
    if credit_amount <= 0:
        raise ValueError("credit_amount must be positive")

    platform_order_id = _read_string(source, "platform_order_id", "order_id", "orderId")
    if not platform_order_id:
        platform_order_id = fallback_platform_order_id

    return {
        "platform_order_id": platform_order_id,
        "product_id": _read_string(source, "product_id", "sku_id", "skuId", "spu_id"),
        "sku_id": _read_string(source, "sku_id", "skuId"),
        "product_name": _read_string(source, "product_name", "title", "name") or "xiaohongshu credit package",
        "paid_amount": _read_int(source, "paid_amount", "pay_amount", "payAmount", "amount"),
        "currency": _read_string(source, "currency") or "CNY",
        "buyer_masked_phone": _read_string(source, "buyer_masked_phone", "buyer_phone", "phone"),
        "order_status": order_status,
        "credit_amount": credit_amount,
        "raw_order_payload": payload,
    }


def _read_string(payload: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = payload.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _read_int(payload: dict[str, Any], *keys: str) -> int:
    for key in keys:
        value = payload.get(key)
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return 0
