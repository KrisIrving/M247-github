# Vacuum control candidates -- NOT production values

These entries become available after applying
`0001-parameterize-low-pressure-floors.patch`.

The first objective is a sensitivity study, not to freeze one arbitrary set.

## constant/thermophysicalProperties

Existing setting:

```text
pMin <case-specific>;
phaseChangeRhoFloor <case-specific>;
```

New parameters exposed by the patch:

```text
rhoMinEOS            1e-3;  // upstream default
pSmallSat            1.0;   // Pa, upstream default
betaSourceRhoFloor   1e-3;  // kg/m3, upstream default
partialMassRhoFloor  1e-3;  // kg/m3, upstream default
```

## system/controlDict

New parameter:

```text
acousticPressureFloor 1e4;  // Pa, upstream default
```

## Planned sensitivity logic for the 0.6 Pa target

The experimental Ar density at 0.6 Pa and 1343.15 K is approximately
2.15e-6 kg/m3. Therefore the existing 1e-3--1e-2 kg/m3 floors are not
physically inactive.

Do not jump directly to a single tiny floor. V0-B/V1 should sweep logarithmic
values and determine the lowest values that:

1. no longer change the verified mass/energy result;
2. remain numerically stable;
3. do not dominate pressure coupling or volume reconstruction.

Likewise, `pSmallSat` should be tested below 0.6 Pa. The V0 analytical oracle
shows that the current 1 Pa value shifts the inherited-M247 equilibrium
temperature by about +34.26 K.

A provisional test matrix (not a production recommendation) is:

```text
pMin                   : 0.6, 0.1, 0.06, 0.01 Pa
pSmallSat              : 1.0, 0.6, 0.1, 0.01 Pa
rhoMinEOS              : 1e-3 ... 1e-8 kg/m3
phaseChangeRhoFloor    : 1e-2 ... 1e-7 kg/m3
betaSourceRhoFloor     : 1e-3 ... 1e-8 kg/m3
partialMassRhoFloor    : 1e-3 ... 1e-8 kg/m3
acousticPressureFloor  : 1e4, 1e3, 100, 10, 1, 0.6 Pa
```

Only a reduced subset should be run after one-at-a-time screening identifies
which controls are active.
