(function (global) {
  "use strict";

  const W = 1024;
  const H = 512;

  const TYPE_CHANNEL = {
    Radiation: "radiation",
    Micrometeorites: "micrometeorites",
    Dust: "dust",
    Moonquake: "moonquakes",
    Temperature: "temperature",
    Solar: "solar",
    SEP: "radiation",
    CME: "solar",
  };

  const PALETTES = {
    Radiation: { c0: [255, 70, 60], c1: [255, 140, 70], c2: [180, 40, 100] },
    Micrometeorites: { c0: [255, 200, 60], c1: [255, 140, 40], c2: [220, 100, 30] },
    Dust: { c0: [210, 170, 100], c1: [170, 130, 80], c2: [120, 90, 55] },
    Moonquake: { c0: [180, 120, 255], c1: [110, 70, 220], c2: [70, 40, 160] },
    Temperature: { c0: [255, 90, 50], c1: [80, 180, 255], c2: [30, 80, 200] },
    Solar: { c0: [255, 220, 80], c1: [255, 150, 40], c2: [255, 90, 30] },
    SEP: { c0: [255, 110, 160], c1: [220, 70, 120], c2: [140, 30, 80] },
    CME: { c0: [255, 160, 60], c1: [240, 100, 40], c2: [160, 50, 20] },
    Storm: { c0: [120, 200, 255], c1: [70, 140, 220], c2: [30, 70, 160] },
    Flare: { c0: [255, 180, 60], c1: [255, 90, 30], c2: [180, 40, 10] },
    ActiveRegion: { c0: [8, 3, 1], c1: [70, 32, 8], c2: [210, 140, 50] },
  };

  const DAYSIDE_TYPES = new Set(["Solar", "Temperature"]);
  const DAYSIDE_SOFT = new Set(["SEP", "CME", "Storm", "Flare"]);

  let gridCache = null;
  let gridPromise = null;

  function apiUrl(path) {
    return typeof global.lipasApiUrl === "function" ? global.lipasApiUrl(path) : path;
  }

  function wrapLon(lon) {
    let x = lon;
    while (x > 180) x -= 360;
    while (x < -180) x += 360;
    return x;
  }

  function sampleField(field, lats, lons, lat, lon) {
    if (!field?.length || !lats?.length || !lons?.length) return null;
    const lo = wrapLon(lon);
    const la = Math.max(-90, Math.min(90, lat));

    let i1 = 0;
    while (i1 < lats.length - 1 && lats[i1 + 1] < la) i1++;
    const i0 = Math.max(0, i1 - 1);
    i1 = Math.min(lats.length - 1, i0 + 1);

    let j0 = 0;
    for (let j = 0; j < lons.length; j++) {
      if (Math.abs(wrapLon(lons[j] - lo)) < Math.abs(wrapLon(lons[j0] - lo))) j0 = j;
    }
    const j1 = (j0 + 1) % lons.length;

    const lat0 = lats[i0];
    const lat1 = lats[i1];
    const lon0 = lons[j0];
    const lon1 = lons[j1];
    const ty = lat1 === lat0 ? 0.5 : (la - lat0) / (lat1 - lat0);
    let dlon = wrapLon(lon1 - lon0);
    if (Math.abs(dlon) > 180) dlon = dlon > 0 ? dlon - 360 : dlon + 360;
    let dlo = wrapLon(lo - lon0);
    if (Math.abs(dlo) > 180) dlo = dlo > 0 ? dlo - 360 : dlo + 360;
    const tx = Math.abs(dlon) < 1e-9 ? 0.5 : dlo / dlon;

    const v00 = field[i0]?.[j0];
    const v01 = field[i0]?.[j1];
    const v10 = field[i1]?.[j0];
    const v11 = field[i1]?.[j1];
    const vals = [v00, v01, v10, v11].filter((v) => Number.isFinite(v));
    if (!vals.length) return null;
    if (vals.length < 4) return vals.reduce((a, b) => a + b, 0) / vals.length;

    const a = v00 * (1 - tx) + v01 * tx;
    const b = v10 * (1 - tx) + v11 * tx;
    return a * (1 - ty) + b * ty;
  }

  function fieldStats(field) {
    let min = Infinity;
    let max = -Infinity;
    let sum = 0;
    let n = 0;
    for (let i = 0; i < field.length; i++) {
      const row = field[i];
      if (!row) continue;
      for (let j = 0; j < row.length; j++) {
        const v = row[j];
        if (!Number.isFinite(v)) continue;
        min = Math.min(min, v);
        max = Math.max(max, v);
        sum += v;
        n++;
      }
    }
    if (!n) return { min: 0, max: 0, mean: 0, stdev: 0, span: 0 };
    const mean = sum / n;
    let varSum = 0;
    for (let i = 0; i < field.length; i++) {
      const row = field[i];
      if (!row) continue;
      for (let j = 0; j < row.length; j++) {
        const v = row[j];
        if (!Number.isFinite(v)) continue;
        const d = v - mean;
        varSum += d * d;
      }
    }
    return { min, max, mean, stdev: Math.sqrt(varSum / n), span: max - min };
  }

  /** Collect hotspot cells — always returns localized peaks for blob splats. */
  function collectHotspots(field, lats, lons, stats, maxPeaks) {
    const cells = [];
    const nLat = field.length;
    const nLon = field[0]?.length || 0;
    const span = Math.max(stats.span, 1e-9);

    for (let i = 0; i < nLat; i++) {
      for (let j = 0; j < nLon; j++) {
        const v = field[i][j];
        if (!Number.isFinite(v)) continue;
        const intensity = Math.max(0.12, Math.min(1, (v - stats.min) / span));
        cells.push({ lat: lats[i], lon: lons[j], value: v, intensity });
      }
    }
    cells.sort((a, b) => b.value - a.value);

    const peaks = [];
    const minSep = 0.08;
    for (const c of cells) {
      if (peaks.length >= (maxPeaks || 14)) break;
      const tooClose = peaks.some(
        (p) => Math.hypot((p.lat - c.lat) / 90, wrapLon(p.lon - c.lon) / 180) < minSep
      );
      if (!tooClose) peaks.push(c);
    }

    if (!peaks.length && cells.length) {
      peaks.push(cells[0], cells[Math.floor(cells.length / 2)], cells[cells.length - 1]);
    }
    return peaks;
  }

  function lonToPx(lon, width) {
    return ((wrapLon(lon) + 180) / 360) * Math.max(1, width - 1);
  }

  function latToPy(lat, height) {
    return ((90 - lat) / 180) * Math.max(1, height - 1);
  }

  function splatBlob(ctx, px, py, radius, pal, intensity, alphaScale) {
    const local = Math.max(0.25, Math.min(1, intensity));
    const a0 = (0.28 + local * 0.52) * alphaScale;
    const a1 = (0.1 + local * 0.24) * alphaScale;
    [-W, 0, W].forEach((dx) => {
      const cx = px + dx;
      const grad = ctx.createRadialGradient(cx, py, 1, cx, py, radius);
      grad.addColorStop(0, `rgba(${pal.c0[0]},${pal.c0[1]},${pal.c0[2]},${a0.toFixed(3)})`);
      grad.addColorStop(0.45, `rgba(${pal.c1[0]},${pal.c1[1]},${pal.c1[2]},${a1.toFixed(3)})`);
      grad.addColorStop(1, `rgba(${pal.c1[0]},${pal.c1[1]},${pal.c1[2]},0)`);
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(cx, py, radius, 0, Math.PI * 2);
      ctx.fill();
    });
  }

  function emptyCanvas() {
    const canvas = document.createElement("canvas");
    canvas.width = W;
    canvas.height = H;
    return canvas;
  }

  function cosineMu(lat, lon, subLat, subLon) {
    const la = (lat * Math.PI) / 180;
    const sla = (subLat * Math.PI) / 180;
    const dlon = (wrapLon(lon - subLon) * Math.PI) / 180;
    return Math.sin(la) * Math.sin(sla) + Math.cos(la) * Math.cos(sla) * Math.cos(dlon);
  }

  function makeMercuryFieldCanvas(type, opts) {
    const pal = PALETTES[type] || PALETTES.Solar;
    const subLon = Number.isFinite(Number(opts?.subsolarLon)) ? Number(opts.subsolarLon) : 0;
    const subLat = Number(opts?.subsolarLat) || 0;
    const sev = Math.max(0.18, Math.min(1, opts?.severity != null ? opts.severity : 0.55));
    const cusp = Math.max(28, Math.min(78, Number(opts?.cuspLat) || 52));
    const canvas = document.createElement("canvas");
    canvas.width = W;
    canvas.height = H;
    const ctx = canvas.getContext("2d");
    const img = ctx.createImageData(W, H);
    const d = img.data;
    for (let y = 0; y < H; y++) {
      const lat = 90 - (y / Math.max(1, H - 1)) * 180;
      const cuspBand = Math.exp(-0.5 * Math.pow((Math.abs(lat) - cusp) / 11, 2));
      const polar = Math.min(1, Math.abs(lat) / 90);
      for (let x = 0; x < W; x++) {
        const lon = (x / Math.max(1, W - 1)) * 360 - 180;
        const mu = cosineMu(lat, lon, subLat, subLon);
        const day = Math.max(0, mu);
        const night = Math.max(0, -mu);
        const i = (y * W + x) * 4;
        let r = pal.c0[0];
        let g = pal.c0[1];
        let b = pal.c0[2];
        let a = 0;
        if (type === "Temperature") {
          if (mu > 0) {
            const t = Math.pow(day, 0.62);
            r = 255;
            g = Math.round(70 + t * 100);
            b = 36;
            a = (0.16 + t * 0.7 * sev) * 255;
          } else {
            r = 36;
            g = 105;
            b = 210;
            a = (0.14 + Math.min(1, night) * 0.42 * sev) * 255;
          }
        } else if (type === "Solar") {
          r = pal.c0[0];
          g = pal.c0[1];
          b = pal.c0[2];
          a = Math.pow(day, 0.95) * 0.82 * sev * 255;
        } else if (type === "Radiation") {
          r = pal.c0[0];
          g = pal.c0[1];
          b = pal.c0[2];
          a = (0.16 + 0.38 * night + 0.28 * day + 0.42 * cuspBand + 0.18 * polar) * 0.62 * sev * 255;
        } else if (type === "SEP" || type === "CME") {
          r = pal.c0[0];
          g = pal.c0[1];
          b = pal.c0[2];
          a = (0.1 + 0.78 * day + 0.45 * cuspBand * (0.35 + day)) * 0.58 * sev * 255;
        } else if (type === "Storm") {
          r = pal.c0[0];
          g = pal.c0[1];
          b = pal.c0[2];
          a = (0.12 + 0.5 * day + 0.78 * cuspBand) * 0.6 * sev * 255;
        } else {
          a = (0.12 + 0.7 * day) * 0.5 * sev * 255;
        }
        d[i] = r;
        d[i + 1] = g;
        d[i + 2] = b;
        d[i + 3] = Math.max(0, Math.min(255, a));
      }
    }
    ctx.putImageData(img, 0, 0);
    return canvas;
  }

  function makeIlluminationCanvas(type, opts) {
    const pal = PALETTES[type] || PALETTES.Solar;
    const subLon = Number(opts?.subsolarLon);
    const subLat = Number(opts?.subsolarLat) || 0;
    if (!Number.isFinite(subLon)) return emptyCanvas();
    const sev = Math.max(0.15, Math.min(1, opts?.severity != null ? opts.severity : 0.55));
    const canvas = document.createElement("canvas");
    canvas.width = W;
    canvas.height = H;
    const ctx = canvas.getContext("2d");
    const img = ctx.createImageData(W, H);
    const d = img.data;
    for (let y = 0; y < H; y++) {
      const lat = 90 - (y / Math.max(1, H - 1)) * 180;
      for (let x = 0; x < W; x++) {
        const lon = (x / Math.max(1, W - 1)) * 360 - 180;
        const mu = cosineMu(lat, lon, subLat, subLon);
        const i = (y * W + x) * 4;
        let r = pal.c0[0];
        let g = pal.c0[1];
        let b = pal.c0[2];
        let a = 0;
        if (type === "Temperature") {
          if (mu > 0) {
            const t = Math.pow(mu, 0.65);
            r = 255;
            g = Math.round(80 + t * 90);
            b = 40;
            a = (0.1 + t * 0.52 * sev) * 255;
          } else {
            const night = Math.min(1, -mu);
            r = 40;
            g = 110;
            b = 210;
            a = (0.08 + night * 0.32 * sev) * 255;
          }
        } else if (type === "Solar") {
          a = Math.pow(Math.max(0, mu), 1.12) * 0.58 * sev * 255;
        } else if (type === "SEP" || type === "CME" || type === "Storm" || type === "Flare") {
          a = (0.12 + 0.78 * Math.max(0, mu)) * 0.42 * sev * 255;
        } else if (type === "Radiation") {
          a = (0.22 + 0.38 * (1 - Math.max(0, mu))) * 0.28 * sev * 255;
        }
        d[i] = r;
        d[i + 1] = g;
        d[i + 2] = b;
        d[i + 3] = Math.max(0, Math.min(255, a));
      }
    }
    ctx.putImageData(img, 0, 0);
    return canvas;
  }

  function driftedLon(lon, hour, degPerHour) {
    const drift = Number(degPerHour);
    const h = Number(hour) || 0;
    if (!Number.isFinite(drift)) return wrapLon(lon);
    return wrapLon(lon - drift * h);
  }

  function makeSunspotCanvas(spots, opts) {
    const style = opts?.style || "umbra";
    const hour = Number(opts?.hour) || 0;
    const drift = Number(opts?.carringtonDegPerHour) || 13.2 / 24;
    const list = Array.isArray(spots)
      ? spots.filter((p) => Number.isFinite(p?.lat) && Number.isFinite(p?.lon))
      : [];
    const canvas = emptyCanvas();
    if (!list.length) return canvas;
    const ctx = canvas.getContext("2d");
    list.forEach((p) => {
      const lon = driftedLon(p.lon, hour, drift);
      if (Math.abs(lon) > 98 && style !== "umbra") return;
      const px = lonToPx(lon, W);
      const py = latToPy(p.lat, H);
      const inten = Math.max(0.2, Math.min(1, Number(p.intensity) || 0.45));
      const area = Number(p.area);
      const areaScale = Number.isFinite(area) ? Math.min(1.8, 0.45 + area / 650) : 0.85 + inten * 0.55;
      if (style === "umbra") {
        const rFac = W * (0.038 + areaScale * 0.07);
        const rPen = rFac * 0.62;
        const rUmb = rPen * 0.4;
        [-W, 0, W].forEach((dx) => {
          const cx = px + dx;
          const fac = ctx.createRadialGradient(cx, py, rPen * 0.85, cx, py, rFac);
          fac.addColorStop(0, `rgba(255,210,90,${(0.22 * inten).toFixed(3)})`);
          fac.addColorStop(0.55, `rgba(255,160,40,${(0.14 * inten).toFixed(3)})`);
          fac.addColorStop(1, "rgba(255,140,30,0)");
          ctx.fillStyle = fac;
          ctx.beginPath();
          ctx.arc(cx, py, rFac, 0, Math.PI * 2);
          ctx.fill();
          const g = ctx.createRadialGradient(cx, py, rUmb * 0.15, cx, py, rPen);
          g.addColorStop(0, `rgba(6,2,0,${(0.96 * inten).toFixed(3)})`);
          g.addColorStop(0.38, `rgba(28,12,4,${(0.88 * inten).toFixed(3)})`);
          g.addColorStop(0.72, `rgba(70,32,8,${(0.55 * inten).toFixed(3)})`);
          g.addColorStop(1, "rgba(40,16,4,0)");
          ctx.fillStyle = g;
          ctx.beginPath();
          ctx.arc(cx, py, rPen, 0, Math.PI * 2);
          ctx.fill();
        });
      } else if (style === "flare") {
        const pal = PALETTES.Flare;
        const r = W * (0.07 + inten * 0.13);
        [-W, 0, W].forEach((dx) => {
          const cx = px + dx;
          ctx.save();
          ctx.translate(cx, py);
          ctx.scale(1.65, 0.55);
          splatBlob(ctx, 0, 0, r, pal, inten, 1.7);
          ctx.restore();
        });
      } else if (style === "cme") {
        const pal = PALETTES.CME;
        const r = W * (0.09 + inten * 0.16);
        [-W, 0, W].forEach((dx) => {
          const cx = px + dx;
          ctx.save();
          ctx.translate(cx, py);
          ctx.rotate((lon * Math.PI) / 180 * 0.15);
          ctx.scale(0.7, 1.55);
          splatBlob(ctx, 0, 0, r, pal, inten, 1.55);
          ctx.restore();
        });
      } else {
        const pal = PALETTES.SEP;
        const r = W * (0.11 + inten * 0.18);
        splatBlob(ctx, px, py, r, pal, inten, 1.45);
      }
    });
    return canvas;
  }

  function frameIndex(grid, hour) {
    const n = grid?.frames?.length || 0;
    if (!n) return 0;
    const h = Number(hour);
    if (!Number.isFinite(h)) return 0;
    return Math.min(n - 1, Math.max(0, Math.floor(((h % 24) / 24) * n)));
  }

  async function fetchGrid(force) {
    if (gridCache && !force) return gridCache;
    if (gridPromise && !force) return gridPromise;
    gridPromise = (async () => {
      try {
        const now = new Date();
        const utcHour = now.getUTCHours() + now.getUTCMinutes() / 60;
        const times = [0, 6, 12, 18].map((d) => ((utcHour + d) % 24).toFixed(2)).join(",");
        const r = await fetch(
          apiUrl("/api/hazard-grid?step=15&times=" + times + "&mode=hybrid&ml_stride=8")
        );
        if (!r.ok) throw new Error("hazard-grid " + r.status);
        gridCache = await r.json();
        global.__LIPAS_HAZ_GRID = gridCache;
        return gridCache;
      } catch (e) {
        console.warn("[LIPAS] hazard grid fetch failed", e);
        return null;
      } finally {
        gridPromise = null;
      }
    })();
    return gridPromise;
  }

  function paintHotspots(ctx, type, peaks, sev) {
    const pal = PALETTES[type] || PALETTES.Radiation;
    const intensity = Math.max(0.35, Math.min(1, sev != null ? sev : 0.55));
    const list = Array.isArray(peaks) ? peaks.filter((p) => Number.isFinite(p?.lat) && Number.isFinite(p?.lon)) : [];
    list.forEach((p, idx) => {
      const px = lonToPx(p.lon, W);
      const py = latToPy(p.lat, H);
      const rank = 1 - idx / Math.max(1, list.length - 1);
      const local = Math.max(0.3, Math.min(1, Number(p.intensity) || intensity));
      const r = W * (0.07 + local * 0.12 * (0.7 + rank * 0.45));
      splatBlob(ctx, px, py, r, pal, Math.min(1, local * 1.2), 1.45);
    });
  }

  function makeHotspotCanvas(type, peaks, sev) {
    const list = Array.isArray(peaks) ? peaks.filter((p) => Number.isFinite(p?.lat) && Number.isFinite(p?.lon)) : [];
    if (!list.length) return emptyCanvas();
    const canvas = emptyCanvas();
    paintHotspots(canvas.getContext("2d"), type, list, sev);
    return canvas;
  }

  function makeGridCanvas(type, grid, frameIdx, meta) {
    const subLon = Number(meta?.subsolarLon ?? grid?.frames?.[frameIdx | 0]?.subsolar?.lon);
    const subLat = Number(meta?.subsolarLat ?? grid?.frames?.[frameIdx | 0]?.subsolar?.lat) || 0;
    const sevHint = Number(meta?.severity);
    if (DAYSIDE_TYPES.has(type) && Number.isFinite(subLon)) {
      return makeIlluminationCanvas(type, {
        subsolarLon: subLon,
        subsolarLat: subLat,
        severity: Number.isFinite(sevHint) ? sevHint : 0.55,
      });
    }

    const channel = TYPE_CHANNEL[type] || "radiation";
    const fr = grid?.frames?.[frameIdx | 0];
    let field = fr?.fields?.[channel];
    const lats = grid?.lats;
    const lons = grid?.lons;

    if (type === "SEP" && fr?.fields?.radiation) field = fr.fields.radiation;
    if (type === "CME" && fr?.fields?.solar) field = fr.fields.solar;

    let canvas = null;
    if (DAYSIDE_SOFT.has(type) && Number.isFinite(subLon)) {
      canvas = makeIlluminationCanvas(type, {
        subsolarLon: subLon,
        subsolarLat: subLat,
        severity: Number.isFinite(sevHint) ? sevHint : 0.55,
      });
    }

    if (!field || !lats?.length || !lons?.length) {
      if (canvas) return canvas;
      if (type === "Radiation" && Number.isFinite(subLon)) {
        return makeIlluminationCanvas("Radiation", {
          subsolarLon: subLon,
          subsolarLat: subLat,
          severity: Number.isFinite(sevHint) ? sevHint : 0.4,
        });
      }
      return emptyCanvas();
    }

    const stats = fieldStats(field);
    const metaBoost =
      type === "SEP"
        ? Number(meta?.sep ?? meta?.solar ?? 0) / 6
        : type === "CME"
          ? Number(meta?.cme ?? meta?.solar ?? 0) / 6
          : 0;
    const sev = Math.max(0.35, Math.min(1, 0.4 + stats.span * 0.5 + metaBoost * 0.2));
    if (!canvas) canvas = emptyCanvas();
    const ctx = canvas.getContext("2d");

    const peaks = collectHotspots(field, lats, lons, stats, 16);
    if (!peaks.length) return canvas;

    const boost = 1 + metaBoost * 0.45;
    peaks.forEach((p, idx) => {
      const px = lonToPx(p.lon, W);
      const py = latToPy(p.lat, H);
      const rank = 1 - idx / Math.max(1, peaks.length - 1);
      const r = W * (0.06 + p.intensity * 0.15 * (0.65 + rank * 0.55));
      const alpha = 1.05 + rank * 0.4;
      splatBlob(ctx, px, py, r, PALETTES[type] || PALETTES.Radiation, Math.min(1, p.intensity * boost * (0.75 + rank * 0.5)), alpha);
    });

    return canvas;
  }

  function siteSample(grid, channel, lat, lon, frameIdx) {
    const fr = grid?.frames?.[frameIdx | 0];
    const field = fr?.fields?.[channel];
    if (!field) return null;
    return sampleField(field, grid.lats, grid.lons, lat, lon);
  }

  function normChannel(channel, v) {
    const x = Number(v);
    if (!Number.isFinite(x)) return 0.12;
    switch (channel) {
      case "radiation":
        return Math.max(0, Math.min(1, (x - 0.042) / 0.11));
      case "dust":
        return Math.max(0, Math.min(1, (x - 0.75) / 2.4));
      case "temperature":
        return Math.max(0, Math.min(1, 0.18 + Math.abs(x + 35) / 185));
      case "moonquakes":
        return Math.max(0, Math.min(1, (x - 10) / 38));
      case "micrometeorites":
        return Math.max(0, Math.min(1, (x - 0.85) / 2.2));
      case "solar":
        return Math.max(0, Math.min(1, x / 21));
      default:
        return 0.2;
    }
  }

  global.LipasHazardGrid = {
    fetchGrid,
    makeGridCanvas,
    makeHotspotCanvas,
    paintHotspots,
    makeIlluminationCanvas,
    makeMercuryFieldCanvas,
    makeSunspotCanvas,
    emptyCanvas,
    cosineMu,
    frameIndex,
    siteSample,
    normChannel,
    getGrid: () => gridCache,
  };
})(typeof window !== "undefined" ? window : globalThis);
