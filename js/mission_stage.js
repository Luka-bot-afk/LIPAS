(function () {
  "use strict";

  const canvas = document.getElementById("mp-stage");
  if (!canvas) return;
  const readout = document.getElementById("mp-stage-readout");

  function num(id, fallback) {
    const n = Number(document.getElementById(id)?.value);
    return Number.isFinite(n) ? n : fallback;
  }

  function hazards() {
    return [...document.querySelectorAll("#hz-grid .hz-cell")].map((cell) => {
      const cls = cell.classList.contains("nogo") ? "nogo" : cell.classList.contains("caution") ? "caution" : cell.classList.contains("go") ? "go" : "idle";
      return { label: cell.querySelector(".hk")?.textContent || "", cls };
    });
  }

  function tone(cls) {
    if (cls === "nogo") return "#e25b5b";
    if (cls === "caution") return "#e0b14a";
    if (cls === "go") return "#3ecf8e";
    return "#8aa0b4";
  }

  function draw() {
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const w = Math.max(320, canvas.clientWidth || 640);
    const h = 220;
    canvas.width = Math.floor(w * dpr);
    canvas.height = Math.floor(h * dpr);
    canvas.style.height = h + "px";
    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const light = document.documentElement.dataset.theme === "light";
    ctx.fillStyle = light ? "#f7f4ee" : "#12161e";
    ctx.fillRect(0, 0, w, h);

    const site = document.getElementById("inp-site")?.value || "Site";
    const eva = Math.max(1, Math.min(12, num("inp-eva-dur", 4)));
    const perDay = Math.max(0, Math.min(12, num("inp-eva-day", 4)));
    const days = Math.max(1, Math.min(180, num("inp-mission-days", 14)));
    const lat = num("inp-lat", -89.68);
    const lst = ((new Date().getUTCHours() + num("inp-lon", 0) / 15) % 24 + 24) % 24;
    const start = (lst + 2) % 24;
    const hz = hazards();
    const worst = hz.some((item) => item.cls === "nogo") ? "NO-GO" : hz.some((item) => item.cls === "caution") ? "CAUTION" : hz.some((item) => item.cls === "go") ? "GO" : "STANDBY";

    ctx.fillStyle = light ? "#1a1916" : "#f4f7fb";
    ctx.font = "600 15px Outfit, IBM Plex Sans, sans-serif";
    ctx.fillText(site.slice(0, 36), 16, 26);
    ctx.font = "12px IBM Plex Sans, sans-serif";
    ctx.fillStyle = light ? "#5c564c" : "#8fa3b8";
    ctx.fillText(`${eva} h EVA · ${perDay} h/day · ${days} days · ${lat.toFixed(1)}°`, 16, 46);

    const left = 16;
    const right = w - 16;
    const top = 68;
    const rowH = 28;
    const span = right - left;
    ctx.font = "11px IBM Plex Sans, sans-serif";
    for (let hour = 0; hour < 24; hour += 3) {
      const x = left + (hour / 24) * span;
      ctx.fillStyle = light ? "#8a8176" : "#6d7d90";
      ctx.fillText(String(hour).padStart(2, "0"), x, top - 8);
    }

    function band(y, label, a, b, fill) {
      ctx.fillStyle = light ? "#1a1916" : "#d5deea";
      ctx.fillText(label, left, y - 6);
      const y0 = y;
      ctx.fillStyle = light ? "#e7e1d6" : "#1c2430";
      round(ctx, left, y0, span, 16, 8);
      ctx.fill();
      const x0 = left + (a / 24) * span;
      const width = Math.max(8, ((b - a) / 24) * span);
      ctx.fillStyle = fill;
      round(ctx, x0, y0, Math.min(width, right - x0), 16, 8);
      ctx.fill();
    }

    const sunA = (6 - lst + 24) % 24;
    band(top + 18, "Sunlight", sunA, Math.min(24, sunA + 12), light ? "#f0d48a" : "#e0b14a");
    const evaEnd = Math.min(24, start + eva);
    band(top + 18 + rowH + 16, "This EVA", start, evaEnd, worst === "NO-GO" ? "#e25b5b" : worst === "CAUTION" ? "#e0b14a" : "#3ecf8e");

    const dose = (0.04 * perDay * days).toFixed(2);
    ctx.fillStyle = light ? "#1a1916" : "#f4f7fb";
    ctx.font = "600 13px Outfit, IBM Plex Sans, sans-serif";
    ctx.fillText(`${worst}  ·  crew dose sketch ${dose} mSv`, left, h - 18);

    hz.filter((item) => item.cls !== "idle").slice(0, 4).forEach((item, i) => {
      const x = right - 18 - i * 22;
      ctx.beginPath();
      ctx.arc(x, h - 22, 6, 0, Math.PI * 2);
      ctx.fillStyle = tone(item.cls);
      ctx.fill();
    });

    if (readout) readout.textContent = `${site} · EVA ${fmtHour(start)}–${fmtHour(evaEnd)} · ${worst} · ${dose} mSv over ${days} d`;
  }

  function fmtHour(h) {
    const x = ((h % 24) + 24) % 24;
    return `${String(Math.floor(x)).padStart(2, "0")}:00`;
  }

  function round(ctx, x, y, w, h, r) {
    const radius = Math.min(r, w / 2, h / 2);
    ctx.beginPath();
    ctx.moveTo(x + radius, y);
    ctx.arcTo(x + w, y, x + w, y + h, radius);
    ctx.arcTo(x + w, y + h, x, y + h, radius);
    ctx.arcTo(x, y + h, x, y, radius);
    ctx.arcTo(x, y, x + w, y, radius);
    ctx.closePath();
  }

  function loop() {
    draw();
    requestAnimationFrame(loop);
  }
  draw();
  window.addEventListener("resize", draw);
  window.addEventListener("lipas-theme-change", draw);
  ["inp-lat", "inp-lon", "inp-site", "inp-eva-dur", "inp-eva-day", "inp-mission-days"].forEach((id) => {
    document.getElementById(id)?.addEventListener("input", draw);
  });
  const grid = document.getElementById("hz-grid");
  if (grid && window.MutationObserver) {
    new MutationObserver(draw).observe(grid, { subtree: true, attributes: true, childList: true });
  }
  if (!window.matchMedia("(prefers-reduced-motion: reduce)").matches) loop();
})();
