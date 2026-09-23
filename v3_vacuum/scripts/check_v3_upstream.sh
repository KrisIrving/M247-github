#!/usr/bin/env bash

# Audit helper for the local LaserBeamFoam source.
# Usage:
#   bash check_v3_upstream.sh /path/to/LaserbeamFoam

LBF_DIR="${1:-.}"

cd "$LBF_DIR" || exit 1

echo "==== repository ===="
git remote -v
git branch --show-current
git rev-parse HEAD
git log -1 --oneline

echo
echo "==== OpenFOAM ===="
echo "WM_PROJECT_VERSION=${WM_PROJECT_VERSION:-<not sourced>}"
command -v foamVersion >/dev/null 2>&1 && foamVersion || true

echo
echo "==== solver ===="
command -v compressibleLaserbeamFoam || true

SRC="applications/solvers/compressibleLaserbeamFoam"

echo
echo "==== low-pressure guards / limiters ===="
grep -RIn --exclude-dir=.git \
  -e 'pMin' \
  -e 'rhoMinEOS' \
  -e 'phaseChangeRhoFloor' \
  -e 'pSmallSat' \
  -e 'rhoFloorY' \
  -e 'rhoMinRec' \
  -e 'rhoFloorPC' \
  -e 'condVoidFloor' \
  -e 'cPurgeTol' \
  -e 'implicitVolLimit' \
  -e 'Foam::max(pI' \
  -e 'pSafe' \
  -e 'minDeltaT' \
  "$SRC" 2>/dev/null || true

echo
echo "==== phase-change controls ===="
grep -RIn --exclude-dir=.git \
  -e 'accommodationCoeff' \
  -e 'phaseChangeGate' \
  -e 'phaseChangeMaskPatches' \
  -e 'closureMaskPatches' \
  "$SRC" 2>/dev/null || true

echo
echo "==== suspicious pressure/density literals ===="
grep -RIn --exclude-dir=.git -E \
  'dimDensity.*1e-|dimPressure.*1e-|max\([^;]*1e[0-9+-]+' \
  "$SRC" 2>/dev/null || true

echo
echo "Review every hit by code path. Do not classify all small constants as vacuum floors."
