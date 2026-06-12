from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4


PROMPT_VERSION = "review-plan-workflow.v1"
SCHEMA_VERSION = "review-plan-schema.v1"
STYLE_VERSION = "physics-master-style.v1"


@dataclass
class WorkflowWarning:
    code: str
    message: str
    severity: str = "medium"

    def to_dict(self) -> dict:
        return {"code": self.code, "message": self.message, "severity": self.severity}


@dataclass
class WorkflowLog:
    node_name: str
    status: str
    latency_ms: int
    error: str = ""

    def to_dict(self) -> dict:
        payload = {
            "node_name": self.node_name,
            "status": self.status,
            "latency_ms": int(self.latency_ms),
        }
        if self.error:
            payload["error"] = self.error
        return payload


@dataclass
class WorkflowContext:
    trace_id: str = field(default_factory=lambda: uuid4().hex)
    subject: str = ""
    provider: str = ""
    model: str = ""
    prompt_version: str = PROMPT_VERSION
    schema_version: str = SCHEMA_VERSION
    style_version: str = STYLE_VERSION
    warnings: list[WorkflowWarning] = field(default_factory=list)
    logs: list[WorkflowLog] = field(default_factory=list)
    node_outputs: dict[str, object] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def add_warning(self, code: str, message: str, severity: str = "medium") -> None:
        self.warnings.append(WorkflowWarning(code=code, message=message, severity=severity))

    def warnings_as_dicts(self) -> list[dict]:
        return [warning.to_dict() for warning in self.warnings]

    def logs_as_dicts(self) -> list[dict]:
        return [log.to_dict() for log in self.logs]
