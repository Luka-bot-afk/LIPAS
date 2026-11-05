#!/usr/bin/env python3
"""Regenerate draft27 result figures: combined summer Window AB + storm Window C28."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch

ROOT = Path("/Users/lukatakki/Documents/L.I.P.A.S. V3")
OUTS = [
    ROOT / "papers/draft27_asr/figures",
    ROOT / "papers/draft27_arxiv/figures",
]
AB_CSV = ROOT / "logs/overnight_improve/final_v3/window_AB/daily_predictions.csv"
C_CSV = ROOT / "logs/overnight_improve/final_v3/window_C28/daily_predictions.csv"
EVENTS = ROOT / "logs/overnight_improve/mission_sim/events.json"
NAVY = "#1e3a5f"
ORANGE = "#c45c26"
GREEN = "#2f5d50"
PURPLE = "#5b4a8a"
SITE_SHORT = {"0N0E": "E", "Apollo11": "A", "NobileRim": "N", "0°N 0°E": "E", "Apollo 11": "A", "Nobile Rim": "N"}

HAZARDS_PLOT = [
    ("temperature_C", "Temperature"),
    ("radiation_mSv", "Radiation"),
    ("meteor_flux_1e15", "Micrometeorites"),
    ("moonquakes_per_day", "Moonquakes"),
    ("dust_g_cm3", "Dust"),
    ("solar_activity", "Solar Activity"),
]


def _save(fig, name: str) -> None:
    for out in OUTS:
        out.mkdir(parents=True, exist_ok=True)
        path = out / name
        fig.savefig(path, dpi=220, bbox_inches="tight", facecolor="white")
        print("wrote", path)
    plt.close(fig)


def _site_key(site: str) -> str:
    if site in SITE_SHORT:
        return SITE_SHORT[site]
    s = str(site)
    if "Apollo" in s:
        return "A"
    if "Nobile" in s:
        return "N"
    if "0" in s and "N" in s:
        return "E"
    return s[:1]


def skill_figure(df: pd.DataFrame, title: str, out_name: str, also_dir: Path | None = None) -> dict:
    site_short = {}
    for site in df["site"].unique():
        site_short[site] = _site_key(site)
    per_site: dict = {}
    for hkey, _ in HAZARDS_PLOT:
        per_site[hkey] = {}
        site_rmses = {}
        for site, g in df.groupby("site"):
            hy = float(np.sqrt(np.mean((g[f"hybrid_{hkey}"] - g[f"truth_{hkey}"]) ** 2)))
            fl = float(np.sqrt(np.mean((g[f"flagship_{hkey}"] - g[f"truth_{hkey}"]) ** 2)))
            site_rmses[site] = {"hybrid": hy, "flagship": fl}
        scale = max([v["hybrid"] for v in site_rmses.values()] + [v["flagship"] for v in site_rmses.values()] + [1e-9])
        for site, rms in site_rmses.items():
            key = site_short[site]
            per_site[hkey][key] = {
                "hybrid_rmse": rms["hybrid"],
                "flagship_rmse": rms["flagship"],
                "hybrid_skill": float(96.0 * max(0.0, 1.0 - rms["hybrid"] / scale)),
                "flagship_skill": float(96.0 * max(0.0, 1.0 - rms["flagship"] / scale)),
            }

    sites_order = ["E", "A", "N"]
    n_h = len(HAZARDS_PLOT)
    group_gap = 0.55
    bar_w = 0.12
    fig, ax = plt.subplots(figsize=(12.5, 5.4))
    for hi, (hkey, _hlabel) in enumerate(HAZARDS_PLOT):
        base = hi * (6 * bar_w + group_gap)
        for si, sid in enumerate(sites_order):
            hv = float(per_site[hkey][sid]["hybrid_skill"])
            fv = float(per_site[hkey][sid]["flagship_skill"])
            hv_draw = max(hv, 0.8)
            fv_draw = max(fv, 0.8)
            ax.bar(
                base + si * bar_w,
                hv_draw,
                bar_w * 0.92,
                color=NAVY,
                edgecolor="white",
                linewidth=0.6,
                label="L.I.P.A.S." if hi == 0 and si == 0 else None,
            )
            ax.bar(
                base + (3 + si) * bar_w,
                fv_draw,
                bar_w * 0.92,
                color="#e07a3d",
                edgecolor="white",
                linewidth=0.6,
                label="Flagship" if hi == 0 and si == 0 else None,
            )
            ax.text(base + si * bar_w, hv_draw + 1.2, sid, ha="center", va="bottom", fontsize=8, color=NAVY, fontweight="bold")
            ax.text(
                base + (3 + si) * bar_w,
                fv_draw + 1.2,
                sid,
                ha="center",
                va="bottom",
                fontsize=8,
                color="#e07a3d",
                fontweight="bold",
            )
    ax.set_ylim(0, 105)
    ax.set_ylabel("Absolute skill from site RMSE (96 = zero error; not % accuracy)")
    ax.set_title(title)
    ax.set_xticks([i * (6 * bar_w + group_gap) + 3 * bar_w for i in range(n_h)])
    ax.set_xticklabels([lab for _, lab in HAZARDS_PLOT])
    ax.legend(
        handles=[Patch(facecolor=NAVY, label="L.I.P.A.S."), Patch(facecolor="#e07a3d", label="Flagship")],
        loc="upper right",
    )
    ax.text(0.01, 0.98, "E = 0°N 0°E   A = Apollo 11   N = Nobile Rim", transform=ax.transAxes, va="top", fontsize=9)
    fig.tight_layout()
    _save(fig, out_name)
    if also_dir is not None:
        also_dir.mkdir(parents=True, exist_ok=True)
        # re-render once into also_dir via copy of last saved
        src = OUTS[0] / out_name
        (also_dir / "skill_by_site.png").write_bytes(src.read_bytes())
    return per_site


def radiation_ab() -> None:
    df = pd.read_csv(AB_CSV, parse_dates=["date"])
    g = (
        df.groupby("date", as_index=False)
        .agg(
            truth=("truth_radiation_mSv", "mean"),
            hybrid=("hybrid_radiation_mSv", "mean"),
            flagship=("flagship_radiation_mSv", "mean"),
        )
        .sort_values("date")
    )
    fig, ax = plt.subplots(figsize=(7.6, 3.3))
    ax.plot(g["date"], g["truth"], "o-", color=ORANGE, lw=1.6, ms=4.0, label="Observed labels")
    ax.plot(g["date"], g["hybrid"], "o-", color=PURPLE, lw=1.6, ms=4.0, label="L.I.P.A.S.")
    ax.plot(g["date"], g["flagship"], "o-", color=GREEN, lw=1.6, ms=4.0, label="GOES + physics")
    # mark gap
    ax.axvspan(pd.Timestamp("2026-07-15"), pd.Timestamp("2026-07-17"), color="#ddd", alpha=0.7, label="15–17 Jul gap")
    ax.set_title("Summer Window S radiation (17 Jun – 4 Aug 2026)", fontsize=11)
    ax.set_ylabel("Radiation (mSv)")
    ax.grid(True, alpha=0.25)
    ax.legend(frameon=False, fontsize=8)
    fig.autofmt_xdate(rotation=30, ha="right")
    fig.tight_layout()
    _save(fig, "fig_windowS_radiation.png")


def meteors_ab() -> None:
    df = pd.read_csv(AB_CSV, parse_dates=["date"])
    # Perseids sit in the July–August sub-interval; plot full summer for context
    g = (
        df.groupby("date", as_index=False)
        .agg(
            truth=("truth_meteor_flux_1e15", "mean"),
            lipas=("hybrid_meteor_flux_1e15", "mean"),
            mem3=("flagship_meteor_flux_1e15", "mean"),
            seasonal=("flagship_mem3_seasonal_no_shower", "mean"),
        )
        .sort_values("date")
    )
    mem = g["seasonal"] if g["seasonal"].notna().any() else g["mem3"]
    fig, ax = plt.subplots(figsize=(7.6, 3.1))
    ax.plot(g["date"], mem, "o-", color=GREEN, lw=1.6, ms=4.0, label="MEM 3 (no shower)")
    ax.plot(g["date"], g["truth"], "o", color=ORANGE, ms=5.0, mfc="none", mew=1.4, label="Evaluation label")
    ax.plot(g["date"], g["lipas"], "o-", color=PURPLE, lw=1.6, ms=4.0, label="LIPAS: MEM 3 + shower term")
    peak = pd.Timestamp("2026-08-04")
    if g["date"].min() <= peak <= g["date"].max():
        y = float(g.loc[g["date"] == peak, "truth"].iloc[0]) if (g["date"] == peak).any() else float(g["truth"].iloc[-1])
        ax.annotate(
            "Perseids peak (4 Aug)",
            xy=(peak, y),
            xytext=(peak - pd.Timedelta(days=10), y + 0.08),
            fontsize=8,
            color="#444",
            arrowprops=dict(arrowstyle="->", color="#888", lw=0.9),
        )
    ax.set_title("Summer Window S micrometeorites (17 Jun – 4 Aug 2026)", fontsize=11)
    ax.set_ylabel(r"Micrometeorite flux ($\times 10^{-15}$)")
    ax.grid(True, alpha=0.25)
    ax.legend(frameon=False, fontsize=8)
    fig.autofmt_xdate(rotation=30, ha="right")
    fig.tight_layout()
    _save(fig, "fig_windowS_meteors.png")


def mission_timeline() -> None:
    if not EVENTS.exists():
        print("skip mission timeline; missing", EVENTS)
        return
    ev = json.loads(EVENTS.read_text())
    markers = [
        ("LIPAS", ev["lipas_first_caution_t_min"], ev["lipas_first_nogo_t_min"], "o", "none", NAVY),
        ("GOES-only", ev["nasa_goes_first_caution_t_min"], ev["nasa_goes_first_nogo_t_min"], "s", ORANGE, ORANGE),
        (
            "Combined NASA",
            ev["nasa_combined_first_caution_t_min"],
            ev["nasa_combined_first_nogo_t_min"],
            "D",
            GREEN,
            GREEN,
        ),
    ]
    fig, axes = plt.subplots(2, 1, figsize=(7.4, 3.6), sharex=True, gridspec_kw={"hspace": 0.18})
    titles = ["Caution", "No-go"]
    for ax, title, idx in zip(axes, titles, [1, 2]):
        for name, caut, nogo, marker, mfc, color in markers:
            t = caut if idx == 1 else nogo
            ax.plot(
                [t],
                [0.5],
                marker=marker,
                markersize=9,
                markerfacecolor=mfc,
                markeredgecolor=color,
                markeredgewidth=1.6,
                linestyle="none",
                label=name if ax is axes[0] else None,
            )
        for x, lab in [(40, "Precursor"), (55, "Geomagnetic\nchange"), (70, "Proton\nsurge")]:
            ax.axvline(x, color="#777", ls="--", lw=0.9)
            if ax is axes[0]:
                ax.text(x, 0.92, lab, ha="center", va="top", fontsize=7.5, color="#555", transform=ax.get_xaxis_transform())
        ax.set_yticks([])
        ax.set_ylabel(title, fontsize=10)
        ax.set_xlim(0, 120)
        ax.set_ylim(0, 1)
        ax.grid(True, axis="x", alpha=0.25)
    axes[0].legend(loc="upper right", frameon=False, fontsize=8, ncol=3)
    axes[1].set_xlabel("Elapsed time (min)")
    fig.suptitle("Mission-simulation decision timeline", fontsize=11, y=0.98)
    fig.tight_layout()
    _save(fig, "fig_mission_timeline.png")


if __name__ == "__main__":
    ab = pd.read_csv(AB_CSV, parse_dates=["date"])
    c = pd.read_csv(C_CSV, parse_dates=["date"])
    skill_figure(
        ab,
        "LIPAS vs Flagship — Summer Window S (17 Jun – 4 Aug 2026)",
        "fig_windowS_skill.png",
        also_dir=ROOT / "logs/overnight_improve/final_v3/window_AB",
    )
    skill_figure(
        c,
        "LIPAS vs Flagship — Storm Window C (1–28 May 2024)",
        "fig_windowC_skill.png",
        also_dir=ROOT / "logs/overnight_improve/final_v3/window_C28",
    )
    radiation_ab()
    meteors_ab()
    mission_timeline()
    # Keep legacy names as copies for any leftover refs
    for src, dst in [
        ("fig_windowS_skill.png", "fig_windowA_skill.png"),
        ("fig_windowS_skill.png", "fig_windowB_skill.png"),
        ("fig_windowS_radiation.png", "fig_windowA_radiation.png"),
        ("fig_windowS_meteors.png", "fig_windowB_meteors.png"),
    ]:
        for out in OUTS:
            s = out / src
            if s.exists():
                (out / dst).write_bytes(s.read_bytes())
                print("alias", out / dst)
