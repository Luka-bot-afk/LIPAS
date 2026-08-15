"""LIPAS."""
import numpy as np

SIGMA_SB = 5.670374419e-8
SOLAR_CONSTANT_1AU_W_M2 = 1361.0
SOLAR_CONSTANT_W_M2 = SOLAR_CONSTANT_1AU_W_M2

_APOLLO_NIGHTSIDE_HOURS = np.array([0.0, 3.0, 6.0, 9.0, 12.0])
_APOLLO_NIGHTSIDE_EQUATOR_TEMPS_C = np.array([-20.0, -90.0, -130.0, -158.0, -173.0])

_APOLLO_NIGHTSIDE_POLY_COEFFS = np.polyfit(_APOLLO_NIGHTSIDE_HOURS, _APOLLO_NIGHTSIDE_EQUATOR_TEMPS_C, 3)

_APOLLO_HEAT_FLOW_MEASUREMENTS_W_M2 = (0.021, 0.016)
_APOLLO_AVG_HEAT_FLOW_W_M2 = float(np.mean(_APOLLO_HEAT_FLOW_MEASUREMENTS_W_M2))
APOLLO_GEOTHERMAL_FLOOR_C = float((_APOLLO_AVG_HEAT_FLOW_W_M2 / (0.95 * SIGMA_SB)) ** 0.25 - 273.15)

# rough terrain defaults
_TERRAIN_OPTICS = {
    'mare': {'albedo': 0.07, 'emissivity': 0.95},
    'highland': {'albedo': 0.12, 'emissivity': 0.93},
    'polar': {'albedo': 0.15, 'emissivity': 0.95},
}

def clamp(v, lo, hi, fallback=None):
    try:
        if v is None:
            return fallback if fallback is not None else lo
        return float(max(lo, min(hi, v)))
    except Exception:
        return fallback if fallback is not None else lo

def earth_sun_distance_au(day_of_year: float) -> float:
    """earth sun distance kinda approx from day of year"""

    doy = float(day_of_year) % 365.25

    M = 2.0 * np.pi * ((doy - 4.0) / 365.25)
    e = 0.0167
    return float(1.0 - e * np.cos(M))

def solar_constant_at_doy(day_of_year=None) -> float:

    import time as _time
    if day_of_year is None:
        day_of_year = int(_time.strftime('%j', _time.gmtime()))
    r_au = earth_sun_distance_au(day_of_year)
    return float(SOLAR_CONSTANT_1AU_W_M2 / max(r_au * r_au, 0.9))

def terrain_optics(terrain: str | None = None, albedo=None, emissivity=None):
    base = _TERRAIN_OPTICS.get(str(terrain or 'mare').lower(), _TERRAIN_OPTICS['mare'])
    a = float(albedo) if albedo is not None else float(base['albedo'])
    e = float(emissivity) if emissivity is not None else float(base['emissivity'])
    return float(clamp(a, 0.02, 0.4, 0.07)), float(clamp(e, 0.7, 0.99, 0.95))

def apollo_nightside_temperature(hour, lat_rad=0.0):
    hour = float(hour) % 24
    hours_after_sunset = (hour - 18.0) if hour >= 18.0 else (hour + 6.0)
    hours_after_sunset = float(clamp(hours_after_sunset, 0.0, 12.0, 12.0))
    equator_temp_c = float(np.polyval(_APOLLO_NIGHTSIDE_POLY_COEFFS, hours_after_sunset))
    lat_cooling_c = (1.0 - np.cos(lat_rad)) * 60.0

    abs_lat_deg = abs(float(np.degrees(lat_rad)))
    if abs_lat_deg > 70.0:
        polar_extra = 25.0 * ((abs_lat_deg - 70.0) / 20.0) ** 2
        lat_cooling_c += polar_extra
    temp_c = equator_temp_c - lat_cooling_c
    return float(clamp(temp_c, APOLLO_GEOTHERMAL_FLOOR_C, 0.0, equator_temp_c))

def physics_temperature(lat, lon, local_time, albedo=0.07, emissivity=0.95,
                        day_of_year=None, terrain=None, thermal_inertia=None):
    try:
        lat_rad = np.radians(float(clamp(float(lat), -90.0, 90.0, 0.0)))
        hour = float(local_time) % 24
        hour_angle = np.pi * (hour - 12.0) / 12.0
        cos_incidence = np.cos(lat_rad) * max(0.0, np.cos(hour_angle))
        a, e = terrain_optics(terrain, albedo=albedo, emissivity=emissivity)
        s_const = solar_constant_at_doy(day_of_year)
        abs_lat = abs(float(lat))

        if abs_lat >= 85.0:
            cos_incidence *= max(0.05, np.cos(np.radians(abs_lat)))
        dayside = 6.0 <= hour <= 18.0 and cos_incidence > 1e-6
        if dayside:
            radiative = s_const * (1.0 - a) * cos_incidence
            temp_k = (radiative / (e * SIGMA_SB)) ** 0.25
            temp_c = temp_k - 273.15

            _ = lon
        else:
            temp_c = apollo_nightside_temperature(hour, lat_rad=lat_rad)

        if thermal_inertia is not None:
            ti_norm = float(clamp((float(thermal_inertia) - 48.0) / 18.0, -1.2, 1.2, 0.0))
            if dayside:
                temp_c -= 7.5 * ti_norm
            else:
                temp_c += 5.5 * ti_norm
        return float(clamp(temp_c, -230.0, 130.0))
    except Exception:
        return -160.0

def physics_solar_activity(solar_activity=5.0, kp=3.0, imf_bz=-2.0,
                           solar_wind_speed=400.0, solar_wind_density=5.0,
                           f107=None):
    sa = float(solar_activity)
    kp = float(kp)
    bz = float(imf_bz)
    v = float(solar_wind_speed)
    n = float(solar_wind_density)

    quiet = 4.5
    kp_term = 0.85 * max(0.0, kp - 2.0) ** 1.35

    bz_term = 0.35 * max(0.0, -bz - 1.0)

    stream = 0.012 * max(0.0, v - 450.0) + 0.08 * max(0.0, n - 8.0)
    f107_term = 0.0
    if f107 is not None:

        f107_term = 0.55 * max(0.0, (float(f107) - 70.0) / 18.0)
    driven = quiet + kp_term + bz_term + stream + f107_term

    out = 0.55 * sa + 0.45 * driven
    return float(clamp(out, 0.0, 80.0, sa))

def physics_radiation(solar_activity=5.0, kp=3.0, proton_flux=1.0,
                      lat=None, imf_bz=None, solar_wind_speed=None):
    sa = float(solar_activity)
    kp = float(kp)
    pf = float(proton_flux)

    solar_mod = max(0.55, min(1.45, sa / 8.0))
    gcr = calc_gcr_radiation(solar_mod=solar_mod)
    quiet = 0.018
    storm = 0.0
    if kp > 2.0:
        storm += 0.006 * (kp - 2.0)
    if kp >= 5.0:
        storm += 0.012 * (kp - 4.5)
    if kp >= 7.0:
        storm += 0.035
    if imf_bz is not None and float(imf_bz) < -5.0:
        storm += 0.008 * min(3.0, (-float(imf_bz) - 5.0) / 5.0)
    if solar_wind_speed is not None and float(solar_wind_speed) > 600.0:
        storm += 0.004 * min(2.0, (float(solar_wind_speed) - 600.0) / 200.0)
    sep = 0.0
    if pf > 1.0:
        sep += 0.004 * (pf - 1.0)
    if sa > 12.0:
        sep += 0.012 * ((sa - 12.0) / 10.0)
    if sa > 25.0:
        sep *= 1.35
    rad = gcr + quiet + storm + sep

    if lat is not None:
        abs_lat = abs(float(lat)) / 90.0
        rad *= (1.0 + 0.08 * abs_lat ** 2)
    return float(clamp(rad, 0.01, 10.0, 0.057))

# shower peaks (doy)
_METEOR_SHOWER_PEAKS = (
    (3, 1.18),
    (22, 1.12),
    (125, 1.22),
    (155, 1.14),
    (189, 1.08),
    (216, 1.30),
    (236, 1.16),
    (278, 1.20),
    (304, 1.14),
    (320, 1.18),
    (346, 1.28),
    (356, 1.12),
)

_MEM3_SUMMARY_CACHE = None

def load_mem3_flux_summary(path: str = 'data/archives/mem3/mem3_flux_summary.json'):
    global _MEM3_SUMMARY_CACHE
    if _MEM3_SUMMARY_CACHE is not None:
        return _MEM3_SUMMARY_CACHE
    from pathlib import Path as _Path
    p = _Path(path)
    if not p.exists():
        _MEM3_SUMMARY_CACHE = {}
        return _MEM3_SUMMARY_CACHE
    try:
        import json as _json
        _MEM3_SUMMARY_CACHE = _json.loads(p.read_text(encoding='utf-8'))
    except Exception:
        _MEM3_SUMMARY_CACHE = {}
    return _MEM3_SUMMARY_CACHE

def physics_micrometeorite_flux(day_of_year=None, shower_factor=1.0, lat=None,
                                use_mem3: bool = True, include_showers: bool = True):
    import time as _time
    avg = 1.6
    mem3_meta = None
    if use_mem3:
        summary = load_mem3_flux_summary()
        proxy = (summary or {}).get('proxy') or {}
        if proxy.get('baseline_flux_1e15') is not None:
            try:
                avg = float(proxy['baseline_flux_1e15'])
                mem3_meta = proxy
            except Exception:
                avg = 1.6
    if day_of_year is None:
        day_of_year = int(_time.strftime('%j', _time.gmtime()))
    doy = float(day_of_year) % 365.0

    phase = 0.5 + 0.5 * np.sin(2 * np.pi * ((doy - 80.0) / 365.0))
    flux = avg * (1.0 + 0.14 * (phase - 0.5) * 2.0)
    if mem3_meta:
        try:
            hi = float(mem3_meta.get('hi_flux_1e15', avg * 1.3))
            lo = float(mem3_meta.get('lo_flux_1e15', avg * 0.7))
            flux = lo + (hi - lo) * phase
        except Exception:
            pass
    shower = 1.0
    if include_showers and float(shower_factor) != 0.0:
        for peak_doy, factor in _METEOR_SHOWER_PEAKS:
            dist = min(abs(doy - peak_doy), 365.0 - abs(doy - peak_doy))
            shower = max(shower, 1.0 + (factor - 1.0) * np.exp(-0.5 * (dist / 3.5) ** 2))
        flux *= shower * float(shower_factor)
    if lat is not None:

        lat_fac = 1.0 + 0.05 * (1.0 - abs(float(lat)) / 90.0)
        if mem3_meta and mem3_meta.get('zenith_hi_flux_1e15') and mem3_meta.get('nadir_hi_flux_1e15'):
            try:
                z = float(mem3_meta['zenith_hi_flux_1e15'])
                n = float(mem3_meta['nadir_hi_flux_1e15'])
                polar = abs(float(lat)) / 90.0
                zn = z / max(n, 1e-6)
                lat_fac *= (1.0 - 0.06 * polar) + 0.06 * polar * float(clamp(zn / 10.0, 0.8, 1.2, 1.0))
                lat_fac = float(clamp(lat_fac, 0.88, 1.20, 1.0))
            except Exception:
                pass
        flux *= lat_fac
    return float(clamp(flux, 0.8, 6.0, avg))

def physics_dust(micrometeorite_flux, lat=None, local_time=None, ldex_factor=1.0,
                 regolith_depth=None):
    base = 1.5
    dust = base + 0.10 * (float(micrometeorite_flux) - 1.6)
    if lat is not None:
        lat_r = np.radians(float(clamp(float(lat), -90.0, 90.0, 0.0)))

        lat_term = 0.06 * np.sin(2.0 * abs(lat_r)) - 0.04 * (abs(np.sin(lat_r)) ** 2)
        dust += lat_term
    if local_time is not None:
        hour = float(local_time) % 24.0

        dist_sr = min(abs(hour - 6.0), 24.0 - abs(hour - 6.0))
        dist_ss = min(abs(hour - 18.0), 24.0 - abs(hour - 18.0))
        near = min(dist_sr, dist_ss)
        dust += 0.12 * max(0.0, 1.0 - near / 3.0)

    dust *= float(clamp(ldex_factor, 0.55, 1.85, 1.0))
    if regolith_depth is not None:

        dust *= 1.0 + 0.015 * (float(regolith_depth) - 5.0)
    return float(clamp(dust, 0.5, 6.0, base))

PSE_NETWORK_AVG_MOONQUAKES_PER_DAY = 28.0 + 3.0 + 15.0

def physics_moonquake_rate(lat=None, local_time=None, regolith_depth=None):
    base = float(PSE_NETWORK_AVG_MOONQUAKES_PER_DAY)
    thermal = 0.0
    if local_time is not None:
        hour = float(local_time) % 24.0
        dist_sunrise = min(abs(hour - 6.0), 24.0 - abs(hour - 6.0))
        dist_sunset = min(abs(hour - 18.0), 24.0 - abs(hour - 18.0))
        near = min(dist_sunrise, dist_sunset)
        thermal = 10.0 * max(0.0, 1.0 - near / 4.0)
    lat_term = 0.0
    if lat is not None:

        lat_term = 3.0 * (1.0 - abs(float(lat)) / 90.0)
    reg_term = 0.0
    if regolith_depth is not None:

        reg_term = 0.35 * (float(regolith_depth) - 5.0)
    return float(clamp(base - 5.0 + thermal + lat_term + reg_term, 12.0, 80.0, base))

def calc_gcr_radiation(solar_mod=1.0):
    base_daily_mSv = 0.38
    base_hourly = base_daily_mSv / 24.0

    sm = max(0.5, min(1.5, solar_mod))
    return base_hourly * (1.0 / sm)

def detect_storm_regime(solar_activity=5.0, kp=3.0, radiation=0.057, imf_bz=-2.0) -> dict:
    """Classify quiet / unsettled / storm for adaptive hybrid blending."""
    sa = float(solar_activity)
    kp = float(kp)
    rad = float(radiation)
    bz = float(imf_bz)
    score = 0.0
    score += max(0.0, kp - 3.0) * 0.35
    score += max(0.0, sa - 10.0) * 0.08
    score += max(0.0, rad - 0.08) * 8.0
    score += max(0.0, -bz - 3.0) * 0.12
    if score < 0.8:
        level = 'quiet'
    elif score < 2.2:
        level = 'unsettled'
    else:
        level = 'storm'
    return {'level': level, 'score': float(score)}
