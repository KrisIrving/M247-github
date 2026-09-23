#!/usr/bin/env bash
# Run short diagnostic controls for the V1 closure-feedback investigation.
# Usage: source v3_vacuum/scripts/env_v2512.sh patched; bash this-script [OUT_ROOT]
set -euo pipefail
LBF_DIR="${LBF_V3_SOURCE:-${HOME}/OpenFOAM/kris-v2512/LaserbeamFoam-V3}"
OUT_ROOT="${1:-${HOME}/OpenFOAM/kris-v2512/v3-validation}"
if [ "$#" -gt 0 ]; then shift; fi
PREP="$(cd "$(dirname "$0")" && pwd)/prepare_case.sh"

prepare_probe() {
    local name="$1" steps="$2"; shift 2
    bash "$PREP" "$LBF_DIR" "$OUT_ROOT/$name" 2000 0.6 1e-14 "$steps" 40 1e-5 1
    python3 - "$OUT_ROOT/$name/constant/thermophysicalProperties" "$@" <<'PY'
from pathlib import Path
import sys
p = Path(sys.argv[1])
s = p.read_text()
marker = "phaseChangeVolLimit 0.1;"
if s.count(marker) != 1:
    raise SystemExit(f"Expected exactly one {marker!r} in {p}")
s = s.replace(marker, marker + "\n" + "\n".join(sys.argv[2:]), 1)
p.write_text(s)
PY
    (cd "$OUT_ROOT/$name" && bash Allrun > run.stdout 2>&1)
}

PROBES=("$@")
if [ "${#PROBES[@]}" -eq 0 ]; then
    PROBES=(noHK noClosure relax01 largeClosureCap)
fi
for probe in "${PROBES[@]}"; do
    case "$probe" in
        noHK) prepare_probe v1-probe-noHK 5 \
            'accommodationCoeffEvap 0;' 'accommodationCoeffCond 0;' ;;
        noClosure) prepare_probe v1-probe-noClosure 5 'closureRelax 0;' ;;
        relax01) prepare_probe v1-probe-relax01 5 'closureRelax 0.1;' ;;
        implicitOff) prepare_probe v1-probe-implicitOff 5 'implicitVolLimit 0;' ;;
        largeClosureCap) prepare_probe v1-probe-largeClosureCap 5 'closureVolLimit 1;' ;;
        noClosure100) prepare_probe v1-probe-noClosure100 100 'closureRelax 0;' ;;
        relax01_100) prepare_probe v1-probe-relax01-100 100 'closureRelax 0.1;' ;;
        *) echo "Unknown probe: $probe" >&2; exit 2 ;;
    esac
done

echo "Completed closure probes under $OUT_ROOT"

