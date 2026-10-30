"""Sanitize AGH JSONL exports for public sharing."""
from __future__ import annotations
import json
from pathlib import Path
import re

KEEP_TYPES = {
    "session/start", "tool/call", "tool/result", "approval/asked", "approval/decided",
    "turn/start", "turn/end", "assistant/message", "user/message",
}
SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{10,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{10,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]{20,}"),
]


def sanitize(value):
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            low = key.lower()
            if low in {"authorization", "cookie", "set-cookie", "apikey", "api_key", "credentialref", "headers"}:
                continue
            if low == "route" and isinstance(item, str):
                out[key] = "<redacted-route>"
            else:
                out[key] = sanitize(item)
        return out
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    if isinstance(value, str):
        text = re.sub(r"[A-Za-z]:\\\\Users\\\\[^\"\\\\]+(?:\\\\[^\"]+)*", "<local-path>", value)
        text = re.sub(r"[A-Za-z]:/Users/[^\"\\\\]+(?:/[^\"]+)*", "<local-path>", text)
        for pattern in SECRET_PATTERNS:
            text = pattern.sub("<redacted-secret>", text)
        return text
    return value


def main(src: str, dst: str) -> int:
    source = Path(src)
    target = Path(dst)
    target.parent.mkdir(parents=True, exist_ok=True)
    with source.open(encoding="utf-8") as src_fh, target.open("w", encoding="utf-8") as dst_fh:
        for line in src_fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("type") not in KEEP_TYPES:
                continue
            row = sanitize(row)
            dst_fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    print("sanitized", target)
    return 0


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("src")
    parser.add_argument("dst")
    args = parser.parse_args()
    raise SystemExit(main(args.src, args.dst))
