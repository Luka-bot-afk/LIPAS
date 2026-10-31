(function () {
  "use strict";
  const api = (p) => (typeof window.lipasApiUrl === "function" ? window.lipasApiUrl(p) : p);
  const PRESETS = [
    { name: "Starbase → KSC", meta: "LEO · Gulf corridor", from: "starbase", to: "ksc", alt2: 220, vehicle: "leo", hours: 6 },
    { name: "KSC → ISS", meta: "Crewed rendezvous · 420 km", from: "ksc", to: "iss", alt2: 420, vehicle: "crew_iss", hours: 8, crew: "crew" },
    { name: "Vandenberg polar", meta: "SSO · Fairbanks downrange", from: "vandenberg", to: "fairbanks", alt2: 700, vehicle: "sso", hours: 3 },
    { name: "Kourou GEO", meta: "GTO · GOES-16", from: "kourou", to: "goes16", alt2: 35786, vehicle: "gto", hours: 6 },
    { name: "Mahia sun-sync", meta: "SSO · Terra intercept", from: "mahia", to: "terra", alt2: 705, vehicle: "sso", hours: 3 },
    { name: "Poker Flat sounding", meta: "Suborbital · Alaska", from: "poker", to: "fairbanks", alt2: 0, vehicle: "suborbital", hours: 1 },
    { name: "ISS reentry", meta: "Entry corridor · KSC", from: "iss", to: "ksc", alt2: 0, vehicle: "reentry", hours: 1 },
  ];
  const MATRIX = [
    { id: "geomagnetic", label: "Geomagnetic", key: "kp", unit: "Kp" },
    { id: "hf_blackout", label: "HF blackout", key: "hf", unit: "" },
    { id: "gnss", label: "GNSS scint.", key: "gnss", unit: "" },
    { id: "saa", label: "SAA", key: "saa", unit: "" },
    { id: "sep", label: "SEP", key: "sep", unit: "" },
    { id: "flare", label: "Flare / X-ray", key: "flare", unit: "" },
    { id: "range_hold", label: "Range hold", key: "range_hold", unit: "" },
    { id: "drag", label: "Drag", key: "drag", unit: "" },
    { id: "charging", label: "Charging", key: "charging", unit: "" },
    { id: "comms", label: "Comms", key: "comms", unit: "" },
  ];
  const PHASE_COLOR = {
    ascent: "#3ecf8e",
    apogee: "#7ee0b0",
    descent: "#5ab88a",
    deorbit: "#e0b14a",
    entry: "#e07a4a",
    terminal: "#e25b5b",
    "GTO coast": "#6eb6ff",
    circularize: "#7ee0b0",
    GEO: "#c9a06a",
    coast: "#5aa0d4",
    insertion: "#4ee09a",
    "on-orbit": "#9ec9b4",
  };
  const OFFLINE_SITES = [
    { id: "ksc", name: "Kennedy Space Center", group: "launch", lat: 28.57, lon: -80.65, alt_km: 0 },
    { id: "starbase", name: "Starbase", group: "launch", lat: 25.99, lon: -97.16, alt_km: 0 },
    { id: "vandenberg", name: "Vandenberg", group: "launch", lat: 34.74, lon: -120.57, alt_km: 0 },
    { id: "kourou", name: "Guiana Space Centre", group: "launch", lat: 5.24, lon: -52.77, alt_km: 0 },
    { id: "mahia", name: "Mahia", group: "launch", lat: -39.26, lon: 177.86, alt_km: 0 },
    { id: "poker", name: "Poker Flat", group: "launch", lat: 65.13, lon: -147.47, alt_km: 0 },
    { id: "fairbanks", name: "Fairbanks", group: "city", lat: 64.84, lon: -147.72, alt_km: 0 },
    { id: "iss", name: "ISS", group: "satellite", lat: 12, lon: -40, alt_km: 420 },
    { id: "goes16", name: "GOES-16", group: "satellite", lat: 0, lon: -75.2, alt_km: 35786 },
    { id: "terra", name: "Terra", group: "satellite", lat: -10, lon: 40, alt_km: 705 },
  ];
  let sites = [];
  let plan = null;
  let hoverIdx = -1;
  function $(id) { return document.getElementById(id); }
  function fmt(v, d) {
    if (v == null || !Number.isFinite(Number(v))) return "—";
    return Number(v).toFixed(d);
  }
  function siteById(id) { return sites.find((s) => s.id === id); }
  function siteLabel(id) {
    const s = siteById(id);
    return s ? s.name : id || "Waypoint";
  }
  function coordLine(lat, lon, alt) {
    const ns = Number(lat) >= 0 ? "N" : "S";
    const ew = Number(lon) >= 0 ? "E" : "W";
    return `${fmt(Math.abs(lat), 2)}°${ns}  ${fmt(Math.abs(lon), 2)}°${ew}\n${fmt(alt, 0)} km`;
  }
  function fillSelects() {
    const groups = [
      ["launch", "Launch pads"],
      ["satellite", "Satellites"],
      ["city", "Cities / aurora"],
    ];
    const html = groups.map(([g, label]) => {
      const opts = sites.filter((s) => s.group === g)
        .map((s) => `<option value="${s.id}">${s.name}</option>`).join("");
      return `<optgroup label="${label}">${opts}</optgroup>`;
    }).join("");
    $("inp-from").innerHTML = html;
    $("inp-to").innerHTML = html;
    $("inp-from").value = "starbase";
    $("inp-to").value = "ksc";
  }
  function applySite(sel, latId, lonId, altId) {
    const s = siteById(sel.value);
    if (!s) return;
    $(latId).value = s.lat;
    $(lonId).value = s.lon;
    if (altId) $(altId).value = s.alt_km || (s.group === "satellite" ? 400 : 0);
    updateRouteMeta();
  }
  function updateRouteMeta() {
    const a = siteById($("inp-from").value);
    const b = siteById($("inp-to").value);
    $("from-meta").textContent = a
      ? coordLine(a.lat, a.lon, $("alt1").value || a.alt_km || 0)
      : coordLine($("lat1").value, $("lon1").value, $("alt1").value);
    $("to-meta").textContent = b
      ? coordLine(b.lat, b.lon, $("alt2").value || b.alt_km || 0)
      : coordLine($("lat2").value, $("lon2").value, $("alt2").value);
  }
  function payload() {
    const inc = $("inp-inc").value;
    return {
      name: $("inp-name").value,
      from_id: $("inp-from").value,
      to_id: $("inp-to").value,
      lat1: Number($("lat1").value),
      lon1: Number($("lon1").value),
      alt1_km: Number($("alt1").value),
      lat2: Number($("lat2").value),
      lon2: Number($("lon2").value),
      alt2_km: Number($("alt2").value),
      hours: Number($("hours").value),
      t0_h: Number($("t0").value),
      risk_posture: $("risk").value,
      vehicle: $("inp-vehicle").value,
      crew: $("inp-crew").value,
      inclination: inc === "" ? null : Number(inc),
    };
  }
  function setBusy(on) {
    document.body.classList.toggle("planner-busy", on);
    $("btn-run").textContent = on ? "Computing…" : "Run trajectory plan";
  }
  function renderPlan(p) {
    plan = p;
    const status = p.status || "caution";
    const score = Number(p.score) || 0;
    $("go-dial").dataset.status = status;
    $("go-label").textContent = status.toUpperCase();
    $("go-score").textContent = `${p.score ?? "—"} / 100`;
    const ring = $("go-ring");
    if (ring) ring.style.strokeDashoffset = String(100 - Math.max(0, Math.min(100, score)));
    const bits = [p.vehicle_label, p.crew === "crew" ? "crewed" : "cargo", p.peak_alt_km != null ? `peak ${fmt(p.peak_alt_km, 0)} km` : ""]
      .filter(Boolean);
    $("go-sub").textContent = p.summary || bits.join(" · ");
    $("go-reasons").innerHTML = (p.reasons || []).map((r) => `<li>${r}</li>`).join("");
    $("ops-banner").dataset.kind = status;
    $("active-site").textContent = p.name || "Corridor";
    $("kpi-row").innerHTML = [
      ["Peak alt", `${fmt(p.peak_alt_km, 0)} km`],
      ["Ground track", `${fmt(p.ground_track_km, 0)} km`],
      ["T0", `+${fmt(p.t0_h, 0)} h`],
      ["Duration", `${p.hours} h`],
    ].map(([k, v]) => `<div class="kpi"><div class="k">${k}</div><div class="v">${v}</div></div>`).join("");
    const worst = p.worst || {};
    $("hz-grid").innerHTML = MATRIX.map((m) => {
      const st = (p.hazard_matrix || {})[m.id] || "go";
      const val = worst[m.key];
      const pct = Math.max(0, Math.min(100, (Number(val) || 0) * 10));
      return `<div class="hz-cell ${st}">
        <div class="hk">${m.label}</div>
        <div class="hv">${st.toUpperCase()}</div>
        <div class="hn">${val == null ? "—" : fmt(val, 1)}${m.unit ? " " + m.unit : ""}</div>
        <div class="hbar"><i style="width:${pct}%;background:currentColor"></i></div>
      </div>`;
    }).join("");
    renderWindows(p);
    renderPhases(p.samples || []);
    renderSamples(p.samples || []);
    drawAll();
    $("loadingScreen")?.classList.add("hidden");
    setBusy(false);
  }
  function renderWindows(p) {
    const windows = p.windows || [];
    const bestH = p.best_window && p.best_window.start_offset_h;
    const t0 = Number(p.t0_h);
    $("window-strip").innerHTML = windows.map((w) => {
      const hgt = Math.max(18, Math.min(100, Number(w.score) || 0));
      const on = Number(w.start_offset_h) === t0 ? " active" : "";
      const best = w.start_offset_h === bestH ? " best" : "";
      return `<button type="button" class="win-cell ${w.status}${on}${best}" data-t0="${w.start_offset_h}">
        <span class="fill" style="height:${hgt}%"></span>
        <span class="wh">${w.label}</span>
        <span class="ws">${w.score ?? "—"}</span>
      </button>`;
    }).join("");
    $("window-strip").querySelectorAll(".win-cell").forEach((el) => {
      el.addEventListener("click", () => {
        $("t0").value = el.dataset.t0;
        run().catch(() => setBusy(false));
      });
    });
    const cur = windows.find((w) => Number(w.start_offset_h) === t0) || p.best_window;
    const best = p.best_window;
    if (cur) {
      $("window-detail").textContent =
        `Active ${cur.label} · ${cur.status.toUpperCase()} ${cur.score}  ·  Kp ${fmt(cur.kp, 1)}  ·  GNSS ${fmt(cur.gnss, 1)}  ·  SAA ${fmt(cur.saa, 1)}  ·  hold ${fmt(cur.range_hold, 1)}`
        + (best && best.start_offset_h !== cur.start_offset_h
          ? `   ·   Best slot ${best.label} (${best.status.toUpperCase()} ${best.score})`
          : "");
    }
    $("window-hint").textContent = best
      ? `Best open slot ${best.label} · ${best.status.toUpperCase()} ${best.score}`
      : "Click a slot to set T0 and recompute";
  }
  function renderPhases(samples) {
    if (!samples.length) { $("phase-rail").innerHTML = ""; return; }
    const segs = [];
    samples.forEach((s) => {
      const last = segs[segs.length - 1];
      if (!last || last.phase !== s.phase) segs.push({ phase: s.phase, n: 1, alt: s.alt_km });
      else { last.n += 1; last.alt = s.alt_km; }
    });
    const total = segs.reduce((a, s) => a + s.n, 0) || 1;
    $("phase-rail").innerHTML = segs.map((s) => {
      const col = PHASE_COLOR[s.phase] || "#3ecf8e";
      return `<div class="phase-seg" style="flex:${s.n / total};border-top-color:${col}">
        ${s.phase}<b>${fmt(s.alt, 0)} km · ${Math.round(100 * s.n / total)}%</b>
      </div>`;
    }).join("");
  }
  function renderSamples(samples) {
    const rows = samples.filter((_, i) => i % 4 === 0);
    $("sample-list").innerHTML =
      `<div class="sample-row head"><span>T+</span><span>Phase</span><span>Position</span><span>Alt</span><span>Kp</span><span>SAA</span></div>`
      + rows.map((s) =>
        `<div class="sample-row">
          <span>+${fmt(s.hour, 1)}h</span>
          <span class="ph">${s.phase || "—"}</span>
          <span>${fmt(s.lat, 2)}°, ${fmt(s.lon, 2)}°</span>
          <span>${fmt(s.alt_km, 0)} km</span>
          <span>${fmt(s.kp, 1)}</span>
          <span>${fmt(s.saa, 1)}</span>
        </div>`
      ).join("");
  }
  function wrapLon(lon) {
    let x = Number(lon);
    while (x > 180) x -= 360;
    while (x < -180) x += 360;
    return x;
  }
  function bounds(samples) {
    const lats = samples.map((s) => s.lat);
    let lons = samples.map((s) => wrapLon(s.lon));
    const loLa = Math.min(...lats);
    const hiLa = Math.max(...lats);
    let loLo = Math.min(...lons);
    let hiLo = Math.max(...lons);
    if (hiLo - loLo > 180) {
      lons = lons.map((x) => (x < 0 ? x + 360 : x));
      loLo = Math.min(...lons);
      hiLo = Math.max(...lons);
    }
    const padLa = Math.max(6, (hiLa - loLa) * 0.28);
    const padLo = Math.max(8, (hiLo - loLo) * 0.28);
    return {
      loLa: loLa - padLa, hiLa: hiLa + padLa,
      loLo: loLo - padLo, hiLo: hiLo + padLo,
      lons,
    };
  }
  function drawAll() {
    const samples = (plan && plan.samples) || [];
    drawPath(samples);
    drawAlt(samples);
    drawGlobe(samples);
  }
  function drawGlobe(samples) {
    const c = $("globe3d");
    if (!c) return;
    const ctx = c.getContext("2d");
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const w = Math.max(320, c.clientWidth || 720);
    const h = 280;
    c.width = w * dpr;
    c.height = h * dpr;
    c.style.height = h + "px";
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const light = document.documentElement.dataset.theme === "light";
    ctx.fillStyle = light ? "#e7e1d6" : "#07140f";
    ctx.fillRect(0, 0, w, h);
    const cx = w * 0.38;
    const cy = h * 0.52;
    const R = Math.min(118, h * 0.38);
    const g = ctx.createRadialGradient(cx - 30, cy - 36, 10, cx, cy, R);
    g.addColorStop(0, "#d7f3e4");
    g.addColorStop(0.45, "#2f6d52");
    g.addColorStop(1, light ? "#8fbfa6" : "#07140f");
    ctx.beginPath();
    ctx.arc(cx, cy, R, 0, Math.PI * 2);
    ctx.fillStyle = g;
    ctx.fill();
    ctx.save();
    ctx.beginPath();
    ctx.arc(cx, cy, R, 0, Math.PI * 2);
    ctx.clip();
    ctx.strokeStyle = "rgba(255,255,255,0.16)";
    for (let i = -3; i <= 3; i++) {
      const y = cy + Math.sin((i / 6) * Math.PI) * R;
      ctx.beginPath();
      ctx.ellipse(cx, y, Math.sqrt(Math.max(4, R * R - (y - cy) * (y - cy))), 3, 0, 0, Math.PI * 2);
      ctx.stroke();
    }
    ctx.restore();
    if (!samples.length) return;
    const maxAlt = Math.max(400, ...samples.map((s) => Number(s.alt_km) || 0));
    const project = (s) => {
      const lat = (Number(s.lat) * Math.PI) / 180;
      const lon = (Number(s.lon) * Math.PI) / 180;
      const lift = 1 + Math.min(0.55, (Number(s.alt_km) || 0) / maxAlt) * 0.45;
      const x = cx + Math.cos(lat) * Math.sin(lon) * R * lift;
      const y = cy - Math.sin(lat) * R * lift;
      const z = Math.cos(lat) * Math.cos(lon);
      return { x, y, z };
    };
    for (let i = 1; i < samples.length; i++) {
      const a = project(samples[i - 1]);
      const b = project(samples[i]);
      if (a.z < -0.05 && b.z < -0.05) continue;
      ctx.beginPath();
      ctx.moveTo(a.x, a.y);
      ctx.lineTo(b.x, b.y);
      ctx.strokeStyle = PHASE_COLOR[samples[i].phase] || "#3ecf8e";
      ctx.lineWidth = 2.4;
      ctx.stroke();
    }
    const end = project(samples[samples.length - 1]);
    ctx.fillStyle = "#e4c27a";
    ctx.beginPath();
    ctx.arc(end.x, end.y, 4.5, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = light ? "#1c1915" : "#d7f8e8";
    ctx.font = "12px IBM Plex Sans, sans-serif";
    ctx.fillText("Corridor in altitude", w * 0.68, 36);
    ctx.fillStyle = document.documentElement.dataset.theme === "light" ? "#5c564c" : "#8fb8a8";
    ctx.fillText(`Peak ${Math.round(maxAlt)} km`, w * 0.68, 56);
  }
  function drawPath(samples) {
    const c = $("pathCanvas");
    if (!c) return;
    const ctx = c.getContext("2d");
    const dpr = window.devicePixelRatio || 1;
    const w = Math.max(320, c.clientWidth || 640);
    const h = 220;
    c.width = w * dpr; c.height = h * dpr;
    c.style.height = h + "px";
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.fillStyle = document.documentElement.dataset.theme === "light" ? "#f7f4ee" : "#07140f";
    ctx.fillRect(0, 0, w, h);
    if (!samples.length) return;
    const b = bounds(samples);
    const px = (lon) => {
      let x = lon;
      if (b.hiLo > 180 && x < 0) x += 360;
      return 18 + ((x - b.loLo) / ((b.hiLo - b.loLo) || 1)) * (w - 36);
    };
    const py = (lat) => 22 + (1 - (lat - b.loLa) / ((b.hiLa - b.loLa) || 1)) * (h - 40);
    ctx.strokeStyle = "rgba(62,207,142,0.08)";
    ctx.lineWidth = 1;
    for (let i = 0; i <= 6; i++) {
      const y = 22 + (i / 6) * (h - 40);
      ctx.beginPath(); ctx.moveTo(18, y); ctx.lineTo(w - 18, y); ctx.stroke();
    }
    for (let i = 0; i <= 8; i++) {
      const x = 18 + (i / 8) * (w - 36);
      ctx.beginPath(); ctx.moveTo(x, 22); ctx.lineTo(x, h - 18); ctx.stroke();
    }
    const saa = { lat: -25, lon: -50, rla: 18, rlo: 38 };
    ctx.fillStyle = "rgba(226,91,91,0.12)";
    ctx.beginPath();
    ctx.ellipse(px(saa.lon), py(saa.lat), Math.abs(px(saa.lon + saa.rlo) - px(saa.lon)), Math.abs(py(saa.lat + saa.rla) - py(saa.lat)), 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "rgba(226,91,91,0.45)";
    ctx.font = "10px IBM Plex Sans, sans-serif";
    ctx.fillText("SAA", px(saa.lon) - 10, py(saa.lat));
    if (b.loLa < 0 && b.hiLa > 0) {
      ctx.strokeStyle = "rgba(126,224,176,0.28)";
      ctx.setLineDash([4, 5]);
      ctx.beginPath(); ctx.moveTo(18, py(0)); ctx.lineTo(w - 18, py(0)); ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = "rgba(158,201,180,0.7)";
      ctx.fillText("equator", 22, py(0) - 4);
    }
    for (let i = 1; i < samples.length; i++) {
      ctx.beginPath();
      ctx.moveTo(px(samples[i - 1].lon), py(samples[i - 1].lat));
      ctx.lineTo(px(samples[i].lon), py(samples[i].lat));
      ctx.strokeStyle = PHASE_COLOR[samples[i].phase] || "#3ecf8e";
      ctx.lineWidth = 3;
      ctx.shadowColor = ctx.strokeStyle;
      ctx.shadowBlur = 8;
      ctx.stroke();
      ctx.shadowBlur = 0;
    }
    const a = samples[0];
    const z = samples[samples.length - 1];
    ctx.fillStyle = "#7ee0b0";
    ctx.beginPath(); ctx.arc(px(a.lon), py(a.lat), 5, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = "#e0b14a";
    ctx.beginPath(); ctx.arc(px(z.lon), py(z.lat), 5, 0, Math.PI * 2); ctx.fill();
    if (hoverIdx >= 0 && samples[hoverIdx]) {
      const s = samples[hoverIdx];
      ctx.strokeStyle = "#e8f6ee";
      ctx.lineWidth = 1.5;
      ctx.beginPath(); ctx.arc(px(s.lon), py(s.lat), 7, 0, Math.PI * 2); ctx.stroke();
    }
    ctx.shadowBlur = 0;
    ctx.fillStyle = "#c5ddd0";
    ctx.font = "600 12px IBM Plex Sans, sans-serif";
    const fromN = siteLabel(plan && plan.from && plan.from.id);
    const toN = siteLabel(plan && plan.to && plan.to.id);
    ctx.fillText(fromN, Math.min(w - 120, px(a.lon) + 8), py(a.lat) - 8);
    ctx.fillText(toN, Math.min(w - 120, px(z.lon) + 8), py(z.lat) + 16);
    ctx.fillStyle = "#9ec9b4";
    ctx.font = "11px IBM Plex Sans, sans-serif";
    ctx.fillText("Ground track", 18, 16);
  }
  function drawAlt(samples) {
    const c = $("altCanvas");
    if (!c) return;
    const ctx = c.getContext("2d");
    const dpr = window.devicePixelRatio || 1;
    const w = Math.max(320, c.clientWidth || 640);
    const h = 176;
    c.width = w * dpr; c.height = h * dpr;
    c.style.height = h + "px";
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const light = document.documentElement.dataset.theme === "light";
    ctx.fillStyle = light ? "#f7f4ee" : "#07140f";
    ctx.fillRect(0, 0, w, h);
    if (!samples.length) return;
    const alts = samples.map((s) => Number(s.alt_km) || 0);
    const hi = Math.max(...alts, 1);
    const left = 48, right = 16, top = 22, bot = 28;
    const xAt = (i) => left + (i / Math.max(1, samples.length - 1)) * (w - left - right);
    const yAt = (alt) => top + (1 - alt / hi) * (h - top - bot);
    ctx.strokeStyle = "rgba(62,207,142,0.1)";
    ctx.fillStyle = "rgba(158,201,180,0.55)";
    ctx.font = "10px IBM Plex Sans, sans-serif";
    ctx.textAlign = "right";
    [0, 0.25, 0.5, 0.75, 1].forEach((f) => {
      const y = yAt(hi * f);
      ctx.beginPath(); ctx.moveTo(left, y); ctx.lineTo(w - right, y); ctx.stroke();
      ctx.fillText(fmt(hi * f, hi > 1000 ? 0 : 0) + " km", left - 6, y + 3);
    });
    ctx.textAlign = "left";
    ctx.beginPath();
    samples.forEach((s, i) => {
      const x = xAt(i), y = yAt(alts[i]);
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    });
    ctx.strokeStyle = "#7ee0b0";
    ctx.lineWidth = 2.2;
    ctx.stroke();
    ctx.lineTo(xAt(samples.length - 1), h - bot);
    ctx.lineTo(left, h - bot);
    ctx.closePath();
    ctx.fillStyle = "rgba(62,207,142,0.12)";
    ctx.fill();
    for (let i = 1; i < samples.length; i++) {
      ctx.beginPath();
      ctx.moveTo(xAt(i - 1), yAt(alts[i - 1]));
      ctx.lineTo(xAt(i), yAt(alts[i]));
      ctx.strokeStyle = PHASE_COLOR[samples[i].phase] || "#7ee0b0";
      ctx.lineWidth = 2.4;
      ctx.stroke();
    }
    if (hoverIdx >= 0 && samples[hoverIdx]) {
      const s = samples[hoverIdx];
      const x = xAt(hoverIdx);
      ctx.strokeStyle = "rgba(232,246,238,0.35)";
      ctx.beginPath(); ctx.moveTo(x, top); ctx.lineTo(x, h - bot); ctx.stroke();
      ctx.fillStyle = light ? "#1a1916" : "#e8f6ee";
      ctx.beginPath(); ctx.arc(x, yAt(alts[hoverIdx]), 4, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = light ? "#5c564c" : "#c5ddd0";
      ctx.font = "11px IBM Plex Sans, sans-serif";
      ctx.fillText(`${s.phase} · ${fmt(s.alt_km, 0)} km · Kp ${fmt(s.kp, 1)}`, Math.min(w - 180, x + 8), yAt(alts[hoverIdx]) - 8);
    }
    ctx.fillStyle = light ? "#5c564c" : "#9ec9b4";
    ctx.font = "11px IBM Plex Sans, sans-serif";
    ctx.fillText(`Altitude · peak ${fmt(hi, 0)} km`, left, 16);
  }
  function sampleAtEvent(canvas, ev) {
    const samples = (plan && plan.samples) || [];
    if (!samples.length) return -1;
    const r = canvas.getBoundingClientRect();
    const x = ev.clientX - r.left;
    const t = Math.max(0, Math.min(1, x / Math.max(1, r.width)));
    return Math.round(t * (samples.length - 1));
  }
  function onHover(ev) {
    const idx = sampleAtEvent(ev.currentTarget, ev);
    if (idx === hoverIdx) return;
    hoverIdx = idx;
    const s = plan && plan.samples && plan.samples[idx];
    if (s) {
      $("chart-hover").textContent =
        `T+${fmt(s.hour, 1)} h · ${s.phase} · ${fmt(s.lat, 2)}°, ${fmt(s.lon, 2)}° · ${fmt(s.alt_km, 0)} km · Kp ${fmt(s.kp, 1)} · SAA ${fmt(s.saa, 1)} · GNSS ${fmt(s.gnss_scintillation, 1)}`;
    }
    drawAll();
  }
  function downloadPDF() {
    if (!plan) { alert("Run a plan first."); return; }
    if (!window.jspdf || !window.jspdf.jsPDF) { alert("PDF still loading."); return; }
    const { jsPDF } = window.jspdf;
    const doc = new jsPDF("p", "mm", "a4");
    const M = 14;
    const PH = doc.internal.pageSize.height;
    let y = 20;
    const check = (n) => { if (y > PH - 16 - n) { doc.addPage(); y = 16; } };
    doc.setFontSize(18);
    doc.setTextColor(27, 107, 74);
    doc.text("L.I.P.A.S. Earth trajectory plan", M, y); y += 10;
    doc.setFontSize(11);
    doc.setTextColor(30, 40, 36);
    [
      `${plan.name}`,
      `Status: ${(plan.status || "").toUpperCase()} · score ${plan.score}`,
      `Vehicle: ${plan.vehicle_label || plan.vehicle} · ${plan.crew || "cargo"}`,
      `From ${fmt(plan.from.lat, 3)}°, ${fmt(plan.from.lon, 3)}° @ ${fmt(plan.from.alt_km, 0)} km`,
      `To ${fmt(plan.to.lat, 3)}°, ${fmt(plan.to.lon, 3)}° @ ${fmt(plan.to.alt_km, 0)} km`,
      `Duration ${plan.hours} h · T0 +${plan.t0_h} h · ${plan.risk_posture}`,
      `Peak altitude ${fmt(plan.peak_alt_km, 0)} km · ground track ${fmt(plan.ground_track_km, 0)} km`,
      plan.summary || "",
    ].forEach((line) => { check(8); doc.text(String(line), M, y); y += 7; });
    y += 4;
    doc.setFont("helvetica", "bold");
    doc.text("Hazard matrix", M, y); y += 7;
    doc.setFont("helvetica", "normal");
    Object.entries(plan.hazard_matrix || {}).forEach(([k, v]) => {
      check(6);
      doc.text(`${k.replace(/_/g, " ")}: ${String(v).toUpperCase()}`, M, y); y += 6;
    });
    y += 3;
    (plan.reasons || []).forEach((r) => { check(6); doc.text("• " + r, M, y); y += 6; });
    y += 4;
    doc.setFont("helvetica", "bold");
    check(8); doc.text("24 h windows", M, y); y += 7;
    doc.setFont("helvetica", "normal");
    (plan.windows || []).forEach((w) => {
      check(6);
      doc.text(`${w.label} ${w.status} score ${w.score}  Kp ${fmt(w.kp, 1)}  SAA ${fmt(w.saa, 1)}`, M, y);
      y += 6;
    });
    const nPages = doc.internal.getNumberOfPages();
    const PW = doc.internal.pageSize.width;
    for (let i = 1; i <= nPages; i++) {
      doc.setPage(i);
      doc.setFontSize(7);
      doc.setTextColor(120, 140, 130);
      doc.text("© 2026 Luka Takki · LIPAS", PW / 2, PH - 8, { align: "center" });
    }
    doc.save(`LIPAS_Earth_Mission_${Date.now()}.pdf`);
  }
  async function run() {
    setBusy(true);
    try {
      const r = await fetch(api("/api/earth/mission"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload()),
      });
      if (!r.ok) throw new Error("plan failed");
      renderPlan(await r.json());
    } catch (err) {
      renderPlan(localPlan(payload()));
    }
  }
  function applyBest() {
    if (!plan || !plan.best_window) return;
    $("t0").value = plan.best_window.start_offset_h;
    run().catch(() => setBusy(false));
  }
  function localPlan(body) {
    const hours = Math.max(1, Number(body.hours) || 6);
    const t0 = Number(body.t0_h) || 0;
    const alt = Math.max(0, Number(body.alt2_km) || 400);
    const windows = Array.from({ length: 12 }, (_, i) => {
      const start = i * 2;
      const kp = 1.8 + Math.sin(i / 2.2) * 1.1;
      const score = Math.round(82 - Math.abs(kp - 2) * 9 - (i % 5 === 4 ? 16 : 0));
      const status = score >= 70 ? "go" : score >= 52 ? "caution" : "nogo";
      return { label: `+${start}h`, start_offset_h: start, score, status, kp, gnss: 1.1 + (i % 3) * 0.4, saa: 0.3 + (i % 4) * 0.2, range_hold: i % 6 === 0 ? 2.4 : 0.2 };
    });
    const best = windows.slice().sort((a, b) => b.score - a.score)[0];
    const n = Math.max(8, hours * 2);
    const samples = Array.from({ length: n }, (_, i) => {
      const hour = (i / (n - 1)) * hours;
      const u = i / (n - 1);
      const phase = hour < hours * 0.12 ? "ascent" : hour > hours * 0.88 ? "descent" : "on-orbit";
      return {
        hour,
        phase,
        lat: body.lat1 + (body.lat2 - body.lat1) * u,
        lon: body.lon1 + (body.lon2 - body.lon1) * u,
        alt_km: phase === "on-orbit" ? alt : Math.max(0, alt * (phase === "ascent" ? u / 0.12 : (1 - u) / 0.12)),
        kp: 2.1 + Math.sin(i / 3) * 0.4,
        saa: 0.4,
        gnss: 1.2,
      };
    });
    const active = windows.find((w) => w.start_offset_h === t0) || best;
    return {
      name: body.name,
      status: active.status,
      score: active.score,
      summary: "Quiet-day corridor. This host has no live SWPC feed, so the window, track, and hazard board are a calm-day sketch you can still walk.",
      reasons: ["Departure and destination are filled from the onboard catalog.", "Recompute on the forecast service for a live commit call."],
      vehicle_label: body.vehicle,
      crew: body.crew,
      peak_alt_km: alt,
      ground_track_km: Math.abs(body.lon2 - body.lon1) * 111,
      t0_h: t0,
      hours,
      hazard_matrix: { geomagnetic: "go", hf_blackout: "go", gnss: "caution", saa: "go", sep: "go", flare: "go", range_hold: "go", drag: "go", charging: "go", comms: "go" },
      worst: { kp: 2.4, hf: 1.1, gnss: 2.2, saa: 0.4, sep: 0.6, flare: 1.4, range_hold: 0.2, drag: 0.8, charging: 0.5, comms: 1.2 },
      windows,
      best_window: best,
      samples,
      source: "offline-estimate",
    };
  }
  async function boot() {
    sites = OFFLINE_SITES.slice();
    try {
      const r = await fetch(api("/api/earth/sites"));
      if (r.ok) {
        const live = (await r.json()).sites || [];
        if (live.length) sites = live;
      }
    } catch (_) {}
    fillSelects();
    $("preset-row").innerHTML = PRESETS.map((p, i) =>
      `<button type="button" class="preset-card${i === 0 ? " active" : ""}" data-i="${i}">
        <span class="pn">${p.name}</span><span class="pm">${p.meta}</span>
      </button>`
    ).join("");
    $("preset-row").addEventListener("click", (e) => {
      const b = e.target.closest("button[data-i]");
      if (!b) return;
      const p = PRESETS[Number(b.dataset.i)];
      $("inp-name").value = p.name;
      $("inp-from").value = p.from;
      $("inp-to").value = p.to;
      $("inp-vehicle").value = p.vehicle || "leo";
      $("inp-crew").value = p.crew || "cargo";
      $("hours").value = p.hours || 6;
      applySite($("inp-from"), "lat1", "lon1", "alt1");
      applySite($("inp-to"), "lat2", "lon2", "alt2");
      $("alt2").value = p.alt2;
      updateRouteMeta();
      $("preset-row").querySelectorAll("button").forEach((x) => x.classList.toggle("active", x === b));
      run().catch(() => setBusy(false));
    });
    $("inp-from").addEventListener("change", () => applySite($("inp-from"), "lat1", "lon1", "alt1"));
    $("inp-to").addEventListener("change", () => applySite($("inp-to"), "lat2", "lon2", "alt2"));
    ["lat1", "lon1", "alt1", "lat2", "lon2", "alt2"].forEach((id) => {
      $(id).addEventListener("input", updateRouteMeta);
    });
    $("inp-vehicle").addEventListener("change", () => {
      const v = $("inp-vehicle").value;
      if (v === "gto") $("alt2").value = 35786;
      if (v === "crew_iss") { $("alt2").value = 420; $("hours").value = 8; }
      if (v === "suborbital") { $("alt2").value = 0; $("hours").value = 1; }
      if (v === "reentry") { $("hours").value = 1; }
      updateRouteMeta();
    });
    $("btn-run").addEventListener("click", () => run().catch(() => setBusy(false)));
    $("btn-best").addEventListener("click", applyBest);
    $("btn-pdf").addEventListener("click", downloadPDF);
    $("btn-luna")?.addEventListener("click", async () => {
      const out = $("luna-plan-out");
      if (!out) return;
      out.textContent = "Thinking through the corridor…";
      const ask = window.lipasAskLuna;
      if (typeof ask !== "function") {
        out.textContent = "Luna is not on this page yet.";
        return;
      }
      const text = await ask(
        "Review this Earth corridor as a planning helper. Say if the window is usable and what to watch. Do not claim this replaces a range commit.",
        { plan: plan || {}, site: $("inp-name")?.value }
      );
      out.textContent = text || "Luna did not return a review. Try again.";
    });
    ["pathCanvas", "altCanvas"].forEach((id) => {
      const el = $(id);
      el.addEventListener("mousemove", onHover);
      el.addEventListener("mouseleave", () => { hoverIdx = -1; $("chart-hover").textContent = "Hover the plots for sample readout"; drawAll(); });
    });
    window.addEventListener("resize", () => drawAll());
    window.addEventListener("lipas-theme-change", () => drawAll());
    const tick = () => { $("utc-clock").textContent = new Date().toISOString().slice(11, 19) + "Z"; };
    tick(); setInterval(tick, 1000);
    applySite($("inp-from"), "lat1", "lon1", "alt1");
    applySite($("inp-to"), "lat2", "lon2", "alt2");
    $("alt2").value = 220;
    updateRouteMeta();
    await run();
  }
  boot().catch(() => {
    $("loadingScreen")?.classList.add("hidden");
    setBusy(false);
  });
})();
