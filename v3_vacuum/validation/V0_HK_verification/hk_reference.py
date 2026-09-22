#!/usr/bin/env python3
"""
V0 analytical reference for LaserBeamFoam V3 vacuum development.

This reproduces the Clausius-Clapeyron saturation pressure and the
Hertz-Knudsen-type net interfacial mass flux currently implemented in
compressibleLaserbeamFoam (OpenFoam_com_main, audited upstream SHA recorded in
the parent README).

It also exposes the effect of the current hard-coded pSmallSat=1 Pa on Tsat and
reports ideal-gas argon density / kinetic mean free path for the target chamber.

Only Python standard-library modules are required.
"""

import argparse
import csv
import math
from pathlib import Path

R = 8.31446261815324
KB = 1.380649e-23

DEFAULT_PRESSURES = [1e5, 1e4, 1e3, 1e2, 10.0, 1.0, 0.6, 0.1, 0.01]
DEFAULT_TEMPERATURES = [1700.0, 1800.0, 2000.0, 2500.0, 3000.0, 3186.0, 3500.0]


def psat_clausius_clapeyron(T, P0, Tboil, molar_mass, latent_heat):
    """LaserBeamFoam V3 Psat expression. molar_mass is in kg/mol."""
    K = molar_mass * latent_heat / (Tboil * R)
    return P0 * math.exp(K * (1.0 - Tboil / T))


def hk_net_mass_flux(
    T,
    p,
    P0,
    Tboil,
    molar_mass,
    latent_heat,
    x_liq=1.0,
    y_vap=1.0,
    sigma=1.0,
):
    """
    Net Hertz-Knudsen-type mass flux [kg/(m2 s)] matching the V3 source form:

      sigma*sqrt(M/(2*pi*R*T)) * (x*Psat - y*p)

    Positive = evaporation; negative = condensation.
    """
    psat = psat_clausius_clapeyron(T, P0, Tboil, molar_mass, latent_heat)
    return sigma * math.sqrt(molar_mass / (2.0 * math.pi * R * T)) * (
        x_liq * psat - y_vap * p
    )


def tsat_from_partial_pressure(
    p,
    P0,
    Tboil,
    molar_mass,
    latent_heat,
    x_liq=1.0,
    y_vap=1.0,
    p_floor=None,
):
    """
    Invert x*Psat(Tsat) = y*p.

    Set p_floor=1.0 to reproduce the current source-level pSmallSat clamp.
    """
    p_eff = max(p, p_floor) if p_floor is not None else p
    K = molar_mass * latent_heat / (Tboil * R)
    arg = max(y_vap * p_eff / (max(x_liq, 1e-12) * P0), 1e-15)
    denominator = max(1.0 - math.log(arg) / K, 0.05)
    return Tboil / denominator


def ideal_gas_density(p, T, molar_mass):
    return p * molar_mass / (R * T)


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
                "Psat_Pa",
                "HK_massFlux_kg_m2_s",
                "Tsat_noFloor_K",
                "Tsat_pSmallSat1Pa_K",
                "Tsat_floor_error_K",
            ]
        )

        for T in args.temperatures:
            psat = psat_clausius_clapeyron(
                T,
                args.P0,
                args.Tboil,
                args.molar_mass,
                args.latent_heat,
            )

            for p in args.pressures:
                flux = hk_net_mass_flux(
                    T,
                    p,
                    args.P0,
                    args.Tboil,
                    args.molar_mass,
                    args.latent_heat,
                    sigma=args.sigma,
                )
                ts_no_floor = tsat_from_partial_pressure(
                    p,
                    args.P0,
                    args.Tboil,
                    args.molar_mass,
                    args.latent_heat,
                )
                ts_1pa = tsat_from_partial_pressure(
                    p,
                    args.P0,
                    args.Tboil,
                    args.molar_mass,
                    args.latent_heat,
                    p_floor=1.0,
                )

                writer.writerow(
                    [
                        T,
                        p,
                        psat,
                        flux,
                        ts_no_floor,
                        ts_1pa,
                        ts_1pa - ts_no_floor,
                    ]
                )


def main():
    parser = argparse.ArgumentParser()

    # M247 surrogate values inherited from the existing OF10 case.
    parser.add_argument("--P0", type=float, default=1e5)
    parser.add_argument("--Tboil", type=float, default=3186.0)
    parser.add_argument(
        "--molar-mass",
        type=float,
        default=0.060,
        help="kg/mol",
    )
    parser.add_argument(
        "--latent-heat",
        type=float,
        default=6.3e6,
        help="J/kg",
    )
    parser.add_argument(
        "--sigma",
        type=float,
        default=1.0,
        help="evaporation accommodation coefficient",
    )
    parser.add_argument(
        "--pressures",
        type=float,
        nargs="+",
        default=DEFAULT_PRESSURES,
    )
    parser.add_argument(
        "--temperatures",
        type=float,
        nargs="+",
        default=DEFAULT_TEMPERATURES,
    )

    # Target vacuum diagnostics.
    parser.add_argument("--argon-pressure", type=float, default=0.6)
    parser.add_argument("--argon-temperature", type=float, default=1343.15)
    parser.add_argument("--argon-molar-mass", type=float, default=0.039948)
    parser.add_argument("--argon-diameter", type=float, default=3.40e-10)
    parser.add_argument(
        "--length-scales",
        type=float,
        nargs="+",
        default=[1e-4, 5e-4, 1e-3],
        help="m; used only for Knudsen-number diagnostics",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("v0_hk_sweep.csv"),
    )

    args = parser.parse_args()

    write_sweep(args.output, args)

    rho_ar = ideal_gas_density(
        args.argon_pressure,
        args.argon_temperature,
        args.argon_molar_mass,
    )
    lambda_ar = mean_free_path(
        args.argon_pressure,
        args.argon_temperature,
        args.argon_diameter,
    )

    print("=== LaserBeamFoam V3 V0 analytical reference ===")
    print(
        "M247 model: "
        f"P0={args.P0:g} Pa, "
        f"Tboil={args.Tboil:g} K, "
        f"M={args.molar_mass:g} kg/mol, "
        f"Lv={args.latent_heat:g} J/kg"
    )
    print(
        f"Ar target: p={args.argon_pressure:g} Pa, "
        f"T={args.argon_temperature:g} K"
    )
    print(f"Ideal-gas Ar density = {rho_ar:.9e} kg/m^3")
    print(f"Ar mean free path    = {lambda_ar:.9e} m")

    for length_scale in args.length_scales:
        print(
            f"Kn(L={length_scale:.3e} m) = "
            f"{lambda_ar / length_scale:.6g}"
        )

    ts_no_floor = tsat_from_partial_pressure(
        args.argon_pressure,
        args.P0,
        args.Tboil,
        args.molar_mass,
        args.latent_heat,
    )
    ts_1pa = tsat_from_partial_pressure(
        args.argon_pressure,
        args.P0,
        args.Tboil,
        args.molar_mass,
        args.latent_heat,
        p_floor=1.0,
    )

    print(
        f"Tsat(0.6 Pa), no pressure floor = "
        f"{ts_no_floor:.6f} K"
    )
    print(
        f"Tsat(0.6 Pa), pSmallSat=1 Pa    = "
        f"{ts_1pa:.6f} K"
    )
    print(
        f"Artificial Tsat shift           = "
        f"{ts_1pa - ts_no_floor:.6f} K"
    )
    print(f"Wrote sweep: {args.output}")


if __name__ == "__main__":
    main()
