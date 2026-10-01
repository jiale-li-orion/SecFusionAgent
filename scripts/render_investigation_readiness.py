from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from packages.evaluation.investigation_readiness import (
    render_investigation_readiness_markdown,
)


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("Investigation readiness payload must be an object")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Render Investigation readiness Markdown")
    parser.add_argument("input", type=Path)
    parser.add_argument("--markdown-output", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rendered = render_investigation_readiness_markdown(_load(args.input))
    if args.check:
        if not args.markdown_output.exists():
            raise SystemExit(f"missing generated Investigation readiness: {args.markdown_output}")
        if args.markdown_output.read_text(encoding="utf-8") != rendered:
            raise SystemExit(f"stale generated Investigation readiness: {args.markdown_output}")
        return 0
    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
