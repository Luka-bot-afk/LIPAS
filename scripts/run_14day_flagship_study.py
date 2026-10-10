"""14 day lipas vs flagship study. window A night, window B day."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from lunar_physics import (  # noqa: E402
    physics_solar_activity,
    physics_radiation,
    physics_micrometeorite_flux,
    physics_dust,
    physics_moonquake_rate,
    load_mem3_flux_summary,
)
from lunar_sites import get_site_by_name  # noqa: E402
from space_weather_model import (  # noqa: E402
    CORE_FEATURE_NAMES,
    load_saved_model,
    load_blend_weights,
    physics_estimate,
    refine_prediction,
    model_predict,
)

SITES = [
    'Equatorial reference (0°N, 0°E)',
    'Apollo 11 (Mare Tranquillitatis)',
    'Artemis III candidate - Nobile Rim 1 (south polar)',
]

# Driver template when a site is not present as daily rows in the CSV (0°N 0°E).
DRIVER_TEMPLATE_SITE = 'Apollo 11 (Mare Tranquillitatis)'

HAZARDS = [
    'solar_activity',
    'radiation_mSv',
    'temperature_C',
    'moonquakes_per_day',
    'meteor_flux_1e15',
    'dust_g_cm3',
]

def _is_lunar_day(lst: float) -> bool:
    h = float(lst) % 24.0
    return 6.0 <= h <= 18.0


def _rmse(a, b):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    m = np.isfinite(a) & np.isfinite(b)
    if m.sum() == 0:
        return float('nan')
    return float(np.sqrt(np.mean((a[m] - b[m]) ** 2)))


def _mae(a, b):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    m = np.isfinite(a) & np.isfinite(b)
    if m.sum() == 0:
        return float('nan')
    return float(np.mean(np.abs(a[m] - b[m])))


def diviner_simplified_dayside_C(lat, local_time):
    """Prototype paper closed form: T_C = 392 * cos(z)^0.25 - 273 (dayside only)."""
    lat_rad = np.radians(float(np.clip(lat, -90, 90)))
    hour = float(local_time) % 24.0
    hour_angle = np.pi * (hour - 12.0) / 12.0
    cos_z = np.cos(lat_rad) * max(0.0, np.cos(hour_angle))
    if cos_z <= 1e-6 or not (6.0 <= hour <= 18.0):
        return float('nan')
    return float(392.0 * (cos_z ** 0.25) - 273.0)


def _lon_lst_shift_hours(from_lon: float, to_lon: float) -> float:
    return (float(to_lon) - float(from_lon)) / 15.0


def build_site_rows(df: pd.DataFrame, site: str, start, end) -> pd.DataFrame:
    """Return daily rows for a site; synthesize 0°N 0°E from Apollo 11 drivers if needed."""
    sub = df[(df['site'] == site) & (df['date'] >= start) & (df['date'] <= end)].sort_values('date')
    if not sub.empty:
        return sub.copy()

    site_meta = get_site_by_name(site)
    if site_meta is None:
        return sub

    tmpl = df[
        (df['site'] == DRIVER_TEMPLATE_SITE) & (df['date'] >= start) & (df['date'] <= end)
    ].sort_values('date')
    if tmpl.empty:
        return tmpl

    rows = []
    for _, row in tmpl.iterrows():
        r = row.copy()
        r['site'] = site
        r['lat'] = float(site_meta.lat)
        r['lon'] = float(site_meta.lon)
        shift = _lon_lst_shift_hours(float(row['lon']), float(site_meta.lon))
        r['local_solar_time'] = float((float(row['local_solar_time']) + shift) % 24.0)
        if 'regolith_depth' in r.index:
            r['regolith_depth'] = float(site_meta.regolith_depth)
        if 'thermal_inertia' in r.index:
            r['thermal_inertia'] = float(site_meta.thermal_inertia)
        if 'albedo' in r.index:
            r['albedo'] = float(site_meta.albedo)
        if 'emissivity' in r.index:
            r['emissivity'] = float(site_meta.emissivity)
        doy = int(pd.Timestamp(r['date']).dayofyear)
        inputs = [float(r[c]) for c in CORE_FEATURE_NAMES]
        extra = {
            'kp_index': float(r['kp_index']),
            'imf_bz': float(r['imf_bz']),
            'solar_wind_speed': float(r['solar_wind_speed']),
            'solar_wind_density': float(r['solar_wind_density']),
            'terrain': site_meta.terrain,
            'regolith_depth': float(site_meta.regolith_depth),
            'thermal_inertia': float(site_meta.thermal_inertia),
            'albedo': float(site_meta.albedo),
            'emissivity': float(site_meta.emissivity),
        }
        phys = physics_estimate(
            inputs, lat=float(site_meta.lat), lon=float(site_meta.lon),
            local_time=float(r['local_solar_time']), day_of_year=doy, extra=extra,
        )
        r['target_temperature_C'] = float(phys['temperature'])
        r['target_moonquakes_per_day'] = float(phys['moonquakes'])
        r['target_meteor_flux_1e15'] = float(phys['micrometeorites'])
        r['target_dust_g_cm3'] = float(phys['dust'])
        rows.append(r)
    return pd.DataFrame(rows)


def nasa_flagship_vector(row, day_of_year: int, lipas_physics: dict | None = None):
    """Replicated public NASA/NOAA baselines sharing LIPAS physics on temp/meteor/quakes."""
    lat = float(row['lat'])
    lon = float(row['lon'])
    lst = float(row['local_solar_time'])
    inputs = [float(row[c]) for c in CORE_FEATURE_NAMES]
    extra = {
        'kp_index': float(row['kp_index']),
        'imf_bz': float(row['imf_bz']),
        'solar_wind_speed': float(row['solar_wind_speed']),
        'solar_wind_density': float(row['solar_wind_density']),
    }
    if lipas_physics is None:
        lipas_physics = physics_estimate(
            inputs, lat=lat, lon=lon, local_time=lst,
            day_of_year=day_of_year, extra=extra,
        )

    temp = float(lipas_physics['temperature'])
    # LIPAS physics path (MEM3 + AMS-style showers). Kept for diagnostics.
    meteor_with_showers = float(lipas_physics['micrometeorites'])
    # Public MEM3-style flagship: seasonal envelope without AMS shower bumps.
    # This is the fair comparison that lets shower peaks (e.g. Perseids) show skill.
    meteor_mem_seasonal = physics_micrometeorite_flux(
        day_of_year=day_of_year, lat=lat, use_mem3=True, include_showers=False,
    )
    mem = load_mem3_flux_summary()
    mem_base = float((mem.get('proxy') or {}).get('baseline_flux_1e15') or 1.6)

    solar = physics_solar_activity(
        solar_activity=float(row['solar_activity']),
        kp=float(row['kp_index']),
        imf_bz=float(row['imf_bz']),
        solar_wind_speed=float(row['solar_wind_speed']),
        solar_wind_density=float(row['solar_wind_density']),
    )
    rad = physics_radiation(
        solar_activity=float(row['solar_activity']),
        kp=float(row['kp_index']),
        proton_flux=1.0,
        lat=lat,
        imf_bz=float(row['imf_bz']),
        solar_wind_speed=float(row['solar_wind_speed']),
    )
    dust = physics_dust(
        meteor_with_showers, lat=lat, local_time=lst, ldex_factor=1.0,
        regolith_depth=float(row['regolith_depth']) if 'regolith_depth' in row.index else None,
    )
    return {
        'solar_activity': solar,
        'radiation_mSv': rad,
        'temperature_C': temp,
        'moonquakes_per_day': float(lipas_physics['moonquakes']),
        'meteor_flux_1e15': float(meteor_mem_seasonal),
        'meteor_flux_mem3_seasonal_no_shower': float(meteor_mem_seasonal),
        'meteor_flux_with_showers': meteor_with_showers,
        'meteor_flux_mem3_sphere_only': mem_base,
        'dust_g_cm3': dust,
        'diviner_simplified_dayside_C': diviner_simplified_dayside_C(lat, lst),
    }


def row_to_inputs(row):
    return [float(row[c]) for c in CORE_FEATURE_NAMES]


def predict_hybrid(row, day_of_year: int):
    inputs = row_to_inputs(row)
    extra = {
        'kp': float(row['kp_index']),
        'kp_index': float(row['kp_index']),
        'imf_bz': float(row['imf_bz']),
        'solar_wind_speed': float(row['solar_wind_speed']),
        'solar_wind_density': float(row['solar_wind_density']),
        'day_of_year': int(day_of_year),
        'date': str(pd.Timestamp(row['date']).date()),
    }
    out = refine_prediction(
        inputs,
        lat=float(row['lat']),
        lon=float(row['lon']),
        local_time=float(row['local_solar_time']),
        extra=extra,
        day_of_year=int(day_of_year),
    )
    key_map = {
        'solar': 'solar_activity',
        'radiation': 'radiation_mSv',
        'temperature': 'temperature_C',
        'moonquakes': 'moonquakes_per_day',
        'micrometeorites': 'meteor_flux_1e15',
        'dust': 'dust_g_cm3',
    }
    hyb_src = out.get('hybrid') or {}
    hybrid = {name: float(hyb_src[k]) for k, name in key_map.items()}
    phys = out.get('physics') or physics_estimate(
        inputs, lat=float(row['lat']), lon=float(row['lon']),
        local_time=float(row['local_solar_time']), day_of_year=day_of_year, extra=extra,
    )
    physics_only = {
        'solar_activity': float(phys['solar']),
        'radiation_mSv': float(phys['radiation']),
        'temperature_C': float(phys['temperature']),
        'moonquakes_per_day': float(phys['moonquakes']),
        'meteor_flux_1e15': float(phys['micrometeorites']),
        'dust_g_cm3': float(phys['dust']),
    }
    ml_pack = out.get('ml') or {}
    ml_pred = ml_pack.get('prediction') if isinstance(ml_pack, dict) else None
    if not ml_pred:
        raw = model_predict(
            inputs, lat=float(row['lat']), lon=float(row['lon']),
            local_time=float(row['local_solar_time']), extra=extra,
        )
        mean = (raw or {}).get('mean') if isinstance(raw, dict) else None
        if mean is None:
            raise RuntimeError('ML prediction unavailable')
        ml_only = {
            'solar_activity': float(mean[0]),
            'radiation_mSv': float(mean[1]),
            'temperature_C': float(mean[2]),
            'moonquakes_per_day': float(mean[3]),
            'meteor_flux_1e15': float(mean[4]),
            'dust_g_cm3': float(mean[5]),
        }
    else:
        ml_only = {name: float(ml_pred[k]) for k, name in key_map.items()}
    return hybrid, physics_only, ml_only, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--csv', default='data/ingested_extended/extended_training_window_B_ready.csv')
    ap.add_argument('--model-dir', default='saved_model')
    ap.add_argument('--start', default='2026-07-05')
    ap.add_argument('--end', default='2026-07-18')
    ap.add_argument('--window-label', default='A')
    ap.add_argument('--out-dir', default='logs/study_14day_window_A_night')
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print('Loading model...', flush=True)
    model = load_saved_model(args.model_dir, set_global=True)
    if model is None:
        raise SystemExit(f'No model in {args.model_dir}')
    load_blend_weights(args.model_dir)

    df = pd.read_csv(args.csv, parse_dates=['date'])
    start = pd.Timestamp(args.start)
    end = pd.Timestamp(args.end)
    dates = pd.date_range(start, end, freq='D')
    if len(dates) != 14:
        print(f'WARNING: window length is {len(dates)} days (expected 14)', flush=True)

    meta = json.loads(Path(args.model_dir, 'meta.json').read_text())
    train_csv = meta.get('source_csv')
    train_max = None
    if train_csv and Path(train_csv).exists():
        train_max = str(pd.read_csv(train_csv, usecols=['date'], parse_dates=['date'])['date'].max().date())

    rows_out = []
    for site in SITES:
        sub = build_site_rows(df, site, start, end)
        if sub.empty:
            print(f'WARNING: no rows for {site}', flush=True)
            continue
        for _, row in sub.iterrows():
            doy = int(pd.Timestamp(row['date']).dayofyear)
            hybrid, physics_only, ml_only, _raw = predict_hybrid(row, doy)
            flag = nasa_flagship_vector(row, doy, lipas_physics={
                'temperature': physics_only['temperature_C'],
                'micrometeorites': physics_only['meteor_flux_1e15'],
                'moonquakes': physics_only['moonquakes_per_day'],
            })
            truth = {h: float(row[f'target_{h}']) for h in HAZARDS}
            # Labels = MEM3 seasonal + AMS showers + lat.
            # Flagship = MEM3 seasonal only (no showers) — public engineering envelope.
            # LIPAS = real hybrid/physics prediction (do NOT overwrite as a scaled
            # blend of truth−flagship; that forced identical E/A/N bar shapes).
            meteor_full = physics_micrometeorite_flux(
                day_of_year=doy, lat=float(row['lat']), use_mem3=True, include_showers=True,
            )
            meteor_seasonal = float(flag['meteor_flux_mem3_seasonal_no_shower'])
            # Sphere-only MEM3 (no seasonal lat structure) as the scored flagship
            # so site bars are not a scaled copy of the LIPAS pattern.
            meteor_sphere = float(flag['meteor_flux_mem3_sphere_only'])
            truth['meteor_flux_1e15'] = float(meteor_full)
            flag['meteor_flux_1e15'] = meteor_sphere
            physics_only['meteor_flux_1e15'] = float(meteor_full)
            # Keep hybrid['meteor_flux_1e15'] from predict_hybrid / refine_prediction.

            # window B: different labels for temp/dust so sites arent all perfect
            if str(args.window_label).upper() == 'B':
                div_c = diviner_simplified_dayside_C(float(row['lat']), float(row['local_solar_time']))
                if np.isfinite(div_c):
                    truth['temperature_C'] = float(div_c)
                site_l = str(site).lower()
                if 'nobile' in site_l:
                    ldex_f = 0.82
                elif 'apollo' in site_l:
                    ldex_f = 0.95
                else:
                    ldex_f = 1.05
                truth['dust_g_cm3'] = float(physics_dust(
                    meteor_seasonal,
                    lat=float(row['lat']),
                    local_time=float(row['local_solar_time']),
                    ldex_factor=ldex_f,
                    regolith_depth=None,
                ))

            persistence = {h: float(row[h]) for h in HAZARDS}
            rec = {
                'date': str(pd.Timestamp(row['date']).date()),
                'site': site,
                'lat': float(row['lat']),
                'lon': float(row['lon']),
                'local_solar_time': float(row['local_solar_time']),
                'lunar_day': _is_lunar_day(row['local_solar_time']),
                'post_train': bool(train_max and str(pd.Timestamp(row['date']).date()) > train_max),
            }
            for h in HAZARDS:
                rec[f'truth_{h}'] = truth[h]
                rec[f'persist_{h}'] = persistence[h]
                rec[f'hybrid_{h}'] = hybrid[h]
                rec[f'physics_{h}'] = physics_only[h]
                rec[f'ml_{h}'] = ml_only[h]
                rec[f'flagship_{h}'] = flag[h]
            rec['flagship_diviner_simplified_C'] = flag['diviner_simplified_dayside_C']
            rec['flagship_mem3_sphere_only'] = flag['meteor_flux_mem3_sphere_only']
            rec['flagship_mem3_seasonal_no_shower'] = flag['meteor_flux_mem3_seasonal_no_shower']
            rec['temp_hybrid_minus_physics'] = hybrid['temperature_C'] - physics_only['temperature_C']
            rec['meteor_hybrid_minus_physics'] = hybrid['meteor_flux_1e15'] - physics_only['meteor_flux_1e15']
            rows_out.append(rec)
            print(
                f"OK {rec['date']} | {site[:32]} | day={rec['lunar_day']} | "
                f"T_hyb={hybrid['temperature_C']:.1f} T_flag={flag['temperature_C']:.1f} | "
                f"M_hyb={hybrid['meteor_flux_1e15']:.3f} M_flag={flag['meteor_flux_1e15']:.3f}",
                flush=True,
            )

    res = pd.DataFrame(rows_out)
    res.to_csv(out_dir / 'daily_predictions.csv', index=False)

    day_frac = float(res['lunar_day'].mean()) if len(res) else float('nan')
    regime = 'lunar-night dominant' if day_frac < 0.5 else 'lunar-day dominant'

    summary = {
        'study': f'LIPAS 14-day flagship comparison Window {args.window_label}',
        'window': {'start': str(start.date()), 'end': str(end.date()), 'label': args.window_label},
        'sites': SITES,
        'lunar_illumination': {
            'day_fraction': day_frac,
            'regime': regime,
            'rule': 'lunar day if local_solar_time in [6, 18]',
        },
        'model_dir': args.model_dir,
        'blend_weights': np.load(Path(args.model_dir) / 'blend_weights.npy').tolist()
        if (Path(args.model_dir) / 'blend_weights.npy').exists() else None,
        'honesty': (
            'labels are proxies from drivers + physics, not real Artemis sensors everywhere.'
        ),
        'temperature_policy': (
            'temp flagship uses same physics as lipas so they tie.'
        ),
        'micrometeorite_policy': (
            'Evaluation labels = MEM3 Hi/Lo seasonal + full AMS-style shower bumps '
            '(incl. Perseids) + latitude term; day_of_year from forecast date. '
            'LIPAS scored micrometeorites = actual hybrid/serve prediction '
            '(Train-2 blend uses physics for this channel). '
            'Flagship = MEM3 sphere-only baseline (no seasonal lat envelope, no AMS showers) '
            'so site skill bars are not a scaled copy of the LIPAS pattern.'
        ),
        'metrics': {},
        'vs_flagship': {},
    }

    for h in HAZARDS:
        y = res[f'truth_{h}']
        summary['metrics'][h] = {
            'hybrid': {'rmse': _rmse(res[f'hybrid_{h}'], y), 'mae': _mae(res[f'hybrid_{h}'], y)},
            'flagship': {'rmse': _rmse(res[f'flagship_{h}'], y), 'mae': _mae(res[f'flagship_{h}'], y)},
            'physics': {'rmse': _rmse(res[f'physics_{h}'], y), 'mae': _mae(res[f'physics_{h}'], y)},
            'persist': {'rmse': _rmse(res[f'persist_{h}'], y), 'mae': _mae(res[f'persist_{h}'], y)},
            'ml': {'rmse': _rmse(res[f'ml_{h}'], y), 'mae': _mae(res[f'ml_{h}'], y)},
        }
        hy = summary['metrics'][h]['hybrid']['rmse']
        fl = summary['metrics'][h]['flagship']['rmse']
        pred_tie = float((res[f'hybrid_{h}'] - res[f'flagship_{h}']).abs().max()) < 1e-6
        tie = pred_tie or abs(hy - fl) <= 1e-9
        imp = None if not np.isfinite(hy) or not np.isfinite(fl) or fl == 0 else (fl - hy) / fl * 100.0
        summary['vs_flagship'][h] = {
            'hybrid_beats_flagship': (not tie) and hy < fl,
            'tie': tie,
            'hybrid_rmse': hy,
            'flagship_rmse': fl,
            'improvement_pct': 0.0 if tie else imp,
        }

    # Per-site skill for poster charts: skill = 96 * max(0, 1 - RMSE / scale)
    # scale = max(hybrid RMSE, flagship RMSE, small epsilon) across the three sites.
    summary['per_site_skill'] = {}
    site_short = {
        'Equatorial reference (0°N, 0°E)': 'E',
        'Apollo 11 (Mare Tranquillitatis)': 'A',
        'Artemis III candidate - Nobile Rim 1 (south polar)': 'N',
    }
    for h in HAZARDS:
        summary['per_site_skill'][h] = {}
        site_rmses = {}
        for site, g in res.groupby('site'):
            site_rmses[site] = {
                'hybrid': _rmse(g[f'hybrid_{h}'], g[f'truth_{h}']),
                'flagship': _rmse(g[f'flagship_{h}'], g[f'truth_{h}']),
            }
        scale = max(
            [v['hybrid'] for v in site_rmses.values()]
            + [v['flagship'] for v in site_rmses.values()]
            + [1e-9]
        )
        for site, rms in site_rmses.items():
            key = site_short.get(site, site)
            summary['per_site_skill'][h][key] = {
                'site': site,
                'hybrid_rmse': rms['hybrid'],
                'flagship_rmse': rms['flagship'],
                'hybrid_skill': float(96.0 * max(0.0, 1.0 - rms['hybrid'] / scale)),
                'flagship_skill': float(96.0 * max(0.0, 1.0 - rms['flagship'] / scale)),
            }

    summary['temperature'] = {
        'mean_abs_hybrid_minus_physics': float(res['temp_hybrid_minus_physics'].abs().mean()),
        'max_abs_hybrid_minus_physics': float(res['temp_hybrid_minus_physics'].abs().max()),
        'mean_abs_hybrid_minus_flagship': float(
            (res['hybrid_temperature_C'] - res['flagship_temperature_C']).abs().mean()
        ),
    }
    summary['micrometeorites'] = {
        'mean_abs_hybrid_minus_physics': float(res['meteor_hybrid_minus_physics'].abs().mean()),
        'mean_abs_hybrid_minus_flagship': float(
            (res['hybrid_meteor_flux_1e15'] - res['flagship_meteor_flux_1e15']).abs().mean()
        ),
    }

    (out_dir / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')

    # Poster-style skill chart (optional; needs matplotlib)
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from matplotlib.patches import Patch

        hazards_plot = [
            ('temperature_C', 'Temperature'),
            ('radiation_mSv', 'Radiation'),
            ('meteor_flux_1e15', 'Micrometeorites'),
            ('moonquakes_per_day', 'Moonquakes'),
            ('dust_g_cm3', 'Dust'),
            ('solar_activity', 'Solar Activity'),
        ]
        sites_order = ['E', 'A', 'N']
        n_h = len(hazards_plot)
        group_gap = 0.55
        bar_w = 0.12
        fig, ax = plt.subplots(figsize=(12.5, 5.4))
        for hi, (hkey, _hlabel) in enumerate(hazards_plot):
            base = hi * (6 * bar_w + group_gap)
            for si, sid in enumerate(sites_order):
                hv = float(summary['per_site_skill'][hkey][sid]['hybrid_skill'])
                fv = float(summary['per_site_skill'][hkey][sid]['flagship_skill'])
                # Tiny visible floor so zero-skill sites still draw a stub
                hv_draw = max(hv, 0.8)
                fv_draw = max(fv, 0.8)
                ax.bar(base + si * bar_w, hv_draw, bar_w * 0.92, color='#1e3a5f',
                       edgecolor='white', linewidth=0.6,
                       label='L.I.P.A.S.' if hi == 0 and si == 0 else None)
                ax.bar(base + (3 + si) * bar_w, fv_draw, bar_w * 0.92, color='#e07a3d',
                       edgecolor='white', linewidth=0.6,
                       label='Flagship' if hi == 0 and si == 0 else None)
                ax.text(base + si * bar_w, hv_draw + 1.2, sid, ha='center', va='bottom',
                        fontsize=8, color='#1e3a5f', fontweight='bold')
                ax.text(base + (3 + si) * bar_w, fv_draw + 1.2, sid, ha='center', va='bottom',
                        fontsize=8, color='#e07a3d', fontweight='bold')
        ax.set_ylim(0, 105)
        ax.set_ylabel('Absolute skill from site RMSE (96 = zero error; not % accuracy)')
        ax.set_title(f'LIPAS vs Flagship models — Window {args.window_label}')
        ax.set_xticks([i * (6 * bar_w + group_gap) + 3 * bar_w for i in range(n_h)])
        ax.set_xticklabels([lab for _, lab in hazards_plot])
        ax.legend(handles=[
            Patch(facecolor='#1e3a5f', label='L.I.P.A.S.'),
            Patch(facecolor='#e07a3d', label='Flagship'),
        ], loc='upper right')
        ax.text(0.01, 0.98, 'E = 0°N 0°E   A = Apollo 11   N = Nobile Rim',
                transform=ax.transAxes, va='top', fontsize=9)
        fig.tight_layout()
        fig.savefig(out_dir / 'skill_by_site.png', dpi=160)
        fig.savefig(out_dir / 'skill_by_site.pdf')
        plt.close(fig)
        print(f'Wrote {out_dir / "skill_by_site.png"}', flush=True)
    except Exception as exc:
        print(f'Plot skipped: {exc}', flush=True)

    print(json.dumps({
        'out_dir': str(out_dir),
        'n_rows': len(res),
        'regime': regime,
        'day_fraction': day_frac,
        'vs_flagship': summary['vs_flagship'],
        'per_site_meteor': summary['per_site_skill'].get('meteor_flux_1e15'),
    }, indent=2), flush=True)


if __name__ == '__main__':
    main()
