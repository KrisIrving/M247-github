# LaserBeamFoam V3 vacuum development

This directory contains the controlled vacuum-model development path for the
M247 LPBF project. The legacy OpenFOAM-10 case at repository root is
intentionally left unchanged.

## Locked experimental target

- OpenFOAM: v2512
- LaserBeamFoam: V3 / `OpenFoam_com_main`
- chamber pressure: 0.6 Pa
- backfill gas: Ar
- preheat: 1070 degC = 1343.15 K
- final process target: M247, 350 W, 1000 mm/s
- final geometry target: continuous 2 mm melt track

## Audited upstream baseline

Official repository: `laserbeamfoam/LaserbeamFoam`  
Branch: `OpenFoam_com_main`  
SHA: `3c93f2657e089e22e9a8298648292969e85a4bad`  
Date: 2026-09-11

The current vacuum patch is tied to this SHA. Do not apply it automatically to
a different source revision without re-auditing the changed code paths.

## Current status

Local execution update (2026-09-22): latest upstream was freshly installed in
Ubuntu-24.04 / WSL2 with OpenFOAM v2512. Upstream and patched builds succeeded;
V0 tests, a **20 ps official-mesh default regression**, and **20 ns Ar screens
at two floor scales** passed. These short screens do not close the full V0-B gate.

- [Execution evidence and remaining issues](results/2026-09-22/README.md)
- [Development plan / 开发计划](docs/development_plan.md)
- [Local installation and replay commands](docs/local_v2512.md)

Completed in this development branch:

- [x] low-pressure source audit
- [x] separation of physical pressure from numerical guards
- [x] first guard-parameterization patch
- [x] analytical Clausius-Clapeyron/Hertz-Knudsen oracle
- [x] V0 analytical regression tests
- [x] literature validation plan

Not yet completed:

- [x] patch compile under OpenFOAM v2512
- [ ] patched-default regression against upstream (V0-B workflow added)
- [x] short 0.6 Pa Ar no-laser smoke screen, including decade-lower guards
- [ ] long-time Ar stability and linear-solver convergence investigation
- [ ] planar evaporation CFD verification
- [ ] Calta/Bidare external validation
- [ ] final M247 V3 case

## Repository layout

```text
v3_vacuum/
├── README.md
├── docs/
│   └── vacuum_source_audit.md
├── patches/
│   ├── 0001-parameterize-low-pressure-floors.patch
│   ├── apply_vacuum_patch.sh
│   ├── README.md
│   └── vacuum_controls.md
├── scripts/
│   └── check_v3_upstream.sh
└── validation/
    ├── V0_HK_verification/
    │   ├── README.md
    │   ├── hk_reference.py
    │   └── test_hk_reference.py
    └── V0B_argon_smoke/
        ├── README.md
        ├── prepare_case.sh
        ├── analyse_case.py
        └── run_field_checks.sh
```

## Verify the local solver identity first

```bash
cd /path/to/LaserbeamFoam
git remote -v
git branch --show-current
git rev-parse HEAD
git log -1 --oneline
foamVersion
which compressibleLaserbeamFoam
```

Then run:

```bash
bash /path/to/M247-github/v3_vacuum/scripts/check_v3_upstream.sh \
    /path/to/LaserbeamFoam
```

## Run V0-A

```bash
cd v3_vacuum/validation/V0_HK_verification
python3 -m unittest -v test_hk_reference.py
python3 hk_reference.py --argon-pressure 0.6 --argon-temperature 1343.15
```

## Apply the first source patch

Only after confirming the local source is exactly the audited SHA:

```bash
bash v3_vacuum/patches/apply_vacuum_patch.sh /path/to/LaserbeamFoam
```

The patch preserves upstream numerical defaults. Applying it does not by itself
create a vacuum model; vacuum-specific values are introduced only in controlled
verification cases.

## Modelling statement

At 0.6 Pa and 1343.15 K, ideal-gas Ar density is approximately
`2.15e-6 kg/m3`. A kinetic-theory mean-free-path estimate is about
`6e-2 m`, giving `Kn ~ 60--600` for 0.1--1 mm LPBF scales.

Therefore the far-field Ar phase is outside the strict continuum regime. The
working interpretation is:

**continuum condensed-metal / metal-vapour model coupled to an effective
low-pressure reservoir.**

Far-field Ar velocity is not treated as quantitatively resolved rarefied-gas
dynamics.

See `docs/vacuum_source_audit.md` for the source-level decisions and the
stop/go gate before M247 production.


## Run V0-B

After applying and compiling the parameterized vacuum patch:

```bash
cd v3_vacuum/validation/V0B_argon_smoke

bash prepare_case.sh \
    /path/to/LaserbeamFoam \
    ./case_V0B_Ar_0p6Pa

cd case_V0B_Ar_0p6Pa
bash Allrun

cd ..
python3 analyse_case.py case_V0B_Ar_0p6Pa
bash run_field_checks.sh case_V0B_Ar_0p6Pa
```

V0-B must pass before the planar-evaporation V1 case is accepted.
