from __future__ import annotations

import json
import math
import os
import time
from concurrent.futures import ThreadPoolExecutor, wait
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

ROOT = Path(__file__).resolve().parent
ARCH = ROOT / "data" / "archives"

_REFRESH_TS = 0.0
_REFRESH_LOCK_TS = 0.0
_REFRESH_TTL_S = 15 * 60.0

SWPC_FILES = {
    "goes_xrays_1day.json": "https://services.swpc.noaa.gov/json/goes/primary/xrays-1-day.json",
    "goes_xrays_7day.json": "https://services.swpc.noaa.gov/json/goes/primary/xrays-7-day.json",
    "goes_integral_protons_1day.json": "https://services.swpc.noaa.gov/json/goes/primary/integral-protons-1-day.json",
    "planetary_k_index_1m.json": "https://services.swpc.noaa.gov/json/planetary_k_index_1m.json",
    "noaa_planetary_k_index.json": "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json",
    "f107_cm_flux.json": "https://services.swpc.noaa.gov/json/f107_cm_flux.json",
    "solar_regions.json": "https://services.swpc.noaa.gov/json/solar_regions.json",
    "solar_wind_mag_1day.json": "https://services.swpc.noaa.gov/json/rtsw/rtsw_mag_1d.json",
    "solar_wind_plasma_1day.json": "https://services.swpc.noaa.gov/json/rtsw/rtsw_wind_1d.json",
    "kp_index_forecast.json": "https://services.swpc.noaa.gov/products/noaa-planetary-k-index-forecast.json",
}

_UA = {"User-Agent": "LIPAS/3.0 (space-weather-ops)"}

def _skip_refresh() -> bool:
    flag = (os.environ.get("LIPAS_SKIP_SWPC_REFRESH") or "").strip().lower()
    return flag in ("1", "true", "yes", "on")

def parse_utc(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    text = text.replace("Z", "+00:00")
    if " " in text and "T" not in text:
        text = text.replace(" ", "T", 1)
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(text[:19], fmt)
                break
            except ValueError:
                dt = None
        if dt is None:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def hours_from_now(dt: Optional[datetime], now: Optional[datetime] = None) -> Optional[float]:
    if dt is None:
        return None
    now = now or datetime.now(timezone.utc)
    return (dt - now).total_seconds() / 3600.0

def flare_class_from_flux(flux: float) -> tuple[str, float]:

    f = float(flux)
    if not math.isfinite(f) or f <= 0:
        return "A0.0", 0.0
    if f >= 1e-4:
        letter, scale = "X", f / 1e-4
    elif f >= 1e-5:
        letter, scale = "M", f / 1e-5
    elif f >= 1e-6:
        letter, scale = "C", f / 1e-6
    elif f >= 1e-7:
        letter, scale = "B", f / 1e-7
    else:
        letter, scale = "A", max(f / 1e-8, 0.1)
    idx = float(min(10.0, max(0.0, math.log10(f) + 8.0)))
    return f"{letter}{scale:.1f}", idx

def interp_series(
    points: Iterable[tuple[float, float]],
    hour: float,
    *,
    persist: bool = True,
    tau_h: Optional[float] = None,
    background: Optional[float] = None,
) -> Optional[float]:

    pts = [
        (float(t), float(v))
        for t, v in points
        if v is not None and math.isfinite(float(v)) and math.isfinite(float(t))
    ]
    if not pts:
        return None
    pts.sort(key=lambda p: p[0])
    h = float(hour)
    if h <= pts[0][0]:
        return pts[0][1] if persist else None
    if h <= pts[-1][0]:
        for i in range(1, len(pts)):
            t0, v0 = pts[i - 1]
            t1, v1 = pts[i]
            if h <= t1:
                if abs(t1 - t0) < 1e-9:
                    return v1
                w = (h - t0) / (t1 - t0)
                return v0 + w * (v1 - v0)
        return pts[-1][1]
    last_t, last_v = pts[-1]
    if not persist:
        return None
    dt = max(0.0, h - last_t)
    if tau_h and tau_h > 0 and background is not None:
        return float(background + (last_v - background) * math.exp(-dt / tau_h))
    return last_v

def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None

def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    tmp.replace(path)

def _http_json(url: str, timeout: float = 8.0) -> Any:
    try:
        import requests
        r = requests.get(url, timeout=timeout, headers=_UA)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None

def refresh_swpc_archives(force: bool = False) -> dict[str, Any]:

    global _REFRESH_TS, _REFRESH_LOCK_TS
    now = time.time()
    if _skip_refresh() and not force:
        return {"skipped": True, "reason": "skip_flag"}
    if not force and (now - _REFRESH_TS) < _REFRESH_TTL_S:
        return {"skipped": True, "reason": "fresh", "age_s": now - _REFRESH_TS}
    if not force and (now - _REFRESH_LOCK_TS) < 20.0:
        return {"skipped": True, "reason": "lock"}
    _REFRESH_LOCK_TS = now

    fetched: dict[str, Any] = {}

    def _one(name_url: tuple[str, str]) -> tuple[str, bool, str]:
        name, url = name_url
        data = _http_json(url, timeout=8.0)
        if data is None:
            return name, False, "empty"
        if isinstance(data, list) and len(data) == 0:
            return name, False, "empty-list"
        try:
            _atomic_write_json(ARCH / name, data)
            n = len(data) if isinstance(data, list) else 1
            return name, True, f"n={n}"
        except Exception as exc:
            return name, False, str(exc)

    try:
        items = list(SWPC_FILES.items())
        with ThreadPoolExecutor(max_workers=8) as pool:
            futs = [pool.submit(_one, item) for item in items]
            wait(futs, timeout=12.0)
            for fut in futs:
                if not fut.done():
                    continue
                try:
                    name, ok, detail = fut.result()
                    fetched[name] = {"ok": ok, "detail": detail}
                except Exception as exc:
                    fetched["error"] = str(exc)
        _REFRESH_TS = time.time()
    except Exception as exc:
        fetched["error"] = str(exc)
    return {"skipped": False, "files": fetched, "utc": datetime.now(timezone.utc).isoformat()}

def _as_rows(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, list) and raw:
        if isinstance(raw[0], dict):
            return [r for r in raw if isinstance(r, dict)]
        if isinstance(raw[0], list):
            header = [str(k) for k in raw[0]]
            out = []
            for rec in raw[1:]:
                if not isinstance(rec, list):
                    continue
                out.append({header[i]: rec[i] for i in range(min(len(header), len(rec)))})
            return out
    return []

def parse_swpc_location(location: Any, latitude: Any = None, longitude: Any = None) -> tuple[Optional[float], Optional[float]]:

    import re
    text = str(location or "").strip().upper()
    m = re.match(r"([NS])(\d+(?:\.\d+)?)([EW])(\d+(?:\.\d+)?)", text)
    if m:
        ns, la, ew, lo = m.group(1), float(m.group(2)), m.group(3), float(m.group(4))
        lat = -la if ns == "S" else la
        lon_stony = lo if ew == "W" else -lo
        return lat, lon_stony
    lat = _num(latitude)
    lon = _num(longitude)
    if lat is None or lon is None:
        return lat, lon

    return lat, lon

def _num(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        v = float(value)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None
    if value is None or value == "":
        return None
    try:
        v = float(value)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None

def _xray_points(now: datetime) -> list[tuple[float, float]]:
    pts: list[tuple[float, float]] = []
    for name in ("goes_xrays_1day.json", "goes_xrays_7day.json"):
        rows = _as_rows(_read_json(ARCH / name))
        long_ch = [
            r for r in rows
            if "0.1" in str(r.get("energy") or r.get("wavelength") or "")
        ]
        pool = long_ch or rows
        for r in pool:
            flux = _num(r.get("flux"))
            t = parse_utc(r.get("time_tag"))
            h = hours_from_now(t, now)
            if flux is None or h is None or flux <= 0:
                continue
            pts.append((h, flux))
        if pts:
            break
    pts.sort(key=lambda p: p[0])
    return pts

def _kp_points(now: datetime) -> list[tuple[float, float]]:
    pts: list[tuple[float, float]] = []
    rows = _as_rows(_read_json(ARCH / "planetary_k_index_1m.json"))
    for r in rows:
        kp = _num(r.get("estimated_kp"))
        if kp is None:
            kp = _num(r.get("kp_index"))
        if kp is None:
            kp = _num(r.get("Kp"))
        t = parse_utc(r.get("time_tag"))
        h = hours_from_now(t, now)
        if kp is None or h is None:
            continue
        pts.append((h, float(max(0.0, min(9.0, kp)))))

    three_hour = _as_rows(_read_json(ARCH / "noaa_planetary_k_index.json"))
    if three_hour:
        extra = []
        for r in three_hour:
            kp = _num(r.get("Kp") if "Kp" in r else r.get("kp_index"))
            t = parse_utc(r.get("time_tag"))
            h = hours_from_now(t, now)
            if kp is None or h is None:
                continue
            extra.append((h, float(max(0.0, min(9.0, kp)))))
        if extra:
            pts = extra
    pts.sort(key=lambda p: p[0])
    return pts

def _kp_forecast_points(now: datetime) -> list[tuple[float, float]]:
    raw = _read_json(ARCH / "kp_index_forecast.json")
    rows = _as_rows(raw)
    pts: list[tuple[float, float]] = []
    for r in rows:
        kp = None
        for key in ("kp", "Kp", "estimated_kp", "kp_index"):
            if key in r:
                kp = _num(r.get(key))
                if kp is not None:
                    break
        t = parse_utc(r.get("time_tag") or r.get("time"))
        h = hours_from_now(t, now)
        if kp is None or h is None:
            continue
        pts.append((h, float(max(0.0, min(9.0, kp)))))
    pts.sort(key=lambda p: p[0])
    return pts

def _proton_points(now: datetime) -> list[tuple[float, float]]:
    rows = _as_rows(_read_json(ARCH / "goes_integral_protons_1day.json"))
    prefer = [r for r in rows if "10" in str(r.get("energy") or "")]
    pool = prefer or rows
    pts: list[tuple[float, float]] = []
    for r in pool:
        flux = _num(r.get("flux"))
        t = parse_utc(r.get("time_tag"))
        h = hours_from_now(t, now)
        if flux is None or h is None:
            continue
        pts.append((h, max(0.0, flux)))
    pts.sort(key=lambda p: p[0])
    return pts

def _bin_hourly(points: list[tuple[float, float]], *, how: str = "last") -> list[tuple[float, float]]:
    if not points:
        return []
    buckets: dict[int, list[float]] = {}
    for t, v in points:
        buckets.setdefault(int(math.floor(t)), []).append(v)
    out = []
    for hour in sorted(buckets):
        vals = buckets[hour]
        if how == "max":
            val = max(vals)
        elif how == "mean":
            val = sum(vals) / max(len(vals), 1)
        else:
            val = vals[-1]
        out.append((float(hour) + 0.5, val))
    return out

def _rtsw_latest(now: datetime) -> dict[str, Any]:
    mag_rows = _as_rows(_read_json(ARCH / "solar_wind_mag_1day.json"))
    plasma_rows = _as_rows(_read_json(ARCH / "solar_wind_plasma_1day.json"))
    prefer = {"IMAP", "DSCOVR", "SOLAR1"}

    def _stamp(r: dict) -> Optional[float]:
        return hours_from_now(parse_utc(r.get("time_tag")), now)

    def _good_mag(r: dict) -> bool:
        if _num(r.get("bz_gsm") if "bz_gsm" in r else r.get("bz")) is None:
            return False
        q = r.get("overall_quality")
        if q not in (None, 0, "0"):
            return False
        return True

    def _good_plasma(r: dict) -> bool:
        v = _num(r.get("speed") or r.get("proton_speed"))
        n = _num(r.get("density") or r.get("proton_density"))
        if v is None or n is None:
            return False
        if not (220 <= v <= 1200 and 0.3 <= n <= 80):
            return False
        q = r.get("overall_quality")
        if q not in (None, 0, "0"):
            return False
        return True

    def _pick(rows: list, ok) -> list[dict]:
        recent = []
        for r in rows:
            h = _stamp(r)
            if h is None or h < -18.0 or not ok(r):
                continue
            recent.append((h, r))
        if not recent:
            return []

        near = [(h, r) for h, r in recent if h >= -4.0]
        pool = near or recent
        pref = [(h, r) for h, r in pool if str(r.get("source") or "").upper() in prefer]
        use = pref or pool
        use.sort(key=lambda x: x[0])
        return [r for _, r in use]

    mag_ok = _pick(mag_rows, _good_mag)
    plasma_ok = _pick(plasma_rows, _good_plasma)
    mag_pts = {"bz": [], "by": [], "bt": [], "bx": []}
    for r in mag_ok:
        h = _stamp(r)
        if h is None:
            continue
        bz = _num(r.get("bz_gsm") if "bz_gsm" in r else r.get("bz_gse") or r.get("bz"))
        by = _num(r.get("by_gsm") if "by_gsm" in r else r.get("by_gse") or r.get("by"))
        bx = _num(r.get("bx_gsm") if "bx_gsm" in r else r.get("bx_gse") or r.get("bx"))
        bt = _num(r.get("bt") or r.get("b_total") or r.get("btotal"))
        if bz is not None:
            mag_pts["bz"].append((h, bz))
        if by is not None:
            mag_pts["by"].append((h, by))
        if bx is not None:
            mag_pts["bx"].append((h, bx))
        if bt is not None:
            mag_pts["bt"].append((h, bt))
    plasma_pts = {"speed": [], "density": []}
    for r in plasma_ok:
        h = _stamp(r)
        if h is None:
            continue
        v = _num(r.get("speed") or r.get("proton_speed"))
        n = _num(r.get("density") or r.get("proton_density"))
        if v is not None:
            plasma_pts["speed"].append((h, v))
        if n is not None:
            plasma_pts["density"].append((h, n))

    out: dict[str, Any] = {}

    def _last(pts: list[tuple[float, float]]) -> Optional[tuple[float, float]]:
        if not pts:
            return None
        pts = sorted(pts, key=lambda p: p[0])
        return pts[-1]

    bz = _last(mag_pts["bz"])
    by = _last(mag_pts["by"])
    bx = _last(mag_pts["bx"])
    bt = _last(mag_pts["bt"])
    speed = _last(plasma_pts["speed"])
    dens = _last(plasma_pts["density"])
    ages = [p[0] for p in (bz, by, bt, speed, dens) if p is not None]
    if not ages:
        return out

    latest_t = max(ages)
    if latest_t < -18.0:
        return out
    if bz:
        out["imf_bz"] = bz[1]
    if by:
        out["imf_by"] = by[1]
    if bx:
        out["imf_bx"] = bx[1]
    if bt:
        out["imf_bt"] = bt[1]
    elif bz and by:
        bx_v = bx[1] if bx else 0.0
        out["imf_bt"] = math.sqrt(bx_v * bx_v + by[1] * by[1] + bz[1] * bz[1])
    if speed:
        out["solar_wind_speed"] = speed[1]
    if dens:
        out["solar_wind_density"] = dens[1]
    out["rtsw_age_hours"] = abs(latest_t)
    out["wind_source"] = "dscovr_rtsw"
    out["series_bz"] = _bin_hourly(mag_pts["bz"], how="mean")
    out["series_by"] = _bin_hourly(mag_pts["by"], how="mean")
    out["series_bt"] = _bin_hourly(mag_pts["bt"], how="mean")
    out["series_speed"] = _bin_hourly(plasma_pts["speed"], how="mean")
    out["series_density"] = _bin_hourly(plasma_pts["density"], how="mean")
    return out

def _region_probs() -> dict[str, Any]:
    rows = _as_rows(_read_json(ARCH / "solar_regions.json"))
    if not rows:
        return {}
    dates = [r.get("observed_date") for r in rows if r.get("observed_date")]
    latest = max(dates) if dates else None
    day = [r for r in rows if r.get("observed_date") == latest] if latest else list(rows)
    if not day:
        return {}
    def _p(key: str) -> float:
        vals = []
        for r in day:
            v = _num(r.get(key))
            if v is not None:
                vals.append(v)
        return max(vals) if vals else 0.0

    obs = parse_utc(latest)
    age_h = abs(hours_from_now(obs) or 999.0) if obs else 999.0
    return {
        "observed_date": latest,
        "count": len(day),
        "c_flare_probability": _p("c_flare_probability"),
        "m_flare_probability": _p("m_flare_probability"),
        "x_flare_probability": _p("x_flare_probability"),
        "proton_probability": _p("proton_probability"),
        "age_hours": age_h,
    }

def _omni_27d(now: datetime) -> dict[str, Any]:
    path = ARCH / "omni2_daily.csv"
    if not path.exists():
        return {}
    try:
        import pandas as pd
        df = pd.read_csv(path)
    except Exception:
        return {}
    if df.empty or "date" not in df.columns:
        return {}
    target = (now.date().toordinal() - 27)
    best = None
    best_d = 10**9
    rec = {}
    for _, row in df.iterrows():
        try:
            d = datetime.fromisoformat(str(row["date"])).date().toordinal()
        except Exception:
            continue
        delta = abs(d - target)
        speed = _num(row.get("solar_wind_speed"))
        dens = _num(row.get("solar_wind_density"))
        bz = _num(row.get("imf_bz"))
        if speed is None and dens is None and bz is None:
            continue
        if delta < best_d:
            best_d = delta
            best = row
    if best is None or best_d > 3:
        return rec
    rec["date"] = str(best.get("date"))
    rec["delta_days"] = int(best_d)
    for k in ("solar_wind_speed", "solar_wind_density", "imf_bz", "kp_index", "dst", "f107"):
        v = _num(best.get(k))
        if v is not None:
            rec[k] = v
    return rec

def attach_nowcast(out: dict[str, Any], now: Optional[datetime] = None) -> dict[str, Any]:

    now = now or datetime.now(timezone.utc)
    xray = _bin_hourly(_xray_points(now), how="max")
    kp_obs = _bin_hourly(_kp_points(now), how="last")
    kp_fcst = _kp_forecast_points(now)
    protons = _bin_hourly(_proton_points(now), how="last")
    rtsw = _rtsw_latest(now)
    regions = _region_probs()
    rec27 = _omni_27d(now)

    series = {
        "xray_flux": xray,
        "kp": kp_obs,
        "kp_forecast": kp_fcst,
        "proton_flux": protons,
        "imf_bz": rtsw.get("series_bz") or [],
        "imf_by": rtsw.get("series_by") or [],
        "imf_bt": rtsw.get("series_bt") or [],
        "solar_wind_speed": rtsw.get("series_speed") or [],
        "solar_wind_density": rtsw.get("series_density") or [],
    }
    out["series"] = series
    out["region_probs"] = regions
    out["omni_27d"] = rec27

    if rtsw.get("wind_source"):
        for k in (
            "solar_wind_speed", "solar_wind_density", "imf_bz", "imf_by",
            "imf_bx", "imf_bt",
        ):
            if rtsw.get(k) is not None:
                out[k] = rtsw[k]
        out["wind_source"] = "dscovr_rtsw"
        out["rtsw_age_hours"] = rtsw.get("rtsw_age_hours")
        if "dscovr_rtsw" not in (out.get("sources") or []):
            out.setdefault("sources", []).append("dscovr_rtsw")
    else:
        out.setdefault("wind_source", "omni2")

    if xray:
        flux = xray[-1][1]
        cls, idx = flare_class_from_flux(flux)
        out["xray_flux"] = flux
        out["flare_class"] = cls
        out["flare_index"] = idx
        out["xray_age_hours"] = abs(xray[-1][0])
        if "goes_xray" not in (out.get("sources") or []):
            out.setdefault("sources", []).append("goes_xray")

    kp_now = interp_series(kp_obs, 0.0, persist=True)
    if kp_now is None:
        kp_now = interp_series(kp_fcst, 0.0, persist=True)
    if kp_now is not None:
        out["kp_index"] = float(kp_now)
        if "swpc_kp" not in (out.get("sources") or []):
            out.setdefault("sources", []).append("swpc_kp")

    if protons:
        out["proton_flux_raw"] = protons[-1][1]
        try:
            from lunar_physics import normalize_proton_flux
            out["proton_flux"] = round(normalize_proton_flux(max(0.05, protons[-1][1])), 4)
        except Exception:
            out["proton_flux"] = max(0.05, protons[-1][1])
        out["proton_age_hours"] = abs(protons[-1][0])

    if regions.get("count"):
        out["solar_region_count"] = int(regions["count"])
        out["c_flare_probability"] = regions.get("c_flare_probability")
        out["m_flare_probability"] = regions.get("m_flare_probability")
        out["x_flare_probability"] = regions.get("x_flare_probability")
        out["proton_probability"] = regions.get("proton_probability")
        out["regions_observed_date"] = regions.get("observed_date")

    ages = []
    for key in ("xray_age_hours", "proton_age_hours", "rtsw_age_hours"):
        if out.get(key) is not None:
            ages.append(float(out[key]))
    if kp_obs:
        ages.append(abs(kp_obs[-1][0]))
    out["data_age_hours"] = round(min(ages), 3) if ages else None
    out["confidence"] = forecast_confidence(out, hour=0.0)
    return out

def forecast_confidence(drv: dict[str, Any], hour: float = 0.0) -> dict[str, Any]:
    h = max(0.0, float(hour))
    xray_age = float(drv.get("xray_age_hours") if drv.get("xray_age_hours") is not None else 48.0)
    kp_series = (drv.get("series") or {}).get("kp") or []
    kp_fcst = (drv.get("series") or {}).get("kp_forecast") or []
    kp_age = abs(kp_series[-1][0]) if kp_series else 48.0
    wind_src = str(drv.get("wind_source") or "")
    rtsw_age = float(drv.get("rtsw_age_hours") if drv.get("rtsw_age_hours") is not None else 48.0)
    region_age = float((drv.get("region_probs") or {}).get("age_hours") or 72.0)
    f107 = drv.get("f107")

    photon = 92.0 if xray_age <= 2 else (84.0 if xray_age <= 12 else (70.0 if xray_age <= 36 else 52.0))
    kp_pct = 90.0 if kp_age <= 4 else (80.0 if kp_age <= 12 else 58.0)
    if h > 0.5 and kp_fcst:
        kp_pct = min(88.0, kp_pct + 4.0)
    elif h > 0.5:
        kp_pct -= min(18.0, h * 0.55)
    if wind_src == "dscovr_rtsw" and rtsw_age <= 3:
        wind = 86.0
    elif wind_src == "dscovr_rtsw" and rtsw_age <= 12:
        wind = 76.0
    else:
        wind = 54.0
    wind -= min(22.0, h * 0.7)
    temp = 90.0
    rad = 0.55 * photon + 0.45 * wind
    solar = 0.6 * photon + 0.4 * kp_pct
    if f107 is not None:
        solar = min(94.0, solar + 3.0)
    if region_age <= 36:
        solar = min(94.0, solar + 3.0)
        photon = min(94.0, photon + 2.0)
    photon -= min(10.0, h * 0.25)
    overall = 0.34 * photon + 0.22 * kp_pct + 0.22 * wind + 0.12 * temp + 0.10 * rad
    overall = float(max(42.0, min(93.0, overall)))
    return {
        "overall_pct": round(overall, 1),
        "basis": " · ".join(
            s for s in (
                "goes_xray" if xray_age < 36 else None,
                "swpc_kp" if kp_age < 24 or kp_fcst else None,
                "dscovr_rtsw" if wind_src == "dscovr_rtsw" else "omni2_stale",
                "swpc_regions" if region_age < 48 else None,
            ) if s
        ) or "physics_persistence",
        "per_channel_pct": {
            "solar_activity": round(max(40.0, min(94.0, solar)), 1),
            "radiation_mSv": round(max(40.0, min(94.0, rad)), 1),
            "temperature_C": round(temp, 1),
            "kp": round(max(40.0, min(94.0, kp_pct)), 1),
            "flares": round(max(40.0, min(94.0, photon)), 1),
            "cme": round(max(38.0, min(90.0, 0.5 * kp_pct + 0.5 * photon - 4)), 1),
            "sep": round(max(38.0, min(90.0, rad - 4)), 1),
            "protons": round(max(40.0, min(92.0, photon - 2)), 1),
            "storm": round(max(40.0, min(90.0, kp_pct - 3)), 1),
        },
        "data_age_hours": drv.get("data_age_hours"),
        "wind_source": wind_src or "omni2",
    }

def drivers_at_hour(extra: dict[str, Any], hour: float) -> dict[str, Any]:

    out = dict(extra)
    h = float(hour)
    if h <= 0.05:
        out["confidence"] = forecast_confidence(extra, hour=0.0)
        return out
    series = extra.get("series") or {}
    rec27 = extra.get("omni_27d") or {}
    regions = extra.get("region_probs") or {}

    xray0 = extra.get("xray_flux")
    xray = interp_series(
        series.get("xray_flux") or [],
        h,
        persist=True,
        tau_h=4.0 if (xray0 and float(xray0) >= 1e-5) else 9.0,
        background=2.5e-7,
    )
    if xray is not None and xray > 0:

        if h > 0.25:
            p_m = float(regions.get("m_flare_probability") or extra.get("m_flare_probability") or 0.0)
            p_x = float(regions.get("x_flare_probability") or extra.get("x_flare_probability") or 0.0)
            p_c = float(regions.get("c_flare_probability") or extra.get("c_flare_probability") or 0.0)

            lift = 1.0 + 0.015 * (p_c / 100.0) + 0.08 * (p_m / 100.0) + 0.25 * (p_x / 100.0)
            xray = min(2e-3, xray * lift)
        cls, idx = flare_class_from_flux(xray)
        out["xray_flux"] = xray
        out["flare_class"] = cls
        out["flare_index"] = idx
        out["solar_activity"] = max(float(out.get("solar_activity") or 5.0), 4.0 + idx * 0.9)

    kp_obs = interp_series(series.get("kp") or [], h, persist=False)
    kp_fc = interp_series(series.get("kp_forecast") or [], h, persist=True)
    if h <= 0.05 and kp_obs is not None:
        out["kp_index"] = kp_obs
    elif kp_fc is not None and (kp_obs is None or h > 1.0):
        out["kp_index"] = kp_fc
    elif kp_obs is not None:
        out["kp_index"] = kp_obs
    elif h > 0.05:
        rec_kp = rec27.get("kp_index")
        cur_kp = extra.get("kp_index")
        if rec_kp is not None and cur_kp is not None:
            w = min(0.42, 0.035 * h)
            out["kp_index"] = (1.0 - w) * float(cur_kp) + w * float(rec_kp)
        rec_dst = rec27.get("dst")
        cur_dst = extra.get("dst")
        if rec_dst is not None and cur_dst is not None:
            w = min(0.42, 0.035 * h)
            out["dst"] = (1.0 - w) * float(cur_dst) + w * float(rec_dst)

    proton = interp_series(
        series.get("proton_flux") or [],
        h,
        persist=True,
        tau_h=8.0,
        background=0.15,
    )
    if proton is not None:
        try:
            from lunar_physics import normalize_proton_flux
            out["proton_flux_raw"] = proton
            out["proton_flux"] = round(normalize_proton_flux(max(0.05, proton)), 4)
        except Exception:
            out["proton_flux"] = max(0.05, proton)

    def _wind_blend(key: str, default: float, tau: float) -> float:
        obs = interp_series(series.get(key) or [], h, persist=True, tau_h=tau, background=default)
        cur = extra.get(key)
        rec = rec27.get(key)
        if obs is not None:
            base = obs
        elif cur is not None:
            try:
                base = float(cur)
            except (TypeError, ValueError):
                base = default
        else:
            base = default
        if rec is None or h < 6.0:
            return float(base)

        w = min(0.35, 0.08 + 0.01 * h)
        return float((1.0 - w) * base + w * float(rec))

    out["solar_wind_speed"] = max(250.0, _wind_blend("solar_wind_speed", 400.0, 18.0))
    out["solar_wind_density"] = max(0.4, _wind_blend("solar_wind_density", 5.0, 12.0))
    out["imf_bz"] = _wind_blend("imf_bz", float(extra.get("imf_bz") or -2.0), 10.0)
    if extra.get("imf_by") is not None or (series.get("imf_by")):
        out["imf_by"] = _wind_blend("imf_by", float(extra.get("imf_by") or 0.0), 10.0)
    if extra.get("imf_bt") is not None or (series.get("imf_bt")):
        out["imf_bt"] = max(1.5, _wind_blend("imf_bt", float(extra.get("imf_bt") or 5.0), 10.0))

    if extra.get("dst") is not None:
        out["dst"] = float(extra["dst"])
    if extra.get("f107") is not None:
        out["f107"] = float(extra["f107"])

    out["confidence"] = forecast_confidence({**extra, **out}, hour=h)
    return out
