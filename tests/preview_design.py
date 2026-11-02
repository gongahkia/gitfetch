"""Offline design previews and intentional golden regeneration."""
import argparse
from pathlib import Path

from design_fixtures import CASES, preview


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', choices=CASES, default='balanced-80x24')
    parser.add_argument('--ansi', action='store_true')
    parser.add_argument('--write', action='store_true', help='Intentionally regenerate plain and ANSI fixtures')
    args = parser.parse_args()
    if args.write:
        root = Path(__file__).parent / 'fixtures' / 'design'
        root.mkdir(parents=True, exist_ok=True)
        for case in CASES:
            for ansi, suffix in [(False, 'txt'), (True, 'ansi')]:
                (root / f'{case}.{suffix}').write_text(preview(case, ansi=ansi) + '\n', encoding='utf-8')
    else:
        print(preview(args.case, ansi=args.ansi))


if __name__ == '__main__':
    main()
