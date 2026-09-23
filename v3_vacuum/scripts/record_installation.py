#!/usr/bin/env python3
"""Record local build identity; run after sourcing env_v2512.sh patched."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess


def command(*args):
    p = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return {"exit_code": p.returncode, "output": p.stdout.strip()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    source = Path(os.environ["LBF_V3_SOURCE"])
    app = Path(os.environ["FOAM_USER_APPBIN"])
    lib = Path(os.environ["FOAM_USER_LIBBIN"])
    baseline = source.parent / "v3-builds/upstream"
    files = [app/"compressibleLaserbeamFoam", lib/"libmultiphaseVapMixtureThermo.so",
             baseline/"bin/compressibleLaserbeamFoam",
             baseline/"lib/libmultiphaseVapMixtureThermo.so"]
    project = Path(__file__).resolve().parents[2]
    patch = project/"v3_vacuum/patches/0001-parameterize-low-pressure-floors.patch"
    files.append(patch)
    report = {
        "platform": platform.platform(),
        "environment": {key: os.environ.get(key) for key in (
            "WM_PROJECT_VERSION", "WM_PROJECT_DIR", "WM_OPTIONS", "FOAM_USER_APPBIN", "FOAM_USER_LIBBIN")},
        "source_head": command("git", "-C", str(source), "rev-parse", "HEAD"),
        "source_status": command("git", "-C", str(source), "status", "--short"),
        "source_diff_check": command("git", "-C", str(source), "diff", "--check"),
        "openfoam_package": command("dpkg-query", "-W", "openfoam2512"),
        "compiler": command("g++", "--version"),
        "solver_help": command(str(app/"compressibleLaserbeamFoam"), "-help"),
        "patched_dynamic_libraries": command("ldd", str(app/"compressibleLaserbeamFoam")),
        "sha256": {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in files},
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(args.output)


if __name__ == "__main__":
    main()
