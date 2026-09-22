#!/usr/bin/env bash

# Run simple field extrema checks after V0-B.
# Usage: bash run_field_checks.sh [case]

CASE="${1:-.}"

cd "$CASE" || exit 1

echo "==== latest time ===="
foamListTimes -latestTime 2>/dev/null || true

echo
echo "==== p ===="
postProcess -latestTime -func "fieldMinMax(p)" 2>/dev/null || true

echo
echo "==== rho ===="
postProcess -latestTime -func "fieldMinMax(rho)" 2>/dev/null || true

echo
echo "==== T ===="
postProcess -latestTime -func "fieldMinMax(T)" 2>/dev/null || true

echo
echo "==== U ===="
postProcess -latestTime -func "fieldMinMax(U)" 2>/dev/null || true

echo
echo "==== phase fractions ===="
postProcess -latestTime -func "fieldMinMax(alpha.air)" 2>/dev/null || true
postProcess -latestTime -func "fieldMinMax(alpha.metal1)" 2>/dev/null || true
postProcess -latestTime -func "fieldMinMax(alpha.metal1vapour)" 2>/dev/null || true
