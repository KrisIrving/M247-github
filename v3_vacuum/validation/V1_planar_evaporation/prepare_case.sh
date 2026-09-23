#!/usr/bin/env bash
# Generate a small, closed, source-faithful planar metal/vapour V1 case.
# Usage: prepare_case.sh LBF_DIR OUT_DIR [temperature_K] [pressure_Pa] [dt_s] [steps] [Nz] [interface_thickness_m] [floor_scale]
set -euo pipefail
LBF_DIR="${1:?Expected audited LaserBeamFoam source directory}"
OUT_DIR="${2:?Expected fresh output directory}"
T0="${3:-2000}"
P="${4:-0.6}"
DT="${5:-1e-14}"
NSTEPS="${6:-1}"
NZ="${7:-40}"
DELTA="${8:-1e-5}"
FLOOR_SCALE="${9:-1}"
EXPECTED_SHA=3c93f2657e089e22e9a8298648292969e85a4bad
if [[ "$(git -C "$LBF_DIR" rev-parse HEAD)" != "$EXPECTED_SHA" ]]; then
    echo "Unaudited upstream SHA" >&2; exit 2
fi
if [[ -e "$OUT_DIR" ]]; then echo "Output already exists" >&2; exit 2; fi
SRC="$LBF_DIR/tutorials/compressiblelaserbeamFoam/LPBF_small_vapour"
mkdir -p "$OUT_DIR"
for part in initial constant system; do cp -a "$SRC/$part" "$OUT_DIR/"; done
python3 - "$OUT_DIR" "$T0" "$P" "$DT" "$NSTEPS" "$NZ" "$DELTA" "$FLOOR_SCALE" <<'PY'
from pathlib import Path
import re, sys
case, temp, pressure, dt, nsteps, nz, delta, fs = Path(sys.argv[1]), float(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4]), int(sys.argv[5]), int(sys.argv[6]), float(sys.argv[7]), float(sys.argv[8])
if not (300 < temp < 4000 and pressure > 0.06*fs and dt > 0 and nsteps > 0 and nz >= 20 and delta > 0 and 0 < fs <= 1):
    raise SystemExit('Require 300<T<4000 K, p>0.06 Pa, and dt>0')

def sub(path, pattern, repl, count=1, flags=0):
    p=case/path; s=p.read_text(); out,n=re.subn(pattern,repl,s,count=count,flags=flags)
    if n != count: raise SystemExit(f'{path}: expected {count} match for {pattern!r}, got {n}')
    p.write_text(out)

# 4x4xNz cells; choose a diffuse band exactly one source delta thick.
sub(Path('system/blockMeshDict'), r'\(40 60 80\)', f'(4 4 {nz})')

height=200e-6; dz=height/nz; nmix=round(delta/dz)
if nmix < 1 or abs(nmix*dz-delta) > 1e-12*height:
    raise SystemExit('interface_thickness must be an integer number of z cells')
iz0=(nz-nmix)//2
zlo=iz0*dz; zhi=zlo+delta
regions=[f'boxToCell {{ box (0 0 0) (100e-6 150e-6 {zlo:.12g}); fieldValues (volScalarFieldValue alpha.metal1 1); }}']
gate=0.01; weights=[]
for j in range(nmix):
    za=zlo+j*dz; zb=za+dz; am=1-(j+0.5)/nmix; av=1-am
    regions.append(f'boxToCell {{ box (0 0 {za:.12g}) (100e-6 150e-6 {zb:.12g}); fieldValues (volScalarFieldValue alpha.metal1 {am:.12g} volScalarFieldValue alpha.metal1vapour {av:.12g}); }}')
    weights.append(min(min(am,av)/gate,1.0))
regions.append(f'boxToCell {{ box (0 0 {zhi:.12g}) (100e-6 150e-6 {height:.12g}); fieldValues (volScalarFieldValue alpha.metal1vapour 1); }}')
(case/'system/setFieldsDict').write_text('''FoamFile\n{ version 2.0; format ascii; class dictionary; object setFieldsDict; }\ndefaultFieldValues\n(\n volScalarFieldValue alpha.air 0\n volScalarFieldValue alpha.metal1 0\n volScalarFieldValue alpha.metal1vapour 0\n volVectorFieldValue U (0 0 0)\n);\nregions\n(\n'''+'\n'.join(regions)+'\n);\n')
plane_area=100e-6*150e-6
effective_area=plane_area*sum(weights)*dz/delta
(case/'V1_GEOMETRY.txt').write_text(
    f'plane_area_m2={plane_area:.12g}\neffective_area_m2={effective_area:.12g}\n'
    f'domain_volume_m3={plane_area*height:.12g}\ncell_volume_m3={plane_area*height/(4*4*nz):.12g}\n'
    f'nz={nz}\ndz_m={dz:.12g}\ninterface_thickness_m={delta:.12g}\n'
    f'diffuse_band_m={delta:.12g}\nmixed_layers={nmix}\nfloor_scale={fs:.12g}\n'
)

# Uniform initial interface temperature and pressure.
for rel in ('initial/T','initial/T.air','initial/T.metal1','initial/T.metal1vapour'):
    sub(Path(rel), r'internalField\s+uniform\s+[^;]+;', f'internalField uniform {temp:.12g};')
for rel in ('initial/p','initial/p_rgh'):
    sub(Path(rel), r'internalField\s+uniform\s+[^;]+;', f'internalField uniform {pressure:.12g};')
sub(Path('initial/p_rgh'), r'(topWall\s*\{.*?\bp0\s+uniform\s+)[^;]+;', rf'\g<1>{pressure:.12g};', flags=re.S)

# Make every boundary impermeable for a closed-control-volume mass audit.
u=case/'initial/U'; s=u.read_text(); s=re.sub(r'topWall\s*\{.*?\n\s*\}', 'topWall { type fixedValue; value uniform (0 0 0); }', s, count=1, flags=re.S); u.write_text(s)

# Zero laser input and short, small time steps keep the source in its linear regime.
p=case/'constant/timeVsLaserPower'; s=p.read_text(); s=re.sub(r'(\(\s*[-+0-9.eE]+\s+)[-+0-9.eE]+(\s*\))',r'\g<1>0\2',s); p.write_text(s)
sub(Path('constant/thermophysicalProperties'), r'\bpMin\s+[^;]+;', f'pMin {0.06*fs:.12g};')
sub(Path('system/controlDict'), r'\bstartFrom\s+[^;]+;', 'startFrom startTime;')
sub(Path('system/controlDict'), r'\bendTime\s+[^;]+;', f'endTime {nsteps*dt:.12g};')
sub(Path('system/controlDict'), r'\bdeltaT\s+[^;]+;', f'deltaT {dt:.12g};')
sub(Path('system/controlDict'), r'\bwriteInterval\s+[^;]+;', f'writeInterval {dt:.12g};')
sub(Path('system/controlDict'), r'\bmaxDeltaT\s+[^;]+;', f'maxDeltaT {dt:.12g};')
sub(Path('system/controlDict'), r'\bwritePrecision\s+[^;]+;', 'writePrecision 12;')

tp=case/'constant/thermophysicalProperties'; s=tp.read_text()
s,n=re.subn(r'\binterface_thickness\s+[^;]+;', f'interface_thickness {delta:.12g};',s,count=1)
if n != 1: raise SystemExit('Expected one interface_thickness')
if 'rhoMinEOS' not in s:
    s += f'''\n// V1 numerical guards, deliberately kept distinct\nrhoMinEOS {1e-8*fs:.12g};\npSmallSat {0.06*fs:.12g};\nphaseChangeRhoFloor {1e-7*fs:.12g};\npartialMassRhoFloor {1e-8*fs:.12g};\nrecoveryRhoFloor {1e-8*fs:.12g};\nimplicitCouplingPressureFloor {0.06*fs:.12g};\nphaseChangeGate 0.01;\nphaseChangeVolLimit 0.1;\n'''
tp.write_text(s)

# Use an ideal-gas metal-vapour EOS at low pressure. The tutorial's rho0=5
# kg/m3 perfect-fluid offset and its default R overwhelm the physical 0.6 Pa
# vapour density. R is the mass-specific gas constant for M=50 g/mol.
sub(Path('constant/thermophysicalProperties.metal1vapour'), r'\brho0\s+[^;]+;', 'rho0 0;')
sub(Path('constant/thermophysicalProperties.metal1vapour'), r'\bR\s+[^;]+;', 'R 166.28;')

# Candidate thermal solver is the one that passed the official-mesh short regression.
fv=case/'system/fvSolution'; s=fv.read_text()
entries='''\n    T { solver PBiCGStab; preconditioner DILU; tolerance 1e-10; relTol 0.05; }\n    TFinal { solver PBiCGStab; preconditioner DILU; tolerance 1e-10; relTol 0.05; }\n'''
marker='\n}\n\nMELTING'
if s.count(marker) != 1: raise SystemExit('Could not locate solvers dictionary end')
fv.write_text(s.replace(marker, entries+marker, 1))
PY
cat > "$OUT_DIR/Allrun" <<'EOF'
#!/usr/bin/env bash
set -e
. "${WM_PROJECT_DIR:?Source OpenFOAM v2512 first}/bin/tools/RunFunctions"
cd "$(dirname "$0")"
if [ -e 0 ]; then echo 'Use a fresh case'; exit 1; fi
cp -a initial 0
runApplication blockMesh
runApplication setFields
runApplication compressibleLaserbeamFoam
EOF
chmod +x "$OUT_DIR/Allrun"
cat > "$OUT_DIR/CASE_METADATA.txt" <<EOF
V1 planar evaporation calibration (not an M247 property claim)
source SHA=$EXPECTED_SHA
P0=1e5 Pa, Tboil=2900 K, molar mass=50 g/mol, Lvap=1e6 J/kg (inherited tutorial surrogate)
vapour EOS rho0=0, R=166.28 J/(kg K) for M=50 g/mol
temperature=$T0 K; initial pressure=$P Pa; dt=$DT s; steps=$NSTEPS; endTime=$(python3 -c "print(int('$NSTEPS')*float('$DT'))") s
two-cell diffuse interface; interface_thickness=10 um; zero laser; closed velocity boundaries
Nz=$NZ; interface_thickness=$DELTA m; diffuse-band thickness=$DELTA m
numeric_floor_scale=$FLOOR_SCALE
plane_area=1.5e-8 m2; VOF-gate-integrated effective area is stored in setFieldsDict metadata
EOF
echo "Prepared V1 planar case: $OUT_DIR"

