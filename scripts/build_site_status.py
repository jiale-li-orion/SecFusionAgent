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
    sources = [json.loads(path.read_text()) for path in (repo / "config/sources").glob("*.json")]
    inventory = json.loads((repo / "config/source-inventory.json").read_text())
    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "main_sha": _git_sha(repo),
        "wiki_sha": _git_sha(wiki) if wiki else None,
        "source_definitions": len(sources),
        "catalog_entries": len(inventory["entries"]),
        "scheduled_monitors": sum(
            (source.get("schedule_policy") or {}).get("enabled", True) is not False
            for source in sources
        ),
        "migrations": _count_files(repo / "alembic/versions", "*.py"),
        "test_files": sum(
            1
            for root in (repo / "apps", repo / "packages", repo / "tests")
            if root.exists()
            for path in root.rglob("test_*.py")
            if path.is_file()
        ),
        "quality_gate": ["ruff", "mypy", "pytest"],
        "phase_zh": "M1-M3 持续数据平面 + Agent / QA / Evaluation Control Plane",
        "phase_en": "M1-M3 Continuous Data Plane + Agent / QA / Evaluation Control Plane",
        "runtime_owners": [
            "Task Runtime / TaskEvent",
            "M4 InvestigationState / EvidenceNeed / StatePatch",
            "M5 Capability / Policy / Budget / WATCH",
            "M6 Decision Runtime / Product Question / Session",
            "M7 Replay / Benchmark / Experience Promotion",
        ],
        "next_evidence_zh": (
            "扩大已有正式 QA 的困难问题与外部能力样本。验收历史世界读取、隔离底座与生产恢复。"
        ),
        "next_evidence_en": (
            "Broaden existing formal QA and external-capability cases; validate historical reads, "
            "isolation and production recovery."
        ),
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
