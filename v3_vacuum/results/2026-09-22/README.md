# Local installation and initial execution evidence — 2026-09-22

## Identity

- Official latest `OpenFoam_com_main`, verified by `git ls-remote`:
  `3c93f2657e089e22e9a8298648292969e85a4bad` (2026-09-11).
- Project starting commit: `41b648a14182133c8164eb77cbd8585d34a3faa8`,
  branch `lbfv3-vacuum-dev`, Draft PR #2.
- WSL2 Ubuntu-24.04, user kris, OpenFOAM package `2512.0-2`,
  solver reports OpenFOAM-2512 build `_bd2b6720-20260127`.
- Build: GCC, double precision, 32-bit labels, optimized, 8 compilation jobs.
- Local environment paths and exact replay commands: `../../docs/local_v2512.md`.
- No modification to the root OF10 case. No empirical recoil or HK physics change.

## Gate results

| Check | Result | Scope |
|---|---|---|
| Official latest source installation | PASS | Fresh Linux checkout, full Allwmake exit 0, solver -help works |
| Low-pressure patch application | PASS | Repaired malformed hunks; exact pinned SHA; git diff --check clean |
| Patched compilation | PASS | Mixture library and solver rebuilt; explicit clean solver rebuild exit 0 |
| V0 analytic tests | PASS | 5 tests; source constants retained |
| Smoke-analyser acceptance tests | PASS | 7 tests including incomplete/fatal/missing-density/nonuniform/nonfinite cases |
| Default original-mesh startup regression | PASS | 192,000 cells, 2e-11 s, 9 steps; **not full 100 us tutorial** |
| Ar stationary screen | PASS | 1536 cells, 2e-8 s, 219 steps, 10 written times |
| Ar decade-lower floor screen | PASS | Same field extrema and timestep history as first screen |
| Native OpenFOAM fieldMinMax | PASS | Latest-time scalar/vector extrema agree with ASCII analysis |
| Full default-regression gate | PENDING | Complete-duration comparison not run |
| Long-time Ar stability / convergence | PENDING | Needs longer duration and investigation of iteration-limit hits |
| V1 / literature / M247 production | PENDING | Do not start production based on these screens |

## Ar results

Across all ten written times in each 20 ns run:

| Quantity | Minimum | Maximum |
|---|---:|---:|
| p [Pa] | 0.6 | 0.6 |
| p_rgh [Pa] | 0.6 | 0.6 |
| rho [kg/m3] | 2.14628406437e-6 | 2.14628406437e-6 |
| T [K] | 1343.15 | 1343.15 |
| speed [m/s] | 1.13563711037e-18 | 2.12691674399e-14 |
| alpha.air | 1 | 1 |
| alpha.metal1 | 0 | 0 |
| alpha.metal1vapour | 0 | 0 |

CODATA ideal-gas reference: 2.1462859870811836e-6 kg/m3. The small difference
is consistent with the gas-constant precision in the OpenFOAM EOS. Density is
read from the actual `rho` field, not manufactured from p/T by the analyser.

Both runs reached `Time = 2e-08` and a standalone `End`, without fatal error/FPE.
Minimum timestep 1.19976004799e-12 s; maximum 1.03277490442e-10 s.
The slightly above-maxDeltaT written step is retained as measured and needs
timestep-controller review; it is not silently rounded to 1e-10.

Base floors: pMin/pSmallSat/implicitCouplingPressureFloor/acousticPressureFloor
0.06 Pa, rhoMinEOS/partialMassRhoFloor/recoveryRhoFloor 1e-8 kg/m3,
phaseChangeRhoFloor 1e-7 kg/m3. The second run scales all eight by 0.1.
The measured p and rho remain above their direct floors; no shift to
1/1000/10000 Pa or 1e-3 kg/m3 occurs. This does not validate guards in inactive
evaporation/condensation branches.

Native latest-time speed maximum is 4.1743459945e-15 m/s; the larger value in
the table is the maximum over **all written times**. Native fieldMinMax includes
zero boundary velocity, while the Python report describes internal cells.

## Default startup regression

`default-regression.json` records p/rho/T, full U components, all phase fractions,
partial masses and mass_dot. All compared values agree at writePrecision=12;
maximum absolute difference is zero for every compared field. Phase masses and
the 9-step timestep histories agree. Neither case contains the new controls.
Both ran serially with the original 40×60×80 mesh and shipped powder location.
Original/patched solver execution times were 16.12/15.89 seconds respectively.
This 20 ps test exercises initialization and early coupling; it does not establish
equivalence after sustained evaporation or keyhole formation.

## First errors and warnings found

1. Original V0 test failed: actual density `2.1462859870811836e-6`, rounded expected
   `2.146e-6`, tolerance `2e-10`. Corrected the reference value; no formula change.
2. Existing patch failed `git apply --check`: `corrupt patch at line 46`; after
   recounting, an incorrectly indented recovery-floor context also failed.
   Repaired/exported the unified diff from the actual pinned source.
3. Patch script previously continued after a failed check/apply and printed success.
   It now exits immediately with a nonzero status on those failures.
4. Build warning: `Clock skew detected. Your build may be incomplete.`
   Addressed by explicitly cleaning/rebuilding the solver target and then running
   the resulting executable. No system clock setting was changed.
5. Clean build warning: `wmkdepend: parse error while scanning 'TEqn.H' ... perhaps
   missing a final newline`. Compilation/linking succeeded; dependency-scanner
   warning remains open, so header edits require a clean target rebuild.
6. Each Ar run has **2540 linear solves reaching 1000 iterations**. Examples include
   T residual 0.289228 -> 0.271390 and p_rgh residual around 8.06e-4 after 1000
   iterations, while p/T/U remain at their stationary target to output precision.
   This may involve normalized residuals at a nearly uniform state; the cause has
   not been established. Diagnose absolute residuals/conditioning before long runs;
   do not claim convergence merely because the field-value screen passes.
7. Native postProcess warns when scanning headerless tutorial data tables
   (e.g. timeVsLaserPosition). It still loads requested fields and reports extrema.

## Artifacts

Version-controlled: this summary, V0 CSV, two Ar JSON reports, default-regression
JSON, and build/runtime manifest. Complete logs are retained locally in this
directory (`*.log`, Git-ignored); complete field outputs remain in the Linux run
directories. Each JSON contains the measured values and test scope.

Overall: **installation complete; initial screens PASS; full vacuum verification
still PENDING**. Next: diagnose solver iteration behavior, complete longer default
and reservoir checks, then V1. See `../../docs/development_plan.md`.
