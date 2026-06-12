from __future__ import annotations

from typing import Any, Callable, TypeVar

from pydantic import BaseModel


ModelT = TypeVar("ModelT", bound=BaseModel)


def generate_structured(
    *,
    producer: Callable[[], dict[str, Any]],
    schema: type[ModelT],
    node_name: str,
) -> ModelT:
    """Validate a structured producer output with a Pydantic schema.

    The production LLM provider stays in ai_processor for Phase 1; this helper
    establishes the future boundary for node-level structured generation.
    """

    payload = producer()
    try:
        return schema.model_validate(payload)
    except Exception as exc:
        raise ValueError(f"{node_name} returned invalid structured output: {exc}") from exc
