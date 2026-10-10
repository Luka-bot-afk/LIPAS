
import argparse
import json
from data_ingestion import fetch_real_source_data, batch_ingest_from_sources, load_json_or_csv

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Batch ingest remote or local source datasets.')
    parser.add_argument('--sources', type=str, help='Path to JSON file containing source payloads')
    parser.add_argument('--source-dir', type=str, help='Directory containing local JSON/CSV source files to ingest')
    parser.add_argument('--fetch-remote', action='store_true', help='Fetch remote NOAA/NASA source data before ingesting')
    parser.add_argument('--start', type=str, help='Start date for remote fetch (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, help='End date for remote fetch (YYYY-MM-DD)')
    parser.add_argument('--nasa-key', type=str, default=None, help='NASA API key for DONKI fetch')
    parser.add_argument('--extra-url', action='append', default=[], help='Additional remote source URL in the form key=url')
    parser.add_argument('--out-dir', type=str, default='data/ingested', help='Directory to save ingested data')
    args = parser.parse_args()

    sources = {}
    if args.sources:
        sources = load_json_or_csv(args.sources)
        if isinstance(sources, dict):
            pass
        elif hasattr(sources, 'to_dict'):
            sources = sources.to_dict(orient='list')
        else:
            raise ValueError('sources file must contain a JSON object')

    if args.source_dir:
        from pathlib import Path
        source_path = Path(args.source_dir)
        if not source_path.is_dir():
            raise ValueError(f'--source-dir must be a directory: {args.source_dir}')
        for path in sorted(source_path.glob('*.json')) + sorted(source_path.glob('*.csv')):
            label = path.stem
            if label in sources:
                label = f'{label}_{len(sources)}'
            sources[label] = str(path)

    if args.fetch_remote:
        extra_urls = {}
        for item in args.extra_url:
            if '=' in item:
                key, url = item.split('=', 1)
                extra_urls[key] = url
        remote = fetch_real_source_data(start_date=args.start, end_date=args.end, nasa_key=args.nasa_key or 'DEMO_KEY', extra_urls=extra_urls)
        sources.update(remote)

    if not sources:
        raise SystemExit('No source payloads provided. Use --sources or --fetch-remote.')

    paths = batch_ingest_from_sources(sources, out_dir=args.out_dir)
    print('Wrote ingested chunks:')
    for p in paths:
        print('-', p)
