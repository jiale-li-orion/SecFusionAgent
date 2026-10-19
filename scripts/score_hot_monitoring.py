"""Recompute a retained-record monitoring snapshot; never call collectors or models."""

from __future__ import annotations

import argparse
import json
from hashlib import sha256
from pathlib import Path

from packages.evaluation.hot_monitoring import score_hot_monitoring_snapshot


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument(
        "--sha256", required=True, help="Frozen input digest declared before replay"
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raw = args.snapshot.read_bytes()
    digest = sha256(raw).hexdigest()
    if digest != args.sha256:
        raise ValueError("frozen monitoring snapshot digest mismatch")
    snapshot = json.loads(raw)
    score = score_hot_monitoring_snapshot(snapshot)
    score["snapshot_sha256"] = digest
    score["operational_category_evidence"] = snapshot.get("operational_category_evidence")
    score["all_day_vulnerability_run_status_counts"] = snapshot.get(
        "all_day_vulnerability_run_status_counts"
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(score, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: v
                for k, v in score.items()
                if k
                not in {"operational_category_evidence", "all_day_vulnerability_run_status_counts"}
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
