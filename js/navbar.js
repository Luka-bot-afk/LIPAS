(function () {
  "use strict";

  const PAGES = [
    { id: "dashboard", href: "doctype.html", label: "Dashboard" },
    { id: "mission", href: "mission_planning.html", label: "Mission Planner" },
    { id: "globe", href: "cesium_map.html", label: "Globe" },
    { id: "sources", href: "sources.html", label: "Sources" },
  ];

  const MASCOT_SVG = `
<svg class="moon-mascot" viewBox="0 0 64 64" aria-hidden="true" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <radialGradient id="moonGrad" cx="32%" cy="28%" r="70%">
      <stop offset="0%" stop-color="#f2f5fa"/>
      <stop offset="35%" stop-color="#c8d4e4"/>
      <stop offset="70%" stop-color="#8fa3b8"/>
      <stop offset="100%" stop-color="#3d5270"/>
    </radialGradient>
  </defs>
  <circle class="body" cx="32" cy="32" r="28"/>
  <circle class="crater" cx="22" cy="24" r="4.5"/>
  <circle class="crater" cx="40" cy="38" r="6"/>
  <circle class="crater" cx="44" cy="22" r="3"/>
  <circle class="eye" cx="24" cy="30" r="2.2"/>
  <circle class="eye" cx="38" cy="30" r="2.2"/>
  <circle class="blush" cx="18" cy="36" r="2.4"/>
  <circle class="blush" cx="44" cy="36" r="2.4"/>
  <path class="mouth" d="M26 40c2.2 3.2 9.8 3.2 12 0"/>
</svg>`;

  const chatHistory = [];

  function detectActive() {
    const file = (location.pathname.split("/").pop() || "landing.html").toLowerCase();
    if (file.includes("doctype") || file.includes("dashboard")) return "dashboard";
    if (file.includes("mission")) return "mission";
    if (file.includes("cesium")) return "globe";
    if (file.includes("sources")) return "sources";
    return "";
  }

  function buildNav(active) {
    const links = PAGES.map(
      (p) =>
        `<a href="${p.href}" class="${p.id === active ? "active" : ""}"${
          p.id === active ? ' aria-current="page"' : ""
        }>${p.label}</a>`
    ).join("\n");
    const cta =
      active === "dashboard"
        ? `<a class="nav-cta" href="mission_planning.html">Plan EVA</a>`
        : `<a class="nav-cta" href="doctype.html">Open Dashboard</a>`;
    return `
<nav class="topnav" id="lipasTopnav" aria-label="Primary">
  <a class="brand-mark" href="landing.html">L.I.P.A.S.<span>·</span>OPS</a>
  <button type="button" class="topnav-mobile-toggle" id="lipasNavToggle" aria-label="Menu" aria-expanded="false">☰</button>
  ${links}
  ${cta}
</nav>`;
  }

  function mountNav() {
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
            <h3>Luna · LIPAS</h3>
            <p>Instant lunar ops briefing</p>
          </div>
          <button type="button" class="moon-assist-close" id="moonAssistClose" aria-label="Close">×</button>
        </div>
        <div class="moon-assist-msgs" id="moonAssistMsgs">
          <div class="moon-msg bot">Hello - I'm Luna. Ask about radiation, EVA windows, dust, storms, polar or far-side sites, or say “suggest activities.” I brief from live Dashboard channels when a site is loaded.</div>
        </div>
        <div class="moon-assist-chips" id="moonAssistChips">
          <button type="button" class="moon-chip" data-q="Give me a status briefing for the current site.">Briefing</button>
          <button type="button" class="moon-chip" data-q="Is EVA safe at this site right now?">EVA safe?</button>
          <button type="button" class="moon-chip" data-q="How bad is radiation at the current site?">Radiation</button>
          <button type="button" class="moon-chip" data-q="What about lunar dust risk?">Dust</button>
          <button type="button" class="moon-chip" data-q="Suggest activities for the current site based on hazards.">Activities</button>
          <button type="button" class="moon-chip" data-q="Why explore far-side sites like Mare Ingenii?">Far side</button>
          <button type="button" class="moon-chip" data-q="Explain the LIPAS hybrid ML model briefly.">ML model</button>
        </div>
        <form class="moon-assist-form" id="moonAssistForm">
          <input id="moonAssistInput" type="text" maxlength="500" placeholder="Ask Luna about LIPAS / the Moon…" autocomplete="off" />
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

    function ask(q) {
      const question = (q || "").trim();
      if (!question) return;
      push("user", question);
      chatHistory.push({ role: "user", content: question });
      const answer = lunaAnswer(question);
      push("bot", answer);
      chatHistory.push({ role: "assistant", content: answer });
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

  function boot() {
    mountNav();
    mountAssistant();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
