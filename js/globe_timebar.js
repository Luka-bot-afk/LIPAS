(function (global) {
  "use strict";

  function bind(opts) {
    const slider = document.getElementById("globeHourSlider");
    const label = document.getElementById("globeHourLabel");
    const meta = document.getElementById("globeHourMeta");
    if (!slider) {
      return { getHour: () => 0, setMeta() {} };
    }
    let hour = Number(slider.value) || 0;
    let timer = null;

    function setLabel() {
      if (label) label.textContent = hour <= 0 ? "Now" : "+" + hour + " h";
    }

    function emit() {
      hour = Number(slider.value) || 0;
      setLabel();
      if (opts && typeof opts.onChange === "function") opts.onChange(hour);
    }

    slider.addEventListener("input", () => {
      hour = Number(slider.value) || 0;
      setLabel();
      clearTimeout(timer);
      timer = setTimeout(emit, 90);
    });
    slider.addEventListener("change", emit);
    setLabel();
    return {
      getHour: () => hour,
      setMeta(text) {
        if (meta) meta.textContent = text || "";
      },
    };
  }

  async function fetchClock(body, hour) {
    const path = "/api/globe/clock?body=" + encodeURIComponent(body) + "&hour=" + encodeURIComponent(hour);
    const url = typeof global.lipasApiUrl === "function" ? global.lipasApiUrl(path) : path;
    const r = await fetch(url);
    if (!r.ok) throw new Error("clock " + r.status);
    return r.json();
  }

  global.LipasGlobeTimebar = { bind, fetchClock };
})(typeof window !== "undefined" ? window : globalThis);
