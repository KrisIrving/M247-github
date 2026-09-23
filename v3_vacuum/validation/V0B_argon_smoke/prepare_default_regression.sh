#!/usr/bin/env bash
# Official mesh/physics, shortened duration. New vacuum controls are omitted.
# Usage: bash prepare_default_regression.sh LBF_DIR OUT_DIR [endTime]
LBF_DIR="${1:?Expected source directory}"
OUT_DIR="${2:?Expected fresh output directory}"
END_TIME="${3:-2e-11}"
EXPECTED_SHA=3c93f2657e089e22e9a8298648292969e85a4bad
if [ "$(git -C "$LBF_DIR" rev-parse HEAD)" != "$EXPECTED_SHA" ]; then
    echo "Unaudited upstream SHA"; exit 2
fi
if [ -e "$OUT_DIR" ]; then
    echo "Output already exists"; exit 2
fi
mkdir -p "$OUT_DIR" || exit 1
for part in initial constant system; do
    cp -a "$LBF_DIR/tutorials/compressiblelaserbeamFoam/LPBF_small_vapour/$part" "$OUT_DIR/" || exit 1
done
python3 - "$OUT_DIR" "$END_TIME" "${V3_T_SOLVER_PROBE:-0}" <<'PY'
from pathlib import Path
import re
import sys
p = Path(sys.argv[1]) / 'system/controlDict'
end = float(sys.argv[2])
probe_temperature = sys.argv[3] == '1'
if not 0 < end <= 1e-4:
    raise SystemExit('endTime must be in (0, 1e-4]')
s = p.read_text()
for key, value in [('endTime', end), ('writeInterval', end), ('writePrecision', 12)]:
    s, n = re.subn(rf'\b{key}\s+[^;]+;', f'{key} {value};', s)
    if n != 1:
        raise SystemExit(f'Expected exactly one {key}')
p.write_text(s)
if probe_temperature:
    solution = Path(sys.argv[1]) / 'system/fvSolution'
    text = solution.read_text()
    # TFinal takes precedence over T in this solver; set both for clarity.
    for key in ('T', 'TFinal'):
        text += f'''\n{key}\n{{\n    solver          PBiCGStab;\n    preconditioner  DILU;\n    tolerance       1e-10;\n    relTol          0.05;\n}}\n'''
    solution.write_text(text)
PY
if [ "$?" -ne 0 ]; then exit 1; fi
cat > "$OUT_DIR/Allrun" <<'EOF'
#!/usr/bin/env bash
cd "$(dirname "$0")" || exit 1
. "${WM_PROJECT_DIR:?}/bin/tools/RunFunctions" || exit 1
if [ -e 0 ]; then echo "Use a fresh case"; exit 1; fi
cp -a initial 0 || exit 1
runApplication blockMesh || exit 1
runApplication setSolidFraction -compressible -alpha.phase1 alpha.metal1 -alpha.phase2 alpha.air -subDivisions 6 || exit 1
runApplication transformPoints -rotate '((0 1 0) (0 0 1))' || exit 1
runApplication compressibleLaserbeamFoam || exit 1
EOF
echo "Generated official-mesh regression at endTime=$END_TIME: $OUT_DIR"
