
"""LIPAS."""
from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lunar_sites import LUNAR_SITES

PRP = ROOT / 'data' / 'archives' / 'diviner' / 'prp'
OUT = ROOT / 'data' / 'archives' / 'diviner' / 'prp_polar_site_temps.json'

def _dist2(a_lat, a_lon, b_lat, b_lon):
    dlat = float(a_lat) - float(b_lat)
    dlon = float(a_lon) - float(b_lon)
    if dlon > 180:
        dlon -= 360
    if dlon < -180:
        dlon += 360

    scale = max(0.05, math.cos(math.radians(float(a_lat))))
    return dlat * dlat + (dlon * scale) ** 2

def scan_tab(path: Path, targets: list[dict], max_dist_deg: float = 2.5) -> None:
    if not path.exists() or path.stat().st_size < 1000:
        print(f'SKIP missing/empty {path}')
        return
    print(f'Scanning {path.name} ({path.stat().st_size} bytes) for {len(targets)} site(s)...')
    with path.open('r', errors='replace', newline='') as fh:
        reader = csv.reader(fh)
        header = next(reader, None)
        if not header:
            return

        try:
            i_lon = header.index('tri_clon')
            i_lat = header.index('tri_clat')
            i_tavg = header.index('temp_avg')
            i_tmax = header.index('temp_max')
        except ValueError:

            i_lon, i_lat, i_tavg, i_tmax = 9, 10, 12, 13
        for row in reader:
            if len(row) <= max(i_lon, i_lat, i_tavg, i_tmax):
                continue
            try:
                clon = float(row[i_lon])
                clat = float(row[i_lat])
                tavg = float(row[i_tavg])
                tmax = float(row[i_tmax])
            except Exception:
                continue
            if not math.isfinite(tavg) or tavg < 20 or tavg > 420:
                continue
            for t in targets:
                d2 = _dist2(t['lat'], t['lon'], clat, clon)
                if d2 < t['best_d2'] and math.sqrt(d2) <= max_dist_deg:
                    t['best_d2'] = d2
                    t['temp_avg_K'] = tavg
                    t['temp_max_K'] = tmax
                    t['sample_lat'] = clat
                    t['sample_lon'] = clon

def main() -> int:
    polar = [
        {
            'name': s.name,
            'lat': float(s.lat),
            'lon': float(s.lon),
            'best_d2': 1e18,
            'temp_avg_K': None,
            'temp_max_K': None,
            'sample_lat': None,
            'sample_lon': None,
        }
        for s in LUNAR_SITES
        if abs(float(s.lat)) >= 70.0
    ]
    if not polar:
        print('No polar sites')
        return 1
    north = [t for t in polar if t['lat'] >= 0]
    south = [t for t in polar if t['lat'] < 0]
    if north:
        scan_tab(PRP / 'dlre_prp_north.tab', north)
    if south:
        scan_tab(PRP / 'dlre_prp_south.tab', south)

    sites = {}
    for t in polar:
        if t['temp_avg_K'] is None:
            print(f'  NO HIT {t["name"][:40]}')
            continue
        sites[t['name']] = {
            'lat': t['lat'],
            'lon': t['lon'],
            'temp_avg_C': round(t['temp_avg_K'] - 273.15, 2),
            'temp_max_C': round(t['temp_max_K'] - 273.15, 2) if t['temp_max_K'] else None,
            'sample_lat': t['sample_lat'],
            'sample_lon': t['sample_lon'],
            'dist_deg': round(math.sqrt(t['best_d2']), 4),
            'source': 'diviner_prp',
        }
        print(f'  OK {t["name"][:40]} avgC={sites[t["name"]]["temp_avg_C"]} dist={sites[t["name"]]["dist_deg"]}')

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        'product': 'Diviner PRP polar site samples',
        'n_sites': len(sites),
        'sites': sites,
    }, indent=2))
    print(f'Wrote {OUT} ({len(sites)} sites)')
    return 0 if sites else 2

if __name__ == '__main__':
    raise SystemExit(main())
