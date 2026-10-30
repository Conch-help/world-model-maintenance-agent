import argparse
import json
from wm_maint.cmapss_scheduling import run_cmapss_scheduling


def main() -> int:
    parser = argparse.ArgumentParser(description="C-MAPSS maintenance scheduling comparison")
    parser.add_argument("--data-root", default="work/public_data")
    parser.add_argument("--out", default="artifacts/cmapss_scheduling.json")
    args = parser.parse_args()
    print(json.dumps(run_cmapss_scheduling(args.data_root, args.out), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
