(function () {
  "use strict";
  const api = (p) => (typeof window.lipasApiUrl === "function" ? window.lipasApiUrl(p) : p);
  const GROUPS = [
    { id: "overview", label: "Overview" },
    { id: "city", label: "Cities" },
    { id: "launch", label: "Launch facilities" },
    { id: "satellite", label: "Satellites" },
  ];
  const OFFLINE_SITES = [
    { id: "overview", name: "Earth", group: "overview", lat: 0, lon: 0, note: "Planet-wide sketch. Live SWPC numbers appear when the forecast service is connected." },
    { id: "boulder", name: "NOAA SWPC Boulder", group: "city", lat: 40.02, lon: -105.27, note: "Space Weather Prediction Center." },
    { id: "houston", name: "Houston / Johnson", group: "city", lat: 29.55, lon: -95.1, note: "ISS flight control." },
    { id: "fairbanks", name: "Fairbanks", group: "city", lat: 64.84, lon: -147.72, note: "Alaskan auroral zone." },
    { id: "ksc", name: "Kennedy Space Center", group: "launch", lat: 28.57, lon: -80.65, note: "US east-coast departure." },
    { id: "starbase", name: "Starbase", group: "launch", lat: 25.99, lon: -97.16, note: "Boca Chica departure site." },
    { id: "kourou", name: "Guiana Space Centre", group: "launch", lat: 5.24, lon: -52.77, note: "ESA equatorial launch site." },
    { id: "baikonur", name: "Baikonur", group: "launch", lat: 45.96, lon: 63.31, note: "Roscosmos departure site." },
    { id: "iss", name: "ISS", group: "satellite", lat: 12, lon: -40, alt_km: 420, note: "Crewed station. Position is a stand-in while the catalog is offline." },
    { id: "tiangong", name: "Tiangong", group: "satellite", lat: -8, lon: 70, alt_km: 390, note: "China Space Station." },
    { id: "hubble", name: "Hubble", group: "satellite", lat: 20, lon: 140, alt_km: 535, note: "NASA observatory." },
  ];
  function offlineForecast(site) {
    const n = 25;
    const time = Array.from({ length: n }, (_, i) => i);
    const wave = (base, amp, phase) => time.map((i) => Math.round((base + amp * Math.sin(i / 3.5 + phase)) * 100) / 100);
    const s = site || OFFLINE_SITES[0];
    return {
      site: s,
      time,
      kp: wave(2.1, 0.7, 0.2),
      dst: wave(-14, 8, 1),
      aurora_pct: wave(16, 9, 0.4),
      hf_blackout: wave(1.1, 0.35, 0.6),
      pca: wave(0.8, 0.3, 1.1),
      gnss_scintillation: wave(2.0, 0.5, 0.8),
      aviation_usv_h: wave(4.2, 0.8, 0.3),
      flare_index: wave(2.1, 0.4, 0.1),
      channels: [
        { id: "kp", label: "Kp", unit: "" },
        { id: "dst", label: "Dst", unit: "nT" },
        { id: "aurora_pct", label: "Aurora", unit: "%" },
        { id: "hf_blackout", label: "HF blackout", unit: "index" },
        { id: "gnss_scintillation", label: "GNSS scintillation", unit: "index" },
        { id: "aviation_usv_h", label: "Aviation dose", unit: "µSv/h" },
      ],
      now: {
        site: s,
        nowcast: { kp: 2.1, g_scale: "G0", flare_class: "B2", mag_lat: s.lat, lst_h: 14, aurora_pct: 16 },
        alerts: [{ level: "ok", title: "Quiet-day sketch", body: "This host has no live SWPC feed. Numbers are a calm-day estimate so the board, map, and chart still work." }],
      },
      satellites: OFFLINE_SITES.filter((x) => x.group === "satellite"),
      source: "offline-estimate",
    };
  }
  let siteId = "overview";
  let sites = [];
  let forecast = null;
  let hour = 0;
  let chartKey = "kp";
  let blobs = [];
  function $(id) { return document.getElementById(id); }
  function fmt(v, d) {
    if (v == null || !Number.isFinite(Number(v))) return "—";
    return Number(v).toFixed(d);
  }
  function wrapLon(lon) {
    let x = Number(lon);
    if (!Number.isFinite(x)) return 0;
    while (x > 180) x -= 360;
    while (x < -180) x += 360;
    return x;
  }
  function statusDot(n) {
    const kp = Number(n.kp || 0);
    const hold = Number(n.range_hold || n.saa || 0);
    if (kp >= 7 || hold >= 7) return "red";
    if (kp >= 5 || hold >= 4) return "yellow";
    return "green";
  }
  function esriThumb(lat, lon, z) {
    const n = Math.pow(2, z);
    const x = Math.floor(((wrapLon(lon) + 180) / 360) * n);
    const latRad = (Number(lat) * Math.PI) / 180;
    const y = Math.floor((1 - Math.log(Math.tan(latRad) + 1 / Math.cos(latRad)) / Math.PI) / 2 * n);
    return `https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/${z}/${y}/${x}`;
  }
  function seriesAt(key, h) {
    const arr = (forecast && forecast[key]) || [];
    const i = Math.max(0, Math.min(arr.length - 1, h | 0));
    return arr[i];
  }
  function nowcastView() {
    const base = (forecast && forecast.now && forecast.now.nowcast) || {};
    const out = { ...base };
    ["kp", "dst", "aurora_pct", "hf_blackout", "pca", "gnss_scintillation", "aviation_usv_h",
      "flare_index", "cme", "sep", "imf_bz", "range_hold", "saa", "drag", "charging",
      "belt_dose", "eclipse", "leo_dose_usv_h", "lst_h", "mag_lat", "g_scale", "flare_class"].forEach((k) => {
      const v = seriesAt(k, hour);
      if (v != null) out[k] = v;
    });
    return out;
  }
  function renderSites(filter) {
    const q = (filter || "").trim().toLowerCase();
    const list = $("siteList");
    if (!list) return;
    const rows = [];
    GROUPS.forEach((g) => {
      const items = sites.filter((s) => s.group === g.id && (!q || (s.name + " " + s.group + " " + s.id).toLowerCase().includes(q)));
      if (!items.length) return;
      rows.push(`<li class="li-section-header">${g.label}</li>`);
      items.forEach((s) => {
        const pinned = s.group === "overview";
        const sat = s.group === "satellite";
        const thumb = sat
          ? "linear-gradient(145deg,#d7ebe3,#9fd4c0 40%,#eef6f2)"
          : `linear-gradient(145deg,rgba(12,24,18,0.35),rgba(8,12,10,0.5)), url('${esriThumb(s.lat, s.lon, 7)}')`;
        const coords = sat
          ? `${fmt(s.alt_km, 0)} km · ${fmt(s.lat, 1)}°, ${fmt(s.lon, 1)}°`
          : `${fmt(s.lat, 2)}°, ${fmt(s.lon, 2)}°`;
        rows.push(`
          <li class="location-item${s.id === siteId ? " active" : ""}${pinned ? " pinned" : ""}" data-id="${s.id}">
            ${pinned ? "" : `<div class="li-image" style="background-image:${thumb}"></div>`}
            <div class="li-info">
              <div class="li-hdr"><div class="li-dot ${statusDot(s)}"></div><div class="li-name">${s.name}</div></div>
              ${pinned ? `<div class="li-badge">Full disk</div>` : `<div class="li-coords">${coords}</div>`}
              <div class="li-summary">${s.note || ""}</div>
            </div>
          </li>`);
      });
    });
    list.innerHTML = rows.join("");
    list.querySelectorAll(".location-item[data-id]").forEach((el) => {
      el.addEventListener("click", () => {
        siteId = el.dataset.id;
        refresh();
      });
    });
  }
  function kpiSet(n, group) {
    if (group === "satellite") {
      return [
        ["Kp / G-scale", `${fmt(n.kp, 1)} ${n.g_scale || ""}`, "geomagnetic"],
        ["SEP", fmt(n.sep, 1), "index"],
        ["SAA", fmt(n.saa, 1), "index"],
        ["Drag", fmt(n.drag, 1), "index"],
        ["Charging", fmt(n.charging, 1), "index"],
        ["Belt dose", fmt(n.belt_dose, 1), "index"],
        ["Orbit dose", fmt(n.leo_dose_usv_h, 1), "µSv/h"],
        ["Eclipse", fmt(n.eclipse, 2), "frac"],
      ];
    }
    if (group === "launch") {
      return [
        ["Kp / G-scale", `${fmt(n.kp, 1)} ${n.g_scale || ""}`, "geomagnetic"],
        ["Flare", n.flare_class || fmt(n.flare_index, 1), "GOES"],
        ["Range hold", fmt(n.range_hold, 1), "index"],
        ["GNSS scint.", fmt(n.gnss_scintillation, 1), "index"],
        ["HF blackout", fmt(n.hf_blackout, 1), "index"],
        ["Ascent dose", fmt(n.aviation_usv_h, 1), "µSv/h"],
        ["Dst", fmt(n.dst, 0), "nT"],
        ["PCA", fmt(n.pca, 1), "index"],
      ];
    }
    return [
      ["Kp / G-scale", `${fmt(n.kp, 1)} ${n.g_scale || ""}`, "geomagnetic"],
      ["Aurora", fmt(n.aurora_pct, 0), "%"],
      ["Aviation dose", fmt(n.aviation_usv_h, 1), "µSv/h"],
      ["Dst", fmt(n.dst, 0), "nT"],
      ["Flare", n.flare_class || fmt(n.flare_index, 1), "GOES"],
      ["HF blackout", fmt(n.hf_blackout, 1), "index"],
      ["GNSS scint.", fmt(n.gnss_scintillation, 1), "index"],
      ["F10.7", fmt(n.f107, 0), "sfu"],
    ];
  }
  function renderKpis(n, group) {
    $("kpiGrid").innerHTML = kpiSet(n, group).map(([k, v, u]) =>
      `<div class="kpi"><div class="k">${k}</div><div class="v">${v}</div><div class="u">${u}</div></div>`
    ).join("");
    $("metricsPanel").innerHTML = kpiSet(n, group).map(([k, v]) =>
      `<div class="metric-chip"><div class="k">${k}</div><div class="v">${v}</div></div>`
    ).join("");
  }
  function renderAlerts(alerts) {
    $("alertRow").innerHTML = (alerts || []).map((a) =>
      `<div class="alert ${a.level}"><b>${a.title}</b>${a.body}</div>`
    ).join("");
    $("warningsContainer").innerHTML = (alerts || []).map((a) =>
      `<div class="warning-box ${a.level === "ok" ? "go" : a.level}"><div class="warning-header">${a.title}</div><div class="warning-desc">${a.body}</div></div>`
    ).join("");
  }
  function renderPills(group) {
    const channels = (forecast && forecast.channels) || [];
    const box = $("metricButtons");
    if (!channels.length) {
      box.innerHTML = "";
      return;
    }
    if (!channels.some((c) => c.id === chartKey)) chartKey = channels[0].id;
    box.innerHTML = channels.map((c) =>
      `<button type="button" class="${c.id === chartKey ? "active" : ""}" data-chart="${c.id}">${c.label}</button>`
    ).join("");
    box.querySelectorAll("button").forEach((b) => {
      b.addEventListener("click", () => {
        chartKey = b.dataset.chart;
        box.querySelectorAll("button").forEach((x) => x.classList.toggle("active", x === b));
        renderChart();
      });
    });
  }
  function chartColor(id) {
    const map = {
      kp: "#1f8a56",
      ap: "#2f6fd6",
      dst: "#3d6fd8",
      f107: "#d4892a",
      bz: "#c4476a",
      imf_bz: "#c4476a",
      sw_speed: "#1d7a9c",
      speed: "#1d7a9c",
      density: "#8a6230",
      sw_density: "#8a6230",
      proton: "#c45d2c",
      fluence: "#a24b9a",
      ae: "#7a4ea8",
      aurora: "#1f8a56",
      hf: "#c4922a",
      gnss: "#a24b9a",
    };
    if (map[id]) return map[id];
    let h = 0;
    String(id || "").split("").forEach((c) => { h = (h * 33 + c.charCodeAt(0)) % 360; });
    return `hsl(${h} 48% 34%)`;
  }
  function renderChart() {
    const canvas = $("graphCanvas");
    if (!canvas) return;
    const series = (forecast && forecast[chartKey]) || [];
    const nums = series.map((v) => Number(v));
    const finite = nums.filter(Number.isFinite);
    const ctx = canvas.getContext("2d");
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const cssW = canvas.clientWidth || 640;
    const cssH = 200;
    canvas.width = Math.floor(cssW * dpr);
    canvas.height = Math.floor(cssH * dpr);
    canvas.style.height = cssH + "px";
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const light = document.documentElement.dataset.theme === "light";
    ctx.fillStyle = light ? "#f7f4ee" : "#0c1612";
    ctx.fillRect(0, 0, cssW, cssH);
    const ch = ((forecast && forecast.channels) || []).find((c) => c.id === chartKey);
    $("chartMeta").textContent = ch ? `${ch.label} · ${ch.unit || ""}`.trim() : chartKey;
    if (finite.length < 2) return;
    const lo = Math.min(...finite);
    const hi = Math.max(...finite);
    const span = hi - lo || 1;
    const pad = { l: 44, r: 12, t: 16, b: 22 };
    const w = cssW - pad.l - pad.r;
    const h = cssH - pad.t - pad.b;
    const col = chartColor(chartKey);
    ctx.strokeStyle = light ? "rgba(28,25,21,0.08)" : "rgba(232,246,238,0.08)";
    ctx.lineWidth = 1;
    for (let g = 0; g <= 3; g++) {
      const y = pad.t + (h * g) / 3;
      ctx.beginPath();
      ctx.moveTo(pad.l, y);
      ctx.lineTo(pad.l + w, y);
      ctx.stroke();
    }
    const xy = (i) => {
      const v = Number.isFinite(nums[i]) ? nums[i] : lo;
      return [
        pad.l + (i / (nums.length - 1)) * w,
        pad.t + (1 - (v - lo) / span) * h,
      ];
    };
    ctx.beginPath();
    nums.forEach((_, i) => {
      const [x, y] = xy(i);
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    });
    ctx.lineTo(pad.l + w, pad.t + h);
    ctx.lineTo(pad.l, pad.t + h);
    ctx.closePath();
    ctx.save();
    ctx.globalAlpha = light ? 0.22 : 0.28;
    ctx.fillStyle = col;
    ctx.fill();
    ctx.restore();
    ctx.beginPath();
    nums.forEach((_, i) => {
      const [x, y] = xy(i);
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    });
    ctx.strokeStyle = col;
    ctx.lineWidth = 2.4;
    ctx.lineJoin = "round";
    ctx.stroke();
    const hx = pad.l + (hour / Math.max(1, nums.length - 1)) * w;
    ctx.strokeStyle = light ? "rgba(26,25,22,0.35)" : "rgba(232,246,238,0.45)";
    ctx.setLineDash([3, 4]);
    ctx.beginPath();
    ctx.moveTo(hx, pad.t);
    ctx.lineTo(hx, pad.t + h);
    ctx.stroke();
    ctx.setLineDash([]);
    const yi = Math.max(0, Math.min(nums.length - 1, hour));
    if (Number.isFinite(nums[yi])) {
      const [x, y] = xy(yi);
      ctx.fillStyle = col;
      ctx.beginPath();
      ctx.arc(x, y, 4, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.fillStyle = light ? "#5c564c" : "#9ec9b4";
    ctx.font = "11px IBM Plex Sans, sans-serif";
    ctx.fillText(String(Math.round(hi * 10) / 10), 6, pad.t + 10);
    ctx.fillText(String(Math.round(lo * 10) / 10), 6, pad.t + h);
  }
  function renderSats(sats) {
    const row = $("satRow");
    if (!row) return;
    row.innerHTML = (sats || []).map((s) =>
      `<a class="sat-card" href="earth_globe.html?sat=${encodeURIComponent(s.id)}">
        <div class="n">${s.name}</div>
        <div class="m">${fmt(s.lat, 1)}°, ${fmt(s.lon, 1)}° · ${fmt(s.alt_km, 0)} km · ${s.group}</div>
      </a>`
    ).join("") || `<div class="m">No satellite catalog yet.</div>`;
  }
  function drawMap(site) {
    const canvas = $("earthMapCanvas");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const w = canvas.width = canvas.clientWidth || 920;
    const h = canvas.height = 360;
    const light = document.documentElement.dataset.theme === "light";
    ctx.fillStyle = light ? "#f4f1ea" : "#08110e";
    ctx.fillRect(0, 0, w, h);
    ctx.strokeStyle = "rgba(62,207,142,0.12)";
    for (let lon = -180; lon <= 180; lon += 30) {
      const x = ((lon + 180) / 360) * w;
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke();
    }
    for (let lat = -60; lat <= 60; lat += 30) {
      const y = ((90 - lat) / 180) * h;
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke();
    }
    const pal = {
      aurora: [62, 207, 142],
      hf: [224, 177, 74],
      pca: [126, 156, 255],
      gnss: [224, 122, 208],
    };
    blobs.forEach((b) => {
      const x = ((wrapLon(b.lon) + 180) / 360) * w;
      const y = ((90 - Number(b.lat)) / 180) * h;
      const c = pal[b.type] || pal.aurora;
      const r = 18 + Number(b.intensity || 0.4) * 36;
      const g = ctx.createRadialGradient(x, y, 1, x, y, r);
      const a = 0.12 + Number(b.intensity || 0.3) * 0.4;
      g.addColorStop(0, `rgba(${c[0]},${c[1]},${c[2]},${a})`);
      g.addColorStop(1, `rgba(${c[0]},${c[1]},${c[2]},0)`);
      ctx.fillStyle = g;
      ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill();
    });
    if (site && site.group !== "overview") {
      const x = ((wrapLon(site.lon) + 180) / 360) * w;
      const y = ((90 - Number(site.lat)) / 180) * h;
      ctx.fillStyle = "#3ecf8e";
      ctx.beginPath(); ctx.arc(x, y, 5, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = light ? "#1a1916" : "#e8f6ee";
      ctx.font = "12px IBM Plex Sans, sans-serif";
      ctx.fillText(site.name || "", x + 8, y - 6);
    }
  }
  function downloadPDF() {
    const loc = (forecast && forecast.site) || {};
    const n = nowcastView();
    if (!window.jspdf || !window.jspdf.jsPDF) {
      alert("PDF library is still loading — wait a second and try again.");
      return;
    }
    const { jsPDF } = window.jspdf;
    const doc = new jsPDF("p", "mm", "a4");
    const PW = doc.internal.pageSize.width;
    const PH = doc.internal.pageSize.height;
    const M = 14;
    let y = 18;
    const check = (need) => {
      if (y > PH - M - (need || 12)) { doc.addPage(); y = M; }
    };
    doc.setFillColor(12, 20, 16);
    doc.rect(0, 0, PW, 42, "F");
    doc.setTextColor(62, 207, 142);
    doc.setFont("helvetica", "bold");
    doc.setFontSize(22);
    doc.text("L.I.P.A.S. Earth", M, 18);
    doc.setFontSize(11);
    doc.setTextColor(232, 246, 238);
    doc.text("Space-weather site briefing", M, 27);
    doc.setFont("helvetica", "normal");
    doc.setFontSize(8);
    doc.setTextColor(158, 201, 180);
    doc.text("SWPC / OMNI nowcast · Celestrak orbits · dipole oval", M, 34);
    y = 52;
    doc.setTextColor(30, 40, 36);
    doc.setFontSize(11);
    [`Site: ${loc.name || siteId}`, `Coordinates: ${fmt(loc.lat, 3)}°, ${fmt(loc.lon, 3)}°`,
      `Type: ${loc.group || "—"}`, `Generated: ${new Date().toISOString()}`,
      `Hour offset: +${hour} h · Kp ${fmt(n.kp, 1)} ${n.g_scale || ""}`].forEach((line) => {
      doc.text(line, M, y); y += 7;
    });
    y += 4;
    doc.setFont("helvetica", "bold");
    doc.setTextColor(27, 107, 74);
    doc.text("Nowcast", M, y); y += 8;
    doc.setFont("helvetica", "normal");
    doc.setTextColor(30, 40, 36);
    kpiSet(n, loc.group).forEach(([k, v, u]) => {
      check(8);
      doc.text(`${k}: ${v} ${u || ""}`, M, y); y += 6;
    });
    y += 4;
    doc.setFont("helvetica", "bold");
    doc.setTextColor(27, 107, 74);
    doc.text("24 h series (" + chartKey + ")", M, y); y += 8;
    doc.setFont("helvetica", "normal");
    doc.setTextColor(30, 40, 36);
    ((forecast && forecast[chartKey]) || []).forEach((v, i) => {
      if (i % 3 !== 0) return;
      check(6);
      doc.text(`+${i}h  ${fmt(v, 2)}`, M, y); y += 5;
    });
    const nPages = doc.internal.getNumberOfPages();
    for (let i = 1; i <= nPages; i++) {
      doc.setPage(i);
      doc.setFontSize(7);
      doc.setTextColor(120, 140, 130);
      doc.text("© 2026 Luka Takki · LIPAS", PW / 2, PH - 8, { align: "center" });
    }
    const safe = String(loc.name || siteId).replace(/\W+/g, "_");
    doc.save(`LIPAS_Earth_${safe}_${Date.now()}.pdf`);
  }
  let hourTimer = 0;
  function applyHourView() {
    if (!forecast) return;
    const site = forecast.site || {};
    const n = nowcastView();
    const lat = seriesAt("lat", hour) ?? site.lat;
    const lon = seriesAt("lon", hour) ?? site.lon;
    const alt = seriesAt("alt_km", hour) ?? site.alt_km;
    const extra = site.group === "satellite" ? ` · ${fmt(alt, 0)} km` : "";
    $("hourLabel").textContent = hour === 0 ? "Now" : `+${hour} h`;
    $("siteKicker").textContent = `${fmt(lat, 2)}°, ${fmt(lon, 2)}° · mag ${fmt(n.mag_lat, 1)}° · LST ${fmt(n.lst_h, 1)} h${extra}`;
    renderKpis(n, site.group);
    renderChart();
    drawMap({ ...site, lat, lon });
    clearTimeout(hourTimer);
    hourTimer = setTimeout(() => loadHourLive(), 160);
  }
  async function loadHourLive() {
    try {
      const [stRes, satRes] = await Promise.all([
        fetch(api(`/api/earth/state?site=${encodeURIComponent(siteId)}&hour=${encodeURIComponent(hour)}`)),
        fetch(api("/api/earth/satellites?hour=" + encodeURIComponent(hour))),
      ]);
      if (stRes.ok) {
        const st = await stRes.json();
        renderAlerts(st.alerts);
        const n = nowcastView();
        const merged = { ...n, ...(st.nowcast || {}) };
        renderKpis(merged, (st.site || {}).group || (forecast.site || {}).group);
        const site = st.site || forecast.site || {};
        const extra = site.group === "satellite" ? ` · ${fmt(site.alt_km, 0)} km` : "";
        if (site.lat != null) {
          $("siteKicker").textContent = `${fmt(site.lat, 2)}°, ${fmt(site.lon, 2)}° · mag ${fmt(merged.mag_lat, 1)}° · LST ${fmt(merged.lst_h, 1)} h${extra}`;
        }
      }
      if (satRes.ok) {
        const sat = await satRes.json();
        renderSats(sat.satellites);
      }
    } catch (_) {}
  }
  async function refresh() {
    let remote = null;
    try {
      const r = await fetch(api(`/api/earth/forecast?site=${encodeURIComponent(siteId)}&hours=24`));
      if (r.ok) remote = await r.json();
    } catch (_) {}
    const picked = sites.find((s) => s.id === siteId) || OFFLINE_SITES[0];
    forecast = remote && (remote.kp || remote.now) ? remote : offlineForecast(picked);
    if (!forecast.site) forecast.site = picked;
    const now = forecast.now || {};
    const site = now.site || picked;
    const n = nowcastView();
    $("siteTitle").textContent = site.name || siteId;
    $("siteNote").textContent = site.note || "Live SWPC / OMNI drivers at this site.";
    const extra = site.group === "satellite" ? ` · ${fmt(site.alt_km, 0)} km` : "";
    $("siteKicker").textContent = `${fmt(site.lat, 2)}°, ${fmt(site.lon, 2)}° · mag ${fmt(n.mag_lat, 1)}° · LST ${fmt(n.lst_h, 1)} h${extra}`;
    $("hourLabel").textContent = hour === 0 ? "Now" : `+${hour} h`;
    $("boardMeta").textContent = site.group === "satellite" ? "Orbit environment" : site.group === "launch" ? "Launch commit" : "Ground / city";
    renderKpis(n, site.group);
    renderAlerts(now.alerts);
    renderPills(site.group);
    renderChart();
    renderSats(forecast.satellites);
    renderSites($("siteSearch").value);
    $("satPanel").style.display = site.group === "satellite" ? "none" : "";
    drawMap(site);
    $("loadingScreen")?.classList.add("hidden");
    document.title = `L.I.P.A.S. Earth · ${site.name || "Dashboard"}`;
  }
  async function loadBlobs() {
    try {
      const r = await fetch(api("/api/earth/hazards?hour=" + encodeURIComponent(hour)));
      const j = await r.json();
      blobs = j.blobs || [];
    } catch (_) {
      blobs = [];
    }
    drawMap((forecast && forecast.site) || null);
  }
  async function boot() {
    sites = OFFLINE_SITES.slice();
    try {
      const r = await fetch(api("/api/earth/sites"));
      if (r.ok) {
        const j = await r.json();
        if (j && Array.isArray(j.sites) && j.sites.length) sites = j.sites;
      }
    } catch (_) {}
    $("siteSearch").addEventListener("input", () => renderSites($("siteSearch").value));
    $("hourSlider").addEventListener("input", (e) => {
      hour = Number(e.target.value) || 0;
      applyHourView();
    });
    $("hourSlider").addEventListener("change", () => {
      loadBlobs();
      loadHourLive();
    });
    $("pdfBtn").addEventListener("click", downloadPDF);
    window.addEventListener("lipas-theme-change", () => {
      renderChart();
      drawMap((forecast && forecast.site) || null);
    });
    window.downloadPDF = downloadPDF;
    const q = new URLSearchParams(location.search).get("site");
    if (q) siteId = q;
    await refresh();
    await loadBlobs();
  }
  boot().catch(() => $("loadingScreen")?.classList.add("hidden"));
})();
