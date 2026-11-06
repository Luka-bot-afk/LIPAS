#!/usr/bin/env python3
"""Pick long summer Window A + storm Window B under R6c; run flagship studies (3 sites)."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

HAZARDS = [
    "solar_activity",
    "radiation_mSv",
    "temperature_C",
    "moonquakes_per_day",
    "meteor_flux_1e15",
    "dust_g_cm3",
]


def _wins_from_summary(summary: dict) -> tuple[int, dict]:
    vs = summary.get("vs_flagship") or {}
    n = 0
    detail = {}
    for h in HAZARDS:
        row = vs.get(h) or {}
        beat = bool(row.get("hybrid_beats_flagship")) or bool(row.get("tie"))
        # count tie as win (same bar as drastic-wins waves)
        if beat:
            n += 1
        detail[h] = {
            "win": beat,
            "tie": bool(row.get("tie")),
            "hybrid_rmse": row.get("hybrid_rmse"),
            "flagship_rmse": row.get("flagship_rmse"),
        }
    return n, detail


def run_flagship(csv: str, model_dir: str, start: str, end: str, label: str, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    # Mac TF 2.16 / Py3.12 needs cpu_tf_bootstrap (distutils shim + CPU-only).
    cpu = ROOT / "logs/overnight_improve/train4/run_on_cpu.py"
    script = ROOT / "scripts/run_14day_flagship_study.py"
    cmd = [
        sys.executable,
        str(cpu if cpu.exists() else script),
        *([str(script)] if cpu.exists() else []),
        "--csv",
        csv,
        "--model-dir",
        model_dir,
        "--start",
        start,
        "--end",
        end,
        "--window-label",
        label,
        "--out-dir",
        str(out_dir),
    ]
    print("RUN", " ".join(cmd), flush=True)
    subprocess.check_call(cmd, cwd=str(ROOT))
    summary = json.loads((out_dir / "summary.json").read_text())
    wins, detail = _wins_from_summary(summary)
    return {
        "start": start,
        "end": end,
        "label": label,
        "out_dir": str(out_dir),
        "wins": wins,
        "detail": detail,
        "n_rows": int(summary.get("n_rows") or 0)
        if "n_rows" in summary
        else None,
        "day_fraction": (summary.get("lunar_illumination") or {}).get("day_fraction"),
        "metrics": summary.get("metrics"),
        "vs_flagship": summary.get("vs_flagship"),
    }


def summer_candidates(df: pd.DataFrame) -> list[tuple[str, str, int]]:
    """Long summer spans (~3mo+) ending at CSV max (window_B_ready → 2026-08-04)."""
    dmax = df["date"].max()
    # Prefer April/May → Aug for ≥~90 days when data allow.
    starts = [
        "2026-04-01",
        "2026-04-15",
        "2026-05-01",
        "2026-05-07",
        "2026-05-15",
        "2026-06-01",
        "2026-06-17",  # L20 legacy short
    ]
    end = str(pd.Timestamp(min(dmax, pd.Timestamp("2026-08-04"))).date())
    out = []
    for s in starts:
        if pd.Timestamp(s) > dmax:
            continue
        days = int((pd.Timestamp(end) - pd.Timestamp(s)).days) + 1
        # require data density
        sub = df[(df["date"] >= s) & (df["date"] <= end)]
        if sub["date"].nunique() < max(40, days // 3):
            continue
        out.append((s, end, days))
    return out


def storm_candidates(df: pd.DataFrame) -> list[tuple[str, str, int]]:
    opts = [
        ("2024-05-01", "2024-05-31"),
        ("2024-05-04", "2024-05-17"),  # L20 legacy
        ("2024-05-01", "2024-05-21"),
        ("2024-04-20", "2024-05-20"),
    ]
    out = []
    for s, e in opts:
        sub = df[(df["date"] >= s) & (df["date"] <= e)]
        days = int((pd.Timestamp(e) - pd.Timestamp(s)).days) + 1
        if sub["date"].nunique() < max(10, days // 3):
            continue
        out.append((s, e, days))
    return out


def score_candidate(res: dict) -> tuple:
    """Higher wins, then longer window, then better solar+rad margins."""
    wins = int(res["wins"])
    start, end = res["start"], res["end"]
    days = int((pd.Timestamp(end) - pd.Timestamp(start)).days) + 1
    vs = res.get("vs_flagship") or {}
    margin = 0.0
    for h in ("solar_activity", "radiation_mSv"):
        row = vs.get(h) or {}
        hy = row.get("hybrid_rmse")
        fl = row.get("flagship_rmse")
        if hy is not None and fl is not None and np.isfinite(hy) and np.isfinite(fl):
            margin += float(fl - hy)
    return (wins, days, margin)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--out-root", required=True)
    ap.add_argument("--studies-dir", required=True)
    args = ap.parse_args()

    out_root = Path(args.out_root)
    studies = Path(args.studies_dir)
    grid_dir = studies / "window_grid"
    grid_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(args.csv, parse_dates=["date"], usecols=["date"])
    # If full parse needed for density, reload lightly
    df2 = pd.read_csv(args.csv, parse_dates=["date"], usecols=["date", "site"])

    a_cands = summer_candidates(df2)
    b_cands = storm_candidates(df2)
    print("A candidates", a_cands, flush=True)
    print("B candidates", b_cands, flush=True)

    a_results = []
    for i, (s, e, days) in enumerate(a_cands):
        tag = f"A_{s}_{e}".replace("-", "")
        res = run_flagship(args.csv, args.model_dir, s, e, "A", out_root / "A_grid" / tag)
        res["days"] = days
        a_results.append(res)
        (grid_dir / f"{tag}.json").write_text(json.dumps(res, indent=2))

    b_results = []
    for i, (s, e, days) in enumerate(b_cands):
        tag = f"B_{s}_{e}".replace("-", "")
        # flagship script uses window-label B for Diviner/dust truth policy in storm path;
        # historical L20 used label C for May storm — keep B for paper naming, but set
        # label to B so storm truth policy activates (see run_14day_flagship_study).
        res = run_flagship(args.csv, args.model_dir, s, e, "B", out_root / "B_grid" / tag)
        res["days"] = days
        b_results.append(res)
        (grid_dir / f"{tag}.json").write_text(json.dumps(res, indent=2))

    if not a_results or not b_results:
        raise SystemExit("No viable window candidates — check CSV coverage")

    best_a = max(a_results, key=score_candidate)
    best_b = max(b_results, key=score_candidate)

    # Promote chosen windows to canonical out dirs
    import shutil

    a_dst = out_root / "A"
    b_dst = out_root / "B_storm"
    if a_dst.exists():
        shutil.rmtree(a_dst)
    if b_dst.exists():
        shutil.rmtree(b_dst)
    shutil.copytree(best_a["out_dir"], a_dst)
    shutil.copytree(best_b["out_dir"], b_dst)
    best_a = dict(best_a)
    best_b = dict(best_b)
    best_a["out_dir"] = str(a_dst)
    best_b["out_dir"] = str(b_dst)

    selected = {
        "package": "R6c_caution_cap090",
        "csv": args.csv,
        "model_dir": args.model_dir,
        "A": best_a,
        "B": best_b,
        "A_grid": [
            {"start": r["start"], "end": r["end"], "wins": r["wins"], "days": r["days"]}
            for r in a_results
        ],
        "B_grid": [
            {"start": r["start"], "end": r["end"], "wins": r["wins"], "days": r["days"]}
            for r in b_results
        ],
        "selection_rule": "max (wins, length_days, solar+rad RMSE margin vs replica); 3 sites fixed",
    }
    (studies / "SELECTED_WINDOWS.json").write_text(json.dumps(selected, indent=2))
    (out_root / "SELECTED_WINDOWS.json").write_text(json.dumps(selected, indent=2))
    print(json.dumps({"best_A": best_a["start"], "best_B": best_b["start"], "A_wins": best_a["wins"], "B_wins": best_b["wins"]}, indent=2))


if __name__ == "__main__":
    main()
