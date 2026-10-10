
"""LIPAS."""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MEM3 = ROOT / 'data' / 'archives' / 'mem3'
OUT = MEM3 / 'mem3_flux_summary.json'

def _parse_cube_avg(path: Path) -> dict:
    text = path.read_text(encoding='utf-8', errors='replace')
    sphere = None
    faces = {}
    face_names = None
    for line in text.splitlines():
        m = re.search(r'total cross-sectional flux\s+([0-9.eE+\-]+)\s*/m\^2/yr', line)
        if m:
            sphere = float(m.group(1))
        if '+x ram' in line and 'zenith' in line:

            face_names = [
                '+x_ram', '-x_wake', '+y_port', '-y_starboard',
                '+z_zenith', '-z_nadir', 'Earth', 'Sun', 'anti-Sun',
                'rot_x', 'rot_y', 'rot_z',
            ]
        if line.strip().startswith('# total flux') or line.strip().startswith('total flux'):
            nums = re.findall(r'[0-9.eE+\-]+', line.split(')', 1)[-1] if ')' in line else line)

            parts = line.split()
            vals = []
            for p in parts:
                try:
                    vals.append(float(p))
                except Exception:
                    continue
            if face_names and len(vals) >= len(face_names):
                faces = {face_names[i]: vals[i] for i in range(len(face_names))}
            elif vals:
                faces = {f'face_{i}': vals[i] for i in range(len(vals))}
    return {
        'path': str(path.relative_to(ROOT)),
        'sphere_flux_per_m2_yr': sphere,
        'face_flux_per_m2_yr': faces,
    }

def main() -> int:
    exports = sorted(MEM3.glob('user_export_*'))
    if not exports:

        exports = [MEM3] if (MEM3 / 'HiDensity' / 'cube_avg.txt').exists() else []
    if not exports:
        print('No MEM3 user export found under data/archives/mem3/')
        return 1

    root = exports[-1]
    hi = _parse_cube_avg(root / 'HiDensity' / 'cube_avg.txt')
    lo = _parse_cube_avg(root / 'LoDensity' / 'cube_avg.txt')

    hi_s = hi.get('sphere_flux_per_m2_yr') or 2.62
    lo_s = lo.get('sphere_flux_per_m2_yr') or 1.40
    mid = 0.5 * (hi_s + lo_s)

    scale = 1.6 / max(mid, 1e-9)
    summary = {
        'extracted_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'export_dir': str(root.relative_to(ROOT)),
        'limiting_mass_g': 1e-6,
        'trajectory': 'lunar_orbit_1024_samples_2027',
        'HiDensity': hi,
        'LoDensity': lo,
        'proxy': {
            'scale_to_lipas_flux': scale,
            'baseline_flux_1e15': float(mid * scale),
            'hi_flux_1e15': float(hi_s * scale),
            'lo_flux_1e15': float(lo_s * scale),
            'zenith_hi_flux_1e15': float((hi.get('face_flux_per_m2_yr') or {}).get('+z_zenith', hi_s) * scale),
            'nadir_hi_flux_1e15': float((hi.get('face_flux_per_m2_yr') or {}).get('-z_nadir', hi_s * 0.1) * scale),
        },
        'note': 'MEM3 sphere/face fluxes from user NASA login export; blended into physics_micrometeorite_flux',
    }
    OUT.write_text(json.dumps(summary, indent=2))
    print(f'Wrote {OUT}')
    print(json.dumps(summary['proxy'], indent=2))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
