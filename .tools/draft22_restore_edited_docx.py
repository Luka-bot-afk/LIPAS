#!/usr/bin/env python3
"""Build draft-22 DOCX = draft 21 + prompt edits only. Never replace the abstract body."""
from __future__ import annotations

import shutil
from pathlib import Path

from docx import Document

SRC = Path("/Users/lukatakki/Documents/L.I.P.A.S. V3/papers/LIPAS article draft 21.docx")
OUTS = [
    Path("/Users/lukatakki/Downloads/LIPAS article draft 22.docx"),
    Path("/Users/lukatakki/Desktop/LIPAS article draft 22.docx"),
    Path("/Users/lukatakki/Desktop/papers/LIPAS article draft 22.docx"),
    Path("/Users/lukatakki/Documents/L.I.P.A.S. V3/papers/LIPAS article draft 22.docx"),
    Path("/Users/lukatakki/Downloads/papers/LIPAS article draft 22.docx"),
    Path("/Users/lukatakki/Desktop/Downloads/papers/LIPAS article draft 22.docx"),
]

# Exact abstract second-paragraph lead-in tweak matching the edited PDF overlay.
ABS_OLD = "This study addresses three distinct research questions."
ABS_NEW = "This study aims to address three research questions."

MAP = [
    ("EV A", "EVA"),
    ("EV\u00ad A", "EVA"),
    ("EV\xa0A", "EVA"),
    ("early client", "prototype"),
    ("Early client", "Prototype"),
    ("the unified dashboard", "LIPAS"),
    ("unified dashboard", "LIPAS"),
    ("6. Results", "5. Results"),
    ("6.1. Prototype", "5.1. Prototype"),
    ("6.1.1.", "5.1.1."),
    ("6.2. Qualitative", "5.2. Qualitative"),
    ("6.3. Fourteen", "5.3. Fourteen"),
    ("6.3.1.", "5.3.1."),
    ("6.3.2.", "5.3.2."),
    ("6.4. Experiment 4: operational mission simulation", "5.4. Operational mission simulation"),
    ("6.5. Input ablation", "5.5. Input ablation"),
    ("9. Conclusion", "8. Conclusion"),
    ("8.3. Expanding solar and radiation models", "7.1. Solar and radiation models"),
    ("8.6. Operational development", "7.2. Validation and operations"),
    ("8.7. Future-work summary", "7.3. Future-work summary"),
    (
        "omitted that additional shower term",
        "did not apply the American Meteor Society (AMS) shower calendar modulation used in the LIPAS physics path",
    ),
    ("physics_estimate path", "the Python physics-estimation function"),
    ("physics_estimate function", "the Python physics-estimation function"),
]

CORRUPT = [
    "Because simultaneous",
    "solar- ersus",
    "solar­ ersus",
    "shower te",
]

ACK = (
    "The author thanks Benjamin Irani-Fey for coding support during the NASA Space Apps Challenge. "
    "The author also thanks NASA, NOAA, and other space agencies and research organizations for the public "
    "lunar-mission data and space-weather archives that made the project possible, and thanks Polygence "
    "research mentor Kyle Kennedy for support in redesigning and re-evaluating the studies, methods, and conclusions."
)

MISSION_OLD = "The GOES-only path used proton flux. The combined path took the worse of the two."
MISSION_NEW = (
    "A radiation-focused EVA compared warning times using a GOES-only proton path and a combined path "
    "that took the earlier (worse) of the GOES-only and geomagnetic/solar-driver warnings."
)
MISSION2_OLD = (
    "The run is radiation-focused. It does not show that the dashboard is safer on every hazard, "
    "and it does not replace an operator."
)
MISSION2_NEW = (
    "The exercise is radiation-focused: it does not show that LIPAS is safer on every hazard, "
    "and it does not replace an operator or flight-certified products."
)


def set_para_text(p, new: str) -> None:
    if p.runs:
        p.runs[0].text = new
        for r in p.runs[1:]:
            r.text = ""
    else:
        p.add_run(new)


def delete_paragraph(p) -> None:
    el = p._element
    parent = el.getparent()
    if parent is not None:
        parent.remove(el)


def abstract_range(paras):
    abs_i = kw_i = intro_i = None
    for i, p in enumerate(paras):
        t = p.text.strip()
        if abs_i is None and (t == "Abstract" or t.startswith("Abstract")):
            abs_i = i
        if abs_i is not None and kw_i is None and t.startswith("Keywords"):
            kw_i = i
        if abs_i is not None and intro_i is None and (
            t.startswith("1.") or t == "Introduction" or t.startswith("1 Introduction")
        ):
            intro_i = i
    end = kw_i if kw_i is not None else intro_i
    return abs_i, end


def apply_map(text: str) -> str:
    new = text.replace("\u00ad", "")
    for a, b in MAP:
        new = new.replace(a, b)
    return new


def main():
    doc = Document(str(SRC))
    abs_i, abs_end = abstract_range(doc.paragraphs)
    to_delete = []
    changed = 0

    for i, p in enumerate(list(doc.paragraphs)):
        raw = p.text
        t = raw.replace("\u00ad", "").replace("\xa0", " ")
        in_abs = abs_i is not None and abs_end is not None and abs_i <= i <= abs_end

        if any(s in t for s in CORRUPT) or "This work highlights" in t:
            to_delete.append(p)
            continue

        if "Marjo" in t or "Lipponen" in t:
            set_para_text(p, ACK)
            changed += 1
            continue

        if in_abs:
            # Only allowed abstract edit: distinct→aims lead-in. Keep everything else.
            if ABS_OLD in t:
                set_para_text(p, t.replace(ABS_OLD, ABS_NEW))
                changed += 1
            continue

        if MISSION_OLD in t:
            set_para_text(p, t.replace(MISSION_OLD, MISSION_NEW))
            changed += 1
            t = p.text
        if MISSION2_OLD in t:
            set_para_text(p, t.replace(MISSION2_OLD, MISSION2_NEW))
            changed += 1
            t = p.text

        new = apply_map(t)
        if new != t:
            set_para_text(p, new)
            changed += 1

    for p in to_delete:
        delete_paragraph(p)

    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    t = p.text.replace("\u00ad", "")
                    new = apply_map(t)
                    if new != t:
                        set_para_text(p, new)
                        changed += 1

    primary = OUTS[0]
    primary.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(primary))
    for dest in OUTS[1:]:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(primary, dest)
        print("Wrote", dest)
    print("Wrote", primary, "changed", changed, "deleted", len(to_delete))

    # verify abstract
    blob = "\n".join(p.text for p in Document(str(primary)).paragraphs)
    assert "documents how the hybrid model LIPAS was developed" in blob
    assert "browser-prototype diagnostic" not in blob
    assert "Locked studies over two 14-day windows then show modest solar gains" not in blob
    print("ABSTRACT_BODY_OK")


if __name__ == "__main__":
    main()
