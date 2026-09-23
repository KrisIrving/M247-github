# V1 planar evaporation verification

This calibration case checks the LaserbeamFoam V3 source against a Hertz–Knudsen (HK) oracle before attempting a laser track or powder bed. It tests source integration, phase-pair mass transfer, latent-energy coupling, and sensitivity to mesh, time step, diffuse-interface width, temperature, pressure, condensation sign, and numerical floors. It is **not** validation of M247 properties or a full vacuum LPBF experiment.

## Reproduce

Run on the Linux OpenFOAM v2512 environment with source revision `3c93f2657e089e22e9a8298648292969e85a4bad` (LaserbeamFoam V3). From the repository root:

```bash
source /path/to/OpenFOAM-v2512/etc/bashrc
bash v3_vacuum/validation/V1_planar_evaporation/prepare_case.sh \
  /path/to/LaserbeamFoam-V3 /path/to/fresh-case 2000 0.6 1e-14 2 40 1e-5 1
cd /path/to/fresh-case
bash Allrun
python3 /path/to/M247-github/v3_vacuum/validation/V1_planar_evaporation/analyse_v1.py \
  /path/to/fresh-case --json result.json
```

Arguments are solver source, fresh output directory, initial temperature (K), initial pressure (Pa), time step (s), step count, z cells, diffuse-band thickness (m), and numerical-floor scale. The prepared case uses a flat interface, zero laser power, closed velocity boundaries, and a two-cell diffuse band by default. It skips `setSolidFraction`, which would overwrite the intended planar phase initialization.

The EOS uses `rho0=0` and `R=166.28 J/(kg K)` for the tutorial surrogate molar mass of 0.05 kg/mol (`R_specific = Ru/M`); the source HK expression retains `Ru=8.314 J/(mol K)`. Inherited tutorial surrogate values are `P0=1e5 Pa`, `Tboil=2900 K`, and `Lvap=1e6 J/kg`; these are calibration values, not asserted M247 properties.

## Results at 2026-09-23

All short runs use two time steps and pass analyzer checks unless noted. At 2000 K and 0.6 Pa, the integrated source rate is approximately `4.0811e-7 kg/s`. Across passing runs, first-step HK relative error is at most `1.2e-12`; paired phase-mass drift is zero; per-step vapor transfer error is below `1.7e-9`; latent-source identity error is below `5e-13` in the baseline. No energy, mass, volume-rate, closure-feedback, or solver-iteration caps occur in passing short runs.

| Check | Cases | Outcome |
|---|---|---|
| Mesh | Nz 20, 40, 80 | PASS; same integrated source rate and 1.508% maximum closure deviation |
| Time step | 1e-14, 1e-15 s | PASS; closure deviation falls from 1.508% to 0.151% at 1e-15 s |
| Diffuse band | 5, 10, 20 um | PASS; HK rate invariant; maximum closure deviation 3.016%, 1.508%, 0.754% |
| Temperature | 1900, 2000, 2100 K | PASS; rate increases monotonically and matches HK oracle |
| Pressure | 0.1, 0.6, 1 Pa | 0.1 Pa at 1e-14 s NEEDS REVIEW (9.05% closure deviation and two capped steps); 0.1 Pa at 1e-15 s and 1 Pa PASS |
| Condensation direction | 2000 K, 60 kPa | PASS; signed rate is negative and matches HK oracle |
| Numerical floors | all configured floors scaled to 0.1 at 0.6 Pa | PASS; rate unchanged and checks pass |
| Sustained transfer | 100 steps at 0.6 Pa, dt=1e-14 and 1e-15 s | NEEDS REVIEW; HK rate, latent identity, paired mass balance, and phase transfer remain accurate, but closure feedback caps 26/100 and 32/100 steps and maximum defect reaches 43.9% and 44.7% |

Short-run evidence establishes the source/oracle and mass/latent coupling checks. It does **not** establish sustained volume-closure stability. Reducing the time step alone did not resolve the 100-step closure feedback. Diagnose the interaction of density changes, compressibility, and closure feedback before extending duration or adding a laser. Keep this V1 gate partially open until a representative sustained run completes without closure caps or excessive defect.

Machine-readable reports are in `../../results/2026-09-23/v1-planar-*.json`. Full OpenFOAM fields and logs remain in the local validation workspace and are not committed.

