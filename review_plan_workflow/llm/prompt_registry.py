from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Union

import yaml


PROMPT_ROOT = Path(__file__).resolve().parents[1] / "prompts"


class PromptRegistry:
    def __init__(self, root: Union[Path, str] = PROMPT_ROOT):
        self.root = Path(root)

    def resolve(self, relative_path: str) -> Path:
        path = (self.root / relative_path).resolve()
        root = self.root.resolve()
        if root not in path.parents and path != root:
            raise ValueError(f"prompt path escapes registry root: {relative_path}")
        if not path.exists():
            raise FileNotFoundError(f"prompt file not found: {path}")
        return path

    def read_text(self, relative_path: str) -> str:
        return self.resolve(relative_path).read_text(encoding="utf-8")

    def read_yaml(self, relative_path: str) -> dict[str, Any]:
        data = yaml.safe_load(self.read_text(relative_path)) or {}
        if not isinstance(data, dict):
            raise ValueError(f"prompt yaml must be a mapping: {relative_path}")
        return data

    def version_for(self, *relative_paths: str) -> str:
        digest = hashlib.sha256()
        for relative_path in relative_paths:
            path = self.resolve(relative_path)
            digest.update(str(path.relative_to(self.root)).encode("utf-8"))
            digest.update(path.read_bytes())
        return digest.hexdigest()[:12]
