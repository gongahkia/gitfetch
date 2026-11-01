"""Offline previews: PYTHONPATH=tests .venv/bin/python tests/preview_modern.py."""
import argparse
from pathlib import Path

from modern_fixtures import CASES, preview


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=CASES, default="standard-80x24")
    parser.add_argument("--ansi", action="store_true", help="Use the existing palette; emits only trusted SGR")
    parser.add_argument("--write", action="store_true", help="Regenerate all reviewed plain-text golden files")
    args = parser.parse_args()
    if args.write:
        root = Path(__file__).parent / "fixtures" / "modern"
        root.mkdir(parents=True, exist_ok=True)
        for name in CASES:
            (root / f"{name}.txt").write_text(preview(name) + "\n", encoding="utf-8")
    else:
        print(preview(args.case, ansi=args.ansi))


if __name__ == "__main__":
    main()
