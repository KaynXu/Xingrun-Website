from __future__ import annotations

import json
import math
from collections.abc import Mapping
from typing import Any
from urllib import error, parse, request

from config_runtime import get_runtime_config
import master_data


class WrongQuestionProxyError(RuntimeError):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


WECHAT_WRONG_QUESTION_BOX_SYSTEM_PROMPT = """你是小学和初中数学错题框选助手。
你的任务是从整页作业或试卷图片里，找出适合单独裁剪成错题记录的题目区域。

只保留真正的题目区域：
- 优先框选印刷体题干、题目编号、配套题图和与该题直接相关的表格
- 一张图里如果有多道独立题目，分别返回多个框

必须忽略这些内容：
- 忽略孩子手写字迹、演算草稿、列式、答案、订正内容
- 老师批改痕迹、对勾、叉号、圈画、箭头、分数和评语
- 页眉页脚、姓名、班级、页码、装饰边框、与题目无关的空白区域

输出规则：
- 只返回 JSON，不要解释
- 顶层字段必须是 boxes
- boxes 里的每个框都必须包含 x、y、width、height
- 坐标使用相对比例，范围在 0 到 1
- 如果不确定某块是否属于题目，宁可不框，也不要把手写答案区或草稿区框进去"""

WECHAT_WRONG_QUESTION_BOX_USER_PROMPT = "请只框出题目区域，忽略孩子手写字迹、演算、批改痕迹和答案内容。"


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


def _service_config_if_present() -> tuple[str, str] | None:
    cfg = get_runtime_config()
    base_url = str(cfg.get("wrong_question_service_url", "")).strip().rstrip("/")
    token = str(cfg.get("wrong_question_service_token", "")).strip()
    if base_url and token:
        return base_url, token
    return None


def _n1n_box_config() -> tuple[str, str, str]:
    cfg = get_runtime_config()
    api_key = str(cfg.get("n1n_api_key", "")).strip()
    base_url = str(cfg.get("n1n_base_url", "https://api.n1n.ai/v1")).strip().rstrip("/")
    model = str(cfg.get("n1n_model", "gpt-4o")).strip() or "gpt-4o"
    if not api_key:
        raise WrongQuestionProxyError("N1N API Key 未配置", 503)
    return api_key, base_url, model


def _normalize_wrong_question_box(box: Any) -> dict[str, float] | None:
    if not isinstance(box, Mapping):
        return None

    try:
        x = float(box.get("x"))
        y = float(box.get("y"))
        width = float(box.get("width"))
        height = float(box.get("height"))
    except (TypeError, ValueError):
        return None

    if not all(math.isfinite(value) for value in (x, y, width, height)):
        return None
    if x < 0 or y < 0 or width <= 0 or height <= 0:
        return None
    if x >= 1 or y >= 1 or x + width > 1 or y + height > 1:
        return None

    return {
        "x": x,
        "y": y,
        "width": width,
        "height": height,
    }


def _normalize_wrong_question_boxes_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise WrongQuestionProxyError("下游服务返回了无效响应", 502)

    raw_boxes = payload.get("boxes")
    if not isinstance(raw_boxes, list):
        raise WrongQuestionProxyError("下游服务返回了无效响应", 502)

    boxes = []
    for item in raw_boxes:
        normalized = _normalize_wrong_question_box(item)
        if normalized is not None:
            boxes.append(normalized)
    return {"boxes": boxes}


def _extract_chat_completion_content(payload: Any) -> str:
    if not isinstance(payload, Mapping):
        raise WrongQuestionProxyError("下游服务返回了无效响应", 502)

    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise WrongQuestionProxyError("下游服务返回了无效响应", 502)

    first_choice = choices[0]
    if not isinstance(first_choice, Mapping):
        raise WrongQuestionProxyError("下游服务返回了无效响应", 502)

    message = first_choice.get("message")
    if not isinstance(message, Mapping):
        raise WrongQuestionProxyError("下游服务返回了无效响应", 502)

    content = message.get("content")
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        text_parts = []
        for item in content:
            if not isinstance(item, Mapping):
                continue
            if item.get("type") == "text" and isinstance(item.get("text"), str):
                text_parts.append(item["text"])
        if text_parts:
            return "".join(text_parts)

    raise WrongQuestionProxyError("下游服务返回了无效响应", 502)


def _detect_wechat_wrong_question_boxes_via_n1n(image_url: str) -> dict[str, Any]:
    api_key, base_url, model = _n1n_box_config()
    body = json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": WECHAT_WRONG_QUESTION_BOX_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": WECHAT_WRONG_QUESTION_BOX_USER_PROMPT},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                },
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        },
        ensure_ascii=False,
    ).encode("utf-8")
    req = request.Request(
        f"{base_url}/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Xingrun-Website/1.0",
            "Accept": "application/json",
        },
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=40) as response:
            raw = response.read()
    except error.HTTPError as exc:
        raise WrongQuestionProxyError(_extract_error_message(exc.read()), exc.code) from exc
    except error.URLError as exc:
        raise WrongQuestionProxyError(f"下游服务不可用: {exc.reason}", 502) from exc

    try:
        completion_payload = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise WrongQuestionProxyError("下游服务返回了无效响应", 502) from exc

    content = _extract_chat_completion_content(completion_payload)
    try:
        boxes_payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise WrongQuestionProxyError("下游服务返回了无效响应", 502) from exc

    return _normalize_wrong_question_boxes_payload(boxes_payload)


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


def detect_wechat_wrong_question_boxes(payload: dict[str, Any]) -> dict[str, Any]:
    image_url = str(payload.get("image_url") or "").strip()
    if not image_url:
        raise WrongQuestionProxyError("image_url is required", 400)

    if _service_config_if_present():
        return _normalize_wrong_question_boxes_payload(
            _request_downstream(
                "/wechat/wrong-question-boxes",
                method="POST",
                payload={"image_url": image_url},
            )
        )

    return _detect_wechat_wrong_question_boxes_via_n1n(image_url)
