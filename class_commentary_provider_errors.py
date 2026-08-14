from __future__ import annotations

import re
from collections.abc import Mapping


CLASS_COMMENTARY_PROVIDER_FAILURE_SCHEMA_V1 = (
    "class_commentary.provider_failure.v1"
)

_PROVIDER_FAILURE_ERROR_CODES = {
    "provider_configuration_invalid",
    "provider_rate_limited",
    "provider_timeout",
    "provider_unavailable",
    "provider_request_rejected",
    "provider_upstream_error",
    "provider_response_invalid",
    "provider_request_failed",
    "provider_dispatch_interrupted",
    "provider_dispatch_legacy_unknown",
}
_PROVIDER_FAILURE_RESULT_STATES = {
    "not_dispatched",
    "rejected",
    "unknown",
    "invalid_response",
}
_SAFE_TOKEN_RE = re.compile(r"[^A-Za-z0-9._:/-]+")


def _safe_token(value: object, *, limit: int) -> str:
    try:
        raw = str(value or "").strip()
    except Exception:
        raw = ""
    normalized = _SAFE_TOKEN_RE.sub("_", raw)
    return normalized[: max(0, int(limit))]


def _safe_getattr(value: object, name: str, default=None):
    try:
        return getattr(value, name, default)
    except Exception:
        return default


def _response(exc: Exception):
    return _safe_getattr(exc, "response", None)


def _header_value(headers: object, *names: str) -> str:
    getter = _safe_getattr(headers, "get", None)
    if not callable(getter):
        return ""
    for name in names:
        try:
            value = getter(name)
            normalized = str(value).strip() if value is not None else ""
        except Exception:
            continue
        if normalized:
            return normalized
    return ""


def provider_error_http_status(exc: Exception) -> int:
    response = _response(exc)
    raw_status = _safe_getattr(exc, "status_code", None) or _safe_getattr(
        response, "status_code", None
    )
    try:
        status_code = int(raw_status) if raw_status is not None else 0
    except (TypeError, ValueError):
        return 0
    return status_code if 100 <= status_code <= 599 else 0


def provider_error_retry_after_seconds(
    exc: Exception,
    default: int = 30,
) -> int:
    response = _response(exc)
    headers = _safe_getattr(response, "headers", None) or _safe_getattr(
        exc, "headers", None
    )
    value = _header_value(headers, "retry-after", "Retry-After")
    try:
        parsed = int(float(value)) if value else int(default)
    except (TypeError, ValueError):
        parsed = int(default)
    return max(1, min(parsed, 600))


def classify_provider_error(exc: Exception) -> tuple[str, bool, int]:
    name = exc.__class__.__name__.lower()
    try:
        message = str(exc).lower()
    except Exception:
        message = ""
    status_code = provider_error_http_status(exc)
    if message.startswith("xr_class_commentary_"):
        return "provider_configuration_invalid", False, 0
    if (
        status_code == 429
        or "ratelimit" in name
        or "rate limit" in message
        or "429" in message
    ):
        return (
            "provider_rate_limited",
            True,
            provider_error_retry_after_seconds(exc, 60),
        )
    if (
        status_code == 408
        or "timeout" in name
        or "timed out" in message
        or "timeout" in message
    ):
        return (
            "provider_timeout",
            True,
            provider_error_retry_after_seconds(exc, 30),
        )
    if (
        status_code in {409, 425}
        or "connection" in name
        or "connection" in message
        or "temporar" in message
    ):
        return (
            "provider_unavailable",
            True,
            provider_error_retry_after_seconds(exc, 30),
        )
    if 400 <= status_code < 500:
        return "provider_request_rejected", False, 0
    if status_code >= 500:
        return (
            "provider_upstream_error",
            True,
            provider_error_retry_after_seconds(exc, 30),
        )
    if (
        isinstance(exc, (AttributeError, IndexError, KeyError))
        or "responsevalidation" in name
        or "jsondecode" in name
    ):
        return "provider_response_invalid", True, 0
    return (
        "provider_request_failed",
        True,
        provider_error_retry_after_seconds(exc, 30),
    )


def _provider_request_id(exc: Exception) -> str:
    direct = _safe_getattr(exc, "request_id", None)
    if direct:
        return _safe_token(direct, limit=200)
    response = _response(exc)
    headers = _safe_getattr(response, "headers", None)
    return _safe_token(
        _header_value(
            headers,
            "x-request-id",
            "X-Request-Id",
            "request-id",
            "openai-request-id",
        ),
        limit=200,
    )


def _upstream_error_code(exc: Exception) -> str:
    return _safe_token(_safe_getattr(exc, "code", None), limit=100)


def _exception_type(exc: Exception) -> str:
    value = f"{exc.__class__.__module__}.{exc.__class__.__name__}"
    return _safe_token(value, limit=160)


def build_provider_failure_snapshot(
    exc: Exception,
    *,
    local_request_id: str,
) -> dict:
    error_code, retryable, retry_after_seconds = classify_provider_error(exc)
    if error_code == "provider_configuration_invalid":
        result_state = "not_dispatched"
    elif error_code in {"provider_rate_limited", "provider_request_rejected"}:
        result_state = "rejected"
    elif error_code == "provider_response_invalid":
        result_state = "invalid_response"
    else:
        result_state = "unknown"
    return normalize_provider_failure_snapshot(
        {
            "schema_version": CLASS_COMMENTARY_PROVIDER_FAILURE_SCHEMA_V1,
            "error_code": error_code,
            "result_state": result_state,
            "exception_type": _exception_type(exc),
            "http_status": provider_error_http_status(exc),
            "upstream_error_code": _upstream_error_code(exc),
            "provider_request_id": _provider_request_id(exc),
            "local_request_id": _safe_token(local_request_id, limit=200),
            "retryable": retryable,
            "retry_after_seconds": retry_after_seconds,
        }
    )


def build_provider_dispatch_interruption_snapshot(
    *,
    local_request_id: str,
    legacy: bool = False,
) -> dict:
    return normalize_provider_failure_snapshot(
        {
            "schema_version": CLASS_COMMENTARY_PROVIDER_FAILURE_SCHEMA_V1,
            "error_code": (
                "provider_dispatch_legacy_unknown"
                if legacy
                else "provider_dispatch_interrupted"
            ),
            "result_state": "unknown",
            "exception_type": "",
            "http_status": 0,
            "upstream_error_code": "",
            "provider_request_id": "",
            "local_request_id": _safe_token(local_request_id, limit=200),
            "retryable": True,
            "retry_after_seconds": 0,
        }
    )


def normalize_provider_failure_snapshot(value: object) -> dict:
    if not isinstance(value, Mapping):
        raise ValueError("provider failure snapshot must be an object")
    expected_keys = {
        "schema_version",
        "error_code",
        "result_state",
        "exception_type",
        "http_status",
        "upstream_error_code",
        "provider_request_id",
        "local_request_id",
        "retryable",
        "retry_after_seconds",
    }
    if set(value) != expected_keys:
        raise ValueError("provider failure snapshot fields are invalid")
    schema_version = str(value.get("schema_version") or "")
    if schema_version != CLASS_COMMENTARY_PROVIDER_FAILURE_SCHEMA_V1:
        raise ValueError("provider failure snapshot schema is invalid")
    error_code = str(value.get("error_code") or "")
    if error_code not in _PROVIDER_FAILURE_ERROR_CODES:
        raise ValueError("provider failure error code is invalid")
    result_state = str(value.get("result_state") or "")
    if result_state not in _PROVIDER_FAILURE_RESULT_STATES:
        raise ValueError("provider failure result state is invalid")
    raw_http_status = value.get("http_status")
    raw_retry_after = value.get("retry_after_seconds")
    if isinstance(raw_http_status, bool) or isinstance(raw_retry_after, bool):
        raise ValueError("provider failure numeric fields are invalid")
    try:
        http_status = int(raw_http_status or 0)
        retry_after_seconds = int(raw_retry_after or 0)
    except (TypeError, ValueError) as exc:
        raise ValueError("provider failure numeric fields are invalid") from exc
    if http_status != 0 and not 100 <= http_status <= 599:
        raise ValueError("provider failure HTTP status is invalid")
    if not 0 <= retry_after_seconds <= 600:
        raise ValueError("provider failure retry delay is invalid")
    retryable = value.get("retryable")
    if not isinstance(retryable, bool):
        raise ValueError("provider failure retryable flag is invalid")
    return {
        "schema_version": schema_version,
        "error_code": error_code,
        "result_state": result_state,
        "exception_type": _safe_token(value.get("exception_type"), limit=160),
        "http_status": http_status,
        "upstream_error_code": _safe_token(
            value.get("upstream_error_code"), limit=100
        ),
        "provider_request_id": _safe_token(
            value.get("provider_request_id"), limit=200
        ),
        "local_request_id": _safe_token(value.get("local_request_id"), limit=200),
        "retryable": retryable,
        "retry_after_seconds": retry_after_seconds,
    }
