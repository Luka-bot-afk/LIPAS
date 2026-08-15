
"""LIPAS."""
import argparse
import json
import os
import time
from datetime import date

import requests
from dotenv import load_dotenv

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
OUT_DIR = os.path.join(ROOT, 'data', 'archives', 'donki_history')

DONKI_URLS = {
    'FLR': 'https://api.nasa.gov/DONKI/FLR',
    'CME': 'https://api.nasa.gov/DONKI/CME',
    'SEP': 'https://api.nasa.gov/DONKI/SEP',
    'GST': 'https://api.nasa.gov/DONKI/GST',
}

def fetch_year(event_type: str, url: str, year: int, api_key: str, max_retries: int = 4):
    start = f'{year}-01-01'
    end = f'{year}-12-31'
    for attempt in range(max_retries):
        try:
            r = requests.get(url, params={'startDate': start, 'endDate': end, 'api_key': api_key}, timeout=30)
        except requests.RequestException as e:
            print(f"  {event_type} {year}: request error ({e}), retrying...")
            time.sleep(2 * (attempt + 1))
            continue
        if r.status_code == 200:
            try:
                return r.json() or []
            except ValueError:
                print(f"  {event_type} {year}: bad JSON body, retrying...")
                time.sleep(2 * (attempt + 1))
                continue
        if r.status_code == 429:
            print(f"  {event_type} {year}: rate limited (429), backing off...")
            time.sleep(10)
            continue

        print(f"  {event_type} {year}: HTTP {r.status_code}, retrying (attempt {attempt + 1}/{max_retries})...")
        time.sleep(2 * (attempt + 1))
    print(f"  {event_type} {year}: FAILED after {max_retries} attempts -- skipping this year")
    return None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--start-year', type=int, default=2010)
    parser.add_argument('--end-year', type=int, default=date.today().year)
    args = parser.parse_args()

    load_dotenv()
    api_key = os.environ.get('NASA_KEY') or os.environ.get('NASA_API_KEY') or 'DEMO_KEY'
    if api_key == 'DEMO_KEY':
        print("WARNING: no NASA_KEY/NASA_API_KEY found in environment -- using DEMO_KEY "
              "(30 req/hour limit, this script will almost certainly get rate-limited).")

    os.makedirs(OUT_DIR, exist_ok=True)

    summary = {}
    for event_type, url in DONKI_URLS.items():
        summary[event_type] = {'years_fetched': [], 'years_failed': [], 'total_events': 0}
        for year in range(args.start_year, args.end_year + 1):
            data = fetch_year(event_type, url, year, api_key)
            if data is None:
                summary[event_type]['years_failed'].append(year)
                continue
            out_path = os.path.join(OUT_DIR, f'{event_type.lower()}_{year}.json')
            with open(out_path, 'w') as f:
                json.dump(data, f)
            n = len(data)
            summary[event_type]['years_fetched'].append(year)
            summary[event_type]['total_events'] += n
            print(f"  {event_type} {year}: {n} events -> {out_path}")
            time.sleep(0.2)

    print()
    print("=== Summary ===")
    for event_type, s in summary.items():
        print(f"{event_type}: {s['total_events']} total events across {len(s['years_fetched'])} years "
              f"({len(s['years_failed'])} years failed: {s['years_failed']})")

    with open(os.path.join(OUT_DIR, '_fetch_summary.json'), 'w') as f:
        json.dump(summary, f, indent=2)

if __name__ == '__main__':
    main()
