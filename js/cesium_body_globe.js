(function (global) {
  "use strict";

  const MOON_R = 1737400;
  const BODY_HAZARDS = {
    mercury: [
      { type: "Radiation", checkboxId: "showRadiation", base: 0.5, siteKey: "radiation", mode: "planet" },
      { type: "Solar", checkboxId: "showSolar", base: 0.58, siteKey: "solar", mode: "planet" },
      { type: "SEP", checkboxId: "showSep", base: 0.48, siteKey: "sep", mode: "planet" },
      { type: "CME", checkboxId: "showCme", base: 0.42, siteKey: "cme", mode: "planet" },
      { type: "Temperature", checkboxId: "showTemperature", base: 0.52, siteKey: "temperature", mode: "planet" },
      { type: "Storm", checkboxId: "showStorm", base: 0.45, siteKey: "kp", mode: "planet" },
    ],
    sun: [
      { type: "ActiveRegion", checkboxId: "showSunspots", base: 0.7, siteKey: "intensity", mode: "sunspots" },
      { type: "Flare", checkboxId: "showFlares", base: 0.55, siteKey: "sep", mode: "ar-glow" },
      { type: "CME", checkboxId: "showCme", base: 0.42, siteKey: "cme", mode: "ar-glow" },
      { type: "SEP", checkboxId: "showSep", base: 0.48, siteKey: "sep", mode: "ar-glow" },
    ],
  };
  const TYPE_FROM_KEY = {
    radiation: "Radiation",
    micrometeorites: "Micrometeorites",
    dust: "Dust",
    moonquakes: "Moonquake",
    temperature: "Temperature",
    solar: "Solar",
    sep: "SEP",
    cme: "CME",
    storm: "Storm",
    flares: "Flare",
    sunspots: "ActiveRegion",
  };
  const ID_FROM_TYPE = {
    Radiation: "showRadiation",
    Micrometeorites: "showMicrometeorites",
    Dust: "showDust",
    Moonquake: "showMoonquakes",
    Temperature: "showTemperature",
    Solar: "showSolar",
    SEP: "showSep",
    CME: "showCme",
    Storm: "showStorm",
    Flare: "showFlares",
    ActiveRegion: "showSunspots",
  };

  const MERCURY_FALLBACK_SITES = [
    { name: "Equatorial reference", lat: 0, lon: 0, summary: "0°N 0°E control site", id: "equator" },
    { name: "Hokusai", lat: 58, lon: 17, summary: "Bright rayed crater", id: "hokusai" },
    { name: "Rachmaninoff Basin", lat: 27.7, lon: 57.6, summary: "Peak-ring basin with hollows", id: "rachmaninoff" },
    { name: "Raditladi Basin", lat: 27.2, lon: 119, summary: "Peak-ring basin east of Caloris", id: "raditladi" },
    { name: "Caloris Basin", lat: 30.5, lon: 189.8, summary: "Largest impact basin", id: "caloris" },
    { name: "Tolstoj Basin", lat: -16.2, lon: -163.5, summary: "Ancient multi-ring basin", id: "tolstoj" },
    { name: "Beethoven Basin", lat: -20.8, lon: -123.4, summary: "Mid-southern plains basin", id: "beethoven" },
    { name: "Discovery Rupes", lat: -56.3, lon: -38.3, summary: "Large lobate scarp", id: "discovery" },
    { name: "Caloris antipode", lat: -30, lon: -18.5, summary: "Hilly and lineated terrain", id: "antipode" },
    { name: "Debussy", lat: -34, lon: 14, summary: "Bright rayed crater near the antipode", id: "debussy" },
    { name: "Prokofiev (N pole)", lat: 85.8, lon: 62.9, summary: "Radar-bright polar crater", id: "prokofiev" },
    { name: "Chao Meng-Fu (S pole)", lat: -87.3, lon: -132.4, summary: "South-polar ice candidate", id: "chao" },
  ];

  function api(path) {
    return typeof global.lipasApiUrl === "function" ? global.lipasApiUrl(path) : path;
  }

  function hideLoading() {
    document.getElementById("loadingScreen")?.classList.add("hidden");
  }

  function num(v, d) {
    const n = Number(v);
    if (!Number.isFinite(n)) return "—";
    return n.toFixed(d);
  }

  function wrapLon(lon) {
    let x = Number(lon);
    if (!Number.isFinite(x)) return 0;
    while (x > 180) x -= 360;
    while (x < -180) x += 360;
    return x;
  }

  function loadImage(url) {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.crossOrigin = "anonymous";
      img.onload = () => resolve(img);
      img.onerror = () => reject(new Error("image load failed: " + url));
      img.src = url;
    });
  }

  function detectDiskRadius(data, w, h) {
    const cx = (w - 1) / 2;
    const cy = (h - 1) / 2;
    let r = 0;
    const y = Math.floor(cy);
    for (let x = Math.floor(cx); x < w; x++) {
      const i = (y * w + x) * 4;
      if (data[i] + data[i + 1] + data[i + 2] > 48) r = x - cx;
    }
    const fallback = 0.48 * Math.min(w, h);
    if (r < minDim(w, h) * 0.3) return fallback;
    return r;
    function minDim(a, b) {
      return Math.min(a, b);
    }
  }

  function diskToEquirect(img, outW, outH) {
    const src = document.createElement("canvas");
    src.width = img.width;
    src.height = img.height;
    const sctx = src.getContext("2d", { willReadFrequently: true });
    sctx.drawImage(img, 0, 0);
    const srcData = sctx.getImageData(0, 0, src.width, src.height);
    const sw = src.width;
    const sh = src.height;
    const cx = (sw - 1) / 2;
    const cy = (sh - 1) / 2;
    const rDisk = detectDiskRadius(srcData.data, sw, sh);

    let meanR = 0, meanG = 0, meanB = 0, nMean = 0;
    for (let i = 0; i < srcData.data.length; i += 16) {
      const lum = srcData.data[i] + srcData.data[i + 1] + srcData.data[i + 2];
      if (lum < 40) continue;
      meanR += srcData.data[i];
      meanG += srcData.data[i + 1];
      meanB += srcData.data[i + 2];
      nMean++;
    }
    if (nMean) {
      meanR /= nMean;
      meanG /= nMean;
      meanB /= nMean;
    } else {
      meanR = 200;
      meanG = 140;
      meanB = 40;
    }

    const out = document.createElement("canvas");
    out.width = outW;
    out.height = outH;
    const octx = out.getContext("2d");
    const dst = octx.createImageData(outW, outH);
    const d = dst.data;
    const s = srcData.data;

    function sample(u, v) {
      const x = Math.max(0, Math.min(sw - 1, u));
      const y = Math.max(0, Math.min(sh - 1, v));
      const i = (Math.floor(y) * sw + Math.floor(x)) * 4;
      return [s[i], s[i + 1], s[i + 2]];
    }

    for (let y = 0; y < outH; y++) {
      const lat = Math.PI / 2 - (y / Math.max(1, outH - 1)) * Math.PI;
      const cosLat = Math.cos(lat);
      const sinLat = Math.sin(lat);
      for (let x = 0; x < outW; x++) {
        const lon = (x / Math.max(1, outW - 1)) * Math.PI * 2 - Math.PI;
        const X = cosLat * Math.sin(lon);
        const Y = sinLat;
        const Z = cosLat * Math.cos(lon);
        const i = (y * outW + x) * 4;
        if (Z > 0) {
          const u = cx + X * rDisk;
          const v = cy - Y * rDisk;
          const px = sample(u, v);
          d[i] = px[0];
          d[i + 1] = px[1];
          d[i + 2] = px[2];
          d[i + 3] = 255;
        } else {
          const u = cx + X * rDisk;
          const v = cy - Y * rDisk;
          const px = sample(u, v);
          d[i] = px[0];
          d[i + 1] = px[1];
          d[i + 2] = px[2];
          d[i + 3] = 255;
        }
      }
    }
    octx.putImageData(dst, 0, 0);
    return out;
  }

  function normalizeSite(raw, body) {
    if (!raw) return null;
    const lat = Number(raw.lat);
    const lon = wrapLon(raw.lon ?? raw.longitude);
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null;
    if (body === "sun") {
      const region = raw.region != null ? String(raw.region) : "";
      return {
        id: raw.id || ("ar_" + region),
        name: raw.name || (region ? "AR " + region : "Active region"),
        lat,
        lon: wrapLon(-lon),
        summary: raw.summary || raw.location || [raw.spot_class, raw.mag_class].filter(Boolean).join(" / ") || "NOAA active region",
        radiation: raw.intensity,
        solar: raw.intensity,
        sep: Number(raw.m_flare_probability || 0) / 100,
        cme: Number(raw.x_flare_probability || 0) / 100,
        temperature: raw.intensity,
        micrometeorites: raw.area,
        dust: raw.number_spots,
        moonquakes: raw.area,
        intensity: raw.intensity,
        extra: raw,
      };
    }
    return {
      id: raw.id || raw.name,
      name: raw.name || "Site",
      lat,
      lon: wrapLon(raw.lon),
      summary: raw.note || raw.summary || raw.terrain || "Mercury site",
      radiation: raw.radiation,
      solar: raw.solar,
      sep: raw.sep,
      cme: raw.cme,
      temperature: raw.temperature,
      micrometeorites: raw.protons ?? raw.micrometeorites,
      dust: raw.p_dyn_npa ?? raw.dust,
      moonquakes: raw.kp ?? raw.moonquakes,
      extra: raw,
    };
  }

  function peaksForType(sites, cfg) {
    const key = cfg.siteKey;
    const vals = sites.map((s) => Number(s[key])).filter(Number.isFinite);
    let lo = 0;
    let hi = 1;
    if (vals.length) {
      lo = Math.min(...vals);
      hi = Math.max(...vals);
      if (lo === hi) hi = lo + 1;
    }
    return sites
      .map((s) => {
        const v = Number(s[key]);
        const intensity = Number.isFinite(v) ? 0.28 + 0.72 * ((v - lo) / (hi - lo)) : 0.45;
        return { lat: s.lat, lon: s.lon, intensity };
      })
      .sort((a, b) => b.intensity - a.intensity);
  }

  async function fetchSites(cfg) {
    const url = cfg.sitesUrl ? api(cfg.sitesUrl) : "";
    if (!url) return cfg.fallbackSites.slice();
    try {
      const r = await fetch(url);
      if (!r.ok) throw new Error("sites " + r.status);
      const data = await r.json();
      const raw = cfg.sitesListKey ? data[cfg.sitesListKey] : data.sites || data.spots || [];
      const list = (Array.isArray(raw) ? raw : [])
        .map((s) => normalizeSite(s, cfg.body))
        .filter(Boolean);
      return list.length ? list : cfg.fallbackSites.slice();
    } catch (err) {
      console.warn("[LIPAS] site catalog failed", err);
      return cfg.fallbackSites.slice();
    }
  }

  function absApi(path) {
    const p = api(path);
    if (p.startsWith("http://") || p.startsWith("https://")) return p;
    try {
      return new URL(p, window.location.href).href;
    } catch (e) {
      return p;
    }
  }

  function trekProvider(url, ellipsoid, maxLevel, credit) {
    return new Cesium.UrlTemplateImageryProvider({
      url: absApi(url),
      tilingScheme: new Cesium.GeographicTilingScheme({ ellipsoid }),
      minimumLevel: 0,
      maximumLevel: maxLevel,
      tileWidth: 256,
      tileHeight: 256,
      credit: credit || "",
    });
  }

  function attachTrekImagery(globe, ellipsoid, cfg) {
    const color = globe.imageryLayers.addImageryProvider(
      trekProvider(cfg.imageryUrl, ellipsoid, cfg.maxLevel || 6, cfg.imageryCredit || "")
    );
    color.brightness = cfg.imageryBrightness != null ? cfg.imageryBrightness : 1.04;
    color.contrast = cfg.imageryContrast != null ? cfg.imageryContrast : 1.06;
    color.saturation = cfg.imagerySaturation != null ? cfg.imagerySaturation : 1.08;
    let shade = null;
    if (cfg.hillshadeUrl) {
      shade = globe.imageryLayers.addImageryProvider(
        trekProvider(cfg.hillshadeUrl, ellipsoid, cfg.hillshadeMaxLevel || cfg.maxLevel || 6, "")
      );
      shade.alpha = cfg.hillshadeAlpha != null ? cfg.hillshadeAlpha : 0.18;
      shade.saturation = 0.15;
      shade.contrast = 1.12;
      shade.brightness = 1.05;
    }
    return { color, shade, detail: null };
  }

  async function attachSolarImagery(globe, ellipsoid, cfg) {
    const tileUrl = "/api/solar/tiles/{z}/{y}/{x}.jpg";
    try {
      const probe = await fetch(absApi("/api/solar/tiles/0/0/0.jpg"), { cache: "no-store" });
      if (!probe.ok) throw new Error("solar tiles " + probe.status);
      const layer = globe.imageryLayers.addImageryProvider(
        trekProvider(tileUrl, ellipsoid, cfg.maxLevel || 4, "NASA SDO / HMI continuum synoptic")
      );
      layer.brightness = 1.38;
      layer.contrast = 1.14;
      layer.saturation = 1.65;
      return { color: layer, shade: null };
    } catch (err) {
      console.warn("[LIPAS] solar tile pyramid failed, falling back to disk remap", err);
    }
    const urls = [api("/api/solar/sdo"), api("/api/solar/synoptic")];
    let canvas = null;
    let credit = "NASA SDO / HMI continuum";
    for (const url of urls) {
      try {
        const img = await loadImage(url);
        if (img.width >= img.height * 1.6) {
          canvas = document.createElement("canvas");
          canvas.width = img.width;
          canvas.height = img.height;
          canvas.getContext("2d").drawImage(img, 0, 0);
          credit = "NASA SDO / HMI continuum mosaic";
        } else {
          canvas = diskToEquirect(img, 2048, 1024);
        }
        break;
      } catch (loadErr) {
        console.warn("[LIPAS] solar imagery source failed", url, loadErr);
      }
    }
    if (!canvas) throw new Error("No solar photosphere imagery available");
    const layer = globe.imageryLayers.addImageryProvider(
      new Cesium.SingleTileImageryProvider({
        url: canvas.toDataURL("image/jpeg", 0.92),
        rectangle: Cesium.Rectangle.fromDegrees(-180, -90, 180, 90),
        tileWidth: canvas.width,
        tileHeight: canvas.height,
        credit,
      })
    );
    return { color: layer, shade: null };
  }

  function styleSpaceScene(viewer, cfg) {
    const scene = viewer.scene;
    scene.backgroundColor = Cesium.Color.fromCssColorString(cfg.body === "sun" ? "#050200" : "#03050a");
    if (scene.fog) scene.fog.enabled = false;
    if (scene.moon) scene.moon.show = false;
    if (scene.sun) scene.sun.show = false;
    if (scene.skyAtmosphere) scene.skyAtmosphere.show = false;
    if (cfg.body === "sun" && scene.globe) {
      scene.globe.showGroundAtmosphere = false;
      scene.globe.enableLighting = false;
    }
  }

  function applySubsolarLight(viewer, ellipsoid, subLon, subLat, on) {
    const globe = viewer.scene.globe;
    if (!on) {
      globe.enableLighting = false;
      return;
    }
    globe.enableLighting = true;
    const sunDir = Cesium.Cartesian3.normalize(
      Cesium.Cartesian3.fromDegrees(subLon, subLat, 0, ellipsoid),
      new Cesium.Cartesian3()
    );
    viewer.scene.light = new Cesium.DirectionalLight({
      direction: Cesium.Cartesian3.negate(sunDir, new Cesium.Cartesian3()),
      intensity: 2.15,
      color: Cesium.Color.fromCssColorString("#fff4e0"),
    });
  }

  function hazardsFor(body) {
    return BODY_HAZARDS[body] || BODY_HAZARDS.mercury;
  }

  function initMobileOptions(viewer) {
    const openBtn = document.getElementById("globeOptionsOpen");
    const closeBtn = document.getElementById("globeOptionsClose");
    const mq = window.matchMedia("(max-width: 720px)");

    function resizeGlobe() {
      try {
        if (viewer && !viewer.isDestroyed()) viewer.resize();
      } catch (e) {}
    }

    function setOptionsOpen(open) {
      if (!mq.matches || document.body.classList.contains("embed-mode")) {
        document.body.classList.remove("globe-options-open");
        return;
      }
      document.body.classList.toggle("globe-options-open", open);
      setTimeout(resizeGlobe, 80);
    }

    openBtn?.addEventListener("click", () => setOptionsOpen(true));
    closeBtn?.addEventListener("click", () => setOptionsOpen(false));
    mq.addEventListener("change", () => {
      if (!mq.matches) document.body.classList.remove("globe-options-open");
      resizeGlobe();
    });
  }

  async function start(userCfg) {
    const cfg = Object.assign(
      {
        body: "mercury",
        radiusMeters: 2439700,
        baseColor: "#8a7a68",
        markerColor: "#e07a3d",
        imageryKind: "trek",
        imageryUrl:
          "/api/trek/Mercury/EQ/Mercury_MESSENGER_MDIS_Basemap_EnhancedColor_Mosaic_Global_665m/1.0.0/default/default028mm/{z}/{y}/{x}.jpg",
        hillshadeUrl:
          "/api/trek/Mercury/EQ/Mercury_Messenger_USGS_DEM_665m_v2_Hillshade/1.0.0/default/default028mm/{z}/{y}/{x}.png",
        imageryCredit: "NASA MESSENGER MDIS Enhanced Color + USGS MLA hillshade (Trek)",
        maxLevel: 6,
        sitesUrl: "/api/mercury/sites",
        sitesListKey: "sites",
        dashboardBase: "index.html",
        fallbackSites: MERCURY_FALLBACK_SITES.map((s) => normalizeSite(s, "mercury")),
      },
      userCfg || {}
    );

    const q = new URLSearchParams(location.search);
    if (q.get("embed") === "1") document.body.classList.add("embed-mode");
    global.__LIPAS_CESIUM_VIEW = q.get("view") || "3d";

    try {
      if (typeof Cesium === "undefined") throw new Error("Cesium library failed to load");

      let token = "";
      try {
        const resp = await fetch("/client-token", { cache: "no-store" });
        if (resp.ok) {
          const j = await resp.json();
          token = j.token || "";
        }
      } catch (tokenErr) {
        console.warn("CESIUM_ION_TOKEN unavailable; continuing with public imagery.", tokenErr);
      }
      if (token) Cesium.Ion.defaultAccessToken = token;

      const ellipsoid = new Cesium.Ellipsoid(cfg.radiusMeters, cfg.radiusMeters, cfg.radiusMeters);
      try {
        if (Cesium.Ellipsoid) Cesium.Ellipsoid.default = ellipsoid;
      } catch (ellErr) {
        console.warn("Could not set default ellipsoid", ellErr);
      }

      const bodyGlobe = new Cesium.Globe(ellipsoid);
      bodyGlobe.terrainProvider = new Cesium.EllipsoidTerrainProvider({ ellipsoid });
      bodyGlobe.baseColor = Cesium.Color.fromCssColorString(cfg.baseColor);
      bodyGlobe.show = true;
      bodyGlobe.enableLighting = false;
      bodyGlobe.depthTestAgainstTerrain = false;

      const viewer = new Cesium.Viewer("cesiumContainer", {
        globe: bodyGlobe,
        baseLayer: false,
        mapProjection: new Cesium.GeographicProjection(ellipsoid),
        baseLayerPicker: false,
        geocoder: false,
        homeButton: false,
        sceneModePicker: false,
        navigationHelpButton: false,
        animation: false,
        timeline: false,
        fullscreenButton: false,
        vrButton: false,
        infoBox: false,
        selectionIndicator: false,
      });
      viewer.scene.globe.depthTestAgainstTerrain = false;
      styleSpaceScene(viewer, cfg);
      const sscc = viewer.scene.screenSpaceCameraController;
      sscc.minimumZoomDistance = cfg.radiusMeters * 0.08;
      sscc.maximumZoomDistance = cfg.radiusMeters * 12;
      global.viewer = viewer;

      let baseLayers = { color: null, shade: null };
      try {
        if (bodyGlobe.imageryLayers) bodyGlobe.imageryLayers.removeAll();
        if (cfg.imageryKind === "solar") baseLayers = await attachSolarImagery(bodyGlobe, ellipsoid, cfg);
        else baseLayers = attachTrekImagery(bodyGlobe, ellipsoid, cfg);
      } catch (imageryErr) {
        console.warn("Base imagery layer failed to attach.", imageryErr);
      }
      const baseCount = bodyGlobe.imageryLayers ? bodyGlobe.imageryLayers.length : 1;

      const WORLD_RECT = Cesium.Rectangle.fromDegrees(-180, -90, 180, 90);
      const HAZARD_TYPES = hazardsFor(cfg.body);
      const hazardLayers = Object.create(null);
      let sites = (cfg.fallbackSites || []).slice();
      let hazardMeta = {};
      let clock = { subsolar: { lon: 0, lat: 0 }, planets: [], hour: 0, carrington_deg_per_hour: 13.2 / 24 };
      let forecastSeries = null;

      function currentSeverity(spec) {
        const h = Number(clock.hour) || 0;
        const series = forecastSeries;
        if (!series) return spec.base;
        const idx = Math.max(0, Math.min((series.solar || series.kp || []).length - 1, Math.round(h)));
        const pick = (key, scale, floor) => {
          const arr = series[key];
          if (!arr || !arr.length) return spec.base;
          const v = Number(arr[idx]);
          if (!Number.isFinite(v)) return spec.base;
          return Math.max(floor || 0.2, Math.min(1, v / scale));
        };
        if (spec.type === "Solar" || spec.type === "Flare") return pick("solar", 55, 0.25);
        if (spec.type === "SEP") return pick("sep", 8, 0.2);
        if (spec.type === "CME") return pick("cme", 8, 0.2);
        if (spec.type === "Radiation") return pick("radiation", 0.18, 0.25);
        if (spec.type === "Temperature") return spec.base;
        if (spec.type === "Storm") return pick("kp", 7, 0.2);
        return spec.base;
      }

      function buildHazardProvider(type, sev) {
        const spec = HAZARD_TYPES.find((h) => h.type === type) || { type, siteKey: "solar", mode: "dayside" };
        const grid = window.LipasHazardGrid;
        const meta = {
          ...hazardMeta,
          subsolarLon: clock.subsolar?.lon,
          subsolarLat: clock.subsolar?.lat,
          hour: clock.hour,
          severity: sev,
        };
        let canvas = null;
        if (cfg.body === "sun" && grid) {
          if (spec.mode === "sunspots" && grid.makeSunspotCanvas) {
            canvas = grid.makeSunspotCanvas(sites, {
              style: "umbra",
              hour: clock.hour,
              carringtonDegPerHour: clock.carrington_deg_per_hour,
            });
          } else if (spec.mode === "ar-glow" && grid.makeSunspotCanvas) {
            const glowSites = sites.filter((s) => {
              if (type === "Flare") return Number(s.sep) > 0.12 || Number(s.intensity) > 0.55;
              if (type === "CME") return Number(s.cme) > 0.08;
              return Number(s.sep) > 0.2;
            });
            canvas = grid.makeSunspotCanvas(glowSites.length ? glowSites : sites, {
              style: type === "Flare" ? "flare" : type === "CME" ? "cme" : "sep",
              hour: clock.hour,
              carringtonDegPerHour: clock.carrington_deg_per_hour,
            });
          }
        } else if (cfg.body === "mercury" && grid) {
          const h = Math.max(0, Math.min(24, Math.round(Number(clock.hour) || 0)));
          const cuspFromFc = Number(forecastSeries?.cusp_lat?.[h]);
          const cuspFromClock = Number(clock.drivers?.cusp_latitude_deg);
          const cuspLat = Number.isFinite(cuspFromFc)
            ? cuspFromFc
            : Number.isFinite(cuspFromClock)
              ? cuspFromClock
              : 52;
          const fieldOpts = {
            subsolarLon: clock.subsolar?.lon,
            subsolarLat: clock.subsolar?.lat,
            severity: sev,
            cuspLat,
          };
          if (grid.makeMercuryFieldCanvas) {
            canvas = grid.makeMercuryFieldCanvas(type, fieldOpts);
          } else {
            canvas = grid.makeIlluminationCanvas(type === "Storm" ? "SEP" : type, fieldOpts);
          }
        } else if (grid) {
          if (spec.mode === "dayside" || spec.mode === "thermal") {
            canvas = grid.makeIlluminationCanvas(type, {
              subsolarLon: clock.subsolar?.lon,
              subsolarLat: clock.subsolar?.lat,
              severity: sev,
            });
            if (spec.mode === "thermal" && grid.paintHotspots) {
              const peaks = (sites || [])
                .filter((s) => Number.isFinite(s?.lat) && Math.abs(s.lat) >= 70)
                .map((s) => ({ lat: s.lat, lon: s.lon, intensity: 0.7 }));
              if (peaks.length && canvas) grid.paintHotspots(canvas.getContext("2d"), "Temperature", peaks, sev);
            }
          } else if (spec.mode === "mixed") {
            canvas = grid.makeIlluminationCanvas("Radiation", {
              subsolarLon: clock.subsolar?.lon,
              subsolarLat: clock.subsolar?.lat,
              severity: sev,
            });
            const peaks = (sites || [])
              .filter((s) => Number.isFinite(s?.lat) && Number.isFinite(s?.lon))
              .map((s) => ({
                lat: s.lat,
                lon: s.lon,
                intensity: Math.max(0.25, Math.min(1, Number(s.radiation || s.intensity || 0.08) / 0.18)),
              }));
            if (peaks.length && canvas && grid.paintHotspots) {
              grid.paintHotspots(canvas.getContext("2d"), "Radiation", peaks, sev);
            }
          } else if (spec.mode === "dayside-soft" && grid.paintHotspots) {
            canvas = grid.makeIlluminationCanvas(type, {
              subsolarLon: clock.subsolar?.lon,
              subsolarLat: clock.subsolar?.lat,
              severity: sev,
            });
            const key = spec.siteKey || "sep";
            const peaks = (sites || [])
              .filter((s) => Number.isFinite(s?.lat) && Number.isFinite(s?.lon))
              .map((s) => ({
                lat: s.lat,
                lon: s.lon,
                intensity: Math.max(0.2, Math.min(1, Number(s[key] || s.sep || s.cme || 0) / 6)),
              }));
            if (peaks.length && canvas) {
              grid.paintHotspots(canvas.getContext("2d"), type, peaks, sev);
            }
          }
        }
        if (!canvas) {
          const c = document.createElement("canvas");
          c.width = 1024;
          c.height = 512;
          canvas = c;
        }
        return new Cesium.SingleTileImageryProvider({
          url: canvas.toDataURL("image/png"),
          rectangle: WORLD_RECT,
          tileWidth: canvas.width,
          tileHeight: canvas.height,
        });
      }

      function refreshAllHazardLayers(meta) {
        if (meta) hazardMeta = { ...hazardMeta, ...meta };
        Object.keys(hazardLayers).forEach((type) => {
          const h = hazardLayers[type];
          if (!h) return;
          const spec = HAZARD_TYPES.find((s) => s.type === type);
          const sev = spec ? currentSeverity(spec) : h.severity;
          h.severity = sev;
          const newLayer = bodyGlobe.imageryLayers.addImageryProvider(buildHazardProvider(type, sev), h.idx);
          newLayer.alpha = h.layer.alpha;
          newLayer.show = h.on;
          const old = h.layer;
          h.layer = newLayer;
          bodyGlobe.imageryLayers.remove(old, true);
        });
      }

      HAZARD_TYPES.forEach((spec, i) => {
        const idx = baseCount + i;
        const layer = bodyGlobe.imageryLayers.addImageryProvider(buildHazardProvider(spec.type, spec.base), idx);
        const on = !!document.getElementById(spec.checkboxId)?.checked;
        layer.alpha = 0.72;
        layer.show = on;
        hazardLayers[spec.type] = { layer, severity: spec.base, on, idx };
      });
      global.__LIPAS_HAZARD_LAYERS = hazardLayers;

      function setHazardTypeVisible(type, visible) {
        const h = hazardLayers[type];
        if (!h) return;
        h.on = !!visible;
        h.layer.show = h.on;
      }

      function syncVisibilityFromCheckboxes() {
        HAZARD_TYPES.forEach((spec) => {
          setHazardTypeVisible(spec.type, !!document.getElementById(spec.checkboxId)?.checked);
        });
      }
      syncVisibilityFromCheckboxes();

      function applyActiveHazardLayers(keys) {
        const list = Array.isArray(keys) ? keys : [];
        if (!list.length) {
          syncVisibilityFromCheckboxes();
          return;
        }
        const want = new Set(list.map((k) => TYPE_FROM_KEY[k] || k));
        Object.values(TYPE_FROM_KEY).forEach((type) => {
          const on = want.has(type);
          setHazardTypeVisible(type, on);
          const el = document.getElementById(ID_FROM_TYPE[type]);
          if (el) el.checked = on;
        });
      }
      global.applyActiveHazardLayers = applyActiveHazardLayers;

      global.syncCesiumHazards = function (hd) {
        if (!hd || !hd._meta) return;
        hazardMeta = { ...hd._meta };
        refreshAllHazardLayers(hazardMeta);
      };

      try {
        const raw = localStorage.getItem("lipas_hazard_meta");
        if (raw) global.syncCesiumHazards({ _meta: JSON.parse(raw) });
      } catch (e) {}

      const _hazPulseT0 = performance.now();
      viewer.clock.onTick.addEventListener(() => {
        const t = (performance.now() - _hazPulseT0) / 1000;
        let i = 0;
        const amp = cfg.body === "sun" ? 0.1 : 0.16;
        const base = cfg.body === "sun" ? 0.7 : 0.62;
        for (const type in hazardLayers) {
          const h = hazardLayers[type];
          i++;
          if (!h.on) continue;
          h.layer.alpha = base + amp * Math.sin(t * (0.2 + i * 0.035) + i * 1.3);
        }
      });

      window.addEventListener("message", (ev) => {
        const msg = ev.data;
        if (!msg || msg.type !== "lipas_hazards") return;
        if (msg.meta) {
          try {
            global.syncCesiumHazards({ _meta: msg.meta });
          } catch (e) {}
        }
        if (Array.isArray(msg.active)) applyActiveHazardLayers(msg.active);
        else syncVisibilityFromCheckboxes();
      });

      const markerH = Math.max(8000, cfg.radiusMeters * (25000 / MOON_R));
      const markerColor = Cesium.Color.fromCssColorString(cfg.markerColor || "#e07a3d");
      const siteEntities = [];
      const planetEntities = [];

      function driftedSiteLon(site) {
        if (cfg.body !== "sun") return site.lon;
        const drift = Number(clock.carrington_deg_per_hour) || 13.2 / 24;
        return wrapLon(site.lon - drift * (Number(clock.hour) || 0));
      }

      function rebuildSiteEntities(list) {
        siteEntities.splice(0).forEach((s) => viewer.entities.remove(s.entity));
        list.forEach((site, i) => {
          const lon = driftedSiteLon(site);
          const inten = Number(site.intensity);
          const size = cfg.body === "sun"
            ? 6 + (Number.isFinite(inten) ? inten * 10 : 4)
            : 8;
          const color = cfg.body === "sun"
            ? Cesium.Color.fromCssColorString("#1a0c04").withAlpha(0.95)
            : markerColor;
          const ent = viewer.entities.add({
            id: "site_" + (site.id || i),
            position: Cesium.Cartesian3.fromDegrees(lon, site.lat, markerH, ellipsoid),
            point: {
              pixelSize: size,
              color,
              outlineColor: Cesium.Color.fromCssColorString(cfg.body === "sun" ? "#f0c060" : "#0b0e13"),
              outlineWidth: cfg.body === "sun" ? 2 : 1.5,
              heightReference: Cesium.HeightReference.NONE,
              scaleByDistance: new Cesium.NearFarScalar(
                cfg.radiusMeters * 0.08,
                1.4,
                cfg.radiusMeters * 3.2,
                0.65
              ),
            },
            label: {
              text: site.name,
              font: "11px IBM Plex Sans, sans-serif",
              fillColor: Cesium.Color.fromCssColorString("#e6eef8"),
              outlineColor: Cesium.Color.fromCssColorString("#0b0e13"),
              outlineWidth: 3,
              style: Cesium.LabelStyle.FILL_AND_OUTLINE,
              verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
              pixelOffset: new Cesium.Cartesian2(0, -10),
              show: false,
              showBackground: true,
              backgroundColor: Cesium.Color.fromCssColorString("#0b0e13").withAlpha(0.72),
              backgroundPadding: new Cesium.Cartesian2(6, 4),
              scaleByDistance: new Cesium.NearFarScalar(
                cfg.radiusMeters * 0.12,
                1.0,
                cfg.radiusMeters * 2.0,
                0.0
              ),
            },
            properties: {
              siteName: site.name,
              siteLat: site.lat,
              siteLon: site.lon,
              siteSummary: site.summary || "",
              siteId: site.id || "",
              isSite: true,
            },
          });
          siteEntities.push({ entity: ent, site, layerOn: true });
        });
      }

      function rebuildPlanetEntities(planets) {
        planetEntities.splice(0).forEach((row) => viewer.entities.remove(row.entity));
        if (cfg.body !== "sun" || !Array.isArray(planets)) return;
        const height = cfg.radiusMeters * 0.38;
        planets.forEach((p) => {
          const isEarth = p.id === "earth";
          const ent = viewer.entities.add({
            id: "planet_" + p.id,
            position: Cesium.Cartesian3.fromDegrees(p.lon, p.lat || 0, height, ellipsoid),
            point: {
              pixelSize: isEarth ? 11 : 7,
              color: Cesium.Color.fromCssColorString(isEarth ? "#7ec8ff" : "#f2d48a"),
              outlineColor: Cesium.Color.fromCssColorString("#1a1208"),
              outlineWidth: 1.5,
            },
            label: {
              text: p.name + (isEarth ? " · CM" : ""),
              font: isEarth ? "13px Syne, sans-serif" : "11px IBM Plex Sans, sans-serif",
              fillColor: Cesium.Color.fromCssColorString(isEarth ? "#c8e6ff" : "#f6e6b8"),
              outlineColor: Cesium.Color.fromCssColorString("#120c04"),
              outlineWidth: 3,
              style: Cesium.LabelStyle.FILL_AND_OUTLINE,
              verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
              pixelOffset: new Cesium.Cartesian2(0, -14),
              showBackground: true,
              backgroundColor: Cesium.Color.fromCssColorString("#120c04").withAlpha(0.62),
              backgroundPadding: new Cesium.Cartesian2(7, 4),
            },
            properties: { isPlanet: true, planetId: p.id },
          });
          planetEntities.push({ entity: ent, planet: p, layerOn: true });
        });
      }

      function setLocationsVisible(on) {
        siteEntities.forEach((s) => {
          s.layerOn = !!on;
          if (!on) s.entity.show = false;
        });
        planetEntities.forEach((s) => {
          s.layerOn = !!on;
          if (!on) s.entity.show = false;
        });
      }

      const _scratchPos = new Cesium.Cartesian3();
      const _scratchNormal = new Cesium.Cartesian3();
      const _scratchCam = new Cesium.Cartesian3();
      function isFacingCamera(lat, lon) {
        if (viewer.scene.mode !== Cesium.SceneMode.SCENE3D) return true;
        const pos = Cesium.Cartesian3.fromDegrees(lon, lat, 0, ellipsoid, _scratchPos);
        const normal = ellipsoid.geodeticSurfaceNormal(pos, _scratchNormal);
        const toCam = Cesium.Cartesian3.subtract(viewer.camera.positionWC, pos, _scratchCam);
        Cesium.Cartesian3.normalize(toCam, toCam);
        return Cesium.Cartesian3.dot(normal, toCam) > 0.1;
      }

      viewer.clock.onTick.addEventListener(() => {
        siteEntities.forEach((s) => {
          if (!s.layerOn) {
            s.entity.show = false;
            return;
          }
          s.entity.show = isFacingCamera(s.site.lat, driftedSiteLon(s.site));
        });
        planetEntities.forEach((s) => {
          if (!s.layerOn) {
            s.entity.show = false;
            return;
          }
          s.entity.show = isFacingCamera(s.planet.lat || 0, s.planet.lon);
        });
      });

      document.getElementById("showLocations")?.addEventListener("change", (e) => {
        setLocationsVisible(e.target.checked);
      });

      const hoverCard = document.getElementById("locHoverCard");
      const hoverName = document.getElementById("locHoverName");
      const hoverCoords = document.getElementById("locHoverCoords");
      const hoverSummary = document.getElementById("locHoverSummary");
      const hoverStatus = document.getElementById("locHoverStatus");
      const hoverStatusText = document.getElementById("locHoverStatusText");
      const hoverHazards = document.getElementById("locHoverHazards");
      const hoverLink = document.getElementById("locHoverLink");
      const dashBtn = document.getElementById("locDashBtn");
      const closeBtn = document.getElementById("locCloseBtn");
      let pinnedSite = null;

      function siteBrief(site) {
        const hazards = [];
        const rad = Number(site.radiation);
        const solar = Number(site.solar);
        const sep = Number(site.sep);
        const cme = Number(site.cme);
        if (cfg.body === "sun") {
          const inten = Number(site.intensity);
          if (inten > 0.7) hazards.push("High intensity");
          else if (inten > 0.4) hazards.push("Active");
          if (sep > 0.4) hazards.push("M-flare");
          if (cme > 0.2) hazards.push("X-flare");
          let status = "go";
          if (inten > 0.75 || cme > 0.25) status = "nogo";
          else if (inten > 0.45 || sep > 0.3) status = "caution";
          return {
            status,
            statusLabel: status === "go" ? "GO" : status === "caution" ? "CAUTION" : "NO-GO",
            hazards: hazards.slice(0, 3),
            link: "Disk",
          };
        }
        if (rad > 0.12) hazards.push("Radiation");
        else if (rad > 0.08) hazards.push("Rad watch");
        if (solar > 40) hazards.push("Solar");
        if (sep > 4) hazards.push("SEP");
        if (cme > 4) hazards.push("CME");
        if (Math.abs(site.lat) >= 80) hazards.push("Polar thermal");
        let status = "go";
        if (rad > 0.2 || solar > 55) status = "nogo";
        else if (rad > 0.1 || solar > 30 || sep > 3) status = "caution";
        return {
          status,
          statusLabel: status === "go" ? "GO" : status === "caution" ? "CAUTION" : "NO-GO",
          hazards: hazards.slice(0, 3),
          link: "Hermean",
        };
      }

      function fillLocCard(site, { pinned } = { pinned: false }) {
        if (!hoverCard || !site) return;
        const brief = siteBrief(site);
        hoverName.textContent = site.name;
        hoverCoords.textContent = `${Number(site.lat).toFixed(2)}°, ${Number(site.lon).toFixed(2)}°`;
        hoverSummary.textContent = site.summary || "";
        if (hoverStatus) {
          hoverStatus.className = `hov-status ${brief.status}`;
          if (hoverStatusText) hoverStatusText.textContent = brief.statusLabel;
        }
        if (hoverHazards) {
          hoverHazards.innerHTML = brief.hazards.length
            ? brief.hazards.map((h) => `<span>${h}</span>`).join("")
            : "<span>Nominal</span>";
        }
        if (hoverLink) hoverLink.textContent = brief.link;
        if (dashBtn) {
          const base = cfg.dashboardBase || "index.html";
          const params = new URLSearchParams({
            site: site.id || "",
            lat: String(site.lat),
            lon: String(site.lon),
            name: site.name,
          });
          dashBtn.href = `${base}?${params.toString()}`;
        }
        hoverCard.classList.add("show");
        hoverCard.classList.toggle("pinned", !!pinned);
        if (pinned) {
          pinnedSite = site;
          hoverCard.style.left = "";
          hoverCard.style.top = "";
        }
      }

      function clearPinnedCard() {
        pinnedSite = null;
        hoverCard?.classList.remove("pinned", "show");
      }
      closeBtn?.addEventListener("click", clearPinnedCard);

      const flyAlt = cfg.radiusMeters * (3200000 / MOON_R);
      function flyToSite(site, altitude) {
        const lon = driftedSiteLon(site);
        viewer.camera.flyTo({
          destination: Cesium.Cartesian3.fromDegrees(lon, site.lat, altitude || flyAlt * 0.28, ellipsoid),
          duration: 1.4,
        });
        siteEntities.forEach((s) => {
          if (s.entity.label) s.entity.label.show = s.site.name === site.name;
        });
      }

      const handler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas);
      handler.setInputAction((movement) => {
        if (pinnedSite) return;
        const picked = viewer.scene.pick(movement.endPosition);
        const ent = picked && picked.id;
        const isSite = ent && ent.properties && ent.properties.isSite && ent.properties.isSite.getValue();
        if (isSite) {
          const id = ent.properties.siteId ? ent.properties.siteId.getValue() : "";
          const site =
            sites.find((s) => s.id === id || s.name === ent.properties.siteName.getValue()) || {
              name: ent.properties.siteName.getValue(),
              lat: ent.properties.siteLat.getValue(),
              lon: ent.properties.siteLon.getValue(),
              summary: ent.properties.siteSummary.getValue(),
              id,
            };
          fillLocCard(site, { pinned: false });
          const x = movement.endPosition.x;
          const y = movement.endPosition.y;
          const rect = viewer.scene.canvas.getBoundingClientRect();
          hoverCard.style.left = Math.min(window.innerWidth - 300, rect.left + x + 16) + "px";
          hoverCard.style.top = Math.min(window.innerHeight - 240, rect.top + y + 16) + "px";
          document.body.style.cursor = "pointer";
        } else {
          hoverCard.classList.remove("show");
          document.body.style.cursor = "";
        }
      }, Cesium.ScreenSpaceEventType.MOUSE_MOVE);

      handler.setInputAction((click) => {
        const picked = viewer.scene.pick(click.position);
        const ent = picked && picked.id;
        if (ent && ent.properties && ent.properties.isSite && ent.properties.isSite.getValue()) {
          const id = ent.properties.siteId ? ent.properties.siteId.getValue() : "";
          const site =
            sites.find((s) => s.id === id || s.name === ent.properties.siteName.getValue()) || {
              name: ent.properties.siteName.getValue(),
              lat: ent.properties.siteLat.getValue(),
              lon: ent.properties.siteLon.getValue(),
              summary: ent.properties.siteSummary.getValue(),
              id,
            };
          flyToSite(site);
          fillLocCard(site, { pinned: true });
        }
      }, Cesium.ScreenSpaceEventType.LEFT_CLICK);

      const searchInput = document.getElementById("locSearchInput");
      const searchResults = document.getElementById("locSearchResults");
      function selectSiteFromSearch(site) {
        if (!site) return;
        if (searchInput) searchInput.value = site.name;
        searchResults?.classList.remove("show");
        flyToSite(site);
        fillLocCard(site, { pinned: true });
      }
      function renderSearch(qStr) {
        if (!searchResults) return;
        const query = (qStr || "").trim().toLowerCase();
        if (!query) {
          searchResults.classList.remove("show");
          searchResults.innerHTML = "";
          return;
        }
        const hits = sites
          .filter(
            (s) =>
              s.name.toLowerCase().includes(query) ||
              String(s.lat).includes(query) ||
              String(s.lon).includes(query) ||
              (s.summary || "").toLowerCase().includes(query) ||
              String(s.id || "").toLowerCase().includes(query)
          )
          .slice(0, 10);
        if (!hits.length) {
          searchResults.innerHTML = '<div class="loc-result"><small>No sites matched</small></div>';
          searchResults.classList.add("show");
          return;
        }
        searchResults.innerHTML = hits
          .map(
            (s) =>
              `<div class="loc-result" data-lat="${s.lat}" data-lon="${s.lon}" data-id="${String(s.id || "").replace(/"/g, "&quot;")}" data-name="${s.name.replace(/"/g, "&quot;")}" data-summary="${(s.summary || "").replace(/"/g, "&quot;")}">
              ${s.name}<small>${s.lat.toFixed(2)}°, ${s.lon.toFixed(2)}° · ${s.summary || ""}</small>
            </div>`
          )
          .join("");
        searchResults.classList.add("show");
        searchResults.querySelectorAll(".loc-result").forEach((el) => {
          el.addEventListener("click", () => {
            const found = sites.find((s) => s.id === el.dataset.id) || {
              name: el.dataset.name || "",
              lat: parseFloat(el.dataset.lat),
              lon: parseFloat(el.dataset.lon),
              summary: el.dataset.summary || "",
              id: el.dataset.id,
            };
            selectSiteFromSearch(found);
          });
        });
      }
      searchInput?.addEventListener("input", () => renderSearch(searchInput.value));
      searchInput?.addEventListener("focus", () => renderSearch(searchInput.value));
      searchInput?.addEventListener("keydown", (e) => {
        if (e.key !== "Enter") return;
        const first = searchResults?.querySelector(".loc-result[data-lat]");
        if (first) {
          e.preventDefault();
          first.click();
        }
      });
      document.addEventListener("click", (e) => {
        if (!e.target.closest(".loc-search-panel")) searchResults?.classList.remove("show");
      });

      let autoRotateEnabled = false;
      let userInteracting = false;
      let lastAutoRotateTs = performance.now();
      const AUTO_ROTATE_RATE = Cesium.Math.toRadians(1.5);
      const canvasEl = viewer.scene.canvas;
      ["mousedown", "touchstart", "wheel"].forEach((evt) =>
        canvasEl.addEventListener(evt, () => { userInteracting = true; }, { passive: true })
      );
      ["mouseup", "touchend"].forEach((evt) => window.addEventListener(evt, () => { userInteracting = false; }));
      viewer.clock.onTick.addEventListener(() => {
        const now = performance.now();
        const dt = Math.min((now - lastAutoRotateTs) / 1000, 0.25);
        lastAutoRotateTs = now;
        if (!autoRotateEnabled || userInteracting) return;
        if (viewer.scene.mode === Cesium.SceneMode.SCENE3D) {
          viewer.scene.camera.rotate(Cesium.Cartesian3.UNIT_Z, -AUTO_ROTATE_RATE * dt);
        } else {
          viewer.scene.camera.moveRight(AUTO_ROTATE_RATE * dt * cfg.radiusMeters);
        }
      });
      document.getElementById("autoRotate")?.addEventListener("change", (e) => {
        autoRotateEnabled = e.target.checked;
        lastAutoRotateTs = performance.now();
      });

      document.getElementById("showTerrain")?.addEventListener("change", (e) => {
        if (baseLayers.shade) {
          const imageryOn = !!document.getElementById("showImagery")?.checked;
          baseLayers.shade.show = !!e.target.checked && imageryOn;
        }
      });
      if (baseLayers.shade) {
        baseLayers.shade.show = !!document.getElementById("showTerrain")?.checked;
      }
      document.getElementById("showImagery")?.addEventListener("change", (e) => {
        bodyGlobe.show = true;
        const on = e.target.checked;
        if (baseLayers.color) baseLayers.color.show = on;
        if (baseLayers.detail) baseLayers.detail.show = on;
        if (baseLayers.shade) {
          baseLayers.shade.show = on && !!document.getElementById("showTerrain")?.checked;
        }
      });
      document.getElementById("enableLighting")?.addEventListener("change", (e) => {
        if (cfg.body === "sun") {
          bodyGlobe.enableLighting = false;
          return;
        }
        applySubsolarLight(viewer, ellipsoid, clock.subsolar?.lon || 0, clock.subsolar?.lat || 0, !!e.target.checked);
      });
      document.getElementById("viewMode")?.addEventListener("change", (e) => {
        bodyGlobe.show = true;
        if (e.target.value === "3d") viewer.scene.morphTo3D(0);
        else if (e.target.value === "columbus") viewer.scene.morphToColumbusView(0);
        else viewer.scene.morphTo2D(0);
      });
      ["showRadiation", "showMicrometeorites", "showDust", "showMoonquakes", "showTemperature", "showSolar", "showSep", "showCme", "showStorm", "showSunspots", "showFlares"].forEach((id) => {
        document.getElementById(id)?.addEventListener("change", syncVisibilityFromCheckboxes);
      });

      rebuildSiteEntities(sites);
      setLocationsVisible(!!document.getElementById("showLocations")?.checked);

      if (cfg.body === "sun") {
        const glowR = cfg.radiusMeters * 1.04;
        viewer.entities.add({
          name: "corona",
          position: Cesium.Cartesian3.ZERO,
          ellipsoid: {
            radii: new Cesium.Cartesian3(glowR, glowR, glowR),
            material: Cesium.Color.fromCssColorString("#ffb14a").withAlpha(0.09),
          },
        });
      }

      async function applyHour(hour) {
        clock.hour = Number(hour) || 0;
        try {
          if (window.LipasGlobeTimebar) {
            const next = await window.LipasGlobeTimebar.fetchClock(cfg.body, clock.hour);
            clock = Object.assign(clock, next);
            if (!clock.subsolar) clock.subsolar = { lon: 0, lat: 0 };
          }
        } catch (clockErr) {
          console.warn("[LIPAS] globe clock", clockErr);
        }
        const lightingOn = cfg.body !== "sun" && !!document.getElementById("enableLighting")?.checked;
        applySubsolarLight(viewer, ellipsoid, clock.subsolar?.lon || 0, clock.subsolar?.lat || 0, lightingOn);
        rebuildPlanetEntities(clock.planets || []);
        setLocationsVisible(!!document.getElementById("showLocations")?.checked);
        refreshAllHazardLayers(hazardMeta);
        if (cfg.body === "sun") rebuildSiteEntities(sites);
        const bits = [];
        if (clock.phase?.name) bits.push(clock.phase.name);
        if (clock.drivers?.goes_class) bits.push("GOES " + clock.drivers.goes_class);
        if (clock.drivers?.kp != null) bits.push("Kp " + Number(clock.drivers.kp).toFixed(1));
        if (cfg.body === "sun") bits.push("Earth at CM (lon 0)");
        if (clock.subsolar && cfg.body !== "sun") {
          bits.push("subsolar " + Number(clock.subsolar.lon).toFixed(0) + "°");
        }
        timebar.setMeta(bits.join(" · "));
      }

      const timebar = window.LipasGlobeTimebar
        ? window.LipasGlobeTimebar.bind({ onChange: applyHour })
        : { getHour: () => 0, setMeta() {} };

      applyHour(timebar.getHour());

      if (cfg.body === "mercury") {
        fetch(api("/api/mercury/forecast?site=equator&hours=25"))
          .then((r) => (r.ok ? r.json() : null))
          .then((d) => {
            if (d) forecastSeries = d;
          })
          .catch(() => {});
      }

      const initialView = (global.__LIPAS_CESIUM_VIEW || "3d").toLowerCase();
      const viewSelect = document.getElementById("viewMode");
      if (viewSelect && (initialView === "columbus" || initialView === "2d")) {
        viewSelect.value = initialView;
        viewSelect.dispatchEvent(new Event("change"));
      }

      const isEmbed = document.body.classList.contains("embed-mode");
      if (viewer.scene.mode === Cesium.SceneMode.SCENE2D) {
        viewer.camera.flyTo({ destination: WORLD_RECT, duration: isEmbed ? 0.5 : 1.5 });
      } else {
        viewer.camera.flyTo({
          destination: Cesium.Cartesian3.fromDegrees(0, 0, isEmbed ? flyAlt * 1.4 : flyAlt, ellipsoid),
          duration: isEmbed ? 0.5 : 2.0,
        });
      }

      fetchSites(cfg).then((live) => {
        if (!live.length) return;
        sites = live;
        rebuildSiteEntities(sites);
        setLocationsVisible(!!document.getElementById("showLocations")?.checked);
        refreshAllHazardLayers(hazardMeta);
      });

      try {
        if (window.parent && window.parent !== window) {
          window.parent.postMessage({ type: "lipas_cesium_ready" }, "*");
        }
      } catch (e) {}

      initMobileOptions(viewer);
      console.info(
        "[LIPAS] Cesium",
        cfg.body,
        "ready -",
        Object.keys(hazardLayers).length,
        "hazard layers,",
        siteEntities.length,
        "markers"
      );
    } catch (e) {
      console.warn("Cesium init failed", e);
      const detail = e && e.message ? String(e.message) : "unknown error";
      const el = document.getElementById("cesiumContainer");
      if (el) {
        el.innerHTML =
          '<div class="globe-fail"><strong>Globe unavailable</strong>Cesium failed to initialize (' +
          detail.replace(/[<>&]/g, "") +
          "). Serve this page from the L.I.P.A.S. Flask server, then hard-reload.</div>";
      }
    } finally {
      setTimeout(hideLoading, 400);
    }
  }

  setTimeout(hideLoading, 12000);

  global.LipasCesiumGlobe = { start };
})(typeof window !== "undefined" ? window : globalThis);
