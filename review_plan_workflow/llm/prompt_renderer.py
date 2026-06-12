from __future__ import annotations

import json
from typing import Any, Optional

from .prompt_registry import PromptRegistry


def _format_yaml_block(title: str, value: Optional[dict[str, Any]]) -> str:
    if not value:
        return ""
    return f"\n\n## {title}\n```json\n{json.dumps(value, ensure_ascii=False, indent=2)}\n```"


def render_prompt(
    *,
    system_prompt_path: str,
    node_prompt_path: str,
    subject_pack_path: Optional[str] = None,
    style_path: Optional[str] = None,
    rubric_path: Optional[str] = None,
    variables: Optional[dict[str, Any]] = None,
    registry: Optional[PromptRegistry] = None,
) -> dict[str, str]:
    registry = registry or PromptRegistry()
    parts = [
        registry.read_text(system_prompt_path),
        registry.read_text(node_prompt_path),
    ]
    if subject_pack_path:
        parts.append(_format_yaml_block("Subject Pack", registry.read_yaml(subject_pack_path)))
    if style_path:
        parts.append(_format_yaml_block("Style Config", registry.read_yaml(style_path)))
    if rubric_path:
        parts.append(_format_yaml_block("Rubric", registry.read_yaml(rubric_path)))
    if variables:
        parts.append(_format_yaml_block("Workflow State", variables))
    paths = [system_prompt_path, node_prompt_path]
    paths.extend(path for path in (subject_pack_path, style_path, rubric_path) if path)
    return {
        "prompt": "\n\n".join(part for part in parts if part),
        "prompt_version": registry.version_for(*paths),
    }
