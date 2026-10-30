import argparse
import json
from dataclasses import asdict
from wm_maint.adapters.daypsci import validate_file


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate authorized DAYPSCI CSV schema")
    parser.add_argument("--input", required=True)
    args = parser.parse_args()
    result = validate_file(args.input)
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    return 0 if result.valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
