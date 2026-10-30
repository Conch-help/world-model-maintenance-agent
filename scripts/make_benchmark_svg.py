"""Create a dependency-free SVG benchmark chart."""
from __future__ import annotations

import csv
import html
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artifacts"


def main() -> int:
    rows = list(csv.DictReader((ART / "benchmark.csv").open(encoding="utf-8-sig")))
    width, height = 1120, 520
    left, top, chart_h = 220, 70, 320
    max_profit = max(max(float(r["profit"]), 0.0) for r in rows)
    min_profit = min(min(float(r["profit"]), 0.0) for r in rows)
    span = max(1.0, max_profit - min_profit)
    colors = ["#7C8DA6", "#9AA8BA", "#F2B84B", "#5FC7B7", "#2F8FEA"]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#0B1524"/>',
        '<text x="42" y="38" fill="#F5F8FC" font-size="22" font-family="Segoe UI, Microsoft YaHei" font-weight="700">Maintenance policy benchmark · 10 unseen 168h scenarios</text>',
    ]
    zero_y = top + chart_h * max_profit / span
    parts.append(f'<line x1="{left}" y1="{zero_y:.1f}" x2="{width-50}" y2="{zero_y:.1f}" stroke="#52627A" stroke-width="1"/>')
    bar_h = chart_h / len(rows) * 0.62
    for idx, row in enumerate(rows):
        value = float(row["profit"])
        y = top + chart_h * (max_profit - max(value, 0.0)) / span
        if value < 0:
            y = zero_y
        bar_w = abs(value) / span * (width - left - 80)
        label = html.escape(row["policy"])
        delta = float(row["profit_delta_pct"])
        parts.append(f'<text x="42" y="{y + bar_h*0.7:.1f}" fill="#C8D4E5" font-size="15" font-family="Segoe UI, Microsoft YaHei">{label}</text>')
        parts.append(f'<rect x="{left}" y="{y:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" rx="6" fill="{colors[idx % len(colors)]}"/>')
        text_x = left + bar_w + 12 if value >= 0 else left + 12
        parts.append(f'<text x="{text_x:.1f}" y="{y + bar_h*0.7:.1f}" fill="#F5F8FC" font-size="14" font-family="Segoe UI">{value:,.0f} ({delta:+.1f}%)</text>')
    parts.append('</svg>')
    out = ART / "benchmark.svg"
    out.write_text("\n".join(parts), encoding="utf-8")
    print("wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
