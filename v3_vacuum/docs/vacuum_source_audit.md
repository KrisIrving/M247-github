# LaserBeamFoam V3 low-pressure source audit

## Scope

Solver: `compressibleLaserbeamFoam`  
Upstream: `laserbeamfoam/LaserbeamFoam` / `OpenFoam_com_main`  
Audited SHA: `3c93f2657e089e22e9a8298648292969e85a4bad` (2026-09-11)

Target experiment:

- chamber pressure: 0.6 Pa
- backfill: Ar
- preheat: 1343.15 K (1070 degC)
- final process target: M247, 350 W, 1000 mm/s, continuous 2 mm melt track

The objective is not to claim that continuum CFD resolves the far-field
0.6 Pa argon gas. The objective is to determine whether the V3 metal-vapour
model can be used as a controlled **continuum metal-vapour + effective vacuum
reservoir** model, and to verify every low-pressure numerical modification.

## Core phase-change formulation found in source

The current V3 source forms the saturation pressure as

```text
Psat = P0 * exp[ (M*Lv)/(Tb*R) * (1 - Tb/T) ]
```

and uses a signed Hertz-Knudsen-type interfacial mass flux

```text
mDot'' = sigma * sqrt(M/(2*pi*R*T)) * (x_liq*Psat - y_vap*p)
```

with separate `accommodationCoeffEvap` and
`accommodationCoeffCond` controls.

This is retained as the baseline physics. No empirical recoil-pressure term is
added in the first vacuum-development stage, because the compressible solver
already transfers mass and momentum through an explicit vapour phase and an
additional recoil model could double count evaporation momentum.

## Low-pressure source audit

| Item | Upstream code path | Default / behaviour | Relevance at 0.6 Pa | First-stage decision |
|---|---|---|---|---|
| `pMin` | `pEqn.H` + case dictionary | `p=max(p_rgh+rho*gh,pMin)`; LPBF vapour tutorial uses 1000 Pa | Direct hard pressure clip | Case-level control; sweep below 0.6 Pa |
| `rhoMinEOS` | `correctRho()` | hard-coded 1e-3 kg/m3 | ~466x target Ar density | Parameterize, preserve default |
| `phaseChangeRhoFloor` | HK/phase-change block | already configurable, default 0.01 kg/m3 | Enters vapour specific volume, PCR and pressure coupling | Keep distinct; sensitivity required |
| `pSmallSat` | Tsat inversion | hard-coded 1 Pa | 0.6 Pa is treated as 1 Pa; inherited M247 Tsat shifts +34.26 K | Parameterize, preserve default |
| `rhoFloorY` | conserved partial-mass volume reconstruction | hard-coded 1e-3 kg/m3 | Can dominate gas volume reconstruction | Expose as `partialMassRhoFloor` |
| `rhoMinRec` | hierarchical alpha recovery | hard-coded 1e-3 kg/m3 | `alpha=c/rho` recovery can be dominated by floor | Expose as `recoveryRhoFloor` |
| pressure denominator in `kPmax` | implicit phase-change pressure-coupling ceiling | hard-coded `max(p,1e4)` | 0.6 Pa state is treated as 10 kPa in this limiter | Expose as `implicitCouplingPressureFloor` |
| acoustic `pSafe` | `setDeltaT_.H` | hard-coded `max(p,1e4)` | Can force an artificial acoustic speed / timestep restriction | Expose as `acousticPressureFloor` |
| second `rhoFloorPC=1e-3` in `SuBeta` | liquid mass-to-volume source conversion | applies only to non-gaseous `liq` phases | M247 liquid density is orders of magnitude larger | Leave unchanged initially; not a vacuum-gas floor |
| `condVoidFloor=1e-3` | closure classification | dimensionless condensed fraction | Not a gas-density floor | Leave unchanged initially |
| `cPurgeTol=1e-10` | partial-mass purge | kg/m3 | Far below target Ar density ~2.15e-6 kg/m3 | Leave unchanged, monitor purged mass |
| `phaseChangeGate=0.01` | interface gate | dimensionless | Interface regularisation, not vacuum pressure | Keep initially; V1 mesh sensitivity |
| `Tmin=300 K` | phase-change rate math | rate-only temperature floor | Inactive at 1343 K preheat | Keep |
| `minDeltaT` | `controlDict` | configurable | Can hide a stability collapse if repeatedly active | Keep but log/monitor |
| `phaseChangeMaskPatches` | phase-change / TEqn open-boundary handling | configurable | Useful for truncated vapour exhaust | Decide in V1 after boundary tests |
| surface radiation | compressible source search | no explicit Stefan-Boltzmann/emissivity path identified in this solver at audited SHA | More relevant when gas convection is negligible | Open physics item before M247 production |

## Why the far-field argon cannot be interpreted as resolved continuum flow

For Ar at

```text
p = 0.6 Pa
T = 1343.15 K
M = 0.039948 kg/mol
d = 3.40e-10 m
```

the ideal-gas density is

```text
rho_Ar = p*M/(R*T) = 2.146e-6 kg/m3
```

and the kinetic-theory mean free path estimate is

```text
lambda = kB*T/(sqrt(2)*pi*d^2*p) = 6.018e-2 m
```

giving approximately

- L=0.1 mm -> Kn ~ 602
- L=0.5 mm -> Kn ~ 120
- L=1.0 mm -> Kn ~ 60

Thus the far-field Ar is highly rarefied. The project interpretation is:

> resolve the condensed metal and locally dense metal vapour with the V3
> compressible formulation, while treating the 0.6 Pa Ar environment as an
> effective low-pressure reservoir rather than a quantitatively resolved
> Navier-Stokes gas flow.

Any far-field Ar velocity or plume shape in the highly rarefied region must be
treated cautiously.

## First patch policy

The first patch:

1. changes **no phase-change physics**;
2. preserves every upstream default;
3. only exposes hard-coded low-pressure guards that can be active at sub-Pa
   conditions;
4. prints the effective low-pressure settings at solver startup;
5. keeps physically distinct guards as separate controls for sensitivity
   analysis.

Patch:
`patches/0001-parameterize-low-pressure-floors.patch`

## Verification ladder

### V0-A -- analytical oracle

Implemented in `validation/V0_HK_verification`.

The oracle independently reproduces:

- source Clausius-Clapeyron `Psat(T)`;
- source HK net mass flux;
- source `Tsat` inversion;
- the effect of `pSmallSat`;
- Ar ideal-gas density and Knudsen diagnostics.

### V0-B -- source regression + 0.6 Pa smoke test

Required before V1:

1. compile the patched source under OpenFOAM v2512;
2. run official upstream `LPBF_small_vapour` unchanged;
3. compare patched-default and unpatched-default results;
4. require no meaningful regression attributable to the patch;
5. run a no-laser 0.6 Pa Ar gas-only case;
6. confirm prescribed pressure and EOS density remain stable and identify
   exactly which guards activate.

### V1 -- planar evaporation CFD verification

Use a flat condensed/vapour interface. Prescribe interface temperature and
reservoir pressure and compare integrated CFD mass transfer with the analytical
oracle.

Sweep, one factor at a time:

- pressure;
- mesh/interface thickness;
- timestep;
- `phaseChangeRhoFloor`;
- `rhoMinEOS`;
- `partialMassRhoFloor`;
- `recoveryRhoFloor`;
- `implicitCouplingPressureFloor`;
- accommodation coefficient.

Acceptance requires:

- mass conservation;
- latent-energy consistency;
- grid/time convergence;
- floor independence once guards are below their active range.

## External validation plan

### Calta et al. (2020)

N. P. Calta et al., *Pressure dependence of the laser-metal interaction under
laser powder bed fusion conditions probed by in situ X-ray imaging*,
Additive Manufacturing 32 (2020) 101084.
DOI: 10.1016/j.addma.2020.101084.

Use for quantitative pressure-dependent melt-pool / vapour-depression
morphology where the published geometry and process conditions are sufficient
for a reproducible case.

### Bidare et al. (2018)

P. Bidare et al., *Laser powder bed fusion at sub-atmospheric pressures*,
International Journal of Machine Tools and Manufacture 130-131 (2018) 65-72.
DOI: 10.1016/j.ijmachtools.2018.03.007.

Use for the near-target pressure regime (down to 10 microbar ~ 1 Pa), focusing
on track/penetration trends. Do not require the present one-way powder
initialisation to reproduce rarefied-gas-driven powder entrainment.

### Interfacial-kinetic references

A. H. Persad and C. A. Ward, Chemical Reviews 116 (2016) 7727-7767.
DOI: 10.1021/acs.chemrev.5b00511.

G. Chen, International Journal of Heat and Mass Transfer 191 (2022) 122845.
DOI: 10.1016/j.ijheatmasstransfer.2022.122845.

These are reserved for deciding whether Schrage/Knudsen-layer corrections are
needed **after** the baseline HK implementation has been verified.

## Stop/go gate before final M247 production

Do not start the 3 mm / 2.4 ms M247 production run until:

- patched-default regression passes;
- 0.6 Pa gas-only smoke test is stable;
- V1 mass/energy verification is converged and floor-independent;
- at least one reduced-pressure LPBF experiment is reproduced at the level
  justified by the model;
- radiation treatment for the compressible solver has been resolved;
- any remaining rarefied-gas limitation is explicitly documented.
