from __future__ import annotations

from dataclasses import dataclass
from time import monotonic
from typing import Callable, Generic, TypeVar

from .observability import workflow_node_span
from .state import WorkflowContext, WorkflowLog


InputT = TypeVar("InputT")
OutputT = TypeVar("OutputT")


@dataclass(frozen=True)
class WorkflowNode(Generic[InputT, OutputT]):
    name: str
    run: Callable[[InputT, WorkflowContext], OutputT]


def _json_safe(value: object) -> object:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def run_workflow_node(node: WorkflowNode[InputT, OutputT], input_data: InputT, context: WorkflowContext) -> OutputT:
    started = monotonic()
    with workflow_node_span(node_name=node.name, input_data=input_data, context=context) as span:
        try:
            output = node.run(input_data, context)
            latency_ms = int((monotonic() - started) * 1000)
            span.record_success(output=output, latency_ms=latency_ms)
            context.node_outputs[node.name] = _json_safe(output)
            context.logs.append(
                WorkflowLog(
                    node_name=node.name,
                    status="success",
                    latency_ms=latency_ms,
                )
            )
            return output
        except Exception as exc:
            latency_ms = int((monotonic() - started) * 1000)
            span.record_failure(error=exc, latency_ms=latency_ms)
            context.logs.append(
                WorkflowLog(
                    node_name=node.name,
                    status="failed",
                    latency_ms=latency_ms,
                    error=str(exc),
                )
            )
            raise
