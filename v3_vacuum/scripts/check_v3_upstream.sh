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
echo "==== low-pressure guards ===="
grep -RIn --exclude-dir=.git \
  -e 'pMin' \
  -e 'rhoMinEOS' \
  -e 'phaseChangeRhoFloor' \
  -e 'pSmallSat' \
  -e 'rhoFloorY' \
  -e 'rhoFloorPC' \
  -e 'pSafe' \
  -e 'minDeltaT' \
  "$SRC" 2>/dev/null || true

echo
echo "==== phase-change controls ===="
grep -RIn --exclude-dir=.git \
  -e 'accommodationCoeff' \
  -e 'phaseChangeGate' \
  -e 'phaseChangeMaskPatches' \
  "$SRC" 2>/dev/null || true
