#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 4:
        print("Usage: erase_wrong_question_image.py <input-image> <output-image> <error-correction-backend>", file=sys.stderr)
        return 2

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    backend_path = Path(sys.argv[3])
    if not backend_path.exists():
        print(f"error_correction backend not found: {backend_path}", file=sys.stderr)
        return 2

    sys.path.insert(0, str(backend_path))
    from models.inference import InferenceEngine

    result_image = InferenceEngine().run(input_path.read_bytes())
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result_image.save(output_path, format="PNG")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
