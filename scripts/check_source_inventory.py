from __future__ import annotations

import argparse
import re
from pathlib import Path

from packages.sources.inventory import load_source_inventory

CATEGORY_RE = re.compile(
    (
        r'\{\n\s+id: "([^"]+)",\n\s+no: "([^"]+)",'
        r'\n\s+title: "([^"]+)"(?P<body>.*?)'
        r'(?=\n\s+\{\n\s+id: "|\n\s+\]\n\};)'
    ),
    re.S,
)
ITEM_RE = re.compile(r'\{\s*name: "([^"]+)"(?P<rest>.*?)\}', re.S)


def parse_website_catalog(path: Path) -> set[tuple[str, str]]:
    text = path.read_text()
    result: set[tuple[str, str]] = set()
    for category in CATEGORY_RE.finditer(text):
        category_id = category.group(1)
        for item in ITEM_RE.finditer(category.group("body")):
            rest = item.group("rest")
            if "kind:" not in rest or "status:" not in rest:
                continue
            result.add((category_id, item.group(1)))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Compare the executable source inventory with a website source catalog projection"
        )
    )
    parser.add_argument("catalog", type=Path)
    args = parser.parse_args()

    inventory = load_source_inventory()
    expected = {(item.category, item.name) for item in inventory.entries}
    projected = parse_website_catalog(args.catalog)
    missing_from_web = sorted(expected - projected)
    missing_from_inventory = sorted(projected - expected)
    if missing_from_web or missing_from_inventory:
        if missing_from_web:
            print("inventory-only entries:")
            for category, name in missing_from_web:
                print(f"  {category}: {name}")
        if missing_from_inventory:
            print("website-only entries:")
            for category, name in missing_from_inventory:
                print(f"  {category}: {name}")
        raise SystemExit(1)
    print(f"source inventory matches website projection: {len(expected)} entries")


if __name__ == "__main__":
    main()
