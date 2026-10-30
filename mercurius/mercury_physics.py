from __future__ import annotations

import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from lunar_physics import (
    SIGMA_SB,
    SOLAR_CONSTANT_1AU_W_M2,
    calc_gcr_radiation,
    clamp,
    detect_storm_regime,
    normalize_proton_flux,
    physics_solar_activity as _lipas_solar_activity,
)

MERCURY_A_AU = 0.387098
MERCURY_E = 0.20563
MERCURY_PERIHELION_AU = MERCURY_A_AU * (1.0 - MERCURY_E)
MERCURY_APHELION_AU = MERCURY_A_AU * (1.0 + MERCURY_E)
MERCURY_PERIOD_D = 87.969
MERCURY_SIDEREAL_DAY_D = 58.646
MERCURY_SOLAR_DAY_D = 175.938
MERCURY_RADIUS_KM = 2439.7
MERCURY_BOND_ALBEDO = 0.088
MERCURY_EMISSIVITY = 0.9
AU_KM = 149597870.7
M_PROTON_KG = 1.6726219e-27
SOLAR_ROT_OMEGA = 2.865e-06

_J2000 = datetime(2000, 1, 1, 12, tzinfo=timezone.utc)
_M0_DEG = 174.796
_N_DEG_D = 4.092317

_TERRAIN = {
    "smooth_plains": {"albedo": 0.08, "emissivity": 0.9, "thermal_lag_h": 0.7},
    "intercrater": {"albedo": 0.1, "emissivity": 0.91, "thermal_lag_h": 0.65},
    "polar": {"albedo": 0.12, "emissivity": 0.93, "thermal_lag_h": 1.2},
    "hollows": {"albedo": 0.14, "emissivity": 0.89, "thermal_lag_h": 0.35},
    "chaotic": {"albedo": 0.11, "emissivity": 0.91, "thermal_lag_h": 0.55},
    "ray_crater": {"albedo": 0.18, "emissivity": 0.9, "thermal_lag_h": 0.5},
    "tectonic": {"albedo": 0.1, "emissivity": 0.91, "thermal_lag_h": 0.8},
}
_TERRAIN_ALIAS = {
    "weird": "chaotic",
    "lineated": "chaotic",
    "hilly": "chaotic",
    "rayed": "ray_crater",
    "rays": "ray_crater",
    "scarp": "tectonic",
    "rupes": "tectonic",
    "lobate": "tectonic",
}


def _days_since_j2000(when: datetime | None = None) -> float:
    if not when:
        when = datetime.now(timezone.utc)
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return (when - _J2000).total_seconds() / 86400.0


def kepler_eccentric_anomaly(M: float, e: float, iters: int = 16) -> float:
    E = float(M)
    for _ in range(iters):
        f = E - e * math.sin(E) - M
        fp = 1.0 - e * math.cos(E)
        if abs(fp) < 1e-15:
            return E
        d = f / fp
        E -= d
        if abs(d) < 1e-14:
            return E
    return E


def mercury_r_au_kepler(when: datetime | None = None) -> float:
    days = _days_since_j2000(when)
    M = math.radians((_M0_DEG + _N_DEG_D * days) % 360.0)
    E = kepler_eccentric_anomaly(M, MERCURY_E)
    r = MERCURY_A_AU * (1.0 - MERCURY_E * math.cos(E))
    return float(clamp(r, MERCURY_PERIHELION_AU * 0.98, MERCURY_APHELION_AU * 1.02, MERCURY_A_AU))


def mercury_r_au(day_of_year: float | None = None, when: datetime | None = None) -> float:
    try:
        from mercurius.data_ingestion import horizons_r_au
        cached = horizons_r_au(when)
        if cached is not None:
            return float(cached)
    except Exception:
        pass
    if when is None and day_of_year is not None:
        from datetime import timedelta
        now = datetime.now(timezone.utc)
        when = datetime(now.year, 1, 1, tzinfo=timezone.utc) + timedelta(days=float(day_of_year) - 1.0)
    return mercury_r_au_kepler(when)


def solar_constant_mercury(r_au: float) -> float:
    r = max(float(r_au), 0.25)
    return float(SOLAR_CONSTANT_1AU_W_M2 / (r * r))


def parker_spiral_angle_rad(r_au: float, v_kms: float = 400.0) -> float:
    r_m = max(float(r_au), 0.2) * AU_KM * 1000.0
    v = max(float(v_kms), 200.0) * 1000.0
    return float(math.atan(SOLAR_ROT_OMEGA * r_m / v))


def scale_solar_wind_to_mercury(
    speed_1au: float,
    density_1au: float,
    imf_bz_1au: float,
    r_au: float,
    imf_by_1au: float | None = None,
    imf_bt_1au: float | None = None,
):
    r = max(float(r_au), 0.25)
    n = float(density_1au) / (r * r)
    v = float(speed_1au)
    bz_1 = float(imf_bz_1au)
    bz = bz_1 / r
    phi = parker_spiral_angle_rad(r, v)
    by_1 = float(imf_by_1au) if imf_by_1au is not None else None
    if imf_bt_1au is not None:
        try:
            b_mag_1au = max(abs(bz_1), float(imf_bt_1au))
        except (TypeError, ValueError):
            b_mag_1au = None
    else:
        b_mag_1au = None
    if b_mag_1au is None:
        perp = math.hypot(by_1 if by_1 is not None else 0.0, bz_1)
        b_mag_1au = max(3.2, perp * 1.12, abs(bz_1))
    br_scale = 1.0 / (r * r)
    bt_scale = 1.0 / r
    b_mag = b_mag_1au * math.sqrt(
        (math.cos(phi) * br_scale) ** 2 + (math.sin(phi) * bt_scale) ** 2
    )
    if by_1 is not None:
        by = by_1 / r
    else:
        residual = max(0.0, b_mag * b_mag - bz * bz)
        by = -math.sqrt(residual)
    return {
        "speed": float(v),
        "density": float(n),
        "imf_bz": float(bz),
        "imf_by": float(by),
        "imf_b_mag": float(b_mag),
        "spiral_deg": float(math.degrees(phi)),
        "r_au": float(r),
    }


def dynamic_pressure_npa(density_cm3: float, speed_kms: float) -> float:
    n = max(float(density_cm3), 0.05)
    v = max(float(speed_kms), 200.0)
    return float(1.6726e-06 * n * v * v)


def physics_temperature_mercury(
    lat,
    lon,
    local_time,
    r_au=None,
    day_of_year=None,
    albedo=None,
    emissivity=None,
    terrain=None,
    when=None,
):
    if r_au is None:
        r_au = mercury_r_au(day_of_year, when=when)
    lat_rad = np.radians(float(clamp(float(lat), -90.0, 90.0, 0.0)))
    hour = float(local_time) % 24.0
    hour_angle = np.pi * (hour - 12.0) / 12.0
    cos_i = float(np.cos(lat_rad) * max(0.0, np.cos(hour_angle)))
    key = str(terrain or "intercrater").lower().replace(" ", "_")
    key = _TERRAIN_ALIAS.get(key, key)
    base = _TERRAIN.get(key, _TERRAIN["intercrater"])
    a = float(albedo) if albedo is not None else float(base["albedo"])
    e = float(emissivity) if emissivity is not None else float(base["emissivity"])
    tau = float(base.get("thermal_lag_h") or 0.65)
    s = solar_constant_mercury(r_au)
    polar = abs(float(lat)) >= 80.0
    dayside = 6.0 <= hour <= 18.0 and cos_i > 1e-05
    if polar and cos_i < 0.08:
        temp_c = -210.0 + 15.0 * cos_i
    elif dayside:
        temp_eq_k = (
            s * (1.0 - a) * max(cos_i, 0.0001) / (e * SIGMA_SB)
        ) ** 0.25
        hours_after_sunrise = hour - 6.0
        ramp = 1.0 - math.exp(-max(hours_after_sunrise, 0.0) / max(tau, 0.15))
        floor_k = 100.0 + 18.0 * abs(math.sin(lat_rad))
        temp_k = floor_k + (temp_eq_k - floor_k) * (0.18 + 0.82 * ramp)
        temp_c = float(temp_k - 273.15)
    else:
        if hour >= 18.0:
            hours_after_sunset = hour - 18.0
        else:
            hours_after_sunset = hour + 6.0
        frac = float(clamp(hours_after_sunset / 12.0, 0.0, 1.0, 1.0))
        floor_k = 100.0 + 18.0 * abs(math.sin(lat_rad))
        sunset_k = 250.0 + 40.0 * abs(math.sin(lat_rad))
        temp_k = sunset_k + (floor_k - sunset_k) * (frac ** 0.55)
        temp_c = float(temp_k - 273.15)
    return float(clamp(temp_c, -220.0, 460.0, temp_c))


def physics_solar_activity_mercury(
    solar_activity=5.0,
    kp=3.0,
    imf_bz=-2.0,
    solar_wind_speed=400.0,
    solar_wind_density=5.0,
    r_au=0.387,
    f107=None,
):
    scaled = scale_solar_wind_to_mercury(solar_wind_speed, solar_wind_density, imf_bz, r_au)
    base = _lipas_solar_activity(
        solar_activity=solar_activity,
        kp=kp,
        imf_bz=scaled["imf_bz"],
        solar_wind_speed=scaled["speed"],
        solar_wind_density=scaled["density"],
        f107=f107,
    )
    flux_scale = 1.0 / max(r_au * r_au, 0.08)
    out = 0.5 * base + 0.5 * base * math.sqrt(min(flux_scale, 12.0))
    return float(clamp(out, 0.0, 160.0, base))


def physics_radiation_mercury(
    solar_activity=5.0,
    kp=3.0,
    proton_flux=1.0,
    lat=None,
    imf_bz=None,
    solar_wind_speed=None,
    r_au=0.387,
    magnetopause_rm=None,
    local_time=12.0,
):
    sa = float(solar_activity)
    kp = float(kp)
    pf_raw = float(proton_flux)
    pf = normalize_proton_flux(pf_raw) if pf_raw > 4.0 else pf_raw
    r = max(float(r_au), 0.25)
    solar_mod = max(0.55, min(1.45, sa / 8.0))
    gcr_1au = calc_gcr_radiation(solar_mod=solar_mod)
    gcr = gcr_1au * (r ** 0.45)
    quiet = 0.016
    storm = 0.0
    if kp > 2.0:
        storm += 0.007 * (kp - 2.0)
    if imf_bz is not None and float(imf_bz) < -5.0:
        storm += 0.01 * min(3.5, ( -float(imf_bz) - 5.0) / 5.0)
    if solar_wind_speed is not None and float(solar_wind_speed) > 600.0:
        storm += 0.005 * min(2.5, (float(solar_wind_speed) - 600.0) / 200.0)
    storm *= 1.0 / r
    sep = 0.0
    if pf > 0.15:
        sep += 0.005 + 0.034 * pf
    if sa > 12.0:
        sep += 0.014 * (sa - 12.0) / 10.0
    sep *= 1.0 / (r * r)
    rad = gcr + quiet + storm + sep
    hour = float(local_time) % 24.0
    dayside = 6.0 <= hour <= 18.0
    rss = float(magnetopause_rm) if magnetopause_rm is not None else 1.45
    if rss <= 1.05 and dayside:
        shield = 1.12
    elif rss <= 1.2 and dayside:
        shield = 1.04
    elif dayside:
        shield = 0.92
    else:
        shield = 0.78
    if lat is not None:
        abs_lat = abs(float(lat)) / 90.0
        cusp = math.exp(-0.5 * ((abs(float(lat)) - 38.0) / 12.0) ** 2)
        if dayside:
            shield *= 1.0 + 0.18 * cusp
        rad *= 1.0 + 0.06 * (abs_lat ** 2)
    rad *= shield
    return float(clamp(rad, 0.008, 30.0, 0.12))


def earth_lead_time_hours(r_au: float, solar_wind_speed_kms: float = 400.0) -> dict:
    r_m = max(float(r_au), 0.25)
    v = max(float(solar_wind_speed_kms), 200.0)
    t_merc_h = r_m * AU_KM / v / 3600.0
    t_earth_h = 1.0 * AU_KM / v / 3600.0
    return {
        "r_au": r_m,
        "solar_wind_transit_mercury_h": round(t_merc_h, 3),
        "solar_wind_transit_earth_h": round(t_earth_h, 3),
        "lead_time_h": round(t_earth_h - t_merc_h, 3),
        "photon_lead_min": round((1.0 - r_m) * 8.317, 3),
        "note": "1 AU OMNI in-situ is a radial proxy, not a ballistic map of the parcel currently at Mercury. Flares/X-rays (GOES) are near-simultaneous (light).",
    }


def mercury_subsolar(when: datetime | None = None) -> dict:
    if not when:
        when = datetime.now(timezone.utc)
    days = _days_since_j2000(when)
    spin = 360.0 * days / MERCURY_SIDEREAL_DAY_D
    orbit = 360.0 * days / MERCURY_PERIOD_D
    lon = (orbit - spin) % 360.0
    if lon > 180.0:
        lon -= 360.0
    return {"lon": round(float(lon), 3), "lat": 0.0}


def local_solar_time_mercury(lon_deg: float, when: datetime | None = None) -> float:
    sub = mercury_subsolar(when)
    rel = (float(lon_deg) - sub["lon"] + 180.0) % 360.0 - 180.0
    lst = 12.0 + rel / 15.0
    return float(lst % 24.0)


def physics_estimate_mercury(inputs, lat=0.0, lon=0.0, local_time=12.0, day_of_year=None, extra=None, when=None) -> dict:
    if not extra:
        extra = {}
    solar = float(inputs[0]) if inputs else 5.0
    rad_in = float(inputs[1]) if inputs and len(inputs) > 1 else 0.06
    r_au = float(extra.get("r_au") or mercury_r_au(day_of_year, when=when))
    kp = float(extra.get("kp_index", extra.get("kp", 3.0)))
    bz_1au = float(extra.get("imf_bz", -2.0))
    v_1au = float(extra.get("solar_wind_speed", 400.0))
    n_1au = float(extra.get("solar_wind_density", 5.0))
    proton = extra.get("proton_flux")
    if proton is not None:
        proton = float(proton)
    else:
        proton = max(1.0, rad_in * 40.0)
    bt_1au = extra.get("imf_bt") or extra.get("imf_b_mag")
    try:
        bt_1au = float(bt_1au) if bt_1au is not None else None
    except (TypeError, ValueError):
        bt_1au = None
    sw = scale_solar_wind_to_mercury(
        v_1au, n_1au, bz_1au, r_au,
        extra.get("imf_by"),
        imf_bt_1au=bt_1au,
    )
    p_dyn = dynamic_pressure_npa(sw["density"], sw["speed"])
    from mercurius.mercury_magnetosphere import magnetopause_standoff_rm
    rss = magnetopause_standoff_rm(p_dyn, imf_bz_nt=sw["imf_bz"])
    phys_solar = physics_solar_activity_mercury(
        solar_activity=solar,
        kp=kp,
        imf_bz=bz_1au,
        solar_wind_speed=v_1au,
        solar_wind_density=n_1au,
        r_au=r_au,
        f107=extra.get("f107"),
    )
    phys_rad = physics_radiation_mercury(
        solar_activity=solar,
        kp=kp,
        proton_flux=proton,
        lat=lat,
        imf_bz=sw["imf_bz"],
        solar_wind_speed=sw["speed"],
        r_au=r_au,
        magnetopause_rm=rss,
        local_time=local_time,
    )
    phys_temp = physics_temperature_mercury(
        lat, lon, local_time,
        r_au=r_au,
        day_of_year=day_of_year,
        albedo=extra.get("albedo"),
        emissivity=extra.get("emissivity"),
        terrain=extra.get("terrain"),
        when=when,
    )
    lead = earth_lead_time_hours(r_au, v_1au)
    regime = detect_storm_regime(phys_solar, kp, phys_rad, sw["imf_bz"])
    return {
        "solar": phys_solar,
        "radiation": phys_rad,
        "temperature": phys_temp,
        "r_au": r_au,
        "solar_constant_w_m2": solar_constant_mercury(r_au),
        "wind_mercury": sw,
        "p_dyn_npa": p_dyn,
        "magnetopause_rm": rss,
        "lead_time": lead,
        "regime": regime,
        "kp_index": kp,
        "f107": extra.get("f107"),
        "proton_flux": proton,
    }
