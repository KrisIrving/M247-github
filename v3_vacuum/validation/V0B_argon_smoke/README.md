# V0-B: patched-default regression and 0.6 Pa Ar smoke test

This stage is the first OpenFOAM execution gate for the LaserBeamFoam V3
vacuum-development path.

It has two independent purposes:

1. **patched-default regression** -- prove that
   `0001-parameterize-low-pressure-floors.patch` preserves upstream behaviour
   when all new controls are omitted;
2. **0.6 Pa Ar smoke test** -- prove that the patched solver can hold a
   stationary low-pressure Ar reservoir without laser heating, melting or
   evaporation obscuring the pressure/EOS behaviour.

Do not use this stage as validation of rarefied-gas flow. The 0.6 Pa Ar field is
only an effective pressure reservoir.

## A. Patched-default regression

Use the official upstream case

`tutorials/compressiblelaserbeamFoam/LPBF_small_vapour`

at the audited upstream SHA:

`3c93f2657e089e22e9a8298648292969e85a4bad`.

Run it once with the unmodified solver and once after applying the vacuum patch,
without adding any new vacuum controls to the case dictionaries.

Recommended workflow:

```bash
# 1. clean upstream checkout at audited SHA
git checkout 3c93f2657e089e22e9a8298648292969e85a4bad

# 2. compile unmodified source and save executable
./Allwmake
cp "$(which compressibleLaserbeamFoam)" ./compressibleLaserbeamFoam.upstream

# 3. apply project patch
bash /path/to/M247-github/v3_vacuum/patches/apply_vacuum_patch.sh "$PWD"

# 4. rebuild and save patched executable
./Allwmake
cp "$(which compressibleLaserbeamFoam)" ./compressibleLaserbeamFoam.patched
```

Run the same copied tutorial with the two executables. At minimum compare:

- end time reached;
- no FOAM FATAL ERROR;
- global min/max of `p`, `rho`, `T`, `U`;
- phase masses;
- `PhaseChangeRate` extrema if written;
- latest-time field checksums only as a diagnostic, not as the sole criterion.

The patch is acceptable only if differences are consistent with solver
round-off / run-to-run non-bitwise reproducibility and there is no systematic
physics change.

## B. Generate the 0.6 Pa Ar smoke case

The smoke case is generated from the exact official
`LPBF_small_vapour` tutorial belonging to the local audited source. This avoids
silently freezing a stale copy of the V3 tutorial in this repository.

```bash
cd v3_vacuum/validation/V0B_argon_smoke

bash prepare_case.sh \
    /path/to/LaserbeamFoam \
    ./case_V0B_Ar_0p6Pa
```

The generator deliberately keeps the phase names `metal1`,
`metal1vapour`, and `air` used by the official tutorial. In this V0-B case
only, **the phase named `air` is physically repurposed as argon**. Renaming the
phase is postponed to the final M247 case so this smoke test perturbs as little
of the upstream tutorial structure as possible.

The generated case has:

- no laser power;
- no DEM / powder initialisation;
- `alpha.air = 1` everywhere;
- condensed and metal-vapour volume fractions zero;
- `T = 1343.15 K`;
- `p = p_rgh = 0.6 Pa`;
- top pressure reservoir = 0.6 Pa;
- Ar ideal-gas EOS with `M = 39.948 g/mol`;
- vacuum numerical controls explicitly written.

Run:

```bash
cd case_V0B_Ar_0p6Pa
bash Allrun
```

Then analyse:

```bash
python3 ../analyse_case.py .
```

## Initial vacuum-control values

These are **screening values**, not production values:

```text
pMin                          0.06 Pa
rhoMinEOS                     1e-8 kg/m3
pSmallSat                     0.06 Pa
phaseChangeRhoFloor           1e-7 kg/m3
partialMassRhoFloor           1e-8 kg/m3
recoveryRhoFloor              1e-8 kg/m3
implicitCouplingPressureFloor 0.06 Pa
acousticPressureFloor         0.06 Pa
```

They are intentionally below the target Ar density / chamber pressure so that
V0-B can reveal whether the solver has any other hidden floor. They are not yet
accepted for M247.

## V0-B acceptance criteria

For the no-laser, all-Ar test:

1. the solver reaches the requested end time without fatal error;
2. `p` remains positive and close to 0.6 Pa;
3. no numerical floor forces `p` toward 1 Pa, 1 kPa or 10 kPa;
4. Ar density remains consistent with the ideal-gas scale
   `rho ~ 2.146e-6 kg/m3` at 1343.15 K;
5. `|U|` remains numerically negligible for the initially uniform reservoir;
6. metal and metal-vapour volume fractions remain negligible;
7. decreasing the numerical floors by another decade does not materially
   change the stationary state.

If this fails, stop before V1 planar evaporation and identify the active source
term / limiter first.
