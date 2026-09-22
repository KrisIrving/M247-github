# V0 Hertz-Knudsen analytical verification

This directory is the first verification stage for the LaserBeamFoam V3 vacuum
development.

It does not run OpenFOAM yet. It provides an independent analytical oracle for
the exact phase-change relations identified in the audited V3 source. This lets
us distinguish errors in the physical equation from errors introduced later by
VOF smearing, pressure coupling, timestep limits or density floors.

## Default M247 surrogate parameters

The defaults are inherited from the existing OF10 M247 case:

```text
P0        = 1.0e5 Pa
Tboil     = 3186 K
M         = 0.060 kg/mol
Lv        = 6.3e6 J/kg
sigmaEvap = 1.0
```

These values are only the V0 oracle defaults; the later V3 thermophysical
mapping will be audited separately.

## Run

```bash
python3 hk_reference.py
```

Outputs:

- terminal diagnostics;
- `v0_hk_sweep.csv`.

A useful explicit target run is:

```bash
python3 hk_reference.py \
    --argon-pressure 0.6 \
    --argon-temperature 1343.15 \
    --output v0_hk_sweep.csv
```

## Expected target diagnostics

Using the defaults above:

```text
ideal-gas Ar density ~ 2.1463e-6 kg/m3
Ar mean free path    ~ 6.0177e-2 m
Kn at 0.1 mm         ~ 602
Kn at 0.5 mm         ~ 120
Kn at 1.0 mm         ~ 60
```

For the current source-level `pSmallSat=1 Pa` clamp:

```text
Tsat(0.6 Pa), unclamped  ~ 1729.07 K
Tsat(0.6 Pa), 1 Pa clamp ~ 1763.32 K
artificial shift         ~ +34.26 K
```

This is why `pSmallSat` must be parameterized before claiming a 0.6 Pa model.

## Interpretation

The HK flux at high surface temperature can become nearly insensitive to the
difference between 1 Pa and 0.6 Pa because `Psat >> p`. That does **not** mean
the pressure clamp is harmless: the same clamp enters the inferred saturation
temperature used by the phase-change limiter and can move the low-pressure
equilibrium state by tens of kelvin.

## Next acceptance test

After the source floors are parameterized, V0-B will compare:

1. unmodified upstream solver with upstream defaults;
2. patched solver with the same defaults;
3. patched solver at 0.6 Pa with vacuum-specific parameters.

Case (1) and (2) should agree within numerical reproducibility. Only then will a
planar evaporation CFD verification be added.

