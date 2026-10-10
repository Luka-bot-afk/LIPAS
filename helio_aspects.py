from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any

LUNAR_PHASE_REFERENCE = datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc)
LUNAR_SYNODIC_DAYS = 29.530588853
LUNAR_OBLIQUITY_DEG = 1.54
J2000 = datetime(2000, 1, 1, 12, tzinfo=timezone.utc)

CARRINGTON_DEG_PER_HOUR = 13.2 / 24.0

_PLANETS = (
    ("mercury", "Mercury", 0.387, 252.250906, 4.0923344368, 7.004979, 48.330766),
    ("venus", "Venus", 0.723, 181.979801, 1.602130357, 3.394676, 76.679843),
    ("earth", "Earth", 1.000, 100.464571, 0.985647352, 0.000000, 0.000000),
    ("mars", "Mars", 1.524, 355.433275, 0.5240206819, 1.849691, 49.559539),
    ("jupiter", "Jupiter", 5.204, 34.396441, 0.083085300, 1.304397, 100.473909),
    ("saturn", "Saturn", 9.583, 49.954244, 0.033444228, 2.485992, 113.662424),
)

def wrap_lon(lon: float) -> float:
    x = float(lon)
    while x > 180.0:
        x -= 360.0
    while x < -180.0:
        x += 360.0
    return x

def _as_utc(when: datetime | None) -> datetime:
    when = when or datetime.now(timezone.utc)
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return when.astimezone(timezone.utc)

def days_since_j2000(when: datetime | None = None) -> float:
    return (_as_utc(when) - J2000).total_seconds() / 86400.0

def instant_from_utc_hour(utc_hour: float, when: datetime | None = None) -> datetime:

    now = _as_utc(when)
    base = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return base + timedelta(hours=float(utc_hour) % 24.0)

def lunar_phase_fraction(when: datetime | None = None) -> float:
    days = (_as_utc(when) - LUNAR_PHASE_REFERENCE).total_seconds() / 86400.0
    return days / LUNAR_SYNODIC_DAYS % 1.0

def lunar_phase_name(fraction: float) -> str:
    f = float(fraction) % 1.0
    if f < 0.03 or f >= 0.97:
        return "new"
    if f < 0.22:
        return "waxing crescent"
    if f < 0.28:
        return "first quarter"
    if f < 0.47:
        return "waxing gibbous"
    if f < 0.53:
        return "full"
    if f < 0.72:
        return "waning gibbous"
    if f < 0.78:
        return "last quarter"
    return "waning crescent"

def lunar_subsolar(when: datetime | None = None) -> dict[str, float]:

    when = _as_utc(when)
    frac = lunar_phase_fraction(when)
    lon = wrap_lon(180.0 - 360.0 * frac)
    doy = when.timetuple().tm_yday + when.hour / 24.0
    lat = LUNAR_OBLIQUITY_DEG * math.sin(2.0 * math.pi * (doy - 81.0) / 365.25)
    return {"lon": round(lon, 3), "lat": round(lat, 3)}

def lunar_local_solar_time(lon_deg: float, when: datetime | None = None) -> float:
    sub = lunar_subsolar(when)
    rel = wrap_lon(float(lon_deg) - sub["lon"])
    return (12.0 + rel / 15.0) % 24.0

def cosine_incidence(lat_deg: float, lon_deg: float, sub_lat: float, sub_lon: float) -> float:
    la = math.radians(float(lat_deg))
    sla = math.radians(float(sub_lat))
    dlon = math.radians(wrap_lon(float(lon_deg) - float(sub_lon)))
    mu = math.sin(la) * math.sin(sla) + math.cos(la) * math.cos(sla) * math.cos(dlon)
    return max(0.0, min(1.0, mu))

def planet_aspects(when: datetime | None = None) -> list[dict[str, Any]]:

    d = days_since_j2000(when)
    longs: dict[str, float] = {}
    lats: dict[str, float] = {}
    aus: dict[str, float] = {}
    for pid, _name, a, l0, n, inc, omega in _PLANETS:
        L = (l0 + n * d) % 360.0
        longs[pid] = L
        lats[pid] = inc * math.sin(math.radians(L - omega))
        aus[pid] = a
    earth_l = longs["earth"]
    out = []
    for pid, name, a, _l0, _n, _inc, _omega in _PLANETS:
        lon = wrap_lon(longs[pid] - earth_l)
        out.append({
            "id": pid,
            "name": name,
            "lon": round(lon, 2),
            "lat": round(lats[pid], 2),
            "r_au": a,
            "earth_facing": pid == "earth",
        })
    return out

def mercury_subsolar(when: datetime | None = None) -> dict[str, float]:
    from mercurius.mercury_physics import mercury_subsolar as _ms
    return _ms(when)

def globe_clock(body: str, hour: float = 0.0, when: datetime | None = None) -> dict[str, Any]:

    body = str(body or "moon").strip().lower()
    if body in ("solar", "photosphere"):
        body = "sun"
    if body in ("luna", "lunar"):
        body = "moon"
    h = max(0.0, min(24.0, float(hour)))
    instant = _as_utc(when) + timedelta(hours=h)
    utc = instant.strftime("%Y-%m-%dT%H:%M:%SZ")

    drivers: dict[str, Any] = {}
    try:
        from data_ingestion import load_serve_space_drivers
        from swpc_nowcast import drivers_at_hour
        extra = load_serve_space_drivers()
        extra = drivers_at_hour(extra, h)
        for key in (
            "solar_activity", "kp_index", "flare_class", "flare_index", "xray_flux",
            "proton_flux", "f107", "imf_bz", "solar_wind_speed",
        ):
            if extra.get(key) is not None:
                drivers[key] = extra.get(key)
        drivers["goes_class"] = extra.get("flare_class")
        drivers["kp"] = extra.get("kp_index")
    except Exception:
        extra = {}

    payload: dict[str, Any] = {
        "body": body,
        "hour": h,
        "utc": utc,
        "subsolar": {"lon": 0.0, "lat": 0.0},
        "planets": [],
        "carrington_deg": round(CARRINGTON_DEG_PER_HOUR * h, 3),
        "carrington_deg_per_hour": CARRINGTON_DEG_PER_HOUR,
        "drivers": drivers,
    }

    if body == "moon":
        sub = lunar_subsolar(instant)
        frac = lunar_phase_fraction(instant)
        payload["subsolar"] = sub
        payload["phase"] = {
            "fraction": round(frac, 4),
            "name": lunar_phase_name(frac),
            "illuminated": round(0.5 * (1.0 - math.cos(2.0 * math.pi * frac)), 3),
        }
        payload["note"] = (
            "Solar / temperature overlays follow the selenographic subsolar point. "
            "New moon lights the far side; full moon lights the near side."
        )
    elif body == "mercury":
        try:
            payload["subsolar"] = mercury_subsolar(instant)
        except Exception:
            payload["subsolar"] = {"lon": 0.0, "lat": 0.0}
        payload["note"] = (
            "Mercury solar day is ~176 Earth days, so 24h mostly moves space weather, not the terminator."
        )
    elif body in ("earth", "terra"):
        payload["body"] = "earth"
        doy = instant.timetuple().tm_yday
        decl = 23.44 * math.sin(2.0 * math.pi * (doy - 81) / 365.25)
        utc_h = instant.hour + instant.minute / 60.0 + instant.second / 3600.0
        lon = 15.0 * (12.0 - utc_h)
        while lon > 180.0:
            lon -= 360.0
        while lon < -180.0:
            lon += 360.0
        payload["subsolar"] = {"lon": round(lon, 3), "lat": round(decl, 3)}
        payload["note"] = "Earth lighting follows the subsolar point. Satellites are Kepler-propagated from Celestrak."
    else:
        payload["body"] = "sun"
        payload["subsolar"] = {"lon": 0.0, "lat": 0.0}
        payload["planets"] = planet_aspects(instant)
        payload["note"] = (
            "Lon 0 faces Earth (central meridian). Active regions drift ~13.2°/day with Carrington rotation."
        )
    return payload
