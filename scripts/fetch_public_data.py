
"""LIPAS."""
import os
import json
import time
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
RAW_DIR = os.path.join(ROOT, 'data', 'raw')
REPORT_PATH = os.path.join(ROOT, 'data', 'fetch_report.json')

def ensure_dirs():
    os.makedirs(RAW_DIR, exist_ok=True)

def safe_write(name, content, mode='w'):
    path = os.path.join(RAW_DIR, name)
    with open(path, mode) as f:
        f.write(content)
    return path

def fetch_url(url, dest_name, binary=False):
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        if binary:
            mode = 'wb'
            content = r.content
        else:
            mode = 'w'
            content = r.text
        path = safe_write(dest_name, content, mode=mode)
        return {'ok': True, 'path': path, 'url': url}
    except Exception as e:
        return {'ok': False, 'error': str(e), 'url': url}

def page_links(url):
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
        links = [a.get('href') for a in soup.find_all('a') if a.get('href')]
        return [urljoin(url, link) for link in links if link not in ('#', '../')]
    except Exception:
        return []

def is_same_host(base, url):
    return urlparse(base).netloc == urlparse(url).netloc

def crawl_swpc_directory(base_url, max_depth=3):
    discovered = []
    visited = set()

    def crawl(url, depth):
        if depth > max_depth or url in visited:
            return
        visited.add(url)
        if url.lower().endswith('.json'):
            discovered.append(url)
            return
        for next_url in page_links(url):
            if not is_same_host(base_url, next_url):
                continue
            if next_url.endswith('.json'):
                discovered.append(next_url)
            elif next_url.endswith('/') or next_url.endswith('.htm') or next_url.endswith('.html'):
                crawl(next_url, depth + 1)
    crawl(base_url, 0)
    return sorted(set(discovered))

def filename_for_url(url):
    parsed = urlparse(url)
    name = parsed.path.lstrip('/').replace('/', '_')
    if parsed.query:
        name += '_' + parsed.query.replace('&', '_').replace('=', '_')
    return name

def fetch_swpc_jsons(report):
    report['noaa_swpc'] = {'sources': {}, 'discovered': []}
    roots = [
        'https://services.swpc.noaa.gov/json/',
        'https://services.swpc.noaa.gov/products/'
    ]
    for root in roots:
        endpoints = crawl_swpc_directory(root)
        report['noaa_swpc']['discovered'].append({root: endpoints})
        for endpoint in endpoints:
            dest = f'noaa_swpc_{filename_for_url(endpoint)}'
            out = fetch_url(endpoint, dest)
            report['noaa_swpc']['sources'][endpoint] = out

def fetch_nasa_donki(report):
    api_key = os.environ.get('NASA_KEY') or os.environ.get('NASA_API_KEY', 'DEMO_KEY')
    start = '2010-01-01'
    end = datetime.utcnow().strftime('%Y-%m-%d')
    urls = {
        'FLR': f'https://api.nasa.gov/DONKI/FLR?startDate={start}&endDate={end}&api_key={api_key}',
        'CME': f'https://api.nasa.gov/DONKI/CME?startDate={start}&endDate={end}&api_key={api_key}',
        'SEP': f'https://api.nasa.gov/DONKI/SEP?startDate={start}&endDate={end}&api_key={api_key}'
    }
    report['nasa_donki'] = {}
    for k, u in urls.items():
        out = fetch_url(u, f'nasa_donki_{k}_{int(time.time())}.json')
        report['nasa_donki'][k] = out

def fetch_lro_diviner(report):

    url = 'https://pds-geosciences.wustl.edu/missions/lro/diviner.htm'
    out = fetch_url(url, f'lro_diviner_index_{int(time.time())}.html')
    report['lro_diviner'] = out

def fetch_crater(report):

    urls = ['http://crater.sr.unh.edu/', 'https://crater.sr.unh.edu/']
    out = None
    for url in urls:
        out = fetch_url(url, f'crater_index_{int(time.time())}.html')
        if out['ok']:
            break
    report['crater'] = out or {'ok': False, 'error': 'No reachable CRaTER page', 'url': urls}

def fetch_ldex(report):

    url = 'https://pds-geosciences.wustl.edu/missions/ladee/ldex.htm'
    out = fetch_url(url, f'ldex_index_{int(time.time())}.html')
    report['ldex'] = out

def run_all():
    ensure_dirs()
    report = {
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'results': {}
    }
    fetch_nasa_donki(report['results'])
    fetch_swpc_jsons(report['results'])
    fetch_lro_diviner(report['results'])
    fetch_crater(report['results'])
    fetch_ldex(report['results'])

    with open(REPORT_PATH, 'w') as f:
        json.dump(report, f, indent=2)

    print('Fetch complete. Summary written to', REPORT_PATH)

if __name__ == '__main__':
    run_all()
