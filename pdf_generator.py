"""LIPAS."""
from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

def _safe(val: Any, default: str = "-") -> str:
    if val is None:
        return default
    if isinstance(val, float):
        return f"{val:.4g}"
    return str(val)

def _status_label(status: str) -> str:
    s = (status or "").lower()
    if s in ("go", "green", "safe"):
        return "GO - EVA APPROVED"
    if s in ("caution", "yellow", "moderate"):
        return "CAUTION - LIMITED EVA"
    if s in ("nogo", "no-go", "red", "unsafe"):
        return "NO-GO - SHELTER / HOLD"
    return (status or "UNKNOWN").upper()

def generate_mission_pdf(plan: Dict[str, Any]) -> bytes:
    """Return PDF bytes for the given mission plan dict."""
    try:
        return _generate_with_reportlab(plan)
    except Exception:
        return _generate_minimal_pdf(plan)

def _generate_with_reportlab(plan: Dict[str, Any]) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
        HRFlowable,
    )

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title="L.I.P.A.S. Mission Plan",
    )

    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "LipasTitle",
        parent=styles["Heading1"],
        fontSize=20,
        textColor=colors.HexColor("#0a2540"),
        spaceAfter=4,
        fontName="Helvetica-Bold",
    )
    subtitle = ParagraphStyle(
        "LipasSub",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.HexColor("#3d5a80"),
        spaceAfter=10,
    )
    h2 = ParagraphStyle(
        "LipasH2",
        parent=styles["Heading2"],
        fontSize=12,
        textColor=colors.HexColor("#0077c8"),
        spaceBefore=10,
        spaceAfter=6,
        fontName="Helvetica-Bold",
    )
    body = ParagraphStyle(
        "LipasBody",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.HexColor("#1a1a2e"),
        leading=12,
    )
    small = ParagraphStyle(
        "LipasSmall",
        parent=styles["Normal"],
        fontSize=8,
        textColor=colors.HexColor("#5a6a7a"),
        leading=10,
    )

    site = plan.get("site") or {}
    eva_now = plan.get("eva_now") or {}
    conditions = plan.get("conditions") or {}
    windows = plan.get("eva_windows") or []
    zones = plan.get("landing_zones") or []
    dose = plan.get("dose") or {}
    generated = plan.get("generated_at") or datetime.now(timezone.utc).isoformat()

    story: List[Any] = []
    story.append(Paragraph("L.I.P.A.S. - Lunar Mission Plan", title))
    story.append(
        Paragraph(
            "Hazard-informed EVA windows · Landing zone ranking · Crew dose estimate",
            subtitle,
        )
    )
    story.append(
        HRFlowable(width="100%", thickness=1, color=colors.HexColor("#0077c8"), spaceAfter=8)
    )

    story.append(Paragraph("1. Mission Parameters", h2))
    params_data = [
        ["Site / Callsign", _safe(site.get("name"), "Custom coordinates")],
        ["Latitude", f"{float(site.get('lat', 0)):.4f}°"],
        ["Longitude", f"{float(site.get('lon', 0)):.4f}°"],
        ["EVA duration", f"{_safe(plan.get('eva_duration_h'))} h"],
        ["Mission length", f"{_safe(plan.get('mission_days'))} days"],
        ["Risk posture", _safe(plan.get("risk_posture"), "nominal").upper()],
        ["Generated (UTC)", generated],
    ]
    t = Table(params_data, colWidths=[55 * mm, 120 * mm])
    t.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#1a1a2e")),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("LINEBELOW", (0, 0), (-1, -2), 0.25, colors.HexColor("#d0d8e0")),
            ]
        )
    )
    story.append(t)

    story.append(Paragraph("2. EVA Safety - Current Window", h2))
    story.append(
        Paragraph(
            f"<b>{_status_label(eva_now.get('status'))}</b> - "
            f"Score {_safe(eva_now.get('score'))}/100 · "
            f"{_safe(eva_now.get('summary'), 'No summary')}",
            body,
        )
    )
    reasons = eva_now.get("reasons") or []
    if reasons:
        for r in reasons:
            story.append(Paragraph(f"• {_safe(r)}", small))

    story.append(Paragraph("3. Predicted Surface Conditions", h2))
    cond_rows = [
        ["Metric", "Value"],
        ["Radiation", f"{_safe(conditions.get('radiation'))} mSv/h"],
        ["Temperature", f"{_safe(conditions.get('temperature'))} °C"],
        ["Dust density", f"{_safe(conditions.get('dust'))} g/cm³"],
        ["Solar activity", _safe(conditions.get("solar"))],
        ["Moonquakes / day", _safe(conditions.get("moonquakes"))],
        ["Micrometeorite index", _safe(conditions.get("micrometeorites"))],
        ["Illumination", f"{_safe(conditions.get('illumination_pct'))}%"],
        ["Model plausibility", f"{_safe(conditions.get('plausibility'))}"],
    ]
    ct = Table(cond_rows, colWidths=[55 * mm, 120 * mm])
    ct.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0a2540")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f4f7fa"), colors.white]),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#c8d2dc")),
            ]
        )
    )
    story.append(ct)

    story.append(Paragraph("4. Recommended EVA Windows (next 24 h)", h2))
    if not windows:
        story.append(Paragraph("No EVA windows computed for the requested duration.", body))
    else:
        wrows = [["Rank", "UTC Window", "Risk", "Avg Rad", "Score"]]
        for i, w in enumerate(windows[:8], 1):
            wrows.append(
                [
                    str(i),
                    _safe(w.get("label")),
                    _safe(w.get("risk"), "?").upper(),
                    f"{_safe(w.get('avg_radiation'))} mSv/h",
                    _safe(w.get("score")),
                ]
            )
        wt = Table(wrows, colWidths=[15 * mm, 55 * mm, 28 * mm, 40 * mm, 25 * mm])
        wt.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0077c8")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#eef5fb"), colors.white]),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#c8d2dc")),
                ]
            )
        )
        story.append(wt)

    story.append(Paragraph("5. Ranked Landing Zones", h2))
    if not zones:
        story.append(Paragraph("No landing zones ranked.", body))
    else:
        zrows = [["Rank", "Zone", "Lat / Lon", "Safety", "Notes"]]
        for i, z in enumerate(zones[:10], 1):
            zrows.append(
                [
                    str(i),
                    _safe(z.get("name")),
                    f"{float(z.get('lat', 0)):.2f}°, {float(z.get('lon', 0)):.2f}°",
                    f"{_safe(z.get('safety_pct'))}%",
                    _safe(z.get("notes"), "")[:42],
                ]
            )
        zt = Table(zrows, colWidths=[12 * mm, 42 * mm, 38 * mm, 18 * mm, 60 * mm])
        zt.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0a2540")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f4f7fa"), colors.white]),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#c8d2dc")),
                ]
            )
        )
        story.append(zt)

    story.append(Paragraph("6. Crew Dose Estimate", h2))
    story.append(
        Paragraph(
            f"Total mission dose ≈ <b>{_safe(dose.get('total_mSv'))} mSv</b> "
            f"({_safe(dose.get('risk'))} risk) · "
            f"EVA share {_safe(dose.get('eva_mSv'))} mSv · "
            f"Habitat share {_safe(dose.get('habitat_mSv'))} mSv · "
            f"NASA career male limit used {_safe(dose.get('pct_male'))}% / "
            f"female {_safe(dose.get('pct_female'))}%",
            body,
        )
    )

    hourly = plan.get("hourly") or []
    if hourly:
        story.append(Paragraph("7. 24 h Hazard Trend (Radiation · Solar · Dust)", h2))
        try:
            from reportlab.graphics.shapes import Drawing, Line, PolyLine, String, Rect

            w, h = 460, 150
            d = Drawing(w, h)
            d.add(Rect(0, 0, w, h, fillColor=colors.HexColor("#f4f7fa"), strokeColor=colors.HexColor("#c8d2dc")))
            pad_l, pad_r, pad_t, pad_b = 36, 12, 14, 22
            plot_w = w - pad_l - pad_r
            plot_h = h - pad_t - pad_b

            def series(key):
                vals = [float(x.get(key) or 0) for x in hourly[:48]]
                return vals or [0.0]

            rad = series("radiation")
            sol = series("solar")
            dus = series("dust")

            def norm(vals):
                lo, hi = min(vals), max(vals)
                if hi - lo < 1e-9:
                    return [0.5] * len(vals)
                return [(v - lo) / (hi - lo) for v in vals]

            def polyline(vals, color):
                n = max(1, len(vals) - 1)
                pts = []
                for i, v in enumerate(norm(vals)):
                    x = pad_l + (i / n) * plot_w
                    y = pad_b + v * plot_h
                    pts.extend([x, y])
                d.add(PolyLine(pts, strokeColor=color, strokeWidth=1.6))

            d.add(Line(pad_l, pad_b, pad_l + plot_w, pad_b, strokeColor=colors.HexColor("#8fa3b8"), strokeWidth=0.6))
            d.add(Line(pad_l, pad_b, pad_l, pad_b + plot_h, strokeColor=colors.HexColor("#8fa3b8"), strokeWidth=0.6))
            polyline(rad, colors.HexColor("#e25b5b"))
            polyline(sol, colors.HexColor("#e0b14a"))
            polyline(dus, colors.HexColor("#c8a86a"))
            d.add(String(pad_l, h - 10, "Radiation", fontSize=7, fillColor=colors.HexColor("#e25b5b")))
            d.add(String(pad_l + 58, h - 10, "Solar", fontSize=7, fillColor=colors.HexColor("#e0b14a")))
            d.add(String(pad_l + 96, h - 10, "Dust", fontSize=7, fillColor=colors.HexColor("#c8a86a")))
            d.add(String(pad_l, 6, "T+0h", fontSize=6, fillColor=colors.HexColor("#5c7088")))
            d.add(String(pad_l + plot_w - 28, 6, f"T+{len(rad)-1}h", fontSize=6, fillColor=colors.HexColor("#5c7088")))
            story.append(Spacer(1, 4))
            story.append(d)
            story.append(
                Paragraph(
                    "Normalized 0-1 per channel for shape comparison (native units differ).",
                    small,
                )
            )
        except Exception:
            story.append(Paragraph("Hourly series available but chart render skipped.", small))

    story.append(Spacer(1, 10))
    story.append(
        HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#a0b0c0"), spaceAfter=6)
    )
    story.append(
        Paragraph(
            "L.I.P.A.S. - Lunar Intelligence Platform & Analysis System · "
            "Physics + ML hybrid (physics_weight locked) · "
            "Sources: NASA DONKI · NOAA SWPC · LRO/Diviner · CRaTER · LADEE/LDEX · Apollo PSE",
            small,
        )
    )
    story.append(
        Paragraph(
            "Advisory only - not a substitute for flight-rule clearance from Mission Control.",
            small,
        )
    )

    doc.build(story)
    return buf.getvalue()

def _escape_pdf_text(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
        .replace("\r", " ")
        .replace("\n", " ")
    )

def _generate_minimal_pdf(plan: Dict[str, Any]) -> bytes:
    """Dependency-free single-page text PDF."""
    site = plan.get("site") or {}
    eva_now = plan.get("eva_now") or {}
    conditions = plan.get("conditions") or {}
    windows = plan.get("eva_windows") or []
    zones = plan.get("landing_zones") or []
    dose = plan.get("dose") or {}
    generated = plan.get("generated_at") or datetime.now(timezone.utc).isoformat()

    lines = [
        "L.I.P.A.S. - LUNAR MISSION PLAN",
        "Hazard-informed EVA windows / landing zones / crew dose",
        "",
        f"Site: {_safe(site.get('name'), 'Custom')}  Lat {float(site.get('lat', 0)):.4f}  Lon {float(site.get('lon', 0)):.4f}",
        f"EVA duration: {_safe(plan.get('eva_duration_h'))} h   Mission: {_safe(plan.get('mission_days'))} days",
        f"Risk posture: {_safe(plan.get('risk_posture'), 'nominal').upper()}   Generated: {generated}",
        "",
        f"EVA NOW: {_status_label(eva_now.get('status'))}  Score {_safe(eva_now.get('score'))}/100",
        _safe(eva_now.get("summary"), ""),
        "",
        "CONDITIONS",
        f"  Radiation: {_safe(conditions.get('radiation'))} mSv/h",
        f"  Temperature: {_safe(conditions.get('temperature'))} C",
        f"  Dust: {_safe(conditions.get('dust'))} g/cm3",
        f"  Solar: {_safe(conditions.get('solar'))}  Quakes: {_safe(conditions.get('moonquakes'))}",
        "",
        "TOP EVA WINDOWS",
    ]
    for i, w in enumerate(windows[:6], 1):
        lines.append(
            f"  {i}. {_safe(w.get('label'))}  {_safe(w.get('risk')).upper()}  "
            f"rad {_safe(w.get('avg_radiation'))}  score {_safe(w.get('score'))}"
        )
    lines.append("")
    lines.append("RANKED LANDING ZONES")
    for i, z in enumerate(zones[:8], 1):
        lines.append(
            f"  {i}. {_safe(z.get('name'))}  "
            f"{float(z.get('lat', 0)):.2f},{float(z.get('lon', 0)):.2f}  "
            f"{_safe(z.get('safety_pct'))}%  {_safe(z.get('notes'), '')[:40]}"
        )
    lines.append("")
    lines.append(
        f"DOSE: total {_safe(dose.get('total_mSv'))} mSv  "
        f"risk {_safe(dose.get('risk'))}  "
        f"EVA {_safe(dose.get('eva_mSv'))} / habitat {_safe(dose.get('habitat_mSv'))}"
    )
    lines.append("")
    lines.append("Advisory only - clear with Mission Control before EVA.")

    y_start = 800
    content_parts = ["BT", "/F1 10 Tf", "14 TL", f"50 {y_start} Td"]
    for i, line in enumerate(lines):
        esc = _escape_pdf_text(line[:110])
        if i == 0:
            content_parts.append("/F1 14 Tf")
            content_parts.append(f"({esc}) Tj")
            content_parts.append("/F1 10 Tf")
            content_parts.append("T*")
        else:
            content_parts.append(f"({esc}) Tj")
            content_parts.append("T*")
    content_parts.append("ET")
    stream = "\n".join(content_parts).encode("latin-1", errors="replace")

    objs: List[bytes] = []
    objs.append(b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n")
    objs.append(b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n")
    objs.append(
        b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>endobj\n"
    )
    objs.append(
        f"4 0 obj<< /Length {len(stream)} >>stream\n".encode("ascii")
        + stream
        + b"\nendstream\nendobj\n"
    )
    objs.append(b"5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n")

    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objs:
        offsets.append(out.tell())
        out.write(obj)
    xref_pos = out.tell()
    out.write(f"xref\n0 {len(objs) + 1}\n".encode("ascii"))
    out.write(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.write(f"{off:010d} 00000 n \n".encode("ascii"))
    out.write(
        f"trailer<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode(
            "ascii"
        )
    )
    return out.getvalue()

def build_filename(plan: Optional[Dict[str, Any]] = None) -> str:
    site = (plan or {}).get("site") or {}
    name = str(site.get("name") or "custom").replace(" ", "_")[:40]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"LIPAS_MissionPlan_{name}_{stamp}.pdf"
