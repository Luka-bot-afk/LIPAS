from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

def main():
    ap = argparse.ArgumentParser(description='Fetch JPL Horizons Mercury ephemeris (daily r_AU).')
    ap.add_argument('--start', default='2025-01-01')
    ap.add_argument('--end', default='2026-12-31')
    args = ap.parse_args()
    from mercurius.data_ingestion import fetch_horizons_mercury, HORIZONS_JSON
    path = fetch_horizons_mercury(args.start, args.end)
    print(f'wrote {path} ({path.stat().st_size} bytes)')
    print(f'cache {HORIZONS_JSON}')

if __name__ == '__main__':
    main()
