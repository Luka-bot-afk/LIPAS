from __future__ import annotations

import math
from typing import Any

import numpy as np

R_M_KM = 2439.7
B0_EQ_NT = 195.0
DIPOLE_OFFSET_Z_RM = 0.196

STANDOFF_COEFF = 2.15
BOW_SHOCK_RATIO = 1.35
SHUE_ALPHA = 0.50
MU0 = 4.0e-7 * math.pi

def magnetopause_standoff_rm(p_dyn_npa: float, imf_bz_nt: float | None = None) -> float:
    p = max(float(p_dyn_npa), 0.35)
    rss = STANDOFF_COEFF * (p ** (-1.0 / 6.0))
    if imf_bz_nt is not None:
        bz = float(imf_bz_nt)
        if bz < 0:
            rss *= 1.0 - 0.07 * min(1.0, (-bz) / 40.0)
        else:
            rss *= 1.0 + 0.03 * min(1.0, bz / 40.0)
    return float(max(0.82, min(2.8, rss)))

def bow_shock_standoff_rm(rss: float) -> float:
    return float(max(1.05, BOW_SHOCK_RATIO * float(rss)))

def shue_radius(rss: float, theta_rad: float, alpha: float = SHUE_ALPHA) -> float:

    c = math.cos(theta_rad)
    return float(rss * (2.0 / max(1e-6, 1.0 + c)) ** alpha)

def _mp_points(rss: float, n: int = 72) -> list[list[float]]:
    pts = []
    for i in range(n + 1):
        theta = math.pi * i / n
        r = shue_radius(rss, theta)

        x = r * math.cos(theta)
        z = r * math.sin(theta)
        pts.append([x, z])
    return pts

def _bs_points(rss: float, n: int = 64) -> list[list[float]]:
    rbs = bow_shock_standoff_rm(rss)
    pts = []
    for i in range(n + 1):
        theta = 0.92 * math.pi * i / n
        r = shue_radius(rbs, theta, alpha=0.65)
        x = r * math.cos(theta)
        z = r * math.sin(theta)
        pts.append([x, z])
    return pts

def dipole_field_nt(x_rm: float, z_rm: float) -> tuple[float, float, float]:

    x = float(x_rm)
    z = float(z_rm) - DIPOLE_OFFSET_Z_RM
    r2 = x * x + z * z
    r = math.sqrt(max(r2, 0.05))

    m_dot_r = z
    fac = B0_EQ_NT / (r ** 3)
    bx = fac * (3.0 * m_dot_r * x / r2)
    bz = fac * (3.0 * m_dot_r * z / r2 - 1.0)
    bmag = math.sqrt(bx * bx + bz * bz)
    return bx, bz, bmag

def cusp_latitude_deg(rss: float) -> float:
    rss = max(float(rss), 1.01)
    colat = math.degrees(math.asin(min(1.0, math.sqrt(1.0 / rss))))
    return float(90.0 - colat)

def field_line_polylines(rss: float, n_lines: int = 8) -> list[dict[str, Any]]:

    lines = []
    l_shells = list(np.linspace(1.08, max(rss * 0.98, 1.2), max(4, n_lines // 2)))
    l_shells += list(np.linspace(rss * 1.05, rss * 1.8, max(3, n_lines // 2)))
    for L in l_shells:
        closed = float(L) <= rss * 1.01
        pts = []
        theta0 = math.asin(min(1.0, math.sqrt(1.0 / max(float(L), 1.01))))
        n = 56
        for k in range(n):
            t = theta0 + (math.pi - 2.0 * theta0) * k / (n - 1)
            r = float(L) * (math.sin(t) ** 2)
            x = r * math.sin(t)
            z = r * math.cos(t)
            pts.append([x, z])
        lines.append({'closed': bool(closed), 'L': float(L), 'points': pts})
    return lines

def classify_point(x: float, z: float, rss: float) -> str:

    r = math.sqrt(x * x + z * z)
    if r <= 1.0:
        return 'planet'
    theta = math.acos(max(-1.0, min(1.0, x / max(r, 1e-6))))
    r_mp = shue_radius(rss, theta)
    r_bs = shue_radius(bow_shock_standoff_rm(rss), theta, alpha=0.65)
    if x > 0 and r > r_bs:
        return 'solar_wind'
    if r > r_bs:
        return 'solar_wind'
    if r > r_mp:
        return 'magnetosheath'

    if x < -0.3 and abs(z) < 0.35 + 0.08 * abs(x):
        return 'plasma_sheet'
    if x > 0 and r < 1.35:
        lat = abs(math.degrees(math.atan2(z, max(x, 1e-6))))
        cusp_lat = cusp_latitude_deg(rss)
        if abs(lat - cusp_lat) < 12.0:
            return 'cusp'
    if rss <= 1.08 and x > 0.15 and r < 1.25:
        return 'open_dayside'
    return 'magnetosphere'

def region_grid(rss: float, nx: int = 72, nz: int = 48) -> dict[str, Any]:
    x_min, x_max = -6.2, 3.2
    z_min, z_max = -3.1, 3.1
    xs = np.linspace(x_min, x_max, nx)
    zs = np.linspace(z_min, z_max, nz)
    grid = []
    for z in zs:
        row = []
        for x in xs:
            row.append(classify_point(float(x), float(z), rss))
        grid.append(row)
    return {
        'x_min': x_min, 'x_max': x_max,
        'z_min': z_min, 'z_max': z_max,
        'nx': nx, 'nz': nz,
        'cells': grid,
    }

def classify_equatorial(x: float, y: float, rss: float) -> str:

    r = math.sqrt(x * x + y * y)
    if r <= 1.0:
        return 'planet'
    theta = math.acos(max(-1.0, min(1.0, x / max(r, 1e-6))))
    r_mp = shue_radius(rss, theta)
    r_bs = shue_radius(bow_shock_standoff_rm(rss), theta, alpha=0.65)
    if r > r_bs:
        return 'solar_wind'
    if r > r_mp:
        return 'magnetosheath'
    if x < -0.25 and abs(y) < 0.55 + 0.12 * abs(x):
        return 'plasma_sheet'
    if rss <= 1.08 and x > 0.15 and r < 1.25:
        return 'open_dayside'
    return 'magnetosphere'

def equatorial_grid(rss: float, nx: int = 72, ny: int = 48) -> dict[str, Any]:
    x_min, x_max = -6.2, 3.2
    y_min, y_max = -3.1, 3.1
    xs = np.linspace(x_min, x_max, nx)
    ys = np.linspace(y_min, y_max, ny)
    grid = []
    for y in ys:
        row = []
        for x in xs:
            row.append(classify_equatorial(float(x), float(y), rss))
        grid.append(row)
    return {
        'x_min': x_min, 'x_max': x_max,
        'y_min': y_min, 'y_max': y_max,
        'nx': nx, 'ny': ny,
        'cells': grid,
    }

def bmag_grid(rss: float, imf_b_nt: float = 20.0, nx: int = 72, nz: int = 48) -> dict[str, Any]:

    x_min, x_max = -6.2, 3.2
    z_min, z_max = -3.1, 3.1
    xs = np.linspace(x_min, x_max, nx)
    zs = np.linspace(z_min, z_max, nz)
    imf = max(float(imf_b_nt), 1.0)
    values = []
    for z in zs:
        row = []
        for x in xs:
            region = classify_point(float(x), float(z), rss)
            if region == 'planet':
                row.append(0.0)
            elif region in ('magnetosphere', 'plasma_sheet', 'cusp', 'open_dayside'):
                _, _, bmag = dipole_field_nt(float(x), float(z))
                row.append(float(min(bmag, 800.0)))
            elif region == 'magnetosheath':
                row.append(float(imf * 3.2))
            else:
                row.append(float(imf))
        values.append(row)
    return {
        'x_min': x_min, 'x_max': x_max,
        'z_min': z_min, 'z_max': z_max,
        'nx': nx, 'nz': nz,
        'unit': 'nT',
        'values': values,
        'vmin': 5.0,
        'vmax': 200.0,
        'palette': 'plasma',
    }

def imf_clock(by_nt: float, bz_nt: float) -> dict[str, float | str]:
    ang = math.degrees(math.atan2(float(by_nt), float(bz_nt)))
    if bz_nt < -1.0 and abs(by_nt) < abs(bz_nt):
        clock = 'southward'
    elif bz_nt > 1.0 and abs(by_nt) < abs(bz_nt):
        clock = 'northward'
    elif by_nt >= 0:
        clock = 'duskward'
    else:
        clock = 'dawnward'
    return {
        'by_nt': float(by_nt),
        'bz_nt': float(bz_nt),
        'angle_deg': float(ang),
        'orientation': clock,
    }

def magnetic_pressure_npa(b_nt: float) -> float:
    b_t = float(b_nt) * 1e-9
    p = (b_t * b_t) / (2.0 * MU0)
    return float(p * 1e9)

def magnetosphere_state(p_dyn_npa: float, by_nt: float, bz_nt: float, b_mag_nt: float) -> dict[str, Any]:
    rss = magnetopause_standoff_rm(p_dyn_npa, imf_bz_nt=bz_nt)
    rbs = bow_shock_standoff_rm(rss)
    compressed = rss <= 1.12
    surface_open = rss <= 1.02
    clock = imf_clock(by_nt, bz_nt)
    p_mag_mp = magnetic_pressure_npa(B0_EQ_NT / max(rss ** 3, 0.5) * 2.2)
    return {
        'standoff_rm': round(rss, 3),
        'bow_shock_rm': round(rbs, 3),
        'compressed': compressed,
        'dayside_open_to_solar_wind': surface_open,
        'cusp_latitude_deg': round(cusp_latitude_deg(rss), 1),
        'dipole_b0_nt': B0_EQ_NT,
        'dipole_offset_z_rm': DIPOLE_OFFSET_Z_RM,
        'p_dyn_npa': round(float(p_dyn_npa), 3),
        'p_mag_mp_npa': round(p_mag_mp, 3),
        'imf_clock': clock,
        'imf_b_mag_nt': round(float(b_mag_nt), 2),
        'magnetopause': {
            'north': _mp_points(rss),
            'south': [[x, -z] for x, z in _mp_points(rss)],
        },
        'bow_shock': {
            'north': _bs_points(rss),
            'south': [[x, -z] for x, z in _bs_points(rss)],
        },
        'field_lines': field_line_polylines(rss),
        'grid': region_grid(rss),
        'equatorial_grid': equatorial_grid(rss),
        'bmag_grid': bmag_grid(rss, b_mag_nt),
        'colors': {
            'solar_wind': '#c4a574',
            'magnetosheath': '#e07a3d',
            'magnetosphere': '#3d9aad',
            'plasma_sheet': '#7b5ea7',
            'cusp': '#d45d8c',
            'open_dayside': '#d94c4c',
            'planet': '#8a7a6b',
            'closed_line': '#7ec8d6',
            'open_line': '#d9b36a',
        },
        'legend': [
            ['solar_wind', 'Solar wind'],
            ['magnetosheath', 'Sheath'],
            ['plasma_sheet', 'Tail'],
            ['magnetosphere', 'Closed field'],
            ['cusp', 'Cusps'],
            ['open_dayside', 'Open to the wind'],
        ],
    }
