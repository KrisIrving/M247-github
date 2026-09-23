#!/usr/bin/env python3
"""Compare identical official LPBF_small_vapour inputs with two solver builds.

Requires serial ASCII outputs. Phase masses use the official fixed box volume
100e-6 * 150e-6 * 200e-6 and its uniform mesh. Not a generic AMR mass integrator.
"""
import argparse
import json
import math
import re
from pathlib import Path
from analyse_case import field_values, NUMBER


def compare(a, b, allow_fv_solution=False):
    errors, fields, masses, histories = [], {}, {}, []
    for case in (a, b):
        log = (case / 'log.compressibleLaserbeamFoam').read_text()
        if not re.search(r'^End\s*$', log, re.M) or 'FOAM FATAL' in log:
            errors.append(f'Incomplete/fatal run: {case}')
        control = (case / 'system/controlDict').read_text()
        end = float(re.search(rf'\bendTime\s+({NUMBER})', control)[1])
        times = re.findall(rf'^Time = ({NUMBER})\s*$', log, re.M)
        if not times or not math.isclose(float(times[-1]), end, rel_tol=1e-6):
            errors.append(f'End time not reached: {case}')
        histories.append(re.findall(rf'^deltaT = ({NUMBER})', log, re.M))
    # Verify equivalent inputs, including omission of the new controls.
    for directory in ('initial', 'constant', 'system'):
        names_a = {p.relative_to(a/directory) for p in (a/directory).rglob('*')
                   if p.is_file() and 'polyMesh' not in p.parts}
        names_b = {p.relative_to(b/directory) for p in (b/directory).rglob('*')
                   if p.is_file() and 'polyMesh' not in p.parts}
        if names_a != names_b:
            errors.append(f'Different input inventories: {directory}')
        for name in names_a & names_b:
            if allow_fv_solution and directory == 'system' and name.as_posix() == 'fvSolution':
                continue
            if (a/directory/name).read_bytes() != (b/directory/name).read_bytes():
                errors.append(f'Different input: {directory}/{name}')
    for case in (a, b):
        dictionaries = (case/'constant/thermophysicalProperties').read_text() + (case/'system/controlDict').read_text()
        if re.search(r'\b(rhoMinEOS|pSmallSat|partialMassRhoFloor|recoveryRhoFloor|implicitCouplingPressureFloor|acousticPressureFloor)\s+', dictionaries):
            errors.append(f'New controls present in default case: {case}')
    folders = []
    for case in (a, b):
        folders.append(max((p for p in case.iterdir() if p.is_dir() and re.fullmatch(NUMBER, p.name)),
                           key=lambda p: float(p.name)))
    if float(folders[0].name) != float(folders[1].name):
        errors.append('Different final times')
    for name in ('p', 'rho', 'T', 'U', 'alpha.air', 'alpha.metal1', 'alpha.metal1vapour',
                 'c.air', 'c.metal1', 'c.metal1vapour', 'mass_dot'):
        x, y = (field_values(p/name, magnitude=False) for p in folders)
        if len(x) == 1: x = x * len(y)
        if len(y) == 1: y = y * len(x)
        if len(x) != len(y):
            errors.append(f'Different field sizes: {name}')
            continue
        diff = max(abs(u-v) for u,v in zip(x,y))
        scale = max(max(abs(v) for v in x), max(abs(v) for v in y))
        if diff > 1e-12 + 1e-10*scale:
            errors.append(f'Field mismatch: {name}')
        fields[name] = {'upstream_min': min(x), 'upstream_max': max(x),
                        'patched_min': min(y), 'patched_max': max(y), 'max_abs_difference': diff}
        if name.startswith('c.'):
            masses[name[2:]] = {'upstream_kg': sum(x)/len(x)*3e-12,
                                'patched_kg': sum(y)/len(y)*3e-12}
    step_match = len(histories[0]) == len(histories[1]) and all(
        math.isclose(float(u),float(v),rel_tol=1e-10,abs_tol=1e-20)
        for u,v in zip(*histories))
    if not step_match: errors.append('Timestep histories differ')
    return {'status': 'FAIL' if errors else 'PASS', 'scope': 'official mesh, specified duration only',
            'endTime': float(folders[0].name), 'fields': fields, 'phase_masses': masses,
            'timestep_count': len(histories[0]), 'timestep_histories_equal': step_match,
            'errors': errors}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('upstream', type=Path)
    p.add_argument('patched', type=Path)
    p.add_argument('--json', type=Path)
    p.add_argument('--allow-fv-solution', action='store_true',
                   help='Permit a controlled solver-only difference in system/fvSolution')
    args = p.parse_args()
    try:
        report = compare(args.upstream, args.patched, args.allow_fv_solution)
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        report = {'status': 'FAIL', 'errors': [str(exc)]}
    output = json.dumps(report, indent=2, allow_nan=False)
    print(output)
    if args.json: args.json.write_text(output + '\n')
    raise SystemExit(0 if report['status'] == 'PASS' else 1)


if __name__ == '__main__':
    main()
