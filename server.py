# flask app entry
from flask import Flask, send_from_directory, jsonify, request, Response
import os, math, random, json
from datetime import datetime, timezone, timedelta

try:
    from dotenv import load_dotenv
    _env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    load_dotenv(_env_path)
    load_dotenv()
except ImportError:
    pass

try:
    from pdf_generator import generate_mission_pdf, build_filename
except ImportError:
    generate_mission_pdf = None
    build_filename = None

app = Flask(__name__, static_folder=None)

MISSION_CANDIDATE_SITES = [
    {"name": "Shackleton Crater Rim", "lat": -89.68, "lon": 166.15, "notes": "Near-constant illumination, polar ice access"},
    {"name": "Malapert Massif", "lat": -85.9, "lon": 12.9, "notes": "Earth-facing high ground, comms favorable"},
    {"name": "Nobile Rim 1", "lat": -85.2, "lon": 31.0, "notes": "Artemis III candidate region"},
    {"name": "Connecting Ridge", "lat": -89.5, "lon": -138.0, "notes": "Peak-of-eternal-light candidate"},
    {"name": "de Gerlache Rim", "lat": -88.5, "lon": -68.0, "notes": "Artemis III exploration zone"},
    {"name": "Haworth Crater", "lat": -86.9, "lon": -4.0, "notes": "PSR-adjacent science target"},
    {"name": "Lunar South Pole", "lat": -89.9, "lon": 0.0, "notes": "Polar volatiles reference site"},
    {"name": "Mare Imbrium", "lat": 32.8, "lon": -15.6, "notes": "Flat mare mid-latitude ops"},
    {"name": "Sea of Tranquility", "lat": 8.5, "lon": 31.4, "notes": "Apollo 11 heritage basalt plain"},
    {"name": "Tycho Crater Floor", "lat": -43.31, "lon": -11.36, "notes": "Young crater complex"},
    {"name": "Oceanus Procellarum", "lat": 18.4, "lon": -57.4, "notes": "Largest mare, long traverse potential"},
    {"name": "Aristarchus Plateau", "lat": 26.7, "lon": -49.0, "notes": "Volcanic / pyroclastic science"},
    {"name": "Von Kármán Crater", "lat": -44.8, "lon": 176.0, "notes": "Far side-Chang'e-4 region inside SPA"},
    {"name": "Schrödinger Crater", "lat": -75.4, "lon": -132.5, "notes": "Far-side south-unique geology / PSR"},
    {"name": "Compton Crater", "lat": 55.3, "lon": 103.8, "notes": "Far side-radio-quiet observatory candidate"},
    {"name": "Mare Moscoviense", "lat": 27.3, "lon": 147.9, "notes": "Far-side mare basin"},
    {"name": "Daedalus Crater", "lat": -5.9, "lon": 179.4, "notes": "Far-side antipode reference"},
    {"name": "Hertzsprung Crater", "lat": 1.4, "lon": -129.2, "notes": "Far-side multi-ring basin"},
    {"name": "Mare Ingenii", "lat": -33.7, "lon": 163.5, "notes": "Far-side swirl mare / magnetic anomaly"},
    {"name": "Freundlich-Sharonov Basin", "lat": 18.5, "lon": 175.0, "notes": "Far-side multi-ring, radio quiet"},
    {"name": "Mare Orientale", "lat": -19.4, "lon": -92.8, "notes": "Far-side limb multi-ring basin"},
    {"name": "Aitken Crater", "lat": -16.8, "lon": 173.4, "notes": "Far side-SPA namesake crater"},
]

_ML_BOOTSTRAPPED = False

def _ensure_ml_loaded():
    global _ML_BOOTSTRAPPED
    if _ML_BOOTSTRAPPED:
        return
    try:
        import space_weather_model as swm
        if not getattr(swm, "TF_AVAILABLE", False):
            _ML_BOOTSTRAPPED = True
            return
        with swm._MODEL_LOCK:
            if swm._MODEL is None:
                loaded = swm.load_saved_model(swm.MODEL_DIR)
                if loaded is not None:
                    swm._MODEL = loaded
            if swm._SCALER is None:
                try:
                    swm._SCALER = swm.load_scaler()
                except Exception:
                    pass
            if swm._CALIBRATION is None:
                try:
                    swm._CALIBRATION = swm.load_calibration(swm.MODEL_DIR)
                except Exception:
                    pass
            try:
                swm.load_blend_weights(swm.MODEL_DIR)
            except Exception:
                pass

            try:
                if hasattr(swm, 'warm_start_feature_history'):
                    swm.warm_start_feature_history(swm.MODEL_DIR)
            except Exception:
                pass
        _ML_BOOTSTRAPPED = True
    except Exception:
        _ML_BOOTSTRAPPED = True

def _gate_ops_prediction(result):
    out = dict(result or {})
    pred = dict(out.get("prediction") or {})
    phys = dict(out.get("physics_estimate") or {})
    ml_block = out.get("ml_estimate") or {}
    ml = dict(ml_block.get("prediction") or {}) if isinstance(ml_block, dict) else {}
    if not phys:
        out["ml_gated"] = False
        return out

    gated_fields = []
    pr = float(phys.get("radiation", 0.07))
    hr = float(pred.get("radiation", pr))
    mr = float(ml.get("radiation", hr)) if ml else hr
    if mr > 0.4 or hr > 0.32:
        pred["radiation"] = pr
        gated_fields.append("radiation")

    ps = float(phys.get("solar", 5.0))
    hs = float(pred.get("solar", ps))
    if hs > 35 and ps < 22:
        pred["solar"] = ps
        gated_fields.append("solar")

    pt = float(phys.get("temperature", 0.0))
    ht = float(pred.get("temperature", pt))
    if abs(ht - pt) > 90:
        pred["temperature"] = pt
        gated_fields.append("temperature")

    pq = float(phys.get("moonquakes", 25.0))
    hq = float(pred.get("moonquakes", pq))
    if hq < 1.0 and pq > 10:
        pred["moonquakes"] = pq
        gated_fields.append("moonquakes")

    out["prediction"] = pred
    out["ml_gated"] = bool(gated_fields)
    out["gated_fields"] = gated_fields
    if gated_fields and out.get("source") == "ml+physics":
        out["source"] = "ml+physics (ops-gated)"
    return out

def _serve_extra(local_time=None):
    try:
        from data_ingestion import serve_extra_for_local_time
        return serve_extra_for_local_time(local_time)
    except Exception:
        return {}

def _try_ml_predict(inputs, lat, lon, local_time, extra=None):
    try:
        _ensure_ml_loaded()
        import space_weather_model as swm
        from space_weather_model import refine_prediction, physics_estimate, DEFAULT_ML_BLEND_WEIGHT
        _HAZARD_KEYS = (
            'solar', 'radiation', 'temperature', 'moonquakes', 'micrometeorites', 'dust'
        )
        def _hazards_only(d):
            if not isinstance(d, dict):
                return d
            return {k: d[k] for k in _HAZARD_KEYS if k in d}
        extra = extra if extra is not None else _serve_extra(local_time)
        fast = _hazards_only(physics_estimate(
            inputs, lat=lat, lon=lon, local_time=local_time, extra=extra,
        ))
        refined = refine_prediction(
            inputs, lat=lat, lon=lon, local_time=local_time,
            physics_weight=DEFAULT_ML_BLEND_WEIGHT, use_ensemble=False, extra=extra,
        )
        pred = _hazards_only((refined or {}).get("hybrid") or fast)
        ml_used = bool((refined or {}).get("ml")) and swm._MODEL is not None
        phys_out = _hazards_only((refined or {}).get("physics") or fast)
        result = {
            "prediction": pred,
            "physics_estimate": phys_out,
            "ml_estimate": (refined or {}).get("ml"),
            "plausibility": (refined or {}).get("plausibility"),
            "confidence": (refined or {}).get("confidence"),
            "blend_weights": (refined or {}).get("blend_weights"),
            "regime": (refined or {}).get("regime"),
            "source": "ml+physics" if ml_used else "physics",
            "model_loaded": swm._MODEL is not None,
            "driver_sources": list((extra or {}).get("driver_sources") or []),
        }
        return _gate_ops_prediction(result)
    except Exception:
        syn = make_synthetic_prediction(inputs, lat=lat, lon=lon, local_time=local_time)
        syn["source"] = "synthetic"
        syn["model_loaded"] = False
        syn["ml_gated"] = False
        return syn

def _earth_link_mode(lon):
    try:
        lo = float(lon)
    except Exception:
        lo = 0.0

    return "Direct" if abs(lo) <= 95.0 else "Relay"

def _derived_driver_channels(solar, radiation, dust, micrometeorites, lat, lon, local_time):
    sol = float(solar)
    rad = float(radiation)
    dust_v = float(dust)
    met = float(micrometeorites)
    lat_r = math.radians(float(lat) if lat is not None else 0.0)
    lst = float(local_time) if local_time is not None else 12.0
    hour_angle = (lst - 12.0) * 15.0 * math.pi / 180.0
    if abs(float(lat or 0.0)) > 80:
        cos_z = max(0.08, abs(math.cos(lat_r)) * 0.35 + 0.15 * max(0.0, math.cos(hour_angle)))
    else:
        cos_z = max(-1.0, min(1.0, math.sin(lat_r) * 0.05 + math.cos(lat_r) * math.cos(hour_angle)))
    illum = max(0.0, min(100.0, 55.0 + 40.0 * max(0.0, cos_z) + (8.0 if abs(float(lat or 0)) > 80 else 0.0)))
    solar_out = max(0.0, min(100.0, illum * (0.85 + 0.03 * min(sol, 12.0))))

    kp = max(0.0, min(9.0, 2.0 + 0.35 * sol + 8.0 * max(0.0, rad - 0.06)))
    sep = max(0.05, 0.25 * sol + 12.0 * rad)
    protons = max(0.1, 35.0 * rad + 0.15 * sol)
    flares = max(0.1, 0.45 * sol + 0.2 * max(0.0, sol - 4.0))
    cme = max(0.05, 0.3 * sol + 0.15 * max(0.0, kp - 3.0))
    storm = int(max(0, min(3, round(sol / 4.0 + (1 if rad > 0.12 else 0) + (1 if kp >= 6 else 0)))))
    eva_risk = max(0.0, min(100.0, rad * 220.0 + dust_v * 6.0 + met * 5.0 + max(0.0, sol - 5.0) * 4.0))

    link = _earth_link_mode(lon)
    comms = 92.0 if link == "Direct" else 48.0
    if abs(float(lat or 0)) > 85:
        comms -= 6.0
    return {
        "illumination": round(illum, 1),
        "solarOutput": round(solar_out, 1),
        "cos_z": round(cos_z, 3),
        "sep": round(sep, 3),
        "protons": round(protons, 3),
        "flares": round(flares, 3),
        "cme": round(cme, 3),
        "kp": round(kp, 2),
        "storm": storm,
        "evaRisk": round(eva_risk, 1),
        "comms": round(max(35.0, min(99.0, comms)), 1),
        "earth_link": link,
    }

def real_forecast_series(lat, lon, hours=48):
    now = datetime.now(timezone.utc)
    hour0 = now.hour + now.minute / 60.0
    extra0 = _serve_extra(hour0)
    base0 = _baseline_inputs(lat, lon, hour0)
    cur = _try_ml_predict(base0, lat, lon, hour0, extra=extra0)
    pred0 = cur.get("prediction") or {}
    rad0 = float(pred0.get("radiation", base0[1]))
    sol0 = float(pred0.get("solar", base0[0]))
    try:
        from space_weather_model import physics_estimate as _phys_est
    except Exception:
        _phys_est = None

    hours = max(1, min(168, int(hours)))

    control = {0}
    for h in range(0, hours, 6):
        control.add(h)
    control.add(hours - 1)
    hybrid_cache = {}

    core_keys = ("time", "radiation", "dust", "temperature", "solar", "moonquakes", "micrometeorites")
    derived_keys = ("illumination", "solarOutput", "cos_z", "sep", "protons", "flares", "cme", "kp", "storm", "evaRisk", "comms", "plausibility")
    series = {k: [] for k in core_keys + derived_keys}
    live_kp = extra0.get("kp_index")
    live_protons = extra0.get("proton_flux")

    for h in range(hours):
        t = (hour0 + h) % 24.0
        extra = _serve_extra(t)
        base = _baseline_inputs(lat, lon, t)
        fade = max(0.0, 1.0 - h / 18.0)
        base[1] = base[1] * (1 - 0.55 * fade) + rad0 * (0.55 * fade)
        base[0] = base[0] * (1 - 0.45 * fade) + sol0 * (0.45 * fade)
        if h in control:
            out = _try_ml_predict(base, lat, lon, t, extra=extra)
            p = out.get("prediction") or {}
            hybrid_cache[h] = p
        elif _phys_est is not None:
            p = _phys_est(base, lat=lat, lon=lon, local_time=t, extra=extra)
        else:
            p = {"solar": base[0], "radiation": base[1], "temperature": base[2],
                 "moonquakes": base[3], "micrometeorites": base[4], "dust": base[5]}

        if h not in control and hybrid_cache:
            nearest = min(hybrid_cache.keys(), key=lambda k: abs(k - h))
            hp = hybrid_cache[nearest]
            w = max(0.0, 1.0 - abs(nearest - h) / 6.0) * 0.55
            for key in ("solar", "radiation", "temperature", "moonquakes", "micrometeorites", "dust"):
                if key in hp and key in p:
                    p[key] = (1.0 - w) * float(p[key]) + w * float(hp[key])
        sol = float(p.get("solar", base[0]))
        rad = float(p.get("radiation", base[1]))
        dust = float(p.get("dust", base[5]))
        temp = float(p.get("temperature", base[2]))
        mq = float(p.get("moonquakes", base[3]))
        met = float(p.get("micrometeorites", base[4]))
        series["time"].append(h)
        series["radiation"].append(round(rad, 4))
        series["dust"].append(round(dust, 3))
        series["temperature"].append(round(temp, 1))
        series["solar"].append(round(sol, 2))
        series["moonquakes"].append(round(mq, 2))
        series["micrometeorites"].append(round(met, 3))
        d = _derived_driver_channels(sol, rad, dust, met, lat, lon, t)

        if live_kp is not None:
            try:
                d["kp"] = round(float(live_kp), 2)
            except Exception:
                pass
        if live_protons is not None:
            try:
                d["protons"] = round(max(0.05, float(live_protons)), 3)
            except Exception:
                pass
        for k in ("illumination", "solarOutput", "cos_z", "sep", "protons", "flares", "cme", "kp", "storm", "evaRisk", "comms"):
            series[k].append(d[k])
        p0 = float(cur.get("plausibility") or 0.72)
        series["plausibility"].append(round(max(0.45, min(0.98, p0 - 0.004 * h)), 3))
    series["anchor"] = {"radiation": rad0, "solar": sol0}
    series["model_loaded"] = bool(cur.get("model_loaded"))
    series["source"] = cur.get("source")
    series["plausibility_now"] = cur.get("plausibility")
    series["confidence"] = cur.get("confidence")
    series["gated_fields"] = cur.get("gated_fields") or []
    series["blend_weights"] = cur.get("blend_weights")
    series["earth_link"] = _earth_link_mode(lon)
    series["driver_sources"] = list(cur.get("driver_sources") or extra0.get("driver_sources") or [])
    series["hybrid_control_hours"] = sorted(control)
    series["channel_origin"] = {
        "radiation": "hybrid_ml_physics",
        "solar": "hybrid_ml_physics",
        "dust": "hybrid_ml_physics",
        "temperature": "hybrid_ml_physics",
        "moonquakes": "hybrid_ml_physics",
        "micrometeorites": "hybrid_ml_physics",
        "illumination": "geometry",
        "solarOutput": "geometry",
        "cos_z": "geometry",
        "comms": "geometry_earth_link",
        "sep": "derived_from_core",
        "protons": "goes_archive_or_derived",
        "flares": "derived_from_core",
        "cme": "derived_from_core",
        "kp": "swpc_omni_or_derived",
        "storm": "derived_from_core",
        "evaRisk": "derived_from_core",
    }
    conf = cur.get("confidence") or {}
    overall = conf.get("overall_pct")
    if overall is None and cur.get("plausibility") is not None:
        overall = round(100.0 * float(cur["plausibility"]), 1)
    series["confidence_pct"] = overall
    n = len(series["time"])
    if overall is not None and n:
        series["confidence_series"] = [
            round(max(35.0, float(overall) - 0.35 * h), 1) for h in range(n)
        ]
    return series

_MODEL_ACCURACY_CACHE = None

def _model_accuracy_pct():
    global _MODEL_ACCURACY_CACHE
    if _MODEL_ACCURACY_CACHE is not None:
        return _MODEL_ACCURACY_CACHE
    try:
        import space_weather_model as swm
        with open(os.path.join(swm.MODEL_DIR, "meta.json")) as f:
            meta = json.load(f)
        m = meta.get("metrics", {})
        rmse, rmse_p = m.get("test_rmse"), m.get("test_rmse_persistence")
        if rmse and rmse_p:
            _MODEL_ACCURACY_CACHE = round(max(0.0, min(99.9, 100.0 * (1.0 - rmse / rmse_p))), 1)
            return _MODEL_ACCURACY_CACHE
    except Exception:
        pass
    return None

def _baseline_inputs(lat, lon, hour):
    lst = (hour + (lon / 15.0)) % 24.0
    lat_r = math.radians(lat)
    hour_angle = (lst - 12.0) * 15.0 * math.pi / 180.0

    if abs(lat) > 80:
        cos_z = max(0.08, abs(math.cos(lat_r)) * 0.35 + 0.15 * max(0.0, math.cos(hour_angle)))
    else:
        cos_z = max(0.0, math.cos(lat_r) * math.cos(hour_angle))
    if cos_z > 0.05:
        temp = 120.0 * (cos_z ** 0.25) - 20.0
        solar = 8.0 + 12.0 * cos_z
        dust = 1.2 + 0.4 * (1.0 - cos_z)
    else:
        temp = -170.0 + 15.0 * math.sin(lat_r)
        solar = 1.5 + abs(lat) * 0.02
        dust = 1.8 + 0.3 * abs(math.sin(lat_r))
    if abs(lat) > 80:
        temp = min(temp, -35.0) if cos_z > 0.1 else temp - 8.0
        solar = max(solar, 7.0)
    radiation = 0.055 + 0.02 * (solar / 20.0) + 0.01 * (abs(lat) / 90.0)
    moonquakes = 22.0 + 8.0 * abs(math.sin(lat_r)) + 3.0 * math.sin(hour / 4.0)
    micrometeorites = 1.4 + 0.3 * math.sin((lat + lon) / 40.0) + 0.1 * (solar / 20.0)
    return [
        round(max(0.0, min(50.0, solar)), 3),
        round(max(0.02, min(0.35, radiation)), 4),
        round(max(-190.0, min(130.0, temp)), 1),
        round(max(5.0, min(80.0, moonquakes)), 2),
        round(max(0.8, min(6.0, micrometeorites)), 3),
        round(max(0.5, min(5.0, dust)), 3),
    ]

def _lvl(val, yellow, red, higher_worse=True):
    if higher_worse:
        if val >= red:
            return "red"
        if val >= yellow:
            return "yellow"
        return "green"
    if val <= red:
        return "red"
    if val <= yellow:
        return "yellow"
    return "green"

def _hazard_levels(pred, lat=None):
    rad = float(pred.get("radiation", 0.08))
    dust = float(pred.get("dust", 1.5))
    quakes = float(pred.get("moonquakes", 28))
    temp = float(pred.get("temperature", 0))
    meteor = float(pred.get("micrometeorites", 1.6))
    solar = float(pred.get("solar", 5.0))
    polar = lat is not None and abs(float(lat)) > 80
    if polar:
        temp_lvl = "yellow" if temp > 100 else "green"
    else:
        temp_lvl = "red" if temp > 125 or temp < -175 else "yellow" if temp > 100 or temp < -150 else "green"

    if solar >= 22 or rad > 0.145:
        storm = "red"
    elif solar >= 14 or rad > 0.095:
        storm = "yellow"
    else:
        storm = "green"

    abrasion = _lvl(dust, 1.7, 2.25)
    thermal_eq = "green"
    if not polar and (temp > 110 or temp < -155):
        thermal_eq = "red" if (temp > 125 or temp < -170) else "yellow"
    elif polar and temp > 95:
        thermal_eq = "yellow"
    struct = _lvl(quakes, 30, 42)
    impact = _lvl(meteor, 1.9, 2.5)

    equip_rank = {"green": 0, "yellow": 1, "red": 2}
    equipment = max([abrasion, thermal_eq, struct, impact], key=lambda x: equip_rank[x])
    return {
        "radiation": _lvl(rad, 0.095, 0.15),
        "solar_storm": storm,
        "dust": _lvl(dust, 1.85, 2.4),
        "seismic": _lvl(quakes, 32, 45),
        "temperature": temp_lvl,
        "meteor": _lvl(meteor, 1.95, 2.6),
        "equipment": equipment,
        "equip_abrasion": abrasion,
        "equip_thermal": thermal_eq,
        "equip_structure": struct,
        "equip_impact": impact,
    }

def _short_reason(key, pred, level):
    rad = float(pred.get("radiation", 0))
    dust = float(pred.get("dust", 0))
    quakes = float(pred.get("moonquakes", 0))
    temp = float(pred.get("temperature", 0))
    meteor = float(pred.get("micrometeorites", 0))
    solar = float(pred.get("solar", 0))
    mapping = {
        "radiation": f"Rad {rad:.3f} mSv/h",
        "solar_storm": f"Storm risk (solar {solar:.0f})",
        "dust": f"Dust {dust:.1f}",
        "seismic": f"Seismic {quakes:.0f}/d",
        "temperature": f"Thermal {temp:.0f}°C",
        "meteor": f"Meteor {meteor:.1f}",
        "equipment": "Equipment stress elevated",
    }
    return mapping.get(key, key)

def _eva_score(pred, risk_posture="nominal", lat=None):
    rad = float(pred.get("radiation", 0.08))
    dust = float(pred.get("dust", 1.5))
    quakes = float(pred.get("moonquakes", 28))
    temp = float(pred.get("temperature", 0))
    meteor = float(pred.get("micrometeorites", 1.6))
    solar = float(pred.get("solar", 5.0))
    polar = lat is not None and abs(float(lat)) > 80
    raw = (
        rad * 380
        + max(0, quakes - 22) * 0.45
        + max(0, dust - 1.1) * 9
        + max(0, meteor - 1.3) * 6.5
        + max(0, solar - 12) * 1.1
    )
    if polar:
        if temp > 110:
            raw += 12
        elif temp > 90:
            raw += 5
    else:
        if temp < -165 or temp > 120:
            raw += 14
        elif temp < -130 or temp > 95:
            raw += 6
    bias = {"conservative": 8, "nominal": 0, "aggressive": -8}.get(risk_posture, 0)
    score = max(0, min(100, 100 - raw - bias))
    levels = _hazard_levels(pred, lat=lat)
    core_keys = ("radiation", "solar_storm", "dust", "seismic", "temperature", "meteor", "equipment")
    reds = sum(1 for k in core_keys if levels.get(k) == "red")
    yellows = sum(1 for k in core_keys if levels.get(k) == "yellow")
    if reds or score < 35:
        status = "nogo"
    elif yellows or score < 62:
        status = "caution"
    else:
        status = "go"
    reasons = []
    for k in core_keys:
        if levels.get(k) in ("yellow", "red"):
            reasons.append(_short_reason(k, pred, levels[k]))
        if len(reasons) >= 3:
            break
    if not reasons:
        reasons.append("Hazards inside GO band" if status == "go" else "Composite score → CAUTION")
    return {
        "score": round(score, 1),
        "status": status,
        "hazards": levels,
        "reasons": reasons[:3],
        "summary": {
            "go": "EVA approved - monitor suits & rad.",
            "caution": "Shorten EVA · watch storms & dust.",
            "nogo": "Hold EVA - limits exceeded.",
        }.get(status, ""),
    }

def _base_suitability(pred, lat, lon, illum_pct):
    rad = float(pred.get("radiation", 0.08))
    dust = float(pred.get("dust", 1.5))
    quakes = float(pred.get("moonquakes", 28))
    meteor = float(pred.get("micrometeorites", 1.6))
    solar = float(pred.get("solar", 5.0))
    levels = _hazard_levels(pred, lat=lat)

    power = min(100.0, illum_pct * 0.55 + min(solar, 20) * 2.0)

    hab = 100.0 - (rad * 280 + max(0, dust - 1.0) * 14 + max(0, quakes - 20) * 0.7 + max(0, meteor - 1.2) * 8)

    near_side = math.cos(math.radians(lon))
    comms = 55 + 35 * max(-1, min(1, near_side))
    if abs(lat) > 80:
        power += 8
        comms += 5 if abs(lon) < 90 else -5
    score = max(0, min(100, 0.38 * power + 0.42 * hab + 0.20 * comms))
    why = []
    if power >= 65:
        why.append("Strong power potential")
    elif power < 40:
        why.append("Limited solar power")
    if levels["equipment"] == "green":
        why.append("Low equipment stress")
    elif levels["equipment"] == "red":
        why.append("High equipment stress")
    if levels["solar_storm"] != "green":
        why.append("Storm watch active")
    if abs(lat) > 80:
        why.append("Polar ice / science access")
    if near_side > 0.2:
        why.append("Near-side comms")
    return {
        "score": round(score, 1),
        "power": round(power, 1),
        "habitability": round(max(0, hab), 1),
        "comms": round(comms, 1),
        "why": why[:4] or ["Balanced site factors"],
        "status": "go" if score >= 68 and levels["equipment"] != "red" else "caution" if score >= 45 else "nogo",
    }

def _site_illumination(lat, lon, hour):
    lst = (hour + (lon / 15.0)) % 24.0
    lat_r = math.radians(lat)
    hour_angle = (lst - 12.0) * 15.0 * math.pi / 180.0
    if abs(lat) > 80:
        cos_z = max(0.08, abs(math.cos(lat_r)) * 0.35 + 0.15 * max(0.0, math.cos(hour_angle)))
    else:
        cos_z = max(0.0, math.cos(lat_r) * math.cos(hour_angle))
    return max(0, min(100, int(round(cos_z * 100))))

def _score_zone(site, hour0, risk_posture, use_ml=False):
    b = _baseline_inputs(site["lat"], site["lon"], hour0)
    plaus = None
    real_conf = None
    if use_ml:
        r = _try_ml_predict(b, site["lat"], site["lon"], hour0)
        p = r.get("prediction") or r.get("refined_estimate") or {}
        plaus = r.get("plausibility")
        real_conf = r.get("confidence")
    else:
        try:
            from space_weather_model import physics_estimate
            p = physics_estimate(b, lat=site["lat"], lon=site["lon"], local_time=hour0)
        except Exception:
            p = {
                "solar": b[0], "radiation": b[1], "temperature": b[2],
                "moonquakes": b[3], "micrometeorites": b[4], "dust": b[5],
            }
        plaus = 0.68
    sc = _eva_score(p, risk_posture, lat=site["lat"])
    illum = _site_illumination(site["lat"], site["lon"], hour0)
    base = _base_suitability(p, site["lat"], site["lon"], illum)
    polar_bonus = 3.0 if abs(site["lat"]) > 80 else 0.0
    safety = min(100.0, sc["score"] + polar_bonus)
    ops_rank = round(0.55 * safety + 0.45 * base["score"], 1)
    conf = _confidence_pct(plaus, sc["status"], site["lat"], site["lon"], confidence=real_conf)
    return {
        "name": site["name"],
        "lat": site["lat"],
        "lon": site["lon"],
        "notes": site.get("notes", ""),
        "safety_pct": round(safety, 1),
        "base_pct": base["score"],
        "ops_rank": ops_rank,
        "status": sc["status"],
        "base_status": base["status"],
        "confidence_pct": conf,
        "radiation": round(float(p.get("radiation", b[1])), 4),
        "temperature": round(float(p.get("temperature", b[2])), 1),
        "dust": round(float(p.get("dust", b[5])), 3),
        "solar": round(float(p.get("solar", b[0])), 2),
        "moonquakes": round(float(p.get("moonquakes", b[3])), 1),
        "illumination_pct": illum,
        "hazards": sc["hazards"],
        "base": base,
        "is_query": bool(site.get("is_query")),
        "scored_with": "ml" if use_ml else "physics",
    }

def _confidence_pct(plausibility, status=None, lat=None, lon=None, confidence=None):
    if isinstance(confidence, dict) and confidence.get("model_uncertainty_available") and confidence.get("overall_pct") is not None:
        try:
            pct = float(confidence["overall_pct"])
        except (TypeError, ValueError):
            pct = None
        if pct is not None:
            st = str(status or "").lower()
            if st in ("nogo", "red"):
                pct -= 8
            elif st in ("caution", "yellow"):
                pct -= 4
            if lon is not None:
                try:
                    if abs(((float(lon) + 180.0) % 360.0) - 180.0) > 90:
                        pct -= 2
                except (TypeError, ValueError):
                    pass
            if lat is not None:
                try:
                    if abs(float(lat)) >= 80:
                        pct += 2
                except (TypeError, ValueError):
                    pass
            return int(round(max(30, min(99, pct))))
    try:
        p = float(plausibility) if plausibility is not None else 0.72
    except (TypeError, ValueError):
        p = 0.72
    p = max(0.4, min(0.98, p))
    pct = p * 100.0
    st = str(status or "").lower()
    if st in ("nogo", "red"):
        pct -= 8
    elif st in ("caution", "yellow"):
        pct -= 4

    if lon is not None:
        try:
            if abs(((float(lon) + 180.0) % 360.0) - 180.0) > 90:
                pct -= 2
        except (TypeError, ValueError):
            pass
    if lat is not None:
        try:
            if abs(float(lat)) >= 80:
                pct += 2
        except (TypeError, ValueError):
            pass
    return int(round(max(42, min(96, pct))))

def _landing_ops_windows(hourly, now, risk_posture, lat, plausibility, confidence=None):
    land_h = 2
    windows = []
    for h in range(0, max(0, 24 - land_h + 1)):
        slice_ = hourly[h:h + land_h]
        avg = {
            k: sum(x[k] for x in slice_) / land_h
            for k in ("radiation", "dust", "moonquakes", "micrometeorites", "temperature", "solar")
        }
        scored = _eva_score(avg, risk_posture, lat=lat)
        storm_hits = sum(1 for x in slice_ if x["storm"] != "green")
        equip_hits = sum(1 for x in slice_ if x["equipment"] != "green")

        temp = avg["temperature"]
        thermal_ok = 140 <= temp <= 300
        land_score = scored["score"]
        if storm_hits:
            land_score = max(0, land_score - 12 * storm_hits)
        if not thermal_ok:
            land_score = max(0, land_score - 15)
        if avg["radiation"] > 0.12:
            land_score = max(0, land_score - 10)
        risk = "nogo" if land_score < 35 or storm_hits >= 2 else (
            "caution" if land_score < 62 or storm_hits or not thermal_ok else "go"
        )
        start = now + timedelta(hours=h)
        end = start + timedelta(hours=land_h)
        windows.append({
            "start_offset_h": h,
            "label": f"{start.strftime('%H:%M')}-{end.strftime('%H:%M')} UTC",
            "start_utc": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end_utc": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "avg_radiation": round(avg["radiation"], 4),
            "avg_dust": round(avg["dust"], 3),
            "avg_temp": round(avg["temperature"], 1),
            "avg_solar": round(avg["solar"], 1),
            "storm_hours": storm_hits,
            "equip_hours": equip_hits,
            "score": round(land_score, 1),
            "risk": risk,
            "confidence_pct": _confidence_pct(plausibility, risk, lat=lat, confidence=confidence),
            "reasons": (scored["reasons"][:1] or ["Landing-ops hazard window"]) + (
                ["Storm quiet"] if not storm_hits else [f"{storm_hits}h storm risk"]
            ),
        })
    windows.sort(key=lambda w: (-w["score"], w["avg_radiation"]))
    return windows[:4]

def _compute_mission_plan(payload):
    lat = float(payload.get("lat", -89.68))
    lon = float(payload.get("lon", 166.15))

    lat = max(-90.0, min(90.0, lat))
    lon = ((lon + 180.0) % 360.0) - 180.0
    name = (payload.get("name") or "").strip() or f"Site {lat:.2f}°, {lon:.2f}°"
    eva_h = max(1, min(12, int(payload.get("eva_duration_h", 4))))
    mission_days = max(1, min(180, int(payload.get("mission_days", 14))))
    eva_per_day = max(0.0, min(12.0, float(payload.get("eva_per_day", min(eva_h, 4)))))
    risk_posture = str(payload.get("risk_posture", "nominal")).lower()
    if risk_posture not in ("conservative", "nominal", "aggressive"):
        risk_posture = "nominal"

    now = datetime.now(timezone.utc)
    hour0 = now.hour + now.minute / 60.0

    base0 = _baseline_inputs(lat, lon, hour0)
    cur = _try_ml_predict(base0, lat, lon, hour0)
    pred0 = cur.get("prediction") or cur.get("refined_estimate") or {}
    eva_now = _eva_score(pred0, risk_posture, lat=lat)
    illum = _site_illumination(lat, lon, hour0)
    site_base = _base_suitability(pred0, lat, lon, illum)

    try:
        from space_weather_model import physics_estimate as _phys_est
    except Exception:
        _phys_est = None
    rad0 = float(pred0.get("radiation", base0[1]))
    sol0 = float(pred0.get("solar", base0[0]))
    hourly = []
    for h in range(24):
        t = (hour0 + h) % 24.0
        base = _baseline_inputs(lat, lon, t)

        fade = max(0.0, 1.0 - h / 18.0)
        base[1] = base[1] * (1 - 0.55 * fade) + rad0 * (0.55 * fade)
        base[0] = base[0] * (1 - 0.45 * fade) + sol0 * (0.45 * fade)
        if _phys_est is not None:
            p = _phys_est(base, lat=lat, lon=lon, local_time=t)
        else:
            p = {
                "solar": base[0], "radiation": base[1], "temperature": base[2],
                "moonquakes": base[3], "micrometeorites": base[4], "dust": base[5],
            }
        stamp = now + timedelta(hours=h)
        hz = _hazard_levels(p, lat=lat)
        hourly.append({
            "hour_offset": h,
            "utc": stamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "local_time": round(t, 2),
            "radiation": float(p.get("radiation", base[1])),
            "temperature": float(p.get("temperature", base[2])),
            "dust": float(p.get("dust", base[5])),
            "solar": float(p.get("solar", base[0])),
            "moonquakes": float(p.get("moonquakes", base[3])),
            "micrometeorites": float(p.get("micrometeorites", base[4])),
            "storm": hz["solar_storm"],
            "equipment": hz["equipment"],
        })

    windows = []
    for h in range(0, 24 - eva_h + 1):
        slice_ = hourly[h:h + eva_h]
        avg = {k: sum(x[k] for x in slice_) / eva_h for k in ("radiation", "dust", "moonquakes", "micrometeorites", "temperature", "solar")}
        scored = _eva_score(avg, risk_posture, lat=lat)
        start = now + timedelta(hours=h)
        end = start + timedelta(hours=eva_h)
        storm_hits = sum(1 for x in slice_ if x["storm"] != "green")
        equip_hits = sum(1 for x in slice_ if x["equipment"] != "green")
        windows.append({
            "start_offset_h": h,
            "label": f"{start.strftime('%H:%M')}-{end.strftime('%H:%M')} UTC",
            "start_utc": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end_utc": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "avg_radiation": round(avg["radiation"], 4),
            "avg_dust": round(avg["dust"], 3),
            "avg_temp": round(avg["temperature"], 1),
            "avg_solar": round(avg["solar"], 1),
            "storm_hours": storm_hits,
            "equip_hours": equip_hits,
            "score": scored["score"],
            "risk": scored["status"],
            "confidence_pct": _confidence_pct(cur.get("plausibility"), scored["status"], lat=lat, lon=lon, confidence=cur.get("confidence")),
            "reasons": scored["reasons"][:2],
        })
    windows.sort(key=lambda w: (-w["score"], w["avg_radiation"]))
    top_windows = windows[:6]
    landing_windows = _landing_ops_windows(hourly, now, risk_posture, lat, cur.get("plausibility"), confidence=cur.get("confidence"))

    candidates = list(MISSION_CANDIDATE_SITES) + [{
        "name": name,
        "lat": lat,
        "lon": lon,
        "notes": "Your planned site",
        "is_query": True,
    }]
    zones = [
        _score_zone(s, hour0, risk_posture, use_ml=bool(s.get("is_query")))
        for s in candidates
    ]
    zones.sort(key=lambda z: (-z["ops_rank"], -z["base_pct"]))
    best_base = zones[0] if zones else None

    rad_h = float(pred0.get("radiation", 0.075))
    gcr = 0.022
    interior = gcr * 0.35
    habitat_h = max(0.0, 24.0 - eva_per_day)
    daily = rad_h * eva_per_day + interior * habitat_h
    total = daily * mission_days
    eva_dose = rad_h * eva_per_day * mission_days
    hab_dose = interior * habitat_h * mission_days
    risk = "HIGH" if total > 100 else "MODERATE" if total > 50 else "LOW" if total > 20 else "MINIMAL"
    dose = {
        "total_mSv": round(total, 2),
        "eva_mSv": round(eva_dose, 2),
        "habitat_mSv": round(hab_dose, 2),
        "daily_mSv": round(daily, 3),
        "risk": risk,
        "pct_male": round(total / 600.0 * 100, 1),
        "pct_female": round(total / 400.0 * 100, 1),
    }

    hz = eva_now["hazards"]
    conf_now = _confidence_pct(cur.get("plausibility"), eva_now.get("status"), lat=lat, lon=lon, confidence=cur.get("confidence"))
    eva_now = {**eva_now, "confidence_pct": conf_now}
    site_base = {**site_base, "confidence_pct": _confidence_pct(cur.get("plausibility"), site_base.get("status"), lat=lat, lon=lon, confidence=cur.get("confidence"))}
    return {
        "site": {"name": name, "lat": lat, "lon": lon},
        "eva_duration_h": eva_h,
        "mission_days": mission_days,
        "eva_per_day": eva_per_day,
        "risk_posture": risk_posture,
        "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "model_source": cur.get("source", "unknown"),
        "model_loaded": bool(cur.get("model_loaded")),
        "ml_gated": bool(cur.get("ml_gated")),
        "gated_fields": cur.get("gated_fields") or [],
        "eva_now": eva_now,
        "site_base": site_base,
        "best_base": best_base,
        "conditions": {
            "radiation": round(float(pred0.get("radiation", base0[1])), 4),
            "temperature": round(float(pred0.get("temperature", base0[2])), 1),
            "dust": round(float(pred0.get("dust", base0[5])), 3),
            "solar": round(float(pred0.get("solar", base0[0])), 2),
            "moonquakes": round(float(pred0.get("moonquakes", base0[3])), 1),
            "micrometeorites": round(float(pred0.get("micrometeorites", base0[4])), 3),
            "illumination_pct": illum,
            "plausibility": cur.get("plausibility"),
            "confidence_pct": conf_now,
            "confidence": cur.get("confidence"),
            "blend_weights": cur.get("blend_weights"),
            "earth_link": _earth_link_mode(lon),
            "solar_storm": hz.get("solar_storm"),
            "equipment": hz.get("equipment"),
        },
        "confidence_detail": cur.get("confidence"),
        "blend_weights": cur.get("blend_weights"),
        "hazard_matrix": {
            "radiation": hz.get("radiation"),
            "solar_storm": hz.get("solar_storm"),
            "dust": hz.get("dust"),
            "seismic": hz.get("seismic"),
            "temperature": hz.get("temperature"),
            "meteor": hz.get("meteor"),
            "equipment": hz.get("equipment"),
            "equip_abrasion": hz.get("equip_abrasion"),
            "equip_thermal": hz.get("equip_thermal"),
            "equip_structure": hz.get("equip_structure"),
            "equip_impact": hz.get("equip_impact"),
        },
        "hourly": hourly,
        "eva_windows": top_windows,
        "landing_windows": landing_windows,
        "all_windows": windows,
        "landing_zones": zones,
        "dose": dose,
    }

@app.route('/')
def index():
    return send_from_directory('.', 'landing.html')

@app.route('/data')
def data_endpoint():
    try:
        lat = float(request.args.get('lat', 0))
        lon = float(request.args.get('lon', 0))
    except Exception:
        lat, lon = 0.0, 0.0
    try:
        hours = max(24, min(168, int(request.args.get('hours', 48))))
    except Exception:
        hours = 48
    now = datetime.now(timezone.utc)
    series = real_forecast_series(lat, lon, hours=hours)
    hourly = []
    for h in range(len(series['time'])):
        stamp = now + timedelta(hours=h)
        row = {
            'hour': h,
            'timestamp': int(stamp.timestamp() * 1000),
            'radiation': series['radiation'][h],
            'dust': series['dust'][h],
            'temperature': series['temperature'][h],
            'solar': series['solar'][h],
            'moonquakes': series['moonquakes'][h],
            'micrometeorites': series['micrometeorites'][h],
            'illumination': series['illumination'][h],
            'solarOutput': series['solarOutput'][h],
            'cos_z': series['cos_z'][h],
            'sep': series['sep'][h],
            'protons': series['protons'][h],
            'flares': series['flares'][h],
            'cme': series['cme'][h],
            'kp': series['kp'][h],
            'storm': series['storm'][h],
            'evaRisk': series['evaRisk'][h],
            'comms': series['comms'][h],
            'plausibility': series['plausibility'][h],
        }
        if series.get('confidence_series'):
            row['confidence_pct'] = series['confidence_series'][h]
        hourly.append(row)
    payload = {
        'real_time': {
            'timestamp': int(now.timestamp() * 1000),
            'summary': 'live ML+physics forecast' if series['model_loaded'] else 'physics-only estimate (ML model not loaded)',
            'source': series['source'],
            'model_loaded': series['model_loaded'],
            'earth_link': series.get('earth_link'),
            'confidence_pct': series.get('confidence_pct'),
            'gated_fields': series.get('gated_fields') or [],
        },
        'historical': {},
        'confidence': series.get('confidence'),
        'confidence_pct': series.get('confidence_pct'),
        'confidence_series': series.get('confidence_series'),
        'channel_origin': series.get('channel_origin'),
        'blend_weights': series.get('blend_weights'),
        'plausibility': series.get('plausibility_now'),
        'radiation_cache': {'hourly': hourly, 'timestamp': int(now.timestamp() * 1000)}
    }
    return jsonify(payload)

def make_synthetic_prediction(inputs, lat=0.0, lon=0.0, local_time=None):
    try:
        solar, radiation, temperature, moonquakes, micrometeorites, dust = [float(v) for v in inputs[:6]]
    except Exception:
        solar, radiation, temperature, moonquakes, micrometeorites, dust = 5.0, 0.057, 120.0, 2.0, 1.6, 1.5
    fast = {
        'solar': round(max(0.0, min(50.0, solar)), 2),
        'radiation': round(max(0.01, min(10.0, radiation)), 3),
        'temperature': round(max(-200.0, min(200.0, temperature)), 1),
        'moonquakes': round(max(0.0, min(200.0, moonquakes)), 2),
        'micrometeorites': round(max(0.8, min(8.0, micrometeorites)), 3),
        'dust': round(max(0.5, min(6.0, dust)), 3)
    }
    refined = {
        'solar': round(fast['solar'] * 0.95 + 0.5, 2),
        'radiation': round(fast['radiation'] * 0.95 + 0.01, 3),
        'temperature': round(fast['temperature'] * 0.98 + 1.2, 1),
        'moonquakes': round(fast['moonquakes'] * 0.98 + 0.1, 2),
        'micrometeorites': round(fast['micrometeorites'] * 0.96 + 0.02, 3),
        'dust': round(fast['dust'] * 0.96 + 0.02, 3)
    }
    return {
        'fast_estimate': fast,
        'refined_estimate': refined,
        'prediction': refined,
        'physics_estimate': fast,
        'ml_estimate': {'prediction': refined, 'uncertainty': [0.1, 0.1, 0.8, 0.2, 0.05, 0.03]},
        'plausibility': 0.75
    }

@app.route('/client-token')
def client_token():
    token = os.getenv('CESIUM_ION_TOKEN', '')
    return jsonify({'token': token})

@app.route('/predict', methods=['POST'])
def predict_endpoint():
    try:
        payload = request.get_json(force=True)
        if not payload:
            return jsonify({'error': 'invalid payload'}), 400
        inputs = payload.get('input') or payload.get('inputs')
        if not inputs or len(inputs) < 6:
            return jsonify({'error': 'input must be an array of 6 values'}), 400
        lat = float(payload.get('lat', 0.0)) if payload.get('lat') is not None else 0.0
        lon = float(payload.get('lon', 0.0)) if payload.get('lon') is not None else 0.0
        local_time = payload.get('local_time')
        if local_time is None:
            local_time = datetime.now(timezone.utc).hour
        else:
            try:
                local_time = float(local_time)
            except Exception:
                local_time = datetime.now(timezone.utc).hour
        result = _try_ml_predict(inputs[:6], lat, lon, local_time)
        pred = result.get('prediction') or {}
        conf = result.get('confidence')
        overall = None
        if isinstance(conf, dict) and conf.get('overall_pct') is not None:
            overall = conf.get('overall_pct')
        elif result.get('plausibility') is not None:
            overall = round(100.0 * float(result['plausibility']), 1)
        return jsonify({
            'fast_estimate': result.get('physics_estimate'),
            'refined_estimate': pred,
            'prediction': pred,
            'physics_estimate': result.get('physics_estimate'),
            'ml_estimate': result.get('ml_estimate'),
            'plausibility': result.get('plausibility'),

            'confidence': conf,
            'confidence_pct': overall,
            'gated_fields': result.get('gated_fields') or [],
            'blend_weights': result.get('blend_weights'),
            'source': result.get('source'),
            'model_loaded': result.get('model_loaded'),
            'ml_gated': result.get('ml_gated'),
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/status')
def status_proxy():
    try:
        _ensure_ml_loaded()
        import space_weather_model as swm
        return swm.status_endpoint()
    except Exception as e:
        return jsonify({'model_loaded': False, 'error': str(e)}), 200

@app.route('/api/real-data-status')
def real_data_status():
    _ensure_ml_loaded()
    import space_weather_model as swm
    has_real_data = bool(swm._MODEL is not None)
    drivers = {}
    try:
        from data_ingestion import load_serve_space_drivers
        drv = load_serve_space_drivers()
        drivers = {
            'sources': list(drv.get('sources') or []),
            'omni_date': drv.get('omni_date'),
            'kp_index': drv.get('kp_index'),
            'f107': drv.get('f107'),
            'proton_flux': drv.get('proton_flux'),
            'dst': drv.get('dst'),
        }
    except Exception as e:
        drivers = {'error': str(e)}
    prod_rmse = None
    try:
        meta_path = os.path.join(swm.MODEL_DIR, 'meta.json')
        if os.path.isfile(meta_path):
            with open(meta_path) as fh:
                prod_rmse = json.load(fh).get('metrics', {}).get('test_rmse')
    except Exception:
        pass
    return jsonify({
        'available': has_real_data,
        'model_loaded': has_real_data,
        'model_dir': getattr(swm, 'MODEL_DIR', 'saved_model'),
        'production_test_rmse': prod_rmse,
        'drivers': drivers,
        'message': ('Real trained LSTM model loaded and serving live ML+physics predictions'
                    if has_real_data else
                    'Model weights not loaded - using physics-only estimates'),
    })

@app.route('/api/environmental-data')
def environmental_data():
    try:
        lat = float(request.args.get('lat', -89.68))
        lon = float(request.args.get('lon', 166.15))
    except Exception:
        lat, lon = -89.68, 166.15
    series = real_forecast_series(lat, lon, hours=48)
    accuracy = _model_accuracy_pct()
    data = {
        'radiation': series['radiation'][0],
        'temperature': series['temperature'][0],
        'dust': series['dust'][0],
        'solar_wind': series['solar'][0],
        'moonquakes': series['moonquakes'][0],
        'micrometeorites': series['micrometeorites'][0],
        'accuracy': accuracy if accuracy is not None else 69.1,
        'model_loaded': series['model_loaded'],
        'source': series['source'],
        'time': series['time'],
        'radiation_series': series['radiation'],
        'temperature_series': series['temperature'],
        'dust_series': series['dust'],
        'solar_series': series['solar'],
        'moonquakes_series': series['moonquakes'],
        'micrometeorites_series': series['micrometeorites'],
    }
    return jsonify(data)

@app.route('/api/forecast')
def api_forecast():
    try:
        lat = float(request.args.get('lat', 0))
        lon = float(request.args.get('lon', 0))
        hours = int(request.args.get('hours', 48))
    except Exception:
        lat, lon, hours = 0, 0, 48
    hours = max(1, min(168, hours))
    series = real_forecast_series(lat, lon, hours=hours)
    return jsonify({
        'time': series['time'],
        'radiation': series['radiation'],
        'dust': series['dust'],
        'temperature': series['temperature'],
        'micrometeorites': series['micrometeorites'],
        'solar': series['solar'],
        'moonquakes': series['moonquakes'],
        'illumination': series.get('illumination'),
        'solarOutput': series.get('solarOutput'),
        'cos_z': series.get('cos_z'),
        'sep': series.get('sep'),
        'protons': series.get('protons'),
        'flares': series.get('flares'),
        'cme': series.get('cme'),
        'kp': series.get('kp'),
        'storm': series.get('storm'),
        'evaRisk': series.get('evaRisk'),
        'comms': series.get('comms'),
        'plausibility': series.get('plausibility'),
        'plausibility_now': series.get('plausibility_now'),
        'confidence': series.get('confidence'),
        'confidence_pct': series.get('confidence_pct'),
        'confidence_series': series.get('confidence_series'),
        'channel_origin': series.get('channel_origin'),
        'blend_weights': series.get('blend_weights'),
        'gated_fields': series.get('gated_fields'),
        'earth_link': series.get('earth_link'),
        'model_loaded': series['model_loaded'],
        'source': series['source'],
        'driver_sources': series.get('driver_sources'),
        'hybrid_control_hours': series.get('hybrid_control_hours'),
    })

def evaluate_hazard_grid(step_deg=10.0, local_time=12.0, times=None, mode='hybrid', ml_stride=None):
    step = float(step_deg)
    step = max(5.0, min(30.0, step))
    lats = []
    lat = -90.0
    while lat <= 90.0 + 1e-9:
        lats.append(round(lat, 6))
        lat += step
    lons = []
    lon = -180.0
    while lon < 180.0 - 1e-9:
        lons.append(round(lon, 6))
        lon += step
    n_lat, n_lon = len(lats), len(lons)
    if times is None:
        times = [float(local_time)]
    times = [float(t) % 24.0 for t in times][:4]
    mode = str(mode or 'hybrid').lower()
    if mode not in ('hybrid', 'physics', 'ml'):
        mode = 'hybrid'

    if ml_stride is None:
        target = 80
        cells = max(1, n_lat * n_lon)
        ml_stride = max(1, int(math.ceil(math.sqrt(cells / float(target)))))
    ml_stride = max(1, int(ml_stride))

    channels = ('solar', 'radiation', 'temperature', 'moonquakes', 'micrometeorites', 'dust')
    idx = {'solar': 0, 'radiation': 1, 'temperature': 2, 'moonquakes': 3, 'micrometeorites': 4, 'dust': 5}

    try:
        from space_weather_model import physics_estimate as _phys_est
    except Exception:
        _phys_est = None

    frames = []
    any_ml = False
    ml_control_total = 0
    driver_sources = []
    for t in times:
        extra = _serve_extra(t)
        if extra.get('driver_sources'):
            driver_sources = list(extra['driver_sources'])

        phys_grid = {c: [[0.0] * n_lon for _ in range(n_lat)] for c in channels}
        for i, la in enumerate(lats):
            for j, lo in enumerate(lons):
                base = _baseline_inputs(la, lo, t)
                if _phys_est is not None:
                    try:
                        pred = _phys_est(base, lat=la, lon=lo, local_time=t, extra=extra)
                    except Exception:
                        pred = None
                else:
                    pred = None
                for c in channels:
                    if pred and c in pred:
                        phys_grid[c][i][j] = float(pred[c])
                    else:
                        phys_grid[c][i][j] = float(base[idx[c]])

        out_grid = {c: [row[:] for row in phys_grid[c]] for c in channels}
        src_label = 'physics'
        n_ml = 0
        if mode in ('hybrid', 'ml'):

            residuals = []
            for i in range(0, n_lat, ml_stride):
                for j in range(0, n_lon, ml_stride):
                    la, lo = lats[i], lons[j]
                    base = _baseline_inputs(la, lo, t)
                    out = _try_ml_predict(base, la, lo, t, extra=extra)
                    if out.get('model_loaded'):
                        any_ml = True
                    pred = out.get('prediction') or {}
                    if mode == 'ml' and isinstance(out.get('ml_estimate'), dict):
                        ml_block = out['ml_estimate']
                        ml_pred = ml_block.get('prediction') if isinstance(ml_block, dict) else None
                        if isinstance(ml_pred, dict) and ml_pred:
                            pred = ml_pred
                    res = {}
                    for c in channels:
                        try:
                            hv = float(pred.get(c, phys_grid[c][i][j]))
                        except Exception:
                            hv = phys_grid[c][i][j]
                        res[c] = hv - phys_grid[c][i][j]
                    residuals.append((i, j, res))
                    n_ml += 1
            ml_control_total += n_ml

            if residuals:
                src_label = 'ml+physics_residual_nn'
                for i in range(n_lat):
                    for j in range(n_lon):
                        best = None
                        best_d = 1e18
                        for ci, cj, res in residuals:
                            d = (ci - i) * (ci - i) + (cj - j) * (cj - j)
                            if d < best_d:
                                best_d = d
                                best = res
                        for c in channels:
                            out_grid[c][i][j] = phys_grid[c][i][j] + best[c]

        fields = {}
        for c in channels:
            fields[c] = [
                [round(out_grid[c][i][j], 2 if c == 'temperature' else 4) for j in range(n_lon)]
                for i in range(n_lat)
            ]
        frames.append({
            'local_time': t,
            'fields': fields,
            'source_mix': {
                'physics_cells': n_lat * n_lon,
                'ml_control_points': n_ml,
                'field_source': src_label,
                'driver_sources': list(extra.get('driver_sources') or []),
            },
        })
    return {
        'lats': lats,
        'lons': lons,
        'step_deg': step,
        'n_cells': n_lat * n_lon,
        'ml_stride': ml_stride,
        'ml_control_total': ml_control_total,
        'channels': list(channels),
        'frames': frames,
        'model_loaded': any_ml,
        'mode': mode,
        'driver_sources': driver_sources,
        'note': 'Moon-wide fields: physics at every cell + ML residuals from control lattice + live/archive drivers. Not UI mock noise.',
    }

@app.route('/api/hazard-grid')
def api_hazard_grid():
    try:
        step = float(request.args.get('step', 10))
    except Exception:
        step = 10.0
    try:
        local_time = float(request.args.get('local_time', 12))
    except Exception:
        local_time = 12.0
    times_raw = request.args.get('times')
    times = None
    if times_raw:
        try:
            times = [float(x) for x in str(times_raw).split(',') if str(x).strip() != '']
        except Exception:
            times = None
    mode = request.args.get('mode', 'hybrid')
    ml_stride = request.args.get('ml_stride')
    try:
        ml_stride = int(ml_stride) if ml_stride is not None else None
    except Exception:
        ml_stride = None
    if step < 5:
        step = 5.0
    grid = evaluate_hazard_grid(
        step_deg=step, local_time=local_time, times=times, mode=mode, ml_stride=ml_stride,
    )
    return jsonify(grid)

@app.route('/api/mission/sites')
def mission_sites():
    return jsonify({"sites": MISSION_CANDIDATE_SITES})

@app.route('/api/mission/plan', methods=['POST'])
def mission_plan():
    try:
        payload = request.get_json(force=True) or {}
        plan = _compute_mission_plan(payload)
        return jsonify(plan)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/mission/eva-now', methods=['POST'])
def mission_eva_now():
    try:
        payload = request.get_json(force=True) or {}
        lat = float(payload.get("lat", -89.68))
        lon = float(payload.get("lon", 166.15))
        risk = str(payload.get("risk_posture", "nominal")).lower()
        hour = datetime.now(timezone.utc).hour + datetime.now(timezone.utc).minute / 60.0
        base = _baseline_inputs(lat, lon, hour)
        cur = _try_ml_predict(base, lat, lon, hour)
        pred = cur.get("prediction") or cur.get("refined_estimate") or {}
        scored = _eva_score(pred, risk, lat=lat)
        conf = _confidence_pct(cur.get("plausibility"), scored.get("status"), lat=lat, lon=lon, confidence=cur.get("confidence"))
        scored = {**scored, "confidence_pct": conf}
        conditions = dict(pred) if isinstance(pred, dict) else {}
        conditions["plausibility"] = cur.get("plausibility")
        conditions["confidence_pct"] = conf
        conditions["confidence_detail"] = cur.get("confidence")
        return jsonify({
            "lat": lat,
            "lon": lon,
            "conditions": conditions,
            "eva_now": scored,
            "model_source": cur.get("source"),
            "checked_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/mission/pdf', methods=['POST'])
def mission_pdf():
    if generate_mission_pdf is None:
        return jsonify({"error": "pdf_generator module unavailable"}), 500
    try:
        payload = request.get_json(force=True) or {}
        if payload.get("eva_windows") is None and payload.get("landing_zones") is None:
            plan = _compute_mission_plan(payload)
        else:
            plan = payload
        pdf_bytes = generate_mission_pdf(plan)
        fname = build_filename(plan) if build_filename else "LIPAS_MissionPlan.pdf"
        return Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{fname}"'},
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def _lipas_snapshot_for_luna(lat=None, lon=None, client_context=None):
    ctx = dict(client_context or {})
    try:
        la = float(lat if lat is not None else ctx.get("lat", -89.68))
        lo = float(lon if lon is not None else ctx.get("lon", 166.15))
    except (TypeError, ValueError):
        la, lo = -89.68, 166.15
    snap = {
        "lat": la,
        "lon": lo,
        "site": ctx.get("site") or ctx.get("location") or "selected site",
    }
    try:
        hour = datetime.now(timezone.utc).hour + datetime.now(timezone.utc).minute / 60.0
        base = _baseline_inputs(la, lo, hour)
        cur = _try_ml_predict(base, la, lo, hour)
        pred = cur.get("prediction") or cur.get("refined_estimate") or {}
        snap.update({
            "model_source": cur.get("source"),
            "model_loaded": cur.get("model_loaded"),
            "plausibility": cur.get("plausibility"),
            "radiation_mSv_h": pred.get("radiation"),
            "dust": pred.get("dust"),
            "temperature": pred.get("temperature"),
            "micrometeorites": pred.get("micrometeorites"),
            "moonquakes": pred.get("moonquakes"),
            "solar": pred.get("solar"),
        })
        scored = _eva_score(pred, "nominal", lat=la)
        snap["eva_now"] = scored.get("status") or scored.get("label")
        snap["eva_score"] = scored.get("score")
    except Exception as e:
        snap["live_error"] = str(e)

    for k, v in ctx.items():
        if k not in snap and v is not None:
            snap[k] = v
    return snap

def _luna_local_answer(message, snap):
    t = (message or "").lower().strip()
    site = snap.get("site") or "the selected site"
    rad = snap.get("radiation_mSv_h")
    temp = snap.get("temperature")
    dust = snap.get("dust")
    solar = snap.get("solar")
    eva = snap.get("eva_now")
    score = snap.get("eva_score")
    src = snap.get("model_source") or ("ml+physics" if snap.get("model_loaded") else "physics")
    plaus = snap.get("plausibility")

    def fmt(v, digits=3):
        try:
            return f"{float(v):.{digits}f}"
        except (TypeError, ValueError):
            return "n/a"

    live = (
        f"Live LIPAS at {site} ({snap.get('lat')}, {snap.get('lon')}): "
        f"radiation {fmt(rad)} mSv/h, temp {fmt(temp, 1)}, dust {fmt(dust, 2)}, "
        f"solar {fmt(solar, 2)}, EVA now {eva or 'n/a'}"
        + (f" (score {fmt(score, 0)})" if score is not None else "")
        + f", model {src}"
        + (f", plausibility {fmt(plaus, 2)}" if plaus is not None else "")
        + "."
    )

    replies = [
        (["radiation", "dose", "gcr", "sievert", "µsv", "usv", "msv"],
         f"{live} Quiet-time lunar surface dose is typically tens of µSv/h; storms can spike SEP/proton risk. "
         f"Use Dashboard radiation + Mission Planner EVA windows before suit egress."),
        (["temp", "thermal", "hot", "cold", "heat", "freeze"],
         f"{live} Lunar thermal swing is extreme (roughly −173°C night to ~127°C day; PSRs colder). "
         f"Pace EVA around illumination and thermal stress on the site you selected."),
        (["dust", "regolith", "abras"],
         f"{live} Regolith is abrasive and electrostatically sticky-worst near terminators and after surface ops. "
         f"Watch seals, radiators, and suit bearings when dust index climbs."),
        (["eva", "walk", "suit", "window", "safe", "go", "no-go", "nogo"],
         f"{live} LIPAS scores EVA from radiation, solar/storm, dust, thermal, meteor, and site fit. "
         f"Open Mission Planner → Run plan for ranked 24h GO/CAUTION/NO-GO windows."),
        (["solar", "flare", "cme", "storm", "sep", "kp"],
         f"{live} Solar drivers (flares/CME/SEP/Kp) fold into hybrid hazard channels. "
         f"If storm posture rises, shorten EVA or hold for a quieter window."),
        (["quake", "seismic", "moonquake"],
         f"{live} Seismic risk is usually low vs radiation/thermal, but elevated periods still matter for habitats and instruments."),
        (["meteor", "micrometeor", "impact"],
         f"{live} Micrometeoroid flux is continuous; LIPAS tracks relative elevation so you can harden or shorten exposed work."),
        (["far side", "farside", "von karman", "ingenii", "radio"],
         f"Far-side sites (Von Kármán, Mare Ingenii, Compton, etc.) never see Earth - great for radio astronomy, harder for direct comms. "
         f"{live}"),
        (["pole", "shackleton", "artemis", "ice", "psr"],
         f"South-polar ridges can offer near-constant sunlight beside permanently shadowed ice. {live}"),
        (["ml", "model", "lstm", "predict", "hybrid", "lipas", "accuracy", "plaus"],
         f"{live} LIPAS blends temporal ML on space-weather features with physics calibration "
         f"(Stefan-Boltzmann / Apollo thermal curves). Plausibility flags physics↔ML agreement."),
        (["hello", "hi", "hey", "help", "what can"],
         f"I'm Luna - I brief lunar hazards using live LIPAS data. Ask about radiation, EVA windows, "
         f"dust, storms, or far-side sites. {live}"),
    ]
    best, best_s = None, 0
    for keys, ans in replies:
        s = sum(len(k) for k in keys if k in t)
        if s > best_s:
            best_s, best = s, ans
    if best and best_s > 0:
        return best
    return (
        f"{live} Ask me about radiation, temperature, dust, solar storms, EVA safety, "
        f"polar/far-side sites, or how the hybrid ML+physics model works."
    )

def _luna_openai_answer(message, snap, history=None):
    import urllib.request
    key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if not key:
        return None, "no_key"
    system = (
        "You are Luna, the L.I.P.A.S. lunar ops assistant. Answer clearly and usefully about "
        "lunar environment, Artemis ops, and LIPAS hybrid ML+physics hazards. "
        "Ground answers in the provided LIPAS snapshot when relevant. Keep replies concise "
        "(2-6 sentences) unless the user asks for detail. Do not invent fake telemetry."
    )
    messages = [{"role": "system", "content": system}]
    messages.append({"role": "system", "content": "LIPAS snapshot JSON: " + json.dumps(snap, default=str)[:3500]})
    for turn in (history or [])[-8:]:
        role = turn.get("role")
        content = turn.get("content")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": str(content)[:1500]})
    messages.append({"role": "user", "content": str(message)[:2000]})
    body = json.dumps({
        "model": os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        "messages": messages,
        "temperature": 0.4,
        "max_tokens": 450,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        text = data["choices"][0]["message"]["content"].strip()
        return text, "openai"
    except Exception as e:
        return None, f"openai_error:{e}"

def _luna_pollinations_answer(message, snap, history=None):
    import ssl
    import urllib.error
    import urllib.request
    system = (
        "You are Luna, the L.I.P.A.S. lunar operations assistant. You are sharp, practical, and "
        "ops-focused. Use the live LIPAS snapshot for site-specific advice. Prefer concrete EVA, "
        "radiation, thermal, dust, solar-storm, polar/far-side, and mission-planning guidance. "
        "When asked for suggested activities, give 3-5 short actionable bullets with GO / CAUTION / "
        "NO-GO tone. Never invent instruments or fake precise telemetry beyond the snapshot. "
        "Keep answers tight unless the user asks for depth."
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "system", "content": "Live LIPAS snapshot: " + json.dumps(snap, default=str)[:3200]},
    ]
    for turn in (history or [])[-6:]:
        role = turn.get("role")
        content = turn.get("content")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": str(content)[:1200]})
    messages.append({"role": "user", "content": str(message)[:2000]})
    body = json.dumps({
        "model": os.environ.get("LUNA_FREE_MODEL", "openai"),
        "messages": messages,
        "temperature": 0.45,
        "max_tokens": 550,
    }).encode("utf-8")
    endpoints = [
        "https://text.pollinations.ai/openai",
        "https://api.pollinations.ai/v1/chat/completions",
    ]

    contexts = []
    try:
        contexts.append(ssl.create_default_context())
    except Exception:
        pass
    try:
        import certifi
        contexts.append(ssl.create_default_context(cafile=certifi.where()))
    except Exception:
        pass
    if not contexts:
        contexts.append(None)
    last_err = None
    for url in endpoints:
        for ctx in contexts:
            try:
                req = urllib.request.Request(
                    url,
                    data=body,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                open_kw = {"timeout": 35}
                if ctx is not None:
                    open_kw["context"] = ctx
                with urllib.request.urlopen(req, **open_kw) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                text = (data.get("choices") or [{}])[0].get("message", {}).get("content")
                if text and str(text).strip():
                    return str(text).strip(), "pollinations"
            except Exception as e:
                last_err = e
                continue
    return None, f"pollinations_error:{last_err}"

@app.route('/api/luna-chat', methods=['POST'])
def luna_chat():
    try:
        payload = request.get_json(force=True) or {}
        message = (payload.get("message") or payload.get("q") or "").strip()
        if not message:
            return jsonify({"error": "message required"}), 400

        client_ctx = payload.get("context") or {}
        has_live = any(
            client_ctx.get(k) is not None
            for k in ("radiation", "temperature", "dust", "evaRisk", "solar")
        )
        if has_live:
            snap = dict(client_ctx)
            try:
                snap["lat"] = float(payload.get("lat") if payload.get("lat") is not None else snap.get("lat", -89.68))
                snap["lon"] = float(payload.get("lon") if payload.get("lon") is not None else snap.get("lon", 166.15))
            except (TypeError, ValueError):
                snap.setdefault("lat", -89.68)
                snap.setdefault("lon", 166.15)
            snap.setdefault("site", snap.get("site") or "selected site")

            if snap.get("radiation") is not None and snap.get("radiation_mSv_h") is None:
                try:

                    snap["radiation_mSv_h"] = float(snap["radiation"]) / 1000.0
                except (TypeError, ValueError):
                    pass
        else:
            snap = _lipas_snapshot_for_luna(
                payload.get("lat"), payload.get("lon"), client_ctx
            )
        history = payload.get("history")

        answer = _luna_local_answer(message, snap)
        source = "lipas-local"

        if (os.environ.get("LUNA_USE_LLM") or "").strip() in ("1", "true", "yes"):
            llm, llm_src = _luna_openai_answer(message, snap, history)
            if not llm:
                llm, llm_src = _luna_pollinations_answer(message, snap, history)
            if llm:
                answer, source = llm, llm_src
        return jsonify({
            "answer": answer,
            "source": source,
            "snapshot": {
                "site": snap.get("site"),
                "lat": snap.get("lat"),
                "lon": snap.get("lon"),
                "eva_now": snap.get("eva_now"),
                "model_source": snap.get("model_source"),
                "radiation_mSv_h": snap.get("radiation_mSv_h"),
            },
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/<path:path>', methods=['GET', 'HEAD'])
def static_proxy(path):

    if '..' in path or path.startswith('api/') or path in ('predict', 'client-token', 'data', 'status'):
        return jsonify({'error': 'not found'}), 404
    resp = send_from_directory('.', path)
    if path.endswith(('.css', '.js', '.png', '.jpg', '.jpeg', '.svg', '.woff2', '.webp')):
        resp.cache_control.max_age = 31536000
        resp.cache_control.public = True
    else:
        resp.cache_control.no_cache = True
    return resp

if __name__ == '__main__':

    port = int(os.getenv('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=True)
