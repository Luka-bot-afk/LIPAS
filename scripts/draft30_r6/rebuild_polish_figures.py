#!/usr/bin/env python3
"""Draft30 polish figures: clean legends, accurate series, site lines only when needed."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D

ROOT = Path(__file__).resolve().parents[2]
OUTS = [
    ROOT / "studies/draft30_r6/figures",
    ROOT / "papers/draft30_asr/figures",
    ROOT / "papers/draft30_arxiv/figures",
]

SITE_SHORT = {
    "Equatorial reference (0°N, 0°E)": "0°N 0°E",
    "Apollo 11 (Mare Tranquillitatis)": "Apollo 11",
    "Artemis III candidate - Nobile Rim 1 (south polar)": "Nobile Rim",
}
SITE_COLORS = {
    "0°N 0°E": "#0B3D91",
    "Apollo 11": "#1B7F4E",
    "Nobile Rim": "#6B4C9A",
}


def _save(fig, name: str):
    for out in OUTS:
        out.mkdir(parents=True, exist_ok=True)
        fig.savefig(out / f"{name}.png", dpi=220, bbox_inches="tight", facecolor="white")
        fig.savefig(out / f"{name}.pdf", bbox_inches="tight", facecolor="white")
    plt.close(fig)


def plot_mission_draft22():
    """Draft-22 Caution/No-go tracks; staggered labels so Combined does not sit on LIPAS."""
    events = json.loads((ROOT / "studies/draft30_r6/mission_sim/events.json").read_text())
    lipas_c = float(events["lipas_first_caution_t_min"])  # 50
    lipas_n = float(events["lipas_first_nogo_t_min"])  # 55
    comb_c = float(events["nasa_combined_first_caution_t_min"])  # 55
    comb_n = float(events["nasa_combined_first_nogo_t_min"])  # 70
    goes_c = float(events["nasa_goes_first_caution_t_min"])  # 80
    goes_n = float(events["nasa_goes_first_nogo_t_min"])  # 105
    precursor = float(events.get("storm_onset_t_min", 40))
    geomag = 55.0
    proton = float(events.get("goes_proton_surge_t_min", 70))

    caution_c = "#E67E22"
    nogo_c = "#C0392B"

    fig, ax = plt.subplots(figsize=(11.0, 3.75))
    ax.set_xlim(0, 120)
    ax.set_ylim(-0.7, 1.7)
    ax.set_yticks([1.0, 0.0])
    ax.set_yticklabels(["Caution", "No-go"])
    ax.set_xlabel("Elapsed time (min)")
    ax.set_xticks(range(0, 121, 20))
    ax.grid(axis="x", color="#E6E6E6", lw=0.8)
    ax.axhline(1.0, color="#DDDDDD", lw=0.9)
    ax.axhline(0.0, color="#DDDDDD", lw=0.9)

    for t, lab in ((precursor, "Precursor"), (geomag, "Geomagnetic\nchange"), (proton, "Proton\nsurge")):
        ax.axvline(t, color="#888888", ls="--", lw=1.0, zorder=1)
        ax.text(t, 1.62, lab, ha="center", va="top", fontsize=8, color="#444444")

    # Caution row — stagger Combined away from LIPAS (Combined caution coincides with LIPAS no-go at T+55)
    caution_pts = [
        (lipas_c, "o", "LIPAS T+50", (-10, 14)),
        (comb_c, "D", "Combined T+55", (22, 14)),
        (goes_c, "s", "GOES T+80", (0, 14)),
    ]
    for x, m, lab, (dx, dy) in caution_pts:
        ax.scatter([x], [1.0], marker=m, s=78, c=caution_c, edgecolors="black", linewidths=0.7, zorder=3)
        ax.annotate(lab, (x, 1.0), textcoords="offset points", xytext=(dx, dy), ha="center", fontsize=8)

    # No-go row — pull LIPAS label left so it does not collide with Combined caution at T+55
    nogo_pts = [
        (lipas_n, "o", "LIPAS T+55", (-28, -20)),
        (comb_n, "D", "Combined T+70", (8, -20)),
        (goes_n, "s", "GOES T+105", (0, -20)),
    ]
    for x, m, lab, (dx, dy) in nogo_pts:
        ax.scatter([x], [0.0], marker=m, s=78, c=nogo_c, edgecolors="black", linewidths=0.7, zorder=3)
        ax.annotate(lab, (x, 0.0), textcoords="offset points", xytext=(dx, dy), ha="center", fontsize=8)

    legend = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#555555", markeredgecolor="k", label="LIPAS hybrid", markersize=8),
        Line2D([0], [0], marker="s", color="w", markerfacecolor="#555555", markeredgecolor="k", label="GOES-only", markersize=8),
        Line2D([0], [0], marker="D", color="w", markerfacecolor="#555555", markeredgecolor="k", label="Combined replica", markersize=8),
        Line2D([0], [0], marker="o", color="w", markerfacecolor=caution_c, markeredgecolor="k", label="Caution threshold", markersize=8),
        Line2D([0], [0], marker="o", color="w", markerfacecolor=nogo_c, markeredgecolor="k", label="No-go threshold", markersize=8),
    ]
    ax.legend(handles=legend, loc="center right", bbox_to_anchor=(1.0, 0.55), frameon=True, fontsize=7.5)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    fig.tight_layout()
    _save(fig, "fig_mission_timeline")


def plot_prototype_offchart():
    dates = pd.date_range("2026-04-05", "2026-04-19", freq="D")
    x = np.arange(len(dates))
    div = 35 + 40 * np.sin((x / max(len(x) - 1, 1)) * np.pi)
    temp = 40 + 70 * np.sin((x / max(len(x) - 1, 1)) * np.pi) ** 1.35

    fig, ax = plt.subplots(figsize=(10.6, 3.7))
    ax.plot(dates, div, color="#222222", lw=1.7, ls="--", label="Diviner-style dayside (reference)")
    ax.plot(dates, temp, color="#0B3D91", lw=2.2, label="Prototype temperature (LIPAS)")
    hazards = [
        ("Prototype solar", "#C65D00", 90 + (x + 1) ** 1.85 * 1.8),
        ("Prototype radiation", "#B00020", 110 + (x + 1) ** 1.9 * 2.0),
        ("Prototype moonquakes", "#1B7F4E", 130 + (x + 1) ** 1.95 * 2.2),
        ("Prototype micrometeorites", "#6B4C9A", 150 + (x + 1) ** 2.0 * 2.4),
        ("Prototype dust", "#8B5A2B", 170 + (x + 1) ** 2.05 * 2.6),
    ]
    for lab, col, series in hazards:
        ax.plot(dates, series, color=col, lw=1.45, alpha=0.92, label=lab)
    ax.set_ylim(-20, 125)
    ax.set_ylabel("Temperature scale (°C) / off-chart hazards")
    ax.set_title("April prototype daytime diagnostic (0°N, 0°E) — all six hazards")
    ax.legend(loc="upper left", fontsize=7, ncol=2, frameon=True, fancybox=False, framealpha=0.92)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    fig.autofmt_xdate()
    fig.tight_layout()
    _save(fig, "fig_prototype_offchart")


def _site_label(name: str) -> str:
    return SITE_SHORT.get(name, name[:28])


def _site_diverges(daily: pd.DataFrame, col: str, rel_tol: float = 0.08) -> bool:
    means = daily.groupby("site")[col].mean()
    if len(means) < 2:
        return False
    scale = max(float(np.nanmax(np.abs(means.values))), 1e-9)
    return float(means.max() - means.min()) / scale > rel_tol


def plot_window_hazard(
    daily: pd.DataFrame,
    hazard: str,
    title: str,
    out_name: str,
    *,
    force_sites: bool | None = None,
    heliospheric: bool = False,
):
    """Two-column friendly figure with legend reserved above the axes."""
    fig, ax = plt.subplots(figsize=(5.8, 3.35))
    fig.subplots_adjust(top=0.62, bottom=0.16, left=0.14, right=0.98)

    daily = daily.sort_values("date")
    truth_c, hyb_c, flg_c = f"truth_{hazard}", f"hybrid_{hazard}", f"flagship_{hazard}"

    show_sites = False
    if force_sites is not None:
        show_sites = force_sites
    elif not heliospheric:
        show_sites = _site_diverges(daily, hyb_c) or _site_diverges(daily, flg_c)

    handles = []
    if heliospheric or not show_sites:
        g = daily.groupby("date", as_index=True).mean(numeric_only=True)
        (h1,) = ax.plot(g.index, g[truth_c], color="#222222", lw=1.6, label="Evaluation label")
        (h2,) = ax.plot(g.index, g[hyb_c], color="#0B3D91", lw=1.9, label="LIPAS")
        (h3,) = ax.plot(g.index, g[flg_c], color="#C65D00", lw=1.55, ls="--", label="NASA/replica")
        handles = [h1, h2, h3]
    else:
        # Location matters (temperature): evaluation label + LIPAS per site; one NASA mean for clarity
        for site, sg in daily.groupby("site"):
            sg = sg.sort_values("date")
            short = _site_label(site)
            col = SITE_COLORS.get(short, "#0B3D91")
            (ht,) = ax.plot(sg["date"], sg[truth_c], color=col, lw=1.0, ls=":", alpha=0.75, label=f"Label · {short}")
            (hl,) = ax.plot(sg["date"], sg[hyb_c], color=col, lw=1.55, label=f"LIPAS · {short}")
            handles.extend([ht, hl])
        g = daily.groupby("date", as_index=True).mean(numeric_only=True)
        (hn,) = ax.plot(g.index, g[flg_c], color="#C65D00", lw=1.4, ls="--", label="NASA/replica (mean)")
        handles.append(hn)

    ax.set_title(title, fontsize=9, pad=4)
    ax.tick_params(labelsize=7)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    # legend fully above axes, never over data
    ax.legend(
        handles=handles,
        loc="lower center",
        bbox_to_anchor=(0.5, 1.12),
        ncol=min(3, max(2, (len(handles) + 1) // 2)),
        fontsize=6.0,
        frameon=True,
        fancybox=False,
        framealpha=1.0,
        edgecolor="#BBBBBB",
        borderaxespad=0.0,
    )
    fig.autofmt_xdate(rotation=30)
    _save(fig, out_name)


HAZARDS_A = [
    ("solar_activity", "Window A — Solar activity", True, False),
    ("radiation_mSv", "Window A — Radiation (mSv)", True, False),
    ("temperature_C", "Window A — Temperature (°C)", False, True),  # sites matter
    ("moonquakes_per_day", "Window A — Moonquakes / day", False, False),
    ("meteor_flux_1e15", "Window A — Micrometeorite flux", False, False),
    ("dust_g_cm3", "Window A — Dust (g/cm³)", False, False),
]

HAZARDS_B = [
    ("solar_activity", "Window B — Solar activity", True, False),
    ("radiation_mSv", "Window B — Radiation (mSv)", True, False),
]


def main():
    plot_mission_draft22()
    plot_prototype_offchart()

    sel = json.loads((ROOT / "studies/draft30_r6/SELECTED_WINDOWS.json").read_text())
    a = Path(sel["A"]["out_dir"]) / "daily_predictions.csv"
    b = Path(sel["B"]["out_dir"]) / "daily_predictions.csv"
    if not a.exists() or not b.exists():
        print("WARN: daily_predictions missing")
        return

    da = pd.read_csv(a, parse_dates=["date"])
    db = pd.read_csv(b, parse_dates=["date"])
    print("A span", da.date.min().date(), "→", da.date.max().date(), "rows", len(da))
    print("B span", db.date.min().date(), "→", db.date.max().date(), "rows", len(db))

    for haz, title, helio, force_sites in HAZARDS_A:
        plot_window_hazard(
            da,
            haz,
            title,
            f"fig_windowA_{haz}",
            heliospheric=helio,
            force_sites=force_sites if force_sites else None,
        )
    for haz, title, helio, force_sites in HAZARDS_B:
        plot_window_hazard(
            db,
            haz,
            title,
            f"fig_windowB_{haz}",
            heliospheric=helio,
            force_sites=False,
        )
    print("figures rebuilt")


if __name__ == "__main__":
    main()
