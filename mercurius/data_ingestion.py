from __future__ import annotations

import json
import math
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
CACHE = ROOT / 'data'
HORIZONS_API = 'https://ssd.jpl.nasa.gov/api/horizons.api'
HORIZONS_JSON = CACHE / 'horizons_mercury_daily.json'

def _parse_horizons_result(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if '$$SOE' not in text or '$$EOE' not in text:
        return rows
    block = text.split('$$SOE', 1)[1].split('$$EOE', 1)[0]
    for raw in block.strip().splitlines():
        line = raw.strip()
        if not line or line.startswith('*'):
            continue

        parts = [p.strip() for p in line.split(',')]
        if len(parts) < 5:
            parts = line.split()
        nums = []
        cal = None
        for p in parts:
            try:
                nums.append(float(p))
            except ValueError:
                if cal is None and any(ch.isalpha() for ch in p):
                    cal = p
        if len(nums) < 3:
            continue

        if len(nums) >= 4:
            x, y, z = nums[-3], nums[-2], nums[-1] if len(nums) == 4 else nums[1:4][0:3]

            if nums[0] > 1e6 and len(nums) >= 4:
                x, y, z = nums[1], nums[2], nums[3]
            else:
                x, y, z = nums[0], nums[1], nums[2]
        else:
            x, y, z = nums[0], nums[1], nums[2]
        r = math.sqrt(x * x + y * y + z * z)
        if not (0.25 < r < 0.55):
            continue
        rec = {'x_au': x, 'y_au': y, 'z_au': z, 'r_au': r}
        if cal:
            rec['calendar'] = cal
        if nums[0] > 1e6:
            rec['jd'] = nums[0]
        rows.append(rec)
    return rows

def fetch_horizons_mercury(start: str, end: str, step: str = '1d') -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    params = {
        'format': 'json',
        'COMMAND': "'199'",
        'OBJ_DATA': 'NO',
        'MAKE_EPHEM': 'YES',
        'EPHEM_TYPE': 'VECTORS',
        'CENTER': "'@sun'",
        'START_TIME': f"'{start}'",
        'STOP_TIME': f"'{end}'",
        'STEP_SIZE': f"'{step}'",
        'VEC_TABLE': '2',
        'OUT_UNITS': 'AU-D',
        'REF_PLANE': 'ECLIPTIC',
        'CSV_FORMAT': 'YES',
    }
    url = HORIZONS_API + '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={'User-Agent': 'LIPAS-Mercury/1.0'})
    with urllib.request.urlopen(req, timeout=90) as resp:
        payload = json.loads(resp.read().decode('utf-8'))
    result = payload.get('result') or ''
    rows = _parse_horizons_result(result)
    if not rows:
        raise RuntimeError('Horizons returned no usable Mercury vectors')

    start_dt = datetime.fromisoformat(start).replace(tzinfo=timezone.utc)
    step_days = 1.0
    if step.endswith('d'):
        try:
            step_days = float(step[:-1].strip() or '1')
        except ValueError:
            step_days = 1.0
    for i, rec in enumerate(rows):
        rec['date'] = (start_dt + timedelta(days=i * step_days)).date().isoformat()

    existing: dict[str, dict] = {}
    if HORIZONS_JSON.exists():
        try:
            prev = json.loads(HORIZONS_JSON.read_text(encoding='utf-8'))
            for rec in prev.get('rows') or []:
                if rec.get('date'):
                    existing[rec['date']] = rec
        except Exception:
            pass
    for rec in rows:
        existing[rec['date']] = rec
    merged = [existing[k] for k in sorted(existing)]
    out = {
        'source': 'JPL Horizons COMMAND=199 CENTER=@sun VECTORS AU-D',
        'fetched_utc': datetime.now(timezone.utc).isoformat(),
        'start': start,
        'end': end,
        'rows': merged,
    }
    HORIZONS_JSON.write_text(json.dumps(out), encoding='utf-8')
    return HORIZONS_JSON

def horizons_r_au(when: datetime | None = None) -> float | None:
    if not HORIZONS_JSON.exists():
        return None
    try:
        blob = json.loads(HORIZONS_JSON.read_text(encoding='utf-8'))
    except Exception:
        return None
    rows = blob.get('rows') or []
    if not rows:
        return None
    when = when or datetime.now(timezone.utc)
    day = when.date().isoformat()
    exact = next((r for r in rows if r.get('date') == day), None)
    if exact and exact.get('r_au'):
        return float(exact['r_au'])

    best = None
    best_d = 10**9
    for r in rows:
        d = r.get('date')
        if not d:
            continue
        try:
            delta = abs((datetime.fromisoformat(d).date() - when.date()).days)
        except Exception:
            continue
        if delta < best_d:
            best_d = delta
            best = r
    if best and best_d <= 3 and best.get('r_au'):
        return float(best['r_au'])
    return None

def reuse_lipas_omni2() -> Path:
    return REPO / 'data' / 'archives' / 'omni2_daily.csv'

def load_lipas_drivers(local_time: float | None = 12.0) -> dict[str, Any]:

    import sys
    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
    from data_ingestion import serve_extra_for_local_time, load_serve_space_drivers
    extra = serve_extra_for_local_time(local_time)
    drv = load_serve_space_drivers()
    extra['driver_sources'] = list(drv.get('sources') or extra.get('driver_sources') or [])
    extra['omni_date'] = drv.get('omni_date')
    for k in (
        'proton_flux_raw', 'ssn', 'dst', 'ap', 'f107',
        'xray_flux', 'flare_class', 'flare_index', 'solar_region_count',
        'series', 'region_probs', 'omni_27d', 'confidence',
        'imf_by', 'imf_bx', 'imf_bt', 'wind_source',
        'c_flare_probability', 'm_flare_probability', 'x_flare_probability',
        'proton_probability', 'data_age_hours', 'rtsw_age_hours',
        'xray_age_hours', 'proton_age_hours', 'regions_observed_date',
    ):
        if drv.get(k) is not None:
            extra[k] = drv[k]

    if extra.get('flare_index') is not None:
        fi = float(extra['flare_index'])
        extra['solar_activity'] = max(float(extra.get('solar_activity') or 5.0), 4.0 + fi * 0.9)
    elif extra.get('f107') is not None:
        f107 = float(extra['f107'])
        extra['solar_activity'] = max(
            float(extra.get('solar_activity') or 5.0),
            min(12.0, 3.0 + (f107 - 70.0) / 30.0),
        )
    return extra

def fetch_messenger_epps(start: str, end: str):

    _ = (start, end)
    return {
        'status': 'unavailable',
        'reason': 'MESSENGER EPPS not bundled',
    }
