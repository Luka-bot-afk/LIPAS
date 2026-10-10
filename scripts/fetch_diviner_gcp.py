
"""LIPAS."""
from __future__ import annotations

import time
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'archives' / 'diviner' / 'gcp'
BASE = 'https://pds-geosciences.wustl.edu/lro/urn-nasa-pds-lro_diviner_derived1/data_derived_gcp/'
LABEL = 'https://pds-geosciences.wustl.edu/lro/urn-nasa-pds-lro_diviner_derived1/label/dlre_gcp.fmt'

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    fmt = OUT / 'dlre_gcp.fmt'
    if not fmt.exists():
        r = requests.get(LABEL, timeout=60)
        r.raise_for_status()
        fmt.write_bytes(r.content)
        print('saved', fmt)

    r = requests.get(BASE, timeout=60)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, 'html.parser')
    links = sorted({urljoin(BASE, a['href']) for a in soup.find_all('a', href=True)})
    targets = [u for u in links if u.endswith(('.tab', '.lbl', '.xml', '.csv'))]
    print(f'{len(targets)} files listed')
    for u in targets:
        name = u.rstrip('/').split('/')[-1]
        dest = OUT / name
        if dest.exists() and dest.stat().st_size > 1000:
            print('skip', name)
            continue
        print('GET', name)
        rr = requests.get(u, timeout=300)
        rr.raise_for_status()
        dest.write_bytes(rr.content)
        print(' OK', len(rr.content))
        time.sleep(0.15)
    print('Done. Next: python scripts/extract_diviner_site_climatology.py')

if __name__ == '__main__':
    main()
