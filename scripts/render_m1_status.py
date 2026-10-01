from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from packages.evaluation.m1_status import (
    project_m1_readme_status,
    render_m1_status_markdown,
    update_m1_readme_status,
)


def _load_result(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("M1 result JSON must contain one object")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render generated M1 documentation from an existing benchmark JSON result"
    )
    parser.add_argument("result", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    parser.add_argument("--readme-status", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.markdown_output is None and args.readme_status is None:
        parser.error("provide --markdown-output and/or --readme-status")

    status = render_m1_status_markdown(_load_result(args.result))
    if args.check:
        stale: list[str] = []
        if args.markdown_output is not None:
            current = args.markdown_output.read_text(encoding="utf-8")
            if current != status:
                stale.append(str(args.markdown_output))
        if args.readme_status is not None:
            current = args.readme_status.read_text(encoding="utf-8")
            projected = project_m1_readme_status(
                current,
                status,
                label=str(args.readme_status),
            )
            if projected != current:
                stale.append(str(args.readme_status))
        if stale:
            raise SystemExit("stale generated M1 documentation: " + ", ".join(stale))
        return 0
    if args.markdown_output is not None:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(status, encoding="utf-8")
    if args.readme_status is not None:
        update_m1_readme_status(args.readme_status, status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
