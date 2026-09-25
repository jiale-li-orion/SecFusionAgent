from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path


def _git_sha(repo: Path) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "-C", str(repo), "rev-parse", "--short=8", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _count_files(root: Path, pattern: str) -> int:
    return sum(1 for path in root.glob(pattern) if path.is_file())


def build(repo: Path, wiki: Path | None) -> dict[str, object]:
    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "main_sha": _git_sha(repo),
        "wiki_sha": _git_sha(wiki) if wiki else None,
        "source_definitions": _count_files(repo / "config/sources", "*.json"),
        "migrations": _count_files(repo / "alembic/versions", "*.py"),
        "test_files": sum(
            1
            for root in (repo / "packages", repo / "tests")
            if root.exists()
            for path in root.rglob("test_*.py")
            if path.is_file()
        ),
        "quality_gate": ["ruff", "mypy", "pytest"],
        "phase": "M1-M3 Data Plane / Integration Probe",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build machine-generated project status for GitHub Pages"
    )
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--wiki", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = build(args.repo.resolve(), args.wiki.resolve() if args.wiki else None)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
