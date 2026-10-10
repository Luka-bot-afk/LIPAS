(function () {
  "use strict";

  window.LIPAS_MERCURY = true;

  const api = (p) => (typeof window.lipasApiUrl === "function" ? window.lipasApiUrl(p) : p);

  const SITES = [
    {
      id: "overview",
      name: "Mercury",
      overview: true,
      lat: 0,
      lon: 0,
      summary: "All sites. Wind, heat, radiation, and the magnetic shield.",
      group: "overview",
    },
    {
      id: "antipode",
      name: "Caloris antipode",
      lat: -30.0,
      lon: -18.5,
      summary: "Rough ground opposite Caloris.",
      group: "antipodes",
    },
    {
      id: "debussy",
      name: "Debussy",
      lat: -34.0,
      lon: 14.0,
      summary: "Bright young crater.",
      group: "antipodes",
    },
    {
      id: "antipode_n",
      name: "North antipode",
      lat: -12.0,
      lon: -25.0,
      summary: "North of the antipode.",
      group: "antipodes",
    },
    {
      id: "antipode_e",
      name: "East antipode",
      lat: -28.0,
      lon: 8.0,
      summary: "East of the antipode.",
      group: "antipodes",
    },
    {
      id: "equator",
      name: "Equator",
      lat: 0.0,
      lon: 0.0,
      summary: "0°N, 0°E.",
      group: "sites",
    },
    {
      id: "hokusai",
      name: "Hokusai",
      lat: 58.0,
      lon: 17.0,
      summary: "Bright crater with long rays.",
      group: "sites",
    },
    {
      id: "rachmaninoff",
      name: "Rachmaninoff",
      lat: 27.7,
      lon: 57.6,
      summary: "Basin with hollows.",
      group: "sites",
    },
    {
      id: "raditladi",
      name: "Raditladi",
      lat: 27.2,
      lon: 119.0,
      summary: "Basin east of Caloris.",
      group: "sites",
    },
    {
      id: "caloris",
      name: "Caloris",
      lat: 30.5,
      lon: 189.8,
      summary: "Largest basin.",
      group: "sites",
    },
    {
      id: "tolstoj",
      name: "Tolstoj",
      lat: -16.2,
      lon: -163.5,
      summary: "Old dark basin.",
      group: "sites",
    },
    {
      id: "beethoven",
      name: "Beethoven",
      lat: -20.8,
      lon: -123.4,
      summary: "Southern plains basin.",
      group: "sites",
    },
    {
      id: "discovery",
      name: "Discovery Rupes",
      lat: -56.3,
      lon: -38.3,
      summary: "Long cliff (scarp).",
      group: "sites",
    },
    {
      id: "prokofiev",
      name: "Prokofiev",
      lat: 85.8,
      lon: 62.9,
      summary: "North pole ice crater.",
      group: "sites",
    },
    {
      id: "chao",
      name: "Chao Meng-Fu",
      lat: -87.3,
      lon: -132.4,
      summary: "South pole ice crater.",
      group: "sites",
    },
  ];

  let magCut = "b";
  let magZoom = 1;
  let colorMode = "thermal";
  let activeChartKey = null;

  let siteId = "equator";
  let hour = 0;
  let state = null;
  let forecast = null;
  let sitesNow = null;
  let hourTimer = null;

  const CUT_TITLES = {
    b: "Magnetic field",
    xz: "Side view",
    xy: "Top view",
    lines: "Field lines",
    standoff: "Shield size",
    density: "Plasma",
    clock: "IMF",
  };

  const METRIC_CHARTS = [
    { key: "solar", title: "Solar activity — 24 h", canvas: "cvSolar", w: 720, h: 200 },
    { key: "radiation", title: "Radiation — 24 h", canvas: "cvRad", w: 720, h: 200 },
    { key: "standoff_rm", title: "Shield size — 24 h", canvas: "cvRss", w: 720, h: 200 },
    { key: "imf", title: "Magnetic field — 24 h", canvas: "cvImf", w: 720, h: 200 },
    { key: "p_dyn", title: "Wind pressure — 24 h", canvas: "cvPdyn", w: 720, h: 200 },
    { key: "pressure", title: "Wind vs field pressure", canvas: "cvP", w: 560, h: 200 },
    { key: "sites", title: "Radiation by site", canvas: "cvSites", w: 560, h: 220 },
  ];

  function $(id) {
    return document.getElementById(id);
  }

  function fmt(v, d) {
    if (v == null || !Number.isFinite(Number(v))) return "—";
    return Number(v).toFixed(d);
  }

  function isOverviewLoc(loc) {
    return !!(loc && (loc.overview || loc.id === "overview" || loc.siteId === "overview" || /overview/i.test(loc.name || "")));
  }

  function matchSite(lat, lon, loc) {
    if (isOverviewLoc(loc)) return SITES.find((s) => s.id === "overview") || SITES[0];
    let best = SITES.find((s) => !s.overview) || SITES[0];
    let bestD = Infinity;
    for (const s of SITES) {
      if (s.overview) continue;
      const d = Math.hypot(s.lat - lat, ((s.lon - lon + 540) % 360) - 180);
      if (d < bestD) {
        bestD = d;
        best = s;
      }
    }
    return best;
  }

  function syncLocs() {
    const arr = window.LOCS || [];
    arr.length = 0;
    SITES.forEach((s) =>
      arr.push({
        name: s.name,
        lat: s.lat,
        lon: s.lon,
        id: s.id,
        summary: s.summary,
        image: s.image,
        overview: !!s.overview,
        group: s.group || "sites",
      })
    );
    window.LOCS = arr;
  }

  window.fetchMercuryForecast = async function fetchMercuryForecast(lat, lon, hours = 24) {
    const locHint = (window.LOCS || [])[window._topoLocIdx | 0] || { lat, lon };
    const site = matchSite(Number(lat) || 0, Number(lon) || 0, locHint);
    const physId = site.id === "overview" ? "equator" : site.id;
    siteId = physId;
    const h = Math.min(48, Math.max(24, Number(hours) || 24));
    const r = await fetch(api(`/api/mercury/forecast?site=${encodeURIComponent(physId)}&hours=${h}`));
    if (!r.ok) throw new Error("mercury forecast " + r.status);
    const raw = await r.json();
    forecast = raw;
    state = raw.now || null;
    window._mercuryNow = state;
    window._mercuryForecast = raw;
    window._preferServerForecast = true;
    if (raw.confidence) window._lastConfidence = raw.confidence;
    if (typeof window.updateLocationColors === "function") {
      try { window.updateLocationColors(); } catch (_) {}
    }
    try {
      const disk = await fetch(api("/api/solar/disk?max=40"));
      if (disk.ok) window._solarDisk = await disk.json();
    } catch (_) {}

    const n = (raw.time && raw.time.length) || h;
    const out = {
      time: raw.time || Array.from({ length: n }, (_, i) => i),
      radiation: raw.radiation || [],
      solar: raw.solar || [],
      temperature: raw.temperature || [],
      temperature_k: raw.temperature_k || [],
      illumination: raw.illumination || [],
      standoff_rm: raw.standoff_rm || [],
      p_dyn: raw.p_dyn_npa || [],
      p_dyn_npa: raw.p_dyn_npa || [],
      imf_bz: raw.imf_bz || [],
      imf_b_mag: raw.imf_b_mag || [],
      kp: raw.kp || [],
      f107: raw.f107 || [],
      dst: raw.dst || [],
      flare_index: raw.flare_index || [],
      sep: raw.sep || [],
      protons: raw.protons || [],
      flares: raw.flares || [],
      cme: raw.cme || [],
      storm: raw.storm || [],
      cusp_lat: raw.cusp_lat || [],
      density: raw.density || [],
      speed: raw.speed || [],
      solar_constant: raw.solar_constant || [],
      lst: raw.lst || [],
      dust: raw.dust || Array(n).fill(0),
      moonquakes: raw.moonquakes || Array(n).fill(0),
      micrometeorites: raw.micrometeorites || Array(n).fill(0),
      evaRisk: raw.evaRisk || Array(n).fill(0),
      comms: raw.comms || Array(n).fill(0),
      channel_origin: raw.channel_origin || {},
      confidence_pct: Number(raw.confidence_pct ?? raw.confidence?.overall_pct ?? 62),
      confidence: raw.confidence || { overall_pct: Number(raw.confidence_pct ?? 62), basis: "mercury_physics" },
      confidence_series: raw.confidence_series || [],
      earth_link: "N/A (Mercury)",
      mercury: true,
      now: raw.now,
      lst_curve: raw.lst_curve,
      flare_class: raw.flare_class,
      ml_policy: raw.ml_policy,
      r_au: raw.r_au,
      site: raw.site,
      source: raw.source,
      alerts: (raw.now && raw.now.alerts) || [],
    };
    return out;
  };

  window.serverPredict = async function serverPredictMercury() {
    const now = window._mercuryNow;
    if (!now || !now.prediction) return null;
    const p = now.prediction;
    const conf = now.confidence || {};
    const pct = Number(now.confidence_pct ?? conf.overall_pct ?? 62);
    return {
      refined_estimate: {
        radiation: p.radiation,
        temperature: p.temperature,
        solar: p.solar,
        dust: p.dust ?? 0,
        moonquakes: p.moonquakes ?? 0,
        micrometeorites: p.micrometeorites ?? 0,
      },
      confidence_pct: pct,
      confidence: {
        overall_pct: pct,
        basis: conf.basis || "mercury_physics+goes_swpc",
        per_channel_pct: conf.per_channel_pct || {},
      },
      plausibility: Math.max(0.4, Math.min(0.95, pct / 100)),
      gated_fields: [],
      source: now.source || "mercury_physics",
    };
  };

  async function loadState(h) {
    const q = new URLSearchParams({ site: siteId, hour: String(h) });
    const r = await fetch(api("/api/mercury/state?" + q.toString()));
    if (!r.ok) throw new Error("mercury state " + r.status);
    state = await r.json();
    window._mercuryNow = state;
    return state;
  }

  async function loadSites() {
    try {
      const r = await fetch(api("/api/mercury/sites"));
      if (r.ok) {
        sitesNow = await r.json();
        window._mercurySitesNow = sitesNow;
        if (typeof window.updateLocationColors === "function") {
          try { window.updateLocationColors(); } catch (_) {}
        } else if (typeof updateLocationColors === "function") {
          try { updateLocationColors(); } catch (_) {}
        }
      }
    } catch (_) {}
  }

  function relocateMagPanel(hero) {
    if (!hero) return;
    const slider = $("slider-section");
    if (slider && slider.parentNode) {
      slider.parentNode.insertBefore(hero, slider);
      return;
    }
    const ft = document.querySelector(".forecast-title");
    if (ft && ft.parentNode) {
      ft.parentNode.insertBefore(hero, ft);
      return;
    }
    const loc = $("locationName");
    if (loc && loc.parentNode) {
      loc.parentNode.insertBefore(hero, loc.nextSibling);
    }
  }

  function placeHelioAfterHero(hero, helio) {
    if (!hero || !helio || !hero.parentNode) return;
    hero.parentNode.insertBefore(helio, hero.nextSibling);
  }

  function injectMagShell() {
    let hero = $("mercMagHero");
    let helio = $("mercHelioPanel");
    if (hero && $("cvMag") && $("timelapseBar")) {
      relocateMagPanel(hero);
      placeHelioAfterHero($("mercMagHero"), $("mercHelioPanel"));
      bindMagControls();
      return;
    }
    if (hero && !$("timelapseBar")) {
      try { hero.remove(); } catch (_) {}
      hero = null;
    }

    const map = $("mapContainer");
    if (!map) return;

    map.dataset.mercuryMag = "5";

    hero = document.createElement("div");
    hero.className = "merc-mag-hero";
    hero.id = "mercMagHero";
    hero.innerHTML = `
      <div class="merc-mag-hero-head">
        <div>
          <h2 class="merc-mag-heading" id="mercCutTitle">Magnetic field</h2>
          <p class="merc-mag-sub" id="mercMagMeta">Shield — · wind — · Bz — · flare —</p>
        </div>
        <div class="merc-mag-toolbar">
          <div class="merc-cut-tabs" id="mercCutTabs" role="tablist">
            <button type="button" data-cut="b" class="active">Field</button>
            <button type="button" data-cut="xz">Side</button>
            <button type="button" data-cut="xy">Top</button>
            <button type="button" data-cut="lines">Lines</button>
            <button type="button" data-cut="standoff">Size</button>
            <button type="button" data-cut="density">Plasma</button>
            <button type="button" data-cut="clock">IMF</button>
          </div>
          <div class="merc-color-modes" id="mercColorModes">
            <button type="button" data-color="thermal" class="active">Thermal</button>
            <button type="button" data-color="mono">Mono</button>
            <button type="button" data-color="contrast">Contrast</button>
          </div>
          <div class="merc-zoom-btns" id="mercZoomBtns">
            <button type="button" data-zoom="in" title="Zoom in">+</button>
            <button type="button" data-zoom="out" title="Zoom out">−</button>
            <button type="button" data-zoom="reset" title="Reset zoom">Reset</button>
          </div>
        </div>
      </div>
      <div class="merc-mag-canvas-wrap">
        <canvas id="cvMag" width="900" height="520"></canvas>
      </div>
      <div class="merc-legend" id="magLegend"></div>
      <input type="hidden" id="mercMagHour" min="0" max="23" value="0" />
      <div class="timelapse-container merc-mag-tl">
        <div class="timelapse-header">
          <span class="timelapse-title">Forecast hour</span>
          <div class="timelapse-controls">
            <button type="button" class="timelapse-btn" id="playPauseBtn" onclick="toggleTimelapsePlay()" title="Play / pause">
              <svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor">
                <path id="playIcon" d="M2 1v10l8-5z"/>
                <path id="pauseIcon" d="M3 1h2v10H3zM7 1h2v10H7z" style="display: none;"/>
              </svg>
            </button>
            <button type="button" class="timelapse-btn" onclick="resetTimelapse()" title="Reset">↺</button>
            <select id="timelapseSpeed" onchange="updateTimelapseSpeed()" class="timelapse-speed" title="Playback speed">
              <option value="0.5">0.5x</option>
              <option value="1" selected>1x</option>
              <option value="2">2x</option>
              <option value="4">4x</option>
            </select>
          </div>
        </div>
        <div class="timelapse-bar-container">
          <div class="timelapse-bar" id="timelapseBar">
            <div class="timelapse-progress" id="timelapseProgress"></div>
            <div class="timelapse-handle" id="timelapseHandle"></div>
            <div class="timelapse-markers" id="timelapseMarkers"></div>
          </div>
        </div>
        <div class="timelapse-info">
          <span id="timelapseCurrentTime">Hour 0 / T+0 h</span>
          <span id="timelapseDuration">24 Hours</span>
        </div>
      </div>`;

    helio = document.createElement("div");
    helio.className = "merc-helio-panel";
    helio.id = "mercHelioPanel";
    helio.innerHTML = `
      <div class="merc-helio-head">
        <h3>Sun, Mercury, and Earth</h3>
        <p class="merc-helio-sub" id="mercHelioSub">Where Mercury sits relative to Earth</p>
      </div>
      <canvas id="cvHelio" width="720" height="280"></canvas>`;

    map.innerHTML = '<div class="map-header merc-map-minimal"><div class="map-title" id="mapTitle"></div></div>';
    map.parentNode.insertBefore(hero, map);
    map.parentNode.insertBefore(helio, map);
    relocateMagPanel(hero);
    placeHelioAfterHero(hero, helio);

    bindMagControls();
  }

  function bindMagControls() {
    const tabs = $("mercCutTabs");
    if (tabs && !tabs.dataset.bound) {
      tabs.dataset.bound = "1";
      tabs.addEventListener("click", (e) => {
        const btn = e.target.closest("button[data-cut]");
        if (!btn) return;
        magCut = btn.dataset.cut;
        tabs.querySelectorAll("button").forEach((b) => b.classList.toggle("active", b === btn));
        const t = $("mercCutTitle");
        if (t) t.textContent = CUT_TITLES[magCut] || CUT_TITLES.b;
        drawCombinedCut();
      });
    }

    const colors = $("mercColorModes");
    if (colors && !colors.dataset.bound) {
      colors.dataset.bound = "1";
      colors.addEventListener("click", (e) => {
        const btn = e.target.closest("button[data-color]");
        if (!btn) return;
        colorMode = btn.dataset.color;
        colors.querySelectorAll("button").forEach((b) => b.classList.toggle("active", b === btn));
        drawCombinedCut();
      });
    }

    const zoom = $("mercZoomBtns");
    if (zoom && !zoom.dataset.bound) {
      zoom.dataset.bound = "1";
      zoom.addEventListener("click", (e) => {
        const btn = e.target.closest("button[data-zoom]");
        if (!btn) return;
        if (btn.dataset.zoom === "in") magZoom = Math.min(3, magZoom * 1.25);
        else if (btn.dataset.zoom === "out") magZoom = Math.max(0.5, magZoom / 1.25);
        else magZoom = 1;
        drawCombinedCut();
      });
    }

    const slider = $("mercMagHour");
    if (slider && !slider.dataset.bound) {
      slider.dataset.bound = "1";
      slider.addEventListener("input", () => {
        const h = Number(slider.value) || 0;
        hour = h;
        window._timelapseHour = h;
        if (typeof window.applyTimelapseFrame === "function") window.applyTimelapseFrame(h, 24);
        else if (typeof window.onMercuryHourChange === "function") window.onMercuryHourChange(h);
      });
    }
    if (typeof window.initTimelapseScrubber === "function") {
      try { window.initTimelapseScrubber(); } catch (_) {}
    }
    syncMagSlider();
  }

  function syncMagSlider() {
    const slider = $("mercMagHour");
    const val = $("mercMagHourVal");
    const meta = $("mercMagMeta");
    if (slider) slider.value = String(hour);
    if (val) val.textContent = `T+${hour} h`;
    const cur = $("timelapseCurrentTime");
    if (cur) cur.textContent = `Hour ${hour} / T+${hour} h`;
    if (typeof window.setTimelapseUI === "function") {
      try { window.setTimelapseUI(hour, 24); } catch (_) {}
    } else {
      const pct = (hour / 23) * 100;
      const progress = $("timelapseProgress");
      const handle = $("timelapseHandle");
      if (progress) progress.style.width = pct + "%";
      if (handle) handle.style.left = pct + "%";
    }
    if (meta && state) {
      const m = state.magnetosphere || {};
      const phys = state.physics || {};
      const flare = phys.flare_class || fmt(phys.flare_index, 1);
      meta.textContent = `Shield ${fmt(m.standoff_rm, 2)} RM · wind ${fmt(phys.p_dyn_npa, 1)} nPa · Bz ${fmt(state.wind_mercury?.imf_bz, 1)} nT · flare ${flare}`;
    }
  }

  function prepMagCanvas() {
    const cv = $("cvMag");
    if (!cv) return null;
    const wrap = cv.parentElement;
    const cssW = Math.max(320, wrap?.clientWidth || cv.clientWidth || 900);
    const cssH = Math.max(360, Math.round(cssW * (520 / 900)));
    const dpr = Math.min(2.5, window.devicePixelRatio || 1);
    const bw = Math.floor(cssW * dpr);
    const bh = Math.floor(cssH * dpr);
    if (cv.width !== bw || cv.height !== bh) {
      cv.width = bw;
      cv.height = bh;
    }
    cv.style.width = cssW + "px";
    cv.style.height = cssH + "px";
    const ctx = cv.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.fillStyle = "#07090c";
    ctx.fillRect(0, 0, cssW, cssH);

    if (magZoom !== 1) {
      ctx.translate(cssW / 2, cssH / 2);
      ctx.scale(magZoom, magZoom);
      ctx.translate(-cssW / 2, -cssH / 2);
    }
    return { cv, ctx, W: cssW, H: cssH, dpr };
  }

  function drawAxisTicks(ctx, W, H, g, yKey) {
    const pad = 8;
    const ymin = g[yKey === "y" ? "y_min" : "z_min"];
    const ymax = g[yKey === "y" ? "y_max" : "z_max"];
    ctx.fillStyle = "rgba(200,210,220,0.75)";
    ctx.font = "10px IBM Plex Sans, sans-serif";
    ctx.textAlign = "left";
    for (let i = 0; i <= 4; i++) {
      const xVal = g.x_min + ((g.x_max - g.x_min) * i) / 4;
      const x = ((xVal - g.x_min) / (g.x_max - g.x_min)) * W;
      ctx.fillText(fmt(xVal, 1), Math.max(pad, Math.min(W - 28, x - 10)), H - 4);
    }
    ctx.textAlign = "left";
    for (let i = 0; i <= 4; i++) {
      const yVal = ymax - ((ymax - ymin) * i) / 4;
      const y = (i / 4) * H;
      ctx.fillText(fmt(yVal, 1), 4, Math.max(12, Math.min(H - 6, y + 4)));
    }
    ctx.fillStyle = "rgba(143,163,184,0.85)";
    ctx.fillText("X (R_M)", W - 52, H - 16);
    ctx.fillText(yKey === "y" ? "Y" : "Z", 4, 14);
  }

  function xyFromGrid(W, H, x, z, g, yKey) {
    const ymin = g[yKey === "y" ? "y_min" : "z_min"];
    const ymax = g[yKey === "y" ? "y_max" : "z_max"];
    const px = ((x - g.x_min) / (g.x_max - g.x_min)) * W;
    const py = (1 - (z - ymin) / (ymax - ymin)) * H;
    return [px, py];
  }

  function drawRegionGrid(prep, grid, colors, mag, yKey) {
    const { ctx, W, H } = prep;
    if (!grid) return;
    const ny = yKey === "y" ? grid.ny : grid.nz;
    const cw = W / grid.nx;
    const ch = H / ny;
    for (let j = 0; j < ny; j++) {
      for (let i = 0; i < grid.nx; i++) {
        let col = colors[grid.cells[j][i]] || "#111";
        if (colorMode === "mono") col = shadeMono(col);
        else if (colorMode === "contrast") col = shadeContrast(col);
        ctx.fillStyle = col;
        ctx.globalAlpha = 0.62;
        ctx.fillRect(i * cw, j * ch, cw + 0.5, ch + 0.5);
      }
    }
    ctx.globalAlpha = 1;
    if (!mag) return;
    function strokePoly(pts, color, width) {
      if (!pts || pts.length < 2) return;
      ctx.beginPath();
      pts.forEach((p, n) => {
        const [x, y] = xyFromGrid(W, H, p[0], p[1], grid, yKey);
        if (n === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.strokeStyle = color;
      ctx.lineWidth = width;
      ctx.stroke();
    }
    if (yKey !== "y") {
      strokePoly(mag.bow_shock?.north, "#e8c48a", 1.5);
      strokePoly(mag.bow_shock?.south, "#e8c48a", 1.5);
      strokePoly(mag.magnetopause?.north, "#e07a3d", 2.2);
      strokePoly(mag.magnetopause?.south, "#e07a3d", 2.2);
      (mag.field_lines || []).forEach((ln) => {
        strokePoly(ln.points, ln.closed ? colors.closed_line || "#7ec8d6" : colors.open_line || "#d45d8c", ln.closed ? 1.2 : 0.9);
      });
    } else {
      const rss = mag.standoff_rm;
      const rbs = mag.bow_shock_rm;
      [
        [rbs, "#e8c48a"],
        [rss, "#e07a3d"],
      ].forEach(([R, col]) => {
        ctx.beginPath();
        for (let i = 0; i <= 64; i++) {
          const th = (Math.PI * i) / 64;
          const r = R * Math.pow(2 / Math.max(1e-6, 1 + Math.cos(th)), 0.5);
          const x = r * Math.cos(th);
          const y = r * Math.sin(th);
          const [px, py] = xyFromGrid(W, H, x, y, grid, "y");
          if (i === 0) ctx.moveTo(px, py);
          else ctx.lineTo(px, py);
        }
        for (let i = 64; i >= 0; i--) {
          const th = (Math.PI * i) / 64;
          const r = R * Math.pow(2 / Math.max(1e-6, 1 + Math.cos(th)), 0.5);
          const x = r * Math.cos(th);
          const y = -r * Math.sin(th);
          const [px, py] = xyFromGrid(W, H, x, y, grid, "y");
          ctx.lineTo(px, py);
        }
        ctx.strokeStyle = col;
        ctx.lineWidth = 1.8;
        ctx.stroke();
      });
    }
    const [cx, cy] = xyFromGrid(W, H, 0, 0, grid, yKey);
    const [ex] = xyFromGrid(W, H, 1, 0, grid, yKey);
    const pr = Math.abs(ex - cx);
    ctx.fillStyle = colors.planet || "#8a7a6b";
    ctx.beginPath();
    ctx.arc(cx, cy, pr, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#f0a060";
    ctx.font = "11px IBM Plex Sans, sans-serif";
    ctx.fillText("SUN →", W - 64, 18);
    drawAxisTicks(ctx, W, H, grid, yKey);
  }

  function shadeMono(hex) {
    return "rgba(180,140,100,0.55)";
  }

  function shadeContrast(hex) {
    if (!hex || typeof hex !== "string") return "#e07a3d";
    return hex;
  }

  function drawMagnetosphere() {
    const prep = prepMagCanvas();
    const mag = state?.magnetosphere;
    if (!prep || !mag?.grid) return;
    drawRegionGrid(prep, mag.grid, mag.colors || {}, mag, "z");
    const leg = $("magLegend");
    if (leg) {
      leg.innerHTML = (mag.legend || [])
        .map(([k, lab]) => `<span><i style="background:${(mag.colors || {})[k]}"></i>${lab}</span>`)
        .join("");
    }
  }

  function drawEquatorial() {
    const prep = prepMagCanvas();
    const mag = state?.magnetosphere;
    if (!prep || !mag?.equatorial_grid) return;
    drawRegionGrid(prep, mag.equatorial_grid, mag.colors || {}, mag, "y");
    const leg = $("magLegend");
    if (leg) {
      leg.innerHTML = (mag.legend || [])
        .map(([k, lab]) => `<span><i style="background:${(mag.colors || {})[k]}"></i>${lab}</span>`)
        .join("");
    }
  }

  function bmagColor(t) {
    if (colorMode === "mono") {
      const g = Math.round(40 + t * 180);
      return `rgb(${g},${Math.round(g * 0.75)},${Math.round(g * 0.45)})`;
    }
    const stops =
      colorMode === "contrast"
        ? [
            [0, [10, 20, 80]],
            [0.35, [20, 200, 220]],
            [0.65, [255, 220, 40]],
            [1, [255, 40, 20]],
          ]
        : [
            [0, [30, 60, 120]],
            [0.35, [45, 160, 180]],
            [0.65, [230, 200, 80]],
            [1, [220, 70, 50]],
          ];
    let a = stops[0],
      b = stops[stops.length - 1];
    for (let i = 0; i < stops.length - 1; i++) {
      if (t >= stops[i][0] && t <= stops[i + 1][0]) {
        a = stops[i];
        b = stops[i + 1];
        break;
      }
    }
    const u = (t - a[0]) / Math.max(1e-6, b[0] - a[0]);
    const c = a[1].map((v, i) => Math.round(v + (b[1][i] - v) * u));
    return `rgb(${c[0]},${c[1]},${c[2]})`;
  }

  function drawBmag() {
    const prep = prepMagCanvas();
    const mag = state?.magnetosphere;
    const g = mag?.bmag_grid;
    if (!prep || !g) return;
    const { ctx, W, H, cv } = prep;
    const cw = W / g.nx;
    const ch = H / g.nz;
    const vmin = Math.log10(g.vmin || 5);
    const vmax = Math.log10(g.vmax || 200);
    for (let j = 0; j < g.nz; j++) {
      for (let i = 0; i < g.nx; i++) {
        const v = g.values[j][i];
        if (v <= 0) ctx.fillStyle = "#8a7a6b";
        else {
          const t = Math.max(0, Math.min(1, (Math.log10(v) - vmin) / (vmax - vmin)));
          ctx.fillStyle = bmagColor(t);
        }
        ctx.fillRect(i * cw, j * ch, cw + 0.5, ch + 0.5);
      }
    }
    if (mag.magnetopause) {
      const stroke = (pts, col) => {
        if (!pts) return;
        ctx.beginPath();
        pts.forEach((p, n) => {
          const [x, y] = xyFromGrid(W, H, p[0], p[1], g, "z");
          if (n === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        });
        ctx.strokeStyle = col;
        ctx.lineWidth = 1.6;
        ctx.stroke();
      };
      stroke(mag.magnetopause.north, "rgba(255,255,255,0.75)");
      stroke(mag.magnetopause.south, "rgba(255,255,255,0.75)");
    }
    ctx.fillStyle = "#e6eef8";
    ctx.font = "11px IBM Plex Sans, sans-serif";
    ctx.fillText("log |B| nT", 10, 16);
    drawAxisTicks(ctx, W, H, g, "z");
    const leg = $("magLegend");
    if (leg) {
      leg.innerHTML =
        '<span><i style="background:#1e3c78"></i>IMF</span><span><i style="background:#e8c850"></i>compressed</span><span><i style="background:#dc4632"></i>dipole</span>';
    }
    void cv;
  }

  function drawFieldLinesView() {
    const prep = prepMagCanvas();
    const mag = state?.magnetosphere;
    if (!prep || !mag) return;
    const { ctx, W, H } = prep;
    const g = mag.grid || {
      x_min: -4,
      x_max: 3,
      z_min: -3,
      z_max: 3,
    };
    const rss = Math.max(1.05, Number(mag.standoff_rm) || 1.45);

    const grd = ctx.createRadialGradient(W * 0.55, H * 0.5, 20, W * 0.55, H * 0.5, W * 0.55);
    grd.addColorStop(0, "rgba(224,122,61,0.12)");
    grd.addColorStop(1, "#07090c");
    ctx.fillStyle = grd;
    ctx.fillRect(0, 0, W, H);

    const strokePoly = (pts, color, width) => {
      if (!pts || pts.length < 2) return;
      ctx.beginPath();
      pts.forEach((p, n) => {
        const [x, y] = xyFromGrid(W, H, p[0], p[1], g, "z");
        if (n === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.strokeStyle = color;
      ctx.lineWidth = width;
      ctx.stroke();
    };
    strokePoly(mag.magnetopause?.north, "#e07a3d", 2.4);
    strokePoly(mag.magnetopause?.south, "#e07a3d", 2.4);
    strokePoly(mag.bow_shock?.north, "#e8c48a", 1.4);
    strokePoly(mag.bow_shock?.south, "#e8c48a", 1.4);
    (mag.field_lines || []).forEach((ln) => {
      strokePoly(ln.points, ln.closed ? "#7ec8d6" : "#e25b5b", ln.closed ? 1.4 : 1.1);
    });

    if (!(mag.field_lines || []).length) {
      for (let i = -4; i <= 4; i++) {
        if (i === 0) continue;
        ctx.beginPath();
        for (let t = 0; t <= 40; t++) {
          const th = (t / 40) * Math.PI;
          const L = 0.9 + Math.abs(i) * 0.35 * rss;
          const r = L * Math.sin(th) * Math.sin(th);
          const x = r * Math.cos(th) * Math.sign(i);
          const z = r * Math.sin(th) * (i > 0 ? 1 : -1) * 0.9;
          const [px, py] = xyFromGrid(W, H, x - 0.2, z, g, "z");
          if (t === 0) ctx.moveTo(px, py);
          else ctx.lineTo(px, py);
        }
        ctx.strokeStyle = "rgba(126,200,214,0.7)";
        ctx.lineWidth = 1.1;
        ctx.stroke();
      }
    }
    const [cx, cy] = xyFromGrid(W, H, 0, 0, g, "z");
    const [ex] = xyFromGrid(W, H, 1, 0, g, "z");
    ctx.fillStyle = "#8a7a6b";
    ctx.beginPath();
    ctx.arc(cx, cy, Math.abs(ex - cx), 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#e6eef8";
    ctx.font = "12px IBM Plex Sans, sans-serif";
    ctx.fillText(`Shield ${fmt(rss, 2)} RM`, 14, 22);
    drawAxisTicks(ctx, W, H, g, "z");
    const leg = $("magLegend");
    if (leg) {
      leg.innerHTML =
        '<span><i style="background:#7ec8d6"></i>closed</span><span><i style="background:#e25b5b"></i>open</span><span><i style="background:#e07a3d"></i>MP</span>';
    }
  }

  function drawStandoffView() {
    const prep = prepMagCanvas();
    const mag = state?.magnetosphere;
    if (!prep || !mag) return;
    const { ctx, W, H } = prep;
    const rss = Math.max(1.02, Number(mag.standoff_rm) || 1.45);
    const rbs = Math.max(rss + 0.2, Number(mag.bow_shock_rm) || rss * 1.3);
    const cx = W * 0.42;
    const cy = H * 0.52;
    const pr = Math.min(W, H) * 0.08;
    ctx.fillStyle = "rgba(242,197,109,0.1)";
    ctx.fillRect(W - 80, 0, 80, H);
    ctx.fillStyle = "#f0a060";
    ctx.font = "12px IBM Plex Sans, sans-serif";
    ctx.fillText("SUN →", W - 62, 24);

    const drawShue = (R, col, width) => {
      ctx.beginPath();
      for (let i = 0; i <= 72; i++) {
        const th = -Math.PI + (Math.PI * i) / 36;
        const r = R * Math.pow(2 / Math.max(1e-6, 1 + Math.cos(Math.min(Math.PI - 0.05, Math.abs(th)))), 0.55);
        const x = cx + r * pr * Math.cos(th);
        const y = cy + r * pr * 0.88 * Math.sin(th);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.strokeStyle = col;
      ctx.lineWidth = width;
      ctx.stroke();
    };
    drawShue(rbs, "#e8c48a", 1.6);
    drawShue(rss, "#e07a3d", 2.6);

    ctx.fillStyle = "#8a7a6b";
    ctx.beginPath();
    ctx.arc(cx, cy, pr, 0, Math.PI * 2);
    ctx.fill();

    ctx.strokeStyle = "rgba(224,122,61,0.5)";
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.lineTo(cx + rss * pr, cy);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = "#e6eef8";
    ctx.font = "13px IBM Plex Sans, sans-serif";
    ctx.fillText(`Shield = ${fmt(rss, 2)} RM`, 18, 28);
    ctx.fillStyle = "#8fa3b8";
    ctx.fillText(`Bow shock ≈ ${fmt(rbs, 2)} R_M`, 18, 48);
    ctx.fillText(`Wind ${fmt(mag.p_dyn_npa ?? state?.physics?.p_dyn_npa, 1)} nPa`, 18, 68);
    const leg = $("magLegend");
    if (leg) {
      leg.innerHTML =
        '<span><i style="background:#e07a3d"></i>magnetopause</span><span><i style="background:#e8c48a"></i>bow shock</span>';
    }
  }

  function drawDensityView() {
    const prep = prepMagCanvas();
    if (!prep) return;
    const { ctx, W, H } = prep;
    const dens = Number(state?.physics?.density ?? forecast?.density?.[hour] ?? 40);
    const spd = Number(state?.wind_mercury?.speed ?? forecast?.speed?.[hour] ?? 400);
    const rss = Math.max(1.05, Number(state?.magnetosphere?.standoff_rm) || 1.4);
    const cx = W * 0.55;
    const cy = H * 0.5;
    const pr = 28;
    for (let j = 0; j < 48; j++) {
      for (let i = 0; i < 72; i++) {
        const x = (i / 72) * W;
        const y = (j / 48) * H;
        const dx = (x - cx) / (pr * rss * 2.2);
        const dy = (y - cy) / (pr * rss * 1.8);
        const inside = dx * dx + dy * dy < 1;
        const sunSide = x < cx;
        let t = sunSide ? dens / 80 : dens / 200;
        if (inside) t *= 0.35;
        t = Math.max(0, Math.min(1, t));
        ctx.fillStyle = `rgba(${Math.round(40 + t * 180)},${Math.round(60 + t * 80)},${Math.round(100 - t * 40)},0.85)`;
        ctx.fillRect(x, y, W / 72 + 1, H / 48 + 1);
      }
    }
    ctx.strokeStyle = "#e07a3d";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.ellipse(cx, cy, pr * rss * 1.8, pr * rss * 1.4, 0, 0, Math.PI * 2);
    ctx.stroke();
    ctx.fillStyle = "#8a7a6b";
    ctx.beginPath();
    ctx.arc(cx, cy, pr, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#e6eef8";
    ctx.font = "12px IBM Plex Sans, sans-serif";
    ctx.fillText(`n ≈ ${fmt(dens, 1)} cm⁻³ · V ${fmt(spd, 0)} km/s`, 14, 22);
    const leg = $("magLegend");
    if (leg) {
      leg.innerHTML =
        '<span><i style="background:#dc8a3c"></i>dense SW</span><span><i style="background:#284060"></i>wake / magnetosphere</span>';
    }
  }

  function drawClockOnMag() {
    const prep = prepMagCanvas();
    if (!prep) return;
    const { ctx, W, H } = prep;
    const clock = state?.magnetosphere?.imf_clock;
    const cx = W * 0.38;
    const cy = H * 0.52;
    const r = Math.min(W, H) * 0.22;
    ctx.strokeStyle = "rgba(140,170,200,0.28)";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.stroke();
    ctx.fillStyle = "#8fa3b8";
    ctx.font = "12px IBM Plex Sans, sans-serif";
    ctx.fillText("+Bz", cx - 12, cy - r - 10);
    ctx.fillText("−Bz", cx - 12, cy + r + 18);
    ctx.fillText("+By", cx + r + 10, cy + 4);
    if (clock) {
      const ang = (Number(clock.angle_deg) * Math.PI) / 180;
      const x2 = cx + Math.sin(ang) * (r - 10);
      const y2 = cy - Math.cos(ang) * (r - 10);
      ctx.strokeStyle = clock.orientation === "southward" ? "#e25b5b" : "#e07a3d";
      ctx.lineWidth = 4;
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.lineTo(x2, y2);
      ctx.stroke();
      ctx.fillStyle = "#e6eef8";
      ctx.font = "14px IBM Plex Sans, sans-serif";
      ctx.fillText(`${clock.orientation}`, W * 0.62, H * 0.35);
      ctx.fillStyle = "#8fa3b8";
      ctx.font = "13px IBM Plex Sans, sans-serif";
      ctx.fillText(`By ${fmt(clock.by_nt, 1)} nT`, W * 0.62, H * 0.35 + 24);
      ctx.fillText(`Bz ${fmt(clock.bz_nt, 1)} nT`, W * 0.62, H * 0.35 + 44);
      ctx.fillText(`${fmt(clock.angle_deg, 0)}°`, W * 0.62, H * 0.35 + 64);
    }
    const leg = $("magLegend");
    if (leg) {
      leg.innerHTML =
        '<span><i style="background:#e07a3d"></i>northward</span><span><i style="background:#e25b5b"></i>southward</span>';
    }
  }

  function drawCombinedCut() {
    if (magCut === "xy") drawEquatorial();
    else if (magCut === "b") drawBmag();
    else if (magCut === "lines") drawFieldLinesView();
    else if (magCut === "standoff") drawStandoffView();
    else if (magCut === "density") drawDensityView();
    else if (magCut === "clock") drawClockOnMag();
    else drawMagnetosphere();
  }

  function lineChart(canvas, series, color, extra) {
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const cssW = canvas.clientWidth || canvas.width || 720;
    const cssH = canvas.clientHeight || 200;
    if (canvas.width !== Math.floor(cssW * dpr) || canvas.height !== Math.floor(cssH * dpr)) {
      canvas.width = Math.floor(cssW * dpr);
      canvas.height = Math.floor(cssH * dpr);
    }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.fillStyle = "#07090c";
    ctx.fillRect(0, 0, cssW, cssH);
    const pad = { l: 42, r: 12, t: 12, b: 24 };
    const w = cssW - pad.l - pad.r;
    const h = cssH - pad.t - pad.b;
    const vals = (series || []).filter((v) => Number.isFinite(v));
    if (!vals.length) return;
    let lo = Math.min(...vals);
    let hi = Math.max(...vals);
    if (extra?.second) {
      const s2 = extra.second.filter((v) => Number.isFinite(v));
      if (s2.length) {
        lo = Math.min(lo, ...s2);
        hi = Math.max(hi, ...s2);
      }
    }
    if (lo === hi) {
      lo -= 1;
      hi += 1;
    }
    if (extra?.zero) {
      lo = Math.min(lo, 0);
      hi = Math.max(hi, 0);
    }
    if (extra?.lstAxis) {
      const xDawn = pad.l + (6 / 24) * w;
      const xDusk = pad.l + (18 / 24) * w;
      ctx.fillStyle = "rgba(40, 60, 90, 0.22)";
      ctx.fillRect(pad.l, pad.t, xDawn - pad.l, h);
      ctx.fillRect(xDusk, pad.t, pad.l + w - xDusk, h);
      ctx.fillStyle = "rgba(224, 122, 61, 0.08)";
      ctx.fillRect(xDawn, pad.t, xDusk - xDawn, h);
    }
    ctx.strokeStyle = "rgba(140,170,200,0.12)";
    for (let g = 0; g <= 4; g++) {
      const y = pad.t + (h * g) / 4;
      ctx.beginPath();
      ctx.moveTo(pad.l, y);
      ctx.lineTo(pad.l + w, y);
      ctx.stroke();
    }
    if (extra?.zero && lo < 0 && hi > 0) {
      const y0 = pad.t + (1 - (0 - lo) / (hi - lo)) * h;
      ctx.strokeStyle = "rgba(200,180,140,0.35)";
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(pad.l, y0);
      ctx.lineTo(pad.l + w, y0);
      ctx.stroke();
      ctx.setLineDash([]);
    }
    const strokeSeries = (arr, col, width) => {
      ctx.beginPath();
      arr.forEach((v, i) => {
        const x = pad.l + (i / Math.max(1, arr.length - 1)) * w;
        const y = pad.t + (1 - (v - lo) / (hi - lo)) * h;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.strokeStyle = col;
      ctx.lineWidth = width;
      ctx.stroke();
    };
    strokeSeries(series, color, 2);
    if (extra?.second) strokeSeries(extra.second, extra.secondColor || "#e0b14a", 1.5);
    const mark = extra?.marker;
    if (mark != null && Number.isFinite(mark) && series.length > 1) {
      const frac = extra?.lstAxis
        ? Math.max(0, Math.min(1, mark / 24))
        : Math.max(0, Math.min(1, mark / Math.max(1, series.length - 1)));
      const x = pad.l + frac * w;
      ctx.strokeStyle = "rgba(230,238,248,0.55)";
      ctx.beginPath();
      ctx.moveTo(x, pad.t);
      ctx.lineTo(x, pad.t + h);
      ctx.stroke();
      const yi = Math.round(frac * (series.length - 1));
      const yv = series[Math.max(0, Math.min(series.length - 1, yi))];
      if (Number.isFinite(yv)) {
        const y = pad.t + (1 - (yv - lo) / (hi - lo)) * h;
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.arc(x, y, 4, 0, Math.PI * 2);
        ctx.fill();
      }
    } else if (hour < series.length) {
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
    if (extra?.lstAxis) {
      ctx.fillText("0 LST", pad.l, cssH - 6);
      ctx.fillText("12", pad.l + w * 0.5 - 6, cssH - 6);
      ctx.fillText("24", pad.l + w - 18, cssH - 6);
    } else {
      ctx.fillText("0 h", pad.l, cssH - 6);
      ctx.fillText("24 h", pad.l + w - 24, cssH - 6);
    }
    if (extra?.caption) {
      ctx.fillStyle = "#6a7f96";
      ctx.fillText(extra.caption, pad.l + 8, pad.t + 12);
    }
  }

  function drawPressure() {
    const cv = $("cvP");
    if (!cv) return;
    const ctx = cv.getContext("2d");
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const cssW = cv.clientWidth || 560;
    const cssH = cv.clientHeight || 200;
    cv.width = Math.floor(cssW * dpr);
    cv.height = Math.floor(cssH * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.fillStyle = "#07090c";
    ctx.fillRect(0, 0, cssW, cssH);
    const mag = state?.magnetosphere;
    if (!mag) return;
    const bars = [
      ["Wind", mag.p_dyn_npa, "#e07a3d"],
      ["Field at shield", mag.p_mag_mp_npa, "#3d9aad"],
    ];
    const max = Math.max(...bars.map((b) => b[1]), 1);
    bars.forEach((b, i) => {
      const y = 40 + i * 70;
      ctx.fillStyle = "#8fa3b8";
      ctx.font = "12px IBM Plex Sans, sans-serif";
      ctx.fillText(`${b[0]}  ${fmt(b[1], 2)} nPa`, 16, y);
      ctx.fillStyle = b[2];
      ctx.fillRect(16, y + 10, (cssW - 40) * (b[1] / max), 18);
    });
  }

  function drawSitesCompare() {
    const cv = $("cvSites");
    if (!cv) return;
    const ctx = cv.getContext("2d");
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const cssW = cv.clientWidth || 560;
    const cssH = Math.max(220, (sitesNow?.sites || []).length * 28 + 24);
    cv.width = Math.floor(cssW * dpr);
    cv.height = Math.floor(cssH * dpr);
    cv.style.height = cssH + "px";
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.fillStyle = "#07090c";
    ctx.fillRect(0, 0, cssW, cssH);
    const rows = sitesNow?.sites || [];
    if (!rows.length) return;
    const maxR = Math.max(...rows.map((s) => s.radiation), 0.05);
    rows.forEach((s, i) => {
      const y = 16 + i * 28;
      ctx.fillStyle = s.id === siteId ? "#e6eef8" : "#8fa3b8";
      ctx.font = "11px IBM Plex Sans, sans-serif";
      ctx.fillText(s.name.split(" (")[0], 8, y + 8);
      ctx.fillStyle = "#e07a3d";
      ctx.fillRect(140, y, ((cssW - 160) * s.radiation) / maxR, 10);
    });
  }

  function drawHelio() {
    const cv = $("cvHelio");
    if (!cv) return;
    const wrap = cv.parentElement;
    const cssW = Math.max(280, wrap?.clientWidth || cv.clientWidth || 720);
    const cssH = 280;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    cv.width = Math.floor(cssW * dpr);
    cv.height = Math.floor(cssH * dpr);
    cv.style.width = cssW + "px";
    cv.style.height = cssH + "px";
    const ctx = cv.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.fillStyle = "#07090c";
    ctx.fillRect(0, 0, cssW, cssH);

    const cx = cssW * 0.42;
    const cy = cssH * 0.52;
    const rAu = Number(state?.r_au ?? forecast?.r_au ?? 0.387) || 0.387;
    const scale = Math.min(cssW, cssH) * 0.38;
    const rM = rAu * scale;
    const rE = 1.0 * scale;

    const day = Date.now() / 86400000;
    const mercLon = ((day / 87.969) * 360) % 360;
    const earthLon = ((day / 365.25) * 360) % 360;
    const mercAng = (mercLon * Math.PI) / 180;
    const earthAng = (earthLon * Math.PI) / 180;
    const rel = ((mercLon - earthLon + 540) % 360) - 180;

    ctx.strokeStyle = "rgba(224,122,61,0.35)";
    ctx.lineWidth = 1.2;
    ctx.beginPath();
    ctx.arc(cx, cy, rM, 0, Math.PI * 2);
    ctx.stroke();
    ctx.strokeStyle = "rgba(196,165,116,0.4)";
    ctx.beginPath();
    ctx.arc(cx, cy, rE, 0, Math.PI * 2);
    ctx.stroke();

    const sunG = ctx.createRadialGradient(cx, cy, 2, cx, cy, 18);
    sunG.addColorStop(0, "#fff8dc");
    sunG.addColorStop(0.5, "#ffc44a");
    sunG.addColorStop(1, "rgba(224,122,61,0)");
    ctx.fillStyle = sunG;
    ctx.beginPath();
    ctx.arc(cx, cy, 18, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#f0a060";
    ctx.beginPath();
    ctx.arc(cx, cy, 8, 0, Math.PI * 2);
    ctx.fill();

    const mx = cx + Math.cos(mercAng) * rM;
    const my = cy + Math.sin(mercAng) * rM;
    const ex = cx + Math.cos(earthAng) * rE;
    const ey = cy + Math.sin(earthAng) * rE;

    ctx.strokeStyle = "rgba(224,122,61,0.4)";
    ctx.setLineDash([3, 3]);
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.lineTo(mx, my);
    ctx.stroke();
    ctx.strokeStyle = "rgba(196,165,116,0.4)";
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.lineTo(ex, ey);
    ctx.stroke();
    ctx.setLineDash([]);

    ctx.fillStyle = "#8a7a6b";
    ctx.beginPath();
    ctx.arc(mx, my, 6, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#c4a574";
    ctx.beginPath();
    ctx.arc(ex, ey, 7, 0, Math.PI * 2);
    ctx.fill();

    ctx.fillStyle = "#e6eef8";
    ctx.font = "12px IBM Plex Sans, sans-serif";
    ctx.fillText("Sun", cx - 12, cy - 22);
    ctx.fillText("Mercury", mx + 10, my + 4);
    ctx.fillText("Earth", ex + 10, ey + 4);

    ctx.fillStyle = "#c4a574";
    ctx.font = "12px IBM Plex Sans, sans-serif";
    ctx.fillText(`r = ${fmt(rAu, 4)} AU`, 14, 22);
    ctx.fillText(`Δλ (Merc−Earth) ${fmt(rel, 1)}°`, 14, 42);
    ctx.fillText(`λ_M ${fmt(mercLon, 1)}° · λ_E ${fmt(earthLon, 1)}°`, 14, 62);

    const sub = $("mercHelioSub");
    if (sub) sub.textContent = `Mercury at ${fmt(rAu, 3)} AU · ${fmt(rel, 1)}° from Earth`;
  }

  function ensureMetricCharts() {
    let host = $("mercMetricCharts");
    const mp = $("metricsPanel");
    if (!mp) return null;
    if (!host) {
      host = document.createElement("div");
      host.id = "mercMetricCharts";
      host.className = "merc-metric-charts";
      mp.insertAdjacentElement("afterend", host);
    }
    if (!host.dataset.built) {
      host.dataset.built = "1";
      host.innerHTML = METRIC_CHARTS.map(
        (c) =>
          `<section class="merc-metric-chart" data-chart="${c.key}" hidden>
            <h3>${c.title}</h3>
            <canvas id="${c.canvas}" width="${c.w}" height="${c.h}"></canvas>
          </section>`
      ).join("");
    }
    return host;
  }

  function setActiveChart(key) {
    activeChartKey = activeChartKey === key ? null : key;
    const host = ensureMetricCharts();
    if (!host) return;
    host.querySelectorAll(".merc-metric-chart").forEach((el) => {
      const on = el.dataset.chart === activeChartKey;
      el.hidden = !on;
      el.classList.toggle("open", on);
    });
    document.querySelectorAll("#metricsPanel .metric-box[data-chart]").forEach((el) => {
      el.classList.toggle("metric-active", el.dataset.chart === activeChartKey);
    });
    if (activeChartKey) renderCharts();
  }

  function first24(arr) {
    return (arr || []).slice(0, 24);
  }

  function renderCharts() {
    if (!forecast) return;
    ensureMetricCharts();
    const hi = Math.max(0, Math.min(47, Number(window._timelapseHour ?? hour) || 0));
    lineChart($("cvSolar"), first24(forecast.solar), "#e07a3d", {
      marker: hi,
      second: first24(forecast.flare_index || forecast.flares || []),
      secondColor: "#f0c14a",
      caption: "solar · flare idx",
    });
    lineChart($("cvRad"), first24(forecast.radiation), "#d45d8c", { digits: 3, marker: hi });
    lineChart($("cvRss"), first24(forecast.standoff_rm), "#3d9aad", { digits: 2, marker: hi });
    lineChart($("cvImf"), first24(forecast.imf_b_mag || []), "#e07a3d", {
      second: first24(forecast.imf_bz || []),
      secondColor: "#e25b5b",
      zero: true,
      marker: hi,
    });
    lineChart($("cvPdyn"), first24(forecast.p_dyn_npa || forecast.p_dyn || []), "#c4a574", { marker: hi });
    drawPressure();
    drawSitesCompare();
  }

  function renderAlerts() {
    const alerts = (state && state.alerts) || [];
    const board = $("warningsContainer");
    if (!board) return;
    if (!alerts.length) {
      board.innerHTML =
        '<div class="warning-box go"><div class="warning-header">All clear</div><div class="warning-desc">No alerts at this hour.</div></div>';
      return;
    }
    const levelClass = { high: "nogo", warn: "caution", info: "go", ok: "go" };
    board.innerHTML = alerts
      .slice(0, 6)
      .map((a) => {
        const cls = levelClass[a.level] || "go";
        const status = a.level === "high" ? "Critical" : a.level === "warn" ? "Elevated" : a.level === "ok" ? "Nominal" : "Advisory";
        return `<div class="warning-box ${cls}"><div class="warning-header">${a.title}</div><div class="warning-desc">${a.body}</div><div class="warning-accuracy">${status}</div></div>`;
      })
      .join("");
  }

  function renderMeta() {
    if (!state) return;
    const mapTitle = $("mapTitle");
    if (mapTitle) mapTitle.textContent = "";
    ["cycleInfo", "currentConditions", "generalAccuracy"].forEach((id) => {
      const el = $(id);
      if (el) el.textContent = "";
    });
    const alert = $("dynamicAlert");
    if (alert) {
      const top = ((state.alerts || []).filter((a) => a.level === "high" || a.level === "warn"))[0];
      alert.textContent = top ? `${top.title}: ${top.body}` : "";
    }
    document.title = `LIPAS Mercury · ${state.site?.name || "Dashboard"}`;
  }

  function kpiSubtitle() {
    if (!state) return "Sun — · flare — · field —";
    const m = state.magnetosphere || {};
    const phys = state.physics || {};
    const ml = String(state.source || "").includes("lstm");
    return `Sun ${fmt(phys.f107, 0)} · flare ${phys.flare_class || fmt(phys.flare_index, 1)} · field ${fmt(m.imf_b_mag_nt ?? state.wind_mercury?.imf_b_mag, 1)} nT · ${ml ? "physics + ML" : "physics nowcast"}`;
  }

  function pruneMetrics() {
    const mp = $("metricsPanel");
    if (!mp || !state) return;
    ensureMetricCharts();

    let sub = $("mercMetricsKpi");
    if (!sub) {
      const title = document.querySelector(".metrics-title");
      sub = document.createElement("div");
      sub.id = "mercMetricsKpi";
      sub.className = "merc-metrics-kpi slider-sub";
      if (title) {
        const oldSub = title.nextElementSibling;
        title.insertAdjacentElement("afterend", sub);
        if (oldSub && oldSub.classList?.contains("slider-sub") && !oldSub.id) {
          oldSub.style.display = "none";
        }
      } else {
        mp.insertAdjacentElement("beforebegin", sub);
      }
    }
    sub.textContent = kpiSubtitle();

    const p = state.prediction || {};
    const m = state.magnetosphere || {};
    const phys = state.physics || {};
    const rows = [
      ["Radiation", fmt(p.radiation, 3), "mSv/h", "radiation"],
      ["Solar", fmt(p.solar, 1), "index", "solar"],
      ["Shield size", fmt(m.standoff_rm, 2), "RM", "standoff_rm"],
      ["Bow shock", fmt(m.bow_shock_rm, 2), "RM", "standoff_rm"],
      ["Wind pressure", fmt(phys.p_dyn_npa, 1), "nPa", "p_dyn"],
      ["Field strength", fmt(m.imf_b_mag_nt ?? state.wind_mercury?.imf_b_mag, 1), "nT", "imf"],
      ["North–south field", fmt(state.wind_mercury?.imf_bz, 1), "nT", "imf"],
      ["Kp", fmt(phys.kp_index, 1), "", "imf"],
      ["Sun (F10.7)", fmt(phys.f107, 0), "sfu", "solar"],
      ["Dst", fmt(phys.dst, 0), "nT", "imf"],
      ["Flare", phys.flare_class || fmt(phys.flare_index, 1), "", "solar"],
      ["Sunlight", fmt(phys.solar_constant_w_m2, 0), "W/m²", "solar"],
      ["Cusp latitude", fmt(m.cusp_latitude_deg, 1), "°", "standoff_rm"],
      ["Wind vs field", "bars", "nPa", "pressure"],
      ["Site radiation", "compare", "", "sites"],
      ["Distance", fmt(state.r_au, 4), "AU", null],
    ];
    mp.innerHTML = rows
      .map(([label, value, unit, chart]) => {
        const click = chart ? ` data-chart="${chart}" tabindex="0" role="button"` : "";
        const cls = chart ? "metric-box go merc-metric-click" : "metric-box go";
        const active = chart && chart === activeChartKey ? " metric-active" : "";
        return `<div class="${cls}${active}"${click}><div class="metric-label">${label}</div><div class="metric-value">${value}</div><div class="metric-accuracy">${unit}</div></div>`;
      })
      .join("");

    if (!mp.dataset.chartBound) {
      mp.dataset.chartBound = "1";
      mp.addEventListener("click", (e) => {
        const box = e.target.closest("[data-chart]");
        if (!box) return;
        setActiveChart(box.dataset.chart);
      });
      mp.addEventListener("keydown", (e) => {
        if (e.key !== "Enter" && e.key !== " ") return;
        const box = e.target.closest("[data-chart]");
        if (!box) return;
        e.preventDefault();
        setActiveChart(box.dataset.chart);
      });
    }
  }

  function startParticles() {
    window.drawMercuryParticles(performance.now(), window._forecastCache || forecast);
  }

  window.drawMercuryParticles = function drawMercuryParticles(nowMs, data) {
    const canvas = $("particleMapCanvas");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const dpr = window.devicePixelRatio || 1;
    const cssW = canvas.clientWidth || 640;
    const cssH = canvas.clientHeight || 220;
    if (canvas.width !== Math.floor(cssW * dpr) || canvas.height !== Math.floor(cssH * dpr)) {
      canvas.width = Math.floor(cssW * dpr);
      canvas.height = Math.floor(cssH * dpr);
    }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const W = cssW;
    const H = cssH;
    const src = data || window._forecastCache || forecast || {};
    const hi = Math.max(0, Math.min(47, Number(window._timelapseHour ?? hour) || 0));
    const at = (arr, fallback) => {
      const v = Number((arr && arr[hi] != null ? arr[hi] : arr && arr[0]) ?? fallback);
      return Number.isFinite(v) ? v : fallback;
    };
    const sep = at(src.sep, 1);
    const protons = at(src.protons, 2);
    const rad = at(src.radiation, 0.03);
    const density = at(src.density, 40);
    const speed = at(src.speed, 400);
    const storm = at(src.storm, 0);
    const pDyn = at(src.p_dyn_npa || src.p_dyn, state?.physics?.p_dyn_npa ?? 8);
    const rss = at(src.standoff_rm, state?.magnetosphere?.standoff_rm ?? 1.45);
    const flareIdx = at(src.flare_index || src.flares, state?.physics?.flare_index ?? 0);
    const intensity = Math.min(1, sep / 10 + protons / 10 + rad * 4 + storm * 0.35 + flareIdx * 0.08);
    const t = (nowMs || performance.now()) / 1000;
    ctx.clearRect(0, 0, W, H);
    const bg = ctx.createLinearGradient(0, 0, W, 0);
    bg.addColorStop(0, "#1a1208");
    bg.addColorStop(0.12, "#070a10");
    bg.addColorStop(1, "#121820");
    ctx.fillStyle = bg;
    ctx.fillRect(0, 0, W, H);

    const sunX = 36;
    const sunY = H / 2;
    const sunR = 14 + intensity * 6 + Math.max(0, flareIdx) * 1.2;
    const sunG = ctx.createRadialGradient(sunX, sunY, 2, sunX, sunY, sunR * 2.4);
    sunG.addColorStop(0, "#fff8dc");
    sunG.addColorStop(0.35, flareIdx > 3 ? "#ff8840" : "#ffc44a");
    sunG.addColorStop(1, "rgba(255,120,40,0)");
    ctx.fillStyle = sunG;
    ctx.beginPath();
    ctx.arc(sunX, sunY, sunR * 2.4, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#ffc44a";
    ctx.beginPath();
    ctx.arc(sunX, sunY, sunR, 0, Math.PI * 2);
    ctx.fill();

    if (flareIdx > 1.5) {
      const pulse = 0.5 + 0.5 * Math.sin(t * (2 + flareIdx * 0.4));
      ctx.strokeStyle = `rgba(255,160,80,${0.25 + pulse * 0.35})`;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(sunX, sunY, sunR + 8 + pulse * 10, 0, Math.PI * 2);
      ctx.stroke();
      for (let k = 0; k < Math.min(6, Math.round(flareIdx)); k++) {
        const ang = t * 0.7 + k * 1.1;
        ctx.strokeStyle = `rgba(255,140,60,${0.2 + pulse * 0.3})`;
        ctx.beginPath();
        ctx.moveTo(sunX + Math.cos(ang) * sunR, sunY + Math.sin(ang) * sunR);
        ctx.lineTo(sunX + Math.cos(ang) * (sunR + 18 + pulse * 12), sunY + Math.sin(ang) * (sunR + 18 + pulse * 12));
        ctx.stroke();
      }
    }

    ctx.fillStyle = "#f2c56d";
    ctx.font = "10px IBM Plex Sans, sans-serif";
    ctx.fillText("SUN", sunX - 12, sunY + sunR + 14);

    const mercX = W - 52;
    const mercY = H / 2;
    const mercR = 16;

    const compress = Math.max(0.55, Math.min(1.35, rss / 1.5));
    const mpRx = mercR * (2.4 * compress) * (1 - Math.min(0.35, pDyn / 40));
    const mpRy = mercR * (1.9 * compress) * (1 - Math.min(0.25, pDyn / 50));
    ctx.strokeStyle = "rgba(224,122,61,0.75)";
    ctx.lineWidth = 1.8;
    ctx.beginPath();
    ctx.ellipse(mercX - mpRx * 0.15, mercY, mpRx, mpRy, 0, 0, Math.PI * 2);
    ctx.stroke();

    for (let i = -2; i <= 2; i++) {
      if (i === 0) continue;
      ctx.strokeStyle = `rgba(126,200,214,${0.35 + intensity * 0.25})`;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.ellipse(mercX - 2, mercY, mpRx * (0.45 + Math.abs(i) * 0.22), mpRy * (0.7 + Math.abs(i) * 0.18), 0, i > 0 ? -0.2 : Math.PI + 0.2, i > 0 ? Math.PI + 0.2 : -0.2);
      ctx.stroke();
    }

    ctx.fillStyle = "#8a7a6b";
    ctx.beginPath();
    ctx.arc(mercX, mercY, mercR, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "rgba(200,200,210,0.35)";
    ctx.beginPath();
    ctx.arc(mercX - 4, mercY - 3, mercR * 0.55, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#8fa3b8";
    ctx.font = "10px IBM Plex Sans, sans-serif";
    ctx.fillText("Mercury", mercX - 22, mercY + mercR + 14);

    const n = 28 + Math.round(intensity * 90) + Math.round(density / 8);
    let s = Math.abs(Math.round(sep * 9137 + protons * 401 + hi * 17 + flareIdx * 91)) >>> 0 || 1;
    const rand = () => {
      s = (Math.imul(s, 1664525) + 1013904223) >>> 0;
      return s / 4294967296;
    };
    for (let i = 0; i < n; i++) {
      const lane = rand();
      const y = 12 + lane * (H - 24);
      const drift = ((t * (60 + speed * 0.08 + intensity * 120) + i * 17) % (mercX - sunX - 30)) + sunX + sunR;
      const x = drift;

      const dx = x - (mercX - mpRx * 0.15);
      const dy = y - mercY;
      const inMp = (dx * dx) / (mpRx * mpRx) + (dy * dy) / (mpRy * mpRy) < 1;
      if (inMp && rand() > 0.25) continue;
      const a = 0.15 + rand() * 0.55 * (0.4 + intensity);
      const r = 0.8 + rand() * (1.4 + intensity * 2);
      const hot = storm >= 2 || intensity > 0.65 || flareIdx > 4;
      ctx.fillStyle = hot ? `rgba(255,140,70,${a})` : `rgba(224,122,61,${a})`;
      ctx.beginPath();
      ctx.arc(x, y, r, 0, Math.PI * 2);
      ctx.fill();
      if (hot && rand() > 0.7) {
        ctx.strokeStyle = `rgba(255,180,120,${a * 0.6})`;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(x, y);
        ctx.lineTo(x + 6 + rand() * 10, y + (rand() - 0.5) * 4);
        ctx.stroke();
      }
    }
    ctx.fillStyle = "rgba(7,9,12,0.72)";
    ctx.fillRect(8, H - 30, W - 16, 22);
    ctx.fillStyle = "#c8d6e4";
    ctx.font = "11px IBM Plex Sans, sans-serif";
    ctx.fillText(
      `SEP ${fmt(sep, 1)} · protons ${fmt(protons, 1)} · shield ${fmt(rss, 2)} · wind ${fmt(pDyn, 1)} · flare ${fmt(flareIdx, 1)} · T+${hi}h`,
      14,
      H - 12
    );
  };

  function renderAll() {
    const locHint = (window.LOCS || [])[window._topoLocIdx | 0] || SITES.find((s) => s.id === siteId) || { id: siteId };
    document.body.classList.toggle("merc-overview", isOverviewLoc(locHint));
    document.body.classList.remove("body-overview");
    renderMeta();
    syncMagSlider();
    drawCombinedCut();
    drawHelio();
    renderCharts();
    renderAlerts();
    startParticles();
    pruneMetrics();
    if (typeof window._refreshMercurySolarPanel === "function") {
      window._refreshMercurySolarPanel();
    }
  }

  function hideMoonSections() {
    const hide = ["evaNowStrip", "terminator-section", "nearfar-section", "forecastHorizonRow", "illumination-section"];
    hide.forEach((id) => {
      const el = $(id);
      if (el) el.style.display = "none";
    });
    document.querySelectorAll(".advice-head, .advice-box, .moon-map-container, .fact-section").forEach((el) => {
      el.style.display = "none";
    });
    document.querySelectorAll(".timelapse-container:not(.merc-mag-tl)").forEach((el) => {
      el.style.display = "none";
    });
    ["cycleInfo", "currentConditions", "generalAccuracy"].forEach((id) => {
      const el = $(id);
      if (el) {
        el.textContent = "";
        el.style.display = "none";
      }
    });

    document.querySelectorAll(".loading-screen").forEach((el) => {
      el.classList.add("hidden");
      el.style.display = "none";
      el.style.opacity = "0";
      el.style.visibility = "hidden";
      el.style.pointerEvents = "none";
    });
    const dynAlert = $("dynamicAlert");
    if (dynAlert) dynAlert.style.display = "";
    const ft = document.querySelector(".forecast-title");
    if (ft) ft.textContent = "Next 24 hours";
    const fh = document.querySelector(".forecast-header");
    if (fh) fh.textContent = "Wind, radiation, and shield size.";
    const illT = $("illuminationTitle");
    if (illT) illT.textContent = "";
    const wt = document.querySelector(".warnings-title");
    if (wt) wt.textContent = "Alerts";
    const gt = document.querySelector(".graph-title");
    if (gt) gt.textContent = "Charts";
    const gs = document.querySelector(".graph-sub");
    if (gs) gs.textContent = "Pick solar, radiation, shield size, and wind.";
    const load = document.querySelector(".loading-text");
    if (load) load.textContent = "Loading Mercury…";
    const search = $("loc-search");
    if (search) search.placeholder = "Search sites…";
    const st = document.querySelector(".slider-title");
    if (st) st.textContent = "Next 24 hours";
    const ss = document.querySelector(".slider-section .slider-sub");
    if (ss) ss.textContent = "Pick a channel, then an hour.";
    const solarT = document.querySelector(".solar-title");
    if (solarT) solarT.textContent = "Sun";
    const solarSub = $("solarSectionSub");
    if (solarSub) solarSub.textContent = "Storm level and solar disk.";
    const partT = document.querySelector("#particle-section .ops-title");
    if (partT) partT.textContent = "Particles";
    const partSub = $("particleSectionSub");
    if (partSub) partSub.textContent = "Fast particles and storm drivers.";
    const mt = document.querySelector(".metrics-title");
    if (mt) mt.textContent = "Now";
    const pdfT = document.querySelector(".pdf-title");
    if (pdfT) pdfT.textContent = "Download PDF";
    const pdfBtn = document.querySelector(".pdf-box button");
    if (pdfBtn) pdfBtn.textContent = "Download PDF";
    const discT = document.querySelector(".disclaimer-title");
    if (discT) discT.textContent = "Note";
    const disc = document.querySelector(".disclaimer-text");
    if (disc) disc.textContent = "Fast nowcast from solar-wind data. Not a full plasma simulation.";
    document.querySelectorAll(".solar-card-meta").forEach((el) => {
      const t = el.textContent || "";
      if (t === "Hybrid") el.textContent = "Nowcast";
      if (t === "Geomagnetic") el.textContent = "Storm index";
      if (t === "Posture") el.textContent = "Level";
    });
  }

  function pruneGraphFactors() {
    const keep = new Set([
      "radiation",
      "solar",
      "illumination",
      "sep",
      "protons",
      "flares",
      "cme",
      "kp",
      "storm",
      "standoff_rm",
      "p_dyn",
      "imf_bz",
      "f107",
      "dst",
    ]);
    document.querySelectorAll("#factorsContent input[type=checkbox]").forEach((el) => {
      if (!keep.has(el.value)) {
        el.checked = false;
        el.closest("label")?.style && (el.closest("label").style.display = "none");
      } else if (["radiation", "solar", "standoff_rm", "imf_bz", "flares"].includes(el.value)) {
        el.checked = true;
      }
    });
    const box = $("factorsContent");
    if (box) {
      [
        ["standoff_rm", "Shield size"],
        ["p_dyn", "Wind pressure"],
        ["imf_bz", "North–south field"],
        ["f107", "Sun (F10.7)"],
        ["dst", "Dst"],
      ].forEach(([v, lab]) => {
        if (box.querySelector(`input[value="${v}"]`)) return;
        const label = document.createElement("label");
        label.className = "dropdown-item";
        label.innerHTML = `<input type="checkbox" class="dropdown-checkbox" value="${v}" checked>${lab}`;
        box.appendChild(label);
        label.querySelector("input")?.addEventListener("change", () => {
          if (typeof window.syncDropdownLabels === "function") window.syncDropdownLabels();
          if (typeof window.renderGraph === "function") window.renderGraph();
        });
      });
    }
  }

  window.onMercuryDashboardReady = async function (idx, loc) {
    injectMagShell();
    hideMoonSections();
    pruneGraphFactors();
    const site = matchSite(loc?.lat ?? 0, loc?.lon ?? 0, loc);
    siteId = site.id === "overview" ? "equator" : site.id || SITES[idx]?.id || siteId;
    hour = window._timelapseHour || 0;
    try {
      if (!sitesNow) await loadSites();
      if (!forecast) {
        forecast = window._mercuryForecast;
      }
      if (!state || state.forecast_hour !== hour) {
        await loadState(hour);
      } else {
        state = window._mercuryNow || state;
      }
      renderAll();
    } catch (err) {
      console.warn("[Mercury]", err);
      const meta = $("mercMagMeta");
      if (meta) meta.textContent = "Could not load Mercury. Is the server running?";
    }
  };

  window.renderMercuryAlerts = renderAlerts;

  window.onMercuryHourChange = function (h) {
    hour = Number(h) || 0;
    clearTimeout(hourTimer);
    hourTimer = setTimeout(async () => {
      try {
        await loadState(hour);
        renderAll();
      } catch (err) {
        console.warn("[Mercury] hour", err);
      }
    }, 90);
  };

  const prevApply = window.applyTimelapseFrame;
  window.applyTimelapseFrame = function (h, total) {
    if (typeof prevApply === "function") prevApply(h, total);
    if (typeof window.onMercuryHourChange === "function") window.onMercuryHourChange(h);
  };

  function waitForJsPDF(ms) {
    const limit = Number(ms) || 8000;
    return new Promise((resolve, reject) => {
      if (window.jspdf && window.jspdf.jsPDF) return resolve(window.jspdf.jsPDF);
      const t0 = Date.now();
      const id = setInterval(() => {
        if (window.jspdf && window.jspdf.jsPDF) {
          clearInterval(id);
          resolve(window.jspdf.jsPDF);
        } else if (Date.now() - t0 > limit) {
          clearInterval(id);
          reject(new Error("jsPDF not loaded"));
        }
      }, 80);
    });
  }

  function canvasPng(id) {
    const el = $(id);
    if (!el || el.tagName !== "CANVAS" || el.width < 8 || el.height < 8) return null;
    try {
      const url = el.toDataURL("image/png");
      return url && url.length > 80 ? url : null;
    } catch (_) {
      return null;
    }
  }

  function pdfAddImage(doc, dataUrl, pageW, margin, y) {
    if (!dataUrl) return y;
    const pageH = doc.internal.pageSize.height;
    const maxW = pageW - margin * 2;
    const maxH = 78;
    if (y + maxH > pageH - margin - 8) {
      doc.addPage();
      y = margin;
    }
    try {
      const props = doc.getImageProperties(dataUrl);
      const ratio = props.width / Math.max(1, props.height);
      let w = maxW;
      let h = w / ratio;
      if (h > maxH) {
        h = maxH;
        w = h * ratio;
      }
      doc.addImage(dataUrl, "PNG", margin, y, w, h);
      return y + h + 6;
    } catch (_) {
      return y;
    }
  }

  async function mercuryDownloadPDF() {
    const loc = window.currentLocation || (window.locations && window.locations[0]) || { name: "Mercury", lat: 0, lon: 0 };
    const now = window._mercuryNow || state || {};
    const fc = window._mercuryForecast || forecast || {};
    let jsPDF;
    try {
      jsPDF = await waitForJsPDF(8000);
    } catch (_) {
      alert("PDF library is still loading. Wait a second and try again.");
      return;
    }
    try {
      const doc = new jsPDF("p", "mm", "a4");
      const PW = doc.internal.pageSize.width;
      const PH = doc.internal.pageSize.height;
      const M = 14;
      let y = 20;
      const check = (need) => {
        if (y > PH - M - (need || 12)) {
          doc.addPage();
          y = M;
        }
      };
      doc.setFillColor(20, 14, 10);
      doc.rect(0, 0, PW, 42, "F");
      doc.setTextColor(224, 122, 61);
      doc.setFont("helvetica", "bold");
      doc.setFontSize(20);
      doc.text("LIPAS Mercury", M, 18);
      doc.setFontSize(11);
      doc.setTextColor(243, 235, 227);
      doc.text("Site nowcast", M, 28);
      doc.setFont("helvetica", "normal");
      doc.setFontSize(8);
      doc.setTextColor(196, 165, 116);
      doc.text("Fast nowcast from solar-wind data. Not a full plasma simulation.", M, 36);
      y = 52;
      doc.setTextColor(40, 30, 22);
      doc.setFontSize(10);
      const pred = now.prediction || now.nowcast || {};
      const mag = now.magnetosphere || {};
      const phys = now.physics || {};
      const src = String(now.source || fc.source || "physics");
      const mlOn = src.includes("lstm");
      const num = (v, d) => (v == null || !Number.isFinite(Number(v)) ? "—" : Number(v).toFixed(d));
      [
        `Site: ${loc.name || now.site?.name || "—"}`,
        `Coordinates: ${Number(loc.lat || 0).toFixed(2)}°, ${Number(loc.lon || 0).toFixed(2)}°`,
        `Generated: ${new Date().toLocaleString()}`,
        `Radiation: ${num(pred.radiation, 3)} mSv/h`,
        `Solar: ${num(pred.solar, 1)}`,
        `Shield size: ${num(mag.standoff_rm ?? pred.standoff_rm, 2)} RM`,
        `Wind pressure: ${num(phys.p_dyn_npa, 1)} nPa`,
        `North–south field: ${num(now.wind_mercury?.imf_bz, 1)} nT`,
        `Field strength: ${num(mag.imf_b_mag_nt ?? now.wind_mercury?.imf_b_mag, 1)} nT`,
        `Method: ${mlOn ? "physics + ML blend" : "physics nowcast"}`,
      ].forEach((line) => {
        check(8);
        doc.text(String(line), M, y);
        y += 6.5;
      });
      const alerts = now.alerts || [];
      if (alerts.length) {
        y += 3;
        check(16);
        doc.setFont("helvetica", "bold");
        doc.setTextColor(224, 122, 61);
        doc.text("Alerts", M, y);
        y += 7;
        doc.setFont("helvetica", "normal");
        doc.setTextColor(40, 30, 22);
        alerts.slice(0, 6).forEach((a) => {
          check(12);
          doc.text(`${a.title || ""}: ${a.body || ""}`, M, y, { maxWidth: PW - M * 2 });
          y += 8;
        });
      }
      y += 2;
      check(20);
      doc.setFont("helvetica", "bold");
      doc.setTextColor(224, 122, 61);
      doc.text("Field and orbit", M, y);
      y += 6;
      y = pdfAddImage(doc, canvasPng("cvMag"), PW, M, y);
      y = pdfAddImage(doc, canvasPng("cvHelio"), PW, M, y);
      const graph = canvasPng("graphCanvas");
      if (graph) {
        check(12);
        doc.setFont("helvetica", "bold");
        doc.setTextColor(224, 122, 61);
        doc.text("Charts", M, y);
        y += 6;
        y = pdfAddImage(doc, graph, PW, M, y);
      }
      y += 2;
      check(18);
      doc.setFont("helvetica", "bold");
      doc.setTextColor(224, 122, 61);
      doc.text("Next 24 hours", M, y);
      y += 7;
      doc.setFont("helvetica", "normal");
      doc.setFontSize(8);
      doc.setTextColor(40, 30, 22);
      doc.setFont("helvetica", "bold");
      doc.text("T+", M, y);
      doc.text("Rad", M + 16, y);
      doc.text("Solar", M + 42, y);
      doc.text("Shield", M + 72, y);
      doc.text("Wind", M + 102, y);
      doc.text("Field", M + 132, y);
      y += 5;
      doc.setFont("helvetica", "normal");
      const n = Math.max(
        (fc.solar || []).length,
        (fc.radiation || []).length,
        (fc.standoff_rm || []).length,
        0
      );
      for (let i = 0; i < n; i += 2) {
        check(6);
        const rad = fc.radiation?.[i];
        const sol = fc.solar?.[i];
        const rss = fc.standoff_rm?.[i];
        const pd = fc.p_dyn_npa?.[i] ?? fc.p_dyn?.[i];
        const b = fc.imf_b_mag?.[i];
        doc.text(`+${i}h`, M, y);
        doc.text(num(rad, 3), M + 16, y);
        doc.text(num(sol, 1), M + 42, y);
        doc.text(num(rss, 2), M + 72, y);
        doc.text(num(pd, 1), M + 102, y);
        doc.text(num(b, 1), M + 132, y);
        y += 5;
      }
      const nPages = doc.internal.getNumberOfPages();
      for (let i = 1; i <= nPages; i++) {
        doc.setPage(i);
        doc.setFontSize(7);
        doc.setTextColor(120, 130, 145);
        doc.text("© 2026 Luka Takki · LIPAS", PW / 2, PH - 8, { align: "center" });
      }
      const slug = String(loc.name || now.site?.name || "site").replace(/\W+/g, "_");
      doc.save(`LIPAS_Mercury_${slug}_${Date.now()}.pdf`);
    } catch (err) {
      console.warn("[Mercury] PDF", err);
      alert("Could not build the PDF. Try again after the dashboard finishes loading.");
    }
  }
  window.mercuryDownloadPDF = mercuryDownloadPDF;

  function boot() {
    document.body.dataset.app = "mercury";
    document.body.classList.add("mercury-mode");
    syncLocs();
    injectMagShell();
    hideMoonSections();
    pruneGraphFactors();
    loadSites();

    const tryReplace = () => {
      if (typeof window.initLocationsMercury === "function") {
        try {
          window.initLocationsMercury();
        } catch (_) {}
      }
    };
    setTimeout(tryReplace, 400);
    setTimeout(tryReplace, 1200);

    window.mercuryDownloadPDF = mercuryDownloadPDF;
    window.downloadPDF = mercuryDownloadPDF;
    window.addEventListener("load", () => {
      window.downloadPDF = mercuryDownloadPDF;
      window.mercuryDownloadPDF = mercuryDownloadPDF;
    });

    window.addEventListener("resize", () => {
      if (state) {
        drawCombinedCut();
        drawHelio();
        if (activeChartKey) renderCharts();
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
