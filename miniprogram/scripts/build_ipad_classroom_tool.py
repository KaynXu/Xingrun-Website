from __future__ import annotations

import argparse
from pathlib import Path


DATA_TAG = '<script src="./classroom-roster-data.js"></script>'


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a self-contained iPad-friendly classroom tool HTML.")
    parser.add_argument(
        "--html",
        type=Path,
        default=Path("classroom-random-score.html"),
        help="Path to the source classroom HTML.",
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=Path("classroom-roster-data.js"),
        help="Path to the roster data JS.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("classroom-random-score-ipad.html"),
        help="Path to the output self-contained HTML.",
    )
    args = parser.parse_args()

    html = args.html.read_text(encoding="utf-8")
    data_js = args.data.read_text(encoding="utf-8").strip()

    if DATA_TAG not in html:
        raise SystemExit("Could not find external roster script tag to inline.")

    inlined_html = html.replace(DATA_TAG, f"<script>\n{data_js}\n</script>", 1)
    args.output.write_text(inlined_html, encoding="utf-8")
    print(f"Built {args.output}")


if __name__ == "__main__":
    main()
