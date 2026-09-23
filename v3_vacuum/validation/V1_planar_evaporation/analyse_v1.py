#!/usr/bin/env python3
"""Audit a source-faithful planar evaporation run against the V0 HK oracle."""
import argparse
import json
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "V0_HK_verification"))
from hk_reference import hk_net_mass_flux_source  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "V0B_argon_smoke"))
from analyse_case import field_values  # noqa: E402

NUMBER = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?"


def analyse(args):
    log_path = args.case / "log.compressibleLaserbeamFoam"
    log = log_path.read_text(errors="replace")
    steps = []
    current = None
    for line in log.splitlines():
        m = re.match(rf"^Time = ({NUMBER})\s*$", line)
        if m:
            current = {"time_s": float(m[1]), "deltaT_s": None,
                       "evap_kg_s": None, "cond_kg_s": None,
                       "clamp_energy": None, "clamp_mass": None,
                       "clamp_volume": None, "closure_max_abs_dev": None,
                       "closure_capped_cells": None, "pair_total_kg": None,
                       "liquid_kg": None, "vapour_kg": None}
            steps.append(current)
            continue
        if current is None:
            continue
        m = re.match(rf"^deltaT = ({NUMBER})", line)
        if m:
            current["deltaT_s"] = float(m[1])
        m = re.search(rf"clamped cells ENERGY/MASS/VOLUME.*?: (\d+)/(\d+)/(\d+)", line)
        if m:
            current["clamp_energy"], current["clamp_mass"], current["clamp_volume"] = map(int, m.groups())
        m = re.search(rf"integrated evap = ({NUMBER}) kg/s, cond = ({NUMBER}) kg/s", line)
        if m:
            current["evap_kg_s"], current["cond_kg_s"] = map(float, m.groups())
        m = re.search(rf"volume closure defect.*max\|dev\| = ({NUMBER})", line)
        if m:
            current["closure_max_abs_dev"] = float(m[1])
        m = re.search(r"closure feedback: relax = [^,]+, capped cells = (\d+)", line)
        if m:
            current["closure_capped_cells"] = int(m[1])
        m = re.search(rf"metal1\+metal1vapour\s*=\s*({NUMBER}).*?\(liq\s+({NUMBER}).*?vap\s+({NUMBER})", line)
        if m:
            current["pair_total_kg"], current["liquid_kg"], current["vapour_kg"] = map(float, m.groups())

    failure_log = re.sub(r"floating point exception trapping enabled", "", log, flags=re.I)
    complete = bool(re.search(r"^End\s*$", log, re.M)) and not re.search(r"FOAM FATAL|Floating point exception|MPI_ABORT", failure_log, re.I)
    dt_matches = re.findall(rf"^deltaT = ({NUMBER})", log, re.M)
    for i, step in enumerate(steps):
        if i < len(dt_matches):
            step["deltaT_s"] = float(dt_matches[i])

    geometry = {}
    geometry_file = args.case / "V1_GEOMETRY.txt"
    if geometry_file.exists():
        for line in geometry_file.read_text().splitlines():
            if "=" in line:
                k,v=line.split("=",1)
                try: geometry[k.strip()]=float(v)
                except ValueError: pass
    effective_area = args.effective_area_m2 or geometry.get("effective_area_m2", 3e-8)
    cell_volume = args.cell_volume_m3 or geometry.get("cell_volume_m3", 9.375e-15)
    psat_hk = hk_net_mass_flux_source(
        args.temperature, args.pressure, args.P0, args.Tboil,
        args.molar_mass_kg_mol, args.latent_heat_J_kg,
        x_liq=1.0, y_vap=1.0, sigma_evap=args.sigma_evap, sigma_cond=args.sigma_cond)
    expected_rate = psat_hk * effective_area
    first_rate = (steps[0]["evap_kg_s"] + steps[0]["cond_kg_s"]) if steps and steps[0]["evap_kg_s"] is not None and steps[0]["cond_kg_s"] is not None else None
    first_error = abs(first_rate - expected_rate) / abs(expected_rate) if first_rate is not None and expected_rate else None
    rates_ok = bool(steps) and all(s["evap_kg_s"] is not None and s["cond_kg_s"] is not None for s in steps)
    caps = {key: sum((s[key] or 0) for s in steps) for key in ("clamp_energy", "clamp_mass", "clamp_volume")}
    pair_totals = [s["pair_total_kg"] for s in steps if s["pair_total_kg"] is not None]
    total_drift = ((max(pair_totals) - min(pair_totals)) / max(abs(pair_totals[0]), 1e-300)) if pair_totals else None
    transfer_checks = []
    for prev, cur in zip(steps, steps[1:]):
        if None in (prev["vapour_kg"], cur["vapour_kg"], prev["liquid_kg"], cur["liquid_kg"], cur["evap_kg_s"], cur["cond_kg_s"], cur["deltaT_s"]):
            continue
        source_mass = (cur["evap_kg_s"] + cur["cond_kg_s"]) * cur["deltaT_s"]
        vap_gain = cur["vapour_kg"] - prev["vapour_kg"]
        liq_loss = prev["liquid_kg"] - cur["liquid_kg"]
        scale = max(abs(source_mass), abs(vap_gain), abs(liq_loss), 1e-300)
        transfer_checks.append({"time_s": cur["time_s"], "source_mass_kg": source_mass,
                                "vapour_gain_kg": vap_gain, "liquid_loss_kg": liq_loss,
                                "vapour_relative_error": abs(vap_gain-source_mass)/scale,
                                "liquid_relative_error": abs(liq_loss-source_mass)/scale})
    # Vapor gain has much finer print resolution than the dense liquid mass;
    # the liquid difference can round to zero when dt is deliberately tiny.
    mass_step_error = max((c["vapour_relative_error"] for c in transfer_checks), default=None)
    closure_caps = sum((s["closure_capped_cells"] or 0) > 0 for s in steps)
    closure_dev = max((s["closure_max_abs_dev"] for s in steps if s["closure_max_abs_dev"] is not None), default=None)
    thermo_path = args.case / "constant/thermophysicalProperties"
    thermo_text = thermo_path.read_text(errors="replace") if thermo_path.exists() else ""
    closure_settings = {}
    for key, default in (("closureRelax", 0.5), ("closureVolLimit", 0.02), ("implicitVolLimit", 0.2)):
        match = re.search(rf"^\s*{key}\s+({NUMBER})\s*;", thermo_text, re.M)
        closure_settings[key] = float(match[1]) if match else default
    solver_cap_hits = len(re.findall(r"No Iterations 1000\b", log))
    latent_report = None
    time_dirs = sorted((p for p in args.case.iterdir() if p.is_dir() and re.fullmatch(NUMBER, p.name) and float(p.name) > 0), key=lambda p: float(p.name))
    if time_dirs:
        folder = time_dirs[0]
        alpha_liq = field_values(folder / "alpha.metal1", magnitude=False)
        alpha_vap = field_values(folder / "alpha.metal1vapour", magnitude=False)
        mass_dot = field_values(folder / "mass_dot", magnitude=False)
        rcv = [a/args.liquid_Cv_J_kgK + b/args.vapour_Cv_J_kgK for a,b in zip(alpha_liq,alpha_vap)]
        if len(rcv) == len(mass_dot) and all(v > 0 for v in rcv):
            latent_power = sum((q/cv)*cell_volume for q,cv in zip(mass_dot,rcv))
            expected_power = (steps[0]["evap_kg_s"] + steps[0]["cond_kg_s"])*args.latent_heat_J_kg if steps else None
            latent_report = {"integrated_latent_sink_W": latent_power,
                             "source_mass_times_L_W": expected_power,
                             "relative_identity_error": abs(latent_power-expected_power)/max(abs(expected_power),1e-300) if expected_power is not None else None,
                             "sign": "positive source means sink because TEqn contains -mass_dot"}
    checks = {
        "completed": complete,
        "has_rates_every_step": rates_ok,
        "closure_feedback_enabled": closure_settings["closureRelax"] > 0,
        "first_step_hk_relative_error_le_5pct": first_error is not None and first_error <= 0.05,
        "no_energy_mass_volume_rate_caps": all(v == 0 for v in caps.values()),
        "pair_mass_drift_le_1e-8": total_drift is not None and total_drift <= 1e-8,
        "per_step_phase_transfer_le_1pct": mass_step_error is not None and mass_step_error <= 0.01,
        "latent_source_mass_times_L_identity_le_5pct": latent_report is not None and latent_report["relative_identity_error"] <= 0.05,
        "no_closure_volume_caps_and_defect_le_5pct": closure_caps == 0 and closure_dev is not None and closure_dev <= 0.05,
        "zero_linear_iteration_cap_hits": solver_cap_hits == 0,
    }
    return {
        "status": "PASS" if all(checks.values()) else "NEEDS_REVIEW",
        "scope": "planar source/oracle rate and paired partial-mass balance; not a physical M247 validation",
        "case": str(args.case), "source_sha": "3c93f2657e089e22e9a8298648292969e85a4bad",
        "parameters": {"T_K": args.temperature, "p_Pa": args.pressure, "P0_Pa": args.P0,
                       "Tboil_K": args.Tboil, "molar_mass_kg_mol": args.molar_mass_kg_mol,
                       "latent_heat_J_kg": args.latent_heat_J_kg,
                       "effective_area_m2": effective_area, "geometry": geometry},
        "oracle": {"HK_flux_kg_m2_s": psat_hk, "expected_integrated_rate_kg_s": expected_rate,
                   "first_CFD_integrated_rate_kg_s": first_rate, "first_relative_error": first_error},
        "run": {"completed": complete, "steps": len(steps), "time_end_s": steps[-1]["time_s"] if steps else None,
                "energy_mass_volume_cap_totals": caps, "solver_iteration_cap_hits": solver_cap_hits,
                "paired_mass_relative_drift": total_drift, "max_per_step_transfer_relative_error": mass_step_error,
                "steps_with_closure_capped_cells": closure_caps, "max_volume_closure_abs_deviation": closure_dev,
                "closure_settings": closure_settings},
        "closure_trajectory": [{"time_s": s["time_s"],
                                 "net_hk_kg_s": (s["evap_kg_s"] + s["cond_kg_s"])
                                 if s["evap_kg_s"] is not None and s["cond_kg_s"] is not None else None,
                                 "max_abs_volume_defect": s["closure_max_abs_dev"],
                                 "capped_cells": s["closure_capped_cells"]} for s in steps],
        "latent_energy": latent_report,
        "checks": checks,
        "transfer_check_count": len(transfer_checks),
        "worst_transfer_check": max(transfer_checks, key=lambda c: max(c["vapour_relative_error"],c["liquid_relative_error"])) if transfer_checks else None,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("case", type=Path)
    p.add_argument("--temperature", type=float, default=2000.0)
    p.add_argument("--pressure", type=float, default=0.6)
    p.add_argument("--P0", type=float, default=1e5)
    p.add_argument("--Tboil", type=float, default=2900.0)
    p.add_argument("--molar-mass-kg-mol", type=float, default=0.05)
    p.add_argument("--latent-heat-J-kg", type=float, default=1e6)
    p.add_argument("--effective-area-m2", type=float)
    p.add_argument("--liquid-Cv-J-kgK", type=float, default=800.0)
    p.add_argument("--vapour-Cv-J-kgK", type=float, default=1039.0)
    p.add_argument("--cell-volume-m3", type=float)
    p.add_argument("--sigma-evap", type=float, default=1.0)
    p.add_argument("--sigma-cond", type=float, default=1.0)
    p.add_argument("--json", type=Path)
    args = p.parse_args()
    report = analyse(args)
    rendered = json.dumps(report, indent=2, allow_nan=False)
    print(rendered)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(rendered + "\n")
    raise SystemExit(0 if report["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()

