# Product typography

Manrope supplies Latin text. Noto Sans SC UI supplies Chinese labels and common article characters in regular and bold weights. Both weights are local WOFF2 subsets of Noto Sans CJK SC 2.004 (Adobe, 2014–2021), under the SIL Open Font License 1.1 in `NotoSans-LICENSE.txt`. Copyright and license metadata are preserved in the fonts.

The 2026-10-14 subset contains all 6,763 GB2312 Han characters, current TS/TSX UI characters, and supported Chinese/full-width punctuation. This replaces the 650-character subset, which missed 41 characters already used by the interface. Characters outside this coverage still use the native CJK fallback stack. Regular is 1,978,452 bytes; bold is 2,022,344 bytes. The larger, cacheable fonts avoid per-machine fallback for common Chinese text; no external font service is used.

Rebuild from local upstream OTFs with Python 3, fonttools and brotli:

```bash
python3 scripts/subset-ui-fonts.py --regular /path/to/NotoSansCJKsc-Regular.otf --bold /path/to/NotoSansCJKsc-Bold.otf
python3 scripts/subset-ui-fonts.py --check
```

Run from `apps/web`; the script resolves output paths independently of the current directory. It preserves source naming/license metadata and timestamps, retains layout features, and removes hints. `--check` verifies both bundled fonts cover the common Han set and all current static UI Han characters without needing the source OTFs.
