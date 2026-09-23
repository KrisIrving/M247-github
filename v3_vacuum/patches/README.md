# LaserBeamFoam V3 vacuum patches

Source patches in this directory will be generated against the pinned upstream
LaserBeamFoam commit documented in `../README.md`.

## Patch policy

1. Preserve upstream defaults.
2. Parameterize low-pressure numerical guards before changing physics.
3. Keep physical model changes separate from numerical-stability changes.
4. Each patch must state the exact upstream SHA.
5. A patch is not considered accepted until it compiles with OpenFOAM v2512
   and passes an upstream-default regression smoke test.

## Patch 0001: low-pressure floors

The first patch will expose the currently hard-coded low-pressure guards:

- `rhoMinEOS`
- `pSmallSat`
- secondary `rhoFloorPC`
- `rhoFloorY`
- acoustic-timestep `pSafe`

The existing dictionary parameter `phaseChangeRhoFloor` does not require a
new source interface and will be handled at case level.

No Hertz-Knudsen/Schrage physics change will be included in the first patch.

## Patch 0002: closure feedback term controls

Adds `closureExplicitVolumeSource` and `closurePressureJacobian` switches to the
phase-volume closure feedback. Both default to `true`, preserving the audited
solver behavior. These controls exist to reproduce the V1 A/B diagnosis and to
support validation; they do not by themselves declare either term disposable.
In the current planar calibration, disabling only the closure Jacobian while
retaining explicit PCR reduces the 100-step closure defect from roughly 44% to
1.51% without caps. The default Jacobian-only probe reproduces the defect. The
modified setting therefore remains an experimental case-level option until
pressure, temperature, mesh, condensation, and non-planar tests are complete.

The patch runner applies both patches in order and refuses a source SHA other
than the pinned upstream commit. On a fresh checkout:

```bash
bash v3_vacuum/patches/apply_vacuum_patch.sh /path/to/LaserbeamFoam-V3
```
