import argparse
import json
from wm_maint.tep_validation import run_tep_validation


def main() -> int:
    parser = argparse.ArgumentParser(description="Tennessee Eastman external validation")
    parser.add_argument("--data-root", default="work/public_data")
    parser.add_argument("--out", default="artifacts/tep_validation.json")
    args = parser.parse_args()
    print(json.dumps(run_tep_validation(args.data_root, args.out), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
