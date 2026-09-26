from __future__ import annotations

import subprocess
from pathlib import Path

from packages.evaluation.m1_m3 import PRODUCT_SOURCE_CATEGORY_ORDER
from scripts.check_source_catalog_pair import parse_catalog


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


def test_website_source_categories_match_frozen_product_taxonomy() -> None:
    zh = Path("../SecFusionAgent.wiki/site/data/source-catalog.zh.js")
    en = Path("../SecFusionAgent.wiki/site/data/source-catalog.en.js")
    if not zh.exists() or not en.exists():
        return
    expected = tuple(item.value for item in PRODUCT_SOURCE_CATEGORY_ORDER)
    assert tuple(item.category_id for item in parse_catalog(zh)) == expected
    assert tuple(item.category_id for item in parse_catalog(en)) == expected
