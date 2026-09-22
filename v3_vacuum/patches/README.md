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

## Planned first patch

The first patch will expose the currently hard-coded low-pressure guards:

- `rhoMinEOS`
- `pSmallSat`
- secondary `rhoFloorPC`
- `rhoFloorY`
- acoustic-timestep `pSafe`

The existing dictionary parameter `phaseChangeRhoFloor` does not require a
new source interface and will be handled at case level.

No Hertz-Knudsen/Schrage physics change will be included in the first patch.
