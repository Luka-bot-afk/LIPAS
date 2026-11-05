#!/usr/bin/env python3
"""Software-flow diagrams in plain language, sized for the manuscript page."""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

OUT = Path("/Users/lukatakki/Documents/L.I.P.A.S. V3/papers/elsevier/figures")
EDGE = "#1e3a5f"
BLUE = "#e7f0fa"
PEACH = "#fff6ea"
GREEN = "#e7f6ea"
PURPLE = "#f3e9ff"
ARROW = "#3d4a5c"


def box(ax, x, y, w, h, text, face, size=8.0):
    ax.add_patch(
        FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.008,rounding_size=0.015",
            linewidth=1.05,
            edgecolor=EDGE,
            facecolor=face,
            clip_on=False,
        )
    )
    ax.text(
        x + w / 2,
        y + h / 2,
        text,
        ha="center",
        va="center",
        fontsize=size,
        color="#1a1a1a",
        linespacing=1.15,
        clip_on=False,
    )
    return (x, y, w, h)


def arrow(ax, x1, y1, x2, y2):
    ax.add_patch(
        FancyArrowPatch(
            (x1, y1),
            (x2, y2),
            arrowstyle="-|>",
            mutation_scale=8,
            linewidth=0.9,
            color=ARROW,
            shrinkA=1.5,
            shrinkB=1.5,
            clip_on=False,
        )
    )


def save(fig, path: Path):
    fig.savefig(path, dpi=200, facecolor="white")
    plt.close(fig)
    print(path)


def data_path() -> None:
    fig, ax = plt.subplots(figsize=(7.08, 2.28))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.subplots_adjust(left=0.01, right=0.99, top=0.90, bottom=0.02)
    ax.set_title(
        "How the forecast input is built",
        fontsize=11,
        color="#1a1a1a",
        pad=1,
    )

    tops = [
        box(ax, 0.02, 0.62, 0.30, 0.28, "Space-weather feeds\nDONKI, SWPC, and OMNI", BLUE, 8),
        box(ax, 0.35, 0.62, 0.30, 0.28, "Lunar records\nDiviner, CRaTER, LADEE,\nApollo PSE, and MEM 3", BLUE, 7.4),
        box(ax, 0.68, 0.62, 0.30, 0.28, "Place and time\nlatitude, longitude,\nlocal solar time", BLUE, 8),
    ]
    mid = box(ax, 0.12, 0.42, 0.76, 0.14, "Collect the feeds and line them up in one table", PEACH, 8)
    low = box(
        ax,
        0.04,
        0.18,
        0.92,
        0.18,
        "18 numbers for each step: six hazards, place, and time,\n"
        "solar wind, magnetic field, geomagnetic index, regolith depth, ground heating",
        GREEN,
        7.4,
    )
    out = box(ax, 0.16, 0.02, 0.68, 0.11, "LSTM forecast for all six hazards", PURPLE, 8.2)

    for src in tops:
        arrow(ax, src[0] + src[2] / 2, src[1] - 0.005, 0.50, mid[1] + mid[3] + 0.005)
    arrow(ax, 0.50, mid[1] - 0.005, 0.50, low[1] + low[3] + 0.005)
    arrow(ax, 0.50, low[1] - 0.005, 0.50, out[1] + out[3] + 0.005)
    save(fig, OUT / "fig_architecture_data_path.png")


def blend() -> None:
    fig, ax = plt.subplots(figsize=(7.08, 2.15))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.subplots_adjust(left=0.01, right=0.99, top=0.90, bottom=0.03)
    ax.set_title(
        "How physics and the learned correction are mixed",
        fontsize=11,
        color="#1a1a1a",
        pad=1,
    )

    left = box(
        ax,
        0.04,
        0.64,
        0.42,
        0.28,
        "Physics calculation\ntemperature, radiation, moonquakes,\nmeteor catalogs, and solar wind",
        BLUE,
        7.3,
    )
    right = box(
        ax,
        0.54,
        0.64,
        0.42,
        0.28,
        "Learned correction\n72-step memory model",
        PURPLE,
        7.6,
    )
    mid = box(
        ax,
        0.14,
        0.36,
        0.72,
        0.20,
        "Mix used in this paper\nsolar 0.4,   radiation 0.0\n"
        "temperature, moonquakes, micrometeorites, and dust: 0\n"
        "storm / high-radiation gate zeros solar ML",
        PEACH,
        7.0,
    )
    lo_l = box(ax, 0.04, 0.03, 0.42, 0.24, "Learning is used for\nsolar activity (quiet/mixed)", BLUE, 7.8)
    lo_r = box(
        ax,
        0.54,
        0.03,
        0.42,
        0.24,
        "Left on the physics path\nradiation, temperature, moonquakes,\nmicrometeorites, and dust",
        GREEN,
        7.2,
    )

    arrow(ax, left[0] + left[2] / 2, left[1] - 0.006, mid[0] + mid[2] * 0.32, mid[1] + mid[3] + 0.006)
    arrow(ax, right[0] + right[2] / 2, right[1] - 0.006, mid[0] + mid[2] * 0.68, mid[1] + mid[3] + 0.006)
    arrow(ax, mid[0] + mid[2] * 0.28, mid[1] - 0.006, lo_l[0] + lo_l[2] / 2, lo_l[1] + lo_l[3] + 0.006)
    arrow(ax, mid[0] + mid[2] * 0.72, mid[1] - 0.006, lo_r[0] + lo_r[2] / 2, lo_r[1] + lo_r[3] + 0.006)
    save(fig, OUT / "fig_architecture_blend.png")


if __name__ == "__main__":
    data_path()
    blend()
