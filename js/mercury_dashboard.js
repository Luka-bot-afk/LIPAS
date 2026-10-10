(function () {
  "use strict";

  const api = (p) => (typeof window.lipasApiUrl === "function" ? window.lipasApiUrl(p) : p);

  let siteId = "equator";
  let hour = 0;
  let lstLocked = false;
  let lst = 12;
  let forecast = null;
  let sitesNow = null;
  let state = null;
  let timer = null;

  function $(id) { return document.getElementById(id); }

  function fmt(v, d) {
    if (v == null || !Number.isFinite(Number(v))) return "—";
    return Number(v).toFixed(d);
  }

  async function loadSites() {
    const r = await fetch(api("/api/mercury/sites"));
    sitesNow = await r.json();
    renderSites();
  }

  async function loadForecast() {
    const r = await fetch(api(`/api/mercury/forecast?site=${encodeURIComponent(siteId)}&hours=24`));
    forecast = await r.json();
  }

  async function loadState() {
    const q = new URLSearchParams({ site: siteId, hour: String(hour) });
    if (lstLocked) q.set("lst", String(lst));
    const r = await fetch(api("/api/mercury/state?" + q.toString()));
    state = await r.json();
    if (!lstLocked) {
      lst = state.lst_h;
      $("lstSlider").value = String(lst);
    }
    renderAll();
  }

  function renderSites() {
    const row = $("siteRow");
    const list = (sitesNow && sitesNow.catalog) || [];
    row.innerHTML = list
      .map(
        (s) => `<button type="button" class="site-btn${s.id === siteId ? " active" : ""}" data-id="${s.id}">
          ${s.name}<small>${Math.abs(s.lat).toFixed(1)}°${s.lat >= 0 ? "N" : "S"} · ${s.terrain.replace("_", " ")}</small>
        </button>`
      )
      .join("");
    row.querySelectorAll(".site-btn").forEach((b) => {
      b.addEventListener("click", async () => {
        siteId = b.dataset.id;
        lstLocked = false;
        await refresh(true);
      });
    });
  }

  function renderAlerts() {
    const alerts = (state && state.alerts) || [];
    $("alertRow").innerHTML = alerts
      .map(
        (a) => `<div class="alert ${a.level}"><b>${a.title}</b>${a.body}</div>`
      )
      .join("");
  }

  function renderKpis() {
    if (!state) return;
    const p = state.prediction || {};
    const m = state.magnetosphere || {};
    const pick = (key, fallback) => {
      const arr = forecast && forecast[key];
      if (Array.isArray(arr) && arr[hour] != null) return arr[hour];
      return fallback;
    };
    const items = [
      ["Solar", fmt(pick("solar", p.solar), 1), "index"],
      ["Radiation", fmt(pick("radiation", p.radiation), 3), "mSv/h"],
      ["Temperature", fmt(pick("temperature", p.temperature), 0), "°C"],
      ["Standoff", fmt(m.standoff_rm, 2), "R_M"],
      ["Dust", fmt(pick("dust", p.dust), 2), "index"],
      ["Micrometeorites", fmt(pick("micrometeorites", p.micrometeorites), 2), "index"],
      ["EVA risk", fmt(pick("evaRisk", p.evaRisk), 2), "index"],
      ["Comms", fmt(pick("comms", p.comms), 2), "index"],
    ];
    $("kpiRow").innerHTML = items
      .map(([k, v, u]) => `<div class="kpi"><div class="k">${k}</div><div class="v">${v}</div><div class="u">${u}</div></div>`)
      .join("");
  }

  function renderMeta() {
    if (!state) return;
    $("hourLabel").textContent = `T+${hour} h`;
    $("lstLabel").textContent = `${fmt(lst, 1)} h`;
    const src = (state.drivers?.sources || []).join(" · ") || "LIPAS archives";
    $("metaLine").innerHTML = `<strong>r</strong> ${fmt(state.r_au, 4)} AU (${state.r_source})<br>
      <strong>LST</strong> ${fmt(state.lst_h, 1)} h · <strong>lead</strong> ${fmt(state.lead_time?.lead_time_h, 1)} h (SW) / ${fmt(state.lead_time?.photon_lead_min, 1)} min (light)<br>
      <strong>Feed</strong> ${src}<br><strong>UTC</strong> ${String(state.utc || "").replace("T", " ").slice(0, 19)}Z`;
    const pol = state.ml_policy;
    if (pol) {
      $("policyNote").textContent =
        "Mercury nowcast uses 1 AU SWPC drivers scaled to this heliocentric distance, plus a Hermean magnetosphere. Dust, micrometeoroids, thermal-contraction quakes, EVA, and comms are physics-derived at this site — not the lunar LSTM.";
    }
  }

  function xyMag(canvas, xrm, zrm, mag) {
    const g = mag.grid;
    const w = canvas.width;
    const h = canvas.height;
    const x = ((xrm - g.x_min) / (g.x_max - g.x_min)) * w;
    const y = (1 - (zrm - g.z_min) / (g.z_max - g.z_min)) * h;
    return [x, y];
  }

  function drawMagnetosphere() {
    const cv = $("cvMag");
    const ctx = cv.getContext("2d");
    const mag = state?.magnetosphere;
    if (!mag) return;
    const colors = mag.colors || {};
    const g = mag.grid;
    const cw = cv.width / g.nx;
    const ch = cv.height / g.nz;
    ctx.fillStyle = "#07090c";
    ctx.fillRect(0, 0, cv.width, cv.height);
    for (let j = 0; j < g.nz; j++) {
      for (let i = 0; i < g.nx; i++) {
        ctx.fillStyle = colors[g.cells[j][i]] || "#111";
        ctx.globalAlpha = 0.55;
        ctx.fillRect(i * cw, j * ch, cw + 0.5, ch + 0.5);
      }
    }
    ctx.globalAlpha = 1;

    function strokePoly(pts, color, width) {
      if (!pts || pts.length < 2) return;
      ctx.beginPath();
      pts.forEach((p, n) => {
        const [x, y] = xyMag(cv, p[0], p[1], mag);
        if (n === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.strokeStyle = color;
      ctx.lineWidth = width;
      ctx.stroke();
    }
    strokePoly(mag.bow_shock?.north, "#e8c48a", 1.6);
    strokePoly(mag.bow_shock?.south, "#e8c48a", 1.6);
    strokePoly(mag.magnetopause?.north, "#7ec8d6", 2);
    strokePoly(mag.magnetopause?.south, "#7ec8d6", 2);

    (mag.field_lines || []).forEach((ln) => {
      strokePoly(ln.points, ln.closed ? colors.closed_line : colors.open_line, ln.closed ? 1.1 : 0.9);
    });

    const [cx, cy] = xyMag(cv, 0, 0, mag);
    const [ex] = xyMag(cv, 1, 0, mag);
    const pr = Math.abs(ex - cx);
    ctx.fillStyle = colors.planet || "#8a7a6b";
    ctx.beginPath();
    ctx.arc(cx, cy, pr, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = "rgba(255,255,255,0.25)";
    ctx.stroke();

    ctx.fillStyle = "#f2c56d";
    ctx.font = "12px IBM Plex Sans, sans-serif";
    ctx.fillText("SUN →", cv.width - 72, 22);
    ctx.fillStyle = "rgba(230,238,248,0.7)";
    ctx.fillText(`R_ss ${fmt(mag.standoff_rm, 2)} R_M`, 12, 20);
    ctx.fillText(`R_bs ${fmt(mag.bow_shock_rm, 2)} R_M`, 12, 36);
    if (mag.dayside_open_to_solar_wind) {
      ctx.fillStyle = "#e25b5b";
      ctx.fillText("DAYSIDE OPEN", 12, 54);
    }

    $("magLegend").innerHTML = (mag.legend || [])
      .map(([k, lab]) => `<span><i style="background:${colors[k]}"></i>${lab}</span>`)
      .join("");
  }

  function drawClock() {
    const cv = $("cvClock");
    const ctx = cv.getContext("2d");
    ctx.fillStyle = "#07090c";
    ctx.fillRect(0, 0, cv.width, cv.height);
    const clock = state?.magnetosphere?.imf_clock;
    const cx = cv.width * 0.38;
    const cy = cv.height * 0.52;
    const r = 68;
    ctx.strokeStyle = "rgba(140,170,200,0.25)";
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.stroke();
    ctx.fillStyle = "var(--muted)";
    ctx.font = "11px IBM Plex Sans, sans-serif";
    ctx.fillStyle = "#8fa3b8";
    ctx.fillText("+Bz", cx - 10, cy - r - 8);
    ctx.fillText("−Bz", cx - 10, cy + r + 16);
    ctx.fillText("+By", cx + r + 8, cy + 4);
    if (!clock) return;
    const ang = (Number(clock.angle_deg) * Math.PI) / 180;

    const x2 = cx + Math.sin(ang) * (r - 8);
    const y2 = cy - Math.cos(ang) * (r - 8);
    ctx.strokeStyle = clock.orientation === "southward" ? "#e25b5b" : "#e07a3d";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.lineTo(x2, y2);
    ctx.stroke();
    ctx.fillStyle = "#e6eef8";
    ctx.font = "13px IBM Plex Sans, sans-serif";
    ctx.fillText(`${clock.orientation}`, cv.width * 0.62, 48);
    ctx.fillStyle = "#8fa3b8";
    ctx.fillText(`By ${fmt(clock.by_nt, 1)} nT`, cv.width * 0.62, 70);
    ctx.fillText(`Bz ${fmt(clock.bz_nt, 1)} nT`, cv.width * 0.62, 88);
    ctx.fillText(`${fmt(clock.angle_deg, 0)}°`, cv.width * 0.62, 106);
  }

  function drawParker() {
    const cv = $("cvParker");
    const ctx = cv.getContext("2d");
    ctx.fillStyle = "#07090c";
    ctx.fillRect(0, 0, cv.width, cv.height);
    const spiral = state?.wind_mercury?.spiral_deg ?? 25;
    const cx = 28;
    const cy = cv.height / 2;
    ctx.fillStyle = "#f2c56d";
    ctx.beginPath();
    ctx.arc(cx, cy, 7, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = "rgba(242,197,109,0.45)";
    ctx.lineWidth = 1.4;
    for (let k = 0; k < 4; k++) {
      ctx.beginPath();
      const off = (k * Math.PI) / 2;
      for (let i = 0; i < 80; i++) {
        const r = 8 + i * 1.55;
        const th = off + (i / 80) * (spiral * Math.PI) / 180 * 4;
        const x = cx + r * Math.cos(th);
        const y = cy + r * Math.sin(th);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
    }
    const rM = 0.387 * 90;
    const rE = 1.0 * 90;
    ctx.fillStyle = "#8a7a6b";
    ctx.beginPath();
    ctx.arc(cx + rM, cy, 5, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#e07a3d";
    ctx.beginPath();
    ctx.arc(cx + rE, cy, 6, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#8fa3b8";
    ctx.font = "11px IBM Plex Sans, sans-serif";
    ctx.fillText(`Parker angle at Mercury ${fmt(spiral, 0)}°`, 16, cv.height - 12);
    ctx.fillText("Mercury", cx + rM - 10, cy - 10);
    ctx.fillText("Earth", cx + rE - 8, cy - 12);
  }

  function lineChart(canvas, series, color, extra) {
    const ctx = canvas.getContext("2d");
    ctx.fillStyle = "#07090c";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    const pad = { l: 42, r: 12, t: 12, b: 24 };
    const w = canvas.width - pad.l - pad.r;
    const h = canvas.height - pad.t - pad.b;
    const vals = (series || []).filter((v) => Number.isFinite(v));
    if (!vals.length) return;
    let lo = Math.min(...vals);
    let hi = Math.max(...vals);
    if (lo === hi) {
      lo -= 1;
      hi += 1;
    }
    if (extra?.zero) {
      lo = Math.min(lo, 0);
      hi = Math.max(hi, 0);
    }
    ctx.strokeStyle = "rgba(140,170,200,0.12)";
    ctx.lineWidth = 1;
    for (let g = 0; g <= 4; g++) {
      const y = pad.t + (h * g) / 4;
      ctx.beginPath();
      ctx.moveTo(pad.l, y);
      ctx.lineTo(pad.l + w, y);
      ctx.stroke();
    }
    ctx.beginPath();
    series.forEach((v, i) => {
      const x = pad.l + (i / Math.max(1, series.length - 1)) * w;
      const y = pad.t + (1 - (v - lo) / (hi - lo)) * h;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.stroke();
    if (hour < series.length) {
      const x = pad.l + (hour / Math.max(1, series.length - 1)) * w;
      ctx.strokeStyle = "rgba(230,238,248,0.35)";
      ctx.beginPath();
      ctx.moveTo(x, pad.t);
      ctx.lineTo(x, pad.t + h);
      ctx.stroke();
    }
    ctx.fillStyle = "#8fa3b8";
    ctx.font = "10px IBM Plex Sans, sans-serif";
    ctx.fillText(fmt(hi, extra?.digits ?? 1), 4, pad.t + 8);
    ctx.fillText(fmt(lo, extra?.digits ?? 1), 4, pad.t + h);
    ctx.fillText("0 h", pad.l, canvas.height - 6);
    ctx.fillText("24 h", pad.l + w - 24, canvas.height - 6);
    if (extra?.second) {
      ctx.beginPath();
      extra.second.forEach((v, i) => {
        const x = pad.l + (i / Math.max(1, extra.second.length - 1)) * w;
        const y = pad.t + (1 - (v - lo) / (hi - lo)) * h;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.strokeStyle = extra.secondColor || "#e0b14a";
      ctx.lineWidth = 1.5;
      ctx.stroke();
    }
  }

  function drawPressure() {
    const cv = $("cvP");
    const ctx = cv.getContext("2d");
    ctx.fillStyle = "#07090c";
    ctx.fillRect(0, 0, cv.width, cv.height);
    const mag = state?.magnetosphere;
    if (!mag) return;
    const bars = [
      ["P_dyn", mag.p_dyn_npa, "#e07a3d"],
      ["P_mag at MP", mag.p_mag_mp_npa, "#3d9aad"],
    ];
    const max = Math.max(...bars.map((b) => b[1]), 1);
    bars.forEach((b, i) => {
      const y = 40 + i * 70;
      ctx.fillStyle = "#8fa3b8";
      ctx.font = "12px IBM Plex Sans, sans-serif";
      ctx.fillText(`${b[0]}  ${fmt(b[1], 2)} nPa`, 16, y);
      ctx.fillStyle = b[2];
      ctx.fillRect(16, y + 10, (cv.width - 40) * (b[1] / max), 18);
    });
  }

  function drawSitesCompare() {
    const cv = $("cvSites");
    const ctx = cv.getContext("2d");
    ctx.fillStyle = "#07090c";
    ctx.fillRect(0, 0, cv.width, cv.height);
    const rows = sitesNow?.sites || [];
    if (!rows.length) return;
    const maxR = Math.max(...rows.map((s) => s.radiation), 0.05);
    rows.forEach((s, i) => {
      const y = 16 + i * 30;
      ctx.fillStyle = s.id === siteId ? "#e6eef8" : "#8fa3b8";
      ctx.font = "11px IBM Plex Sans, sans-serif";
      ctx.fillText(s.name.split(" (")[0], 8, y + 8);
      ctx.fillStyle = "#d45d8c";
      ctx.fillRect(130, y, ((cv.width - 150) * s.radiation) / maxR, 10);
    });
  }

  function renderCharts() {
    if (!forecast) return;
    lineChart($("cvSolar"), forecast.solar, "#e07a3d");
    lineChart($("cvRad"), forecast.radiation, "#d45d8c", { digits: 3 });
    lineChart($("cvRss"), forecast.standoff_rm, "#3d9aad", { digits: 2 });
    const bz = forecast.imf_bz || [];
    const bmag = forecast.imf_b_mag || [];
    const all = bz.concat(bmag);
    lineChart($("cvImf"), bmag, "#e07a3d", { second: bz, secondColor: "#e25b5b", zero: true });
    const tc = forecast.lst_curve?.temperature || [];
    lineChart($("cvT"), tc, "#c4a574", { digits: 0 });
    drawPressure();
    drawSitesCompare();
  }

  function renderAll() {
    renderSites();
    renderAlerts();
    renderKpis();
    renderMeta();
    drawMagnetosphere();
    drawClock();
    drawParker();
    renderCharts();
  }

  async function refresh(reloadForecast) {
    $("loadingScreen").classList.remove("hidden");
    try {
      if (!sitesNow) await loadSites();
      if (reloadForecast || !forecast) await loadForecast();
      await loadState();
    } catch (err) {
      console.error(err);
      $("metaLine").textContent = "Could not load Mercury state. Is the Flask server running?";
    }
    $("loadingScreen").classList.add("hidden");
  }

  $("hourSlider").addEventListener("input", (e) => {
    hour = Number(e.target.value);
    $("hourLabel").textContent = `T+${hour} h`;
    clearTimeout(timer);
    timer = setTimeout(() => loadState(), 80);
  });
  $("lstSlider").addEventListener("input", (e) => {
    lstLocked = true;
    lst = Number(e.target.value);
    $("lstLabel").textContent = `${fmt(lst, 1)} h`;
    clearTimeout(timer);
    timer = setTimeout(() => loadState(), 80);
  });

  window.addEventListener("load", () => refresh(true));
})();
