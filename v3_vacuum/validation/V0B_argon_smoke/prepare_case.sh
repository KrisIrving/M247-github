#!/usr/bin/env bash

# Generate a minimal 0.6 Pa Ar smoke test from the exact audited
# LaserBeamFoam V3 LPBF_small_vapour tutorial.
#
# Usage:
#   bash prepare_case.sh /path/to/LaserbeamFoam [output_case]

LBF_DIR="${1:-}"
OUT_DIR="${2:-case_V0B_Ar_0p6Pa}"
EXPECTED_SHA="3c93f2657e089e22e9a8298648292969e85a4bad"

if [ -z "$LBF_DIR" ]; then
    echo "Usage: $0 /path/to/LaserbeamFoam [output_case]"
    exit 2
fi

if [ ! -d "$LBF_DIR/.git" ]; then
    echo "Not a Git repository: $LBF_DIR"
    exit 2
fi

SHA="$(git -C "$LBF_DIR" rev-parse HEAD)"
if [ "$SHA" != "$EXPECTED_SHA" ]; then
    echo "Expected LaserBeamFoam SHA: $EXPECTED_SHA"
    echo "Found SHA               : $SHA"
    echo "Refusing to generate a case from an unaudited source revision."
    exit 3
fi

SRC="$LBF_DIR/tutorials/compressiblelaserbeamFoam/LPBF_small_vapour"
if [ ! -d "$SRC" ]; then
    echo "Tutorial not found: $SRC"
    exit 4
fi

if [ -e "$OUT_DIR" ]; then
    echo "Output already exists: $OUT_DIR"
    echo "Remove it or choose another output directory."
    exit 5
fi

cp -a "$SRC" "$OUT_DIR"
rm -rf "$OUT_DIR/DEM_small" "$OUT_DIR/postProcessing" "$OUT_DIR"/[1-9]*        "$OUT_DIR"/processor* "$OUT_DIR"/log.* 2>/dev/null || true

# Keep the official field name alpha.air to minimise changes in V0-B.
# Replace only the physical properties of that phase with argon.
cat > "$OUT_DIR/constant/thermophysicalProperties.air" <<'EOF'
FoamFile
{
    version     2.0;
    format      ascii;
    class       dictionary;
    location    "constant";
    object      thermophysicalProperties.air;
}

phaseState      gaseous;

thermoType
{
    type            heRhoThermo;
    mixture         pureMixture;
    transport       const;
    thermo          hConst;
    equationOfState perfectGas;
    specie          specie;
    energy          sensibleInternalEnergy;
}

TSolidus               5.0;
TLiquidus              10.0;
LatentHeat             1.0;
elec_conductivity      1.0;
magnetic_permeability  1.256e-6;

mixture
{
    specie
    {
        molWeight   39.948;
    }
    thermodynamics
    {
        Cp          520.3;
        Hf          0;
    }
    transport
    {
        // Transport is dynamically irrelevant in this stationary smoke test.
        // A finite constant value is retained for numerical completeness.
        mu          5.0e-5;
        Pr          0.67;
    }
}
EOF

python3 - "$OUT_DIR" <<'PY'
from pathlib import Path
import re
import sys

case = Path(sys.argv[1])
T0 = "1343.15"
P0 = "0.6"

def replace_once(path, pattern, repl, flags=0):
    p = case / path
    s = p.read_text()
    ns, n = re.subn(pattern, repl, s, count=1, flags=flags)
    if n != 1:
        raise SystemExit(f"Expected one match in {p}: {pattern!r}, got {n}")
    p.write_text(ns)

# Temperature fields: mixture + per-phase.
for rel in ["initial/T", "initial/T.air", "initial/T.metal1", "initial/T.metal1vapour"]:
    replace_once(rel, r"internalField\s+uniform\s+[^;]+;", f"internalField   uniform {T0};")

# Pressure fields.
replace_once("initial/p", r"internalField\s+uniform\s+[^;]+;", f"internalField   uniform {P0};")
replace_once("initial/p_rgh", r"internalField\s+uniform\s+[^;]+;", f"internalField   uniform {P0};")
replace_once(
    "initial/p_rgh",
    r"(topWall\s*\{.*?\bp0\s+uniform\s+)[^;]+;",
    rf"\g<1>{P0};",
    flags=re.S,
)

# Gas-only phase state.
replace_once("initial/alpha.air", r"internalField\s+uniform\s+[^;]+;", "internalField   uniform 1;")
replace_once("initial/alpha.metal1", r"internalField\s+uniform\s+[^;]+;", "internalField   uniform 0;")
replace_once("initial/alpha.metal1vapour", r"internalField\s+uniform\s+[^;]+;", "internalField   uniform 0;")

# Zero laser power at all tabulated times.
tp = case / "constant/timeVsLaserPower"
s = tp.read_text()
s = re.sub(r"(\(\s*[-+0-9.eE]+\s+)[-+0-9.eE]+(\s*\))", r"\g<1>0\2", s)
tp.write_text(s)

# Short smoke-test runtime.
replace_once("system/controlDict", r"endTime\s+[^;]+;", "endTime         2e-8;")
replace_once("system/controlDict", r"deltaT\s+[^;]+;", "deltaT          1e-12;")
replace_once("system/controlDict", r"writeInterval\s+[^;]+;", "writeInterval   2e-9;")
replace_once("system/controlDict", r"maxDeltaT\s+[^;]+;", "maxDeltaT       1e-10;")

# Add acoustic pressure floor to controlDict.
control = case / "system/controlDict"
s = control.read_text()
if "acousticPressureFloor" not in s:
    s += "\n// V0-B vacuum numerical control\nacousticPressureFloor 0.06;\n"
control.write_text(s)

# Add low-pressure controls to thermophysicalProperties.
tp = case / "constant/thermophysicalProperties"
s = tp.read_text()
s = re.sub(r"\bpMin\s+[^;]+;", "pMin            0.06;", s, count=1)
controls = """
// V0-B vacuum numerical controls -- screening values only
rhoMinEOS                     1e-8;
pSmallSat                     0.06;
phaseChangeRhoFloor           1e-7;
partialMassRhoFloor           1e-8;
recoveryRhoFloor              1e-8;
implicitCouplingPressureFloor 0.06;
phaseChangeMaskPatches        (topWall);
"""
if "rhoMinEOS" not in s:
    s += "\n" + controls
tp.write_text(s)
PY

cat > "$OUT_DIR/Allrun" <<'EOF'
#!/usr/bin/env bash
. "$WM_PROJECT_DIR/bin/tools/RunFunctions"

rm -rf 0
cp -a initial 0

runApplication blockMesh
runApplication compressibleLaserbeamFoam
EOF
chmod +x "$OUT_DIR/Allrun"

cat > "$OUT_DIR/CASE_METADATA.txt" <<EOF
V0-B Ar smoke test
Generated from LaserBeamFoam SHA: $EXPECTED_SHA
Physical target:
  pressure = 0.6 Pa
  temperature = 1343.15 K
  gas = Ar (phase name retained as 'air' for minimal perturbation)
  laser power = 0 W
Interpretation:
  effective low-pressure reservoir smoke test only; not rarefied-gas validation.
EOF

echo "Generated: $OUT_DIR"
echo "Run:"
echo "  cd '$OUT_DIR'"
echo "  bash Allrun"
