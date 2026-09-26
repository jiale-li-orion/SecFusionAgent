from __future__ import annotations

import subprocess
from pathlib import Path


def test_localized_source_catalogs_have_structural_parity() -> None:
    zh = Path("../SecFusionAgent.wiki/site/data/source-catalog.zh.js")
    en = Path("../SecFusionAgent.wiki/site/data/source-catalog.en.js")
    if not zh.exists() or not en.exists():
        return
    result = subprocess.run(
        [
            "python3",
            "scripts/check_source_catalog_pair.py",
            str(zh),
            str(en),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "99 entries" in result.stdout
