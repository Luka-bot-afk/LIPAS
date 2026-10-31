(function (global) {
  "use strict";
  const api = (p) => (typeof global.lipasApiUrl === "function" ? global.lipasApiUrl(p) : p);
  const GREEN = "#3ecf8e";
  let viewer = null;
  let hour = 0;
  let sites = [];
  let sats = [];
  let blobs = [];
  let siteEntities = [];
  let satEntities = [];
  let orbitEntities = [];
  let hazardLayer = null;
  let followId = null;
  let rotate = false;
  let pulseStarted = false;
  function hideLoading() {
    document.getElementById("loadingScreen")?.classList.add("hidden");
  }
  function wrapLon(lon) {
    let x = Number(lon);
    if (!Number.isFinite(x)) return 0;
    while (x > 180) x -= 360;
    while (x < -180) x += 360;
    return x;
  }
  function splitTrack(track) {
    const segs = [];
    let cur = [];
    let prevLon = null;
    (track || []).forEach((p) => {
      const lon = wrapLon(p[0]);
      const lat = Number(p[1]);
      const alt = Math.max(120, Number(p[2]) || 400) * 1000;
      if (!Number.isFinite(lat)) return;
      if (prevLon != null && Math.abs(lon - prevLon) > 180) {
        if (cur.length > 1) segs.push(cur);
        cur = [];
      }
      cur.push(Cesium.Cartesian3.fromDegrees(lon, lat, alt));
      prevLon = lon;
    });
    if (cur.length > 1) segs.push(cur);
    return segs;
  }
  async function ionToken() {
    try {
      const r = await fetch(api("/client-token"));
      const j = await r.json();
      if (j && j.token) Cesium.Ion.defaultAccessToken = j.token;
    } catch (_) {}
  }
  function imageryLayer() {
    return new Cesium.UrlTemplateImageryProvider({
      url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
      maximumLevel: 18,
      credit: "Esri World Imagery",
    });
  }
  function setSceneMode(mode) {
    if (mode === "2d") viewer.scene.mode = Cesium.SceneMode.SCENE2D;
    else if (mode === "columbus") viewer.scene.mode = Cesium.SceneMode.COLUMBUS_VIEW;
    else viewer.scene.mode = Cesium.SceneMode.SCENE3D;
  }
  function applyLighting(on) {
    viewer.scene.globe.enableLighting = !!on;
    if (viewer.scene.sun) viewer.scene.sun.show = !!on;
  }
  function applyAtmosphere(on) {
    if (viewer.scene.skyAtmosphere) viewer.scene.skyAtmosphere.show = !!on;
    viewer.scene.globe.showGroundAtmosphere = !!on;
  }
  function clear(list) {
    list.forEach((e) => { try { viewer.entities.remove(e); } catch (_) {} });
    list.length = 0;
  }
  function addSites() {
    clear(siteEntities);
    const show = document.getElementById("showLocations")?.checked !== false;
    if (!show) return;
    sites.filter((s) => s.group !== "satellite" && s.group !== "overview").forEach((s) => {
      const lat = Number(s.lat);
      const lon = wrapLon(s.lon);
      if (!Number.isFinite(lat)) return;
      const ent = viewer.entities.add({
        name: s.name,
        position: Cesium.Cartesian3.fromDegrees(lon, lat),
        point: {
          pixelSize: 9,
          color: Cesium.Color.fromCssColorString(GREEN),
          outlineColor: Cesium.Color.WHITE,
          outlineWidth: 1,
          heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
        },
        label: {
          text: s.name,
          font: "11px IBM Plex Sans, sans-serif",
          fillColor: Cesium.Color.WHITE,
          showBackground: true,
          backgroundColor: Cesium.Color.BLACK.withAlpha(0.45),
          pixelOffset: new Cesium.Cartesian2(0, -16),
          scale: 0.82,
          heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
        },
        properties: { siteId: s.id, note: s.note || "", lat, lon },
      });
      siteEntities.push(ent);
    });
  }
  function satPosition(s) {
    const track = s.track || [];
    if (track.length < 2) {
      return Cesium.Cartesian3.fromDegrees(wrapLon(s.lon), Number(s.lat), Math.max(120, Number(s.alt_km) || 400) * 1000);
    }
    const prop = new Cesium.SampledPositionProperty();
    prop.setInterpolationOptions({
      interpolationDegree: 2,
      interpolationAlgorithm: Cesium.LagrangePolynomialApproximation,
    });
    const start = viewer.clock.startTime;
    const spanMin = Number(s.period_min) > 600
      ? Math.min(Number(s.period_min), 1436)
      : Math.max(50, Math.min(Number(s.period_min) || 92, 140));
    const dt = (spanMin * 60) / Math.max(1, track.length - 1);
    track.forEach((p, i) => {
      const t = Cesium.JulianDate.addSeconds(start, i * dt, new Cesium.JulianDate());
      prop.addSample(t, Cesium.Cartesian3.fromDegrees(wrapLon(p[0]), Number(p[1]), Math.max(120, Number(p[2]) || 400) * 1000));
    });
    return prop;
  }
  function regimeColor(alt) {
    const a = Number(alt) || 400;
    if (a > 20000) return "#c9a6ff";
    if (a > 1800) return "#e0b14a";
    return GREEN;
  }
  function addSats() {
    clear(satEntities);
    clear(orbitEntities);
    const showOrbits = document.getElementById("showOrbits")?.checked !== false;
    const start = Cesium.JulianDate.now();
    viewer.clock.startTime = start.clone();
    viewer.clock.stopTime = Cesium.JulianDate.addHours(start, 3, new Cesium.JulianDate());
    viewer.clock.currentTime = start.clone();
    viewer.clock.clockRange = Cesium.ClockRange.LOOP_STOP;
    viewer.clock.multiplier = 60;
    viewer.clock.shouldAnimate = true;
    sats.forEach((s) => {
      const lat = Number(s.lat);
      if (!Number.isFinite(lat)) return;
      const color = regimeColor(s.alt_km);
      const ent = viewer.entities.add({
        id: "sat-" + s.id,
        name: s.name,
        position: satPosition(s),
        point: {
          pixelSize: s.name === "ISS" ? 11 : 7,
          color: Cesium.Color.fromCssColorString(color),
          outlineColor: Cesium.Color.WHITE.withAlpha(0.85),
          outlineWidth: 1,
          scaleByDistance: new Cesium.NearFarScalar(2e5, 1.5, 4e7, 0.7),
        },
        label: {
          text: s.name,
          font: "11px IBM Plex Sans, sans-serif",
          fillColor: Cesium.Color.fromCssColorString("#f4f7fb"),
          outlineColor: Cesium.Color.BLACK,
          outlineWidth: 3,
          style: Cesium.LabelStyle.FILL_AND_OUTLINE,
          showBackground: false,
          pixelOffset: new Cesium.Cartesian2(0, -14),
          scaleByDistance: new Cesium.NearFarScalar(4e5, 1, 1.6e7, 0),
          distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 2.2e7),
        },
        properties: { satId: String(s.id) },
      });
      satEntities.push(ent);
      if (showOrbits && Array.isArray(s.track) && s.track.length > 2) {
        splitTrack(s.track).forEach((seg) => {
          if (seg.length < 2) return;
          const orbit = viewer.entities.add({
            polyline: {
              positions: seg,
              width: s.name === "ISS" ? 7 : 4.5,
              arcType: Cesium.ArcType.NONE,
              material: new Cesium.PolylineGlowMaterialProperty({
                glowPower: 0.2,
                color: Cesium.Color.fromCssColorString(color),
              }),
            },
          });
          orbitEntities.push(orbit);
        });
      }
    });
    applyFollow();
  }
  function applyFollow() {
    const on = document.getElementById("followSat")?.checked;
    if (!on || !followId) {
      viewer.trackedEntity = undefined;
      return;
    }
    const ent = viewer.entities.getById("sat-" + followId);
    viewer.trackedEntity = ent || undefined;
  }
  function flyOverview() {
    const follow = document.getElementById("followSat");
    if (follow) follow.checked = false;
    viewer.trackedEntity = undefined;
    viewer.camera.flyTo({
      destination: Cesium.Cartesian3.fromDegrees(-20, 18, 2.4e7),
      duration: 1.6,
    });
  }
  function hazardOn(type) {
    const el = document.getElementById("haz-" + type);
    return !el || el.checked;
  }
  function paintHazards() {
    if (hazardLayer) {
      try { viewer.imageryLayers.remove(hazardLayer); } catch (_) {}
      hazardLayer = null;
    }
    if (document.getElementById("showHazards")?.checked === false) return;
    const canvas = document.createElement("canvas");
    canvas.width = 1024;
    canvas.height = 512;
    const ctx = canvas.getContext("2d");
    const pal = {
      aurora: [62, 207, 142],
      hf: [224, 177, 74],
      pca: [126, 156, 255],
      gnss: [224, 122, 208],
    };
    blobs.forEach((b) => {
      if (!hazardOn(b.type)) return;
      const x0 = ((wrapLon(b.lon) + 180) / 360) * 1024;
      const y = ((90 - Number(b.lat)) / 180) * 512;
      const c = pal[b.type] || pal.aurora;
      const intensity = Math.max(0.15, Math.min(1, Number(b.intensity || 0.4)));
      const stretch = b.type === "aurora" ? 2.4 : b.type === "hf" ? 1.35 : 1.05;
      const rx = (b.type === "aurora" ? 70 : 36) + intensity * 90;
      const ry = rx / stretch;
      [-1024, 0, 1024].forEach((dx) => {
        const x = x0 + dx;
        for (let k = 5; k >= 1; k--) {
          const t = k / 5;
          ctx.beginPath();
          ctx.ellipse(x, y, rx * t, ry * t, 0, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(${c[0]},${c[1]},${c[2]},${(0.045 + intensity * 0.09) * (1.15 - t)})`;
          ctx.fill();
          if (k === 2 || k === 4) {
            ctx.strokeStyle = `rgba(${c[0]},${c[1]},${c[2]},${0.28 + intensity * 0.35})`;
            ctx.lineWidth = 1.25;
            ctx.stroke();
          }
        }
      });
    });
    const provider = new Cesium.SingleTileImageryProvider({
      url: canvas.toDataURL("image/png"),
      rectangle: Cesium.Rectangle.fromDegrees(-180, -90, 180, 90),
    });
    hazardLayer = viewer.imageryLayers.addImageryProvider(provider);
    if (!pulseStarted) {
      pulseStarted = true;
      const t0 = performance.now();
      const tick = () => {
        if (hazardLayer) {
          const t = (performance.now() - t0) / 1000;
          hazardLayer.alpha = 0.78 + 0.2 * Math.sin(t * 0.7);
        }
        requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    }
  }
  function renderSatList() {
    const box = document.getElementById("satList");
    if (!box) return;
    const q = (document.getElementById("satFilter")?.value || "").trim().toLowerCase();
    const list = sats.filter((s) => !q || (s.name + " " + s.group).toLowerCase().includes(q));
    box.innerHTML = (list.length ? list : []).map((s) => `
      <div class="sat-item${String(s.id) === String(followId) ? " active" : ""}" data-id="${s.id}">
        <div>
          <div class="n">${s.name}</div>
          <div style="font-size:11px;color:#8fb8a8">${Number(s.alt_km).toFixed(0)} km · i ${Number(s.inclination).toFixed(1)}° · ${s.group || ""}</div>
        </div>
        <button type="button" data-follow="${s.id}">Follow</button>
      </div>`).join("") || `<div class="sat-item"><div class="n">No match in ${sats.length}</div></div>`;
    box.querySelectorAll("button[data-follow]").forEach((b) => {
      b.addEventListener("click", () => {
        followId = String(b.dataset.follow);
        document.getElementById("followSat").checked = true;
        renderSatList();
        applyFollow();
      });
    });
  }
  function renderSearch(q) {
    const box = document.getElementById("locSearchResults");
    if (!box) return;
    const s = (q || "").trim().toLowerCase();
    if (!s) {
      box.classList.remove("show");
      box.innerHTML = "";
      return;
    }
    const hits = sites.filter((x) => x.group !== "overview" && (x.name + " " + x.group + " " + x.id).toLowerCase().includes(s)).slice(0, 8);
    if (!hits.length) {
      box.innerHTML = '<div class="loc-result"><small>No sites matched</small></div>';
      box.classList.add("show");
      return;
    }
    box.innerHTML = hits.map((x) =>
      `<div class="loc-result" role="button" tabindex="0" data-id="${x.id}">${x.name}<small>${Number(x.lat).toFixed(2)}°, ${wrapLon(x.lon).toFixed(2)}° · ${x.group || ""}</small></div>`
    ).join("");
    box.classList.add("show");
    box.querySelectorAll(".loc-result[data-id]").forEach((b) => {
      b.addEventListener("click", () => flyToSite(b.dataset.id));
    });
  }
  function flyToSite(id) {
    const s = sites.find((x) => x.id === id);
    if (!s || !viewer) return;
    const follow = document.getElementById("followSat");
    if (follow) follow.checked = false;
    viewer.trackedEntity = undefined;
    document.getElementById("locSearchResults")?.classList.remove("show");
    const alt = s.group === "satellite" ? Math.max(8e5, Number(s.alt_km || 400) * 4000) : 2.2e6;
    viewer.camera.flyTo({
      destination: Cesium.Cartesian3.fromDegrees(wrapLon(s.lon), Number(s.lat), alt),
      duration: 1.4,
    });
    showHover(s);
  }
  function showHover(s) {
    const card = document.getElementById("locHoverCard");
    if (!card) return;
    document.getElementById("locHoverName").textContent = s.name;
    document.getElementById("locHoverCoords").textContent = `${Number(s.lat).toFixed(2)}°, ${wrapLon(s.lon).toFixed(2)}°`;
    document.getElementById("locHoverSummary").textContent = s.note || s.group || "";
    document.getElementById("locHoverStatusText").textContent = s.g_scale || "LIVE";
    const haz = document.getElementById("locHoverHazards");
    if (haz) haz.textContent = `Aurora ${Number(s.aurora_pct || 0).toFixed(0)}% · Kp ${Number(s.kp || 0).toFixed(1)}`;
    const dash = document.getElementById("locDashBtn");
    if (dash) dash.href = "earth.html?site=" + encodeURIComponent(s.id);
    card.classList.add("show", "pinned");
    card.style.display = "block";
  }
  async function load(hourVal) {
    hour = Number(hourVal) || 0;
    let siteJson = {};
    let satJson = {};
    let hazJson = {};
    try {
      const [siteRes, satRes, hazRes] = await Promise.all([
        fetch(api("/api/earth/sites")),
        fetch(api("/api/earth/satellites?hour=" + encodeURIComponent(hour))),
        fetch(api("/api/earth/hazards?hour=" + encodeURIComponent(hour))),
      ]);
      if (siteRes.ok) siteJson = await siteRes.json();
      if (satRes.ok) satJson = await satRes.json();
      if (hazRes.ok) hazJson = await hazRes.json();
    } catch (err) {
      console.warn("[LIPAS] earth globe catalog", err);
    }
    sites = siteJson.sites || siteJson.catalog || [
      { id: "ksc", name: "Kennedy Space Center", lat: 28.57, lon: -80.65, group: "launch", note: "US east-coast crewed and cargo departure." },
      { id: "starbase", name: "Starbase", lat: 25.99, lon: -97.16, group: "launch", note: "Boca Chica departure site." },
      { id: "kourou", name: "Guiana Space Centre", lat: 5.24, lon: -52.77, group: "launch", note: "ESA equatorial launch site." },
      { id: "baikonur", name: "Baikonur", lat: 45.96, lon: 63.31, group: "launch", note: "Roscosmos departure site." },
    ];
    function withTrack(s) {
      if (Array.isArray(s.track) && s.track.length > 2) return s;
      const inc = (Number(s.inclination) || 51.6) * Math.PI / 180;
      const alt = Number(s.alt_km) || 400;
      const phase = ((Number(s.lon) || 0) * Math.PI) / 180;
      const track = [];
      for (let i = 0; i <= 72; i++) {
        const ang = phase + (i / 72) * Math.PI * 2;
        const lat = Math.asin(Math.sin(inc) * Math.sin(ang)) * 180 / Math.PI;
        const lon = Math.atan2(Math.sin(ang) * Math.cos(inc), Math.cos(ang)) * 180 / Math.PI;
        track.push([lon, lat, alt]);
      }
      return Object.assign({}, s, { track });
    }
    sats = satJson.satellites || [];
    if (!sats.length) {
      sats = [
        { id: "iss", name: "ISS", lat: 12, lon: -40, alt_km: 420, inclination: 51.6, group: "LEO", note: "Crewed station. Position is a stand-in when the catalog is offline." },
        { id: "css", name: "Tiangong", lat: -8, lon: 70, alt_km: 390, inclination: 41.5, group: "LEO", note: "China Space Station." },
        { id: "hst", name: "Hubble", lat: 20, lon: 140, alt_km: 535, inclination: 28.5, group: "LEO", note: "NASA observatory." },
      ];
    }
    sats = sats.map(withTrack);
    blobs = hazJson.blobs || [];
    if (!followId && sats[0]) followId = String(sats[0].id);
    const qSat = new URLSearchParams(location.search).get("sat");
    if (qSat && sats.some((s) => String(s.id) === String(qSat))) followId = String(qSat);
    addSites();
    addSats();
    paintHazards();
    renderSatList();
    renderSearch(document.getElementById("locSearchInput")?.value);
    const meta = document.getElementById("globeHourMeta");
    if (meta) meta.textContent = `${sats.length} satellites moving · ${satJson.source || "catalog"} · ${blobs.length} hazard blobs`;
  }
  function bindUi() {
    document.getElementById("enableLighting")?.addEventListener("change", (e) => applyLighting(e.target.checked));
    document.getElementById("showAtmosphere")?.addEventListener("change", (e) => applyAtmosphere(e.target.checked));
    document.getElementById("showLocations")?.addEventListener("change", addSites);
    document.getElementById("showOrbits")?.addEventListener("change", addSats);
    document.getElementById("followSat")?.addEventListener("change", applyFollow);
    document.getElementById("autoRotate")?.addEventListener("change", (e) => { rotate = e.target.checked; });
    document.getElementById("viewMode")?.addEventListener("change", (e) => setSceneMode(e.target.value));
    document.getElementById("locSearchInput")?.addEventListener("input", (e) => renderSearch(e.target.value));
    document.getElementById("satFilter")?.addEventListener("input", renderSatList);
    document.getElementById("overviewBtn")?.addEventListener("click", flyOverview);
    document.getElementById("showHazards")?.addEventListener("change", paintHazards);
    ["aurora", "hf", "pca", "gnss"].forEach((t) => {
      document.getElementById("haz-" + t)?.addEventListener("change", paintHazards);
    });
    document.querySelectorAll("#legendPanel [data-hazard]").forEach((btn) => {
      const box = document.getElementById(btn.getAttribute("data-hazard"));
      const paint = () => {
        const on = box ? !!box.checked : true;
        btn.classList.toggle("is-off", !on);
        btn.setAttribute("aria-pressed", on ? "true" : "false");
      };
      paint();
      btn.addEventListener("click", () => {
        if (!box) return;
        box.checked = !box.checked;
        box.dispatchEvent(new Event("change", { bubbles: true }));
        paint();
      });
      box?.addEventListener("change", paint);
    });
    document.getElementById("locCloseBtn")?.addEventListener("click", () => {
      const card = document.getElementById("locHoverCard");
      card?.classList.remove("show", "pinned");
      if (card) card.style.display = "none";
    });
    const openBtn = document.getElementById("globeOptionsOpen");
    const closeBtn = document.getElementById("globeOptionsClose");
    const mq = window.matchMedia("(max-width: 720px)");
    function setOpen(open) {
      document.body.classList.toggle("globe-options-open", open);
      setTimeout(() => viewer?.resize(), 80);
    }
    openBtn?.addEventListener("click", () => setOpen(true));
    closeBtn?.addEventListener("click", () => setOpen(false));
    viewer.screenSpaceEventHandler.setInputAction((click) => {
      const picked = viewer.scene.pick(click.position);
      const id = picked && picked.id;
      const props = id && id.properties;
      if (props && props.satId) {
        followId = String(props.satId.getValue());
        const box = document.getElementById("followSat");
        if (box) box.checked = true;
        renderSatList();
        applyFollow();
        return;
      }
      if (props && props.siteId) {
        const s = sites.find((x) => x.id === props.siteId.getValue());
        if (s) showHover(s);
      }
    }, Cesium.ScreenSpaceEventType.LEFT_CLICK);
    if (global.LipasGlobeTimebar) {
      global.LipasGlobeTimebar.bind({
        onChange: (h) => { load(h).catch(() => {}); },
      });
    } else {
      document.getElementById("globeHourSlider")?.addEventListener("change", (e) => load(e.target.value));
    }
  }
  async function start() {
    await ionToken();
    const base = new Cesium.ImageryLayer(imageryLayer());
    viewer = new Cesium.Viewer("cesiumContainer", {
      animation: true,
      timeline: false,
      geocoder: false,
      homeButton: true,
      sceneModePicker: false,
      baseLayerPicker: false,
      navigationHelpButton: false,
      fullscreenButton: true,
      infoBox: false,
      selectionIndicator: false,
      baseLayer: base,
      shouldAnimate: true,
    });
    viewer.scene.globe.enableLighting = true;
    viewer.scene.globe.showGroundAtmosphere = true;
    if (viewer.scene.skyAtmosphere) viewer.scene.skyAtmosphere.show = true;
    if (viewer.scene.moon) viewer.scene.moon.show = true;
    if (viewer.scene.sun) viewer.scene.sun.show = true;
    viewer.clock.shouldAnimate = true;
    viewer.clock.multiplier = 80;
    viewer.camera.setView({
      destination: Cesium.Cartesian3.fromDegrees(-20, 18, 2.4e7),
    });
    viewer.scene.postRender.addEventListener(() => {
      if (!rotate || viewer.trackedEntity) return;
      viewer.scene.camera.rotate(Cesium.Cartesian3.UNIT_Z, -0.00018);
    });
    bindUi();
    await load(0);
    hideLoading();
  }
  start().catch((err) => {
    console.error(err);
    hideLoading();
  });
})(window);
