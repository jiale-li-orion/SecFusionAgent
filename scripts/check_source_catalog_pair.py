from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path

CATEGORY_RE = re.compile(
    (
        r'\{\n\s+id: "([^"]+)",\n\s+no: "([^"]+)",'
        r'\n\s+title: "([^"]+)"(?P<body>.*?)'
        r'(?=\n\s+\{\n\s+id: "|\n\s+\]\n\};)'
    ),
    re.S,
)
ITEM_RE = re.compile(r'\{\s*name: "([^"]+)"(?P<rest>.*?)\}', re.S)
FIELD_RE = re.compile(r'(url|path|status|impl): "([^"]*)"')


@dataclass(frozen=True)
class CatalogItem:
    name: str
    url: str | None
    status: str | None
    impl: str | None


@dataclass(frozen=True)
class CatalogCategory:
    category_id: str
    number: str
    items: tuple[CatalogItem, ...]


def parse_catalog(path: Path) -> list[CatalogCategory]:
    text = path.read_text()
    categories: list[CatalogCategory] = []
    for category in CATEGORY_RE.finditer(text):
        items: list[CatalogItem] = []
        for item in ITEM_RE.finditer(category.group("body")):
            rest = item.group("rest")
            if "kind:" not in rest or "status:" not in rest:
                continue
            fields = {key: value for key, value in FIELD_RE.findall(rest)}
            items.append(
                CatalogItem(
                    name=item.group(1),
                    url=fields.get("url"),
                    status=fields.get("status"),
                    impl=fields.get("impl"),
                )
            )
        categories.append(
            CatalogCategory(
                category_id=category.group(1),
                number=category.group(2),
                items=tuple(items),
            )
        )
    return categories


def _stable_impl(value: str | None) -> str | None:
    if value is None:
        return None
    # Source ids and grouped source ids are language-independent. Prose status
    # descriptions are intentionally localized and are not treated as identity.
    if re.fullmatch(r"[a-z0-9][a-z0-9._/-]*(?:\s*\+\s*[a-z0-9][a-z0-9._/-]*)*", value):
        return value
    return None


def compare_catalogs(left: Path, right: Path) -> list[str]:
    a = parse_catalog(left)
    b = parse_catalog(right)
    errors: list[str] = []
    if len(a) != len(b):
        errors.append(f"category count mismatch: {len(a)} != {len(b)}")
        return errors

    for index, (left_category, right_category) in enumerate(zip(a, b, strict=True)):
        if (left_category.category_id, left_category.number) != (
            right_category.category_id,
            right_category.number,
        ):
            errors.append(
                "category identity mismatch at index "
                f"{index}: {(left_category.category_id, left_category.number)!r} != "
                f"{(right_category.category_id, right_category.number)!r}"
            )
            continue
        if len(left_category.items) != len(right_category.items):
            errors.append(
                f"{left_category.category_id}: item count mismatch "
                f"{len(left_category.items)} != {len(right_category.items)}"
            )
            continue
        for item_index, (left_item, right_item) in enumerate(
            zip(left_category.items, right_category.items, strict=True)
        ):
            prefix = f"{left_category.category_id}[{item_index}]"
            if left_item.status != right_item.status:
                errors.append(
                    f"{prefix}: status mismatch {left_item.status!r} != {right_item.status!r}"
                )
            if left_item.url != right_item.url:
                errors.append(f"{prefix}: url mismatch {left_item.url!r} != {right_item.url!r}")
            left_impl = _stable_impl(left_item.impl)
            right_impl = _stable_impl(right_item.impl)
            if left_impl is not None or right_impl is not None:
                if left_impl != right_impl:
                    errors.append(f"{prefix}: stable impl mismatch {left_impl!r} != {right_impl!r}")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Check structural parity between localized website source catalogs"
    )
    parser.add_argument("left", type=Path)
    parser.add_argument("right", type=Path)
    args = parser.parse_args()

    errors = compare_catalogs(args.left, args.right)
    if errors:
        for error in errors:
            print(error)
        raise SystemExit(1)
    total = sum(len(category.items) for category in parse_catalog(args.left))
    print(f"source catalog pair structurally aligned: {total} entries")


if __name__ == "__main__":
    main()
