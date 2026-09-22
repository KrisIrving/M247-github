#!/usr/bin/env bash

# Run simple field extrema checks after V0-B.
# Usage: bash run_field_checks.sh [case]

CASE="${1:-.}"

cd "$CASE" || exit 1

echo "==== latest time ===="
foamListTimes -latestTime || exit 1

echo
echo "==== p ===="
postProcess -latestTime -func "fieldMinMax(p)" || exit 1

echo
echo "==== rho ===="
postProcess -latestTime -func "fieldMinMax(rho)" || exit 1

echo
echo "==== T ===="
postProcess -latestTime -func "fieldMinMax(T)" || exit 1

echo
echo "==== U ===="
postProcess -latestTime -func "fieldMinMax(U)" || exit 1

echo
echo "==== phase fractions ===="
postProcess -latestTime -func "fieldMinMax(alpha.air)" || exit 1
postProcess -latestTime -func "fieldMinMax(alpha.metal1)" || exit 1
postProcess -latestTime -func "fieldMinMax(alpha.metal1vapour)" || exit 1
