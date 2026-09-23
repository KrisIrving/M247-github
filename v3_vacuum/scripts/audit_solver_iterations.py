#!/usr/bin/env python3
"""Summarize OpenFOAM equation-solver iteration caps in a solver log.

This reports iterative linear-system nonconvergence; it does not diagnose its
cause or infer field accuracy. Residuals belonging to different equations must
not be compared as if they had the same scaling.
"""
import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

NUMBER = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?"
SOLVE = re.compile(
    rf"^(\S+):\s+Solving for (\S+), Initial residual = ({NUMBER}), "
    rf"Final residual = ({NUMBER}), No Iterations (\d+)"
)


def audit(path, iteration_cap):
    counts = defaultdict(lambda: {
        "solves": 0, "cap_hits": 0, "max_iterations": 0,
        "max_hit_final_residual": 0.0, "worst_hit_initial_residual": 0.0,
    })
    steps, current_time, pending_dt, hits = [], None, None, []
    for line_no, line in enumerate(path.read_text(errors="replace").splitlines(), 1):
        match = re.match(rf"^deltaT = ({NUMBER})", line)
        if match:
            pending_dt = float(match[1])
        match = re.match(rf"^Time = ({NUMBER})\s*$", line)
        if match:
            current_time = float(match[1])
            steps.append({"time": current_time, "deltaT": pending_dt,
                          "linear_solves": 0, "cap_hits": 0})
        match = SOLVE.match(line)
        if not match:
            continue
        solver, field = match[1], match[2]
        initial, final, iterations = float(match[3]), float(match[4]), int(match[5])
        key = f"{field} [{solver}]"
        item = counts[key]
        item["solves"] += 1
        item["max_iterations"] = max(item["max_iterations"], iterations)
        if steps:
            steps[-1]["linear_solves"] += 1
        if iterations >= iteration_cap:
            item["cap_hits"] += 1
            item["max_hit_final_residual"] = max(item["max_hit_final_residual"], final)
            item["worst_hit_initial_residual"] = max(item["worst_hit_initial_residual"], initial)
            hits.append({"time": current_time, "line": line_no, "field": field,
                         "solver": solver, "iterations": iterations,
                         "initial_residual": initial, "final_residual": final})
            if steps:
                steps[-1]["cap_hits"] += 1
    return {
        "log": str(path), "iteration_cap": iteration_cap,
        "status": "CAP_HITS" if hits else "NO_CAP_HITS",
        "solves_by_equation_and_solver": dict(sorted(counts.items())),
        "steps_with_most_cap_hits": sorted(steps, key=lambda x: x["cap_hits"], reverse=True)[:20],
        "cap_hit_examples": hits[:50], "cap_hit_count": len(hits),
        "interpretation": "Iteration-cap hits are not convergence; normalized residuals only have meaning within their equation and settings.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("log", type=Path)
    parser.add_argument("--iteration-cap", type=int, default=1000)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    report = audit(args.log, args.iteration_cap)
    rendered = json.dumps(report, indent=2, allow_nan=False)
    print(rendered)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(rendered + "\n")


if __name__ == "__main__":
    main()
