#!/usr/bin/env bash
# Short, one-equation-at-a-time solver test; retains all physical controls.
# Usage: source scripts/env_v2512.sh patched && bash scripts/run_linear_solver_probe.sh LBF_DIR FRESH_OUTPUT_ROOT
# Optional: V3_PROBE_TESTS="combined" V3_PROBE_END_TIME=2e-8 for the longer reservoir run.
LBF_DIR="${1:?Expected pinned LaserBeamFoam source path}"
OUT_ROOT="${2:?Expected new output directory}"
PROBE_TESTS="${V3_PROBE_TESTS:-T p_rgh combined}"
PROBE_END_TIME="${V3_PROBE_END_TIME:-2e-10}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
CASE_SCRIPT="$PROJECT_DIR/v3_vacuum/validation/V0B_argon_smoke"

if [ -e "$OUT_ROOT" ]; then
    echo "Output exists; choose a new directory: $OUT_ROOT"
    exit 2
fi
mkdir -p "$OUT_ROOT" || exit 1

for test in $PROBE_TESTS; do
    case_dir="$OUT_ROOT/case_${test}_krylov"
    bash "$CASE_SCRIPT/prepare_case.sh" "$LBF_DIR" "$case_dir" || exit 1
    python3 - "$case_dir" "$test" "$PROBE_END_TIME" <<'PY' || exit 1
from pathlib import Path
import re
import sys
case, test, duration = Path(sys.argv[1]), sys.argv[2], float(sys.argv[3])
if duration <= 0 or duration > 1e-5: raise SystemExit('duration must be in (0, 1e-5]')
control = case/'system/controlDict'
s = control.read_text()
for key, value in [('endTime', f'{duration:.12g}'), ('writeInterval', f'{duration/10:.12g}')]:
    s, n = re.subn(rf'\b{key}\s+[^;]+;', f'{key} {value};', s, count=1)
    if n != 1: raise SystemExit(f'Could not set {key}')
control.write_text(s)
fv = case/'system/fvSolution'
s = fv.read_text()
if test in ('T', 'combined'):
    marker = '    "(U|T|k|B|nuTilda)"'
    start = s.index(marker)
    brace = s.index('{', start)
    depth, end = 0, None
    for i in range(brace, len(s)):
        if s[i] == '{': depth += 1
        elif s[i] == '}':
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end is None: raise SystemExit('Unclosed generic solver block')
    entry = '''

    T
    {
        solver          PBiCGStab;
        preconditioner  DILU;
        tolerance       1e-8;
        relTol          0;
        maxIter         100;
    }'''
    s = s[:end] + entry + s[end:]
    final_marker = '    "(U|T|k|B|nuTilda)Final"'
    if final_marker not in s: raise SystemExit('Cannot find final solver block')
    final_entry = '''    TFinal
    {
        solver          PBiCGStab;
        preconditioner  DILU;
        tolerance       1e-8;
        relTol          0;
        maxIter         100;
    }

'''
    s = s.replace(final_marker, final_entry+final_marker, 1)
if test in ('p_rgh', 'combined'):
    match = re.search(r'(?m)^    p_rgh\s*\{', s)
    if not match: raise SystemExit('Cannot find exact p_rgh solver block')
    brace = s.index('{', match.start())
    depth, end = 0, None
    for i in range(brace, len(s)):
        if s[i] == '{': depth += 1
        elif s[i] == '}':
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end is None: raise SystemExit('Unclosed p_rgh solver block')
    entry = '''    p_rgh
    {
        solver          PCG;
        preconditioner  DIC;
        tolerance       1e-7;
        relTol          0;
        maxIter         100;
    }'''
    s = s[:match.start()] + entry + s[end:]
fv.write_text(s)
PY
    (cd "$case_dir" && bash Allrun) || exit 1
    python3 "$SCRIPT_DIR/audit_solver_iterations.py" \
        "$case_dir/log.compressibleLaserbeamFoam" \
        --json "$OUT_ROOT/${test}-iterations.json" || exit 1
    python3 "$CASE_SCRIPT/analyse_case.py" "$case_dir" \
        --json "$OUT_ROOT/${test}-fields.json" || exit 1
done
echo "Compare the T and p_rgh iteration/field JSONs in $OUT_ROOT"
