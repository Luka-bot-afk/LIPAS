(function () {
  "use strict";

  const PRESETS = [
    { name: "Shackleton Crater Rim", lat: -89.68, lon: 166.15 },
    { name: "Malapert Massif", lat: -85.9, lon: 12.9 },
    { name: "Nobile Rim 1", lat: -85.2, lon: 31.0 },
    { name: "Connecting Ridge", lat: -89.5, lon: -138.0 },
    { name: "de Gerlache Rim", lat: -88.5, lon: -68.0 },
    { name: "Sea of Tranquility", lat: 8.5, lon: 31.4 },
    { name: "Mare Imbrium", lat: 32.8, lon: -15.6 },
    { name: "Tycho Crater Floor", lat: -43.31, lon: -11.36 },
    { name: "Von Kármán Crater", lat: -44.8, lon: 176.0 },
    { name: "Compton Crater", lat: 55.3, lon: 103.8 },
    { name: "Mare Orientale", lat: -19.4, lon: -92.8 },
    { name: "Daedalus Crater", lat: -5.9, lon: 179.4 },
  ];

  const HZ_LABEL = {
    green: "GO",
    yellow: "WATCH",
    red: "ALERT",
    go: "GO",
    caution: "WATCH",
    nogo: "ALERT",
  };

  const state = {
    plan: null,
    busy: false,
    chart: null,
    clockTimer: null,
  };

  const $ = (id) => document.getElementById(id);

  function el(tag, cls, html) {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (html != null) n.innerHTML = html;
    return n;
  }

  function fmt(n, d = 2) {
    if (n == null || Number.isNaN(Number(n))) return "-";
    return Number(n).toFixed(d);
  }

  function statusClass(s) {
    const v = String(s || "").toLowerCase();
    if (v === "go" || v === "green" || v === "safe") return "go";
    if (v === "caution" || v === "yellow" || v === "moderate" || v === "watch") return "caution";
    return "nogo";
  }

  function statusLabel(s) {
    const c = statusClass(s);
    if (c === "go") return "GO";
    if (c === "caution") return "CAUTION";
    return "NO-GO";
  }

  function hzClass(level) {
    const v = String(level || "").toLowerCase();
    if (v === "green" || v === "go") return "go";
    if (v === "yellow" || v === "caution") return "caution";
    return "nogo";
  }

  function readForm() {
    let lat = parseFloat($("inp-lat").value);
    let lon = parseFloat($("inp-lon").value);
    if (Number.isNaN(lat) || Number.isNaN(lon)) {
      throw new Error("Enter valid latitude and longitude.");
    }
    lat = Math.max(-90, Math.min(90, lat));
    lon = ((lon + 180) % 360 + 360) % 360 - 180;
    $("inp-lat").value = lat;
    $("inp-lon").value = lon;
    return {
      name: ($("inp-site").value || "").trim() || `Site ${lat.toFixed(2)}°, ${lon.toFixed(2)}°`,
      lat,
      lon,
      eva_duration_h: parseInt($("inp-eva-dur").value, 10) || 4,
      mission_days: parseInt($("inp-mission-days").value, 10) || 14,
      eva_per_day: parseFloat($("inp-eva-day").value) || 4,
      risk_posture: $("inp-risk").value || "nominal",
    };
  }

  function setBusy(on, msg) {
    state.busy = on;
    const btn = $("btn-run");
    const pdf = $("btn-pdf");
    if (btn) {
      btn.disabled = on;
      btn.textContent = on ? (msg || "Computing…") : "Run mission plan";
    }
    if (pdf) pdf.disabled = on || !state.plan;
    const pulse = $("compute-pulse");
    if (pulse) pulse.classList.toggle("active", on);
  }

  function setBanner(msg, kind) {
    const b = $("ops-banner");
    if (!b) return;
    const short = String(msg || "").length > 110 ? String(msg).slice(0, 107) + "…" : msg;
    b.textContent = short;
    b.title = msg || "";
    b.dataset.kind = kind || "info";
  }

  async function apiPlan(body) {
    const res = await fetch("/api/mission/plan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      if (res.status === 405) {
        throw new Error('Plan request failed (405) - use http://127.0.0.1:8765/mission_planning.html (Flask: PORT=8765 python server.py). Static hosts / old server instances reject POST.');
      }
      throw new Error(err.error || `Plan request failed (${res.status})`);
    }
    return res.json();
  }

  async function apiEvaNow(body) {
    const res = await fetch("/api/mission/eva-now", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error("EVA-now check failed");
    return res.json();
  }

  function confLabel(pct) {
    if (pct == null || Number.isNaN(Number(pct))) return "Conf -";
    return `Conf <strong>${Math.round(Number(pct))}%</strong>`;
  }

  function renderGoDial(eva) {
    const dial = $("go-dial");
    const label = $("go-label");
    const sub = $("go-sub");
    const score = $("go-score");
    if (!dial || !eva) return;
    const cls = statusClass(eva.status);
    dial.dataset.status = cls;
    if (label) label.textContent = statusLabel(eva.status);
    const confBit = eva.confidence_pct != null ? ` · conf ${Math.round(eva.confidence_pct)}%` : "";
    if (sub) sub.textContent = (eva.summary || "") + confBit;
    if (score) score.textContent = `${fmt(eva.score, 0)}`;
    const list = $("go-reasons");
    if (list) {
      list.innerHTML = "";
      (eva.reasons || []).slice(0, 3).forEach((r) => {
        const li = el("li", null, r);
        li.title = r;
        list.appendChild(li);
      });
    }
  }

  function renderConditions(c) {
    if (!c) return;
    const conf = c.confidence_pct;
    const map = {
      "m-rad": `${fmt(c.radiation, 4)}`,
      "m-temp": `${fmt(c.temperature, 1)}`,
      "m-dust": `${fmt(c.dust, 2)}`,
      "m-solar": `${fmt(c.solar, 1)}`,
      "m-quake": `${fmt(c.moonquakes, 0)}`,
      "m-meteor": `${fmt(c.micrometeorites, 2)}`,
      "m-illum": `${fmt(c.illumination_pct, 0)}`,
      "m-storm": HZ_LABEL[c.solar_storm] || statusLabel(c.solar_storm) || "-",
    };
    Object.entries(map).forEach(([id, val]) => {
      const n = $(id);
      if (n) n.textContent = val;
      const cEl = $(`${id}-c`);
      if (cEl) cEl.innerHTML = confLabel(conf);
    });
    const stormEl = $("m-storm");
    if (stormEl) {
      stormEl.style.color =
        statusClass(c.solar_storm) === "go"
          ? "var(--go)"
          : statusClass(c.solar_storm) === "caution"
            ? "var(--caution)"
            : "var(--nogo)";
    }
  }

  function renderHazardMatrix(matrix, siteBase, confidencePct) {
    const grid = $("hz-grid");
    if (!grid || !matrix) return;
    const baseConf = confidencePct != null
      ? Number(confidencePct)
      : (siteBase && siteBase.confidence_pct != null ? Number(siteBase.confidence_pct) : null);
    grid.querySelectorAll(".hz-cell").forEach((cell) => {
      const k = cell.dataset.k;
      let level = matrix[k];
      if (k === "site_base" && siteBase) level = siteBase.status;
      const cls = hzClass(level);
      cell.classList.remove("go", "caution", "nogo");
      cell.classList.add(cls);
      const hv = cell.querySelector(".hv");
      if (hv) {
        if (k === "site_base" && siteBase) {
          hv.textContent = `${fmt(siteBase.score, 0)}%`;
        } else {
          hv.textContent = HZ_LABEL[level] || "-";
        }
      }
      const hc = cell.querySelector(".hc");
      if (hc) {
        let pct = baseConf;
        if (k === "site_base" && siteBase && siteBase.confidence_pct != null) {
          pct = siteBase.confidence_pct;
        } else if (cls === "nogo" && pct != null) pct = Math.max(42, pct - 6);
        else if (cls === "caution" && pct != null) pct = Math.max(42, pct - 3);
        hc.innerHTML = confLabel(pct);
      }
    });
    const equip = $("equip-sub");
    if (equip) {
      equip.querySelectorAll(".equip-pill").forEach((pill) => {
        const k = pill.dataset.k;
        const cls = hzClass(matrix[k]);
        pill.classList.remove("go", "caution", "nogo");
        pill.classList.add(cls);
      });
    }
  }

  function renderWindows(windows) {
    const rail = $("window-rail");
    const list = $("window-list");
    if (!rail || !list) return;
    rail.innerHTML = "";
    list.innerHTML = "";
    if (!windows || !windows.length) {
      list.appendChild(el("p", "empty-note", "No windows fit the requested EVA duration in the next 24 h."));
      return;
    }
    windows.forEach((w, i) => {
      const seg = el("button", `rail-seg ${statusClass(w.risk)}`);
      seg.type = "button";
      seg.title = `${w.label} · ${statusLabel(w.risk)} · score ${w.score}${w.confidence_pct != null ? ` · conf ${w.confidence_pct}%` : ""}`;
      seg.innerHTML = `<span class="rail-rank">${i + 1}</span><span class="rail-time">${w.label.split("-")[0]}</span>`;
      seg.addEventListener("click", () => highlightWindow(i));
      rail.appendChild(seg);

      const extras = [];
      if (w.storm_hours) extras.push(`${w.storm_hours}h storm`);
      if (w.equip_hours) extras.push(`${w.equip_hours}h equip`);
      if (w.confidence_pct != null) extras.push(`conf ${Math.round(w.confidence_pct)}%`);
      const row = el("div", `window-row ${statusClass(w.risk)}`);
      row.dataset.idx = String(i);
      row.innerHTML = `
        <div class="wr-rank">${i + 1}</div>
        <div class="wr-main">
          <div class="wr-title">${w.label}</div>
          <div class="wr-meta">Rad ${fmt(w.avg_radiation, 4)} · Dust ${fmt(w.avg_dust, 2)} · Solar ${fmt(w.avg_solar, 0)}${extras.length ? " · " + extras.join(" · ") : ""}</div>
        </div>
        <div class="wr-side">
          <span class="badge ${statusClass(w.risk)}">${statusLabel(w.risk)}</span>
          <span class="wr-score">${fmt(w.score, 0)}</span>
        </div>`;
      list.appendChild(row);
    });
  }

  function renderLandingWindows(windows) {
    const list = $("landing-window-list");
    if (!list) return;
    list.innerHTML = "";
    if (!windows || !windows.length) {
      list.appendChild(el("p", "empty-note", "No quiet landing-ops windows in the next 24 h."));
      return;
    }
    windows.forEach((w, i) => {
      const extras = [];
      if (w.storm_hours) extras.push(`${w.storm_hours}h storm`);
      if (w.confidence_pct != null) extras.push(`conf ${Math.round(w.confidence_pct)}%`);
      const row = el("div", `window-row ${statusClass(w.risk)}`);
      row.innerHTML = `
        <div class="wr-rank">${i + 1}</div>
        <div class="wr-main">
          <div class="wr-title">${w.label}</div>
          <div class="wr-meta">Rad ${fmt(w.avg_radiation, 4)} · Temp ${fmt(w.avg_temp, 0)}° · Solar ${fmt(w.avg_solar, 0)}${extras.length ? " · " + extras.join(" · ") : ""}</div>
        </div>
        <div class="wr-side">
          <span class="badge ${statusClass(w.risk)}">${statusLabel(w.risk)}</span>
          <span class="wr-score">${fmt(w.score, 0)}</span>
        </div>`;
      list.appendChild(row);
    });
  }

  function highlightWindow(idx) {
    document.querySelectorAll(".window-row").forEach((r) => {
      r.classList.toggle("focus", r.dataset.idx === String(idx));
    });
    document.querySelectorAll(".rail-seg").forEach((s, i) => {
      s.classList.toggle("focus", i === idx);
    });
  }

  function renderBasePick(best) {
    if (!best) return;
    const name = $("bp-name");
    const coords = $("bp-coords");
    const score = $("bp-score");
    if (name) name.textContent = best.name;
    if (coords) {
      coords.textContent = `${fmt(best.lat, 2)}°, ${fmt(best.lon, 2)}° · EVA ${fmt(best.safety_pct, 0)}% · Base ${fmt(best.base_pct, 0)}%`;
    }
    if (score) score.innerHTML = `${fmt(best.ops_rank, 0)}<span>%</span>`;
    const b = best.base || {};
    const setBar = (fillId, numId, val) => {
      const f = $(fillId);
      const n = $(numId);
      const v = Number(val) || 0;
      if (f) f.style.width = `${Math.max(0, Math.min(100, v))}%`;
      if (n) n.textContent = fmt(v, 0);
    };
    setBar("bp-power", "bp-power-n", b.power);
    setBar("bp-hab", "bp-hab-n", b.habitability);
    setBar("bp-comms", "bp-comms-n", b.comms);
    const why = $("bp-why");
    if (why) {
      why.innerHTML = "";
      (b.why || []).forEach((w) => why.appendChild(el("span", "bp-chip", w)));
    }
    const bpConf = $("bp-conf");
    if (bpConf) {
      const pct = best.confidence_pct != null ? best.confidence_pct : best.base?.confidence_pct;
      bpConf.innerHTML = pct != null ? `Confidence <strong>${Math.round(pct)}%</strong>` : "Confidence -";
    }
    const use = $("btn-use-base");
    if (use) {
      use.onclick = () => {
        $("inp-lat").value = best.lat;
        $("inp-lon").value = best.lon;
        $("inp-site").value = best.name;
        document.querySelectorAll(".preset-chip").forEach((c) => c.classList.remove("active"));
        runPlan();
      };
    }
  }

  function renderZones(zones) {
    const host = $("zone-list");
    if (!host) return;
    host.innerHTML = "";
    (zones || []).slice(0, 12).forEach((z, i) => {
      const conf = z.confidence_pct != null ? ` · conf ${Math.round(z.confidence_pct)}%` : "";
      const row = el("button", `zone-row ${statusClass(z.status)}${z.is_query ? " query" : ""}`);
      row.type = "button";
      row.innerHTML = `
        <div class="zr-rank">${i + 1}</div>
        <div class="zr-body">
          <div class="zr-name">${z.name}${z.is_query ? " · you" : ""}</div>
          <div class="zr-meta">${fmt(z.lat, 2)}°, ${fmt(z.lon, 2)}° · base ${fmt(z.base_pct, 0)}%${conf} · ${z.notes || ""}</div>
        </div>
        <div class="zr-score">
          <span class="pct">${fmt(z.ops_rank != null ? z.ops_rank : z.safety_pct, 0)}%</span>
          <span class="badge ${statusClass(z.base_status || z.status)}">${statusLabel(z.base_status || z.status)}</span>
        </div>`;
      row.addEventListener("click", () => {
        $("inp-lat").value = z.lat;
        $("inp-lon").value = z.lon;
        $("inp-site").value = z.name;
        document.querySelectorAll(".preset-chip").forEach((c) => c.classList.remove("active"));
        runPlan();
      });
      host.appendChild(row);
    });
  }

  function renderDose(dose) {
    if (!dose) return;
    const set = (id, v) => {
      const n = $(id);
      if (n) n.textContent = v;
    };
    set("dose-total", `${fmt(dose.total_mSv, 1)} mSv`);
    set("dose-risk", dose.risk || "-");
    set("dose-eva", `${fmt(dose.eva_mSv, 1)} mSv`);
    set("dose-hab", `${fmt(dose.habitat_mSv, 1)} mSv`);
    set("dose-male", `${fmt(dose.pct_male, 1)}%`);
    set("dose-female", `${fmt(dose.pct_female, 1)}%`);
    const riskEl = $("dose-risk");
    if (riskEl) riskEl.dataset.risk = String(dose.risk || "").toLowerCase();
  }

  function normalizeSeries1d(arr) {
    const nums = arr.map(Number).filter((v) => Number.isFinite(v));
    if (!nums.length) return arr.map(() => 0.5);
    const min = Math.min(...nums);
    const max = Math.max(...nums);
    if (max === min) return arr.map(() => 0.5);
    return arr.map((v) => {
      const n = Number(v);
      return Number.isFinite(n) ? (n - min) / (max - min) : 0.5;
    });
  }

  function renderHourlyChart(hourly) {
    const canvas = $("hazard-chart");
    if (!canvas || typeof Chart === "undefined" || !hourly || !hourly.length) return;
    const labels = hourly.map((h) => {
      const d = new Date(h.utc);
      return `${String(d.getUTCHours()).padStart(2, "0")}:00`;
    });
    const radN = normalizeSeries1d(hourly.map((h) => h.radiation));
    const solN = normalizeSeries1d(hourly.map((h) => h.solar));
    const dustN = normalizeSeries1d(hourly.map((h) => h.dust));
    if (state.chart) state.chart.destroy();
    state.chart = new Chart(canvas.getContext("2d"), {
      type: "line",
      data: {
        labels,
        datasets: [
          {
            label: "Radiation (norm)",
            data: radN,
            borderColor: "#4db8ff",
            backgroundColor: "rgba(77,184,255,0.10)",
            tension: 0.35,
            fill: true,
            pointRadius: 0,
            borderWidth: 2,
          },
          {
            label: "Solar (norm)",
            data: solN,
            borderColor: "#e0b14a",
            backgroundColor: "transparent",
            tension: 0.35,
            pointRadius: 0,
            borderWidth: 1.5,
          },
          {
            label: "Dust (norm)",
            data: dustN,
            borderColor: "#8fa3b8",
            backgroundColor: "transparent",
            tension: 0.35,
            pointRadius: 0,
            borderWidth: 1.25,
            borderDash: [4, 3],
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: {
            labels: { color: "#9eb0c4", boxWidth: 10, font: { family: "IBM Plex Sans", size: 10 } },
          },
        },
        scales: {
          x: {
            ticks: { color: "#7a8fa3", maxRotation: 0, autoSkipPadding: 10, font: { size: 10 } },
            grid: { color: "rgba(120,140,160,0.08)" },
          },
          y: {
            min: 0,
            max: 1,
            ticks: { color: "#8fa3b8", font: { size: 10 } },
            grid: { color: "rgba(120,140,160,0.1)" },
            title: { display: true, text: "Normalized 0-1", color: "#8fa3b8", font: { size: 10 } },
          },
        },
      },
    });
  }

  function renderMeta(plan) {
    const src = $("model-source");
    const gen = $("plan-generated");
    if (src) {
      src.textContent = plan.model_loaded
        ? "ML weights + physics (0.25 blend)"
        : plan.model_source === "ml+physics"
          ? "ML + physics hybrid"
          : plan.model_source === "physics"
            ? "Physics baseline"
            : String(plan.model_source || "-");
    }
    if (gen) gen.textContent = plan.generated_at || "-";
    const site = $("active-site");
    if (site) site.textContent = `${plan.site.name} · ${fmt(plan.site.lat, 2)}°, ${fmt(plan.site.lon, 2)}°`;
    const pill = $("model-pill");
    const pillText = $("model-pill-text");
    if (pill && pillText) {
      const gated = !!plan.ml_gated;
      pill.classList.toggle("on", !!plan.model_loaded || String(plan.model_source || "").includes("ml"));
      pillText.textContent = plan.model_loaded
        ? gated
          ? "ML loaded · ops-gated"
          : "Keras model loaded"
        : plan.model_source === "physics"
          ? "Physics path (use .venv313)"
          : "Hybrid predict ready";
    }
  }

  function applyPlan(plan) {
    state.plan = plan;
    const conf = plan.eva_now?.confidence_pct ?? plan.conditions?.confidence_pct;
    renderGoDial(plan.eva_now);
    renderConditions(plan.conditions);
    renderHazardMatrix(plan.hazard_matrix || plan.eva_now?.hazards || {}, plan.site_base, conf);
    renderWindows(plan.eva_windows);
    renderLandingWindows(plan.landing_windows);
    renderBasePick(plan.best_base || plan.landing_zones?.[0]);
    renderZones(plan.landing_zones);
    renderDose(plan.dose);
    renderHourlyChart(plan.hourly);
    renderMeta(plan);
    $("btn-pdf").disabled = false;
    $("results-shell").classList.add("ready");
    const top = plan.eva_windows?.[0]?.label || "n/a";
    const land = plan.landing_windows?.[0]?.label || "n/a";
    const base = plan.best_base?.name || "-";
    setBanner(
      `${statusLabel(plan.eva_now.status)} · EVA ${top} · land ${land} · base ${base}`,
      statusClass(plan.eva_now.status)
    );
  }

  async function runPlan() {
    if (state.busy) return;
    let body;
    try {
      body = readForm();
    } catch (e) {
      setBanner(e.message, "nogo");
      return;
    }
    setBusy(true, "Running hybrid predict…");
    setBanner("Scoring site: EVA, storms, equipment, base zones…", "info");
    try {
      const plan = await apiPlan(body);
      applyPlan(plan);
    } catch (e) {
      console.error(e);
      setBanner(e.message || "Mission plan failed", "nogo");
    } finally {
      setBusy(false);
    }
  }

  async function quickEvaCheck() {
    try {
      const body = readForm();
      const res = await apiEvaNow({
        lat: body.lat,
        lon: body.lon,
        risk_posture: body.risk_posture,
      });
      renderGoDial(res.eva_now);
      if (res.conditions) {
        renderConditions({
          ...res.conditions,
          illumination_pct: state.plan?.conditions?.illumination_pct,
          solar_storm: res.eva_now?.hazards?.solar_storm,
        });
      }
      if (res.eva_now?.hazards) {
        renderHazardMatrix(
          res.eva_now.hazards,
          state.plan?.site_base,
          res.eva_now?.confidence_pct ?? res.conditions?.confidence_pct
        );
      }
      setBanner(`Live check · ${statusLabel(res.eva_now.status)}`, statusClass(res.eva_now.status));
    } catch (e) {
      setBanner("Live check unavailable - run a full plan.", "caution");
    }
  }

  async function downloadPdf() {
    if (!state.plan) {
      setBanner("Run a plan before exporting PDF.", "caution");
      return;
    }
    setBusy(true, "Building PDF…");
    try {
      const res = await fetch("/api/mission/pdf", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(state.plan),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || "PDF generation failed");
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      const disp = res.headers.get("Content-Disposition") || "";
      const match = /filename="?([^"]+)"?/.exec(disp);
      a.href = url;
      a.download = match ? match[1] : "LIPAS_MissionPlan.pdf";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      setBanner("PDF downloaded.", "go");
    } catch (e) {
      setBanner(e.message || "PDF download failed", "nogo");
    } finally {
      setBusy(false);
    }
  }

  function renderPresets() {
    const host = $("preset-row");
    if (!host) return;
    host.innerHTML = "";
    PRESETS.forEach((p, i) => {
      const chip = el("button", "preset-chip" + (i === 0 ? " active" : ""), p.name);
      chip.type = "button";
      chip.addEventListener("click", () => {
        host.querySelectorAll(".preset-chip").forEach((c) => c.classList.remove("active"));
        chip.classList.add("active");
        $("inp-lat").value = p.lat;
        $("inp-lon").value = p.lon;
        $("inp-site").value = p.name;
        runPlan();
      });
      host.appendChild(chip);
    });
  }

  function tickClock() {
    const n = $("utc-clock");
    if (!n) return;
    n.textContent = new Date().toISOString().replace("T", " ").replace(/\.\d+Z$/, " UTC");
  }

  function bind() {
    $("btn-run")?.addEventListener("click", runPlan);
    $("btn-pdf")?.addEventListener("click", downloadPdf);
    $("btn-eva-check")?.addEventListener("click", quickEvaCheck);
    ["inp-lat", "inp-lon", "inp-eva-dur", "inp-mission-days", "inp-eva-day", "inp-risk", "inp-site"].forEach((id) => {
      $(id)?.addEventListener("keydown", (e) => {
        if (e.key === "Enter") runPlan();
      });
    });
    $("inp-risk")?.addEventListener("change", () => {
      if (state.plan) runPlan();
    });
  }

  function boot() {
    renderPresets();
    bind();
    tickClock();
    state.clockTimer = setInterval(tickClock, 1000);
    const params = new URLSearchParams(window.location.search || "");
    const qLat = parseFloat(params.get("lat"));
    const qLon = parseFloat(params.get("lon"));
    const qName = (params.get("name") || "").trim();
    if (Number.isFinite(qLat) && Number.isFinite(qLon)) {
      $("inp-lat").value = Math.max(-90, Math.min(90, qLat));
      $("inp-lon").value = ((qLon + 180) % 360 + 360) % 360 - 180;
      $("inp-site").value = qName || `Site ${qLat.toFixed(2)}°, ${qLon.toFixed(2)}°`;
    } else {
      $("inp-lat").value = PRESETS[0].lat;
      $("inp-lon").value = PRESETS[0].lon;
      $("inp-site").value = PRESETS[0].name;
    }
    const loader = $("loadingScreen");
    if (loader) setTimeout(() => loader.classList.add("hidden"), 500);
    runPlan();
    setInterval(() => {
      if (!state.busy && document.visibilityState === "visible") quickEvaCheck();
    }, 120000);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
