#!/usr/bin/env python3
"""
V0 analytical oracle for LaserBeamFoam V3 vacuum development.

The phase-change functions reproduce the constants and algebra in
compressibleLaserbeamFoam at the audited upstream SHA. In particular, the
source currently uses R=8.314 exactly in the phase-change block.

The argon ideal-gas diagnostic uses the CODATA molar gas constant separately.
"""

import argparse
import csv
import math
from pathlib import Path

R_SOURCE = 8.314
R_SI = 8.31446261815324
KB = 1.380649e-23

DEFAULT_PRESSURES = [1e5, 1e4, 1e3, 1e2, 10.0, 1.0, 0.6, 0.1, 0.01]
DEFAULT_TEMPERATURES = [1700.0, 1800.0, 2000.0, 2500.0, 3000.0, 3186.0, 3500.0]


def psat_source(T, P0, Tboil, molar_mass, latent_heat):
    """Exact algebra/constants used by the audited V3 phase-change source."""
    Tsafe = max(T, 300.0)
    K = molar_mass * latent_heat / (Tboil * R_SOURCE)
    return P0 * math.exp(K * (1.0 - Tboil / Tsafe))


def hk_net_mass_flux_source(
    T,
    p,
    P0,
    Tboil,
    molar_mass,
    latent_heat,
    x_liq=1.0,
    y_vap=1.0,
    sigma_evap=1.0,
    sigma_cond=1.0,
):
    """
    Signed interfacial flux [kg/(m2 s)] corresponding to the source r*deltaPC.

    Positive = evaporation; negative = condensation.
    """
    Tsafe = max(T, 300.0)
    psat = psat_source(Tsafe, P0, Tboil, molar_mass, latent_heat)
    raw = math.sqrt(molar_mass / (2.0 * math.pi * R_SOURCE * Tsafe)) * (
        x_liq * psat - y_vap * p
    )
    return raw * (sigma_evap if raw > 0.0 else sigma_cond)


def tsat_source(
    p,
    P0,
    Tboil,
    molar_mass,
    latent_heat,
    x_liq=1.0,
    y_vap=1.0,
    p_small_sat=1.0,
):
    """Reproduce the audited source Tsat inversion, including its guards."""
    p_eff = max(p, p_small_sat)
    K = molar_mass * latent_heat / (Tboil * R_SOURCE)
    arg = max(y_vap * p_eff / (max(x_liq, 1e-12) * P0), 1e-15)
    denominator = max(1.0 - math.log(arg) / K, 0.05)
    return Tboil / denominator


def ideal_gas_density(p, T, molar_mass):
    """Physical diagnostic; uses CODATA R rather than the source HK constant."""
    return p * molar_mass / (R_SI * T)


def mean_free_path(p, T, collision_diameter):
    return KB * T / (
        math.sqrt(2.0) * math.pi * collision_diameter**2 * p
    )


def write_sweep(path, args):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "T_K",
                "p_Pa",
                "Psat_source_Pa",
                "HK_flux_source_kg_m2_s",
                "volumetric_rate_source_kg_m3_s",
                "Tsat_unclamped_K",
                "Tsat_upstream_1Pa_K",
                "Tsat_selectedFloor_K",
                "Tsat_upstream_error_K",
                "Tsat_selected_error_K",
            ]
        )

        for T in args.temperatures:
            psat = psat_source(
                T, args.P0, args.Tboil, args.molar_mass, args.latent_heat
            )

            for p in args.pressures:
                flux = hk_net_mass_flux_source(
                    T,
                    p,
                    args.P0,
                    args.Tboil,
                    args.molar_mass,
                    args.latent_heat,
                    x_liq=args.x_liq,
                    y_vap=args.y_vap,
                    sigma_evap=args.sigma_evap,
                    sigma_cond=args.sigma_cond,
                )
                volumetric_rate = flux / args.interface_thickness

                ts_unclamped = tsat_source(
                    p,
                    args.P0,
                    args.Tboil,
                    args.molar_mass,
                    args.latent_heat,
                    x_liq=args.x_liq,
                    y_vap=args.y_vap,
                    p_small_sat=0.0,
                )
                ts_upstream = tsat_source(
                    p,
                    args.P0,
                    args.Tboil,
                    args.molar_mass,
                    args.latent_heat,
                    x_liq=args.x_liq,
                    y_vap=args.y_vap,
                    p_small_sat=1.0,
                )
                ts_selected = tsat_source(
                    p,
                    args.P0,
                    args.Tboil,
                    args.molar_mass,
                    args.latent_heat,
                    x_liq=args.x_liq,
                    y_vap=args.y_vap,
                    p_small_sat=args.p_small_sat,
                )

                writer.writerow(
                    [
                        T,
                        p,
                        psat,
                        flux,
                        volumetric_rate,
                        ts_unclamped,
                        ts_upstream,
                        ts_selected,
                        ts_upstream - ts_unclamped,
                        ts_selected - ts_unclamped,
                    ]
                )


def build_parser():
    parser = argparse.ArgumentParser()

    # M247 surrogate values inherited from the existing OF10 case.
    parser.add_argument("--P0", type=float, default=1e5)
    parser.add_argument("--Tboil", type=float, default=3186.0)
    parser.add_argument("--molar-mass", type=float, default=0.060, help="kg/mol")
    parser.add_argument("--latent-heat", type=float, default=6.3e6, help="J/kg")
    parser.add_argument("--sigma-evap", type=float, default=1.0)
    parser.add_argument("--sigma-cond", type=float, default=1.0)
    parser.add_argument("--x-liq", type=float, default=1.0)
    parser.add_argument("--y-vap", type=float, default=1.0)
    parser.add_argument(
        "--interface-thickness",
        type=float,
        default=1e-5,
        help="m; only converts interfacial flux to source-style volumetric rate",
    )
    parser.add_argument(
        "--p-small-sat",
        type=float,
        default=1.0,
        help="Pa; selected Tsat pressure guard (upstream default 1 Pa)",
    )
    parser.add_argument("--pressures", type=float, nargs="+", default=DEFAULT_PRESSURES)
    parser.add_argument(
        "--temperatures", type=float, nargs="+", default=DEFAULT_TEMPERATURES
    )

    parser.add_argument("--argon-pressure", type=float, default=0.6)
    parser.add_argument("--argon-temperature", type=float, default=1343.15)
    parser.add_argument("--argon-molar-mass", type=float, default=0.039948)
    parser.add_argument("--argon-diameter", type=float, default=3.40e-10)
    parser.add_argument(
        "--length-scales",
        type=float,
        nargs="+",
        default=[1e-4, 5e-4, 1e-3],
        help="m; Knudsen-number diagnostics",
    )
    parser.add_argument("--output", type=Path, default=Path("v0_hk_sweep.csv"))
    return parser


def main():
    args = build_parser().parse_args()

    if args.interface_thickness <= 0:
        raise SystemExit("--interface-thickness must be > 0")
    if args.p_small_sat < 0:
        raise SystemExit("--p-small-sat must be >= 0")

    write_sweep(args.output, args)

    rho_ar = ideal_gas_density(
        args.argon_pressure, args.argon_temperature, args.argon_molar_mass
    )
    lambda_ar = mean_free_path(
        args.argon_pressure, args.argon_temperature, args.argon_diameter
    )

    print("=== LaserBeamFoam V3 V0 analytical source oracle ===")
    print(f"Audited source HK gas constant = {R_SOURCE:g} J/(mol K)")
    print(
        "M247 surrogate: "
        f"P0={args.P0:g} Pa, Tboil={args.Tboil:g} K, "
        f"M={args.molar_mass:g} kg/mol, Lv={args.latent_heat:g} J/kg"
    )
    print(
        f"Ar target: p={args.argon_pressure:g} Pa, "
        f"T={args.argon_temperature:g} K"
    )
    print(f"Ideal-gas Ar density = {rho_ar:.9e} kg/m^3")
    print(f"Ar mean free path    = {lambda_ar:.9e} m")
    for length_scale in args.length_scales:
        print(f"Kn(L={length_scale:.3e} m) = {lambda_ar/length_scale:.6g}")

    ts_unclamped = tsat_source(
        args.argon_pressure,
        args.P0,
        args.Tboil,
        args.molar_mass,
        args.latent_heat,
        p_small_sat=0.0,
    )
    ts_upstream = tsat_source(
        args.argon_pressure,
        args.P0,
        args.Tboil,
        args.molar_mass,
        args.latent_heat,
        p_small_sat=1.0,
    )
    ts_selected = tsat_source(
        args.argon_pressure,
        args.P0,
        args.Tboil,
        args.molar_mass,
        args.latent_heat,
        p_small_sat=args.p_small_sat,
    )

    print(f"Tsat(target), unclamped         = {ts_unclamped:.6f} K")
    print(f"Tsat(target), upstream 1 Pa     = {ts_upstream:.6f} K")
    print(f"Upstream artificial shift       = {ts_upstream-ts_unclamped:.6f} K")
    print(
        f"Tsat(target), selected floor {args.p_small_sat:g} Pa = "
        f"{ts_selected:.6f} K"
    )
    print(f"Selected-floor shift             = {ts_selected-ts_unclamped:.6f} K")
    print(f"Wrote sweep: {args.output}")


if __name__ == "__main__":
    main()
