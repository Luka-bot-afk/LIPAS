from __future__ import annotations

import math
from datetime import datetime, timezone, timedelta
from typing import Any

from mercurius.data_ingestion import load_lipas_drivers, horizons_r_au
from mercurius.mercury_magnetosphere import magnetosphere_state
from mercurius.mercury_model import RETRAIN_VERDICT, hybrid_forecast
from mercurius.mercury_physics import (
    MERCURY_SOLAR_DAY_D,
    local_solar_time_mercury,
    mercury_r_au,
)
from mercurius.mercury_sites import SITES, get_site, sites_payload

_DRAW_KEYS = (
    'grid', 'equatorial_grid', 'bmag_grid', 'magnetopause', 'bow_shock',
    'field_lines', 'colors', 'legend',
)

def _drivers_for_hour(extra: dict, hour: float) -> dict:

    try:
        from swpc_nowcast import drivers_at_hour
        out = drivers_at_hour(extra, hour)
    except Exception:
        out = dict(extra)
    if out.get('solar_activity') is not None or out.get('flare_index') is not None:
        sa0 = float(out.get('solar_activity') or 5.0)
        fi = float(out.get('flare_index') if out.get('flare_index') is not None else 2.0)
        out['solar_activity'] = max(sa0, 4.0 + fi * 0.85)
    return out

def _flare_hazard(flare_index: float, xray_flux=None, region_probs=None) -> float:

    fi = float(flare_index or 0.0)
    if xray_flux is not None:
        try:
            from swpc_nowcast import flare_class_from_flux
            _, idx = flare_class_from_flux(float(xray_flux))
            fi = max(fi, idx)
        except Exception:
            pass
    probs = region_probs or {}
    p_m = float(probs.get('m_flare_probability') or 0.0)
    p_x = float(probs.get('x_flare_probability') or 0.0)
    return float(min(10.0, max(0.0, 0.85 * fi + 0.012 * p_m + 0.03 * p_x)))

def _cme_hazard(kp: float, bz: float, flare_index: float, region_probs=None) -> float:
    probs = region_probs or {}
    p_m = float(probs.get('m_flare_probability') or 0.0)
    p_x = float(probs.get('x_flare_probability') or 0.0)
    p_p = float(probs.get('proton_probability') or 0.0)
    return float(min(10.0, max(0.0,
        max(0.0, kp - 2.0) * 0.55
        + max(0.0, -bz) * 0.08
        + flare_index * 0.12
        + 0.02 * p_m + 0.05 * p_x + 0.04 * p_p
    )))

def _sep_index(rad: float, kp: float, bz: float) -> float:
    return float(min(10.0, max(0.0, (rad - 0.05) * 28.0 + max(0.0, kp - 3.0) * 0.9 + max(0.0, -bz) * 0.15)))

def _hermean_surface(st: dict[str, Any], site_lat: float) -> dict[str, float]:
    lst = float(st.get("lst_h") or 12.0)
    rad = float((st.get("prediction") or {}).get("radiation") or 0.05)
    temp = float((st.get("prediction") or {}).get("temperature") or 0.0)
    solar = float((st.get("prediction") or {}).get("solar") or 8.0)
    kp = float((st.get("physics") or {}).get("kp_index") or 3.0)
    fi = float((st.get("physics") or {}).get("flare_index") or 2.0)
    r_au = float(st.get("r_au") or 0.387)
    flux = (1.0 / max(0.28, r_au)) ** 1.25
    dawn = math.exp(-(((lst - 6.0) / 3.2) ** 2))
    dusk = math.exp(-(((lst - 18.0) / 3.2) ** 2))
    dayside = 1.0 if 6.0 <= lst <= 18.0 else 0.15
    illum = max(0.0, math.cos(math.pi * (lst - 12.0) / 12.0)) if 6.0 <= lst <= 18.0 else 0.0
    micrometeorites = min(10.0, 1.7 * flux * (0.75 + 0.35 * (1.0 - 0.5 * dayside)) + 0.05 * kp)
    dust = min(10.0, 2.1 * flux * (0.3 + 0.7 * illum + 0.5 * dawn) + 0.06 * kp)
    moonquakes = min(10.0, 1.5 + 6.0 * (dawn + dusk) + abs(site_lat) / 85.0)
    thermal = min(10.0, abs(temp + 20.0) / 42.0)
    eva = min(10.0, rad * 32.0 + thermal * 0.5 + dust * 0.22)
    comms = min(10.0, 0.85 * fi + 0.12 * solar + (2.4 if illum > 0.45 else 0.35))
    return {
        "dust": round(dust, 3),
        "moonquakes": round(moonquakes, 3),
        "micrometeorites": round(micrometeorites, 3),
        "evaRisk": round(eva, 3),
        "comms": round(comms, 3),
    }


def _proton_index(proton_flux, rad: float, kp: float) -> float:
    if proton_flux is not None:
        try:
            pf = float(proton_flux)
            if pf > 0:
                return float(min(10.0, max(0.0, math.log10(max(pf, 0.01)) * 2.2 + 2.5)))
        except (TypeError, ValueError):
            pass
    return float(min(10.0, max(0.0, (rad - 0.05) * 35.0 + max(0.0, kp - 2.0) * 0.4)))

def _inputs_from_drivers(extra: dict) -> list[float]:
    from mercurius.mercury_model import one_au_solar_prior

    kp = float(extra.get('kp_index') or extra.get('kp') or 3.0)
    solar_seed = float(extra.get('solar_activity') or 5.0)
    solar_1au, _, _ = one_au_solar_prior([solar_seed, 0.06, 0.0, 0.0, 0.0, 0.0], extra)
    proton = extra.get('proton_flux')
    if proton is not None:
        try:
            from lunar_physics import normalize_proton_flux
            rad = 0.045 + float(normalize_proton_flux(float(proton))) * 0.18 + 0.012 * max(0.0, kp - 2.0)
        except Exception:
            rad = 0.05 + 0.025 * max(0.0, kp - 2.0)
    else:
        rad = 0.05 + 0.025 * max(0.0, kp - 2.0)
    return [solar_1au, rad, 0.0, 0.0, 0.0, 0.0]

def _alerts(phys: dict, mstate: dict, lst: float) -> list[dict[str, str]]:
    alerts = []
    rss = float(mstate.get('standoff_rm') or 1.45)
    rad = float(phys.get('radiation') or 0)
    solar = float(phys.get('solar') or 0)
    temp = float(phys.get('temperature') or 0)
    clock = (mstate.get('imf_clock') or {}).get('orientation')
    p = float(mstate.get('p_dyn_npa') or 0)
    if rss <= 1.02:
        alerts.append({
            'level': 'high',
            'id': 'mp_surface',
            'title': 'Shield at the surface',
            'body': f'Size {rss:.2f} RM. Solar wind can hit the ground on the day side.',
        })
    elif rss <= 1.15:
        alerts.append({
            'level': 'warn',
            'id': 'mp_compressed',
            'title': 'Shield squeezed',
            'body': f'Size {rss:.2f} RM (quiet is about 1.45). Less protection.',
        })
    if clock == 'southward' and p > 8:
        alerts.append({
            'level': 'warn',
            'id': 'reconnection',
            'title': 'Field points south',
            'body': 'Wind pressure is high and the field is south. More particles can get in.',
        })
    if rad >= 0.25:
        alerts.append({
            'level': 'high',
            'id': 'sep',
            'title': 'High radiation',
            'body': f'{rad:.3f} mSv/h at this site.',
        })
    elif rad >= 0.12:
        alerts.append({
            'level': 'info',
            'id': 'rad_up',
            'title': 'Radiation up',
            'body': f'{rad:.3f} mSv/h — above a quiet day.',
        })
    if solar >= 40:
        alerts.append({
            'level': 'warn',
            'id': 'solar',
            'title': 'Strong solar activity',
            'body': f'Solar index {solar:.1f}.',
        })
    if temp >= 350:
        alerts.append({
            'level': 'info',
            'id': 'hot',
            'title': 'Very hot day side',
            'body': f'{temp:.0f} °C at this hour. Noon can pass 400 °C.',
        })
    elif temp <= -190:
        alerts.append({
            'level': 'info',
            'id': 'cold',
            'title': 'Polar cold',
            'body': f'{temp:.0f} °C — normal in a dark polar crater.',
        })
    elif temp <= -100 and not (6.0 <= float(lst) % 24.0 <= 18.0):
        alerts.append({
            'level': 'info',
            'id': 'night_cold',
            'title': 'Night cold',
            'body': f'{temp:.0f} °C is normal Mercury night.',
        })
    if not alerts:
        alerts.append({
            'level': 'ok',
            'id': 'quiet',
            'title': 'Quiet',
            'body': f'Shield {rss:.2f} RM, radiation {rad:.3f} mSv/h.',
        })
    return alerts

def _slim_magnetosphere(mstate: dict) -> dict:
    return {k: v for k, v in mstate.items() if k not in _DRAW_KEYS}

def build_state(
    site_id: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
    hour: float = 0.0,
    lst: float | None = None,
    extra: dict | None = None,
    include_draw: bool = True,
) -> dict[str, Any]:
    site = get_site(site_id)
    if lat is not None:
        site_lat, site_lon = float(lat), float(lon if lon is not None else site.lon)
        site_name = site.name if site_id else 'Custom'
        terrain, albedo = site.terrain, site.albedo
    else:
        site_lat, site_lon = site.lat, site.lon
        site_name = site.name
        terrain, albedo = site.terrain, site.albedo

    now = datetime.now(timezone.utc) + timedelta(hours=float(hour))
    if extra is None:
        extra = load_lipas_drivers(12.0)
    else:
        extra = dict(extra)
    extra = _drivers_for_hour(extra, hour)
    r_au = horizons_r_au(now) or mercury_r_au(when=now)
    extra['r_au'] = r_au
    extra['terrain'] = terrain
    extra['albedo'] = albedo
    extra['day_of_year'] = int(now.strftime('%j'))
    extra['hour_of_day'] = float(now.hour) + float(hour)
    extra['day_of_month'] = float(now.day)
    extra['month_of_year'] = float(now.month)

    lst_now = local_solar_time_mercury(site_lon, now)
    if lst is None:
        lst = (lst_now + float(hour) * (24.0 / (MERCURY_SOLAR_DAY_D * 24.0))) % 24.0
    lst = float(lst) % 24.0

    inputs = _inputs_from_drivers(extra)
    blended = hybrid_forecast(inputs, lat=site_lat, lon=site_lon, local_time=lst, extra=extra)
    phys = blended['physics']
    sw = dict(phys['wind_mercury'])
    hybrid = blended.get('hybrid') or {}
    p_dyn = float(hybrid.get('p_dyn_npa', phys['p_dyn_npa']))
    if hybrid.get('imf_b_mag') is not None:
        sw['imf_b_mag'] = float(hybrid['imf_b_mag'])
    mfull = magnetosphere_state(
        p_dyn, sw['imf_by'], sw['imf_bz'], sw['imf_b_mag'],
    )
    mstate = mfull if include_draw else _slim_magnetosphere(mfull)
    alert_phys = dict(phys)
    alert_phys['radiation'] = float(hybrid.get('radiation', phys['radiation']))
    alert_phys['solar'] = float(hybrid.get('solar', phys['solar']))
    alert_phys['temperature'] = float(hybrid.get('temperature', phys['temperature']))
    alerts = _alerts(alert_phys, mfull, lst)
    temp_c = float(phys['temperature'])
    day_night = 'dayside' if 6.0 <= lst <= 18.0 else 'nightside'
    flare_class = extra.get('flare_class')
    flare_index = float(extra.get('flare_index') or min(10.0, max(0.0, float(phys['solar']) * 0.14)))
    conf = extra.get('confidence')
    if not isinstance(conf, dict):
        try:
            from swpc_nowcast import forecast_confidence
            conf = forecast_confidence(extra, hour=float(hour))
        except Exception:
            conf = {'overall_pct': 62.0, 'basis': 'physics_persistence', 'per_channel_pct': {}}
    conf_pct = float(conf.get('overall_pct') or 62.0)

    out = {
        'utc': now.isoformat(),
        'forecast_hour': float(hour),
        'site': {
            'id': site.id if lat is None else 'custom',
            'name': site_name,
            'lat': site_lat,
            'lon': site_lon,
            'terrain': terrain,
            'albedo': albedo,
            'note': site.note if lat is None else '',
        },
        'lst_h': round(lst, 3),
        'day_night': day_night,
        'r_au': round(float(r_au), 5),
        'r_source': 'horizons' if horizons_r_au(now) else 'kepler',
        'prediction': blended['hybrid'],
        'confidence_pct': round(conf_pct, 1),
        'confidence': conf,
        'physics': {
            'solar': phys['solar'],
            'radiation': phys['radiation'],
            'temperature': phys['temperature'],
            'temperature_k': round(temp_c + 273.15, 1),
            'solar_constant_w_m2': phys['solar_constant_w_m2'],
            'p_dyn_npa': phys['p_dyn_npa'],
            'kp_index': phys['kp_index'],
            'f107': phys.get('f107') if phys.get('f107') is not None else extra.get('f107'),
            'proton_flux': phys.get('proton_flux'),
            'dst': extra.get('dst'),
            'ap': extra.get('ap'),
            'ssn': extra.get('ssn'),
            'xray_flux': extra.get('xray_flux'),
            'flare_class': flare_class,
            'flare_index': flare_index,
        },
        'wind_1au': {
            'speed': extra.get('solar_wind_speed'),
            'density': extra.get('solar_wind_density'),
            'imf_bz': extra.get('imf_bz'),
            'imf_by': extra.get('imf_by'),
            'imf_bt': extra.get('imf_bt'),
            'kp_index': extra.get('kp_index'),
            'omni_date': extra.get('omni_date'),
            'f107': extra.get('f107'),
            'dst': extra.get('dst'),
            'flare_class': flare_class,
            'source': extra.get('wind_source'),
        },
        'wind_mercury': sw,
        'magnetosphere': mstate,
        'lead_time': phys['lead_time'],
        'regime': phys['regime'],
        'alerts': alerts,
        'drivers': {
            'sources': extra.get('driver_sources') or [],
            'omni_date': extra.get('omni_date'),
            'flare_class': flare_class,
            'solar_region_count': extra.get('solar_region_count'),
            'wind_source': extra.get('wind_source'),
            'data_age_hours': extra.get('data_age_hours'),
            'm_flare_probability': extra.get('m_flare_probability')
                or (extra.get('region_probs') or {}).get('m_flare_probability'),
            'x_flare_probability': extra.get('x_flare_probability')
                or (extra.get('region_probs') or {}).get('x_flare_probability'),
            'regions_observed_date': extra.get('regions_observed_date'),
        },
        'ml_policy': RETRAIN_VERDICT,
        'ml': blended.get('ml'),
        'ml_ready': blended.get('ml_ready'),
        'ml_error': blended.get('ml_error'),
        'solar_prior_1au': blended.get('solar_prior_1au'),
        'solar_prior_source': blended.get('solar_prior_source'),
        'source': blended.get('source'),
    }
    surf = _hermean_surface(out, site_lat)
    pred = dict(out['prediction'] or {})
    pred.update(surf)
    out['prediction'] = pred
    out['surface'] = surf
    return out

def math_cos_incidence(lat: float, lst_h: float) -> float:
    lat_r = math.radians(lat)
    ha = math.pi * ((lst_h % 24.0) - 12.0) / 12.0
    return float(max(0.0, math.cos(lat_r) * math.cos(ha)))

def build_forecast(site_id: str | None = None, hours: int = 24,
                   lst: float | None = None) -> dict[str, Any]:
    hours = max(1, min(48, int(hours)))
    site = get_site(site_id)
    extra = load_lipas_drivers(12.0)
    now = datetime.now(timezone.utc)
    series: dict[str, list] = {
        'time': [], 'solar': [], 'radiation': [], 'temperature': [],
        'temperature_k': [], 'standoff_rm': [], 'p_dyn_npa': [],
        'imf_bz': [], 'imf_b_mag': [],
        'kp': [], 'lst': [], 'illumination': [], 'sep': [], 'protons': [],
        'flares': [], 'cme': [], 'storm': [], 'solar_constant': [],
        'cusp_lat': [], 'density': [], 'speed': [],
        'f107': [], 'dst': [], 'flare_index': [],
        'confidence_series': [],
        'dust': [], 'moonquakes': [], 'micrometeorites': [],
        'evaRisk': [], 'comms': [],
    }
    flare0 = float(extra.get('flare_index') or 2.0)
    region_probs = extra.get('region_probs') or {
        'm_flare_probability': extra.get('m_flare_probability'),
        'x_flare_probability': extra.get('x_flare_probability'),
        'proton_probability': extra.get('proton_probability'),
        'c_flare_probability': extra.get('c_flare_probability'),
    }
    for h in range(hours):
        st = build_state(
            site_id=site.id, hour=float(h), lst=lst, extra=extra, include_draw=False,
        )
        series['time'].append(h)
        series['solar'].append(st['prediction']['solar'])
        series['radiation'].append(st['prediction']['radiation'])
        t_c = float(st['prediction']['temperature'])
        series['temperature'].append(t_c)
        series['temperature_k'].append(t_c + 273.15)
        series['standoff_rm'].append(st['magnetosphere']['standoff_rm'])
        series['p_dyn_npa'].append(st['physics']['p_dyn_npa'])
        series['imf_bz'].append(st['wind_mercury']['imf_bz'])
        series['imf_b_mag'].append(st['wind_mercury']['imf_b_mag'])
        series['kp'].append(st['physics']['kp_index'])
        series['lst'].append(st['lst_h'])
        series['illumination'].append(
            max(0.0, math_cos_incidence(site.lat, st['lst_h'])) * 100.0
        )
        rad = float(st['prediction']['radiation'])
        kp = float(st['physics']['kp_index'] or 3)
        sol = float(st['prediction']['solar'])
        bz = float(st['wind_mercury']['imf_bz'])
        series['sep'].append(_sep_index(rad, kp, bz))
        series['protons'].append(_proton_index(st['physics'].get('proton_flux'), rad, kp))
        fi = float(st['physics'].get('flare_index') or flare0)
        series['flare_index'].append(fi)
        series['flares'].append(_flare_hazard(fi, st['physics'].get('xray_flux'), region_probs))
        series['cme'].append(_cme_hazard(kp, bz, fi, region_probs))
        if kp >= 7 or fi >= 7:
            storm_lvl = 2
        elif kp >= 5 or fi >= 4.5:
            storm_lvl = 1
        else:
            storm_lvl = 0
        series['storm'].append(storm_lvl)
        series['solar_constant'].append(st['physics']['solar_constant_w_m2'])
        series['cusp_lat'].append(st['magnetosphere'].get('cusp_latitude_deg', 45.0))
        series['density'].append(st['wind_mercury']['density'])
        series['speed'].append(st['wind_mercury']['speed'])
        series['f107'].append(st['physics'].get('f107') or extra.get('f107') or 120.0)
        series['dst'].append(st['physics'].get('dst') if st['physics'].get('dst') is not None else -20.0)
        series['confidence_series'].append(float(st.get('confidence_pct') or 62.0))
        surf = st.get('surface') or {}
        series['dust'].append(surf.get('dust', 0.0))
        series['moonquakes'].append(surf.get('moonquakes', 0.0))
        series['micrometeorites'].append(surf.get('micrometeorites', 0.0))
        series['evaRisk'].append(surf.get('evaRisk', 0.0))
        series['comms'].append(surf.get('comms', 0.0))

    lst_curve = {
        'hour': [], 'temperature': [], 'temperature_k': [],
        'radiation': [], 'illumination': [], 'day_night': [],
    }
    extra_lst = dict(extra)
    extra_lst['skip_ml'] = True
    for i in range(25):
        st = build_state(
            site_id=site.id, hour=0.0, lst=float(i), extra=extra_lst, include_draw=False,
        )
        t_c = float(st['prediction']['temperature'])
        lst_curve['hour'].append(float(i))
        lst_curve['temperature'].append(t_c)
        lst_curve['temperature_k'].append(t_c + 273.15)
        lst_curve['radiation'].append(st['prediction']['radiation'])
        lst_curve['illumination'].append(
            max(0.0, math_cos_incidence(site.lat, float(i))) * 100.0
        )
        lst_curve['day_night'].append('day' if 6.0 <= i <= 18.0 else 'night')

    snap0 = build_state(site_id=site.id, hour=0.0, lst=lst, extra=extra, include_draw=True)
    return {
        **series,
        'lst_curve': lst_curve,
        'now': snap0,
        'hours': hours,
        'site': snap0['site'],
        'r_au': snap0['r_au'],
        'source': snap0['source'],
        'driver_sources': snap0['drivers']['sources'],
        'flare_class': snap0['physics'].get('flare_class'),
        'ml_policy': RETRAIN_VERDICT,
        'ml_ready': snap0.get('ml_ready'),
        'ml_error': snap0.get('ml_error'),
        'utc': now.isoformat(),
        'confidence_pct': snap0.get('confidence_pct'),
        'confidence': snap0.get('confidence'),
        'channel_origin': {
            'radiation': 'mercury_lstm+physics' if 'lstm' in str(snap0.get('source') or '') else 'mercury_physics',
            'solar': '1au_swpc_scaled',
            'temperature': 'mercury_physics',
            'temperature_k': 'derived',
            'standoff_rm': 'hermean_magnetosphere',
            'p_dyn_npa': 'scaled_solar_wind',
            'imf_bz': 'dscovr_rtsw_or_omni',
            'kp': 'swpc_omni',
            'f107': 'swpc',
            'dst': 'swpc_or_omni',
            'illumination': 'geometry',
            'sep': 'derived_from_core',
            'protons': 'goes_archive_or_derived',
            'flares': 'goes_xray',
            'flare_index': 'goes_xray',
            'cme': 'derived_from_core',
            'dust': 'hermean_exosphere',
            'moonquakes': 'thermal_contraction',
            'micrometeorites': 'meteoroid_flux_0p4au',
            'evaRisk': 'derived_from_core',
            'comms': 'flare_plasma',
        },
    }

def build_sites_now() -> dict[str, Any]:
    extra = load_lipas_drivers(12.0)
    rows = []
    for s in SITES:
        if s.group == 'overview' or s.id == 'overview':
            continue
        st = build_state(site_id=s.id, hour=0.0, extra=extra, include_draw=False)
        rad = float(st['prediction']['radiation'])
        kp = float(st['physics']['kp_index'] or 3)
        sol = float(st['prediction']['solar'])
        bz = float(st['wind_mercury']['imf_bz'])
        fi = float(st['physics'].get('flare_index') or 2.0)
        rows.append({
            'id': s.id,
            'name': s.name,
            'lat': s.lat,
            'lon': s.lon,
            'terrain': s.terrain,
            'albedo': s.albedo,
            'image': s.image,
            'quadrant': s.quadrant,
            'group': s.group,
            'note': s.note,
            'solar': sol,
            'radiation': rad,
            'temperature': st['prediction']['temperature'],
            'temperature_k': float(st['prediction']['temperature']) + 273.15,
            'lst_h': st['lst_h'],
            'day_night': st.get('day_night'),
            'standoff_rm': st['magnetosphere']['standoff_rm'],
            'p_dyn_npa': st['physics']['p_dyn_npa'],
            'imf_bz': bz,
            'imf_b_mag': st['wind_mercury'].get('imf_b_mag'),
            'kp': kp,
            'sep': _sep_index(rad, kp, bz),
            'protons': _proton_index(st['physics'].get('proton_flux'), rad, kp),
            'flares': _flare_hazard(fi, st['physics'].get('xray_flux'), extra.get('region_probs')),
            'cme': _cme_hazard(kp, bz, fi, extra.get('region_probs')),
            'storm': 2 if kp >= 7 or fi >= 7 else (1 if kp >= 5 or fi >= 4.5 else 0),
            'f107': st['physics'].get('f107'),
            'flare_class': st['physics'].get('flare_class'),
            'alerts': st.get('alerts') or [],
        })
    return {
        'sites': rows,
        'catalog': sites_payload(),
        'channels': [
            {'id': 'radiation', 'label': 'Radiation', 'unit': 'mSv/h'},
            {'id': 'solar', 'label': 'Solar', 'unit': 'index'},
            {'id': 'temperature', 'label': 'Temperature', 'unit': 'C'},
            {'id': 'standoff_rm', 'label': 'MP standoff', 'unit': 'R_M'},
            {'id': 'p_dyn_npa', 'label': 'P_dyn', 'unit': 'nPa'},
            {'id': 'imf_bz', 'label': 'IMF Bz', 'unit': 'nT'},
            {'id': 'kp', 'label': 'Kp', 'unit': ''},
            {'id': 'f107', 'label': 'F10.7', 'unit': 'sfu'},
            {'id': 'dst', 'label': 'Dst', 'unit': 'nT'},
            {'id': 'flares', 'label': 'Flares', 'unit': 'GOES'},
        ],
        'coverage': {
            'count': len(rows),
            'quadrants': sorted({r.get('quadrant') or 'other' for r in rows}),
            'note': 'Antipodes, polar craters, Caloris, and equatorial longitudes.',
        },
        'drivers': {
            'sources': extra.get('driver_sources') or [],
            'flare_class': extra.get('flare_class'),
            'f107': extra.get('f107'),
            'omni_date': extra.get('omni_date'),
        },
    }
