#!/usr/bin/env bash

# Apply the first LaserBeamFoam V3 vacuum-development patch.
# This script refuses to apply to an unknown upstream commit.
#
# Usage:
#   bash apply_vacuum_patch.sh /path/to/LaserbeamFoam

LBF_DIR="${1:-}"
EXPECTED_SHA="3c93f2657e089e22e9a8298648292969e85a4bad"

if [ -z "$LBF_DIR" ]; then
    echo "Usage: $0 /path/to/LaserbeamFoam"
    exit 2
fi

if [ ! -d "$LBF_DIR/.git" ]; then
    echo "Not a Git repository: $LBF_DIR"
    exit 2
fi

HERE="$(cd "$(dirname "$0")" && pwd)"
PATCH="$HERE/0001-parameterize-low-pressure-floors.patch"

CURRENT_SHA="$(git -C "$LBF_DIR" rev-parse HEAD)" || exit 2

echo "LaserBeamFoam: $LBF_DIR"
echo "Current SHA  : $CURRENT_SHA"
echo "Expected SHA : $EXPECTED_SHA"

if [ "$CURRENT_SHA" != "$EXPECTED_SHA" ]; then
    echo
    echo "Refusing to apply automatically because the source SHA differs."
    echo "Run scripts/check_v3_upstream.sh and re-audit the changed source first."
    exit 3
fi

echo
echo "Checking patch..."
git -C "$LBF_DIR" apply --check "$PATCH" || exit 4

echo "Applying patch..."
git -C "$LBF_DIR" apply "$PATCH" || exit 4

echo
echo "Checking resulting diff..."
git -C "$LBF_DIR" diff --check || exit 5

echo
echo "Patch applied. Review with:"
echo "  git -C '$LBF_DIR' diff"
echo
echo "Do not treat this patch as validated until it compiles under OpenFOAM v2512"
echo "and passes the upstream-default regression smoke test."
