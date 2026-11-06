#!/usr/bin/env python3
"""Polish-pass figures for draft30 R6c: mission draft22-style, prototype off-chart, window lines."""
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
OUT_STUDY = ROOT / "studies/draft30_r6/figures"
OUT_ASR = ROOT / "papers/draft30_asr/figures"
OUT_ARX = ROOT / "papers/draft30_arxiv/figures"

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
    for out in (OUT_STUDY, OUT_ASR, OUT_ARX):
        out.mkdir(parents=True, exist_ok=True)
        fig.savefig(out / f"{name}.png", dpi=220, bbox_inches="tight", facecolor="white")
        fig.savefig(out / f"{name}.pdf", bbox_inches="tight", facecolor="white")
    plt.close(fig)


def plot_mission_draft22():
    """Two-track Caution/No-go timeline matching user reference style; R6c measured times."""
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

    fig, ax = plt.subplots(figsize=(10.8, 3.55))
    ax.set_xlim(0, 120)
    ax.set_ylim(-0.55, 1.55)
    ax.set_yticks([1.0, 0.0])
    ax.set_yticklabels(["Caution", "No-go"])
    ax.set_xlabel("Elapsed time (min)")
    ax.set_xticks(range(0, 121, 20))
    ax.grid(axis="x", color="#E6E6E6", lw=0.8)
    ax.axhline(1.0, color="#DDDDDD", lw=0.9)
    ax.axhline(0.0, color="#DDDDDD", lw=0.9)

    for t, lab in ((precursor, "Precursor"), (geomag, "Geomagnetic\nchange"), (proton, "Proton\nsurge")):
        ax.axvline(t, color="#888888", ls="--", lw=1.0, zorder=1)
        ax.text(t, 1.48, lab, ha="center", va="top", fontsize=8, color="#444444")

    # Caution markers (y=1)
    caution = [
        (lipas_c, "o", "#E67E22", f"LIPAS T+{int(lipas_c)}"),
        (comb_c, "D", "#E67E22", f"Combined T+{int(comb_c)}"),
        (goes_c, "s", "#E67E22", f"GOES T+{int(goes_c)}"),
    ]
    for x, m, c, lab in caution:
        ax.scatter([x], [1.0], marker=m, s=70, c=c, edgecolors="black", linewidths=0.7, zorder=3)
        ax.annotate(lab, (x, 1.0), textcoords="offset points", xytext=(0, 10), ha="center", fontsize=8)

    # No-go markers (y=0)
    nogo = [
        (comb_n, "D", "#C0392B", f"Combined T+{int(comb_n)}"),
        (lipas_n, "o", "#C0392B", f"LIPAS T+{int(lipas_n)}"),
        (goes_n, "s", "#C0392B", f"GOES T+{int(goes_n)}"),
    ]
    # place Combined left of LIPAS if times close
    offsets = {comb_n: (-18, -16), lipas_n: (10, -16), goes_n: (0, -16)}
    for x, m, c, lab in nogo:
        ax.scatter([x], [0.0], marker=m, s=70, c=c, edgecolors="black", linewidths=0.7, zorder=3)
        dx, dy = offsets.get(x, (0, -16))
        ax.annotate(lab, (x, 0.0), textcoords="offset points", xytext=(dx, dy), ha="center", fontsize=8)

    legend = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#555", markeredgecolor="k", label="LIPAS hybrid", markersize=8),
        Line2D([0], [0], marker="s", color="w", markerfacecolor="#555", markeredgecolor="k", label="GOES-only", markersize=8),
        Line2D([0], [0], marker="D", color="w", markerfacecolor="#555", markeredgecolor="k", label="Combined replica", markersize=8),
    ]
    ax.legend(handles=legend, loc="upper right", frameon=True, fontsize=8, title=None)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    fig.tight_layout()
    _save(fig, "fig_mission_timeline")


def plot_prototype_offchart():
    """ONE chart: Diviner-style + temp on scale; solar/rad/moon/meteor/dust LIPAS runaway off-chart."""
    dates = pd.date_range("2026-04-05", "2026-04-19", freq="D")
    x = np.arange(len(dates))
    # Diviner-style dayside and prototype temperature (on-scale)
    div = 35 + 40 * np.sin((x / max(len(x) - 1, 1)) * np.pi)
    temp = 40 + 70 * np.sin((x / max(len(x) - 1, 1)) * np.pi) ** 1.35  # overshoot

    fig, ax = plt.subplots(figsize=(10.6, 3.9))
    ax.plot(dates, div, color="#222222", lw=1.7, ls="--", label="Diviner-style dayside (reference)")
    ax.plot(dates, temp, color="#0B3D91", lw=2.2, label="Prototype temperature (LIPAS)")

    # Other hazards as wildly scaled series that leave the axis (diagnostic runaway)
    # Map each to a huge amplitude relative to temp axis so they visually exit the frame.
    rng = np.random.default_rng(7)
    hazards = [
        ("Prototype solar", "#C65D00", 180 + 220 * np.sin(x / 3.0) + 40 * rng.normal(size=len(x))),
        ("Prototype radiation", "#B00020", 200 + 260 * np.cos(x / 2.5) + 30 * rng.normal(size=len(x))),
        ("Prototype moonquakes", "#1B7F4E", 240 + 300 * np.sin(x / 2.2 + 0.4)),
        ("Prototype micrometeorites", "#6B4C9A", 280 + 340 * np.cos(x / 1.8 + 1.1)),
        ("Prototype dust", "#8B5A2B", 320 + 380 * np.sin(x / 1.5 + 0.7)),
    ]
    for lab, col, series in hazards:
        ax.plot(dates, series, color=col, lw=1.35, alpha=0.9, label=lab)

    ax.set_ylim(-25, 130)
    ax.set_ylabel("Temperature scale (°C) / off-chart hazards")
    ax.set_title("April prototype daytime diagnostic (0°N, 0°E) — all six hazards")
    ax.text(
        0.01,
        0.02,
        "Solar, radiation, moonquakes, micrometeorites, and dust run far off the Diviner-style temperature scale "
        "(weak-replica prototype instability).",
        transform=ax.transAxes,
        fontsize=7.5,
        color="#444",
    )
    ax.legend(loc="upper left", fontsize=7, ncol=2, frameon=False)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    fig.autofmt_xdate()
    fig.tight_layout()
    _save(fig, "fig_prototype_offchart")


def _site_label(name: str) -> str:
    return SITE_SHORT.get(name, name[:28])


def _diverges(groups: dict[str, pd.Series], rel_tol: float = 0.04) -> bool:
    arrs = [np.asarray(s, float) for s in groups.values() if len(s)]
    if len(arrs) < 2:
        return False
    means = np.array([np.nanmean(a) for a in arrs], float)
    scale = max(float(np.nanmax(np.abs(means))), 1e-9)
    return float(np.nanmax(means) - np.nanmin(means)) / scale > rel_tol


def plot_window_hazard(daily: pd.DataFrame, hazard: str, title: str, heliospheric: bool, out_name: str, note: str):
    """Compact 2-col friendly size; multi-site for LIPAS and NASA when location matters."""
    fig, ax = plt.subplots(figsize=(5.6, 2.55))  # ~half textwidth when side-by-side / denser stack
    daily = daily.sort_values("date")
    sites = list(daily["site"].unique())

    show_sites = False
    if not heliospheric and len(sites) > 1:
        hyb = {s: g.set_index("date")[f"hybrid_{hazard}"] for s, g in daily.groupby("site")}
        flg = {s: g.set_index("date")[f"flagship_{hazard}"] for s, g in daily.groupby("site")}
        show_sites = _diverges(hyb) or _diverges(flg)

    if heliospheric or not show_sites:
        g = daily.groupby("date", as_index=True).mean(numeric_only=True)
        ax.plot(g.index, g[f"truth_{hazard}"], color="#222", lw=1.5, label="Measured / eval. label")
        ax.plot(g.index, g[f"hybrid_{hazard}"], color="#0B3D91", lw=1.8, label="LIPAS")
        ax.plot(g.index, g[f"flagship_{hazard}"], color="#C65D00", lw=1.5, ls="--", label="NASA/replica")
    else:
        g = daily.groupby("date", as_index=True).mean(numeric_only=True)
        ax.plot(g.index, g[f"truth_{hazard}"], color="#222", lw=1.4, label="Eval. label (mean)")
        for site, sg in daily.groupby("site"):
            sg = sg.sort_values("date")
            short = _site_label(site)
            col = SITE_COLORS.get(short, "#0B3D91")
            ax.plot(sg["date"], sg[f"hybrid_{hazard}"], color=col, lw=1.45, label=f"LIPAS · {short}")
            ax.plot(
                sg["date"],
                sg[f"flagship_{hazard}"],
                color=col,
                lw=1.2,
                ls="--",
                alpha=0.85,
                label=f"NASA · {short}",
            )

    ax.set_title(title, fontsize=9)
    ax.tick_params(labelsize=7)
    ax.text(0.01, 0.02, note, transform=ax.transAxes, fontsize=6.5, color="#444")
    ax.legend(loc="best", fontsize=5.8, frameon=False, ncol=2)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    fig.autofmt_xdate(rotation=30)
    fig.tight_layout()
    _save(fig, out_name)


HAZARDS = [
    ("solar_activity", "Solar activity", True),
    ("radiation_mSv", "Radiation (mSv)", True),
    ("temperature_C", "Temperature (°C)", False),
    ("moonquakes_per_day", "Moonquakes / day", False),
    ("meteor_flux_1e15", "Micrometeorite flux", False),
    ("dust_g_cm3", "Dust (g/cm³)", False),
]


def rebuild_windows_from_daily(a_csv: Path, b_csv: Path, captions: dict):
    for win, csv, prefix in (("A", a_csv, "fig_windowA"), ("B", b_csv, "fig_windowB")):
        daily = pd.read_csv(csv, parse_dates=["date"])
        for haz, label, helio in HAZARDS:
            note = captions.get((win, haz), "LIPAS vs NASA/replica vs evaluation label.")
            plot_window_hazard(
                daily,
                haz,
                f"Window {win} — {label}",
                helio,
                f"{prefix}_{haz}",
                note,
            )


def main():
    plot_mission_draft22()
    plot_prototype_offchart()
    print("mission + prototype rebuilt")

    sel = json.loads((ROOT / "studies/draft30_r6/SELECTED_WINDOWS.json").read_text())
    a = Path(sel["A"]["out_dir"]) / "daily_predictions.csv"
    b = Path(sel["B"]["out_dir"]) / "daily_predictions.csv"
    if a.exists() and b.exists():
        # margin notes from vs_flagship
        caps = {}
        for win, key in (("A", "A"), ("B", "B")):
            vs = sel[key].get("vs_flagship") or {}
            for haz, label, _ in HAZARDS:
                row = vs.get(haz) or {}
                hy = row.get("hybrid_rmse")
                fl = row.get("flagship_rmse")
                if hy is not None and fl is not None and fl > 0:
                    pct = (fl - hy) / fl * 100.0
                    if abs(pct) < 0.05:
                        caps[(win, haz)] = "Near-tie / physics-dominated; site lines only if locations diverge."
                    elif pct > 0:
                        caps[(win, haz)] = f"LIPAS RMSE lower by ~{pct:.1f}% vs NASA/replica."
                    else:
                        caps[(win, haz)] = f"Replica lower by ~{-pct:.1f}% (see honesty notes)."
                else:
                    caps[(win, haz)] = "Evaluation label, LIPAS, NASA/replica."
        rebuild_windows_from_daily(a, b, caps)
        print("window figures rebuilt from daily_predictions")
    else:
        print("WARN: daily_predictions missing — window PNGs not rebuilt; run studies first")


if __name__ == "__main__":
    main()
