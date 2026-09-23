#!/usr/bin/env python3
"""Fail-closed checks of serial, uncompressed ASCII V0-B internal cell fields.

Reports all written times, actual density, velocity magnitudes, completion and
timestep history. Use native fieldMinMax as an independent cross-check.
This is a stationary screen, not validation of evaporation or rarefied flow.
"""
import argparse
import json
import math
import re
from pathlib import Path

RHO_TARGET = 0.6 * 0.039948 / (8.31446261815324 * 1343.15)
FIELDS = ("p", "p_rgh", "rho", "T", "U", "alpha.air",
          "alpha.metal1", "alpha.metal1vapour")
NUMBER = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?"


def field_values(path, magnitude=True):
    text = path.read_text()
    if re.search(r"\bformat\s+binary", text):
        raise ValueError(f"Binary fields unsupported: {path}")
    text = re.sub(r"/\*.*?\*/|//[^\n]*", "", text, flags=re.S)
    vector = bool(re.search(r"\bclass\s+volVectorField", text))
    uniform = re.search(r"internalField\s+uniform\s+([^;]+);", text)
    if uniform:
        raw, count = uniform[1], 1
    else:
        match = re.search(
            r"internalField\s+nonuniform\s+List<(scalar|vector)>\s+(\d+)\s*\((.*?)\)\s*;",
            text, re.S)
        if not match:
            raise ValueError(f"Missing/unsupported internalField: {path}")
        count, raw = int(match[2]), match[3]
    values = [float(x) for x in raw.replace("(", " ").replace(")", " ").split()]
    if len(values) != count * (3 if vector else 1) or not values:
        raise ValueError(f"Wrong field length: {path}")
    if not all(math.isfinite(x) for x in values):
        raise ValueError(f"Nonfinite field: {path}")
    if vector and magnitude:
        return [math.sqrt(sum(v*v for v in values[i:i+3]))
                for i in range(0, len(values), 3)]
    return values


def analyse(case):
    errors = []
    log_path = case / "log.compressibleLaserbeamFoam"
    log = log_path.read_text(errors="replace") if log_path.exists() else ""
    if not re.search(r"^End\s*$", log, re.M):
        errors.append("Solver has no standalone End marker")
    failure_log = "\n".join(line for line in log.splitlines()
                            if "floating point exception trapping" not in line.lower())
    if re.search(r"FOAM FATAL|Floating point exception|MPI_ABORT|Segmentation fault", failure_log, re.I):
        errors.append("Fatal solver marker")
    control = (case / "system/controlDict").read_text()
    end_match = re.search(rf"\bendTime\s+({NUMBER})\s*;", control)
    if not end_match:
        raise ValueError("Missing numeric endTime")
    end = float(end_match[1])
    log_times = [float(x) for x in re.findall(rf"^Time = ({NUMBER})\s*$", log, re.M)]
    if not log_times or not math.isclose(log_times[-1], end, rel_tol=1e-6, abs_tol=1e-15):
        errors.append("Solver did not reach configured endTime")
    times = []
    for p in case.iterdir():
        if p.is_dir() and re.fullmatch(NUMBER, p.name) and float(p.name) > 0:
            times.append((float(p.name), p))
    times.sort()
    if not times or not math.isclose(times[-1][0], end, rel_tol=1e-6, abs_tol=1e-15):
        errors.append("No final-time written fields")
    extrema = {}
    for _, folder in times:
        for name in FIELDS:
            try:
                values = field_values(folder / name)
            except (ValueError, OSError) as exc:
                errors.append(str(exc))
                continue
            low, high = min(values), max(values)
            old = extrema.setdefault(name, {"min": low, "max": high})
            old["min"], old["max"] = min(old["min"], low), max(old["max"], high)
    targets = {"p": (0.6, 0.6e-4), "p_rgh": (0.6, 0.6e-4),
               "rho": (RHO_TARGET, RHO_TARGET*1e-4), "T": (1343.15, 1e-3),
               "U": (0, 1e-6), "alpha.air": (1, 1e-10),
               "alpha.metal1": (0, 1e-10), "alpha.metal1vapour": (0, 1e-10)}
    for name, (target, tolerance) in targets.items():
        if name not in extrema:
            errors.append(f"Missing result field {name}")
        elif any(abs(v-target) > tolerance for v in extrema[name].values()):
            errors.append(f"{name} outside target {target} +/- {tolerance}")
    steps = [float(x) for x in re.findall(rf"^deltaT = ({NUMBER})", log, re.M)]
    controls = {}
    for key in ("rhoMinEOS", "pSmallSat", "phaseChangeRhoFloor", "partialMassRhoFloor",
                "recoveryRhoFloor", "implicitCouplingPressureFloor"):
        match = re.search(rf"^\s*{key}\s*=\s*({NUMBER})", log, re.M)
        controls[key] = float(match[1]) if match else None
    for rel, key in (("system/controlDict", "acousticPressureFloor"),
                     ("constant/thermophysicalProperties", "pMin")):
        match = re.search(rf"\b{key}\s+({NUMBER})\s*;", (case/rel).read_text())
        controls[key] = float(match[1]) if match else None
    return {
        "status": "FAIL" if errors else "PASS", "case": str(case),
        "scope": "stationary reservoir screen; written internal cell fields",
        "endTime": end, "last_solver_time": log_times[-1] if log_times else None,
        "written_times_checked": len(times), "rho_expected": RHO_TARGET,
        "field_extrema_all_written_times": extrema, "active_controls": controls,
        "timestep": {"count": len(steps), "min": min(steps) if steps else None,
                     "max": max(steps) if steps else None, "history": steps},
        "linear_solves_at_1000_iterations": len(re.findall(r"No Iterations 1000\b", log)),
        "floor_interpretation": "p/rho can be compared with guards; inactive phase-change branches are untested",
        "errors": errors,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("case", nargs="?", type=Path, default=Path("."))
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    try:
        report = analyse(args.case.resolve())
    except (OSError, ValueError) as exc:
        report = {"status": "FAIL", "errors": [str(exc)]}
    rendered = json.dumps(report, indent=2, allow_nan=False)
    if args.json:
        args.json.write_text(rendered + "\n")
    concise = {k: v for k, v in report.items() if k != "timestep"}
    if "timestep" in report:
        concise["timestep"] = {k: v for k, v in report["timestep"].items() if k != "history"}
    print(json.dumps(concise, indent=2, allow_nan=False))
    raise SystemExit(0 if report["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
