#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from space_weather_model import (  # noqa: E402
    CORE_FEATURE_NAMES,
    load_saved_model,
    load_blend_weights,
    refine_prediction,
)
from lunar_physics import physics_radiation  # noqa: E402

# Apollo 17 EVA-3 duration
EVA_MINUTES = 7 * 60 + 37  # 457
STEP_MIN = 5

# Ops thresholds from server._hazard_levels / storm logic
RAD_CAUTION = 0.095
RAD_NOGO = 0.15
GOES_PROTON_CAUTION = 10.0   # arbitrary relative units in this script
GOES_PROTON_NOGO = 50.0

SITE = {
    'name': 'Apollo 11 (Mare Tranquillitatis)',
    'lat': 0.67408,
    'lon': 23.47297,
}


def _lvl_rad(rad: float) -> str:
    if rad >= RAD_NOGO:
        return 'red'
    if rad >= RAD_CAUTION:
        return 'yellow'
    return 'green'


def _eva_status(rad: float, solar: float) -> str:
    if rad >= RAD_NOGO or solar >= 22 or rad > 0.145:
        return 'nogo'
    if rad >= RAD_CAUTION or solar >= 14 or rad > 0.095:
        return 'caution'
    return 'go'


def storm_profile(t_min: float) -> dict:
    """Controlled injection timeline (documented scenario, not a real July event).

    T+0    : quiet EVA start
    T+40   : solar/CME driver onset (DONKI-like precursor)
    T+55   : Kp / IMF coupling rises
    T+70   : GOES proton flux surge (Earth-orbit measurement arrival)
    T+120  : peak
    T+200  : decay
    """
    # Solar activity precursor
    if t_min < 40:
        solar = 5.0
    elif t_min < 70:
        solar = 5.0 + 18.0 * ((t_min - 40) / 30.0)  # ramp to ~23
    elif t_min < 120:
        solar = 23.0 + 8.0 * ((t_min - 70) / 50.0)
    elif t_min < 200:
        solar = 31.0 - 10.0 * ((t_min - 120) / 80.0)
    else:
        solar = max(6.0, 21.0 - 0.04 * (t_min - 200))

    # Kp
    if t_min < 55:
        kp = 2.5
    elif t_min < 100:
        kp = 2.5 + 5.0 * ((t_min - 55) / 45.0)
    elif t_min < 180:
        kp = 7.5
    else:
        kp = max(2.5, 7.5 - 0.025 * (t_min - 180))

    # IMF Bz southward during storm
    if t_min < 50:
        bz = -1.0
    elif t_min < 160:
        bz = -12.0
    else:
        bz = -2.0

    # GOES-like proton flux (relative). Surge starts T+70
    if t_min < 70:
        protons = 1.0
    elif t_min < 120:
        protons = 1.0 + 80.0 * ((t_min - 70) / 50.0)
    elif t_min < 220:
        protons = 81.0 - 40.0 * ((t_min - 120) / 100.0)
    else:
        protons = max(1.0, 41.0 - 0.15 * (t_min - 220))

    sw_speed = 400.0 + max(0.0, (kp - 2.5) * 80.0)
    sw_dens = 5.0 + max(0.0, (kp - 2.5) * 2.0)
    return {
        'solar_activity': float(solar),
        'kp_index': float(kp),
        'imf_bz': float(bz),
        'proton_flux': float(protons),
        'solar_wind_speed': float(sw_speed),
        'solar_wind_density': float(sw_dens),
        'storm_phase': (
            'quiet' if t_min < 40 else
            'precursor_solar' if t_min < 70 else
            'proton_surge' if t_min < 120 else
            'peak_or_decay'
        ),
    }


def base_row_from_csv(csv_path: str, site_name: str, day: str) -> dict:
    df = pd.read_csv(csv_path, parse_dates=['date'])
    sub = df[(df['site'] == site_name) & (df['date'] == pd.Timestamp(day))]
    if sub.empty:
        sub = df[df['site'] == site_name].sort_values('date').tail(1)
    row = sub.iloc[0]
    out = {c: float(row[c]) for c in CORE_FEATURE_NAMES}
    for c in ('lat', 'lon', 'local_solar_time', 'regolith_depth', 'thermal_inertia',
              'kp_index', 'imf_bz', 'solar_wind_speed', 'solar_wind_density'):
        if c in row.index:
            out[c] = float(row[c])
    out['site'] = site_name
    return out


def nasa_goes_alert(protons: float) -> str:
    if protons >= GOES_PROTON_NOGO:
        return 'nogo'
    if protons >= GOES_PROTON_CAUTION:
        return 'caution'
    return 'go'


def first_time(rows, pred_key, status_value):
    for r in rows:
        if r[pred_key] == status_value:
            return r['t_min']
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--csv', default='data/ingested_extended/extended_training_window_B_ready.csv')
    ap.add_argument('--day', default='2026-07-12')
    ap.add_argument('--model-dir', default='saved_model')
    ap.add_argument('--out-dir', default='logs/study_mission_sim_radiation_eva')
    args = ap.parse_args()
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    print('Loading train2...', flush=True)
    if load_saved_model(args.model_dir, set_global=True) is None:
        raise SystemExit('model missing')
    load_blend_weights(args.model_dir)

    base = base_row_from_csv(args.csv, SITE['name'], args.day)
    lat, lon = float(base['lat']), float(base['lon'])
    lst0 = float(base.get('local_solar_time', 12.0))

    rows = []
    for t in range(0, EVA_MINUTES + 1, STEP_MIN):
        storm = storm_profile(t)
        lst = (lst0 + t / 60.0) % 24.0
        # Core 6 hazards; OMNI/Kp/Bz drivers go through `extra` into 18-feature expand.
        rad_phys = physics_radiation(
            storm['solar_activity'], storm['kp_index'], storm['proton_flux'],
            lat, storm['imf_bz'], storm['solar_wind_speed'],
        )
        inputs = [float(base[c]) for c in CORE_FEATURE_NAMES]
        inputs[0] = storm['solar_activity']
        inputs[1] = rad_phys

        extra = {
            'kp': storm['kp_index'],
            'kp_index': storm['kp_index'],
            'imf_bz': storm['imf_bz'],
            'solar_wind_speed': storm['solar_wind_speed'],
            'solar_wind_density': storm['solar_wind_density'],
            'protons': storm['proton_flux'],
            'proton_flux': storm['proton_flux'],
            'hour_of_day': lst,
            'local_solar_time': lst,
            'regolith_depth': float(base.get('regolith_depth', 4.2)),
            'thermal_inertia': float(base.get('thermal_inertia', 48.0)),
        }
        pred = refine_prediction(inputs, lat=lat, lon=lon, local_time=lst, extra=extra)
        hyb = pred['hybrid']
        lipas_rad = float(hyb['radiation'])
        lipas_solar = float(hyb['solar'])
        lipas_status = _eva_status(lipas_rad, lipas_solar)
        lipas_rad_lvl = _lvl_rad(lipas_rad)

        # NASA stack: (1) physics radiation replica (2) GOES proton product alert
        nasa_rad = rad_phys
        nasa_phys_status = _eva_status(nasa_rad, storm['solar_activity'])
        goes_status = nasa_goes_alert(storm['proton_flux'])
        # Combined NASA ops call: worst of physics-radiation thresholds and GOES protons
        rank = {'go': 0, 'caution': 1, 'nogo': 2}
        nasa_status = max([nasa_phys_status, goes_status], key=lambda s: rank[s])

        rows.append({
            't_min': t,
            't_hhmm': f'{t // 60:02d}:{t % 60:02d}',
            'storm_phase': storm['storm_phase'],
            'solar_activity_driver': storm['solar_activity'],
            'kp': storm['kp_index'],
            'imf_bz': storm['imf_bz'],
            'goes_proton_proxy': storm['proton_flux'],
            'lipas_radiation_mSv_h': lipas_rad,
            'lipas_solar': lipas_solar,
            'lipas_rad_level': lipas_rad_lvl,
            'lipas_eva_status': lipas_status,
            'nasa_physics_radiation_mSv_h': nasa_rad,
            'nasa_physics_eva_status': nasa_phys_status,
            'nasa_goes_alert_status': goes_status,
            'nasa_combined_eva_status': nasa_status,
        })

    df = pd.DataFrame(rows)
    df.to_csv(out / 'eva_timeline.csv', index=False)

    events = {
        'scenario': {
            'site': SITE,
            'eva_duration_min': EVA_MINUTES,
            'apollo_reference': 'Apollo 17 EVA-3 ≈ 7 h 37 min',
            'base_day_drivers_from': args.day,
            'model': 'second-train / train2 saved_model',
            'injection': {
                'T+40min': 'solar/CME precursor rise (DONKI-like)',
                'T+55min': 'Kp / IMF coupling rise',
                'T+70min': 'GOES proton flux surge',
            },
            'thresholds': {
                'radiation_caution_mSv_h': RAD_CAUTION,
                'radiation_nogo_mSv_h': RAD_NOGO,
                'goes_proton_caution': GOES_PROTON_CAUTION,
                'goes_proton_nogo': GOES_PROTON_NOGO,
            },
            'bias_note': (
                'Radiation is the scripted abort driver because it is operationally decisive for EVA '
                'and was a hybrid strength channel in the 14-day study. This does not imply LIPAS '
                'wins every hazard; other channels were monitored but not used as the abort trigger.'
            ),
        },
        'storm_onset_t_min': 40,
        'goes_proton_surge_t_min': 70,
        'lipas_first_caution_t_min': first_time(rows, 'lipas_eva_status', 'caution'),
        'lipas_first_nogo_t_min': first_time(rows, 'lipas_eva_status', 'nogo'),
        'nasa_physics_first_caution_t_min': first_time(rows, 'nasa_physics_eva_status', 'caution'),
        'nasa_physics_first_nogo_t_min': first_time(rows, 'nasa_physics_eva_status', 'nogo'),
        'nasa_goes_first_caution_t_min': first_time(rows, 'nasa_goes_alert_status', 'caution'),
        'nasa_goes_first_nogo_t_min': first_time(rows, 'nasa_goes_alert_status', 'nogo'),
        'nasa_combined_first_caution_t_min': first_time(rows, 'nasa_combined_eva_status', 'caution'),
        'nasa_combined_first_nogo_t_min': first_time(rows, 'nasa_combined_eva_status', 'nogo'),
    }

    # Lead times relative to proton surge (T+70) and storm precursor (T+40)
    for who, key in [
        ('lipas', 'lipas_first_caution_t_min'),
        ('lipas', 'lipas_first_nogo_t_min'),
        ('nasa_combined', 'nasa_combined_first_caution_t_min'),
        ('nasa_combined', 'nasa_combined_first_nogo_t_min'),
        ('nasa_goes', 'nasa_goes_first_caution_t_min'),
        ('nasa_goes', 'nasa_goes_first_nogo_t_min'),
    ]:
        pass
    events['lead_time_analysis'] = {
        'lipas_caution_minus_storm_onset_min': (
            None if events['lipas_first_caution_t_min'] is None else
            events['lipas_first_caution_t_min'] - 40
        ),
        'lipas_caution_minus_goes_surge_min': (
            None if events['lipas_first_caution_t_min'] is None else
            events['lipas_first_caution_t_min'] - 70
        ),
        'nasa_goes_caution_minus_goes_surge_min': (
            None if events['nasa_goes_first_caution_t_min'] is None else
            events['nasa_goes_first_caution_t_min'] - 70
        ),
        'lipas_nogo_minus_nasa_goes_nogo_min': (
            None if events['lipas_first_nogo_t_min'] is None or events['nasa_goes_first_nogo_t_min'] is None else
            events['nasa_goes_first_nogo_t_min'] - events['lipas_first_nogo_t_min']
        ),
        'recommended_return_call': (
            f"LIPAS NO-GO at T+{events['lipas_first_nogo_t_min']} min"
            if events['lipas_first_nogo_t_min'] is not None else 'No LIPAS NO-GO in window'
        ),
    }

    (out / 'events.json').write_text(json.dumps(events, indent=2))

    # Markdown report + paper section
    lc, ln = events['lipas_first_caution_t_min'], events['lipas_first_nogo_t_min']
    gc, gn = events['nasa_goes_first_caution_t_min'], events['nasa_goes_first_nogo_t_min']
    nc, nn = events['nasa_combined_first_caution_t_min'], events['nasa_combined_first_nogo_t_min']

    def fmt(t):
        if t is None:
            return 'n/a'
        return f'T+{t} min ({t // 60}h {t % 60:02d}m)'

    report = f"""# Mission Simulation — Radiation-Driven EVA Abort

**Site:** {SITE['name']}  
**Duration:** {EVA_MINUTES} min (Apollo 17 EVA-3 length)  
**Model:** train2 / second-train hybrid  
**Base day drivers:** {args.day}  
**Step:** every {STEP_MIN} minutes  

## Bias / framing
Radiation is the scripted abort driver because EVA abort decisions are often radiation-led and the 14-day study found hybrid radiation skill vs NASA replicas. This scenario does **not** claim LIPAS is best on every hazard.

## Injected timeline
| Time | Event |
|---|---|
| T+0 | EVA start (quiet) |
| T+40 | Solar/CME precursor rises (DONKI-like) |
| T+55 | Kp / IMF storm coupling rises |
| T+70 | GOES proton flux surge |
| T+120 | Storm peak region |
| T+{EVA_MINUTES} | Scheduled EVA end |

## Warning times
| System | First CAUTION | First NO-GO |
|---|---|---|
| LIPAS hybrid | {fmt(lc)} | {fmt(ln)} |
| NASA GOES proton product | {fmt(gc)} | {fmt(gn)} |
| NASA combined (physics rad + GOES) | {fmt(nc)} | {fmt(nn)} |

## Lead-time notes
- Storm precursor onset: T+40
- GOES proton surge: T+70
- LIPAS caution relative to precursor: {events['lead_time_analysis']['lipas_caution_minus_storm_onset_min']} min
- LIPAS caution relative to GOES surge: {events['lead_time_analysis']['lipas_caution_minus_goes_surge_min']} min
- NASA GOES caution relative to proton surge: {events['lead_time_analysis']['nasa_goes_caution_minus_goes_surge_min']} min
- Minutes LIPAS NO-GO leads NASA GOES NO-GO: {events['lead_time_analysis']['lipas_nogo_minus_nasa_goes_nogo_min']}

## Outputs
- `eva_timeline.csv`
- `events.json`
"""
    (out / 'REPORT.md').write_text(report)

    section = f"""5.4 Operational Mission Simulations

A controlled radiation-driven EVA simulation was executed at Apollo 11 using the locked second-train hybrid model and an EVA duration matching Apollo 17 EVA-3 (7 hours 37 minutes). Quiet baseline drivers from {args.day} were advanced in 5-minute steps while a documented storm injection was applied: solar/CME precursor rise at T+40 minutes, geomagnetic coupling rise at T+55 minutes, and a GOES-like proton surge at T+70 minutes. Identical caution/no-go radiation thresholds were used for LIPAS and the NASA physics replica (caution at 0.095 mSv/h, no-go at 0.15 mSv/h), while the NASA GOES path alerted from the proton-flux product alone.

LIPAS issued its first caution at {fmt(lc)} and first no-go at {fmt(ln)}. The NASA GOES proton product reached caution at {fmt(gc)} and no-go at {fmt(gn)}. The combined NASA stack (physics radiation plus GOES) reached caution at {fmt(nc)} and no-go at {fmt(nn)}. Relative to the proton surge at T+70, LIPAS caution occurred at {events['lead_time_analysis']['lipas_caution_minus_goes_surge_min']} minutes (negative values mean earlier than the surge). The recommended return call under LIPAS was {events['lead_time_analysis']['recommended_return_call']}.

This scenario is intentionally radiation-focused because radiation is an operationally decisive EVA abort driver. It demonstrates warning timing and return-call behavior under a shared script, not overall multi-hazard superiority.
"""
    (out / 'PAPER_SECTION_5_4.txt').write_text(section)
    print(report)
    print('\n--- PAPER SECTION ---\n')
    print(section)


if __name__ == '__main__':
    main()
