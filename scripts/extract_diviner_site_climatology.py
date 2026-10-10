
"""LIPAS."""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lunar_sites import LUNAR_SITES

GCP = ROOT / 'data' / 'archives' / 'diviner' / 'gcp'
OUT = ROOT / 'data' / 'archives' / 'diviner' / 'site_climatology.json'

def band_for_lat(lat: float) -> str:
    if lat >= 0:
        lo = int(lat // 10) * 10
        hi = lo + 10
        return f'{lo:02d}n{hi:02d}n'
    a = abs(lat)
    hi = int(a // 10) * 10
    lo = hi + 10
    if hi == 0:
        return '10s00s'
    return f'{lo:02d}s{hi:02d}s'

def norm_lon(lon: float) -> float:
    lon = float(lon)
    while lon > 180:
        lon -= 360
    while lon < -180:
        lon += 360
    return lon

def parse_csv_line(line: str):
    parts = [p.strip() for p in line.strip().split(',')]
    if len(parts) < 11:
        return None
    try:
        vals = [float(x) for x in parts[:11]]
    except Exception:
        return None
    return vals[0], vals[1], vals[2], vals[10]

def main():
    by_band = defaultdict(list)
    for s in LUNAR_SITES:
        by_band[band_for_lat(s.lat)].append(s)

    profiles = {}
    for band, sites in by_band.items():
        tab = GCP / f'global_cumul_avg_cyl_{band}_002.tab'
        if not tab.exists():
            print(f'MISSING band {band} for {[s.name[:30] for s in sites]}')
            continue

        targets = []
        for s in sites:
            targets.append({
                'name': s.name,
                'lat': float(s.lat),
                'lon': norm_lon(s.lon),
                'best': {},
            })
        print(f'Scanning {tab.name} for {len(targets)} site(s)...')
        with tab.open('r', errors='replace', newline='') as fh:
            _ = fh.readline()
            for line in fh:
                parsed = parse_csv_line(line)
                if parsed is None:
                    continue
                clon, clat, ltim, tbol = parsed
                if tbol <= -9000 or tbol != tbol:
                    continue
                for t in targets:
                    dlat = abs(clat - t['lat'])
                    dlon = abs(clon - t['lon'])
                    if dlon > 180:
                        dlon = 360 - dlon
                    if dlat > 0.6 or dlon > 0.6:
                        continue
                    dist2 = dlat * dlat + dlon * dlon
                    key = round(ltim * 4) / 4.0
                    prev = t['best'].get(key)
                    if prev is None or dist2 < prev[0]:
                        t['best'][key] = (dist2, tbol)

        for t in targets:
            best = t['best']
            if not best:
                print('NO_BINS', t['name'][:40], band)
                continue
            hours = np.arange(0, 24, 1.0)
            xs = np.array(sorted(best.keys()), dtype=np.float64)
            ys = np.array([best[x][1] for x in xs], dtype=np.float64)
            xs_w = np.concatenate([xs - 24.0, xs, xs + 24.0])
            ys_w = np.concatenate([ys, ys, ys])
            tk = np.interp(hours, xs_w, ys_w)
            tc = tk - 273.15
            profiles[t['name']] = {
                'band': band,
                'lat': t['lat'],
                'lon': t['lon'],
                'n_ltim_bins': len(best),
                'temp_C_hourly': [round(float(x), 3) for x in tc],
                'source': 'Diviner GCP global_cumul_avg v002 (2009-07 to 2015-04), nearest 0.5deg cell, tbol',
            }
            print(
                f"OK {t['name'][:40]:40s} bins={len(best):3d} "
                f"T=[{float(tc.min()):.1f},{float(tc.max()):.1f}] C"
            )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        'product': 'LRO-L-DLRE-5-GCP-V1.0 global_cumul_avg_cyl_*_002',
        'sites': profiles,
    }, indent=2))
    print(f'Wrote {OUT} ({len(profiles)}/{len(LUNAR_SITES)} sites)')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
