#!/usr/bin/env python3
"""
Lightweight post-run checks for the V0-B 0.6 Pa Ar smoke test.

This script intentionally avoids ParaView dependencies. It scans the solver log
and latest-time ASCII fields for obvious failures and reports expected Ar
density from the ideal-gas law.
"""

import argparse
import math
import re
from pathlib import Path

R = 8.31446261815324
M_AR = 0.039948
P_TARGET = 0.6
T_TARGET = 1343.15


def foam_times(case):
    vals = []
    for p in case.iterdir():
        if not p.is_dir():
            continue
        try:
            vals.append((float(p.name), p))
        except ValueError:
            pass
    return sorted(vals)


def scalar_internal(path):
    if not path.exists():
        return None
    text = path.read_text(errors="replace")
    m = re.search(r"internalField\s+uniform\s+([-+0-9.eE]+)\s*;", text)
    return float(m.group(1)) if m else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("case", nargs="?", default=".")
    args = ap.parse_args()

    case = Path(args.case).resolve()
    rho_expected = P_TARGET * M_AR / (R * T_TARGET)

    print("=== V0-B 0.6 Pa Ar smoke-test check ===")
    print(f"case             : {case}")
    print(f"target pressure  : {P_TARGET:.9g} Pa")
    print(f"target temperature: {T_TARGET:.9g} K")
    print(f"ideal-gas rho(Ar): {rho_expected:.9e} kg/m3")

    logs = sorted(case.glob("log.compressibleLaserbeamFoam*"))
    if not logs:
        print("solver log       : NOT FOUND")
    else:
        log = logs[-1]
        text = log.read_text(errors="replace")
        fatal = (
            "FOAM FATAL ERROR" in text
            or "Floating point exception" in text
            or "MPI_ABORT" in text
        )
        ended = "End" in text
        print(f"solver log       : {log.name}")
        print(f"fatal marker     : {'YES' if fatal else 'no'}")
        print(f"End marker       : {'yes' if ended else 'NO'}")

        # Surface any explicit low-pressure-control printout from the patch.
        for key in (
            "rhoMinEOS",
            "pSmallSat",
            "phaseChangeRhoFloor",
            "partialMassRhoFloor",
            "recoveryRhoFloor",
            "implicitCouplingPressureFloor",
        ):
            hits = [ln.strip() for ln in text.splitlines() if key in ln]
            if hits:
                print(f"{key:28s}: {hits[-1]}")

    times = foam_times(case)
    if not times:
        print("time directories : none")
        raise SystemExit(1)

    latest_t, latest = times[-1]
    print(f"latest time      : {latest_t:g}")

    p = scalar_internal(latest / "p")
    prgh = scalar_internal(latest / "p_rgh")
    T = scalar_internal(latest / "T")
    aa = scalar_internal(latest / "alpha.air")
    am = scalar_internal(latest / "alpha.metal1")
    av = scalar_internal(latest / "alpha.metal1vapour")

    for name, value in (
        ("p uniform", p),
        ("p_rgh uniform", prgh),
        ("T uniform", T),
        ("alpha.air uniform", aa),
        ("alpha.metal1 uniform", am),
        ("alpha.metal1vapour uniform", av),
    ):
        print(f"{name:28s}: {value if value is not None else 'nonuniform/not-found'}")

    print()
    print("Interpretation:")
    print("- Nonuniform fields are normal after solver execution; inspect min/max with")
    print("  OpenFOAM postProcess/fieldMinMax if available.")
    print("- Passing this smoke test does NOT validate rarefied Ar dynamics.")
    print("- If p is driven toward 1, 1000 or 10000 Pa, another pressure guard remains active.")


if __name__ == "__main__":
    main()
