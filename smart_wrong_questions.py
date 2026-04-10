from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any
from urllib import error, parse, request

from config_runtime import get_runtime_config
import master_data


class WrongQuestionProxyError(RuntimeError):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


def _service_config() -> tuple[str, str]:
    cfg = get_runtime_config()
    base_url = str(cfg.get("wrong_question_service_url", "")).strip().rstrip("/")
    token = str(cfg.get("wrong_question_service_token", "")).strip()
    if not base_url or not token:
        raise WrongQuestionProxyError("智能错题服务尚未配置", 503)
    return base_url, token


def _normalize_query(query: Any) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    if query is None:
        return normalized

    if hasattr(query, "lists"):
        for key, values in query.lists():
            cleaned = [value for value in values if value not in (None, "", [])]
            if not cleaned:
                continue
            normalized[key] = cleaned if len(cleaned) > 1 else cleaned[0]
        return normalized

    if isinstance(query, Mapping):
        for key, value in query.items():
            if value in (None, "", []):
                continue
            normalized[key] = value
    return normalized


def _extract_error_message(raw: bytes) -> str:
    if not raw:
        return "下游服务请求失败"
    text = raw.decode("utf-8", errors="replace")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return text or "下游服务请求失败"

    if isinstance(payload, dict):
        detail = payload.get("error") or payload.get("message") or payload.get("detail")
        if isinstance(detail, str) and detail.strip():
            return detail.strip()
    return text or "下游服务请求失败"


def _request_downstream(
    path: str,
    *,
    method: str = "GET",
    query: Any = None,
    payload: dict[str, Any] | None = None,
    expect_binary: bool = False,
) -> Any:
    base_url, token = _service_config()
    query_params = _normalize_query(query)
    query_params["token"] = token

    url = f"{base_url}{path}"
    if query_params:
        url = f"{url}?{parse.urlencode(query_params, doseq=True)}"

    body = None
    headers = {}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = request.Request(url, data=body, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=20) as response:
            raw = response.read()
            if expect_binary:
                return raw, response.headers
            if not raw:
                return {}
            try:
                return json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError as exc:
                raise WrongQuestionProxyError("下游服务返回了无效响应", 502) from exc
    except error.HTTPError as exc:
        raise WrongQuestionProxyError(_extract_error_message(exc.read()), exc.code) from exc
    except error.URLError as exc:
        raise WrongQuestionProxyError(f"下游服务不可用: {exc.reason}", 502) from exc


def _quote_record_id(record_id: str) -> str:
    return parse.quote(str(record_id), safe="")


def _require_object_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise WrongQuestionProxyError("下游服务返回了无效响应", 502)
    return dict(payload)


def fetch_wrong_question_records(query: Any) -> dict[str, Any]:
    payload = _require_object_payload(_request_downstream("/wrong-questions", query=query))
    raw_items = payload.get("items")
    if not isinstance(raw_items, list):
        raw_items = payload.get("records")
    items = raw_items if isinstance(raw_items, list) else []

    payload["items"] = [
        master_data.normalize_wrong_question_record(item)
        if isinstance(item, Mapping)
        else item
        for item in items
    ]

    # Keep compatibility with frontend list parsing logic while preserving
    # the original downstream shape for debugging and incremental migration.
    if "records" in payload and not isinstance(payload.get("records"), list):
        payload["records"] = payload["items"]
    return payload


def fetch_wrong_question_record(record_id: str, query: Any) -> dict[str, Any]:
    payload = _require_object_payload(
        _request_downstream(f"/wrong-questions/{_quote_record_id(record_id)}", query=query)
    )
    return master_data.normalize_wrong_question_record(payload)


def save_wrong_question_review(record_id: str, query: Any, payload: dict[str, Any]) -> dict[str, Any]:
    return _require_object_payload(
        _request_downstream(
            f"/wrong-questions/{_quote_record_id(record_id)}/review",
            method="PUT",
            query=query,
            payload=payload,
        )
    )