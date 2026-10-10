(function () {
  "use strict";

  const MISSION_CANDIDATE_SITES = [
    { name: "Shackleton Crater Rim", lat: -89.68, lon: 166.15, notes: "Near-constant illumination, polar ice access" },
    { name: "Malapert Massif", lat: -85.9, lon: 12.9, notes: "Earth-facing high ground, comms favorable" },
    { name: "Nobile Rim 1", lat: -85.2, lon: 31.0, notes: "Artemis III candidate region" },
    { name: "Connecting Ridge", lat: -89.5, lon: -138.0, notes: "Peak-of-eternal-light candidate" },
    { name: "de Gerlache Rim", lat: -88.5, lon: -68.0, notes: "Artemis III exploration zone" },
    { name: "Haworth Crater", lat: -86.9, lon: -4.0, notes: "PSR-adjacent science target" },
    { name: "Lunar South Pole", lat: -89.9, lon: 0.0, notes: "Polar volatiles reference site" },
    { name: "Mare Imbrium", lat: 32.8, lon: -15.6, notes: "Flat mare mid-latitude ops" },
    { name: "Sea of Tranquility", lat: 8.5, lon: 31.4, notes: "Apollo 11 heritage basalt plain" },
    { name: "Tycho Crater Floor", lat: -43.31, lon: -11.36, notes: "Young crater complex" },
    { name: "Oceanus Procellarum", lat: 18.4, lon: -57.4, notes: "Largest mare, long traverse potential" },
    { name: "Aristarchus Plateau", lat: 26.7, lon: -49.0, notes: "Volcanic / pyroclastic science" },
    { name: "Von Kármán Crater", lat: -44.8, lon: 176.0, notes: "Far side-Chang'e-4 region inside SPA" },
    { name: "Schrödinger Crater", lat: -75.4, lon: -132.5, notes: "Far-side south-unique geology / PSR" },
    { name: "Compton Crater", lat: 55.3, lon: 103.8, notes: "Far side-radio-quiet observatory candidate" },
    { name: "Mare Moscoviense", lat: 27.3, lon: 147.9, notes: "Far-side mare basin" },
    { name: "Daedalus Crater", lat: -5.9, lon: 179.4, notes: "Far-side antipode reference" },
    { name: "Hertzsprung Crater", lat: 1.4, lon: -129.2, notes: "Far-side multi-ring basin" },
    { name: "Mare Ingenii", lat: -33.7, lon: 163.5, notes: "Far-side swirl mare / magnetic anomaly" },
    { name: "Freundlich-Sharonov Basin", lat: 18.5, lon: 175.0, notes: "Far-side multi-ring, radio quiet" },
    { name: "Mare Orientale", lat: -19.4, lon: -92.8, notes: "Far-side limb multi-ring basin" },
    { name: "Aitken Crater", lat: -16.8, lon: 173.4, notes: "Far side-SPA namesake crater" },
  ];

  const DEG = Math.PI / 180;

  function clamp(v, lo, hi) {
    return Math.max(lo, Math.min(hi, v));
  }

  function baselineInputs(lat, lon, hour) {
    const lst = (hour + lon / 15.0) % 24.0;
    const latR = lat * DEG;
    const hourAngle = ((lst - 12.0) * 15.0 * DEG);
    let cosZ;
    if (Math.abs(lat) > 80) {
      cosZ = Math.max(0.08, Math.abs(Math.cos(latR)) * 0.35 + 0.15 * Math.max(0, Math.cos(hourAngle)));
    } else {
      cosZ = Math.max(0, Math.cos(latR) * Math.cos(hourAngle));
    }
    let temp, solar, dust;
    if (cosZ > 0.05) {
      temp = 120.0 * Math.pow(cosZ, 0.25) - 20.0;
      solar = 8.0 + 12.0 * cosZ;
      dust = 1.2 + 0.4 * (1.0 - cosZ);
    } else {
      temp = -170.0 + 15.0 * Math.sin(latR);
      solar = 1.5 + Math.abs(lat) * 0.02;
      dust = 1.8 + 0.3 * Math.abs(Math.sin(latR));
    }
    if (Math.abs(lat) > 80) {
      temp = cosZ > 0.1 ? Math.min(temp, -35.0) : temp - 8.0;
      solar = Math.max(solar, 7.0);
    }
    const radiation = 0.055 + 0.02 * (solar / 20.0) + 0.01 * (Math.abs(lat) / 90.0);
    const moonquakes = 22.0 + 8.0 * Math.abs(Math.sin(latR)) + 3.0 * Math.sin(hour / 4.0);
    const micrometeorites = 1.4 + 0.3 * Math.sin((lat + lon) / 40.0) + 0.1 * (solar / 20.0);
    return [
      clamp(solar, 0, 50),
      clamp(radiation, 0.02, 0.35),
      clamp(temp, -190, 130),
      clamp(moonquakes, 5, 80),
      clamp(micrometeorites, 0.8, 6),
      clamp(dust, 0.5, 5),
    ];
  }

  function predFromBase(base) {
    return {
      solar: base[0],
      radiation: base[1],
      temperature: base[2],
      moonquakes: base[3],
      micrometeorites: base[4],
      dust: base[5],
    };
  }

  function lvl(val, yellow, red, higherWorse = true) {
    if (higherWorse) {
      if (val >= red) return "red";
      if (val >= yellow) return "yellow";
      return "green";
    }
    if (val <= red) return "red";
    if (val <= yellow) return "yellow";
    return "green";
  }

  function hazardLevels(pred, lat) {
    const rad = Number(pred.radiation ?? 0.08);
    const dust = Number(pred.dust ?? 1.5);
    const quakes = Number(pred.moonquakes ?? 28);
    const temp = Number(pred.temperature ?? 0);
    const meteor = Number(pred.micrometeorites ?? 1.6);
    const solar = Number(pred.solar ?? 5);
    const polar = lat != null && Math.abs(Number(lat)) > 80;
    let tempLvl;
    if (polar) tempLvl = temp > 100 ? "yellow" : "green";
    else tempLvl = temp > 125 || temp < -175 ? "red" : temp > 100 || temp < -150 ? "yellow" : "green";
    const storm = solar >= 22 || rad > 0.145 ? "red" : solar >= 14 || rad > 0.095 ? "yellow" : "green";
    const abrasion = lvl(dust, 1.7, 2.25);
    let thermalEq = "green";
    if (!polar && (temp > 110 || temp < -155)) thermalEq = temp > 125 || temp < -170 ? "red" : "yellow";
    else if (polar && temp > 95) thermalEq = "yellow";
    const struct = lvl(quakes, 30, 42);
    const impact = lvl(meteor, 1.9, 2.5);
    const rank = { green: 0, yellow: 1, red: 2 };
    const equipment = [abrasion, thermalEq, struct, impact].reduce((a, b) => (rank[a] >= rank[b] ? a : b));
    return {
      radiation: lvl(rad, 0.095, 0.15),
      solar_storm: storm,
      dust: lvl(dust, 1.85, 2.4),
      seismic: lvl(quakes, 32, 45),
      temperature: tempLvl,
      meteor: lvl(meteor, 1.95, 2.6),
      equipment,
      equip_abrasion: abrasion,
      equip_thermal: thermalEq,
      equip_structure: struct,
      equip_impact: impact,
    };
  }

  function shortReason(key, pred) {
    const rad = Number(pred.radiation ?? 0);
    const dust = Number(pred.dust ?? 0);
    const quakes = Number(pred.moonquakes ?? 0);
    const temp = Number(pred.temperature ?? 0);
    const meteor = Number(pred.micrometeorites ?? 0);
    const solar = Number(pred.solar ?? 0);
    const map = {
      radiation: `Rad ${rad.toFixed(3)} mSv/h`,
      solar_storm: `Storm risk (solar ${solar.toFixed(0)})`,
      dust: `Dust ${dust.toFixed(1)}`,
      seismic: `Seismic ${quakes.toFixed(0)}/d`,
      temperature: `Thermal ${temp.toFixed(0)}°C`,
      meteor: `Meteor ${meteor.toFixed(1)}`,
      equipment: "Equipment stress elevated",
    };
    return map[key] || key;
  }

  function evaScore(pred, riskPosture = "nominal", lat = null) {
    const rad = Number(pred.radiation ?? 0.08);
    const dust = Number(pred.dust ?? 1.5);
    const quakes = Number(pred.moonquakes ?? 28);
    const temp = Number(pred.temperature ?? 0);
    const meteor = Number(pred.micrometeorites ?? 1.6);
    const solar = Number(pred.solar ?? 5);
    const polar = lat != null && Math.abs(Number(lat)) > 80;
    let raw =
      rad * 380 +
      Math.max(0, quakes - 22) * 0.45 +
      Math.max(0, dust - 1.1) * 9 +
      Math.max(0, meteor - 1.3) * 6.5 +
      Math.max(0, solar - 12) * 1.1;
    if (polar) {
      if (temp > 110) raw += 12;
      else if (temp > 90) raw += 5;
    } else {
      if (temp < -165 || temp > 120) raw += 14;
      else if (temp < -130 || temp > 95) raw += 6;
    }
    const bias = { conservative: 8, nominal: 0, aggressive: -8 }[riskPosture] ?? 0;
    const score = clamp(100 - raw - bias, 0, 100);
    const levels = hazardLevels(pred, lat);
    const coreKeys = ["radiation", "solar_storm", "dust", "seismic", "temperature", "meteor", "equipment"];
    const reds = coreKeys.filter((k) => levels[k] === "red").length;
    const yellows = coreKeys.filter((k) => levels[k] === "yellow").length;
    let status = "go";
    if (reds || score < 35) status = "nogo";
    else if (yellows || score < 62) status = "caution";
    const reasons = [];
    for (const k of coreKeys) {
      if (levels[k] === "yellow" || levels[k] === "red") reasons.push(shortReason(k, pred));
      if (reasons.length >= 3) break;
    }
    if (!reasons.length) {
      reasons.push(status === "go" ? "Hazards inside GO band" : "Composite score → CAUTION");
    }
    return {
      score: Math.round(score * 10) / 10,
      status,
      hazards: levels,
      reasons: reasons.slice(0, 3),
      summary: {
        go: "EVA ok. Watch suits and dose.",
        caution: "Keep EVA short. Watch storms and dust.",
        nogo: "Hold EVA. Limits hit.",
      }[status] || "",
    };
  }

  function siteIllumination(lat, lon, hour) {
    const lst = (hour + lon / 15.0) % 24.0;
    const latR = lat * DEG;
    const hourAngle = ((lst - 12.0) * 15.0 * DEG);
    let cosZ;
    if (Math.abs(lat) > 80) {
      cosZ = Math.max(0.08, Math.abs(Math.cos(latR)) * 0.35 + 0.15 * Math.max(0, Math.cos(hourAngle)));
    } else {
      cosZ = Math.max(0, Math.cos(latR) * Math.cos(hourAngle));
    }
    return clamp(Math.round(cosZ * 100), 0, 100);
  }

  function baseSuitability(pred, lat, lon, illumPct) {
    const rad = Number(pred.radiation ?? 0.08);
    const dust = Number(pred.dust ?? 1.5);
    const quakes = Number(pred.moonquakes ?? 28);
    const meteor = Number(pred.micrometeorites ?? 1.6);
    const solar = Number(pred.solar ?? 5);
    const levels = hazardLevels(pred, lat);
    const power = Math.min(100, illumPct * 0.55 + Math.min(solar, 20) * 2.0);
    const hab = 100 - (rad * 280 + Math.max(0, dust - 1.0) * 14 + Math.max(0, quakes - 20) * 0.7 + Math.max(0, meteor - 1.2) * 8);
    const nearSide = Math.cos(lon * DEG);
    let comms = 55 + 35 * clamp(nearSide, -1, 1);
    if (Math.abs(lat) > 80) {
      power += 8;
      comms += Math.abs(lon) < 90 ? 5 : -5;
    }
    const score = clamp(0.38 * power + 0.42 * hab + 0.2 * comms, 0, 100);
    const why = [];
    if (power >= 65) why.push("Strong power potential");
    else if (power < 40) why.push("Limited solar power");
    if (levels.equipment === "green") why.push("Low equipment stress");
    else if (levels.equipment === "red") why.push("High equipment stress");
    if (levels.solar_storm !== "green") why.push("Storm watch active");
    if (Math.abs(lat) > 80) why.push("Polar ice / science access");
    if (nearSide > 0.2) why.push("Near-side comms");
    return {
      score: Math.round(score * 10) / 10,
      power: Math.round(power * 10) / 10,
      habitability: Math.round(Math.max(0, hab) * 10) / 10,
      comms: Math.round(comms * 10) / 10,
      why: (why.slice(0, 4).length ? why.slice(0, 4) : ["Balanced site factors"]),
      status: score >= 68 && levels.equipment !== "red" ? "go" : score >= 45 ? "caution" : "nogo",
    };
  }

  function confidencePct(plausibility, status, lat, lon) {
    let p = Number(plausibility);
    if (!Number.isFinite(p)) p = 0.68;
    p = clamp(p, 0.4, 0.98);
    let pct = p * 100;
    const st = String(status || "").toLowerCase();
    if (st === "nogo" || st === "red") pct -= 8;
    else if (st === "caution" || st === "yellow") pct -= 4;
    if (lon != null && Math.abs(((Number(lon) + 180) % 360) - 180) > 90) pct -= 2;
    if (lat != null && Math.abs(Number(lat)) >= 80) pct += 2;
    return Math.round(clamp(pct, 42, 96));
  }

  function fmtUtc(d) {
    return d.toISOString().replace(/\.\d{3}Z$/, "Z");
  }

  function fmtUtcShort(d) {
    const h = String(d.getUTCHours()).padStart(2, "0");
    const m = String(d.getUTCMinutes()).padStart(2, "0");
    return `${h}:${m}`;
  }

  function landingOpsWindows(hourly, now, riskPosture, lat, plausibility) {
    const landH = 2;
    const windows = [];
    for (let h = 0; h <= 24 - landH; h++) {
      const slice = hourly.slice(h, h + landH);
      const avg = {
        radiation: slice.reduce((s, x) => s + x.radiation, 0) / landH,
        dust: slice.reduce((s, x) => s + x.dust, 0) / landH,
        moonquakes: slice.reduce((s, x) => s + x.moonquakes, 0) / landH,
        micrometeorites: slice.reduce((s, x) => s + x.micrometeorites, 0) / landH,
        temperature: slice.reduce((s, x) => s + x.temperature, 0) / landH,
        solar: slice.reduce((s, x) => s + x.solar, 0) / landH,
      };
      const scored = evaScore(avg, riskPosture, lat);
      const stormHits = slice.filter((x) => x.storm !== "green").length;
      const equipHits = slice.filter((x) => x.equipment !== "green").length;
      const temp = avg.temperature;
      const polar = Math.abs(Number(lat)) >= 80;
      const thermalOk = polar ? temp >= -230 && temp <= 100 : temp >= -180 && temp <= 130;
      let landScore = scored.score;
      if (stormHits) landScore = Math.max(0, landScore - 12 * stormHits);
      if (!thermalOk) landScore = Math.max(0, landScore - 15);
      if (avg.radiation > 0.12) landScore = Math.max(0, landScore - 10);
      const risk =
        landScore < 35 || stormHits >= 2 ? "nogo" : landScore < 62 || stormHits || !thermalOk ? "caution" : "go";
      const start = new Date(now.getTime() + h * 3600000);
      const end = new Date(start.getTime() + landH * 3600000);
      windows.push({
        start_offset_h: h,
        label: `${fmtUtcShort(start)}-${fmtUtcShort(end)} UTC`,
        start_utc: fmtUtc(start),
        end_utc: fmtUtc(end),
        avg_radiation: Math.round(avg.radiation * 10000) / 10000,
        avg_dust: Math.round(avg.dust * 1000) / 1000,
        avg_temp: Math.round(avg.temperature * 10) / 10,
        avg_solar: Math.round(avg.solar * 10) / 10,
        storm_hours: stormHits,
        equip_hours: equipHits,
        score: Math.round(landScore * 10) / 10,
        risk,
        confidence_pct: confidencePct(plausibility, risk, lat, null),
        reasons: (scored.reasons.slice(0, 1).length ? scored.reasons.slice(0, 1) : ["Landing-ops hazard window"]).concat(
          stormHits ? [`${stormHits}h storm risk`] : ["Storm quiet"]
        ),
      });
    }
    windows.sort((a, b) => b.score - a.score || a.avg_radiation - b.avg_radiation);
    return windows.slice(0, 4);
  }

  function scoreZone(site, hour0, riskPosture) {
    const b = baselineInputs(site.lat, site.lon, hour0);
    const p = predFromBase(b);
    const sc = evaScore(p, riskPosture, site.lat);
    const illum = siteIllumination(site.lat, site.lon, hour0);
    const base = baseSuitability(p, site.lat, site.lon, illum);
    const polarBonus = Math.abs(site.lat) > 80 ? 3.0 : 0.0;
    const safety = Math.min(100, sc.score + polarBonus);
    const opsRank = Math.round((0.55 * safety + 0.45 * base.score) * 10) / 10;
    const conf = confidencePct(0.68, sc.status, site.lat, site.lon);
    return {
      name: site.name,
      lat: site.lat,
      lon: site.lon,
      notes: site.notes || "",
      safety_pct: Math.round(safety * 10) / 10,
      base_pct: base.score,
      ops_rank: opsRank,
      status: sc.status,
      base_status: base.status,
      confidence_pct: conf,
      radiation: Math.round(p.radiation * 10000) / 10000,
      temperature: Math.round(p.temperature * 10) / 10,
      dust: Math.round(p.dust * 1000) / 1000,
      solar: Math.round(p.solar * 100) / 100,
      moonquakes: Math.round(p.moonquakes * 10) / 10,
      illumination_pct: illum,
      hazards: sc.hazards,
      base,
      is_query: !!site.is_query,
      scored_with: "physics",
    };
  }

  function computeMissionPlanClient(payload) {
    let lat = Number(payload.lat ?? -89.68);
    let lon = Number(payload.lon ?? 166.15);
    lat = clamp(lat, -90, 90);
    lon = ((lon + 180) % 360) - 180;
    const name = String(payload.name || "").trim() || `Site ${lat.toFixed(2)}°, ${lon.toFixed(2)}°`;
    const evaH = clamp(parseInt(payload.eva_duration_h, 10) || 4, 1, 12);
    const missionDays = clamp(parseInt(payload.mission_days, 10) || 14, 1, 180);
    const evaPerDay = clamp(Number(payload.eva_per_day ?? Math.min(evaH, 4)), 0, 12);
    let riskPosture = String(payload.risk_posture || "nominal").toLowerCase();
    if (!["conservative", "nominal", "aggressive"].includes(riskPosture)) riskPosture = "nominal";

    const now = new Date();
    const hour0 = now.getUTCHours() + now.getUTCMinutes() / 60.0;
    const base0 = baselineInputs(lat, lon, hour0);
    const pred0 = predFromBase(base0);
    const evaNow = evaScore(pred0, riskPosture, lat);
    const illum = siteIllumination(lat, lon, hour0);
    const siteBase = baseSuitability(pred0, lat, lon, illum);
    const rad0 = pred0.radiation;
    const sol0 = pred0.solar;
    const plausibility = 0.68;

    const hourly = [];
    for (let h = 0; h < 24; h++) {
      const t = (hour0 + h) % 24.0;
      const base = baselineInputs(lat, lon, t).slice();
      const fade = Math.max(0, 1 - h / 18.0);
      base[1] = base[1] * (1 - 0.55 * fade) + rad0 * (0.55 * fade);
      base[0] = base[0] * (1 - 0.45 * fade) + sol0 * (0.45 * fade);
      const p = predFromBase(base);
      const stamp = new Date(now.getTime() + h * 3600000);
      const hz = hazardLevels(p, lat);
      hourly.push({
        hour_offset: h,
        utc: fmtUtc(stamp),
        local_time: Math.round(t * 100) / 100,
        radiation: p.radiation,
        temperature: p.temperature,
        dust: p.dust,
        solar: p.solar,
        moonquakes: p.moonquakes,
        micrometeorites: p.micrometeorites,
        storm: hz.solar_storm,
        equipment: hz.equipment,
      });
    }

    const windows = [];
    for (let h = 0; h <= 24 - evaH; h++) {
      const slice = hourly.slice(h, h + evaH);
      const avg = {
        radiation: slice.reduce((s, x) => s + x.radiation, 0) / evaH,
        dust: slice.reduce((s, x) => s + x.dust, 0) / evaH,
        moonquakes: slice.reduce((s, x) => s + x.moonquakes, 0) / evaH,
        micrometeorites: slice.reduce((s, x) => s + x.micrometeorites, 0) / evaH,
        temperature: slice.reduce((s, x) => s + x.temperature, 0) / evaH,
        solar: slice.reduce((s, x) => s + x.solar, 0) / evaH,
      };
      const scored = evaScore(avg, riskPosture, lat);
      const start = new Date(now.getTime() + h * 3600000);
      const end = new Date(start.getTime() + evaH * 3600000);
      const stormHits = slice.filter((x) => x.storm !== "green").length;
      const equipHits = slice.filter((x) => x.equipment !== "green").length;
      windows.push({
        start_offset_h: h,
        label: `${fmtUtcShort(start)}-${fmtUtcShort(end)} UTC`,
        start_utc: fmtUtc(start),
        end_utc: fmtUtc(end),
        avg_radiation: Math.round(avg.radiation * 10000) / 10000,
        avg_dust: Math.round(avg.dust * 1000) / 1000,
        avg_temp: Math.round(avg.temperature * 10) / 10,
        avg_solar: Math.round(avg.solar * 10) / 10,
        storm_hours: stormHits,
        equip_hours: equipHits,
        score: scored.score,
        risk: scored.status,
        confidence_pct: confidencePct(plausibility, scored.status, lat, lon),
        reasons: scored.reasons.slice(0, 2),
      });
    }
    windows.sort((a, b) => b.score - a.score || a.avg_radiation - b.avg_radiation);
    const topWindows = windows.slice(0, 6);
    const landingWindows = landingOpsWindows(hourly, now, riskPosture, lat, plausibility);

    const candidates = MISSION_CANDIDATE_SITES.concat([
      { name, lat, lon, notes: "Your planned site", is_query: true },
    ]);
    const zones = candidates.map((s) => scoreZone(s, hour0, riskPosture));
    zones.sort((a, b) => b.ops_rank - a.ops_rank || b.base_pct - a.base_pct);
    const bestBase = zones[0] || null;

    const radH = pred0.radiation;
    const gcr = 0.022;
    const interior = gcr * 0.35;
    const habitatH = Math.max(0, 24 - evaPerDay);
    const daily = radH * evaPerDay + interior * habitatH;
    const total = daily * missionDays;
    const evaDose = radH * evaPerDay * missionDays;
    const habDose = interior * habitatH * missionDays;
    const doseRisk = total > 100 ? "HIGH" : total > 50 ? "MODERATE" : total > 20 ? "LOW" : "MINIMAL";
    const hz = evaNow.hazards;
    const confNow = confidencePct(plausibility, evaNow.status, lat, lon);
    const evaNowOut = { ...evaNow, confidence_pct: confNow };
    const siteBaseOut = { ...siteBase, confidence_pct: confidencePct(plausibility, siteBase.status, lat, lon) };

    return {
      site: { name, lat, lon },
      eva_duration_h: evaH,
      mission_days: missionDays,
      eva_per_day: evaPerDay,
      risk_posture: riskPosture,
      generated_at: fmtUtc(now),
      model_source: "physics",
      model_loaded: false,
      ml_gated: false,
      gated_fields: [],
      client_mode: true,
      eva_now: evaNowOut,
      site_base: siteBaseOut,
      best_base: bestBase,
      conditions: {
        radiation: Math.round(pred0.radiation * 10000) / 10000,
        temperature: Math.round(pred0.temperature * 10) / 10,
        dust: Math.round(pred0.dust * 1000) / 1000,
        solar: Math.round(pred0.solar * 100) / 100,
        moonquakes: Math.round(pred0.moonquakes * 10) / 10,
        micrometeorites: Math.round(pred0.micrometeorites * 1000) / 1000,
        illumination_pct: illum,
        plausibility,
        confidence_pct: confNow,
        earth_link: Math.abs(lon) <= 95 ? "Direct" : "Relay",
        solar_storm: hz.solar_storm,
        equipment: hz.equipment,
      },
      hazard_matrix: {
        radiation: hz.radiation,
        solar_storm: hz.solar_storm,
        dust: hz.dust,
        seismic: hz.seismic,
        temperature: hz.temperature,
        meteor: hz.meteor,
        equipment: hz.equipment,
        equip_abrasion: hz.equip_abrasion,
        equip_thermal: hz.equip_thermal,
        equip_structure: hz.equip_structure,
        equip_impact: hz.equip_impact,
      },
      hourly,
      eva_windows: topWindows,
      landing_windows: landingWindows,
      all_windows: windows,
      landing_zones: zones,
      dose: {
        total_mSv: Math.round(total * 100) / 100,
        eva_mSv: Math.round(evaDose * 100) / 100,
        habitat_mSv: Math.round(habDose * 100) / 100,
        daily_mSv: Math.round(daily * 1000) / 1000,
        risk: doseRisk,
        pct_male: Math.round((total / 600) * 1000) / 10,
        pct_female: Math.round((total / 400) * 1000) / 10,
      },
    };
  }

  window.computeMissionPlanClient = computeMissionPlanClient;
})();
