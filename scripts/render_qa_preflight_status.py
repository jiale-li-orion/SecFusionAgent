from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from packages.evaluation.qa_preflight_status import render_qa_preflight_markdown


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"QA preflight payload must be an object: {path}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Render QA no-model preflight status")
    parser.add_argument("--product", type=Path, required=True)
    parser.add_argument("--session", type=Path, required=True)
    parser.add_argument("--markdown-output", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    rendered = render_qa_preflight_markdown(_load(args.product), _load(args.session))
    if args.check:
        if not args.markdown_output.exists():
            raise SystemExit(
                f"missing generated QA preflight documentation: {args.markdown_output}"
            )
        current = args.markdown_output.read_text(encoding="utf-8")
        if current != rendered:
            raise SystemExit(f"stale generated QA preflight documentation: {args.markdown_output}")
        return 0

    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
