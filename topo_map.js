
const TOPO = (() => {
    const WAC  = 'https://trek.nasa.gov/tiles/Moon/EQ/LRO_WAC_Mosaic_Global_303ppd_v02/1.0.0/default/default028mm';
    const ZOOM = 7;
    const TILE_SIZE = 256;
    const GRID = 5;

    const LOCS = [
        [ 0.0,    0.0,   'mare'],
        [-89.68, 166.15, 'polar'],
        [-90.0,    0.0,  'polar'],
        [-43.31, -11.36, 'crater'],
        [ 32.8,  -15.6,  'mare'],
        [-85.9,   12.9,  'polar'],
        [  8.5,   31.4,  'mare'],
        [ 18.4,  -57.4,  'mare'],
        [ 23.7,  -47.4,  'highland'],
        [  9.62, -20.08, 'crater'],
        [ -3.01,  17.5,  'highland'],
        [  8.1,  -51.0,  'crater'],
        [-53.0,  158.0,  'basin'],
        [ 51.6,   -9.4,  'crater'],
        [ 28.0,   17.5,  'mare'],
        [ 17.0,   59.1,  'mare'],
        [-24.4,  -38.6,  'mare'],
        [-21.3,  -13.3,  'mare'],
        [ 13.3,    3.6,  'mare'],
        [  5.5,  -18.4,  'mare'],
        [ 44.1,  -31.7,  'mare'],
        [ 55.5,  -24.8,  'highland'],
        [  0.0,    0.0,  'mare'],
        [ 14.5,  -11.3,  'crater'],
        [-58.4,  -14.4,  'crater'],
        [-67.2,  -69.2,  'crater'],
        [-75.4, -132.5,  'crater'],
        [-84.7,   83.1,  'polar'],
        [-82.3,  -48.5,  'polar'],
        [-88.1,  -45.0,  'polar'],
        [-88.4,  -86.7,  'polar'],
        [-87.8,   77.4,  'polar'],
        [-87.0,  -70.0,  'polar'],
        [-89.1,  -45.5,  'polar'],
        [-88.5,  -45.0,  'polar'],
        [-85.0,   25.0,  'highland'],
        [-86.0,   10.0,  'polar'],
        [-88.0,  -85.0,  'polar'],
        [-44.8,  176.0,  'crater'],
        [-21.2,  128.9,  'crater'],
        [ 27.3,  147.9,  'mare'],
        [ -4.4, -157.4,  'basin'],
        [-36.1, -151.9,  'basin'],
        [ -5.9,  179.4,  'crater'],
        [  1.4, -129.2,  'basin'],
        [  5.5,  141.0,  'basin'],
        [ 55.3,  103.8,  'crater'],
        [-75.2, -133.6,  'polar'],
        [-33.7,  163.5,  'mare'],
        [-19.7,  149.3,  'crater'],
        [-35.0,  147.0,  'crater'],
        [-57.3,  163.1,  'basin'],
        [ 58.7, -146.1,  'crater'],
        [-11.9,  104.6,  'highland'],
        [-35.2, -166.3,  'crater'],
        [-69.3, -172.0,  'basin'],
    ];

    function latLonToTile(lat, lon, zoom) {
        const n = 1 << zoom;
        const col = Math.floor((lon + 180) / 360 * n);
        const row = Math.floor((90 - lat) / 180 * (n / 2));
        return {
            row: Math.max(0, Math.min(n / 2 - 1, row)),
            col: ((col % n) + n) % n
        };
    }

    function latLonToPixelOffset(lat, lon, zoom) {
        const n = 1 << zoom;
        const fx = (lon + 180) / 360 * n;
        const fy = (90 - lat) / 180 * (n / 2);
        return { px: (fx - Math.floor(fx)) * TILE_SIZE, py: (fy - Math.floor(fy)) * TILE_SIZE };
    }

    function tileUrl(row, col, zoom) {
        const n = 1 << zoom;
        const c = ((col % n) + n) % n;
        const r = Math.max(0, Math.min(n / 2 - 1, row));
        return `${WAC}/${zoom}/${r}/${c}.jpg`;
    }

    function elevColor(e, type) {
        switch (type) {
            case 'polar': {
                const v = Math.round(30 + e * 80);
                return `rgba(${v},${v+10},${v+25},0.38)`;
            }
            case 'mare': {
                const v = Math.round(10 + e * 40);
                return `rgba(${v+5},${v+8},${v+20},0.28)`;
            }
            case 'basin': {
                const v = Math.round(20 + e * 60);
                return `rgba(${v+10},${v},${v+5},0.35)`;
            }
            case 'crater':
            case 'highland':
            default: {
                if (e < 0.4) {
                    const t = e / 0.4;
                    return `rgba(${Math.round(20+t*30)},${Math.round(15+t*22)},${Math.round(10+t*15)},0.32)`;
                }
                const t = (e - 0.4) / 0.6;
                return `rgba(${Math.round(50+t*90)},${Math.round(37+t*68)},${Math.round(25+t*45)},0.30)`;
            }
        }
    }

    function seededRand(seed) {
        let s = (Math.abs(Math.round(seed * 9973)) | 1) >>> 0;
        return () => { s = Math.imul(s, 1664525) + 1013904223 >>> 0; return s / 4294967296; };
    }

    function drawElevationOverlay(ctx, W, H, locIdx, type) {
        const [lat, lon] = LOCS[locIdx];
        const rand = seededRand(lat * 1000 + lon * 100 + locIdx * 7);

        const FW = 64, FH = 32;
        const field = new Float32Array(FW * FH);
        const layers = [
            { ax: rand()*4+2,  ay: rand()*4+2,  px: rand()*6.28, py: rand()*6.28, amp: 0.5  },
            { ax: rand()*8+4,  ay: rand()*8+4,  px: rand()*6.28, py: rand()*6.28, amp: 0.25 },
            { ax: rand()*16+8, ay: rand()*16+8, px: rand()*6.28, py: rand()*6.28, amp: 0.12 },
            { ax: rand()*32+16,ay: rand()*32+16,px: rand()*6.28, py: rand()*6.28, amp: 0.06 },
        ];
        const flatness = (type === 'mare') ? 0.3 : (type === 'polar') ? 0.55 : 1.0;
        for (let y = 0; y < FH; y++) {
            for (let x = 0; x < FW; x++) {
                let v = 0;
                for (const l of layers) v += Math.sin(x / FW * l.ax + l.px) * Math.cos(y / FH * l.ay + l.py) * l.amp;
                field[y * FW + x] = v * flatness;
            }
        }
        let mn = Infinity, mx = -Infinity;
        for (let i = 0; i < field.length; i++) { if (field[i] < mn) mn = field[i]; if (field[i] > mx) mx = field[i]; }
        const rng = mx - mn || 1;
        for (let i = 0; i < field.length; i++) field[i] = (field[i] - mn) / rng;

        const scaleX = W / FW, scaleY = H / FH;
        for (let y = 0; y < FH; y++) {
            for (let x = 0; x < FW; x++) {
                ctx.fillStyle = elevColor(field[y * FW + x], type);
                ctx.fillRect(Math.round(x * scaleX), Math.round(y * scaleY),
                             Math.ceil(scaleX) + 1, Math.ceil(scaleY) + 1);
            }
        }

        const levels = 10;
        ctx.save();
        for (let l = 1; l < levels; l++) {
            const thr = l / levels;
            const major = l % 3 === 0;
            ctx.beginPath();
            for (let y = 0; y < FH - 1; y++) {
                for (let x = 0; x < FW - 1; x++) {
                    const v  = field[y * FW + x];
                    const vr = field[y * FW + x + 1];
                    const vd = field[(y+1) * FW + x];
                    if ((v < thr) !== (vr < thr)) {
                        const t = (thr - v) / (vr - v);
                        const px = (x + t) * scaleX, py = y * scaleY;
                        ctx.moveTo(px, py); ctx.lineTo(px, py + scaleY);
                    }
                    if ((v < thr) !== (vd < thr)) {
                        const t = (thr - v) / (vd - v);
                        const px = x * scaleX, py = (y + t) * scaleY;
                        ctx.moveTo(px, py); ctx.lineTo(px + scaleX, py);
                    }
                }
            }
            const alpha = major ? 0.55 : 0.22;
            const col = (type === 'mare' || type === 'polar')
                ? `rgba(120,160,220,${alpha})`
                : `rgba(220,200,160,${alpha})`;
            ctx.strokeStyle = col;
            ctx.lineWidth = major ? 1.2 : 0.5;
            ctx.stroke();
        }
        ctx.restore();
    }

    function drawMarker(ctx, cx, cy, name, scale = 1.0) {
        const baseScale = scale;
        const pulse = 0.92 + 0.08 * Math.sin(_blobPhase * 1.4);

        const glowRadius = 34 * baseScale * pulse;
        const glow = ctx.createRadialGradient(cx, cy, 2 * baseScale, cx, cy, glowRadius);
        glow.addColorStop(0, 'rgba(110,182,255,0.45)');
        glow.addColorStop(0.35, 'rgba(110,182,255,0.18)');
        glow.addColorStop(1, 'rgba(110,182,255,0)');
        ctx.beginPath(); ctx.arc(cx, cy, glowRadius, 0, Math.PI * 2);
        ctx.fillStyle = glow; ctx.fill();

        ctx.save();
        ctx.strokeStyle = 'rgba(230,238,248,0.85)';
        ctx.lineWidth = 2 * baseScale;
        ctx.lineCap = 'round';
        ctx.beginPath();
        ctx.moveTo(cx, cy + 4 * baseScale);
        ctx.lineTo(cx, cy + 18 * baseScale);
        ctx.stroke();
        ctx.restore();

        ctx.beginPath(); ctx.arc(cx, cy, 10 * baseScale, 0, Math.PI * 2);
        ctx.strokeStyle = 'rgba(230,238,248,0.95)'; ctx.lineWidth = 2 * baseScale; ctx.stroke();
        ctx.beginPath(); ctx.arc(cx, cy, 10 * baseScale, 0, Math.PI * 2);
        ctx.strokeStyle = 'rgba(110,182,255,0.9)'; ctx.lineWidth = 1.2 * baseScale; ctx.stroke();

        ctx.beginPath(); ctx.arc(cx, cy, 4.5 * baseScale, 0, Math.PI * 2);
        ctx.fillStyle = '#6eb6ff'; ctx.fill();
        ctx.strokeStyle = 'rgba(255,255,255,0.9)'; ctx.lineWidth = 1 * baseScale; ctx.stroke();

        if (name) {
            ctx.save();
            ctx.font = `600 ${11 * baseScale}px IBM Plex Sans, system-ui, sans-serif`;
            const tw = ctx.measureText(name).width;
            const lx = cx + 16 * baseScale, ly = cy - 10 * baseScale;
            const padX = 8 * baseScale, padY = 5 * baseScale;
            const bw = tw + padX * 2, bh = 16 * baseScale;
            ctx.beginPath();
            const r = 8 * baseScale;
            ctx.moveTo(lx + r, ly - bh / 2);
            ctx.arcTo(lx + bw, ly - bh / 2, lx + bw, ly + bh / 2, r);
            ctx.arcTo(lx + bw, ly + bh / 2, lx, ly + bh / 2, r);
            ctx.arcTo(lx, ly + bh / 2, lx, ly - bh / 2, r);
            ctx.arcTo(lx, ly - bh / 2, lx + bw, ly - bh / 2, r);
            ctx.closePath();
            ctx.fillStyle = 'rgba(11,14,19,0.82)';
            ctx.fill();
            ctx.strokeStyle = 'rgba(110,182,255,0.45)';
            ctx.lineWidth = 1;
            ctx.stroke();
            ctx.fillStyle = '#e6eef8';
            ctx.fillText(name, lx + padX, ly + 4 * baseScale);
            ctx.restore();
        }
    }

    function drawWaypoints(ctx, W, H, locIdx) {
        const [clat, clon] = LOCS[locIdx] || LOCS[0];
        const names = (typeof window.LOCS !== 'undefined' && Array.isArray(window.LOCS))
            ? window.LOCS.map(l => l.name)
            : LOCS.map((_, i) => `WP-${i}`);
        const degPerPxX = 0.045;
        const degPerPxY = 0.045;
        for (let i = 0; i < LOCS.length; i++) {
            if (i === locIdx) continue;
            const [lat, lon] = LOCS[i];
            let dLon = lon - clon;
            if (dLon > 180) dLon -= 360;
            if (dLon < -180) dLon += 360;
            const dLat = lat - clat;
            const px = W / 2 + dLon / degPerPxX;
            const py = H / 2 - dLat / degPerPxY;
            if (px < 12 || px > W - 12 || py < 12 || py > H - 12) continue;
            const dist = Math.hypot(dLat, dLon);
            if (dist > 28) continue;

            const a = Math.max(0.25, 1 - dist / 28);
            ctx.beginPath();
            ctx.arc(px, py, 4.5, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(110,182,255,${0.55 * a})`;
            ctx.fill();
            ctx.strokeStyle = `rgba(230,238,248,${0.75 * a})`;
            ctx.lineWidth = 1.2;
            ctx.stroke();

            const label = (names[i] || '').split(/[---]/)[0].trim().slice(0, 18);
            if (label && dist < 14) {
                ctx.save();
                ctx.font = '500 9px IBM Plex Sans, system-ui, sans-serif';
                ctx.fillStyle = `rgba(200,220,240,${0.7 * a})`;
                ctx.fillText(label, px + 7, py + 3);
                ctx.restore();
            }
        }
    }

    function sampleField(field, fw, fh, u, v) {
        if (!field || !fw || !fh) return 0;
        const x = Math.max(0, Math.min(fw - 1.001, u * (fw - 1)));
        const y = Math.max(0, Math.min(fh - 1.001, v * (fh - 1)));
        const x0 = Math.floor(x), y0 = Math.floor(y);
        const x1 = Math.min(fw - 1, x0 + 1), y1 = Math.min(fh - 1, y0 + 1);
        const tx = x - x0, ty = y - y0;
        const a = field[y0 * fw + x0], b = field[y0 * fw + x1];
        const c = field[y1 * fw + x0], d = field[y1 * fw + x1];
        return a * (1 - tx) * (1 - ty) + b * tx * (1 - ty) + c * (1 - tx) * ty + d * tx * ty;
    }

    function getSelectedOverlays() {
        if (typeof window.getActiveHazardOverlays === 'function') {
            const keys = window.getActiveHazardOverlays();
            if (keys && keys.length) return keys;
        }
        const overlayType = document.getElementById('hazardOverlaySelect')?.value || 'none';
        return overlayType === 'none' ? [] : [overlayType];
    }

    function drawHazardBlobs(ctx, W, H) {
        if (!window.hazardData) return;
        const types = getSelectedOverlays();
        if (!types.length) return;

        const palettes = {
            radiation:       { c0: [255, 70, 60],  c1: [255, 140, 70], c2: [180, 40, 100] },
            micrometeorites: { c0: [255, 200, 60], c1: [255, 140, 40], c2: [220, 100, 30] },
            dust:            { c0: [210, 170, 100],c1: [170, 130, 80], c2: [120, 90, 55] },
            moonquakes:      { c0: [180, 120, 255],c1: [110, 70, 220], c2: [70, 40, 160] },
            temperature:     { c0: [255, 90, 50],  c1: [80, 180, 255], c2: [30, 80, 200] },
            solar:           { c0: [255, 220, 80], c1: [255, 150, 40], c2: [255, 90, 30] },
            sep:             { c0: [255, 110, 160],c1: [220, 70, 120], c2: [140, 30, 80] },
            cme:             { c0: [255, 160, 60], c1: [240, 100, 40], c2: [160, 50, 20] },
        };
        const pulse = 0.92 + 0.08 * Math.sin(_blobPhase);

        types.forEach((overlayType, layerIdx) => {
            const layer = window.hazardData[overlayType];
            if (!layer) return;
            const pal = palettes[overlayType] || { c0: [90, 180, 255], c1: [50, 120, 220], c2: [40, 80, 180] };
            const field = layer.field;
            const fw = layer.fw || 48, fh = layer.fh || 32;
            const baseI = (layer.intensity != null ? layer.intensity : 0.5) * pulse;
            const stackBoost = 0.75 + layerIdx * 0.08;

            ctx.save();
            if (layerIdx > 0) ctx.globalCompositeOperation = 'lighter';
            const step = Math.max(3, Math.floor(Math.min(W, H) / 90));
            for (let y = 0; y < H; y += step) {
                for (let x = 0; x < W; x += step) {
                    let v;
                    if (field) {
                        v = sampleField(field, fw, fh, x / W, y / H);
                    } else if (layer.length) {
                        v = 0.08;
                        for (let i = 0; i < layer.length; i++) {
                            const b = layer[i];
                            if (!b) continue;
                            const d = Math.hypot(x / W - b.x, y / H - b.y);
                            const t = Math.max(0, 1 - d / Math.max(0.08, b.r));
                            v += (b.intensity || 0.4) * t * t;
                        }
                    } else {
                        continue;
                    }
                    v = Math.max(0, Math.min(1, v * (0.85 + baseI * 0.4)));
                    if (v < 0.04) continue;
                    let r, g, b, a;
                    if (overlayType === 'temperature') {
                        const hot = v;
                        r = Math.round(pal.c1[0] + (pal.c0[0] - pal.c1[0]) * hot);
                        g = Math.round(pal.c1[1] + (pal.c0[1] - pal.c1[1]) * hot);
                        b = Math.round(pal.c1[2] + (pal.c0[2] - pal.c1[2]) * hot);
                        a = (0.10 + v * 0.48) * stackBoost;
                    } else {
                        const t = v;
                        r = Math.round(pal.c2[0] + (pal.c0[0] - pal.c2[0]) * t);
                        g = Math.round(pal.c2[1] + (pal.c0[1] - pal.c2[1]) * t);
                        b = Math.round(pal.c2[2] + (pal.c0[2] - pal.c2[2]) * t);
                        a = (0.08 + v * 0.45) * stackBoost;
                    }
                    ctx.fillStyle = `rgba(${r},${g},${b},${Math.min(0.72, a).toFixed(3)})`;
                    ctx.fillRect(x, y, step + 1, step + 1);
                }
            }

            ctx.globalCompositeOperation = 'lighter';
            const blobs = Array.isArray(layer) ? layer : [];
            blobs.forEach((b, i) => {
                if (!b || b.x == null) return;
                const phase = _blobPhase + i * 0.9 + layerIdx * 0.3;
                const bx = b.x * W + Math.sin(phase * 0.6) * 6;
                const by = b.y * H + Math.cos(phase * 0.5) * 5;
                const br = Math.max(24, b.r * Math.min(W, H) * (0.9 + 0.1 * Math.sin(phase)));
                const intens = Math.max(0.15, Math.min(1, (b.intensity || baseI) * pulse));
                const g = ctx.createRadialGradient(bx, by, 0, bx, by, br);
                g.addColorStop(0, `rgba(${pal.c0[0]},${pal.c0[1]},${pal.c0[2]},${(intens * 0.42).toFixed(3)})`);
                g.addColorStop(0.45, `rgba(${pal.c1[0]},${pal.c1[1]},${pal.c1[2]},${(intens * 0.18).toFixed(3)})`);
                g.addColorStop(1, `rgba(${pal.c2[0]},${pal.c2[1]},${pal.c2[2]},0)`);
                ctx.beginPath();
                ctx.ellipse(bx, by, br, br * 0.72, phase * 0.1, 0, Math.PI * 2);
                ctx.fillStyle = g;
                ctx.fill();
            });
            ctx.restore();
        });
    }

    function drawVignette(ctx, W, H) {
        const v = ctx.createRadialGradient(W/2, H/2, H * 0.28, W/2, H/2, H * 0.78);
        v.addColorStop(0, 'rgba(0,0,0,0)');
        v.addColorStop(1, 'rgba(0,2,10,0.72)');
        ctx.fillStyle = v;
        ctx.fillRect(0, 0, W, H);
    }

    function drawScaleBar(ctx, W, H, zoom) {
        const kmPerTile = 340;
        const pxPerKm = TILE_SIZE / kmPerTile;
        const barKm = 100;
        const barPx = barKm * pxPerKm;
        const x = 20, y = H - 28;
        ctx.save();
        ctx.strokeStyle = 'rgba(200,220,255,0.85)';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(x, y); ctx.lineTo(x + barPx, y);
        ctx.moveTo(x, y - 5); ctx.lineTo(x, y + 5);
        ctx.moveTo(x + barPx, y - 5); ctx.lineTo(x + barPx, y + 5);
        ctx.stroke();
        ctx.fillStyle = 'rgba(200,220,255,0.9)';
        ctx.font = '10px Poppins, sans-serif';
        ctx.fillText(`${barKm} km`, x + barPx / 2 - 14, y - 8);
        ctx.restore();
    }

    let _canvas, _ctx;
    let _locIdx = 0;
    let _zoom = 0, _offX = 0, _offY = 0;
    let _dragging = false, _lastX, _lastY;
    let _tileCache = {};
    let _pendingDraw = false;
    let _animFrame = null;
    let _blobPhase = 0;
    let _cachedTiles = null;
    let _cachedLocIdx = -1;
    let _initialLoadDone = false;

    function loadTile(url) {
        if (_tileCache[url]) return _tileCache[url];
        const img = new Image();
        img.crossOrigin = 'anonymous';
        const p = new Promise(resolve => {
            img.onload  = () => resolve(img);
            img.onerror = () => resolve(null);
            img.src = url;
        });
        _tileCache[url] = p;
        return p;
    }

    function debugTileUrls(lat, lon, zoom) {
        const { row: cr, col: cc } = latLonToTile(lat, lon, zoom);
        const half = Math.floor(GRID / 2);
        const urls = [];
        for (let dr = -half; dr <= half; dr++) {
            for (let dc = -half; dc <= half; dc++) {
                urls.push(tileUrl(cr + dr, cc + dc, zoom));
            }
        }
        return urls;
    }

    async function loadTileGrid(centerRow, centerCol, zoom) {
        const half = Math.floor(GRID / 2);
        const promises = [];
        for (let dr = -half; dr <= half; dr++) {
            for (let dc = -half; dc <= half; dc++) {
                promises.push(loadTile(tileUrl(centerRow + dr, centerCol + dc, zoom)));
            }
        }
        return Promise.all(promises);
    }

    async function render() {
        if (!_canvas) return;
        const W = _canvas.width, H = _canvas.height;
        const ctx = _ctx;

        const [lat, lon, type] = LOCS[_locIdx] || LOCS[0];
        const { row: cr, col: cc } = latLonToTile(lat, lon, ZOOM);
        const { px: offPx, py: offPy } = latLonToPixelOffset(lat, lon, ZOOM);

        if (!_initialLoadDone) {
            ctx.fillStyle = '#000';
            ctx.fillRect(0, 0, W, H);
            ctx.fillStyle = '#00e5ff';
            ctx.font = '14px Poppins, sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText('Loading LRO imagery...', W / 2, H / 2);
        }

        let tiles;
        if (_cachedLocIdx === _locIdx && _cachedTiles) {
            tiles = _cachedTiles;
        } else {
            tiles = await loadTileGrid(cr, cc, ZOOM);
            _cachedTiles = tiles;
            _cachedLocIdx = _locIdx;
            _initialLoadDone = true;
        }

        ctx.fillStyle = '#000';
        ctx.fillRect(0, 0, W, H);

        ctx.save();
        ctx.translate(_offX, _offY);
        ctx.scale(1 + _zoom * 0.4, 1 + _zoom * 0.4);

        const half = Math.floor(GRID / 2);
        const gridPxW = GRID * TILE_SIZE;
        const gridPxH = GRID * TILE_SIZE;
        const startX = W / 2 - (half * TILE_SIZE + offPx);
        const startY = H / 2 - (half * TILE_SIZE + offPy);

        let ti = 0;
        for (let dr = -half; dr <= half; dr++) {
            for (let dc = -half; dc <= half; dc++) {
                const img = tiles[ti++];
                const dx = startX + (dc + half) * TILE_SIZE;
                const dy = startY + (dr + half) * TILE_SIZE;
                if (img) {
                    ctx.drawImage(img, dx, dy, TILE_SIZE, TILE_SIZE);
                } else {
                    ctx.fillStyle = '#0a0c14';
                    ctx.fillRect(dx, dy, TILE_SIZE, TILE_SIZE);
                }
            }
        }

        ctx.save();
        ctx.beginPath();
        ctx.rect(startX, startY, gridPxW, gridPxH);
        ctx.clip();
        ctx.translate(startX, startY);
        drawElevationOverlay(ctx, gridPxW, gridPxH, _locIdx, type);
        ctx.restore();

        drawHazardBlobs(ctx, W, H);

        const locName = document.getElementById('locationName')?.textContent || '';
        const zoomScale = 1 + _zoom * 0.4;
        const markerScale = 1.0 / Math.max(0.5, zoomScale);
        drawWaypoints(ctx, W, H, _locIdx);
        drawMarker(ctx, W / 2, H / 2, locName, markerScale);

        drawVignette(ctx, W, H);

        ctx.restore();

        drawScaleBar(ctx, W, H, ZOOM);

        const zoomLabel = (1 + _zoom * 0.4).toFixed(1);
        const info = document.getElementById('moonMapInfo');
        if (info) info.textContent = `Lat: ${lat.toFixed(2)}°  Lon: ${lon.toFixed(2)}°  |  Zoom: ${zoomLabel}×  |  LRO WAC`;
    }

    function scheduleDraw() {
        if (_pendingDraw) return;
        _pendingDraw = true;
        requestAnimationFrame(() => { _pendingDraw = false; render(); });
    }

    let _lastAnimTs = 0;
    function _startAnim() {
        if (_animFrame) return;
        const step = (ts) => {
            const hasHazards = !!(window.hazardData && getSelectedOverlays().length);
            const minDt = hasHazards ? 33 : 80;
            if (ts - _lastAnimTs >= minDt) {
                _lastAnimTs = ts;
                _blobPhase = (_blobPhase + (hasHazards ? 0.05 : 0.03)) % (Math.PI * 2);
                render();
            }
            _animFrame = requestAnimationFrame(step);
        };
        _animFrame = requestAnimationFrame(step);
    }

    function _stopAnim() {
        if (_animFrame) { cancelAnimationFrame(_animFrame); _animFrame = null; }
    }

    function refreshHazardAnim() {
        if (window.hazardData && getSelectedOverlays().length) _startAnim();
        else if (!_animFrame) _startAnim();
        scheduleDraw();
    }

    function init(canvas) {
        _canvas = canvas;
        _ctx = canvas.getContext('2d');

        canvas.addEventListener('mousedown', e => {
            _dragging = true; _lastX = e.clientX; _lastY = e.clientY;
            canvas.style.cursor = 'grabbing';
        });
        canvas.addEventListener('mousemove', e => {
            if (!_dragging) return;
            const dx = e.clientX - _lastX;
            const dy = e.clientY - _lastY;
            _lastX = e.clientX; _lastY = e.clientY;
            
            const zoomScale = 1 + _zoom * 0.4;
            const scaledGridSize = GRID * TILE_SIZE * zoomScale;
            
            if (scaledGridSize > _canvas.width) {
                const maxPanX = (scaledGridSize - _canvas.width) / 2;
                _offX = Math.max(-maxPanX, Math.min(maxPanX, _offX + dx));
            } else {
                _offX = 0;
            }
            
            if (scaledGridSize > _canvas.height) {
                const maxPanY = (scaledGridSize - _canvas.height) / 2;
                _offY = Math.max(-maxPanY, Math.min(maxPanY, _offY + dy));
            } else {
                _offY = 0;
            }
            
            scheduleDraw();
        });
        const endDrag = () => { _dragging = false; canvas.style.cursor = 'crosshair'; };
        canvas.addEventListener('mouseup', endDrag);
        canvas.addEventListener('mouseleave', endDrag);

        canvas.addEventListener('wheel', e => {
            e.preventDefault();
            const newZoom = Math.max(0, Math.min(8, _zoom + (e.deltaY < 0 ? 0.3 : -0.3)));
            const zoomScale = 1 + newZoom * 0.4;
            const scaledGridSize = GRID * TILE_SIZE * zoomScale;
            
            if (scaledGridSize <= _canvas.width && scaledGridSize <= _canvas.height) {
                _offX = 0;
                _offY = 0;
            }
            
            _zoom = newZoom;
            scheduleDraw();
        }, { passive: false });

        let lastTouchDist = null;
        canvas.addEventListener('touchstart', e => {
            if (e.touches.length === 1) { _dragging = true; _lastX = e.touches[0].clientX; _lastY = e.touches[0].clientY; }
            if (e.touches.length === 2) { lastTouchDist = Math.hypot(e.touches[0].clientX - e.touches[1].clientX, e.touches[0].clientY - e.touches[1].clientY); }
        }, { passive: true });
        canvas.addEventListener('touchmove', e => {
            e.preventDefault();
            if (e.touches.length === 1 && _dragging) {
                const dx = e.touches[0].clientX - _lastX;
                const dy = e.touches[0].clientY - _lastY;
                _lastX = e.touches[0].clientX; _lastY = e.touches[0].clientY;
                
                const zoomScale = 1 + _zoom * 0.4;
                const scaledGridSize = GRID * TILE_SIZE * zoomScale;
                
                if (scaledGridSize > _canvas.width) {
                    const maxPanX = (scaledGridSize - _canvas.width) / 2;
                    _offX = Math.max(-maxPanX, Math.min(maxPanX, _offX + dx));
                } else {
                    _offX = 0;
                }
                
                if (scaledGridSize > _canvas.height) {
                    const maxPanY = (scaledGridSize - _canvas.height) / 2;
                    _offY = Math.max(-maxPanY, Math.min(maxPanY, _offY + dy));
                } else {
                    _offY = 0;
                }
                
                scheduleDraw();
            }
            if (e.touches.length === 2 && lastTouchDist !== null) {
                const d = Math.hypot(e.touches[0].clientX - e.touches[1].clientX, e.touches[0].clientY - e.touches[1].clientY);
                _zoom = Math.max(0, Math.min(8, _zoom + (d - lastTouchDist) * 0.02));
                lastTouchDist = d;
                scheduleDraw();
            }
        }, { passive: false });
        canvas.addEventListener('touchend', () => { _dragging = false; lastTouchDist = null; });
    }

    function setLocation(idx) {
        _locIdx = Math.max(0, Math.min(LOCS.length - 1, idx));
        _zoom = 0; _offX = 0; _offY = 0;
        _cachedTiles = null;
        _cachedLocIdx = -1;
        _initialLoadDone = false;
        resize();
        const [lat, lon] = LOCS[_locIdx];
        const { row: cr, col: cc } = latLonToTile(lat, lon, ZOOM);
        const half = Math.floor(GRID / 2);
        for (let dr = -half; dr <= half; dr++)
            for (let dc = -half; dc <= half; dc++)
                loadTile(tileUrl(cr + dr, cc + dc, ZOOM));
        scheduleDraw();
    }

    function resize() {
        if (!_canvas) return;
        const container = _canvas.parentElement;
        if (!container) return;
        const rect = container.getBoundingClientRect();
        const w = Math.max(1, Math.round(rect.width || container.clientWidth || container.offsetWidth || 800));
        const h = Math.max(1, Math.round(rect.height || container.clientHeight || container.offsetHeight || 500));
        if (_canvas.width !== w || _canvas.height !== h) {
            _canvas.width = w;
            _canvas.height = h;
        }
        scheduleDraw();
    }

    function zoomIn()  { _zoom = Math.min(8, _zoom + 0.5); scheduleDraw(); }
    function zoomOut() { _zoom = Math.max(0, _zoom - 0.5); scheduleDraw(); }
    function reset()   { _zoom = 0; _offX = 0; _offY = 0; scheduleDraw(); }
    function redraw()  { refreshHazardAnim(); }

    return { init, setLocation, resize, zoomIn, zoomOut, reset, redraw, refreshHazardAnim };
})();
