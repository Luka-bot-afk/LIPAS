#!/usr/bin/env python3
"""Regenerate draft25 result figures from overnight final_v3 / mission_sim outputs."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path("/Users/lukatakki/Documents/L.I.P.A.S. V3")
OUTS = [
    ROOT / "papers/draft25_asr/figures",
    ROOT / "papers/draft25_arxiv/figures",
    ROOT / "papers/elsevier/figures",
]
A_CSV = ROOT / "logs/overnight_improve/final_v3/window_A/daily_predictions.csv"
B_CSV = ROOT / "logs/overnight_improve/final_v3/window_B/daily_predictions.csv"
EVENTS = ROOT / "logs/overnight_improve/mission_sim/events.json"
NAVY = "#1e3a5f"
ORANGE = "#c45c26"
GREEN = "#2f5d50"
PURPLE = "#5b4a8a"


def _save(fig, name: str) -> None:
    for out in OUTS:
        out.mkdir(parents=True, exist_ok=True)
        path = out / name
        fig.savefig(path, dpi=220, bbox_inches="tight", facecolor="white")
        print("wrote", path)
    plt.close(fig)


def window_a_radiation() -> None:
    df = pd.read_csv(A_CSV, parse_dates=["date"])
    g = (
        df.groupby("date", as_index=False)
        .agg(
            truth=("truth_radiation_mSv", "mean"),
            hybrid=("hybrid_radiation_mSv", "mean"),
            flagship=("flagship_radiation_mSv", "mean"),
        )
        .sort_values("date")
    )
    fig, ax = plt.subplots(figsize=(7.2, 3.2))
    ax.plot(g["date"], g["truth"], "o-", color=ORANGE, lw=1.6, ms=4.5, label="Observed labels")
    ax.plot(g["date"], g["hybrid"], "o-", color=PURPLE, lw=1.6, ms=4.5, label="L.I.P.A.S.")
    ax.plot(g["date"], g["flagship"], "o-", color=GREEN, lw=1.6, ms=4.5, label="GOES + physics")
    ax.set_title("Window A radiation (17 Jun – 14 Jul 2026)", fontsize=11)
    ax.set_ylabel("Radiation (mSv)")
    ax.grid(True, alpha=0.25)
    ax.legend(frameon=False, fontsize=8)
    fig.autofmt_xdate(rotation=30, ha="right")
    fig.tight_layout()
    _save(fig, "fig_windowA_radiation.png")


def window_b_meteors() -> None:
    df = pd.read_csv(B_CSV, parse_dates=["date"])
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
    # Prefer seasonal MEM3 without shower if present; else flagship sphere-only.
    mem = g["seasonal"] if g["seasonal"].notna().any() else g["mem3"]
    fig, ax = plt.subplots(figsize=(7.2, 3.0))
    ax.plot(g["date"], mem, "o-", color=GREEN, lw=1.6, ms=4.5, label="MEM 3 (no shower)")
    ax.plot(g["date"], g["truth"], "o", color=ORANGE, ms=5.5, mfc="none", mew=1.4, label="Evaluation label")
    ax.plot(g["date"], g["lipas"], "o-", color=PURPLE, lw=1.6, ms=4.5, label="LIPAS: MEM 3 + shower term")
    # Perseids peak annotation near 4 Aug if in range
    peak = pd.Timestamp("2026-08-04")
    if g["date"].min() <= peak <= g["date"].max():
        y = float(g.loc[g["date"] == peak, "truth"].iloc[0]) if (g["date"] == peak).any() else float(g["truth"].iloc[-1])
        ax.annotate(
            "Perseids peak (4 Aug)",
            xy=(peak, y),
            xytext=(peak - pd.Timedelta(days=8), y + 0.08),
            fontsize=8,
            color="#444",
            arrowprops=dict(arrowstyle="->", color="#888", lw=0.9),
        )
    ax.set_title("Window B micrometeorites (18 Jul – 14 Aug 2026)", fontsize=11)
    ax.set_ylabel(r"Micrometeorite flux ($\times 10^{-15}$)")
    ax.grid(True, alpha=0.25)
    ax.legend(frameon=False, fontsize=8)
    fig.autofmt_xdate(rotation=30, ha="right")
    fig.tight_layout()
    _save(fig, "fig_windowB_meteors.png")


def mission_timeline() -> None:
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


def skill_copies() -> None:
    mapping = {
        "A": "fig_windowA_skill.png",
        "B": "fig_windowB_skill.png",
        "C": "fig_windowC_skill.png",
    }
    for label, name in mapping.items():
        src = ROOT / f"logs/overnight_improve/final_v3/window_{label}/skill_by_site.png"
        if not src.exists():
            print("missing", src)
            continue
        data = src.read_bytes()
        for out in OUTS[:2]:
            dest = out / name
            dest.write_bytes(data)
            print("copied", dest)


if __name__ == "__main__":
    window_a_radiation()
    window_b_meteors()
    mission_timeline()
    skill_copies()
    # Also refresh architecture blend via sibling script
    import draw_software_flows as dsf

    dsf.OUT = ROOT / "papers/elsevier/figures"
    dsf.blend()
    blend_src = dsf.OUT / "fig_architecture_blend.png"
    for out in OUTS[:2]:
        dest = out / "fig_architecture_blend.png"
        dest.write_bytes(blend_src.read_bytes())
        print("copied", dest)
