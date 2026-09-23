# Vacuum control candidates -- verification values, not production values

These controls are available after applying
`0001-parameterize-low-pressure-floors.patch`.

The objective is to separate **physical pressure** from **numerical guards**.
The upstream defaults are preserved so the patched solver can first be checked
against the unmodified V3 solver.

## constant/thermophysicalProperties

Existing upstream controls:

```text
pMin                     <case-specific>   // Pa
phaseChangeRhoFloor       0.01              // kg/m3 upstream default
```

New controls exposed by the patch:

```text
rhoMinEOS                 1e-3   // kg/m3; EOS density floor
pSmallSat                 1.0    // Pa; lower pressure used only in Tsat inversion
partialMassRhoFloor       1e-3   // kg/m3; c/rho volume reconstruction guard
recoveryRhoFloor          1e-3   // kg/m3; alpha=c/rho recovery guard
implicitCouplingPressureFloor 1e4 // Pa; denominator guard for vDotP ceiling
```

The already-available phase-change control:

```text
phaseChangeRhoFloor       0.01
```

is intentionally kept separate. It enters the specific-volume change used by
phase-change pressure coupling and can materially affect low-density vapour
behaviour.

## system/controlDict

New control:

```text
acousticPressureFloor     1e4   // Pa; only the acoustic timestep estimate
```

This does not directly clip the solved pressure, but at sub-Pa pressure the
upstream 10 kPa floor can make the acoustic timestep estimate artificially
severe.

## Controls deliberately NOT reclassified as vacuum density floors

The upstream source also contains several small constants that serve different
roles. They should not all be reduced merely because the chamber is at 0.6 Pa.

Examples:

```text
condVoidFloor       1e-3   // dimensionless condensed-volume threshold
cPurgeTol           1e-10  // kg/m3 partial-mass purge threshold
phaseChangeGate     0.01   // dimensionless interface gate
betaSmall           1e-8   // dimensionless divide-by-zero guard
```

They remain unchanged in the first vacuum patch unless V1 shows that they are
active in the verified result.

## Target condition

Experiment:

```text
pAmbient = 0.6 Pa
T0       = 1343.15 K
gas      = Ar
```

Ideal-gas Ar density is approximately:

```text
rhoAr = 2.146e-6 kg/m3
```

Therefore the original 1e-3--1e-2 kg/m3 density guards are not guaranteed to
be inactive.

## Screening matrix

Do not perform the full Cartesian product. Use one-at-a-time screening first.

```text
pMin                         : 0.6, 0.1, 0.06, 0.01 Pa
pSmallSat                    : 1.0, 0.6, 0.1, 0.01 Pa
rhoMinEOS                    : 1e-3 ... 1e-8 kg/m3
phaseChangeRhoFloor          : 1e-2 ... 1e-7 kg/m3
partialMassRhoFloor          : 1e-3 ... 1e-8 kg/m3
recoveryRhoFloor             : 1e-3 ... 1e-8 kg/m3
implicitCouplingPressureFloor: 1e4, 1e3, 100, 10, 1, 0.6, 0.1 Pa
acousticPressureFloor        : 1e4, 1e3, 100, 10, 1, 0.6 Pa
```

## Acceptance rule

A guard may be considered numerically inactive only when reducing it further:

1. does not materially change the verified mass flux, latent-heat sink,
   pressure response or phase volume;
2. does not change the converged solution beyond the chosen numerical
   tolerance;
3. does not introduce instability or nonphysical negative pressure/density.

The final M247 case will use the **largest safe values that are already
solution-independent**, not simply the smallest values that still run.
