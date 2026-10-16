"""Rebuild the bundled Chinese UI fonts from local, OFL-licensed Noto OTFs.

Requires fonttools and brotli. --check only inspects bundled character coverage.
"""

import argparse
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "src/assets/fonts"


def characters() -> set[int]:
    chars: set[str] = set()
    for high in range(0xB0, 0xF8):
        for low in range(0xA1, 0xFF):
            try:
                chars.update(bytes((high, low)).decode("gb2312"))
            except UnicodeDecodeError:
                pass
    chars.update(chr(code) for code in range(0x3000, 0x3040))
    chars.update(chr(code) for code in range(0xFF01, 0xFF61))
    for path in sorted((ROOT / "src").rglob("*")):
        if path.suffix in {".ts", ".tsx"}:
            chars.update(c for c in path.read_text() if 0x3400 <= ord(c) <= 0x9FFF)
    return {ord(c) for c in chars}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--regular", type=Path)
    parser.add_argument("--bold", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if not args.check and not (args.regular and args.bold):
        parser.error("supply --regular and --bold local Noto Sans CJK SC OTF paths")
    requested = characters()
    for weight, source in (("Regular", args.regular), ("Bold", args.bold)):
        target = DEST / f"NotoSansSC-UI-{weight}.woff2"
        if not args.check:
            font = TTFont(source, recalcTimestamp=False)
            # Reserved punctuation code points without source glyphs are omitted.
            selected = requested & set(font.getBestCmap())
            options = subset.Options()
            options.hinting = False
            options.layout_features = ["*"]
            options.name_IDs = ["*"]
            cutter = subset.Subsetter(options=options)
            cutter.populate(unicodes=selected)
            cutter.subset(font)
            font.flavor = "woff2"
            font.save(target)
            font.close()
        with TTFont(target) as font:
            required_han = {c for c in requested if 0x3400 <= c <= 0x9FFF}
            missing = required_han - set(font.getBestCmap())
            if missing:
                raise SystemExit(f"{weight}: missing {''.join(map(chr, sorted(missing)))}")
            print(
                f"{weight}: {len(required_han)} required Han characters covered; "
                f"{target.stat().st_size:,} bytes"
            )


if __name__ == "__main__":
    main()
