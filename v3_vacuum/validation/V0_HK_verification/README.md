# V0 Hertz-Knudsen analytical verification

This is the first executable verification stage for the LaserBeamFoam V3
vacuum development. It does **not** run OpenFOAM.

Its job is to provide an independent oracle for the exact phase-change algebra
identified in the audited V3 source before VOF smearing, pressure coupling,
density guards and timestep limiters are introduced.

## Source fidelity

The oracle intentionally follows the audited source rather than silently
"improving" it:

- phase-change gas constant: `R = 8.314`, exactly as in the V3 source;
- kinetic temperature guard: `T >= 300 K`;
- Clausius-Clapeyron form used by `Psat`;
- HK signed flux form used before division by interface thickness;
- `xSmall=1e-12`, `argSmall=1e-15`, denominator floor 0.05 in `Tsat`;
- configurable `pSmallSat`, with 1 Pa reproducing upstream behaviour.

The argon ideal-gas diagnostic uses the CODATA gas constant separately because
it is a physical diagnostic, not part of the source oracle.

## Default M247 surrogate parameters

Inherited from the existing OF10 M247 case:

```text
P0        = 1.0e5 Pa
Tboil     = 3186 K
M         = 0.060 kg/mol
Lv        = 6.3e6 J/kg
sigmaEvap = 1.0
sigmaCond = 1.0
```

These are V0 verification defaults only. The V3 M247 thermophysical mapping is
a later audited stage.

## Run the regression tests

```bash
cd v3_vacuum/validation/V0_HK_verification
python3 -m unittest -v test_hk_reference.py
```

The tests check:

1. `Psat(Tboil)=P0`;
2. HK net flux is zero at equilibrium;
3. `Tsat` inverts `Psat` when the pressure guard is disabled;
4. the upstream 1 Pa guard changes the 0.6 Pa M247-surrogate equilibrium
   temperature by about 34.26 K;
5. the target 0.6 Pa Ar ideal-gas density is about 2.146e-6 kg/m3.

## Generate the pressure/temperature sweep

```bash
python3 hk_reference.py
```

or explicitly:

```bash
python3 hk_reference.py \
    --argon-pressure 0.6 \
    --argon-temperature 1343.15 \
    --p-small-sat 1.0 \
    --output v0_hk_sweep.csv
```

To examine a candidate pressure guard without changing source:

```bash
python3 hk_reference.py --p-small-sat 0.1
```

## Output columns

`v0_hk_sweep.csv` contains:

- `Psat_source_Pa`
- `HK_flux_source_kg_m2_s`
- source-style volumetric rate `flux/interface_thickness`
- unclamped `Tsat`
- upstream 1 Pa `Tsat`
- selected-floor `Tsat`
- the corresponding artificial temperature shifts

## Expected target diagnostics

At 0.6 Pa, 1343.15 K Ar:

```text
rho_Ar  ~ 2.146e-6 kg/m3
lambda  ~ 6.02e-2 m
Kn(0.1 mm) ~ 602
Kn(0.5 mm) ~ 120
Kn(1.0 mm) ~ 60
```

For the inherited M247 surrogate:

```text
Tsat(0.6 Pa), unclamped  ~ 1729.1 K
Tsat(0.6 Pa), 1 Pa guard ~ 1763.3 K
shift                    ~ +34.26 K
```

The high-temperature HK flux may be weakly sensitive to 0.6 versus 1 Pa when
`Psat >> p`; this does **not** make the clamp harmless because the same
pressure guard enters the equilibrium-temperature limiter.

## Acceptance status

- [x] source equations independently reproduced
- [x] source constants mirrored explicitly
- [x] oracle unit tests added
- [ ] patched solver compiled under OpenFOAM v2512
- [ ] patched-default regression against unmodified upstream
- [ ] 0.6 Pa gas-only smoke test
- [ ] V1 planar evaporation CFD verification

Do not use V0-A alone as evidence that the CFD model is valid at 0.6 Pa.
