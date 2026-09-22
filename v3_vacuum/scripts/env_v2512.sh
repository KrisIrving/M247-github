#!/usr/bin/env bash
# Source from Ubuntu 24.04 / WSL2. Do not source an OF9/OF10/v2506 environment first.
# Usage: source v3_vacuum/scripts/env_v2512.sh [patched|upstream]
V3_VARIANT="${1:-patched}"
case "$V3_VARIANT" in
    patched|upstream) ;;
    *) echo "Expected patched or upstream"; return 2 ;;
esac
source /usr/lib/openfoam/openfoam2512/etc/bashrc || return 1
export LBF_V3_SOURCE="${LBF_V3_SOURCE:-$HOME/OpenFOAM/kris-v2512/LaserbeamFoam-V3}"
if [ "$V3_VARIANT" = upstream ]; then
    V3_RUNTIME="$HOME/OpenFOAM/kris-v2512/v3-builds/upstream"
else
    V3_RUNTIME="$FOAM_USER_APPBIN/.."
fi
export PATH="$V3_RUNTIME/bin:$PATH"
export LD_LIBRARY_PATH="$V3_RUNTIME/lib:$LD_LIBRARY_PATH"
hash -r
if ! command -v compressibleLaserbeamFoam >/dev/null; then
    echo "compressibleLaserbeamFoam not installed for $V3_VARIANT"
    return 1
fi
