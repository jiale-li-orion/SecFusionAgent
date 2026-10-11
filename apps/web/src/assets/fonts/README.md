# Product typography

Manrope supplies Latin text. Noto Sans SC (SIL Open Font License 1.1, see NotoSans-LICENSE.txt) supplies Chinese UI labels in regular and bold weights. WOFF2 files are subsets of Noto Sans CJK SC, containing the Chinese UI characters in Product Web source as of 2026-10-11. Other article characters use the native CJK fallback stack.

To regenerate, collect CJK characters from src/**/*.ts and src/**/*.tsx, and run fonttools pyftsubset with --text-file, --flavor=woff2, --layout-features=* and --no-hinting. No external font service is used.
