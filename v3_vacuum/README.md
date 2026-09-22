# LaserBeamFoam V3 vacuum development

This directory contains the vacuum-model development path for the M247 LPBF project.

## Locked experimental target

- OpenFOAM: v2512
- LaserBeamFoam: V3/OpenFoam_com_main family
- Target chamber pressure: 0.6 Pa
- Backfill gas: Ar
- Preheat: 1070 degC = 1343.15 K
- Final process target: M247, 350 W, 1000 mm/s, continuous 2 mm melt track

The legacy OpenFOAM-10 case at repository root is intentionally left unchanged.

## Upstream source baseline used for this audit

Official repository: laserbeamfoam/LaserbeamFoam  
Branch: OpenFoam_com_main  
Audited upstream commit: 3c93f2657e089e22e9a8298648292969e85a4bad  
Commit date: 2026-09-11

Before running any validation case, record the local solver commit:

```bash
cd /path/to/LaserbeamFoam
git branch --show-current
git rev-parse HEAD
git log -1 --oneline
foamVersion
which compressibleLaserbeamFoam
```

If the local SHA differs from the audited SHA, rerun `scripts/check_v3_upstream.sh` and review the source differences before interpreting results.

## Development stages

1. **V0 source/equation verification**
   - audit pressure/density floors and low-pressure guards;
   - reproduce the implemented Clausius-Clapeyron and Hertz-Knudsen equations independently;
   - quantify the effect of each numerical floor.
2. **V1 planar evaporation CFD verification**
   - construct a minimal liquid/vapour/argon interface case;
   - compare CFD mass flux, latent heat and pressure response to the analytical oracle.
3. **V2 literature validation**
   - Calta et al. 2020: pressure-dependent LPBF depression morphology;
   - Bidare et al. 2018: sub-atmospheric LPBF down to 10 microbar (~1 Pa).
4. **V3 physics decision**
   - retain the current HK model if validation is adequate;
   - otherwise evaluate Schrage/Knudsen-layer corrections without double-counting recoil.
5. **M247 production model**
   - only after the vacuum model is verified/validated.

## Important modelling statement

At 0.6 Pa and 1343.15 K, ideal-gas Ar density is about 2.15e-6 kg/m3.
Using an Ar collision diameter of 3.40 Angstrom gives a mean free path of about
6.0e-2 m. For 0.1--1 mm LPBF length scales this implies Kn ~ 60--600.

Therefore the far-field argon phase is not a continuum flow in the strict
Navier-Stokes sense. The intended model is a **continuum metal-vapour model
coupled to an effective low-pressure reservoir**. Far-field argon velocities
must not be interpreted as quantitatively resolved rarefied-gas dynamics.

See `docs/vacuum_source_audit.md` for the detailed decisions.

## Run the current V0 analytical reference

```bash
cd v3_vacuum/validation/V0_HK_verification
python3 hk_reference.py
```

This writes `v0_hk_sweep.csv` and prints the target Ar density, mean free path,
Knudsen numbers and the effect of the current 1 Pa `pSmallSat` clamp.

