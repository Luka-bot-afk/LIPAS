(function () {
  "use strict";

  function readMetaBase() {
    const m = document.querySelector('meta[name="lipas-api-base"]');
    if (!m || !m.content) return "";
    return String(m.content).trim().replace(/\/$/, "");
  }

  function storedBase() {
    try {
      return (localStorage.getItem("lipas_api_base") || "").trim().replace(/\/$/, "");
    } catch (_) {
      return "";
    }
  }

  const API_BASE = readMetaBase() || storedBase();
  window.LIPAS_API_BASE = API_BASE;

  window.lipasApiUrl = function lipasApiUrl(path) {
    const p = path.startsWith("/") ? path : `/${path}`;
    return API_BASE ? `${API_BASE}${p}` : p;
  };

  window.lipasHasBackend = function lipasHasBackend() {
    return !!API_BASE;
  };

  window.lipasSetApiBase = function lipasSetApiBase(url) {
    const clean = String(url || "").trim().replace(/\/$/, "");
    try {
      if (clean) localStorage.setItem("lipas_api_base", clean);
      else localStorage.removeItem("lipas_api_base");
    } catch (_) {}
    window.LIPAS_API_BASE = clean;
    location.reload();
  };
})();
