(function () {
  "use strict";

  const COPYRIGHT = "© 2026 LIPAS Research";

  try {
    const saved = localStorage.getItem("lipas-theme");
    document.documentElement.dataset.theme = saved === "light" ? "light" : "dark";
  } catch (_) {
    document.documentElement.dataset.theme = "dark";
  }
  if (!document.getElementById("lipas-ops-font")) {
    const font = document.createElement("link");
    font.id = "lipas-ops-font";
    font.rel = "stylesheet";
    font.href = "https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=Outfit:wght@400;500;600;700&display=swap";
    document.head.appendChild(font);
  }
  if (!document.getElementById("lipas-ops-skin")) {
    const skin = document.createElement("link");
    skin.id = "lipas-ops-skin";
    skin.rel = "stylesheet";
    skin.href = "styles/ops-console.css?v=12";
    document.head.appendChild(skin);
  }
  if (!document.getElementById("lipas-dash-skin")) {
    const dash = document.createElement("link");
    dash.id = "lipas-dash-skin";
    dash.rel = "stylesheet";
    dash.href = "styles/dash-skin.css?v=10";
    document.head.appendChild(dash);
  }
  if (!document.getElementById("lipas-page-fix")) {
    const fix = document.createElement("link");
    fix.id = "lipas-page-fix";
    fix.rel = "stylesheet";
    fix.href = "styles/page-fix.css?v=6";
    document.head.appendChild(fix);
  }

  async function lipasAskLuna(question, ctx, history) {
    const snapshot = ctx || {};
    try {
      const res = await fetch("/api/luna-chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: question,
          context: snapshot,
          lat: snapshot.lat,
          lon: snapshot.lon,
          history: history || [],
        }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data && data.answer) return String(data.answer);
      }
    } catch (_) {}
    try {
      const res = await fetch("https://text.pollinations.ai/openai", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model: "openai",
          messages: [
            { role: "system", content: "You are Luna, a space-weather assistant for LIPAS mission ops. Answer in plain English, under 140 words. Use the snapshot. Say when a value is an estimate. Do not print hidden reasoning." },
            { role: "user", content: question + "\n\nSnapshot:\n" + JSON.stringify(snapshot).slice(0, 1600) },
          ],
        }),
      });
      if (res.ok) {
        const data = await res.json();
        const text = data && data.choices && data.choices[0] && data.choices[0].message && data.choices[0].message.content;
        if (text) return String(text);
      }
    } catch (_) {}
    return "";
  }
  window.lipasAskLuna = lipasAskLuna;

  function installChartSkin() {
    const Chart = window.Chart;
    if (!Chart || Chart.__lipasSkin) return;
    Chart.__lipasSkin = true;
    Chart.defaults.font.family = '"IBM Plex Sans", system-ui, sans-serif';
    Chart.defaults.elements.line.tension = 0.35;
    Chart.defaults.elements.line.borderWidth = 2;
    Chart.defaults.elements.point.radius = 0;
    Chart.defaults.elements.point.hoverRadius = 4;
    Chart.defaults.plugins.legend.labels.usePointStyle = true;
    Chart.register({
      id: "lipasIntel",
      beforeDatasetsDraw(chart) {
        const area = chart.chartArea;
        const y = chart.scales && (chart.scales.y || chart.scales.y1);
        if (!area || !y || !Number.isFinite(y.min) || !Number.isFinite(y.max) || y.min === y.max) return;
        const light = document.documentElement.dataset.theme === "light";
        const ctx = chart.ctx;
        const span = y.max - y.min;
        const caution = y.getPixelForValue(y.min + span * 0.62);
        const high = y.getPixelForValue(y.min + span * 0.82);
        ctx.save();
        ctx.fillStyle = light ? "rgba(31, 138, 86, 0.06)" : "rgba(62, 207, 142, 0.05)";
        ctx.fillRect(area.left, caution, area.right - area.left, area.bottom - caution);
        ctx.fillStyle = light ? "rgba(154, 107, 18, 0.08)" : "rgba(224, 177, 74, 0.07)";
        ctx.fillRect(area.left, high, area.right - area.left, caution - high);
        ctx.fillStyle = light ? "rgba(180, 35, 44, 0.08)" : "rgba(226, 91, 91, 0.08)";
        ctx.fillRect(area.left, area.top, area.right - area.left, high - area.top);
        ctx.restore();
      },
    });
  }
  installChartSkin();

  const ICO = {
    dash: '<svg viewBox="0 0 16 16" aria-hidden="true"><rect x="1.5" y="1.5" width="5.5" height="5.5" rx="1.2" fill="none" stroke="currentColor" stroke-width="1.4"/><rect x="9" y="1.5" width="5.5" height="5.5" rx="1.2" fill="none" stroke="currentColor" stroke-width="1.4"/><rect x="1.5" y="9" width="5.5" height="5.5" rx="1.2" fill="none" stroke="currentColor" stroke-width="1.4"/><rect x="9" y="9" width="5.5" height="5.5" rx="1.2" fill="none" stroke="currentColor" stroke-width="1.4"/></svg>',
    mission: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M2 12.5 6.2 8.2 8.4 10.4 14 3.5" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/><path d="M10.2 3.5H14V7.2" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/></svg>',
    globe: '<svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="6" fill="none" stroke="currentColor" stroke-width="1.4"/><ellipse cx="8" cy="8" rx="2.6" ry="6" fill="none" stroke="currentColor" stroke-width="1.2"/><path d="M2.2 8h11.6M3.2 5.2h9.6M3.2 10.8h9.6" fill="none" stroke="currentColor" stroke-width="1.1"/></svg>',
    sun: '<svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="2.4" fill="none" stroke="currentColor" stroke-width="1.4"/><path d="M8 1.6v1.8M8 12.6v1.8M1.6 8h1.8M12.6 8h1.8M3.4 3.4l1.3 1.3M11.3 11.3l1.3 1.3M12.6 3.4l-1.3 1.3M4.7 11.3l-1.3 1.3" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/></svg>',
    book: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 2.5h7.2A2.3 2.3 0 0 1 12.5 4.8V13.5H4.6A1.6 1.6 0 0 0 3 15V2.5Z" fill="none" stroke="currentColor" stroke-width="1.3"/><path d="M3 13.2h9.5" stroke="currentColor" stroke-width="1.3"/></svg>',
  };

  const FAMILIES = {
    moon: {
      label: "Moon",
      note: "Surface hazards & EVA",
      home: "doctype.html",
      links: [
        { id: "dashboard", href: "doctype.html", label: "Dashboard", icon: "dash" },
        { id: "mission", href: "mission_planning.html", label: "Mission", icon: "mission" },
        { id: "globe", href: "cesium_map.html", label: "Globe", icon: "globe" },
        { id: "sources", href: "sources.html?app=moon", label: "Sources", icon: "book" },
      ],
    },
    mercury: {
      label: "Mercury",
      note: "Magnetosphere & solar wind",
      home: "index.html",
      links: [
        { id: "dashboard", href: "index.html", label: "Dashboard", icon: "dash" },
        { id: "globe", href: "mercury_globe.html", label: "Globe", icon: "globe" },
        { id: "sun", href: "sun_globe.html", label: "Sun", icon: "sun" },
        { id: "sources", href: "sources.html?app=mercury", label: "Sources", icon: "book" },
      ],
    },
    earth: {
      label: "Earth",
      note: "Launch, aurora & orbits",
      home: "earth.html",
      links: [
        { id: "dashboard", href: "earth.html", label: "Dashboard", icon: "dash" },
        { id: "mission", href: "earth_mission.html", label: "Mission", icon: "mission" },
        { id: "globe", href: "earth_globe.html", label: "Globe", icon: "globe" },
        { id: "sources", href: "sources.html?app=earth", label: "Sources", icon: "book" },
      ],
    },
  };

  const PAGES = [
    { id: "dashboard", href: "doctype.html", label: "Dashboard" },
    { id: "mission", href: "mission_planning.html", label: "Mission Planner" },
    { id: "globe", href: "cesium_map.html", label: "Globe" },
    { id: "sources", href: "sources.html", label: "Sources" },
  ];

  const MASCOT_SVG = `
<svg class="moon-mascot" viewBox="0 0 64 64" aria-hidden="true" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <clipPath id="lunaDisc"><circle cx="32" cy="32" r="28"/></clipPath>
  </defs>
  <g clip-path="url(#lunaDisc)">
    <circle cx="32" cy="32" r="28" fill="#d7e0ea"/>
    <circle cx="20" cy="16" r="20" fill="#f7f9fc"/>
    <circle cx="22" cy="24" r="4.2" fill="#8ea0b4"/>
    <circle cx="41" cy="40" r="5.4" fill="#7d91a6"/>
    <circle cx="44" cy="21" r="2.4" fill="#96a9bc"/>
    <circle cx="30" cy="48" r="3" fill="#8ea0b4"/>
  </g>
  <circle cx="24" cy="30" r="2.15" fill="#1c2838"/>
  <circle cx="38" cy="30" r="2.15" fill="#1c2838"/>
  <circle cx="24.7" cy="29.3" r="0.7" fill="#fff"/>
  <circle cx="38.7" cy="29.3" r="0.7" fill="#fff"/>
  <circle cx="18" cy="36" r="2.1" fill="#f0b7b0"/>
  <circle cx="44" cy="36" r="2.1" fill="#f0b7b0"/>
  <path d="M26 39.5c2.2 3 9.8 3 12 0" fill="none" stroke="#1c2838" stroke-width="1.6" stroke-linecap="round"/>
</svg>`;

  const chatHistory = [];

  function pageFile() {
    return (location.pathname.split("/").pop() || "").toLowerCase();
  }

  function currentFamily() {
    const file = pageFile();
    const app = new URLSearchParams(location.search).get("app");
    if (app === "moon" || app === "mercury" || app === "earth") {
      try { sessionStorage.setItem("lipas-family", app); } catch (_) {}
      return app;
    }
    if (file.includes("earth") || document.body?.dataset?.app === "earth" || document.body?.classList.contains("earth-mode")) {
      return "earth";
    }
    if (
      document.body?.dataset?.app === "mercury" ||
      document.body?.classList.contains("mercury-mode") ||
      file.includes("mercury") ||
      file.includes("sun_globe") ||
      file === "index.html"
    ) {
      return "mercury";
    }
    let family = "";
    try { family = sessionStorage.getItem("lipas-family") || ""; } catch (_) {}
    if ((file.includes("sources") || file.includes("landing") || file === "") && FAMILIES[family]) return family;
    return "moon";
  }

  function isMercuryUi() {
    return currentFamily() === "mercury";
  }

  function detectActive() {
    const file = pageFile() || "landing.html";
    if (file.includes("sun_globe") || file === "sun.html") return "sun";
    if (file.includes("globe") || file.includes("cesium")) return "globe";
    if (file.includes("mission")) return "mission";
    if (file.includes("doctype") || file.includes("dashboard") || file === "index.html" || file === "earth.html") return "dashboard";
    if (file.includes("sources")) return "sources";
    return "";
  }

  function profileRecord() {
    try {
      const raw = JSON.parse(localStorage.getItem("lipas-profile") || "{}");
      const name = String(raw.name || "").trim();
      return { name: name || "LIPAS Research", role: String(raw.role || "Forecast ops").trim() || "Forecast ops" };
    } catch (_) {
      return { name: "LIPAS Research", role: "Forecast ops" };
    }
  }

  function profileMark(name) {
    if (!name || name === "LIPAS Research") return "LR";
    const parts = name.split(/\s+/).filter(Boolean);
    return ((parts[0] || "L")[0] + (parts[1] ? parts[1][0] : "")).toUpperCase();
  }

  function buildNav(active) {
    const familyId = currentFamily();
    const family = FAMILIES[familyId];
    const links = family.links.map((p) => {
      const on = p.id === active;
      return `<a href="${p.href}" class="${on ? "active" : ""}"${on ? ' aria-current="page"' : ""}>${ICO[p.icon] || ""}${p.label}</a>`;
    }).join("");
    const worlds = Object.keys(FAMILIES).map((id) => {
      const f = FAMILIES[id];
      const on = id === familyId && pageFile() !== "landing.html" && pageFile() !== "";
      return `<a href="${f.home}" data-family="${id}"${on ? ' aria-current="true"' : ""}><span><strong>${f.label}</strong><small>${f.note}</small></span></a>`;
    }).join("");
    const profile = profileRecord();
    const light = document.documentElement.dataset.theme === "light";
    return `
<nav class="topnav" id="lipasTopnav" aria-label="Primary">
  <div class="ops-switch" id="lipasOps">
    <button type="button" class="brand-mark" id="lipasOpsBtn" aria-haspopup="listbox" aria-expanded="false" aria-controls="lipasOpsMenu">
      LIPAS <span>OPS</span>
      <svg viewBox="0 0 12 12" aria-hidden="true"><path d="M2.5 4.5 6 8l3.5-3.5" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/></svg>
    </button>
    <div class="ops-menu" id="lipasOpsMenu" role="listbox" hidden>
      <a href="landing.html"><span><strong>Home</strong><small>Back to the landing</small></span></a>
      ${worlds}
    </div>
  </div>
  ${links}
  <div class="nav-tools">
    <a class="nav-profile" href="profile.html" title="${profile.name.replace(/"/g, "")}">
      <span>${profileMark(profile.name)}</span>
    </a>
    <button type="button" class="theme-toggle" id="lipasTheme" aria-pressed="${light ? "true" : "false"}" aria-label="${light ? "Switch to dark theme" : "Switch to light theme"}">
      <svg class="ico-sun" viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="2.3" fill="none" stroke="currentColor" stroke-width="1.4"/><path d="M8 1.5v1.7M8 12.8v1.7M1.5 8h1.7M12.8 8h1.7M3.3 3.3l1.2 1.2M11.5 11.5l1.2 1.2M12.7 3.3l-1.2 1.2M4.5 11.5l-1.2 1.2" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/></svg>
      <svg class="ico-moon" viewBox="0 0 16 16" aria-hidden="true"><path d="M10.2 2.2A5.6 5.6 0 1 0 13.8 9 4.4 4.4 0 0 1 10.2 2.2Z" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/></svg>
    </button>
    <button type="button" class="topnav-mobile-toggle" id="lipasNavToggle" aria-label="Menu" aria-expanded="false">
      <span class="nav-burger" aria-hidden="true"><span></span><span></span><span></span></span>
    </button>
  </div>
</nav>`;
  }

  function mountNav() {
    const familyId = currentFamily();
    try { sessionStorage.setItem("lipas-family", familyId); } catch (_) {}
    document.body.dataset.family = familyId;
    document.body.classList.toggle("mercury-mode", familyId === "mercury");
    document.body.classList.toggle("earth-mode", familyId === "earth");
    if (familyId === "mercury" && !document.body.dataset.app) document.body.dataset.app = "mercury";
    if (familyId === "earth" && !document.body.dataset.app) document.body.dataset.app = "earth";
    const host = document.getElementById("lipas-topnav");
    const active = (host && host.dataset.active) || detectActive();
    const html = buildNav(active === "home" ? "" : active);
    if (host) {
      host.outerHTML = html.trim();
    } else if (!document.getElementById("lipasTopnav") && !document.querySelector("nav.topnav")) {
      document.body.insertAdjacentHTML("afterbegin", html);
    } else {
      const existing = document.querySelector("nav.topnav");
      if (existing && !existing.id) {
        existing.id = "lipasTopnav";
        existing.querySelectorAll("a").forEach((a) => {
          const href = (a.getAttribute("href") || "").toLowerCase();
          a.classList.toggle(
            "active",
            (active === "dashboard" && href.includes("doctype")) ||
              (active === "mission" && href.includes("mission")) ||
              (active === "globe" && href.includes("cesium")) ||
              (active === "sources" && href.includes("sources"))
          );
        });
      }
    }

    const nav = document.getElementById("lipasTopnav");
    const toggle = document.getElementById("lipasNavToggle");
    if (nav && toggle) {
      toggle.addEventListener("click", () => {
        const open = nav.classList.toggle("open");
        toggle.setAttribute("aria-expanded", open ? "true" : "false");
      });
    }
    const ops = document.getElementById("lipasOps");
    const opsBtn = document.getElementById("lipasOpsBtn");
    const opsMenu = document.getElementById("lipasOpsMenu");
    if (ops && opsBtn && opsMenu) {
      opsBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        const open = ops.classList.toggle("open");
        opsMenu.hidden = !open;
        opsBtn.setAttribute("aria-expanded", open ? "true" : "false");
      });
      document.addEventListener("click", (e) => {
        if (!ops.contains(e.target)) {
          ops.classList.remove("open");
          opsMenu.hidden = true;
          opsBtn.setAttribute("aria-expanded", "false");
        }
      });
      document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
          ops.classList.remove("open");
          opsMenu.hidden = true;
          opsBtn.setAttribute("aria-expanded", "false");
        }
      });
    }
    const themeBtn = document.getElementById("lipasTheme");
    if (themeBtn) {
      themeBtn.addEventListener("click", () => {
        const next = document.documentElement.dataset.theme === "light" ? "dark" : "light";
        document.documentElement.dataset.theme = next;
        try { localStorage.setItem("lipas-theme", next); } catch (_) {}
        themeBtn.setAttribute("aria-pressed", next === "light" ? "true" : "false");
        themeBtn.setAttribute("aria-label", next === "light" ? "Switch to dark theme" : "Switch to light theme");
        window.dispatchEvent(new CustomEvent("lipas-theme-change", { detail: next }));
      });
    }
  }

  function num(v) {
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
  }

  function gatherLipasContext() {
    const loc =
      (typeof window.currentLocation === "object" && window.currentLocation) ||
      (Array.isArray(window.LOCS) && window.LOCS[window._topoLocIdx | 0]) ||
      null;
    const fc = window._forecastCache || null;
    const pred = window._lastPrediction || null;
    const est = pred && (pred.refined_estimate || pred.fast_estimate || pred.prediction);
    const ctx = {
      site: loc?.name || document.getElementById("locationName")?.textContent || "The Moon",
      lat: loc?.lat ?? num(document.getElementById("inp-lat")?.value),
      lon: loc?.lon ?? num(document.getElementById("inp-lon")?.value),
      page: detectActive() || "landing",
      summary: loc?.summary || null,
      illumination: loc?.illumination ?? (fc ? fc.illumination?.[0] : null),
    };
    const pick = (key, estKey) => {
      if (est && est[estKey ?? key] != null) return num(est[estKey ?? key]);
      if (fc && fc[key] != null) return num(Array.isArray(fc[key]) ? fc[key][0] : fc[key]);
      return null;
    };
    ctx.radiation = pick("radiation");
    ctx.dust = pick("dust");
    ctx.temperature = pick("temperature");
    ctx.solar = pick("solar");
    ctx.moonquakes = pick("moonquakes");
    ctx.micrometeorites = pick("micrometeorites");
    ctx.evaRisk = pick("evaRisk");
    ctx.kp = pick("kp");
    ctx.sep = pick("sep");
    ctx.cme = pick("cme");
    ctx.storm = pick("storm");
    ctx.protons = pick("protons");
    ctx.flares = pick("flares");
    ctx.comms = pick("comms");
    ctx.solarOutput = pick("solarOutput");
    if (ctx.illumination == null) ctx.illumination = pick("illumination");
    return ctx;
  }

  function bandRad(usvh) {
    if (usvh == null) return "unknown";
    if (usvh < 0.08) return "go";
    if (usvh < 0.18) return "caution";
    return "nogo";
  }
  function bandIndex(v, lo, hi) {
    if (v == null) return "unknown";
    if (v < lo) return "go";
    if (v < hi) return "caution";
    return "nogo";
  }
  function bandTempK(t) {
    if (t == null) return "unknown";
    if (t >= 160 && t <= 300) return "go";
    if (t >= 120 && t <= 340) return "caution";
    return "nogo";
  }
  function bandLabel(b) {
    return ({ go: "GO", caution: "CAUTION", nogo: "NO-GO", unknown: "-" })[b] || "-";
  }
  function worstBand(bands) {
    if (bands.includes("nogo")) return "nogo";
    if (bands.includes("caution")) return "caution";
    if (bands.includes("go")) return "go";
    return "unknown";
  }

  function fmt(v, digits) {
    if (v == null || !Number.isFinite(Number(v))) return "n/a";
    return Number(v).toFixed(digits ?? (Math.abs(v) >= 10 ? 0 : 2));
  }

  function coord(lat, lon) {
    if (lat == null || lon == null) return "";
    const ns = lat >= 0 ? "N" : "S";
    const ew = lon >= 0 ? "E" : "W";
    return `${Math.abs(lat).toFixed(2)}°${ns}, ${Math.abs(lon).toFixed(2)}°${ew}`;
  }

  function assess(ctx) {
    const rad = bandRad(ctx.radiation);
    const dust = bandIndex(ctx.dust, 2.0, 3.5);
    const solar = bandIndex(ctx.solar, 3.0, 5.0);
    const mets = bandIndex(ctx.micrometeorites, 2.5, 4.0);
    const quakes = bandIndex(ctx.moonquakes, 2.5, 4.0);
    const thermal = bandTempK(ctx.temperature);
    const eva =
      ctx.evaRisk != null
        ? ctx.evaRisk < 35
          ? "go"
          : ctx.evaRisk < 55
            ? "caution"
            : "nogo"
        : worstBand([rad, dust, solar, thermal, mets]);
    return { rad, dust, solar, mets, quakes, thermal, eva };
  }

  const INTENTS = [
    {
      id: "activities",
      keys: ["activit", "suggest", "what should", "recommend", "what can i do", "ops plan", "task"],
    },
    {
      id: "radiation",
      keys: ["radiation", "dose", "gcr", "cosmic", "sievert", "µsv", "usv", "msv", "sep", "proton"],
    },
    {
      id: "temperature",
      keys: ["temp", "thermal", "hot", "cold", "heat", "freeze", "kelvin", "celsius"],
    },
    {
      id: "dust",
      keys: ["dust", "regolith", "abras", "levitat", "sticky"],
    },
    {
      id: "solar",
      keys: ["solar", "flare", "cme", "storm", "swpc", "space weather", "kp", "geomagnetic"],
    },
    {
      id: "eva",
      keys: ["eva", "walk", "suit", "window", "safe", "safety", "go/no", "nogo", "no-go", "egress"],
    },
    {
      id: "micrometeor",
      keys: ["micrometeor", "meteoroid", "impact flux", "meteor"],
    },
    {
      id: "seismic",
      keys: ["moonquake", "seismic", "quake", "tremor"],
    },
    {
      id: "sites",
      keys: [
        "landing",
        "site",
        "shackleton",
        "south pole",
        "polar",
        "far side",
        "farside",
        "von kármán",
        "von karman",
        "ingenii",
        "malapert",
        "artemis",
        "zone",
      ],
    },
    {
      id: "illumination",
      keys: ["day", "night", "cycle", "lunar day", "illumination", "sunlight", "shadow", "psr"],
    },
    {
      id: "water",
      keys: ["water", "ice", "volatile", "hydrogen", "psr"],
    },
    {
      id: "model",
      keys: ["lipas", "model", "ml", "predict", "physics", "hybrid", "lstm", "accuracy", "how does", "how do you"],
    },
    {
      id: "comms",
      keys: ["comms", "communication", "relay", "radio quiet", "latency", "delay"],
    },
    {
      id: "gravity",
      keys: ["gravity", "mass", "weight", "escape"],
    },
    {
      id: "distance",
      keys: ["distance", "how far", "km away", "light time"],
    },
    {
      id: "atmosphere",
      keys: ["atmosphere", "air", "exosphere", "vacuum", "pressure"],
    },
    {
      id: "briefing",
      keys: ["brief", "status", "overview", "summary", "conditions", "now", "current", "snapshot", "report"],
    },
    {
      id: "hello",
      keys: ["hello", "hi ", "hey", "help", "what can you", "who are you"],
    },
  ];

  function detectIntents(q) {
    const t = ` ${String(q || "").toLowerCase().trim()} `;
    const hits = [];
    for (const intent of INTENTS) {
      let score = 0;
      for (const k of intent.keys) {
        if (t.includes(k)) score += Math.min(k.length, 12);
      }
      if (score > 0) hits.push({ id: intent.id, score });
    }
    hits.sort((a, b) => b.score - a.score);
    if (!hits.length) {
      const lastUser = [...chatHistory].reverse().find((m) => m.role === "user");
      if (lastUser && /^(and|also|what about|how about|same|more|why|ok)\b/i.test(q.trim())) {
        return detectIntents(lastUser.content);
      }
      return [{ id: "briefing", score: 1 }];
    }
    return hits.slice(0, 3);
  }

  const SITE_NOTES = [
    {
      match: /shackleton|south\s*pole|malapert|de\s*gerlache|connecting\s*ridge/i,
      note: "South-polar ridges often trade near-constant sunlight against nearby permanently shadowed ice. Great Artemis logistics, but thermal gradients and terrain slopes dominate planning.",
    },
    {
      match: /von\s*k[aá]rm[aá]n|ingenii|compton|far[\s-]?side|farside/i,
      note: "Far-side sites never see Earth directly - outstanding for radio astronomy, but you need a relay for ops voice/data. Treat comms as a hard constraint.",
    },
    {
      match: /tranquility|apollo\s*11|mare\s*serenitatis|mare\s*imbrium/i,
      note: "Nearside mare plains are historically well characterized. Simpler illumination cycles than the poles, but dust and thermal swing still rule EVA pacing.",
    },
    {
      match: /schr[oö]dinger|orientale|south\s*pole.?aitken/i,
      note: "Basin terrain offers unique geology with complex topography - prioritize hazard overlays and rover pathfinding before long traverses.",
    },
  ];

  function siteNote(ctx) {
    const hay = `${ctx.site || ""} ${ctx.summary || ""}`;
    for (const s of SITE_NOTES) {
      if (s.match.test(hay)) return s.note;
    }
    if (ctx.lat != null && Math.abs(ctx.lat) >= 80) {
      return "High-latitude site: expect grazing sunlight, long shadows, and strong dependence on local topography for power and thermal.";
    }
    if (ctx.lon != null && (ctx.lon < -90 || ctx.lon > 90)) {
      return "Likely far-side / limb geometry - verify Earth-line-of-sight and relay coverage before long EVA.";
    }
    return null;
  }

  function liveLine(ctx, bands) {
    const parts = [`${ctx.site}`];
    const c = coord(ctx.lat, ctx.lon);
    if (c) parts.push(`(${c})`);
    const metrics = [];
    if (ctx.radiation != null) metrics.push(`rad ${fmt(ctx.radiation, 3)} µSv/h [${bandLabel(bands.rad)}]`);
    if (ctx.temperature != null) metrics.push(`T ${fmt(ctx.temperature, 0)} K [${bandLabel(bands.thermal)}]`);
    if (ctx.dust != null) metrics.push(`dust ${fmt(ctx.dust, 2)} [${bandLabel(bands.dust)}]`);
    if (ctx.solar != null) metrics.push(`solar ${fmt(ctx.solar, 2)} [${bandLabel(bands.solar)}]`);
    if (ctx.evaRisk != null) metrics.push(`EVA risk ${fmt(ctx.evaRisk, 0)}% [${bandLabel(bands.eva)}]`);
    else metrics.push(`EVA posture ${bandLabel(bands.eva)}`);
    if (ctx.illumination != null) metrics.push(`illum ${fmt(ctx.illumination, 0)}%`);
    const hasLive = ctx.radiation != null || ctx.temperature != null || ctx.dust != null;
    if (!hasLive) {
      return `${parts.join(" ")} - open the Dashboard on a site to load live hybrid channels; I still brief lunar ops from physics + mission knowledge.`;
    }
    return `${parts.join(" ")}: ${metrics.join(" · ")}.`;
  }

  function genActivities(ctx, bands) {
    const site = ctx.site || "this site";
    const lines = [];
    if (bands.eva === "go") {
      lines.push(`• GO - Short EVA / instrument setup at ${site}: radiation and thermal look workable.`);
    } else if (bands.eva === "caution") {
      lines.push(`• CAUTION - Cap EVA duration; prefer sheltered tasks and tighter timelines at ${site}.`);
    } else {
      lines.push(`• NO-GO - Hold suit egress at ${site} until radiation/thermal/storm channels cool.`);
    }

    if (bands.solar === "go") {
      lines.push("• GO - Geology sampling / rover traverse: solar drivers quiet.");
    } else {
      lines.push(`• ${bandLabel(bands.solar)} - Re-check Mission Planner before open-field rover ops (solar/storm elevated).`);
    }

    if (bands.thermal === "go") {
      lines.push(`• GO - Habitat logistics / radiator checks OK (T ≈ ${fmt(ctx.temperature, 0)} K).`);
    } else {
      lines.push(`• CAUTION - Thermal pacing: stage radiator checks; limit suit thermal load between waypoints.`);
    }

    if (bands.dust !== "go") {
      lines.push(`• ${bandLabel(bands.dust)} - Dust mitigation: sealed sample transfers; wipe seals before repress.`);
    } else {
      lines.push("• GO - Dust index nominal; standard seal hygiene still required.");
    }

    if (bands.mets !== "go") {
      lines.push(`• ${bandLabel(bands.mets)} - Prefer canopy/rover cover for long exposed work.`);
    }

    const note = siteNote(ctx);
    if (note) lines.push(`• Note - ${note}`);
    lines.push("• Next - Open Mission Planner → Run plan for ranked 24h GO / CAUTION / NO-GO windows.");
    return lines.join("\n");
  }

  function answerForIntent(id, ctx, bands, q) {
    const live = liveLine(ctx, bands);
    const note = siteNote(ctx);

    switch (id) {
      case "hello":
        return (
          `I'm Luna - L.I.P.A.S. ops companion. I brief radiation, thermal, dust, storms, EVA posture, and sites using live dashboard channels when available.\n\n` +
          `${live}\n\n` +
          `Ask for a status briefing, EVA call, activity suggestions, or a polar / far-side site trade.`
        );

      case "briefing":
        return (
          `Ops briefing - ${live}` +
          (note ? `\n${note}` : "") +
          `\n\nDrivers to watch: radiation [${bandLabel(bands.rad)}], thermal [${bandLabel(bands.thermal)}], dust [${bandLabel(bands.dust)}], solar [${bandLabel(bands.solar)}]. ` +
          `Overall EVA posture: ${bandLabel(bands.eva)}. Use Mission Planner for timed windows.`
        );

      case "activities":
        return `Suggested activities for ${ctx.site}:\n${genActivities(ctx, bands)}\n\n${live}`;

      case "radiation": {
        const tip =
          bands.rad === "nogo"
            ? "Delay surface work; wait for the hybrid channel to drop."
            : bands.rad === "caution"
              ? "Shorten exposure; favor sheltered tasks."
              : "Nominal quiet-time dose - still verify before long EVA.";
        return (
          `${live}\n\n` +
          `Lunar surface dose is galactic cosmic rays plus solar energetic particles - no magnetosphere or thick air to blunt them. ` +
          `Quiet periods sit around tens of µSv/h; SEP events spike fast. ${tip} ` +
          `L.I.P.A.S. folds NOAA/SWPC drivers into the hybrid radiation channel on the Dashboard.`
        );
      }

      case "temperature": {
        const tC = ctx.temperature != null ? ctx.temperature - 273.15 : null;
        return (
          `${live}\n\n` +
          `Lunar thermal swing is extreme: roughly −173 °C night to ~127 °C day; PSR floors can approach −230 °C. ` +
          (tC != null ? `Current site ≈ ${fmt(tC, 0)} °C (${fmt(ctx.temperature, 0)} K) → ${bandLabel(bands.thermal)}. ` : "") +
          `L.I.P.A.S. blends Stefan-Boltzmann dayside physics with Apollo nightside polynomials for site forecasts. Pace EVA around illumination.`
        );
      }

      case "dust":
        return (
          `${live}\n\n` +
          `Regolith is fine, sharp, and electrostatically sticky. Terminator charging can levitate grains and foul seals, radiators, and bearings. ` +
          `Dust risk rises near dawn/dusk and after surface ops kick material up. ` +
          `Current dust band: ${bandLabel(bands.dust)}. Prefer sealed sample transfers when elevated.`
        );

      case "solar":
        return (
          `${live}\n\n` +
          `Flares, CMEs, SEP, and Kp map into lunar radiation and storm posture. ` +
          `If solar/storm bands rise (${bandLabel(bands.solar)}` +
          (ctx.kp != null ? `, Kp ${fmt(ctx.kp, 1)}` : "") +
          (ctx.cme != null ? `, CME ${fmt(ctx.cme, 2)}` : "") +
          `), shorten EVA or hold for a quieter window. Dashboard solar panels + Mission Planner are the go/no-go gate.`
        );

      case "eva":
        return (
          `${live}\n\n` +
          `EVA call for ${ctx.site}: ${bandLabel(bands.eva)}. ` +
          `L.I.P.A.S. scores windows from radiation, solar/storm, dust, thermal, micrometeoroids, and site fit. ` +
          (bands.eva === "go"
            ? "Proceed with nominal suit checks and keep a weather eye on storm channels."
            : bands.eva === "caution"
              ? "Go shorter, stay closer to shelter, and re-run Mission Planner before committing."
              : "Hold egress. Reassess when hybrid channels improve.") +
          `\n\n${genActivities(ctx, bands)}`
        );

      case "micrometeor":
        return (
          `${live}\n\n` +
          `Micrometeoroid flux is continuous and higher than on Earth - probabilistic but real for long EVA and exposed hardware. ` +
          `Current band: ${bandLabel(bands.mets)}. When elevated, harden posture and shorten open-field work.`
        );

      case "seismic":
        return (
          `${live}\n\n` +
          `Deep, shallow, and thermal moonquakes are usually low magnitude vs Earth, but habitats and precision instruments still care. ` +
          `Seismic band now: ${bandLabel(bands.quakes)}. Radiation/thermal usually dominate EVA risk more than quakes.`
        );

      case "sites":
        return (
          `${live}\n\n` +
          (note ? `${note}\n\n` : "") +
          `South-polar ridges (Shackleton / Malapert class) offer power + nearby PSR ice potential. ` +
          `Far-side basins (Von Kármán, Mare Ingenii, Compton) are radio-quiet but need relay. ` +
          `Use Mission Planner ranking and Dashboard overlays to compare risk across candidates.`
        );

      case "illumination":
        return (
          `${live}\n\n` +
          `A synodic lunar day is ~29.5 Earth days. Equator: ~14 d sun / ~14 d night. Poles: topography-driven - some peaks see near-continuous light for much of the year; PSR floors stay dark. ` +
          (ctx.illumination != null ? `Illumination at ${ctx.site}: ~${fmt(ctx.illumination, 0)}%. ` : "") +
          `Illumination drives power, thermal, and dust-charging risk together.`
        );

      case "water":
        return (
          `Permanently shadowed regions near the poles can trap water ice and volatiles - a core Artemis science/ISRU driver. ` +
          `Pair illuminated ridges (power) with nearby PSRs (ice). ${live}` +
          (note ? `\n${note}` : "")
        );

      case "model":
        return (
          `${live}\n\n` +
          `L.I.P.A.S. is a hybrid system: temporal ML on space-weather features + deterministic physics calibration ` +
          `(Stefan-Boltzmann / Apollo thermal curves), map overlays, Cesium globe, and Mission Planner EVA windows with PDF reports. ` +
          `Plausibility flags when ML and physics disagree - trust physics bounds when they diverge.`
        );

      case "comms":
        return (
          `${live}\n\n` +
          `Nearside sites have direct Earth line-of-sight; far-side needs a relay (halo/relay constellation). ` +
          `One-way light time is ~1.3 s - fine for most ops, painful for fine teleoperation. ` +
          (ctx.comms != null ? `Comms metric now: ${fmt(ctx.comms, 0)}%. ` : "") +
          `Treat relay coverage as a mission-critical resource on far-side EVAs.`
        );

      case "gravity":
        return (
          `Lunar gravity ≈ 1/6 g (1.62 m/s²); escape ≈ 2.38 km/s. Easier mobility, worse dust lofting and traction. ` +
          `Suit and rover designs trade that carefully. ${live}`
        );

      case "distance":
        return (
          `Average Earth-Moon distance ≈ 384,400 km; one-way light time ≈ 1.3 s. ` +
          `That latency matters for teleops and contingency voice loops. ${live}`
        );

      case "atmosphere":
        return (
          `The Moon has only a tenuous exosphere - effectively vacuum for ops. No Earth-like weather, but plasma, UV, and dust charging still shape surface conditions. ${live}`
        );

      default:
        return (
          `${live}\n\n` +
          `Ask about radiation, temperature, dust, solar storms, EVA safety, activity suggestions, polar/far-side sites, or the hybrid ML+physics model.`
        );
    }
  }

  function composeAnswer(question, ctx) {
    const bands = assess(ctx);
    const intents = detectIntents(question);
    const primary = intents[0].id;
    let answer = answerForIntent(primary, ctx, bands, question);

    if (intents.length > 1) {
      const secondary = intents[1].id;
      const combo = new Set(["radiation", "dust", "solar", "temperature", "micrometeor", "seismic"]);
      if (combo.has(secondary) && primary !== "briefing" && primary !== "activities" && primary !== "eva") {
        const extra = [];
        if (secondary === "radiation" && ctx.radiation != null)
          extra.push(`Radiation ${fmt(ctx.radiation, 3)} µSv/h (${bandLabel(bands.rad)})`);
        if (secondary === "dust" && ctx.dust != null) extra.push(`Dust ${fmt(ctx.dust, 2)} (${bandLabel(bands.dust)})`);
        if (secondary === "solar" && ctx.solar != null) extra.push(`Solar ${fmt(ctx.solar, 2)} (${bandLabel(bands.solar)})`);
        if (secondary === "temperature" && ctx.temperature != null)
          extra.push(`Temp ${fmt(ctx.temperature, 0)} K (${bandLabel(bands.thermal)})`);
        if (extra.length) answer += `\n\nAlso noted: ${extra.join("; ")}.`;
      }
    }

    const t = (question || "").toLowerCase();
    if (/\bwhy\b/.test(t) && primary === "eva") {
      answer +=
        "\n\nWhy: EVA posture is the worst-case blend of radiation, solar/storm, dust, thermal, and micrometeoroid bands - not a single sensor.";
    }
    if (/\bbest\b|\bsafest\b|\brank\b/.test(t)) {
      answer +=
        "\n\nFor ranked sites, open Mission Planner and run a plan across candidates - Luna's live brief is for the currently selected site.";
    }

    return answer;
  }

  function lunaAnswer(question) {
    const q = String(question || "").trim();
    if (!q) return "Ask anything about lunar hazards, EVA windows, or L.I.P.A.S. ops.";
    const ctx = gatherLipasContext();
    return composeAnswer(q, ctx);
  }

  function mountAssistant() {
    document.querySelectorAll("#floatingOrb, .floating-orb").forEach((el) => el.remove());

    if (document.getElementById("moonAssist")) return;

    const root = document.createElement("div");
    root.className = "moon-assist";
    root.id = "moonAssist";
    root.innerHTML = `
      <div class="moon-assist-panel" id="moonAssistPanel" role="dialog" aria-label="Ask Luna" aria-hidden="true">
        <div class="moon-assist-head">
          <div>
            <h3>Luna</h3>
          </div>
          <button type="button" class="moon-assist-close" id="moonAssistClose" aria-label="Close">×</button>
        </div>
        <div class="moon-assist-msgs" id="moonAssistMsgs">
          <div class="moon-msg bot">Ask me about the Moon.</div>
        </div>
        <div class="moon-assist-chips" id="moonAssistChips">
          <button type="button" class="moon-chip" data-q="Give me a status briefing for the current site.">Briefing</button>
          <button type="button" class="moon-chip" data-q="Is it safe to walk at this site right now?">Safe to walk</button>
          <button type="button" class="moon-chip" data-q="How bad is radiation at the current site?">Radiation</button>
          <button type="button" class="moon-chip" data-q="What about lunar dust risk?">Dust</button>
          <button type="button" class="moon-chip" data-q="Suggest activities for the current site based on hazards.">Activities</button>
          <button type="button" class="moon-chip" data-q="Why explore far-side sites like Mare Ingenii?">Far side</button>
          <button type="button" class="moon-chip" data-q="Explain the LIPAS hybrid ML model briefly.">The model</button>
        </div>
        <form class="moon-assist-form" id="moonAssistForm">
          <input id="moonAssistInput" type="text" maxlength="500" placeholder="Ask about the Moon" autocomplete="off" />
          <button type="submit">Ask</button>
        </form>
      </div>
      <button type="button" class="moon-assist-fab" id="moonAssistFab" aria-label="Open Luna assistant" aria-expanded="false" title="Ask Luna">
        <span class="moon-assist-pulse" aria-hidden="true"></span>
        ${MASCOT_SVG}
      </button>
    `;
    document.body.appendChild(root);

    const panel = document.getElementById("moonAssistPanel");
    const fab = document.getElementById("moonAssistFab");
    const msgs = document.getElementById("moonAssistMsgs");
    const form = document.getElementById("moonAssistForm");
    const input = document.getElementById("moonAssistInput");

    function setOpen(open) {
      panel.classList.toggle("open", open);
      panel.setAttribute("aria-hidden", open ? "false" : "true");
      fab.setAttribute("aria-expanded", open ? "true" : "false");
      if (open) setTimeout(() => input.focus(), 80);
    }

    fab.addEventListener("click", () => setOpen(!panel.classList.contains("open")));
    document.getElementById("moonAssistClose").addEventListener("click", () => setOpen(false));

    function push(role, text) {
      const el = document.createElement("div");
      el.className = `moon-msg ${role}`;
      el.textContent = text;
      msgs.appendChild(el);
      msgs.scrollTop = msgs.scrollHeight;
    }

    async function ask(q) {
      const question = (q || "").trim();
      if (!question) return "";
      push("user", question);
      chatHistory.push({ role: "user", content: question });
      const pending = document.createElement("div");
      pending.className = "moon-msg bot pending";
      pending.innerHTML = "Thinking through the forecast<span class=\"luna-dots\"></span>";
      msgs.appendChild(pending);
      msgs.scrollTop = msgs.scrollHeight;
      let answer = "";
      const ctx = gatherLipasContext();
      answer = await lipasAskLuna(question, ctx, chatHistory.slice(-8));
      if (!answer) answer = lunaAnswer(question);
      pending.textContent = answer;
      pending.classList.remove("pending");
      chatHistory.push({ role: "assistant", content: answer });
      msgs.scrollTop = msgs.scrollHeight;
      return answer;
    }

    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const q = input.value;
      input.value = "";
      ask(q);
    });

    document.getElementById("moonAssistChips").addEventListener("click", (e) => {
      const btn = e.target.closest(".moon-chip");
      if (!btn) return;
      setOpen(true);
      ask(btn.dataset.q);
    });

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && panel.classList.contains("open")) setOpen(false);
    });

    window.askLuna = function (question) {
      setOpen(true);
      return Promise.resolve(ask(question));
    };
    window.openLunaAssist = function () {
      setOpen(true);
    };
    window.lunaAnswer = lunaAnswer;
  }

  function mountCopyright() {
    document.querySelectorAll(".lipas-copyright").forEach((el) => {
      el.textContent = COPYRIGHT;
    });
    if (!document.querySelector(".lipas-copyright")) {
      const credit = [...document.querySelectorAll("footer .footer > div, footer.footer > div, .footer > div")].find(
        (n) => /©/.test(n.textContent || "")
      );
      if (credit) {
        credit.classList.add("lipas-copyright");
        credit.textContent = COPYRIGHT;
      } else {
        const footer = document.createElement("footer");
        footer.className = "lipas-site-footer";
        if (document.getElementById("cesiumContainer") || document.body.classList.contains("sun-globe")) {
          footer.classList.add("lipas-site-footer--overlay");
        }
        footer.innerHTML = `<p class="lipas-copyright">${COPYRIGHT}</p>`;
        document.body.appendChild(footer);
      }
    }
    if (!document.querySelector('meta[name="author"]')) {
      const author = document.createElement("meta");
      author.name = "author";
      author.content = "Luka Takki";
      document.head.appendChild(author);
    }
    if (!document.querySelector('meta[name="copyright"]')) {
      const copy = document.createElement("meta");
      copy.name = "copyright";
      copy.content = COPYRIGHT;
      document.head.appendChild(copy);
    }
  }

  function boot() {
    installChartSkin();
    mountNav();
    mountAssistant();
    mountCopyright();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
