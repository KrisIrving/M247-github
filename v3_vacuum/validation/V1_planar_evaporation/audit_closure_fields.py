#!/usr/bin/env python3
"""Summarize written scalar fields across an OpenFOAM case's time directories."""
import argparse
import json
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "V0B_argon_smoke"))
from analyse_case import field_values  # noqa: E402

NUMBER = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
FIELDS = ("p", "T", "rho", "alpha.metal1", "alpha.metal1vapour",
          "c.metal1", "c.metal1vapour", "PhaseChangeRate")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("case", type=Path)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--times", nargs="+", type=float,
                        help="only print these times (JSON output still stores all times)")
    args = parser.parse_args()
    times = sorted((p for p in args.case.iterdir() if p.is_dir()
                    and NUMBER.fullmatch(p.name) and float(p.name) >= 0),
                   key=lambda p: float(p.name))
    rows = []
    for time_dir in times:
        row = {"time": float(time_dir.name), "fields": {}}
        for name in FIELDS:
            path = time_dir / name
            if not path.exists():
                continue
            values = field_values(path, magnitude=False)
            if values:
                row["fields"][name] = {
                    "min": min(values), "max": max(values),
                    "mean": sum(values) / len(values), "count": len(values),
                }
        rows.append(row)
    report = {"case": str(args.case), "times": rows}
    rendered = json.dumps(report, indent=2, allow_nan=False)
    if args.times:
        selected = {"case": str(args.case), "times": [r for r in rows
                    if any(math.isclose(r["time"], t, rel_tol=1e-8, abs_tol=1e-30)
                           for t in args.times)]}
        print(json.dumps(selected, indent=2, allow_nan=False))
    else:
        print(rendered)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(rendered + "\n")


if __name__ == "__main__":
    main()

