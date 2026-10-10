from __future__ import annotations

import io
import json
import os
import shutil
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

import numpy as np
from PIL import Image
from scipy.ndimage import map_coordinates

ROOT = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(ROOT, "data", "cache", "solar_globe")
MASTER_PATH = os.path.join(CACHE_DIR, "master.jpg")
META_PATH = os.path.join(CACHE_DIR, "master_meta.json")
TILE_ROOT = os.path.join(CACHE_DIR, "tiles")
MASTER_MAX_AGE = 20 * 60
UA = "Mozilla/5.0 (compatible; LIPAS/3; space-weather-ops)"
NEAR_URL = "https://sdo.gsfc.nasa.gov/assets/img/latest/latest_2048_HMIIC.jpg"
SYNODIC_DAYS = 27.2753
N_FRAMES = 8
OUT_W = 2048
OUT_H = 1024
TILE = 256
MAX_LEVEL = 4
JPEG_QUALITY = 86

_lock = threading.Lock()
_mem_master = None
_mem_mtime = 0.0

def _fetch(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
    if not data or len(data) < 2000:
        raise RuntimeError("empty image " + url)
    return data

def _round_sdo_quarter(dt: datetime) -> datetime:
    minute = (dt.minute // 15) * 15
    return dt.replace(minute=minute, second=0, microsecond=0)

def _browse_hmiic_url(dt: datetime, size: int = 2048) -> str:
    stamp = dt.strftime("%Y%m%d_%H%M%S")
    return (
        f"https://sdo.gsfc.nasa.gov/assets/img/browse/"
        f"{dt:%Y}/{dt:%m}/{dt:%d}/{stamp}_{size}_HMIIC.jpg"
    )

def _load_disk_at(now: datetime, days_ago: float) -> tuple[Image.Image, str]:
    if days_ago < 0.35:
        img = Image.open(io.BytesIO(_fetch(NEAR_URL, timeout=30))).convert("RGB")
        return img, NEAR_URL
    day = (now - timedelta(days=days_ago)).astimezone(timezone.utc)
    candidates = []
    for hour, minute in ((12, 0), (0, 0), (18, 0), (6, 0)):
        dt = day.replace(hour=hour, minute=minute, second=0, microsecond=0)
        for size in (1024, 2048):
            candidates.append((dt, size))
    errors = []
    for dt, size in candidates:
        url = _browse_hmiic_url(dt, size)
        try:
            img = Image.open(io.BytesIO(_fetch(url, timeout=15))).convert("RGB")
            return img, url
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, RuntimeError) as exc:
            errors.append(f"{url}: {exc}")
            continue
    raise RuntimeError("HMI continuum unavailable at -%.1fd: %s" % (days_ago, "; ".join(errors[:2])))

def _disk_radius(arr: np.ndarray) -> tuple[float, float, float]:
    lum = arr.mean(axis=2)
    h, w = lum.shape
    cy = (h - 1) * 0.5
    cx = (w - 1) * 0.5
    y = int(round(cy))
    bg = float(np.percentile(lum, 6))
    thresh = max(18.0, bg + 12.0)
    r = 0.0
    row = lum[min(max(y, 0), h - 1)]
    for x in range(int(cx), w):
        if row[x] > thresh:
            r = x - cx
    fallback = 0.48 * min(w, h)
    if r < 0.32 * min(w, h):
        r = fallback
    return float(r), float(cx), float(cy)

def _sample_disk(disk: np.ndarray, lon0_rad: float, out_w: int, out_h: int):

    sh, sw = disk.shape[:2]
    r, cx, cy = _disk_radius(disk)
    ys, xs = np.meshgrid(
        np.linspace(0.0, 1.0, out_h, dtype=np.float64),
        np.linspace(0.0, 1.0, out_w, dtype=np.float64),
        indexing="ij",
    )
    lat = (0.5 - ys) * np.pi
    lon = (xs * 2.0 - 1.0) * np.pi - lon0_rad
    cos_lat = np.cos(lat)
    x = cos_lat * np.sin(lon)
    y = np.sin(lat)
    z = cos_lat * np.cos(lon)
    u = cx + x * r
    v = cy - y * r
    inside = (
        (z > 0.08)
        & (u >= 0.5)
        & (u <= sw - 1.5)
        & (v >= 0.5)
        & (v <= sh - 1.5)
    )

    weight = np.where(inside, np.clip(z, 0.0, 1.0) ** 3.0, 0.0).astype(np.float32)
    rgb = np.zeros((out_h, out_w, 3), dtype=np.float32)
    coords = np.vstack([v.ravel(), u.ravel()])
    for c in range(3):
        sampled = map_coordinates(
            disk[:, :, c].astype(np.float32),
            coords,
            order=1,
            mode="nearest",
        ).reshape(out_h, out_w)
        rgb[:, :, c] = sampled
    return rgb, weight

def _compose_synoptic(frames: list[tuple[Image.Image, float]]) -> Image.Image:
    acc = np.zeros((OUT_H, OUT_W, 3), dtype=np.float32)
    wsum = np.zeros((OUT_H, OUT_W), dtype=np.float32)
    for img, lon0 in frames:
        rgb, weight = _sample_disk(np.asarray(img, dtype=np.float32), lon0, OUT_W, OUT_H)
        acc += rgb * weight[..., None]
        wsum += weight
    tot = np.maximum(wsum, 1e-4)
    out = acc / tot[..., None]
    missing = wsum < 1e-3
    if np.any(missing):
        valid = ~missing
        for x in range(OUT_W):
            col = valid[:, x]
            if not np.any(col) or np.all(col):
                continue
            ys = np.where(col)[0]
            empty = np.where(~col)[0]
            nearest = ys[np.abs(empty[:, None] - ys[None, :]).argmin(axis=1)]
            out[empty, x] = out[nearest, x]
    out = np.clip(out, 0, 255).astype(np.uint8)
    return Image.fromarray(out, mode="RGB")

def _master_fresh() -> bool:
    try:
        return os.path.isfile(MASTER_PATH) and (time.time() - os.path.getmtime(MASTER_PATH)) < MASTER_MAX_AGE
    except OSError:
        return False

def ensure_master(force: bool = False) -> Image.Image:
    global _mem_master, _mem_mtime
    with _lock:
        if not force and _mem_master is not None and (time.time() - _mem_mtime) < MASTER_MAX_AGE:
            return _mem_master
        if not force and _master_fresh():
            img = Image.open(MASTER_PATH).convert("RGB")
            _mem_master = img
            _mem_mtime = os.path.getmtime(MASTER_PATH)
            return img
        now = datetime.now(timezone.utc)
        from concurrent.futures import ThreadPoolExecutor

        def _one(i):
            days_ago = i * SYNODIC_DAYS / N_FRAMES
            lon0 = 2.0 * np.pi * (i / N_FRAMES)
            img, url = _load_disk_at(now, days_ago)
            return i, img, lon0, url, days_ago

        with ThreadPoolExecutor(max_workers=N_FRAMES) as pool:
            loaded = list(pool.map(_one, range(N_FRAMES)))
        loaded.sort(key=lambda row: row[0])
        frames = [(img, lon0) for _, img, lon0, _, _ in loaded]
        sources = [{"days_ago": round(days_ago, 3), "url": url} for _, _, _, url, days_ago in loaded]
        master = _compose_synoptic(frames)
        os.makedirs(CACHE_DIR, exist_ok=True)
        tmp = MASTER_PATH + ".tmp"
        master.save(tmp, format="JPEG", quality=90, optimize=True)
        os.replace(tmp, MASTER_PATH)
        try:
            with open(META_PATH, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "sources": sources,
                        "built": now.isoformat(),
                        "width": master.width,
                        "height": master.height,
                    },
                    f,
                )
        except OSError:
            pass
        try:
            if os.path.isdir(TILE_ROOT):
                shutil.rmtree(TILE_ROOT, ignore_errors=True)
        except OSError:
            pass
        _mem_master = master
        _mem_mtime = time.time()
        return master

def _tile_bounds(z: int, x: int, y: int):
    tiles_x = 2 << z
    tiles_y = 1 << z
    if z < 0 or z > MAX_LEVEL or x < 0 or y < 0 or x >= tiles_x or y >= tiles_y:
        return None
    west = -180.0 + x * (360.0 / tiles_x)
    east = west + 360.0 / tiles_x
    north = 90.0 - y * (180.0 / tiles_y)
    south = north - 180.0 / tiles_y
    return west, south, east, north

def render_tile(z: int, y: int, x: int) -> bytes:
    bounds = _tile_bounds(int(z), int(x), int(y))
    if bounds is None:
        return b""
    west, south, east, north = bounds
    cache_path = os.path.join(TILE_ROOT, str(z), str(y), f"{x}.jpg")
    try:
        if os.path.isfile(cache_path) and _master_fresh():
            with open(cache_path, "rb") as f:
                data = f.read()
            if data:
                return data
    except OSError:
        pass
    master = ensure_master()
    w, h = master.size
    x0 = (west + 180.0) / 360.0 * w
    x1 = (east + 180.0) / 360.0 * w
    y0 = (90.0 - north) / 180.0 * h
    y1 = (90.0 - south) / 180.0 * h
    box = (
        max(0, int(np.floor(x0))),
        max(0, int(np.floor(y0))),
        min(w, int(np.ceil(x1))),
        min(h, int(np.ceil(y1))),
    )
    if box[2] <= box[0] or box[3] <= box[1]:
        return b""
    tile = master.crop(box).resize((TILE, TILE), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    tile.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    data = buf.getvalue()
    try:
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        tmp = cache_path + ".tmp"
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, cache_path)
    except OSError:
        pass
    return data

def master_jpeg() -> bytes:
    ensure_master()
    with open(MASTER_PATH, "rb") as f:
        return f.read()
