# LIPAS

Moon hazard forecasts for mission planning. Also includes a Mercury magnetosphere view that uses the same public space-weather feeds.

## Setup

```bash
python3.13 -m venv .venv313
source .venv313/bin/activate
pip install -r requirements.txt
cp .env.example .env
python3.13 server.py
```

Then open `landing.html` (Moon), `doctype.html` (dashboard), or `index.html` / `mercury_globe.html` (Mercury).

```bash
python mercurius/scripts/fetch_horizons.py --start 2025-01-01 --end 2026-12-31
python mercurius/scripts/compare_moon_window.py
python -m unittest tests/test_mercury_physics.py
```

Trained lunar weights are kept offline. Mercury runs on its own physics path.

© 2026 Luka Takki
