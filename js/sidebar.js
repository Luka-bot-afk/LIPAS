(function () {
  "use strict";

  const sidebar = document.getElementById("sidebar");
  const overlay = document.getElementById("sidebarOverlay");
  const openTab = document.getElementById("sidebarOpenTab");
  const resizeHandle = document.getElementById("sidebarResizeHandle");
  if (!sidebar) return;

  const MIN_W = 240;
  const MAX_W = Math.min(520, Math.round(window.innerWidth * 0.92));
  const MOBILE_MQ = window.matchMedia("(max-width: 768px)");

  function isMobile() {
    return MOBILE_MQ.matches;
  }

  function setHidden(hidden) {
    if (!isMobile()) {
      sidebar.classList.remove("hidden");
      overlay?.classList.remove("visible");
      openTab?.classList.remove("visible");
      sidebar.style.transform = "";
      return;
    }
    sidebar.classList.toggle("hidden", hidden);
    overlay?.classList.toggle("visible", !hidden);
    openTab?.classList.toggle("visible", hidden);
    document.body.classList.toggle("sidebar-closed", hidden);
    if (!hidden) sidebar.style.transform = "";
  }

  function setWidth(px) {
    const max = Math.min(520, Math.round(window.innerWidth * 0.92));
    const w = Math.max(MIN_W, Math.min(max, px));
    sidebar.style.width = w + "px";
    sidebar.style.flexBasis = w + "px";
    sidebar.style.maxWidth = w + "px";
    try {
      localStorage.setItem("lipas-sidebar-w", String(w));
    } catch (e) {}
  }

  function restoreWidth() {
    let w = 320;
    try {
      const saved = Number(localStorage.getItem("lipas-sidebar-w"));
      if (Number.isFinite(saved)) w = saved;
    } catch (e) {}
    setWidth(w);
  }

  restoreWidth();
  if (isMobile()) setHidden(false);

  openTab?.addEventListener("click", () => setHidden(false));
  overlay?.addEventListener("click", () => setHidden(true));

  MOBILE_MQ.addEventListener("change", () => {
    if (!isMobile()) {
      overlay?.classList.remove("visible");
      openTab?.classList.remove("visible");
      sidebar.classList.remove("hidden");
      sidebar.style.transform = "";
    } else if (sidebar.classList.contains("hidden")) {
      openTab?.classList.add("visible");
    }
  });

  /* ── Resize handle ── */
  if (resizeHandle) {
    let resizing = false;
    let startX = 0;
    let startW = 0;

    const onResizeMove = (clientX) => {
      if (!resizing) return;
      setWidth(startW + (clientX - startX));
    };

    const stopResize = () => {
      resizing = false;
      sidebar.classList.remove("resizing");
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerup", stopResize);
      window.removeEventListener("pointercancel", stopResize);
    };

    const onPointerMove = (e) => onResizeMove(e.clientX);

    resizeHandle.addEventListener("pointerdown", (e) => {
      resizing = true;
      startX = e.clientX;
      startW = sidebar.getBoundingClientRect().width;
      sidebar.classList.add("resizing");
      document.body.style.cursor = "ew-resize";
      document.body.style.userSelect = "none";
      resizeHandle.setPointerCapture?.(e.pointerId);
      window.addEventListener("pointermove", onPointerMove);
      window.addEventListener("pointerup", stopResize);
      window.addEventListener("pointercancel", stopResize);
      e.preventDefault();
    });
  }

  /* ── Drag to close (mobile) ── */
  let dragX = 0;
  let dragging = false;
  let dragStartX = 0;
  let dragStartTx = 0;

  const dragZone = sidebar.querySelector(".sidebar-drag-zone") || sidebar;

  const onDragMove = (clientX) => {
    if (!dragging || !isMobile()) return;
    dragX = Math.min(0, clientX - dragStartX);
    sidebar.style.transform = `translateX(${dragStartTx + dragX}px)`;
  };

  const stopDrag = () => {
    if (!dragging) return;
    dragging = false;
    sidebar.classList.remove("dragging");
    const w = sidebar.getBoundingClientRect().width;
    if (dragX < -w * 0.28) {
      sidebar.style.transform = "";
      setHidden(true);
    } else {
      sidebar.style.transform = "";
    }
    dragX = 0;
    window.removeEventListener("pointermove", onDragPointerMove);
    window.removeEventListener("pointerup", stopDrag);
    window.removeEventListener("pointercancel", stopDrag);
  };

  const onDragPointerMove = (e) => onDragMove(e.clientX);

  dragZone.addEventListener("pointerdown", (e) => {
    if (!isMobile()) return;
    if (e.target.closest(".sidebar-resize-handle, .search-bar, .location-list, input, button, a")) return;
    dragging = true;
    dragStartX = e.clientX;
    dragStartTx = 0;
    sidebar.classList.add("dragging");
    window.addEventListener("pointermove", onDragPointerMove);
    window.addEventListener("pointerup", stopDrag);
    window.addEventListener("pointercancel", stopDrag);
  });

  window.lipasSidebar = { open: () => setHidden(false), close: () => setHidden(true), toggle: () => setHidden(!sidebar.classList.contains("hidden")) };
})();
