# Local OpenFOAM v2512 / V3 installation and replay

Host: Windows, WSL2 `Ubuntu-24.04`, Linux user `kris`.
Use a fresh Ubuntu-24.04 shell; Ubuntu-22.04 contains different OpenFOAM versions.

```powershell
wsl -d Ubuntu-24.04
```

## Installed paths

```text
OpenFOAM: /usr/lib/openfoam/openfoam2512
Source:   /home/kris/OpenFOAM/kris-v2512/LaserbeamFoam-V3
Project:  /mnt/h/Codex/LaserBeamFoam/M247-github
Runs:     /home/kris/OpenFOAM/kris-v2512/v3-validation
Baseline: /home/kris/OpenFOAM/kris-v2512/v3-builds/upstream/{bin,lib}
Patched:  /home/kris/OpenFOAM/kris-v2512/platforms/linux64GccDPInt32Opt/{bin,lib}
```

The old Windows checkout and Ubuntu-22.04 source were not overwritten.
The project stores a replayable source patch, not a duplicate vendor source tree.
Compiled files and large CFD outputs stay outside Git.

## Daily use

```bash
cd /mnt/h/Codex/LaserBeamFoam/M247-github
source v3_vacuum/scripts/env_v2512.sh patched
printenv WM_PROJECT_VERSION
command -v compressibleLaserbeamFoam
compressibleLaserbeamFoam -help
```

For an upstream baseline run, use a separate fresh shell and source the same
script with `upstream`. It selects both the executable and saved libraries.
The installed package does not provide `foamVersion`; check
`WM_PROJECT_VERSION`, `dpkg-query -W openfoam2512`, and solver `-help` instead.

## Installation commands used on 2026-09-22

These commands document a fresh installation. Do not rerun `git clone` into an
existing directory or overwrite the baseline snapshot with a patched build.

```bash
source /usr/lib/openfoam/openfoam2512/etc/bashrc
cd /home/kris/OpenFOAM/kris-v2512
git clone --branch OpenFoam_com_main --single-branch \
    https://github.com/laserbeamfoam/LaserbeamFoam.git LaserbeamFoam-V3
cd LaserbeamFoam-V3
git rev-parse HEAD
# Must be 3c93f2657e089e22e9a8298648292969e85a4bad for the current patch.
# Re-audit if the remote branch has advanced; never bypass the patch guard.
export WM_NCOMPPROCS=8
./Allwmake -j 8 > /mnt/h/Codex/LaserBeamFoam/M247-github/v3_vacuum/results/2026-09-22/build-upstream.log 2>&1
# Continue only after a successful build and executable/library load check.
compressibleLaserbeamFoam -help
mkdir -p ../v3-builds/upstream
cp -a "$FOAM_USER_APPBIN" ../v3-builds/upstream/bin
cp -a "$FOAM_USER_LIBBIN" ../v3-builds/upstream/lib
bash /mnt/h/Codex/LaserBeamFoam/M247-github/v3_vacuum/patches/apply_vacuum_patch.sh "$PWD"
git diff --check
cd applications/solvers/compressibleLaserbeamFoam
./Allwmake -j 8 > /mnt/h/Codex/LaserBeamFoam/M247-github/v3_vacuum/results/2026-09-22/build-patched.log 2>&1
# A clock-skew warning occurred; the executable target was explicitly rebuilt.
wclean
./Allwmake -j 8 > /mnt/h/Codex/LaserBeamFoam/M247-github/v3_vacuum/results/2026-09-22/build-patched-clean.log 2>&1
```

The clean rebuild log contains the actual C++ compilation and link commands.
An upstream `wmkdepend` warning for `TEqn.H` remains documented; do not assume
incremental dependency tracking is flawless. Use a clean solver target rebuild
when editing included equation headers until that warning is resolved.

## Reproduce the completed screens

Use new output names if the recorded run directories already exist. Scripts
deliberately refuse to reuse an existing case. All commands below run in Bash.

```bash
cd /mnt/h/Codex/LaserBeamFoam/M247-github
source v3_vacuum/scripts/env_v2512.sh patched
python3 -m unittest discover -s v3_vacuum/validation/V0_HK_verification -v
python3 -m unittest discover -s v3_vacuum/validation/V0B_argon_smoke -v
python3 v3_vacuum/validation/V0_HK_verification/hk_reference.py \
    --output v3_vacuum/results/2026-09-22/v0_hk_sweep.csv

V3_TESTS="$HOME/OpenFOAM/kris-v2512/v3-validation"
V3_SCRIPTS="$PWD/v3_vacuum/validation/V0B_argon_smoke"
bash "$V3_SCRIPTS/prepare_case.sh" "$LBF_V3_SOURCE" "$V3_TESTS/case_V0B_Ar_0p6Pa"
bash "$V3_TESTS/case_V0B_Ar_0p6Pa/Allrun"
python3 "$V3_SCRIPTS/analyse_case.py" "$V3_TESTS/case_V0B_Ar_0p6Pa" \
    --json v3_vacuum/results/2026-09-22/v0b-argon.json
bash "$V3_SCRIPTS/run_field_checks.sh" "$V3_TESTS/case_V0B_Ar_0p6Pa"

bash "$V3_SCRIPTS/prepare_case.sh" "$LBF_V3_SOURCE" "$V3_TESTS/case_V0B_Ar_floor01" 0.1
bash "$V3_TESTS/case_V0B_Ar_floor01/Allrun"
python3 "$V3_SCRIPTS/analyse_case.py" "$V3_TESTS/case_V0B_Ar_floor01" \
    --json v3_vacuum/results/2026-09-22/v0b-argon-floor01.json

source v3_vacuum/scripts/env_v2512.sh upstream
bash "$V3_SCRIPTS/prepare_default_regression.sh" "$LBF_V3_SOURCE" "$V3_TESTS/case_default_upstream"
bash "$V3_TESTS/case_default_upstream/Allrun"
source v3_vacuum/scripts/env_v2512.sh patched
bash "$V3_SCRIPTS/prepare_default_regression.sh" "$LBF_V3_SOURCE" "$V3_TESTS/case_default_patched"
bash "$V3_TESTS/case_default_patched/Allrun"
python3 "$V3_SCRIPTS/compare_default_cases.py" \
    "$V3_TESTS/case_default_upstream" "$V3_TESTS/case_default_patched" \
    --json v3_vacuum/results/2026-09-22/default-regression.json
```

The official regression uses the shipped particle location file without rerunning
DEM. Only endTime/writeInterval/writePrecision differ from the official inputs.
The 20 ps duration is a startup check, not a melt-pool validation.

## Incremental development

Change the solver locally, then export its minimal diff into this repository's
`v3_vacuum/patches/`. Rebuild the affected library/solver and repeat the baseline
and smoke checks before committing. Preserve the audited SHA guard. Keep physical
model changes in separate patches/commits from numerical controls.
Push development commits to `lbfv3-vacuum-dev`; keep PR #2 draft until its gates pass.
