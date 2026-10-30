from pathlib import Path
import argparse
import json
import sys

from wm_maint.external_validation import validate_cmapss


def main() -> int:
    parser = argparse.ArgumentParser(description="External C-MAPSS validation")
    parser.add_argument("--data-root", default="work/public_data")
    parser.add_argument("--out", default="artifacts/cmapss_validation.json")
    parser.add_argument("--fd", type=int, default=1)
    args = parser.parse_args()
    result = validate_cmapss(args.data_root, args.out, fd=args.fd)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
