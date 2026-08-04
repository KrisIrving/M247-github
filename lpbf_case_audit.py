#!/usr/bin/env python3
"""
LPBF / LaserBeamFoam case auditor

Run from the case root:
    python3 lpbf_case_audit.py .

Outputs (default: ./case_audit):
    LPBF_case_audit.md
    LPBF_case_audit.json

The script uses only the Python standard library. It is designed for the
M247-github case layout, while keeping most parsing logic generic enough for
similar OpenFOAM/LaserBeamFoam cases.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence


# ----------------------------- utility functions ----------------------------


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"//.*?$", "", text, flags=re.M)
    text = re.sub(r"#.*?$", "", text, flags=re.M)
    return text


def as_float(token: str | None, default: float | None = None) -> float | None:
    if token is None:
        return default
    token = token.strip().strip("()")
    try:
        return float(token)
    except (TypeError, ValueError):
        return default


def scalar(text: str, key: str, default: float | None = None) -> float | None:
    clean = strip_comments(text)
    m = re.search(rf"(?m)^\s*{re.escape(key)}\s+([^;\s]+)\s*;", clean)
    return as_float(m.group(1), default) if m else default


def word(text: str, key: str, default: str = "") -> str:
    clean = strip_comments(text)
    m = re.search(rf"(?m)^\s*{re.escape(key)}\s+([^;\s]+)\s*;", clean)
    return m.group(1).strip('"') if m else default


def vector(text: str, key: str) -> list[float] | None:
    clean = strip_comments(text)
    m = re.search(rf"(?m)^\s*{re.escape(key)}\s*\(([^)]+)\)\s*;", clean)
    if not m:
        return None
    vals = [as_float(v) for v in m.group(1).split()]
    return [float(v) for v in vals if v is not None] if len(vals) == 3 else None


def vector_n(text: str, key: str, n: int) -> list[float] | None:
    clean = strip_comments(text)
    m = re.search(rf"(?m)^\s*{re.escape(key)}\s*\(([^)]+)\)\s*;", clean)
    if not m:
        return None
    vals = [as_float(v) for v in m.group(1).split()]
    if len(vals) != n or any(v is None for v in vals):
        return None
    return [float(v) for v in vals]


def fmt_num(x: float | int | None, sig: int = 5) -> str:
    if x is None:
        return "未读取"
    if isinstance(x, int):
        return f"{x:,}"
    if not math.isfinite(x):
        return str(x)
    return f"{x:.{sig}g}"


def fmt_um(x_m: float | None, digits: int = 3) -> str:
    return "未读取" if x_m is None else f"{x_m * 1e6:.{digits}f} μm"


def fmt_us(x_s: float | None, digits: int = 3) -> str:
    return "未读取" if x_s is None else f"{x_s * 1e6:.{digits}f} μs"


def fmt_pct(x: float | None, digits: int = 2) -> str:
    return "未读取" if x is None else f"{100*x:.{digits}f}%"


def percentile(values: Sequence[float], q: float) -> float | None:
    if not values:
        return None
    s = sorted(values)
    pos = (len(s) - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return s[lo]
    f = pos - lo
    return s[lo] * (1 - f) + s[hi] * f


def weighted_percentile(values: Sequence[float], weights: Sequence[float], q: float) -> float | None:
    if not values or len(values) != len(weights):
        return None
    pairs = sorted(zip(values, weights), key=lambda x: x[0])
    total = sum(max(0.0, w) for _, w in pairs)
    if total <= 0:
        return None
    target = q * total
    cumulative = 0.0
    for value, weight in pairs:
        cumulative += max(0.0, weight)
        if cumulative >= target:
            return value
    return pairs[-1][0]


def python_constant(text: str, name: str) -> float | None:
    m = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*([+\-\d.eE]+)", text)
    return float(m.group(1)) if m else None


def raw_entry(text: str, key_pattern: str, default: str = "") -> str:
    clean = strip_comments(text)
    m = re.search(rf"(?m)^\s*{key_pattern}\s+([^;]+);", clean)
    return m.group(1).strip() if m else default


def relpath(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def git_revision(root: Path) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=3,
        ).strip()
    except Exception:
        return None


def add_finding(findings: list[dict[str, str]], severity: str, title: str, detail: str, action: str) -> None:
    findings.append({"severity": severity, "title": title, "detail": detail, "action": action})


# ----------------------------- geometry parsing -----------------------------


def extract_parenthesized_block(text: str, keyword: str) -> str:
    clean = strip_comments(text)
    m = re.search(rf"\b{re.escape(keyword)}\b\s*\(", clean)
    if not m:
        return ""
    start = clean.find("(", m.start())
    depth = 0
    for i in range(start, len(clean)):
        if clean[i] == "(":
            depth += 1
        elif clean[i] == ")":
            depth -= 1
            if depth == 0:
                return clean[start + 1 : i]
    return ""


def parse_vertices(text: str) -> list[list[float]]:
    block = extract_parenthesized_block(text, "vertices")
    out: list[list[float]] = []
    for m in re.finditer(r"\(([^()]+)\)", block):
        vals = [as_float(v) for v in m.group(1).split()]
        if len(vals) == 3 and all(v is not None for v in vals):
            out.append([float(v) for v in vals])
    scale = scalar(text, "convertToMeters", 1.0) or 1.0
    return [[scale * v for v in p] for p in out]


def parse_hex_cells(text: str) -> list[int] | None:
    clean = strip_comments(text)
    m = re.search(r"hex\s*\([^)]*\)\s*\((\d+)\s+(\d+)\s+(\d+)\)", clean)
    return [int(m.group(i)) for i in (1, 2, 3)] if m else None


def parse_patch_types(text: str) -> dict[str, str]:
    block = extract_parenthesized_block(text, "boundary")
    result: dict[str, str] = {}
    # For each top-level name followed by a brace, find the matching brace.
    pos = 0
    while pos < len(block):
        m = re.search(r"([A-Za-z_][\w.]*)\s*\{", block[pos:])
        if not m:
            break
        name = m.group(1)
        brace = pos + m.end() - 1
        depth = 0
        end = None
        for i in range(brace, len(block)):
            if block[i] == "{":
                depth += 1
            elif block[i] == "}":
                depth -= 1
                if depth == 0:
                    end = i
                    break
        if end is None:
            break
        body = block[brace + 1 : end]
        t = word(body, "type", "")
        if t:
            result[name] = t
        pos = end + 1
    return result


def bounds(points: Sequence[Sequence[float]]) -> list[list[float]] | None:
    if not points:
        return None
    return [[min(p[i] for p in points), max(p[i] for p in points)] for i in range(3)]


def normalize(v: Sequence[float]) -> list[float]:
    n = math.sqrt(sum(x*x for x in v))
    if n == 0:
        raise ValueError("zero vector")
    return [x / n for x in v]


def dot(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(x*y for x, y in zip(a, b))


def cross(a: Sequence[float], b: Sequence[float]) -> list[float]:
    return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]


def rotation_from_to(a: Sequence[float], b: Sequence[float]) -> list[list[float]]:
    """Rodrigues rotation mapping normalized vector a to b."""
    a = normalize(a)
    b = normalize(b)
    v = cross(a, b)
    c = max(-1.0, min(1.0, dot(a, b)))
    s = math.sqrt(dot(v, v))
    if s < 1e-14:
        if c > 0:
            return [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
        # 180 degrees: choose an axis perpendicular to a.
        helper = [1.0, 0.0, 0.0] if abs(a[0]) < 0.9 else [0.0, 1.0, 0.0]
        axis = normalize(cross(a, helper))
        x, y, z = axis
        return [
            [2*x*x-1, 2*x*y, 2*x*z],
            [2*x*y, 2*y*y-1, 2*y*z],
            [2*x*z, 2*y*z, 2*z*z-1],
        ]
    vx = [[0.0, -v[2], v[1]], [v[2], 0.0, -v[0]], [-v[1], v[0], 0.0]]
    k = (1.0 - c) / (s*s)
    # R = I + [v]x + [v]x^2 * (1-c)/s^2
    vx2 = [[sum(vx[i][q]*vx[q][j] for q in range(3)) for j in range(3)] for i in range(3)]
    return [[(1.0 if i == j else 0.0) + vx[i][j] + k*vx2[i][j] for j in range(3)] for i in range(3)]


def matvec(m: Sequence[Sequence[float]], p: Sequence[float]) -> list[float]:
    return [sum(m[i][j] * p[j] for j in range(3)) for i in range(3)]


def parse_transform_rotation(allrun: str) -> tuple[list[float], list[float]] | None:
    m = re.search(
        r"transformPoints[^\n]*rotate\s*=\s*\(\s*\(([^)]+)\)\s*\(([^)]+)\)\s*\)",
        allrun,
    )
    if not m:
        return None
    try:
        a = [float(v) for v in m.group(1).split()]
        b = [float(v) for v in m.group(2).split()]
        return (a, b) if len(a) == len(b) == 3 else None
    except ValueError:
        return None


# ------------------------------ table parsing -------------------------------


def parse_scalar_table(text: str) -> list[tuple[float, float]]:
    clean = strip_comments(text)
    out = []
    for m in re.finditer(r"\(\s*([+\-\d.eE]+)\s+([+\-\d.eE]+)\s*\)", clean):
        try:
            out.append((float(m.group(1)), float(m.group(2))))
        except ValueError:
            pass
    return out


def parse_vector_table(text: str) -> list[tuple[float, list[float]]]:
    clean = strip_comments(text)
    out = []
    pattern = r"\(\s*([+\-\d.eE]+)\s+\(\s*([+\-\d.eE]+)\s+([+\-\d.eE]+)\s+([+\-\d.eE]+)\s*\)\s*\)"
    for m in re.finditer(pattern, clean):
        try:
            out.append((float(m.group(1)), [float(m.group(i)) for i in (2, 3, 4)]))
        except ValueError:
            pass
    return out


def interpolate_scalar(table: Sequence[tuple[float, float]], t: float) -> float | None:
    if not table:
        return None
    tab = sorted(table)
    if t <= tab[0][0]:
        return tab[0][1]
    if t >= tab[-1][0]:
        return tab[-1][1]
    for (t0, y0), (t1, y1) in zip(tab, tab[1:]):
        if t0 <= t <= t1:
            f = (t - t0) / (t1 - t0)
            return y0 + f * (y1 - y0)
    return None


def interpolate_vector(table: Sequence[tuple[float, Sequence[float]]], t: float) -> list[float] | None:
    if not table:
        return None
    tab = sorted(table, key=lambda x: x[0])
    if t <= tab[0][0]:
        return list(tab[0][1])
    if t >= tab[-1][0]:
        return list(tab[-1][1])
    for (t0, y0), (t1, y1) in zip(tab, tab[1:]):
        if t0 <= t <= t1:
            f = (t - t0) / (t1 - t0)
            return [y0[i] + f * (y1[i] - y0[i]) for i in range(3)]
    return None


def integrate_scalar_table(table: Sequence[tuple[float, float]], t_end: float) -> float | None:
    """Piecewise-linear integral from 0 to t_end."""
    if not table:
        return None
    times = sorted({0.0, t_end} | {t for t, _ in table if 0.0 < t < t_end})
    area = 0.0
    for a, b in zip(times, times[1:]):
        ya = interpolate_scalar(table, a)
        yb = interpolate_scalar(table, b)
        if ya is None or yb is None:
            return None
        area += 0.5 * (ya + yb) * (b - a)
    return area


# ----------------------------- particle parsing -----------------------------


def parse_last_liggghts_dump(path: Path) -> tuple[int | None, list[tuple[float, float, float, float]]]:
    lines = read_text(path).splitlines()
    atom_indices = [i for i, line in enumerate(lines) if line.startswith("ITEM: ATOMS")]
    if not atom_indices:
        return None, []
    i = atom_indices[-1]
    timestep = None
    for j in range(i - 1, -1, -1):
        if lines[j].startswith("ITEM: TIMESTEP") and j + 1 < len(lines):
            try:
                timestep = int(float(lines[j + 1].strip()))
            except ValueError:
                pass
            break
    particles = []
    for line in lines[i + 1 :]:
        if line.startswith("ITEM:"):
            break
        vals = line.split()
        if len(vals) >= 4:
            try:
                particles.append(tuple(float(v) for v in vals[:4]))
            except ValueError:
                pass
    return timestep, particles


def sphere_below_plane_volume(zc: float, r: float, z_plane: float) -> float:
    h = max(0.0, min(2.0*r, z_plane - (zc - r)))
    return math.pi * h*h * (r - h/3.0)


def sphere_between_planes_volume(zc: float, r: float, lo: float, hi: float) -> float:
    return sphere_below_plane_volume(zc, r, hi) - sphere_below_plane_volume(zc, r, lo)


def particle_metrics(
    particles: Sequence[tuple[float, float, float, float]],
    footprint_x: float | None,
    footprint_y: float | None,
    plate_top: float | None,
    trim_top: float | None,
    density: float | None,
    cell_size: float | None,
) -> dict[str, Any]:
    if not particles:
        return {"count": 0}
    xs, ys, zs, rs = zip(*particles)
    ds = [2*r for r in rs]
    tops = [z+r for z, r in zip(zs, rs)]
    bottoms = [z-r for z, r in zip(zs, rs)]
    volume = sum(4.0/3.0 * math.pi*r**3 for r in rs)
    result: dict[str, Any] = {
        "count": len(particles),
        "center_bounds_m": [[min(xs), max(xs)], [min(ys), max(ys)], [min(zs), max(zs)]],
        "diameter_m": {
            "min": min(ds),
            "d10_number": percentile(ds, 0.10), "d50_number": percentile(ds, 0.50), "d90_number": percentile(ds, 0.90),
            "d10_volume": weighted_percentile(ds, [d**3 for d in ds], 0.10),
            "d50_volume": weighted_percentile(ds, [d**3 for d in ds], 0.50),
            "d90_volume": weighted_percentile(ds, [d**3 for d in ds], 0.90),
            "max": max(ds),
        },
        "diameter_counts_um": dict(sorted(Counter(round(d*1e6, 6) for d in ds).items())),
        "sphere_volume_m3": volume,
        "mass_kg": volume*density if density else None,
        "top_elevation_m": {
            "min": min(tops), "p10": percentile(tops, 0.10), "p50": percentile(tops, 0.50),
            "p90": percentile(tops, 0.90), "max": max(tops),
        },
        "bottom_elevation_m": {"min": min(bottoms), "p50": percentile(bottoms, 0.50), "max": max(bottoms)},
    }
    if footprint_x and footprint_y and plate_top is not None and trim_top is not None and trim_top > plate_top:
        bulk = footprint_x * footprint_y * (trim_top - plate_top)
        clipped = sum(sphere_between_planes_volume(z, r, plate_top, trim_top) for z, r in zip(zs, rs))
        result.update({
            "nominal_layer_thickness_m": trim_top - plate_top,
            "nominal_bulk_volume_m3": bulk,
            "solid_volume_in_layer_m3": clipped,
            "packing_fraction": clipped / bulk,
            "porosity": 1.0 - clipped / bulk,
            "equivalent_solid_thickness_m": clipped / (footprint_x*footprint_y),
        })
    overlaps = []
    for i in range(len(particles)):
        xi, yi, zi, ri = particles[i]
        for j in range(i+1, len(particles)):
            xj, yj, zj, rj = particles[j]
            dist = math.sqrt((xi-xj)**2 + (yi-yj)**2 + (zi-zj)**2)
            ov = ri + rj - dist
            if ov > 0:
                overlaps.append((ov, ov/min(ri, rj)))
    result["overlap_pair_count"] = len(overlaps)
    result["max_overlap_m"] = max((x[0] for x in overlaps), default=0.0)
    result["max_overlap_to_min_radius"] = max((x[1] for x in overlaps), default=0.0)
    if footprint_x and footprint_y:
        wall_clearances = []
        for x, y, _, r in particles:
            wall_clearances.extend([x-r, footprint_x-(x+r), y-r, footprint_y-(y+r)])
        result["minimum_lateral_clearance_m"] = min(wall_clearances)
        result["lateral_clearance_below_minus_0_1um_count"] = sum(c < -0.1e-6 for c in wall_clearances)
    if cell_size:
        result["cells_per_diameter"] = {
            "min": min(ds)/cell_size, "d50": (percentile(ds, 0.50) or 0)/cell_size, "max": max(ds)/cell_size,
        }
    return result


# -------------------------- OpenFOAM field checks ---------------------------


def foam_header_object(text: str) -> str | None:
    m = re.search(r"FoamFile\s*\{(.*?)\}", text, flags=re.S)
    return word(m.group(1), "object", "") or None if m else None


def parse_boundary_types(field_text: str) -> dict[str, str]:
    clean = strip_comments(field_text)
    m = re.search(r"\bboundaryField\b\s*\{", clean)
    if not m:
        return {}
    start = clean.find("{", m.start())
    depth = 0
    end = None
    for i in range(start, len(clean)):
        if clean[i] == "{": depth += 1
        elif clean[i] == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    if end is None:
        return {}
    block = clean[start+1:end]
    result: dict[str, str] = {}
    pos = 0
    while pos < len(block):
        n = re.search(r"([A-Za-z_][\w.]*)\s*\{", block[pos:])
        if not n: break
        name = n.group(1)
        brace = pos + n.end() - 1
        d = 0
        stop = None
        for i in range(brace, len(block)):
            if block[i] == "{": d += 1
            elif block[i] == "}":
                d -= 1
                if d == 0:
                    stop = i
                    break
        if stop is None: break
        body = block[brace+1:stop]
        result[name] = word(body, "type", "未指定")
        pos = stop+1
    return result


# ----------------------------- audit assembly -------------------------------


def audit_case(root: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    findings: list[dict[str, str]] = []
    files = {
        "allrun": root / "Allrun",
        "allrun_parallel": root / "Allrun_parallel",
        "block": root / "system/blockMeshDict",
        "control": root / "system/controlDict",
        "decomp": root / "system/decomposeParDict",
        "momentum": root / "constant/momentumTransport",
        "fvsolution": root / "system/fvSolution",
        "fvschemes": root / "system/fvSchemes",
        "bed": root / "system/bedPlateDict",
        "setfields": root / "system/setFieldsDict",
        "laser": root / "constant/LaserProperties",
        "path": root / "constant/timeVsLaserPosition",
        "power": root / "constant/timeVsLaserPower",
        "phase": root / "constant/phaseProperties",
        "metal": root / "constant/physicalProperties.metal",
        "gas": root / "constant/physicalProperties.gas",
        "g": root / "constant/g",
        "location": root / "constant/location",
        "dem_input": root / "DEM_large/input.liggghts",
        "dem_check": root / "DEM_large/check.py",
        "dem_log": root / "DEM_large/log.liggghts",
        "dem_allrun": root / "DEM_large/Allrun",
    }
    missing = [relpath(p, root) for p in files.values() if not p.exists() and p.name not in {"Allrun", "log.liggghts"}]
    if missing:
        add_finding(findings, "HIGH", "关键文件缺失", ", ".join(missing), "补齐文件后重新运行审查。")

    txt = {k: read_text(p) for k, p in files.items()}
    vertices = parse_vertices(txt["block"])
    cell_counts = parse_hex_cells(txt["block"])
    pre_bounds = bounds(vertices)
    pre_lengths = [b[1]-b[0] for b in pre_bounds] if pre_bounds else None
    total_cells = math.prod(cell_counts) if cell_counts else None
    pre_cell_size = [pre_lengths[i]/cell_counts[i] for i in range(3)] if pre_lengths and cell_counts else None

    rot_spec = parse_transform_rotation(txt["allrun"] + "\n" + txt["allrun_parallel"])
    rotation = rotation_from_to(*rot_spec) if rot_spec else None
    final_vertices = [matvec(rotation, p) for p in vertices] if rotation else vertices
    final_bounds = bounds(final_vertices)
    final_lengths = [b[1]-b[0] for b in final_bounds] if final_bounds else None
    # Axis-aligned rotation preserves the 5 µm cubic cells in this case.
    nominal_cell_size = min(pre_cell_size) if pre_cell_size else None

    end_time = scalar(txt["control"], "endTime")
    delta_t = scalar(txt["control"], "deltaT")
    max_dt = scalar(txt["control"], "maxDeltaT")
    write_interval = scalar(txt["control"], "writeInterval")
    max_co = scalar(txt["control"], "maxCo")
    max_alpha_co = scalar(txt["control"], "maxAlphaCo")
    application = word(txt["control"], "application")
    start_from = word(txt["control"], "startFrom")
    actual_solver = None
    msolver = re.findall(r"runApplication\s+([\w.-]+)", txt["allrun"])
    if msolver:
        actual_solver = msolver[-1]
    elif "laserbeamFoam" in txt["allrun"]:
        actual_solver = "laserbeamFoam"

    nproc = int(scalar(txt["decomp"], "numberOfSubdomains", 0) or 0)
    decomp_n = vector_n(txt["decomp"], "n", 3)
    cells_per_proc = total_cells/nproc if total_cells and nproc else None

    laser_radius = scalar(txt["laser"], "laserRadius")
    wavelength = scalar(txt["laser"], "wavelength")
    electron_density = scalar(txt["laser"], "e_num_density")
    radius_flavour = scalar(txt["laser"], "Radius_Flavour")
    subdivisions = scalar(txt["laser"], "N_sub_divisions")
    v_incident = vector(txt["laser"], "V_incident")
    powder_sim = word(txt["laser"], "PowderSim")
    path_table = parse_vector_table(txt["path"])
    power_table = parse_scalar_table(txt["power"])
    pos0 = interpolate_vector(path_table, 0.0)
    pos_end = interpolate_vector(path_table, end_time) if end_time is not None else None
    power0 = interpolate_scalar(power_table, 0.0)
    power_end = interpolate_scalar(power_table, end_time) if end_time is not None else None
    laser_energy = integrate_scalar_table(power_table, end_time) if end_time is not None else None
    simulated_distance = math.dist(pos0, pos_end) if pos0 and pos_end else None
    mean_scan_speed = simulated_distance/end_time if simulated_distance is not None and end_time else None
    schedule_motion_end = None
    if len(path_table) >= 2:
        for (t0,p0), (t1,p1) in zip(path_table, path_table[1:]):
            if math.dist(p0, p1) > 0:
                schedule_motion_end = t1
    schedule_end = max((t for t, _ in path_table), default=None)
    nominal_scan_speed = None
    speeds = []
    for (t0,p0), (t1,p1) in zip(path_table, path_table[1:]):
        if t1 > t0 and math.dist(p0,p1) > 0:
            speeds.append(math.dist(p0,p1)/(t1-t0))
    if speeds:
        nominal_scan_speed = sum(speeds)/len(speeds)
    line_energy = power_end/nominal_scan_speed if power_end is not None and nominal_scan_speed else None

    # Bed geometry is specified before transformPoints.
    bed = {k: scalar(txt["bed"], k) for k in ("xmin","xmax","ymin","ymax","zmin","zmax")}
    footprint_x = (bed["xmax"]-bed["xmin"]) if bed["xmax"] is not None and bed["xmin"] is not None else None
    footprint_y = (bed["ymax"]-bed["ymin"]) if bed["ymax"] is not None and bed["ymin"] is not None else None
    plate_top = bed["zmax"]

    # DEM setup.
    dem_timestep = scalar(txt["dem_input"], "timestep")
    # timestep has no semicolon in LIGGGHTS, so use a second parser.
    md = re.search(r"(?m)^\s*timestep\s+([+\-\d.eE]+)", strip_comments(txt["dem_input"]))
    dem_timestep = float(md.group(1)) if md else dem_timestep
    insert_rate = None
    insert_every = None
    nparticles_requested = None
    mi = re.search(r"fix\s+ins\b.*?insert/rate/region(.*?)(?:\n\s*\n|# Boundary)", txt["dem_input"], re.S)
    if mi:
        body = mi.group(1).replace("&", " ")
        for key in ("particlerate", "insert_every", "nparticles"):
            mm = re.search(rf"\b{key}\s+([+\-\d.eE]+)", body)
            if mm:
                val = float(mm.group(1))
                if key == "particlerate": insert_rate = val
                elif key == "insert_every": insert_every = int(val)
                else: nparticles_requested = int(val)
    particles_per_event = insert_rate*insert_every*dem_timestep if all(v is not None for v in (insert_rate,insert_every,dem_timestep)) else None
    trim_match = re.search(r'z\s*\+\s*c_1\s*>\s*([+\-\d.eE]+)', txt["dem_input"])
    trim_top = float(trim_match.group(1))*0.01 if trim_match else None  # cgs cm -> m
    dump_step, particles = parse_last_liggghts_dump(files["location"])
    metal_density = scalar(txt["metal"], "rho")
    pmetrics = particle_metrics(particles, footprint_x, footprint_y, plate_top, trim_top, metal_density, nominal_cell_size)
    target_layer = python_constant(txt["dem_check"], "TARGET_LAYER_UM")
    target_packing = python_constant(txt["dem_check"], "TARGET_PACKING_FRACTION")
    if pmetrics.get("equivalent_solid_thickness_m") is not None:
        eq_um = pmetrics["equivalent_solid_thickness_m"] * 1e6
        pmetrics["target_layer_thickness_m"] = target_layer*1e-6 if target_layer else None
        pmetrics["target_packing_fraction"] = target_packing
        pmetrics["apparent_packing_at_target_layer"] = eq_um/target_layer if target_layer else None
        pmetrics["implied_layer_thickness_at_target_packing_m"] = (eq_um/target_packing)*1e-6 if target_packing else None
        if plate_top is not None:
            pmetrics["top_height_above_plate_m"] = {
                k: (v-plate_top if v is not None else None)
                for k,v in pmetrics.get("top_elevation_m",{}).items()
            }

    terminal_text = read_text(root/"DEM_large/terminal.log")
    warning_counts = [len(re.findall(r"Less insertions than requested", t, flags=re.I)) for t in (txt["dem_log"], terminal_text)]
    insertion_warnings = max(warning_counts, default=0)
    log_text = txt["dem_log"] + "\n" + terminal_text
    deleted_match = re.findall(r"Deleted\s+(\d+)\s+atoms", log_text, flags=re.I)
    deleted_particles = int(deleted_match[-1]) if deleted_match else None
    dangerous = re.findall(r"Dangerous builds\s*=\s*(\d+)", log_text, flags=re.I)
    dangerous_builds = int(dangerous[-1]) if dangerous else None
    dem_clean = strip_comments(txt["dem_input"])
    def ligg_value(pattern: str) -> float | None:
        mm = re.search(pattern, dem_clean, flags=re.M)
        return float(mm.group(1)) if mm else None
    dem_contact = {
        "youngs_modulus_cgs": ligg_value(r"^\s*fix\s+\w+\s+all\s+property/global\s+youngsModulus\s+peratomtype\s+([+\-\d.eE]+)"),
        "poisson_ratio": ligg_value(r"^\s*fix\s+\w+\s+all\s+property/global\s+poissonsRatio\s+peratomtype\s+([+\-\d.eE]+)"),
        "coefficient_restitution": ligg_value(r"^\s*fix\s+\w+\s+all\s+property/global\s+coefficientRestitution.*?([+\-\d.eE]+)\s*$"),
        "coefficient_friction": ligg_value(r"^\s*fix\s+\w+\s+all\s+property/global\s+coefficientFriction.*?([+\-\d.eE]+)\s*$"),
        "gravity_cgs_cm_s2": ligg_value(r"^\s*fix\s+grav\s+all\s+gravity\s+([+\-\d.eE]+)"),
    }

    phase = {
        "surface_tension_N_m": scalar(txt["phase"], "sigma"),
        "dsigma_dT_N_m_K": scalar(txt["phase"], "dsigmadT"),
        "ambient_pressure_Pa": scalar(txt["phase"], "p0"),
        "vaporization_temperature_K": scalar(txt["phase"], "Tvap"),
        "molar_mass_kg_mol": scalar(txt["phase"], "Mm"),
        "latent_heat_vaporization_J_kg": scalar(txt["phase"], "LatentHeatVap"),
    }
    metal = {
        "rho_kg_m3": metal_density,
        "nu_m2_s": scalar(txt["metal"], "nu"),
        "electrical_resistivity_ohm_m": scalar(txt["metal"], "elec_resistivity"),
        "solidus_K": scalar(txt["metal"], "Tsolidus"),
        "liquidus_K": scalar(txt["metal"], "Tliquidus"),
        "latent_heat_fusion_J_kg": scalar(txt["metal"], "LatentHeat"),
        "thermal_expansion_1_K": scalar(txt["metal"], "beta"),
        "k_polynomial": vector_n(txt["metal"], "poly_kappa", 8),
        "cp_polynomial": vector_n(txt["metal"], "poly_cp", 8),
    }
    gas = {"rho_kg_m3": scalar(txt["gas"], "rho"), "nu_m2_s": scalar(txt["gas"], "nu")}
    def poly_eval(coeffs: Sequence[float] | None, temperature: float | None) -> float | None:
        if coeffs is None or temperature is None:
            return None
        return sum(c * temperature**i for i,c in enumerate(coeffs))
    metal["dynamic_viscosity_Pa_s"] = (metal["rho_kg_m3"]*metal["nu_m2_s"] if metal["rho_kg_m3"] and metal["nu_m2_s"] else None)
    gas["dynamic_viscosity_Pa_s"] = (gas["rho_kg_m3"]*gas["nu_m2_s"] if gas["rho_kg_m3"] and gas["nu_m2_s"] else None)
    metal["evaluated_properties"] = {}
    for label, temperature in (("300K",300.0), ("solidus",metal["solidus_K"]), ("liquidus",metal["liquidus_K"])):
        kval = poly_eval(metal["k_polynomial"], temperature)
        cpval = poly_eval(metal["cp_polynomial"], temperature)
        alpha = kval/(metal["rho_kg_m3"]*cpval) if kval and cpval and metal["rho_kg_m3"] else None
        metal["evaluated_properties"][label] = {"temperature_K":temperature,"k_W_m_K":kval,"cp_J_kg_K":cpval,"thermal_diffusivity_m2_s":alpha}
    metal["melting_range_K"] = (metal["liquidus_K"]-metal["solidus_K"] if metal["liquidus_K"] is not None and metal["solidus_K"] is not None else None)
    gravity = vector(txt["g"], "value") or vector(txt["g"], "g")
    if gravity is None:
        mg = re.search(r"value\s*\(?\s*uniform\s*\(([^)]+)\)", strip_comments(txt["g"]))
        if mg:
            gravity = [float(v) for v in mg.group(1).split()]

    mesh_patch_types = parse_patch_types(txt["block"])
    field_files = list((root/"initial").glob("*")) if (root/"initial").exists() else []
    field_data: dict[str, Any] = {}
    for fp in sorted(f for f in field_files if f.is_file()):
        ft = read_text(fp)
        field_data[fp.name] = {
            "header_object": foam_header_object(ft),
            "internal_field": (re.search(r"internalField\s+([^;]+);", strip_comments(ft)) or [None, ""])[1].strip(),
            "boundary_types": parse_boundary_types(ft),
        }

    # Findings: reproducibility and metadata.
    if application and actual_solver and application != actual_solver:
        add_finding(findings, "HIGH", "controlDict 的 application 与实际求解器不一致",
                    f"application={application}，Allrun 实际执行 {actual_solver}。这会误导复现者，并可能影响依赖 application 字段的流程。",
                    f"把 system/controlDict 中 application 改为 {actual_solver}。")
    if start_from == "latestTime":
        add_finding(findings, "HIGH", "默认从 latestTime 启动，容易意外续算旧结果",
                    "Allrun 仅执行 cp -r initial 0，未先删除旧时间目录；若 0 已存在，复制语义也可能生成 0/initial。",
                    "在全新运行脚本中先清理 0 和数值时间目录，或改为 startFrom startTime；续算另设独立脚本。")
    for name, info in field_data.items():
        obj = info.get("header_object")
        if obj and obj != name:
            add_finding(findings, "HIGH", f"字段头部 object 名称错误：initial/{name}",
                        f"文件名为 {name}，FoamFile.object 却为 {obj}。", f"将 object 改为 {name}，随后运行 foamDictionary/求解器启动检查。")
    dictionary_expected = {"LaserProperties":"LaserProperties", "physicalProperties.metal":"physicalProperties.metal", "physicalProperties.gas":"physicalProperties.gas"}
    for key, expected in dictionary_expected.items():
        file_key = "laser" if key == "LaserProperties" else ("metal" if key.endswith("metal") else "gas")
        obj = foam_header_object(txt[file_key])
        if obj and obj != expected:
            add_finding(findings, "MEDIUM", f"字典 object 元数据陈旧：constant/{key}",
                        f"FoamFile.object={obj}，与文件名 {expected} 不一致。", "统一 object 名称，减少版本迁移和自动检查歧义。")

    # Laser-domain consistency after rotation.
    if final_bounds and pos0:
        outside_axes = []
        for i, axis in enumerate("xyz"):
            if pos0[i] < final_bounds[i][0] or pos0[i] > final_bounds[i][1]:
                outside_axes.append((axis, pos0[i], final_bounds[i]))
        if outside_axes:
            details = "; ".join(f"{a}={v*1e6:.3f} μm，域范围 [{b[0]*1e6:.3f},{b[1]*1e6:.3f}] μm" for a,v,b in outside_axes)
            dir_note = ""
            if v_incident:
                center = [(b[0]+b[1])/2 for b in final_bounds]
                toward_center = dot(v_incident, [center[i]-pos0[i] for i in range(3)])
                if toward_center < 0:
                    dir_note = " 且 V_incident 按通常传播方向解释时指向远离计算域的一侧。"
            add_finding(findings, "HIGH", "旋转后激光位置与计算域坐标需核验",
                        f"t=0 激光中心位于旋转后域外：{details}.{dir_note}",
                        "确认 LaserBeamFoam 对 V_incident 的符号定义；用 transformPoints 后的实际网格坐标重写轨迹，并在 ParaView 中显示激光中心/射线进行验证。")
    if end_time and schedule_motion_end and end_time < schedule_motion_end*0.999:
        add_finding(findings, "MEDIUM", "模拟时间只覆盖激光计划的一部分",
                    f"endTime={end_time*1e6:.3f} μs，而移动轨迹定义到 {schedule_motion_end*1e6:.3f} μs；本次仅覆盖约 {end_time/schedule_motion_end:.1%}。",
                    "在报告/目录名中明确这是 100 μs 初始段；若目标是整条 1 mm 扫描，将 endTime 延长到至少 1000 μs。")
    if pmetrics.get("packing_fraction") is not None and pmetrics.get("target_layer_thickness_m"):
        add_finding(findings, "MEDIUM", "截断高度与名义层厚的定义需要区分",
                    f"按 100–{trim_top*1e6:.0f} μm 整个截断区计算，固相体积分数为 {pmetrics['packing_fraction']:.3f}；但按 check.py 的 {pmetrics['target_layer_thickness_m']*1e6:.0f} μm 目标层厚计算，表观堆积率为 {pmetrics['apparent_packing_at_target_layer']:.3f}。",
                    "报告中同时给出截断区厚度、目标名义层厚、等效致密厚度及顶部高度分布，避免把 180 μm 截断面直接当作均匀粉层顶面。")
    if pmetrics.get("diameter_m") and pmetrics["diameter_m"].get("max") and pmetrics["diameter_m"]["max"] < 70e-6:
        add_finding(findings, "MEDIUM", "最终 PSD 与输入 PSD 有明显选择性偏差",
                    f"输入模板覆盖约 32.5–77.5 μm，但最终颗粒最大直径为 {pmetrics['diameter_m']['max']*1e6:.1f} μm，较大颗粒可能在截断时被优先删除。",
                    "同时保存插入前、沉降后和截断后的 PSD；不要只用输入分布代表最终粉末床。")
    if insertion_warnings:
        add_finding(findings, "MEDIUM", "DEM 插入阶段出现受限插入警告",
                    f"日志中检测到 {insertion_warnings} 次 “Less insertions than requested”。这通常表示当前插入区域/重叠约束无法在该事件中达到计划数量。",
                    "结合实际累计插入数检查；必要时扩大 factory 区、降低每事件数量、增加 ntry_mc 或延长插入阶段。")
    if dem_contact.get("youngs_modulus_cgs") is not None:
        young_pa = dem_contact["youngs_modulus_cgs"] * 0.1  # dyn/cm^2 -> Pa
        if young_pa < 1e8:
            add_finding(findings, "MEDIUM", "DEM 使用了显著软化的接触刚度",
                        f"youngsModulus=5e7（cgs 压力单位），等效约 {young_pa/1e6:.3g} MPa；这应被视为数值加速参数，而非 M247 的真实弹性模量。",
                        "记录软化依据，并对 Young 模量和 DEM 时间步进行敏感性检查，确认最终堆积率与 PSD 不依赖该数值选择。")
    if "check/timestep/gran" in txt["dem_input"] and not re.search(r"(?m)^\s*fix\s+\w+\s+all\s+check/timestep/gran", strip_comments(txt["dem_input"])):
        add_finding(findings, "MEDIUM", "DEM 时间步安全检查被注释",
                    "input.liggghts 中存在 check/timestep/gran 示例，但当前未启用。",
                    "在材料/接触参数确定后临时启用 check/timestep/gran，记录 Rayleigh/Hertz 时间步比例，再决定生产 timestep。")
    if files["dem_allrun"].exists() and re.search(r"(?m)^\s*#\s*cp\s+.*location", txt["dem_allrun"]):
        add_finding(findings, "MEDIUM", "DEM 结果不会自动同步到 CFD 算例",
                    "DEM_large/Allrun 中复制 location 到 constant 的命令被注释，且示例路径写成 /post/location。",
                    "显式执行 cp post/location ../constant/location，并在复制后运行本审查脚本；建议把该步骤写入可失败即停止的工作流。")
    if particles_per_event is not None:
        if abs(particles_per_event-round(particles_per_event)) > 1e-6:
            add_finding(findings, "LOW", "每次插入事件的名义颗粒数不是整数",
                        f"particlerate × insert_every × timestep = {particles_per_event:.4g}。", "调整参数使每事件目标数量清晰、可解释。")
    if files["dem_allrun"].exists() and re.search(r"/home/[^\s]+/liggghts", txt["dem_allrun"]):
        add_finding(findings, "MEDIUM", "DEM 启动脚本含用户机器绝对路径",
                    "DEM_large/Allrun 将 LIGGGHTS 可执行文件写死为 /home/...。", "改用环境变量、PATH 或脚本参数，例如 ${LIGGGHTS_BIN:-liggghts}。")
    if txt["setfields"] and "setFields" not in txt["allrun"]:
        add_finding(findings, "LOW", "setFieldsDict 当前未被 Allrun 使用",
                    "主流程执行 setSolidFraction，而不是 setFields。保留的 setFieldsDict 容易被误认为有效配置。",
                    "删除、归档或在 README 中标注该文件为弃用配置。")
    extra_patches = set()
    for info in field_data.values():
        extra_patches |= set(info["boundary_types"]) - set(mesh_patch_types)
    if extra_patches:
        add_finding(findings, "LOW", "初始字段包含网格中不存在的边界条目",
                    f"额外条目：{', '.join(sorted(extra_patches))}。", "清理 defaultFaces 等遗留条目，使边界字典与 blockMesh 完全一致。")
    if subdivisions is not None and subdivisions <= 1:
        add_finding(findings, "LOW", "激光子划分数较低",
                    f"N_sub_divisions={subdivisions:g}。在自由表面曲率大或粉末多次反射敏感时，角向/面积积分分辨率可能不足。",
                    "先做 N_sub_divisions 的网格独立性/能量吸收敏感性对比，再决定生产值。")

    result: dict[str, Any] = {
        "audit": {
            "generated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "case_root": str(root.resolve()),
            "git_revision": git_revision(root),
            "script_version": "1.1.0",
        },
        "workflow": {
            "serial_commands": re.findall(r"runApplication\s+([^\n]+)", txt["allrun"]),
            "controlDict_application": application,
            "actual_solver": actual_solver,
            "startFrom": start_from,
        },
        "coordinates": {
            "transform_rotation_from_to": rot_spec,
            "rotation_matrix": rotation,
            "gravity_m_s2": gravity,
            "laser_incident_direction": v_incident,
            "pre_rotation_bounds_m": pre_bounds,
            "final_bounds_m": final_bounds,
        },
        "mesh": {
            "pre_rotation_lengths_m": pre_lengths,
            "final_lengths_m": final_lengths,
            "cell_counts_block": cell_counts,
            "total_cells": total_cells,
            "pre_rotation_cell_sizes_m": pre_cell_size,
            "nominal_min_cell_size_m": nominal_cell_size,
            "mesh_patch_types": mesh_patch_types,
        },
        "powder_bed": {
            "bed_plate_pre_rotation_m": bed,
            "trim_top_m": trim_top,
            "dump_timestep": dump_step,
            "particles": pmetrics,
            "dem": {
                "units": "cgs",
                "timestep_s": dem_timestep,
                "requested_particles": nparticles_requested,
                "particle_rate_per_s": insert_rate,
                "insert_every_steps": insert_every,
                "nominal_particles_per_event": particles_per_event,
                "insertion_warning_count": insertion_warnings,
                "deleted_particles_from_log": deleted_particles,
                "dangerous_builds": dangerous_builds,
                "contact_model": "hertz tangential history",
                "contact_parameters": dem_contact,
            },
        },
        "laser": {
            "radius_m": laser_radius,
            "diameter_m": 2*laser_radius if laser_radius else None,
            "cells_per_radius": laser_radius/nominal_cell_size if laser_radius and nominal_cell_size else None,
            "cells_per_diameter": 2*laser_radius/nominal_cell_size if laser_radius and nominal_cell_size else None,
            "wavelength_m": wavelength,
            "electron_number_density_m3": electron_density,
            "Radius_Flavour": radius_flavour,
            "N_sub_divisions": subdivisions,
            "PowderSim": powder_sim,
            "path_table": path_table,
            "power_table": power_table,
            "position_at_start_m": pos0,
            "position_at_endTime_m": pos_end,
            "power_at_start_W": power0,
            "power_at_endTime_W": power_end,
            "nominal_scan_speed_m_s": nominal_scan_speed,
            "simulated_distance_m": simulated_distance,
            "mean_speed_over_simulation_m_s": mean_scan_speed,
            "line_energy_J_m": line_energy,
            "energy_deposited_by_power_schedule_J": laser_energy,
            "path_schedule_end_s": schedule_end,
            "motion_schedule_end_s": schedule_motion_end,
        },
        "materials": {"metal": metal, "gas": gas, "interface_and_vaporization": phase},
        "numerics": {
            "endTime_s": end_time, "initial_deltaT_s": delta_t, "maxDeltaT_s": max_dt,
            "writeInterval_s": write_interval, "maxCo": max_co, "maxAlphaCo": max_alpha_co,
            "nominal_initial_step_count": end_time/delta_t if end_time and delta_t else None,
            "minimum_output_interval_count": end_time/write_interval if end_time and write_interval else None,
            "parallel_subdomains": nproc, "decomposition_n": decomp_n,
            "average_cells_per_subdomain": cells_per_proc,
            "momentum_model": word(txt.get("momentum", ""), "simulationType", "laminar") or "laminar",
            "schemes": {
                "time": raw_entry(txt["fvschemes"], r"default", "").split()[0] if raw_entry(txt["fvschemes"], r"default", "") else None,
                "div_phi_U": raw_entry(txt["fvschemes"], r'div\(rhoPhi,U\)', ""),
                "div_phi_T": raw_entry(txt["fvschemes"], r'div\(\(interpolate\(cp\)\*rhoPhi\),T\)', ""),
                "div_alpha": raw_entry(txt["fvschemes"], r'div\(phi,alpha\)', ""),
                "laplacian_default": raw_entry(txt["fvschemes"], r"default", ""),
            },
            "pimple": {
                "nOuterCorrectors": scalar(txt["fvsolution"], "nOuterCorrectors"),
                "nCorrectors": scalar(txt["fvsolution"], "nCorrectors"),
                "nNonOrthogonalCorrectors": scalar(txt["fvsolution"], "nNonOrthogonalCorrectors"),
            },
            "alpha_controls": {
                "nAlphaCorr": scalar(txt["fvsolution"], "nAlphaCorr"),
                "nAlphaSubCycles": scalar(txt["fvsolution"], "nAlphaSubCycles"),
            },
        },
        "initial_fields": field_data,
        "findings": findings,
    }
    return result, findings


# ------------------------------ report writer -------------------------------


def v3_um(v: Sequence[float] | None) -> str:
    return "未读取" if not v else "(" + ", ".join(f"{x*1e6:.3f}" for x in v) + ") μm"


def bounds_um(b: Sequence[Sequence[float]] | None) -> str:
    if not b:
        return "未读取"
    return "; ".join(f"{a}=[{r[0]*1e6:.3f}, {r[1]*1e6:.3f}] μm" for a,r in zip("xyz", b))


def render_markdown(data: dict[str, Any]) -> str:
    a = data["audit"]
    wf = data["workflow"]
    c = data["coordinates"]
    m = data["mesh"]
    pb = data["powder_bed"]
    pm = pb["particles"]
    dem = pb["dem"]
    laser = data["laser"]
    mat = data["materials"]
    num = data["numerics"]
    findings = data["findings"]
    counts = {s: sum(f["severity"] == s for f in findings) for s in ("HIGH","MEDIUM","LOW","INFO")}

    lines: list[str] = []
    lines += [
        "# LPBF / LaserBeamFoam 算例审查报告",
        "",
        f"- 生成时间：{a['generated_at']}",
        f"- 算例根目录：`{a['case_root']}`",
        f"- Git revision：`{a['git_revision'] or '未检测到 Git 元数据'}`",
        f"- 审查脚本版本：{a['script_version']}",
        "",
        "## 1. 结论摘要",
        "",
        f"该算例使用约 **{m['total_cells']:,}** 个六面体单元、**{pm.get('count',0)}** 个最终粉末颗粒、"
        f"激光半径 **{fmt_um(laser['radius_m'])}**，在 **{fmt_us(num['endTime_s'])}** 的时间窗内模拟扫描初始段。",
        f"自动检查得到：**HIGH {counts['HIGH']} 项、MEDIUM {counts['MEDIUM']} 项、LOW {counts['LOW']} 项**。",
        "",
        "最优先核验事项是：① `transformPoints` 后的激光位置/方向；② `controlDict` 求解器名称与实际命令；"
        "③ `initial/T`、`initial/Laser_boundary` 等 FoamFile.object 元数据；④ 粉末床堆积率与最终 PSD。",
        "",
        "## 2. 运行流程与复现入口",
        "",
        f"- `controlDict.application`：`{wf['controlDict_application']}`",
        f"- Allrun 实际求解器：`{wf['actual_solver']}`",
        f"- `startFrom`：`{wf['startFrom']}`",
        "- 串行流程：复制 `initial` → `blockMesh` → `setSolidFraction` → `transformPoints` → `laserbeamFoam`。",
        "- 粉末来源：`DEM_large/input.liggghts` 生成颗粒，最终 `constant/location` 被 `setSolidFraction` 读取。",
        "",
        "## 3. 坐标系、几何与网格",
        "",
        f"- 旋转前网格范围：{bounds_um(c['pre_rotation_bounds_m'])}",
        f"- 旋转后实际范围：{bounds_um(c['final_bounds_m'])}",
        f"- `transformPoints` 旋转：{c['transform_rotation_from_to'] or '无'}",
        f"- 重力：{c['gravity_m_s2']} m/s²；激光入射向量：{c['laser_incident_direction']}",
        f"- block 单元数：{m['cell_counts_block']}；总单元：{m['total_cells']:,}",
        f"- 旋转前单元尺寸：{', '.join(fmt_um(x) for x in (m['pre_rotation_cell_sizes_m'] or []))}",
        f"- 激光直径跨越约 **{fmt_num(laser['cells_per_diameter'],4)} 个单元**；半径跨越约 {fmt_num(laser['cells_per_radius'],4)} 个单元。",
        "",
        "旋转 `(0,1,0) → (0,0,1)` 后，本算例的空间语义可读为：最终 **Y 为竖直方向**、最终 **Z 为扫描长方向**；"
        "边界名称不会因旋转自动改名，因此 `topWall`、`rightWall` 等名称应按实际几何位置解释，而不能只按名字解释。",
        "",
        "## 4. 粉末床与 DEM 指标",
        "",
        f"- 最终颗粒数：**{pm.get('count',0)}**；location 时间步：{pb['dump_timestep']}",
        f"- 粒径（数量分布）：Dmin={fmt_um(pm.get('diameter_m',{}).get('min'))}，"
        f"D10={fmt_um(pm.get('diameter_m',{}).get('d10_number'))}，D50={fmt_um(pm.get('diameter_m',{}).get('d50_number'))}，"
        f"D90={fmt_um(pm.get('diameter_m',{}).get('d90_number'))}，Dmax={fmt_um(pm.get('diameter_m',{}).get('max'))}",
        f"- 粒径（体积加权）：D10={fmt_um(pm.get('diameter_m',{}).get('d10_volume'))}，"
        f"D50={fmt_um(pm.get('diameter_m',{}).get('d50_volume'))}，D90={fmt_um(pm.get('diameter_m',{}).get('d90_volume'))}",
        f"- 粉末质量：{(pm.get('mass_kg') or 0)*1e6:.6f} mg；球体总体积：{(pm.get('sphere_volume_m3') or 0)*1e9:.6f} mm³",
        f"- 截断区厚度：{fmt_um(pm.get('nominal_layer_thickness_m'))}；该整个区间的固相体积分数：**{fmt_num(pm.get('packing_fraction'),4)}**；"
        f"孔隙率：**{fmt_num(pm.get('porosity'),4)}**",
        f"- 等效致密固体厚度：{fmt_um(pm.get('equivalent_solid_thickness_m'))}；check.py 目标层厚：{fmt_um(pm.get('target_layer_thickness_m'))}；"
        f"按目标层厚计算的表观堆积率：**{fmt_num(pm.get('apparent_packing_at_target_layer'),4)}**",
        f"- 若目标堆积率为 {fmt_num(pm.get('target_packing_fraction'),3)}，当前粉末量对应名义层厚：{fmt_um(pm.get('implied_layer_thickness_at_target_packing_m'))}",
        f"- 颗粒顶部高度：P10={fmt_um(pm.get('top_elevation_m',{}).get('p10'))}，"
        f"P50={fmt_um(pm.get('top_elevation_m',{}).get('p50'))}，"
        f"P90={fmt_um(pm.get('top_elevation_m',{}).get('p90'))}，最大={fmt_um(pm.get('top_elevation_m',{}).get('max'))}",
        f"- 相对基板顶面的颗粒顶部高度：P50={fmt_um(pm.get('top_height_above_plate_m',{}).get('p50'))}，"
        f"P90={fmt_um(pm.get('top_height_above_plate_m',{}).get('p90'))}，最大={fmt_um(pm.get('top_height_above_plate_m',{}).get('max'))}",
        f"- 接触重叠对数：{pm.get('overlap_pair_count',0)}；最大几何重叠：{fmt_um(pm.get('max_overlap_m'),6)}；"
        f"最大重叠/较小半径：{fmt_pct(pm.get('max_overlap_to_min_radius'),4)}",
        f"- DEM 时间步：{fmt_num(dem['timestep_s'])} s；插入率：{fmt_num(dem['particle_rate_per_s'])} 1/s；"
        f"insert_every={dem['insert_every_steps']}；名义每事件插入数={fmt_num(dem['nominal_particles_per_event'])}",
        f"- 请求插入：{dem['requested_particles']}；日志删除：{dem['deleted_particles_from_log']}；"
        f"最终保留：{pm.get('count',0)}；受限插入警告：{dem['insertion_warning_count']} 次。",
        f"- DEM 接触模型：{dem.get('contact_model')}；参数={dem.get('contact_parameters')}",
        "",
        "最终离散粒径计数（μm → 颗粒数）：",
        "",
        "```text",
        ", ".join(f"{d:g}: {n}" for d,n in pm.get('diameter_counts_um',{}).items()),
        "```",
        "",
        "## 5. 激光与工艺参数",
        "",
        f"- 激光半径/直径：{fmt_um(laser['radius_m'])} / {fmt_um(laser['diameter_m'])}",
        f"- 波长：{laser['wavelength_m']*1e6:.4f} μm；电子数密度：{fmt_num(laser['electron_number_density_m3'])} m⁻³",
        f"- `Radius_Flavour`={laser['Radius_Flavour']}；`N_sub_divisions`={laser['N_sub_divisions']}；`PowderSim`={laser['PowderSim']}",
        f"- t=0 位置：{v3_um(laser['position_at_start_m'])}；t=endTime 位置：{v3_um(laser['position_at_endTime_m'])}",
        f"- t=0 功率：{fmt_num(laser['power_at_start_W'])} W；t=endTime 功率：{fmt_num(laser['power_at_endTime_W'])} W",
        f"- 名义扫描速度：{fmt_num(laser['nominal_scan_speed_m_s'])} m/s；本次模拟距离：{fmt_um(laser['simulated_distance_m'])}",
        f"- 名义线能量 P/v：{fmt_num(laser['line_energy_J_m'])} J/m（即 {fmt_num((laser['line_energy_J_m'] or 0)/1000)} J/mm）",
        f"- 功率时间表在本次时间窗内积分能量：{fmt_num(laser['energy_deposited_by_power_schedule_J'])} J",
        f"- 轨迹移动定义到：{fmt_us(laser['motion_schedule_end_s'])}；算例 endTime：{fmt_us(num['endTime_s'])}",
        "",
        "说明：这里的“积分能量”是输入功率对时间的积分，不等于材料实际吸收能量；实际吸收还受光学模型、自由表面、反射和数值离散影响。",
        "",
        "## 6. 材料与界面物性",
        "",
        f"- 金属：ρ={fmt_num(mat['metal']['rho_kg_m3'])} kg/m³，ν={fmt_num(mat['metal']['nu_m2_s'])} m²/s，"
        f"Tsolidus={fmt_num(mat['metal']['solidus_K'])} K，Tliquidus={fmt_num(mat['metal']['liquidus_K'])} K，"
        f"Lf={fmt_num(mat['metal']['latent_heat_fusion_J_kg'])} J/kg",
        f"- 动力黏度 μ=ρν：{fmt_num(mat['metal']['dynamic_viscosity_Pa_s'])} Pa·s；熔化区间：{fmt_num(mat['metal']['melting_range_K'])} K",
        f"- 导热系数多项式系数：{mat['metal']['k_polynomial']}；比热多项式系数：{mat['metal']['cp_polynomial']}",
        f"- 300 K：k={fmt_num(mat['metal']['evaluated_properties']['300K']['k_W_m_K'])} W/(m·K)，"
        f"cp={fmt_num(mat['metal']['evaluated_properties']['300K']['cp_J_kg_K'])} J/(kg·K)，"
        f"α={fmt_num(mat['metal']['evaluated_properties']['300K']['thermal_diffusivity_m2_s'])} m²/s",
        f"- solidus：k={fmt_num(mat['metal']['evaluated_properties']['solidus']['k_W_m_K'])} W/(m·K)，"
        f"cp={fmt_num(mat['metal']['evaluated_properties']['solidus']['cp_J_kg_K'])} J/(kg·K)；"
        f"liquidus：k={fmt_num(mat['metal']['evaluated_properties']['liquidus']['k_W_m_K'])} W/(m·K)，"
        f"cp={fmt_num(mat['metal']['evaluated_properties']['liquidus']['cp_J_kg_K'])} J/(kg·K)",
        f"- 表面张力 σ={fmt_num(mat['interface_and_vaporization']['surface_tension_N_m'])} N/m；"
        f"dσ/dT={fmt_num(mat['interface_and_vaporization']['dsigma_dT_N_m_K'])} N/(m·K)",
        f"- 蒸发：Tvap={fmt_num(mat['interface_and_vaporization']['vaporization_temperature_K'])} K，"
        f"Lv={fmt_num(mat['interface_and_vaporization']['latent_heat_vaporization_J_kg'])} J/kg，"
        f"p0={fmt_num(mat['interface_and_vaporization']['ambient_pressure_Pa'])} Pa",
        f"- 气相：ρ={fmt_num(mat['gas']['rho_kg_m3'])} kg/m³，ν={fmt_num(mat['gas']['nu_m2_s'])} m²/s。",
        "",
        "## 7. 时间推进、输出与并行设置",
        "",
        f"- endTime={fmt_us(num['endTime_s'])}；初始 Δt={num['initial_deltaT_s']:.3e} s；最大 Δt={num['maxDeltaT_s']:.3e} s",
        f"- maxCo={num['maxCo']}；maxAlphaCo={num['maxAlphaCo']}；writeInterval={fmt_us(num['writeInterval_s'])}",
        f"- 若始终使用初始 Δt，名义步数约 {num['nominal_initial_step_count']:.0f}；实际步数由可调时间步决定。",
        f"- 并行域数：{num['parallel_subdomains']}；simple 分解 n={num['decomposition_n']}；"
        f"平均约 {num['average_cells_per_subdomain']:.0f} cells/rank。",
        f"- 动量模型：{num['momentum_model']}；PIMPLE={num['pimple']}；alpha 控制={num['alpha_controls']}",
        f"- 关键离散格式：U 对流={num['schemes']['div_phi_U']}；T 对流={num['schemes']['div_phi_T']}；alpha 对流={num['schemes']['div_alpha']}",
        "",
        "## 8. 初始/边界条件概览",
        "",
    ]
    for field, info in data["initial_fields"].items():
        b = ", ".join(f"{k}:{v}" for k,v in info["boundary_types"].items())
        lines.append(f"- `{field}`：object=`{info['header_object']}`；internalField=`{info['internal_field']}`；边界={b}")

    lines += ["", "## 9. 自动发现的问题与建议", ""]
    order = {"HIGH":0,"MEDIUM":1,"LOW":2,"INFO":3}
    for i, f in enumerate(sorted(findings, key=lambda x: order.get(x["severity"],9)), 1):
        lines += [
            f"### {i}. [{f['severity']}] {f['title']}",
            "",
            f"**现象：** {f['detail']}",
            "",
            f"**建议：** {f['action']}",
            "",
        ]
    lines += [
        "## 10. 建议的算例归档清单",
        "",
        "每次正式计算建议同时归档以下内容：",
        "",
        "1. 本报告与 JSON；Git commit/hash；OpenFOAM、LaserBeamFoam、LIGGGHTS 版本和编译选项。",
        "2. `checkMesh`、`setSolidFraction`、求解器完整日志，以及并行分解与重构日志。",
        "3. 粉末床的最终 `location`、PSD、体积分数、顶部高度分布、截断前后颗粒数。",
        "4. 激光轨迹在最终旋转坐标系中的可视化截图或采样点；明确传播向量符号约定。",
        "5. 能量守恒、最大温度、熔池长/宽/深、熔化体积、气液界面质量守恒和 Courant 数历史。",
        "",
        "---",
        "本报告是静态配置审查，不能替代实际运行时的 `checkMesh`、日志收敛检查、质量/能量守恒检查和结果物理验证。",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit an LPBF LaserBeamFoam/OpenFOAM case.")
    parser.add_argument("case_root", nargs="?", default=".", help="Case root containing constant/, system/, initial/.")
    parser.add_argument("-o", "--output-dir", default="case_audit", help="Output directory (relative to case root unless absolute).")
    parser.add_argument("--fail-on-high", action="store_true", help="Return exit code 1 when HIGH findings exist (useful in CI).")
    args = parser.parse_args()
    root = Path(args.case_root).expanduser().resolve()
    if not root.exists():
        print(f"ERROR: case root does not exist: {root}", file=sys.stderr)
        return 2
    out = Path(args.output_dir).expanduser()
    if not out.is_absolute():
        out = root / out
    out.mkdir(parents=True, exist_ok=True)
    data, findings = audit_case(root)
    md_path = out / "LPBF_case_audit.md"
    json_path = out / "LPBF_case_audit.json"
    md_path.write_text(render_markdown(data), encoding="utf-8")
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    counts = Counter(f["severity"] for f in findings)
    print(f"Audit complete: {md_path}")
    print(f"JSON metrics:  {json_path}")
    print(f"Findings: HIGH={counts['HIGH']} MEDIUM={counts['MEDIUM']} LOW={counts['LOW']}")
    if counts["HIGH"] and not args.fail_on_high:
        print("Note: HIGH findings were reported, but the audit completed successfully. Use --fail-on-high for CI gating.")
    return 1 if args.fail_on_high and counts["HIGH"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
