# LaserBeamFoam V3 low-pressure source audit

## Scope

This audit targets `compressibleLaserbeamFoam` at upstream commit
`3c93f2657e089e22e9a8298648292969e85a4bad` on `OpenFoam_com_main`.

Target experiment:

- chamber pressure: 0.6 Pa
- Ar backfill
- preheat: 1343.15 K
- eventual material: M247

The purpose of this stage is **not** to claim that continuum CFD resolves the
0.6 Pa argon gas. It is to identify which solver terms prevent a controlled
low-pressure metal-vapour calculation and which terms are merely numerical
stabilisers.

## Source-level findings

| Item | Source location | Upstream behaviour | Effect at 0.6 Pa | Decision |
|---|---|---|---|---|
| `pMin` | `applications/solvers/compressibleLaserbeamFoam/pEqn.H` plus `constant/thermophysicalProperties` | `p = max(p_rgh + rho*gh, pMin)`. LPBF vapour tutorial uses 1000 Pa. | Hard-clips pressure far above experiment. | Case-level parameter; no source patch required. Vacuum sweep must include `pMin` sensitivity. |
| `rhoMinEOS` | `multiphaseMixtureThermo/multiphaseMixtureThermo.C::correctRho` | Hard-coded density floor 1e-3 kg/m3. | Target Ar density at 0.6 Pa, 1343.15 K is ~2.15e-6 kg/m3, so the floor is ~466x too high. | **Patch required:** make dictionary-configurable while preserving 1e-3 default. |
| `phaseChangeRhoFloor` | phase-change block in `multiphaseMixtureThermo.C` | Already dictionary-configurable; default 0.01 kg/m3. Used in liquid/vapour specific-volume terms and pressure coupling. | Strongly affects volumetric dilation/pressure coupling if vapour density is very low. | Do not remove blindly. Use controlled sensitivity study; source patch not required for this specific parameter. |
| `pSmallSat` | saturation-temperature inversion in `multiphaseMixtureThermo.C` | Hard-coded 1 Pa minimum in `max(p, pSmallSat)`. | 0.6 Pa is treated as 1 Pa in the Tsat branch. For the inherited M247 parameters, this shifts Tsat by ~34.3 K. | **Patch required:** make dictionary-configurable; preserve 1 Pa default. |
| second `rhoFloorPC` | `SuBeta` volume conversion in `multiphaseMixtureThermo.C` | Hard-coded 1e-3 kg/m3. | Can alter mass-to-volume conversion in low-density states. | **Patch required:** parameterize separately or consistently with the chosen phase-change density floor. |
| `rhoFloorY` | conserved partial-mass / packing block in `multiphaseMixtureThermo.C` | Hard-coded 1e-3 kg/m3. | Can dominate gas volume reconstruction at vacuum density. | **Patch required:** make dictionary-configurable; retain upstream default for non-vacuum cases. |
| `pSafe` in acoustic timestep | `applications/solvers/compressibleLaserbeamFoam/setDeltaT_.H` | Acoustic estimate uses `max(p,1e4 Pa)`. | Does not directly alter p solution, but at 0.6 Pa it can impose an artificial acoustic speed and excessively small/biased timestep control. | **Patch required or expose as controlDict option.** Keep numerical role separate from physical pressure floors. |
| `minDeltaT` | `setDeltaT_.H` | Already controlDict-configurable, default 1e-12 s. | May hide true stability failure if timestep repeatedly hits the floor. | No source patch. Log/monitor how often it activates. |
| `Tmin=300 K` for phase-change kinetics | `multiphaseMixtureThermo.C` | Prevents sqrt/exp FPE in rate maths. | Target preheat is 1343.15 K, so not active in normal M247 runs. | Keep unchanged. |
| `phaseChangeGate` | `multiphaseMixtureThermo.C` | Dictionary-configurable, default 0.01. | Interface regularisation, not a vacuum pressure model. | Keep initially; later mesh/interface sensitivity. |
| `accommodationCoeffEvap/Cond` | `multiphaseMixtureThermo.C` | Already separately configurable. | Physically important but uncertain; can strongly scale evaporation/condensation. | Start at documented/default value and perform sensitivity. Do not tune solely to force agreement. |
| `phaseChangeMaskPatches` | `multiphaseMixtureThermo.C`, `TEqn.H` | Can suppress phase change next to open boundaries to prevent artificial boundary condensation/freezing. | Likely useful for a truncated vapour exhaust region. | Use deliberately on open vacuum-reservoir patches after V1 verification. |
| surface radiation | compressible solver search at audited SHA | No clear `radiationModel`, Stefan-Boltzmann or emissivity term found in the compressible solver path during this audit. | At 0.6 Pa, gas convection is weak, so radiation may be relatively more important. | **Open physics item:** inspect energy equation/PR history before production M247 runs; add only with a documented formulation. |

## Equations verified from source

The current phase-change model forms a Clausius-Clapeyron saturation pressure:

```text
Psat = P0 * exp[ (M*Lv)/(Tb*R) * (1 - Tb/T) ]
```

and a signed Hertz-Knudsen-type interfacial mass flux:

```text
mDot'' = sigma * sqrt(M/(2*pi*R*T)) * (x_liq*Psat - y_vap*p)
```

where positive flux denotes evaporation. The code supports separate
`accommodationCoeffEvap` and `accommodationCoeffCond`.

This is a physically reasonable baseline and should be **verified first**.
Adding a separate empirical recoil pressure before verifying this formulation
would risk double-counting evaporation momentum.

## Target-gas rarefaction estimate

For Ar:

```text
p = 0.6 Pa
T = 1343.15 K
M_Ar = 0.039948 kg/mol
d_Ar = 3.40e-10 m
```

Ideal-gas density:

```text
rho_Ar = p*M/(R*T) = 2.146e-6 kg/m3
```

Kinetic-theory mean free path:

```text
lambda = k_B*T / (sqrt(2)*pi*d^2*p) = 6.018e-2 m
```

Therefore:

- L = 0.1 mm -> Kn ~ 602
- L = 0.5 mm -> Kn ~ 120
- L = 1.0 mm -> Kn ~ 60

The far-field Ar is therefore outside the continuum regime. The current project
will treat it as an **effective pressure reservoir**, not as a quantitatively
resolved rarefied argon flow.

## First modification policy

The first source patch should **not alter the phase-change equation**. It should:

1. expose hard-coded low-pressure numerical floors as dictionary/controlDict
   parameters;
2. preserve current upstream defaults so normal V3 tutorials remain unchanged;
3. print the effective values at solver startup;
4. make vacuum-specific choices only in the validation cases;
5. keep each physical/numerical floor distinct so sensitivity can be traced.

Candidate vacuum parameters will not be frozen until V0/V1 tests show stability
and floor-independence.

## Verification ladder

### V0-A: analytical oracle (implemented)

`validation/V0_HK_verification/hk_reference.py`

- independently reproduces source Psat;
- independently reproduces HK net flux;
- reproduces the current 1 Pa Tsat clamp;
- sweeps pressure from atmospheric to below the target pressure;
- reports Ar density and Knudsen-number diagnostics.

### V0-B: patched-source smoke verification (next)

After floor parameterization:

- compile the patched solver against OpenFOAM v2512;
- run upstream `LPBF_small_vapour` with defaults;
- confirm unchanged behaviour against unpatched upstream;
- run a low-pressure no-laser gas-only smoke test at 0.6 Pa;
- verify that pressure and density remain at their prescribed values without
  floor activation.

### V1: planar evaporation CFD

Use a flat condensed/vapour interface with prescribed temperature and pressure.
Compare integrated CFD mass transfer to the analytical HK oracle. Sweep:

- pressure;
- interface thickness / local interface thickness;
- mesh resolution;
- `phaseChangeRhoFloor`;
- accommodation coefficient;
- timestep.

Acceptance requires conservation and a converged flux independent of purely
numerical floors.

## External validation literature

1. P. Bidare et al., "Laser powder bed fusion at sub-atmospheric pressures",
   International Journal of Machine Tools and Manufacture 130-131 (2018) 65-72.
   DOI: 10.1016/j.ijmachtools.2018.03.007.
   Reports LPBF down to 10 microbar (~1 Pa); the paper states the 10 microbar
   case is fully molecular with Kn approximately 1800 and shows pressure-dependent
   track/penetration trends.

2. N. P. Calta et al., "Pressure dependence of the laser-metal interaction under
   laser powder bed fusion conditions probed by in situ X-ray imaging",
   Additive Manufacturing 32 (2020) 101084.
   DOI: 10.1016/j.addma.2020.101084.
   Provides in-situ subsurface morphology versus pressure and is a strong
   candidate for quantitative keyhole/depression validation.

3. A. H. Persad and C. A. Ward, "Expressions for the Evaporation and
   Condensation Coefficients in the Hertz-Knudsen Relation",
   Chemical Reviews 116 (2016) 7727-7767.
   DOI: 10.1021/acs.chemrev.5b00511.
   Reviews limitations and interpretation of HK accommodation coefficients.

4. G. Chen, "On the molecular picture and interfacial temperature
   discontinuity during evaporation and condensation",
   International Journal of Heat and Mass Transfer 191 (2022) 122845.
   DOI: 10.1016/j.ijheatmasstransfer.2022.122845.
   Gives kinetic-theory context for Schrage/Knudsen-layer interfacial
   corrections if the baseline HK model proves insufficient.

## Stop/go criterion before M247 production

Do **not** start the 3 mm / 2.4 ms M247 production case until:

- V0 source floors are parameterized and documented;
- upstream-default regression smoke test passes;
- 0.6 Pa gas-only smoke test is stable;
- V1 mass/energy verification is converged;
- at least one published reduced-pressure LPBF trend is reproduced without
  tuning numerical floors to the answer.

