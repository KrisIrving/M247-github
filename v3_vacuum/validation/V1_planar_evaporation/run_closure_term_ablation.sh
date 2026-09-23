#!/usr/bin/env bash
# Build the patched solver and run controlled explicit-PCR/Jacobian A/B cases.
# Usage: source v3_vacuum/scripts/env_v2512.sh patched; bash this-script [OUT_ROOT] [PROBES...]
set -euo pipefail
LBF_DIR="${LBF_V3_SOURCE:-${HOME}/OpenFOAM/kris-v2512/LaserbeamFoam-V3}"
OUT_ROOT="${1:-${HOME}/OpenFOAM/kris-v2512/v3-validation}"
if [ "$#" -gt 0 ]; then shift; fi
PROBES=("$@")
if [ "${#PROBES[@]}" -eq 0 ]; then
    PROBES=(explicitOnly jacobianOnly explicitOnly100)
fi
(
    cd "$LBF_DIR/applications/solvers/compressibleLaserbeamFoam/multiphaseMixtureThermo"
    wmake libso
)
bash "$(cd "$(dirname "$0")" && pwd)/run_closure_diagnostics.sh" \
    "$OUT_ROOT" "${PROBES[@]}"
