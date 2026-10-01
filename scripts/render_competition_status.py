from __future__ import annotations

import argparse
import json
from pathlib import Path

from packages.evaluation.benchmark import CompetitionReport
from packages.evaluation.competition_status import render_competition_report_markdown


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render competition Markdown from an existing CompetitionReport JSON"
    )
    parser.add_argument("report", type=Path)
    parser.add_argument("--markdown-output", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    payload = json.loads(args.report.read_text(encoding="utf-8"))
    report = CompetitionReport.model_validate(payload)
    rendered = render_competition_report_markdown(report)
    if args.check:
        current = args.markdown_output.read_text(encoding="utf-8")
        if current != rendered:
            raise SystemExit(f"stale generated competition documentation: {args.markdown_output}")
        return 0
    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
