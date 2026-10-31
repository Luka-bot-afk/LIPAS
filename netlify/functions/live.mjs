const UA = "Mozilla/5.0 (compatible; LIPAS/3; space-weather-ops)";
let mem = { at: 0, drivers: null, sats: null };
const MERCURY_SITES = [
  ["overview", "Mercury", 0, 0, "overview", "All sites."],
  ["antipode", "Caloris antipode", -30, -18.5, "antipodes", "Rough ground opposite Caloris."],
  ["debussy", "Debussy", -34, 14, "antipodes", "Bright young crater."],
  ["antipode_n", "North antipode", -12, -25, "antipodes", "North of the antipode."],
  ["antipode_e", "East antipode", -28, 8, "antipodes", "East of the antipode."],
  ["equator", "Equator", 0, 0, "sites", "0°N, 0°E."],
  ["hokusai", "Hokusai", 58, 17, "sites", "Bright crater with long rays."],
  ["rachmaninoff", "Rachmaninoff", 27.7, 57.6, "sites", "Basin with hollows."],
  ["raditladi", "Raditladi", 27.2, 119, "sites", "Basin east of Caloris."],
  ["caloris", "Caloris", 30.5, 189.8, "sites", "Largest basin."],
  ["tolstoj", "Tolstoj", -16.2, -163.5, "sites", "Old dark basin."],
  ["beethoven", "Beethoven", -20.8, -123.4, "sites", "Southern plains basin."],
  ["discovery", "Discovery Rupes", -56.3, -38.3, "sites", "Long cliff (scarp)."],
  ["prokofiev", "Prokofiev", 85.8, 62.9, "sites", "North pole ice crater."],
  ["chao", "Chao Meng-Fu", -87.3, -132.4, "sites", "South pole ice crater."],
];
const EARTH_PLACES = [
  ["overview", "Earth", "overview", 0, 0, 0, "Planet-wide conditions from the live SWPC feed."],
  ["boulder", "NOAA SWPC Boulder", "city", 40.02, -105.27, 0, "Space Weather Prediction Center."],
  ["houston", "Houston / Johnson", "city", 29.55, -95.1, 0, "ISS flight control."],
  ["fairbanks", "Fairbanks", "city", 64.84, -147.72, 0, "Alaskan auroral zone."],
  ["ksc", "Kennedy Space Center", "launch", 28.57, -80.65, 0, "US east-coast departure."],
  ["starbase", "Starbase", "launch", 25.99, -97.16, 0, "Boca Chica departure site."],
  ["vandenberg", "Vandenberg", "launch", 34.74, -120.57, 0, "US west-coast polar departure."],
  ["kourou", "Guiana Space Centre", "launch", 5.24, -52.77, 0, "ESA equatorial launch site."],
  ["baikonur", "Baikonur", "launch", 45.96, 63.31, 0, "Roscosmos departure site."],
  ["mahia", "Mahia", "launch", -39.26, 177.86, 0, "Rocket Lab departure site."],
  ["poker", "Poker Flat", "launch", 65.13, -147.48, 0, "Sounding-rocket range."],
];
function json(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "public, max-age=60",
      "access-control-allow-origin": "*",
    },
  });
}
function num(v, dflt = null) {
  const n = Number(v);
  return Number.isFinite(n) ? n : dflt;
}
function wrap(lon) {
  let x = Number(lon) || 0;
  while (x > 180) x -= 360;
  while (x < -180) x += 360;
  return x;
}
function round(v, d = 2) {
  const n = Number(v);
  if (!Number.isFinite(n)) return null;
  const p = 10 ** d;
  return Math.round(n * p) / p;
}
async function getJSON(url) {
  const r = await fetch(url, { headers: { "User-Agent": UA, Accept: "application/json" } });
  if (!r.ok) throw new Error(r.status + " " + url);
  return r.json();
}
function lastObj(arr) {
  if (!Array.isArray(arr) || !arr.length) return null;
  for (let i = arr.length - 1; i >= 0; i--) {
    if (arr[i] && typeof arr[i] === "object" && !Array.isArray(arr[i])) return arr[i];
  }
  return null;
}
function flareFromFlux(flux) {
  const f = Number(flux);
  if (!Number.isFinite(f) || f <= 0) return { flare_class: "A0", flare_index: 0.4, xray_flux: null };
  const bands = [["X", 1e-4, 8], ["M", 1e-5, 6], ["C", 1e-6, 4], ["B", 1e-7, 2], ["A", 1e-8, 0.4]];
  for (const [letter, thr, base] of bands) {
    if (f >= thr) {
      const mag = f / thr;
      return {
        flare_class: letter + (mag >= 10 ? mag.toFixed(0) : mag.toFixed(1)),
        flare_index: Math.min(10, base + Math.min(1.8, mag / 5)),
        xray_flux: f,
      };
    }
  }
  return { flare_class: "A0", flare_index: 0.3, xray_flux: f };
}
function gScale(kp) {
  const k = Number(kp) || 0;
  if (k >= 9) return "G5";
  if (k >= 8) return "G4";
  if (k >= 7) return "G3";
  if (k >= 6) return "G2";
  if (k >= 5) return "G1";
  return "G0";
}
function parseKpRows(rows) {
  if (!Array.isArray(rows)) return [];
  const out = [];
  for (const row of rows) {
    if (Array.isArray(row)) {
      if (row[0] === "time_tag") continue;
      const kp = num(row[1]);
      if (kp == null) continue;
      out.push({ time: row[0], kp, observed: String(row[2] || ""), scale: row[3] || gScale(kp) });
    } else if (row && row.kp != null) {
      out.push({ time: row.time_tag, kp: num(row.kp), observed: "observed", scale: gScale(row.kp) });
    }
  }
  return out;
}
function parseRegionLocation(loc) {
  const s = String(loc || "").toUpperCase();
  const m = s.match(/([NS])(\d{1,2})([EW])(\d{1,2})/);
  if (!m) return null;
  const lat = (m[1] === "S" ? -1 : 1) * Number(m[2]);
  const lon = (m[3] === "W" ? -1 : 1) * Number(m[4]);
  return { lat, lon };
}
async function loadDrivers() {
  if (mem.drivers && Date.now() - mem.at < 90_000) return mem.drivers;
  const urls = {
    kp: "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json",
    kpForecast: "https://services.swpc.noaa.gov/products/noaa-planetary-k-index-forecast.json",
    xray: "https://services.swpc.noaa.gov/json/goes/primary/xrays-6-hour.json",
    f107: "https://services.swpc.noaa.gov/json/f107_cm_flux.json",
    wind: "https://services.swpc.noaa.gov/products/summary/solar-wind-speed.json",
    mag: "https://services.swpc.noaa.gov/products/summary/solar-wind-mag-field.json",
    protons: "https://services.swpc.noaa.gov/json/goes/primary/integral-protons-6-hour.json",
    regions: "https://services.swpc.noaa.gov/json/solar_regions.json",
    dst: "https://services.swpc.noaa.gov/json/geospace/geospace_dst_1_hour.json",
  };
  const settled = await Promise.all(
    Object.entries(urls).map(async ([k, url]) => {
      try {
        return [k, await getJSON(url)];
      } catch (err) {
        return [k, null, String(err.message || err)];
      }
    })
  );
  const raw = {};
  const sources = [];
  for (const [k, val] of settled) {
    raw[k] = val;
    if (val) sources.push("noaa-swpc:" + k);
  }
  const kpRows = parseKpRows(raw.kp);
  const kpFc = parseKpRows(raw.kpForecast);
  const kpNow = kpRows.length ? kpRows[kpRows.length - 1].kp : 2;
  const xrayRows = Array.isArray(raw.xray) ? raw.xray.filter((r) => r && (r.energy === "0.1-0.8nm" || r.energy === "0.1-0.8 nm" || !r.energy)) : [];
  const xray = xrayRows.length ? xrayRows[xrayRows.length - 1] : lastObj(raw.xray);
  const flare = flareFromFlux(xray && (xray.flux || xray.observed_flux));
  const f107row = lastObj(raw.f107);
  const f107 = num(f107row && (f107row.flux || f107row.f107), 130);
  const wind = raw.wind || {};
  const mag = raw.mag || {};
  const speed = num(wind.WindSpeed || wind.wind_speed, 400);
  const bt = num(mag.Bt || mag.bt, 5);
  const bz = num(mag.Bz || mag.bz, -1);
  const protonRows = Array.isArray(raw.protons) ? raw.protons.filter((r) => /10/.test(String(r.energy || r.channel || ""))) : [];
  const proton = protonRows.length ? protonRows[protonRows.length - 1] : lastObj(raw.protons);
  const protonFlux = num(proton && (proton.flux || proton.proton_flux), 0.2);
  const dstRow = lastObj(raw.dst);
  const dst = num(dstRow && (dstRow.dst || dstRow.Dst || dstRow.value), -15);
  const regions = Array.isArray(raw.regions) ? raw.regions : [];
  const newestDate = regions.find((r) => r && r.observed_date)?.observed_date || null;
  const list = newestDate ? regions.filter((r) => r.observed_date === newestDate) : regions;
  const spots = [];
  for (const r of list) {
    if (!r || typeof r !== "object") continue;
    const parsed = parseRegionLocation(r.location) || { lat: num(r.latitude), lon: num(r.longitude) };
    if (parsed.lat == null || parsed.lon == null) continue;
    const area = num(r.area, 0);
    const nSpots = num(r.number_spots, 0);
    const mProb = num(r.m_flare_probability, 0);
    const xProb = num(r.x_flare_probability, 0);
    spots.push({
      region: r.region,
      location: r.location,
      lat: parsed.lat,
      lon: parsed.lon,
      visible: Math.abs(parsed.lon) <= 90,
      area,
      number_spots: nSpots,
      spot_class: r.spot_class,
      mag_class: r.mag_class,
      c_flare_probability: r.c_flare_probability,
      m_flare_probability: mProb,
      x_flare_probability: xProb,
      intensity: round(Math.min(1, 0.15 + area / 800 + nSpots / 40 + mProb / 80 + xProb / 40), 3),
    });
  }
  const kpSeries = (kpFc.length ? kpFc : kpRows.slice(-8)).slice(0, 24);
  const drivers = {
    sources,
    kp: kpNow,
    kpSeries: kpSeries.map((r) => r.kp),
    g_scale: gScale(kpNow),
    ...flare,
    f107,
    speed,
    bt,
    bz,
    proton_flux: protonFlux,
    dst,
    spots,
    observed_date: newestDate || (xray && xray.time_tag) || null,
    fetched_at: new Date().toISOString(),
  };
  mem = { ...mem, at: Date.now(), drivers };
  return drivers;
}
function mercuryRau(date) {
  const epoch = Date.UTC(2000, 0, 1, 12);
  const days = (date - epoch) / 86400000;
  const M = (174.796 + 4.09233445 * days) * Math.PI / 180;
  const e = 0.20563;
  const E = M + e * Math.sin(M);
  const nu = 2 * Math.atan2(Math.sqrt(1 + e) * Math.sin(E / 2), Math.sqrt(1 - e) * Math.cos(E / 2));
  const a = 0.387098;
  return a * (1 - e * Math.cos(E));
}
function moonSubsolar(date) {
  const epoch = Date.UTC(2024, 0, 11, 11, 57);
  const syn = 29.530588 * 86400000;
  const phase = ((date - epoch) % syn + syn) % syn / syn;
  return { lat: round(1.54 * Math.sin(2 * Math.PI * phase), 2), lon: round(wrap(-phase * 360), 2), phase };
}
function incidence(lat, lon, sub) {
  const la = lat * Math.PI / 180;
  const dLon = (lon - sub.lon) * Math.PI / 180;
  const sb = sub.lat * Math.PI / 180;
  return Math.max(0, Math.sin(la) * Math.sin(sb) + Math.cos(la) * Math.cos(sb) * Math.cos(dLon));
}
function magDraw(rss) {
  const R = Math.max(1.15, Number(rss) || 1.42);
  const nx = 56;
  const nz = 40;
  const xMin = -4;
  const xMax = 3;
  const zMin = -3;
  const zMax = 3;
  const cells = [];
  const values = [];
  for (let j = 0; j < nz; j++) {
    const row = [];
    const vals = [];
    const z = zMax - ((j + 0.5) / nz) * (zMax - zMin);
    for (let i = 0; i < nx; i++) {
      const x = xMin + ((i + 0.5) / nx) * (xMax - xMin);
      const rad = Math.hypot(x, z);
      const th = Math.atan2(z, x);
      const shape = Math.sqrt(2 / (1 + Math.max(-0.92, Math.cos(th))));
      let kind = "wind";
      if (rad < 1) kind = "planet";
      else if (rad < R * shape) kind = "magnetosphere";
      else if (rad < R * 1.55 * shape) kind = "sheath";
      row.push(kind);
      vals.push(12 + 140 / Math.pow(Math.max(0.35, rad), 3));
    }
    cells.push(row);
    values.push(vals);
  }
  const arc = (scale, sign) => {
    const pts = [];
    for (let i = 0; i <= 24; i++) {
      const th = -1.15 + (2.3 * i) / 24;
      const r = scale * Math.sqrt(2 / (1 + Math.max(-0.92, Math.cos(th))));
      pts.push([r * Math.cos(th), sign * Math.abs(r * Math.sin(th))]);
    }
    return pts;
  };
  return {
    standoff_rm: round(R, 3),
    bow_shock_rm: round(R * 1.55, 3),
    cusp_latitude_deg: round(50 + (R - 1.3) * 18, 1),
    grid: { nx, nz, x_min: xMin, x_max: xMax, z_min: zMin, z_max: zMax, cells },
    bmag_grid: { nx, nz, x_min: xMin, x_max: xMax, z_min: zMin, z_max: zMax, vmin: 8, vmax: 160, values },
    equatorial_grid: { nx, nz, ny: nz, x_min: xMin, x_max: xMax, z_min: zMin, z_max: zMax, y_min: zMin, y_max: zMax, cells },
    colors: { planet: "#b08968", magnetosphere: "#7eb6d6", sheath: "#e4c56a", wind: "#e07a4a" },
    legend: [["wind", "Solar wind"], ["sheath", "Sheath"], ["magnetosphere", "Magnetosphere"], ["planet", "Mercury"]],
    bow_shock: { north: arc(R * 1.55, 1), south: arc(R * 1.55, -1) },
    magnetopause: { north: arc(R, 1), south: arc(R, -1) },
    field_lines: [0.4, 0.9, 1.4].map((z0) => ({
      closed: z0 < 1.2,
      points: [[0.2, z0 * 0.2], [0.8, z0], [1.6, z0 * 0.7], [2.2, z0 * 0.2]],
    })),
  };
}
function hourDriver(d, hour) {
  const series = d.kpSeries && d.kpSeries.length ? d.kpSeries : [d.kp];
  const kp = series[Math.min(series.length - 1, Math.max(0, hour | 0))] ?? d.kp;
  const wobble = 1 + 0.04 * Math.sin(hour / 3.5);
  return {
    kp,
    bz: d.bz * wobble,
    speed: d.speed * (1 + 0.02 * Math.sin(hour / 5)),
    proton_flux: d.proton_flux * (1 + 0.08 * Math.sin(hour / 4)),
    flare_index: d.flare_index,
    f107: d.f107,
    dst: d.dst + 4 * Math.sin(hour / 6),
  };
}
function mercuryAt(site, d, hour, when) {
  const h = hourDriver(d, hour);
  const r = mercuryRau(when + hour * 3600000);
  const scale = 1 / (r * r);
  const n = 5 * scale;
  const pdyn = 1.6726e-6 * n * h.speed * h.speed;
  const rss = 1.45 * Math.pow(8 / Math.max(1.5, pdyn), 1 / 6);
  const draw = magDraw(rss);
  const lst = (12 + hour + site.lon / 15) % 24;
  const day = lst >= 6 && lst <= 18;
  const illum = day ? Math.max(0, Math.cos(Math.PI * (lst - 12) / 12) * Math.cos(site.lat * Math.PI / 180)) : 0;
  const tK = 100 + 520 * Math.pow(illum, 0.25);
  const rad = 0.05 * scale * (1 + Math.log10(1 + h.proton_flux) * 0.35) * (0.85 + 0.3 * illum);
  const solar = Math.min(40, 4 + h.flare_index * 1.4 + h.f107 / 40);
  return {
    site: { id: site.id, name: site.name, lat: site.lat, lon: site.lon, group: site.group, note: site.note },
    r_au: round(r, 4),
    lst_h: round((lst + 24) % 24, 2),
    day_night: day ? "day" : "night",
    source: "noaa-swpc+mercury-physics",
    prediction: { radiation: round(rad, 4), solar: round(solar, 2), temperature: round(tK - 273.15, 1), dust: round(1.2 + illum * 2, 2), moonquakes: 1.2, micrometeorites: round(1.4 * scale, 2) },
    physics: {
      flare_class: d.flare_class,
      flare_index: round(h.flare_index, 2),
      f107: round(h.f107, 1),
      kp_index: round(h.kp, 2),
      p_dyn_npa: round(pdyn, 2),
      dst: round(h.dst, 1),
      proton_flux: round(h.proton_flux, 3),
      xray_flux: d.xray_flux,
      solar_constant_w_m2: round(1361 * scale, 1),
    },
    wind_mercury: { imf_bz: round(h.bz / r, 2), imf_b_mag: round((d.bt || 5) / r, 2), density: round(n, 2), speed: round(h.speed, 1) },
    magnetosphere: { ...draw, p_dyn_npa: round(pdyn, 2), p_mag_mp_npa: round(pdyn * 0.8, 2), imf_b_mag_nt: round((d.bt || 5) / r, 2) },
    drivers: { sources: d.sources },
    confidence_pct: 70,
    confidence: { overall_pct: 70, basis: "noaa-swpc+mercury-physics" },
    alerts: [{
      level: h.kp >= 5 || h.flare_index >= 6 ? "caution" : "ok",
      title: h.kp >= 5 ? "Geomagnetic storm at Earth" : "Live SWPC drivers",
      body: `Kp ${round(h.kp, 1)} ${gScale(h.kp)} · GOES ${d.flare_class} · wind ${round(h.speed, 0)} km/s scaled to ${round(r, 3)} AU.`,
    }],
    illumination: round(illum * 100, 1),
  };
}
function moonForecast(lat, lon, hours, d) {
  const when = Date.now();
  const n = Math.max(1, Math.min(168, hours | 0));
  const keys = ["time", "radiation", "dust", "temperature", "micrometeorites", "solar", "moonquakes", "illumination", "sep", "protons", "flares", "cme", "kp", "storm", "f107", "dst", "evaRisk", "comms", "plausibility", "confidence_series"];
  const series = Object.fromEntries(keys.map((k) => [k, []]));
  for (let h = 0; h < n; h++) {
    const sub = moonSubsolar(when + h * 3600000);
    const mu = incidence(lat, lon, sub);
    const hd = hourDriver(d, h);
    const rad = 0.045 + 0.012 * Math.log10(1 + hd.proton_flux) + hd.kp * 0.004 + mu * 0.01;
    const solar = Math.min(20, 1.5 + hd.flare_index * 0.9);
    const temp = 90 + 300 * Math.pow(mu, 0.25) - 273.15;
    series.time.push(h);
    series.radiation.push(round(rad, 4));
    series.dust.push(round(0.8 + mu * 2.2, 2));
    series.temperature.push(round(temp, 1));
    series.micrometeorites.push(round(1.1 + hd.kp * 0.05, 2));
    series.solar.push(round(solar, 2));
    series.moonquakes.push(round(1.1 + (mu < 0.05 ? 0.4 : 0.1), 2));
    series.illumination.push(round(mu * 100, 1));
    series.sep.push(round(Math.min(10, hd.proton_flux * 0.4 + Math.max(0, hd.kp - 3)), 2));
    series.protons.push(round(Math.min(10, Math.log10(1 + hd.proton_flux) * 3), 2));
    series.flares.push(round(hd.flare_index, 2));
    series.cme.push(round(Math.min(10, Math.max(0, hd.kp - 2) * 0.4 + Math.max(0, -hd.bz) * 0.05), 2));
    series.kp.push(round(hd.kp, 2));
    series.storm.push(hd.kp >= 7 ? 2 : hd.kp >= 5 ? 1 : 0);
    series.f107.push(round(hd.f107, 1));
    series.dst.push(round(hd.dst, 1));
    series.evaRisk.push(round(Math.min(10, rad * 40 + (hd.kp >= 5 ? 2 : 0)), 2));
    series.comms.push(round(Math.min(10, hd.flare_index * 0.4 + Math.max(0, hd.kp - 4)), 2));
    series.plausibility.push(0.74);
    series.confidence_series.push(72);
  }
  return {
    ...series,
    model_loaded: false,
    source: "noaa-swpc+lunar-geometry",
    driver_sources: d.sources,
    confidence_pct: 72,
    confidence: { overall_pct: 72, basis: "noaa-swpc" },
    channel_origin: { radiation: "goes-protons", solar: "goes-xray", kp: "swpc", illumination: "geometry", temperature: "geometry" },
  };
}
function hazardGrid(step, times, d) {
  const s = Math.max(10, Math.min(30, Number(step) || 15));
  const lats = [];
  const lons = [];
  for (let la = -90; la <= 90 + 1e-6; la += s) lats.push(round(la, 4));
  for (let lo = -180; lo < 180 - 1e-6; lo += s) lons.push(round(lo, 4));
  const frames = (times.length ? times : [0]).slice(0, 4).map((t) => {
    const sub = moonSubsolar(Date.now() + Number(t) * 3600000);
    const hd = hourDriver(d, Number(t));
    const fields = { solar: [], radiation: [], temperature: [], moonquakes: [], micrometeorites: [], dust: [] };
    for (const la of lats) {
      const rows = { solar: [], radiation: [], temperature: [], moonquakes: [], micrometeorites: [], dust: [] };
      for (const lo of lons) {
        const mu = incidence(la, lo, sub);
        rows.solar.push(round((1.2 + hd.flare_index) * (0.06 + 0.94 * mu), 3));
        rows.radiation.push(round(0.045 + 0.01 * Math.log10(1 + hd.proton_flux) + mu * 0.02, 4));
        rows.temperature.push(round(90 + 300 * Math.pow(mu, 0.25) - 273.15, 1));
        rows.moonquakes.push(round(1 + (mu < 0.08 ? 0.6 : 0.15), 2));
        rows.micrometeorites.push(round(1.1 + hd.kp * 0.04, 2));
        rows.dust.push(round(0.7 + mu * 2.4, 2));
      }
      Object.keys(fields).forEach((k) => fields[k].push(rows[k]));
    }
    return { local_time: Number(t), subsolar: sub, fields, source_mix: { field_source: "noaa-swpc+geometry", driver_sources: d.sources } };
  });
  return {
    lats, lons, step_deg: s, n_cells: lats.length * lons.length, channels: Object.keys(frames[0].fields),
    frames, model_loaded: false, mode: "live", driver_sources: d.sources,
    note: "Moon-wide fields from live NOAA drivers and the subsolar point. Trained residuals run on the Flask server.",
  };
}
function propagate(el, hour) {
  const epoch = Date.parse(el.EPOCH);
  const n = num(el.MEAN_MOTION, 15);
  const dtDays = (Date.now() + hour * 3600000 - epoch) / 86400000;
  const theta = (num(el.MEAN_ANOMALY, 0) * Math.PI) / 180 + 2 * Math.PI * n * dtDays;
  const inc = (num(el.INCLINATION, 51.6) * Math.PI) / 180;
  const raan = (num(el.RA_OF_ASC_NODE, 0) * Math.PI) / 180;
  const argp = (num(el.ARG_OF_PERICENTER, 0) * Math.PI) / 180;
  const u = theta + argp;
  const lat = Math.asin(Math.max(-1, Math.min(1, Math.sin(inc) * Math.sin(u))));
  const jd = Date.now() / 86400000 + 2440587.5 + hour / 24;
  const gmst = ((280.46061837 + 360.98564736629 * (jd - 2451545)) * Math.PI) / 180;
  const lon = Math.atan2(Math.cos(inc) * Math.sin(u), Math.cos(u)) + raan - gmst;
  const nrad = (n * 2 * Math.PI) / 86400;
  const a = Math.cbrt(398600.4418 / (nrad * nrad));
  return {
    lat: lat * 180 / Math.PI,
    lon: wrap(lon * 180 / Math.PI),
    alt_km: a - 6378.137,
    inclination: num(el.INCLINATION, 0),
  };
}
function trackOf(el) {
  const n = Math.max(0.5, num(el.MEAN_MOTION, 15));
  const periodH = 24 / n;
  const pts = [];
  for (let i = 0; i <= 72; i++) pts.push(propagate(el, (i / 72) * periodH));
  return pts.map((p) => [round(p.lon, 3), round(p.lat, 3), round(p.alt_km, 1)]);
}
async function loadSats(hour) {
  if (!mem.sats || Date.now() - mem.sats.at > 10 * 60 * 1000) {
    const groups = ["stations", "gps-ops", "weather", "resource"];
    const lists = await Promise.all(groups.map(async (g) => {
      try {
        const rows = await getJSON(`https://celestrak.org/NORAD/elements/gp.php?GROUP=${g}&FORMAT=json`);
        return Array.isArray(rows) ? rows.slice(0, g === "resource" ? 12 : 40) : [];
      } catch (_) {
        return [];
      }
    }));
    const byId = new Map();
    lists.flat().forEach((el) => {
      const id = String(el.NORAD_CAT_ID || el.OBJECT_NAME);
      if (!byId.has(id)) byId.set(id, el);
    });
    mem.sats = { at: Date.now(), els: [...byId.values()].slice(0, 80) };
  }
  return mem.sats.els.map((el) => {
    const p = propagate(el, hour);
    const name = String(el.OBJECT_NAME || "SAT").trim();
    return {
      id: String(el.NORAD_CAT_ID || name),
      name,
      lat: round(p.lat, 3),
      lon: round(p.lon, 3),
      alt_km: round(p.alt_km, 1),
      inclination: round(p.inclination, 2),
      group: p.alt_km > 20000 ? "GEO" : p.alt_km > 1500 ? "MEO" : "LEO",
      note: `NORAD ${el.NORAD_CAT_ID} · CelesTrak`,
      track: trackOf(el),
    };
  });
}
function earthPlaces() {
  return EARTH_PLACES.map(([id, name, group, lat, lon, alt, note]) => ({ id, name, group, lat, lon, alt_km: alt, note }));
}
function earthNow(d, hour, site) {
  const h = hourDriver(d, hour);
  const lat = site ? site.lat : 0;
  const aurora = Math.max(0, Math.min(100, (Math.abs(lat) - (70 - h.kp * 2.2)) * 8 + h.kp * 4));
  return {
    kp: round(h.kp, 2),
    dst: round(h.dst, 1),
    aurora_pct: round(Math.max(0, aurora), 1),
    hf_blackout: round(Math.min(10, h.flare_index * 0.45 + Math.max(0, h.kp - 4) * 0.8), 2),
    pca: round(Math.min(10, h.proton_flux * 0.15), 2),
    gnss_scintillation: round(Math.min(10, 0.6 + h.kp * 0.35 + (Math.abs(lat) > 55 ? 1.2 : 0)), 2),
    aviation_usv_h: round(3.5 + h.kp * 0.35 + Math.log10(1 + h.proton_flux), 2),
    flare_index: round(h.flare_index, 2),
    flare_class: d.flare_class,
    g_scale: gScale(h.kp),
    sep: round(Math.min(10, h.proton_flux * 0.3), 2),
    imf_bz: round(h.bz, 2),
    f107: round(h.f107, 1),
    saa: round(Math.max(0, 2.2 - Math.abs(lat + 25) / 18), 2),
    range_hold: round(h.kp >= 6 ? 6 : h.kp >= 5 ? 3.5 : 0.4, 2),
    drag: round(0.4 + h.f107 / 180 + h.kp * 0.08, 2),
    charging: round(0.3 + Math.max(0, -h.bz) * 0.08 + h.kp * 0.1, 2),
    belt_dose: round(1 + h.kp * 0.2, 2),
    leo_dose_usv_h: round(8 + h.kp * 0.6 + h.proton_flux * 0.2, 2),
    eclipse: 0.35,
    mag_lat: round(lat, 1),
    lst_h: round((new Date().getUTCHours() + hour + (site ? site.lon : 0) / 15 + 48) % 24, 1),
  };
}
function earthForecast(site, d) {
  const keys = ["kp", "dst", "aurora_pct", "hf_blackout", "pca", "gnss_scintillation", "aviation_usv_h", "flare_index", "sep", "imf_bz", "f107", "range_hold", "saa", "drag", "charging", "belt_dose", "leo_dose_usv_h"];
  const series = { time: [], site };
  keys.forEach((k) => { series[k] = []; });
  const now = earthNow(d, 0, site);
  for (let h = 0; h < 25; h++) {
    const n = earthNow(d, h, site);
    series.time.push(h);
    keys.forEach((k) => series[k].push(n[k]));
  }
  return {
    ...series,
    now: {
      site,
      nowcast: now,
      alerts: [{
        level: now.kp >= 5 ? "caution" : "ok",
        title: now.kp >= 5 ? `${now.g_scale} in progress` : "Live SWPC",
        body: `Kp ${now.kp} ${now.g_scale} · GOES ${d.flare_class} · F10.7 ${round(d.f107, 0)} sfu · Dst ${round(d.dst, 0)} nT.`,
      }],
    },
    channels: [
      { id: "kp", label: "Kp", unit: "" },
      { id: "dst", label: "Dst", unit: "nT" },
      { id: "aurora_pct", label: "Aurora", unit: "%" },
      { id: "hf_blackout", label: "HF blackout", unit: "index" },
      { id: "gnss_scintillation", label: "GNSS scintillation", unit: "index" },
      { id: "aviation_usv_h", label: "Aviation dose", unit: "µSv/h" },
    ],
    source: "noaa-swpc",
  };
}
function auroraBlobs(d) {
  const edge = 70 - d.kp * 2.1;
  const blobs = [];
  for (const sign of [1, -1]) {
    for (let lon = -180; lon < 180; lon += 30) {
      blobs.push({ type: "aurora", lat: sign * edge, lon, intensity: Math.min(1, 0.25 + d.kp / 9) });
    }
  }
  if (d.flare_index >= 3) blobs.push({ type: "hf", lat: 0, lon: 0, intensity: Math.min(1, d.flare_index / 8) });
  if (d.proton_flux > 1) blobs.push({ type: "pca", lat: 75, lon: 0, intensity: Math.min(1, d.proton_flux / 20) }, { type: "pca", lat: -75, lon: 20, intensity: Math.min(1, d.proton_flux / 20) });
  blobs.push({ type: "gnss", lat: 65, lon: -150, intensity: Math.min(1, 0.2 + d.kp / 10) }, { type: "gnss", lat: -62, lon: 140, intensity: Math.min(1, 0.2 + d.kp / 10) });
  return blobs;
}
function level(v, caution, nogo) {
  if (v >= nogo) return "nogo";
  if (v >= caution) return "caution";
  return "go";
}
function earthMission(body, d) {
  const hours = Math.max(1, num(body.hours, 6));
  const t0 = num(body.t0_h, 0);
  const alt = Math.max(0, num(body.alt2_km, 400));
  const windows = [];
  for (let i = 0; i < 12; i++) {
    const start = i * 2;
    const n = earthNow(d, start, { lat: num(body.lat1, 0), lon: num(body.lon1, 0) });
    const score = Math.round(Math.max(8, Math.min(96, 90 - Math.max(0, n.kp - 3) * 12 - n.hf_blackout * 3 - n.range_hold * 4)));
    const status = score >= 70 ? "go" : score >= 52 ? "caution" : "nogo";
    windows.push({ label: `+${start}h`, start_offset_h: start, score, status, kp: n.kp, gnss: n.gnss_scintillation, saa: n.saa, range_hold: n.range_hold });
  }
  const best = windows.slice().sort((a, b) => b.score - a.score)[0];
  const active = windows.find((w) => w.start_offset_h === t0) || best;
  const samples = [];
  const nSamp = Math.max(8, hours * 2);
  for (let i = 0; i < nSamp; i++) {
    const u = i / (nSamp - 1);
    const hour = u * hours;
    const phase = hour < hours * 0.12 ? "ascent" : hour > hours * 0.88 ? "descent" : "on-orbit";
    const lat = num(body.lat1, 0) + (num(body.lat2, 0) - num(body.lat1, 0)) * u;
    const lon = num(body.lon1, 0) + (num(body.lon2, 0) - num(body.lon1, 0)) * u;
    const n = earthNow(d, t0 + hour, { lat, lon });
    samples.push({
      hour, phase, lat, lon,
      alt_km: phase === "on-orbit" ? alt : Math.max(0, alt * (phase === "ascent" ? u / 0.12 : (1 - u) / 0.12)),
      kp: n.kp, saa: n.saa, gnss: n.gnss_scintillation,
    });
  }
  const worstN = earthNow(d, t0, { lat: num(body.lat1, 0), lon: num(body.lon1, 0) });
  const matrix = {
    geomagnetic: level(worstN.kp, 5, 7),
    hf_blackout: level(worstN.hf_blackout, 3, 6),
    gnss: level(worstN.gnss_scintillation, 3, 6),
    saa: level(worstN.saa, 3, 6),
    sep: level(worstN.sep, 3, 6),
    flare: level(worstN.flare_index, 4, 7),
    range_hold: level(worstN.range_hold, 3, 6),
    drag: level(worstN.drag, 3, 6),
    charging: level(worstN.charging, 3, 6),
    comms: level(worstN.hf_blackout, 3, 6),
  };
  return {
    name: body.name || "Corridor",
    status: active.status,
    score: active.score,
    summary: `Live NOAA window. Kp ${worstN.kp} ${worstN.g_scale}, GOES ${d.flare_class}. This is a planning helper, not a range commit.`,
    reasons: [
      `Kp forecast ${worstN.kp} (${worstN.g_scale}) from SWPC.`,
      `GOES X-ray class ${d.flare_class}.`,
      "Best slot is the highest score in the next 24 h.",
    ],
    vehicle_label: body.vehicle,
    crew: body.crew,
    peak_alt_km: alt,
    ground_track_km: Math.abs(num(body.lon2, 0) - num(body.lon1, 0)) * 111,
    t0_h: t0,
    hours,
    hazard_matrix: matrix,
    worst: { kp: worstN.kp, hf: worstN.hf_blackout, gnss: worstN.gnss_scintillation, saa: worstN.saa, sep: worstN.sep, flare: worstN.flare_index, range_hold: worstN.range_hold, drag: worstN.drag, charging: worstN.charging, comms: worstN.hf_blackout },
    windows,
    best_window: best,
    samples,
    source: "noaa-swpc",
  };
}
function clock(body, hour, d) {
  const when = Date.now() + hour * 3600000;
  const sub = body === "sun" ? { lat: 0, lon: 0 } : body === "mercury" ? { lat: 0, lon: round(wrap((when / 86400000) * (360 / 175.9)), 2) } : moonSubsolar(when);
  const day = when / 86400000;
  const merc = wrap(252 + (360 / 87.969) * day);
  const earth = wrap(100 + (360 / 365.25) * day);
  const venus = wrap(181 + (360 / 224.7) * day);
  return {
    body, hour,
    subsolar: sub,
    carrington_deg_per_hour: 13.2 / 24,
    phase: { name: body === "moon" ? (sub.phase < 0.5 ? "waxing" : "waning") : "live" },
    drivers: { kp: d.kp, goes_class: d.flare_class, f107: d.f107, bz: d.bz, cusp_latitude_deg: 55 },
    planets: [
      { id: "mercury", name: "Mercury", lat: 0, lon: round(wrap(merc - earth), 2) },
      { id: "venus", name: "Venus", lat: 0, lon: round(wrap(venus - earth), 2) },
      { id: "earth", name: "Earth", lat: 0, lon: 0 },
    ],
    source: "noaa-swpc",
  };
}
async function proxyImage(url, mime) {
  const r = await fetch(url, { headers: { "User-Agent": UA } });
  if (!r.ok) return json({ error: "upstream " + r.status }, 502);
  const buf = await r.arrayBuffer();
  if (!buf || buf.byteLength < 200) return json({ error: "empty image" }, 502);
  return new Response(buf, {
    headers: {
      "content-type": r.headers.get("content-type") || mime,
      "cache-control": "public, max-age=3600",
      "access-control-allow-origin": "*",
    },
  });
}
async function luna(body) {
  const message = String(body.message || body.question || "").slice(0, 2000);
  const snap = JSON.stringify(body.context || body.snapshot || {}).slice(0, 1600);
  const sys = "You are Luna, a space-weather assistant for LIPAS mission ops. Answer in plain English, under 140 words. Use the snapshot. Say when a value is an estimate. Do not print hidden reasoning.";
  if (process.env.OPENAI_API_KEY) {
    try {
      const r = await fetch("https://api.openai.com/v1/chat/completions", {
        method: "POST",
        headers: { "content-type": "application/json", authorization: "Bearer " + process.env.OPENAI_API_KEY },
        body: JSON.stringify({
          model: "gpt-4o-mini",
          messages: [{ role: "system", content: sys }, { role: "user", content: message + "\n\nSnapshot:\n" + snap }],
        }),
      });
      const data = await r.json();
      const text = data && data.choices && data.choices[0] && data.choices[0].message && data.choices[0].message.content;
      if (text) return json({ answer: text, source: "openai" });
    } catch (_) {}
  }
  try {
    const r = await fetch("https://text.pollinations.ai/openai", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        model: "openai",
        messages: [{ role: "system", content: sys }, { role: "user", content: message + "\n\nSnapshot:\n" + snap }],
      }),
    });
    const data = await r.json();
    const text = data && data.choices && data.choices[0] && data.choices[0].message && data.choices[0].message.content;
    if (text) return json({ answer: text, source: "pollinations" });
  } catch (_) {}
  return json({ answer: "I could not reach the language model. The snapshot is still on the board. Try again in a moment.", source: "lipas-local" });
}
export default async function handler(request) {
  const url = new URL(request.url);
  const path = url.pathname.replace(/\/$/, "") || "/";
  if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: { "access-control-allow-origin": "*", "access-control-allow-methods": "GET,POST,OPTIONS", "access-control-allow-headers": "content-type" } });
  try {
    if (path.startsWith("/api/trek/")) {
      const sub = path.slice("/api/trek/".length);
      if (!sub.startsWith("Mercury/") || sub.includes("..")) return json({ error: "not allowed" }, 404);
      return proxyImage("https://trek.nasa.gov/tiles/" + sub, "image/jpeg");
    }
    if (path === "/api/solar/sdo" || path === "/api/solar/synoptic") {
      return proxyImage("https://sdo.gsfc.nasa.gov/assets/img/latest/latest_1024_HMII.jpg", "image/jpeg");
    }
    if (path.startsWith("/api/solar/tiles/")) return json({ error: "use the SDO disk" }, 404);
    const d = await loadDrivers();
    if (path === "/api/real-data-status") {
      return json({
        available: true,
        model_loaded: false,
        message: "Live NOAA SWPC drivers on Netlify. Trained model weights run on the Flask server.",
        drivers: { sources: d.sources, kp_index: d.kp, f107: d.f107, proton_flux: d.proton_flux, dst: d.dst, flare_class: d.flare_class },
      });
    }
    if (path === "/api/capability") return json({ model_generation: "live-swpc", model_loaded: false, note: "Weights are not on this host." });
    if (path === "/api/environmental-data" || path === "/api/forecast") {
      const lat = num(url.searchParams.get("lat"), -89.68);
      const lon = num(url.searchParams.get("lon"), 166.15);
      const hours = path === "/api/forecast" ? num(url.searchParams.get("hours"), 48) : 48;
      const series = moonForecast(lat, lon, hours, d);
      if (path === "/api/environmental-data") {
        return json({
          radiation: series.radiation[0], temperature: series.temperature[0], dust: series.dust[0],
          solar_activity: series.solar[0], moonquakes: series.moonquakes[0], micrometeorites: series.micrometeorites[0],
          accuracy: 72, model_loaded: false, source: series.source, time: series.time,
          radiation_series: series.radiation, temperature_series: series.temperature, dust_series: series.dust,
          solar_series: series.solar, moonquakes_series: series.moonquakes, micrometeorites_series: series.micrometeorites,
        });
      }
      return json(series);
    }
    if (path === "/api/hazard-grid") {
      const times = String(url.searchParams.get("times") || "0").split(",").map((t) => num(t, 0));
      return json(hazardGrid(url.searchParams.get("step"), times, d));
    }
    if (path === "/api/solar/disk") {
      const max = Math.max(1, num(url.searchParams.get("max"), 40));
      const spots = d.spots.slice(0, max);
      return json({
        observed_date: d.observed_date,
        intensity: round(Math.min(1, 0.3 + d.flare_index / 12 + spots.length / 30), 3),
        flare_class: d.flare_class,
        xray_flux: d.xray_flux,
        drivers: { f107: d.f107, flare_class: d.flare_class, flare_index: d.flare_index, kp_index: d.kp, dst: d.dst, proton_flux: d.proton_flux, sources: d.sources },
        spots, spot_count: spots.length, visible_count: spots.filter((s) => s.visible).length, source: "noaa-swpc",
      });
    }
    if (path === "/api/globe/clock") return json(clock(url.searchParams.get("body") || "moon", num(url.searchParams.get("hour"), 0), d));
    if (path === "/api/mercury/sites") {
      const rows = [];
      for (const [id, name, lat, lon, group, note] of MERCURY_SITES) {
        if (id === "overview") continue;
        const st = mercuryAt({ id, name, lat, lon, group, note }, d, 0, Date.now());
        rows.push({ id, name, lat, lon, group, note, ...st.prediction, temperature_k: round(st.prediction.temperature + 273.15, 1), lst_h: st.lst_h, day_night: st.day_night, standoff_rm: st.magnetosphere.standoff_rm, p_dyn_npa: st.physics.p_dyn_npa, imf_bz: st.wind_mercury.imf_bz, kp: st.physics.kp_index, flare_class: d.flare_class, alerts: st.alerts });
      }
      return json({ sites: rows, source: "noaa-swpc+mercury-physics", drivers: { sources: d.sources, flare_class: d.flare_class, f107: d.f107 } });
    }
    if (path === "/api/mercury/forecast" || path === "/api/mercury/state") {
      const id = url.searchParams.get("site") || url.searchParams.get("site_id") || "equator";
      const found = MERCURY_SITES.find((s) => s[0] === id) || MERCURY_SITES.find((s) => s[0] === "equator");
      const site = { id: found[0] === "overview" ? "equator" : found[0], name: found[1], lat: found[2], lon: found[3], group: found[4], note: found[5] };
      if (path === "/api/mercury/state") {
        const st = mercuryAt(site, d, num(url.searchParams.get("hour"), 0), Date.now());
        return json(st);
      }
      const hours = Math.max(1, Math.min(48, num(url.searchParams.get("hours"), 24)));
      const keys = ["time", "solar", "radiation", "temperature", "temperature_k", "standoff_rm", "p_dyn_npa", "imf_bz", "imf_b_mag", "kp", "lst", "illumination", "sep", "protons", "flares", "cme", "storm", "f107", "dst", "flare_index", "density", "speed", "confidence_series"];
      const series = Object.fromEntries(keys.map((k) => [k, []]));
      for (let h = 0; h < hours; h++) {
        const st = mercuryAt(site, d, h, Date.now());
        series.time.push(h);
        series.solar.push(st.prediction.solar);
        series.radiation.push(st.prediction.radiation);
        series.temperature.push(st.prediction.temperature);
        series.temperature_k.push(round(st.prediction.temperature + 273.15, 1));
        series.standoff_rm.push(st.magnetosphere.standoff_rm);
        series.p_dyn_npa.push(st.physics.p_dyn_npa);
        series.imf_bz.push(st.wind_mercury.imf_bz);
        series.imf_b_mag.push(st.wind_mercury.imf_b_mag);
        series.kp.push(st.physics.kp_index);
        series.lst.push(st.lst_h);
        series.illumination.push(st.illumination);
        series.sep.push(round(Math.min(10, st.prediction.radiation * 20), 2));
        series.protons.push(round(Math.log10(1 + st.physics.proton_flux) * 2, 2));
        series.flares.push(st.physics.flare_index);
        series.flare_index.push(st.physics.flare_index);
        series.cme.push(round(Math.max(0, st.physics.kp_index - 2) * 0.4, 2));
        series.storm.push(st.physics.kp_index >= 5 ? 1 : 0);
        series.f107.push(st.physics.f107);
        series.dst.push(st.physics.dst);
        series.density.push(st.wind_mercury.density);
        series.speed.push(st.wind_mercury.speed);
        series.confidence_series.push(70);
      }
      const now = mercuryAt(site, d, 0, Date.now());
      return json({ ...series, now, site: now.site, r_au: now.r_au, source: now.source, flare_class: d.flare_class, confidence_pct: 70, confidence: now.confidence, driver_sources: d.sources });
    }
    if (path === "/api/earth/sites") {
      return json({ sites: earthPlaces(), source: "lipas-catalog" });
    }
    if (path === "/api/earth/satellites") {
      const hour = num(url.searchParams.get("hour"), 0);
      const satellites = await loadSats(hour);
      return json({ satellites, source: "celestrak", count: satellites.length });
    }
    if (path === "/api/earth/forecast" || path === "/api/earth/state") {
      const id = url.searchParams.get("site") || "overview";
      const places = earthPlaces();
      let site = places.find((s) => s.id === id) || places[0];
      if (!places.find((s) => s.id === id)) {
        const sats = await loadSats(num(url.searchParams.get("hour"), 0));
        const sat = sats.find((s) => s.id === id);
        if (sat) site = { ...sat, group: "satellite" };
      }
      if (path === "/api/earth/state") {
        const n = earthNow(d, num(url.searchParams.get("hour"), 0), site);
        return json({ site, nowcast: n, alerts: earthForecast(site, d).now.alerts, source: "noaa-swpc" });
      }
      const fc = earthForecast(site, d);
      const satellites = (await loadSats(0)).filter((s) => /ISS|CSS|HST|TIANGONG|HUBBLE|GOES|TERRA|AQUA|NOAA/i.test(s.name)).slice(0, 12);
      return json({ ...fc, satellites });
    }
    if (path === "/api/earth/hazards") return json({ blobs: auroraBlobs(d), source: "noaa-swpc" });
    if (path === "/api/earth/mission" && request.method === "POST") {
      const body = await request.json().catch(() => ({}));
      return json(earthMission(body, d));
    }
    if (path === "/api/luna-chat" && request.method === "POST") {
      const body = await request.json().catch(() => ({}));
      return luna(body);
    }
    if (path === "/api/mission/plan" || path === "/api/mission/eva-now" || path === "/api/mission/pdf") {
      return json({ error: "use onboard planner" }, 501);
    }
    return json({ error: "no live route", path }, 404);
  } catch (err) {
    return json({ error: String(err && err.message ? err.message : err) }, 500);
  }
}
export const config = { path: "/api/*" };
