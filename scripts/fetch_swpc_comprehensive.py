
"""LIPAS."""
import os
import json
import time
import requests
from pathlib import Path

ROOT = Path(__file__).parent.parent
RAW_DIR = ROOT / 'data' / 'raw'
RAW_DIR.mkdir(parents=True, exist_ok=True)

ENDPOINTS = [
    'https://services.swpc.noaa.gov/json/f107_cm_flux.json',
    'https://services.swpc.noaa.gov/json/planetary_k_index_1m.json',
    'https://services.swpc.noaa.gov/json/goes/primary/integral-protons-1-day.json',
    'https://services.swpc.noaa.gov/json/goes/primary/differential-protons-1-day.json',
    'https://services.swpc.noaa.gov/json/goes/primary/integral-electrons-1-day.json',
    'https://services.swpc.noaa.gov/json/goes/primary/xrays-1-day.json',
    'https://services.swpc.noaa.gov/json/goes/secondary/xrays-1-day.json',
    'https://services.swpc.noaa.gov/json/goes/primary/magnetometers-1-day.json',
    'https://services.swpc.noaa.gov/json/solar-cycle/observed-solar-cycle-indices.json',
    'https://services.swpc.noaa.gov/json/solar-cycle/predicted-solar-cycle.json',
    'https://services.swpc.noaa.gov/json/planetary_k_index_1m.json',
    'https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json',
    'https://services.swpc.noaa.gov/products/kyoto-dst.json',
]

fetched = {}
for url in ENDPOINTS:
    try:
        print(f'Fetching {url}...')
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        data = r.json()
        fname = url.split('/')[-1].replace('.json', f'_{int(time.time())}.json')
        path = RAW_DIR / fname
        with open(path, 'w') as f:
            json.dump(data, f)
        print(f'  OK -> {path.name}')
        fetched[url] = {'ok': True, 'file': path.name, 'records': len(data) if isinstance(data, list) else 1}
    except Exception as e:
        print(f'  FAIL: {e}')
        fetched[url] = {'ok': False, 'error': str(e)}

report_path = ROOT / 'data' / 'fetch_swpc_report.json'
with open(report_path, 'w') as f:
    json.dump({'timestamp': time.time(), 'endpoints': fetched}, f, indent=2)
print(f'\nReport: {report_path}')
print(f'Successfully fetched {sum(1 for v in fetched.values() if v.get("ok"))} / {len(fetched)} endpoints')
