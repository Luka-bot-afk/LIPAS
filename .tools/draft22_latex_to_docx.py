#!/usr/bin/env python3
"""Build editable Times New Roman 12pt Draft 22 DOCX from Elsevier LaTeX sections."""
from __future__ import annotations

import re
import shutil
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

ROOT = Path("/Users/lukatakki/Documents/L.I.P.A.S. V3")
SEC = ROOT / "papers" / "elsevier" / "sections"
FIG = ROOT / "papers" / "elsevier" / "figures"
MAIN = ROOT / "papers" / "elsevier" / "main.tex"

OUTS = [
    Path("/Users/lukatakki/Downloads/LIPAS article draft 22.docx"),
    Path("/Users/lukatakki/Desktop/LIPAS article draft 22.docx"),
    Path("/Users/lukatakki/Desktop/papers/LIPAS article draft 22.docx"),
    ROOT / "papers" / "LIPAS article draft 22.docx",
]

BODY_FONT = "Times New Roman"
BODY_PT = 12


def set_run_font(run, *, bold=False, italic=False, size=BODY_PT, font=BODY_FONT):
    run.font.name = font
    run._element.rPr.rFonts.set(qn("w:eastAsia"), font)
    run.font.size = Pt(size)
    run.bold = bold
    run.italic = italic
    run.font.color.rgb = RGBColor(0, 0, 0)


def add_para(doc, text, *, bold=False, italic=False, size=BODY_PT, space_after=8, align=None):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_after = Pt(space_after)
    pf.space_before = Pt(0)
    pf.line_spacing_rule = WD_LINE_SPACING.SINGLE
    if align is not None:
        p.alignment = align
    run = p.add_run(text)
    set_run_font(run, bold=bold, italic=italic, size=size)
    return p


def brace_arg(s: str, start: int) -> tuple[str, int]:
    """Return content of {...} starting at s[start]=='{' and index after closing brace."""
    assert s[start] == "{"
    depth = 0
    for i in range(start, len(s)):
        if s[i] == "{":
            depth += 1
        elif s[i] == "}":
            depth -= 1
            if depth == 0:
                return s[start + 1 : i], i + 1
    return s[start + 1 :], len(s)


def replace_cmd_args(s: str, cmd: str, repl) -> str:
    """Replace \\cmd{...} with repl(inner), supporting one-level nested braces."""
    out = []
    i = 0
    token = "\\" + cmd
    while i < len(s):
        if s.startswith(token, i) and (i + len(token) >= len(s) or not s[i + len(token)].isalpha()):
            j = i + len(token)
            while j < len(s) and s[j].isspace():
                j += 1
            if j < len(s) and s[j] == "{":
                inner, j2 = brace_arg(s, j)
                out.append(repl(inner))
                i = j2
                continue
        out.append(s[i])
        i += 1
    return "".join(out)


def strip_tex(s: str) -> str:
    s = s.replace("\u00ad", "")
    s = re.sub(r"(?<!\\)%.*", "", s)
    # citations / refs
    s = re.sub(r"\\citep[tp]?\{[^}]*\}", "", s)
    s = re.sub(r"\\label\{[^}]*\}", "", s)
    s = re.sub(r"(?:Figures?|Figs?\.?|Sections?|Eqs?\.?|Appendices|Appendix)~?\\ref\{[^}]*\}", lambda m: re.sub(r"~?\\ref\{[^}]*\}", "", m.group(0)).strip(), s)
    s = re.sub(r"\\ref\{[^}]*\}", "", s)
    s = re.sub(r"\\eqref\{[^}]*\}", "the equation", s)
    # formatting macros with nested braces
    for cmd in ("textbf", "textit", "emph", "texttt", "path", "url"):
        s = replace_cmd_args(s, cmd, lambda inner: inner)
    s = re.sub(r"\\href\{[^}]*\}\{([^{}]*)\}", r"\1", s)
    # math-ish cleanup
    s = s.replace(r"\,", " ")
    s = s.replace(r"\ ", " ")
    s = s.replace(r"\&", "&")
    s = s.replace(r"\%", "%")
    s = s.replace(r"\_", "_")
    s = s.replace(r"\#", "#")
    s = s.replace("---", "—")
    s = s.replace("--", "–")
    s = s.replace("~", " ")
    s = s.replace("``", '"').replace("''", '"')
    s = s.replace(r"\ldots", "...")
    s = s.replace(r"\dots", "...")
    s = re.sub(r"\$([^$]*)\$", lambda m: clean_math(m.group(1)), s)
    # remaining simple macros
    s = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?", "", s)
    s = s.replace("{", "").replace("}", "")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    s = re.sub(r"\s+\.", ".", s)
    s = re.sub(r"\s+,", ",", s)
    return s.strip()


def clean_math(m: str) -> str:
    # nested frac / sqrt first
    changed = True
    while changed:
        changed = False
        def frac_repl(match):
            nonlocal changed
            changed = True
            a, rest = brace_arg(match.string, match.end() - 1)
            # match ends at first '{'; re-find properly below
            return match.group(0)
        # iterative balanced frac
        while True:
            idx = m.find(r"\frac")
            if idx < 0:
                break
            j = idx + len(r"\frac")
            while j < len(m) and m[j].isspace():
                j += 1
            if j >= len(m) or m[j] != "{":
                m = m[:idx] + "frac" + m[idx + 5 :]
                continue
            num, j2 = brace_arg(m, j)
            while j2 < len(m) and m[j2].isspace():
                j2 += 1
            if j2 >= len(m) or m[j2] != "{":
                m = m[:idx] + f"({num})" + m[j2:]
                continue
            den, j3 = brace_arg(m, j2)
            m = m[:idx] + f"({clean_math(num)})/({clean_math(den)})" + m[j3:]
        while True:
            idx = m.find(r"\sqrt")
            if idx < 0:
                break
            j = idx + len(r"\sqrt")
            while j < len(m) and m[j].isspace():
                j += 1
            if j < len(m) and m[j] == "{":
                inner, j2 = brace_arg(m, j)
                m = m[:idx] + f"sqrt({clean_math(inner)})" + m[j2:]
            else:
                m = m[:idx] + "sqrt" + m[j:]
        break
    m = m.replace(r"\mathrm", "")
    m = m.replace(r"\mathbf", "")
    m = m.replace(r"\Delta", "Delta")
    m = replace_cmd_args(m, "hat", lambda inner: f"{inner}hat")
    m = re.sub(r"\\hat\{([^{}]+)\}", r"\1hat", m)
    m = re.sub(r"\\hat([A-Za-z])", r"\1hat", m)
    m = m.replace(r"\max", "max")
    m = m.replace(r"\min", "min")
    m = m.replace(r"\times", "×")
    m = m.replace(r"\cdot", "·")
    m = m.replace(r"\sum", "sum")
    m = m.replace(r"\left", "")
    m = m.replace(r"\right", "")
    m = m.replace(r"\!", "")
    m = m.replace(r"\,", " ")
    m = m.replace(r"\;", " ")
    m = m.replace(r"\ ", " ")
    m = re.sub(r"_\{([^{}]+)\}", r"_\1", m)
    m = re.sub(r"\^\{([^{}]+)\}", r"^\1", m)
    m = replace_cmd_args(m, "mathrm", lambda inner: inner)
    m = replace_cmd_args(m, "mathbf", lambda inner: inner)
    m = re.sub(r"\\[a-zA-Z]+", "", m)
    m = m.replace("{", "").replace("}", "")
    m = m.replace("\\", "")
    m = re.sub(r"\s+", " ", m)
    return m.strip()


def clean_equation(body: str) -> str:
    body = re.sub(r"\\label\{[^}]*\}", "", body)
    body = body.replace("&", " ")
    body = clean_math(body)
    body = re.sub(r"\s+", " ", body).strip()
    if body and not body.startswith("Eq"):
        body = f"Eq.: {body}"
    return body


def extract_abstract(main_tex: str) -> str:
    m = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", main_tex, re.S)
    return strip_tex(m.group(1)) if m else ""


def extract_title(main_tex: str) -> str:
    m = re.search(r"\\title\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}", main_tex)
    return strip_tex(m.group(1)) if m else "LIPAS manuscript"


FIG_MAP = {
    "fig_architecture_data_path.png": "fig_architecture_data_path.png",
    "fig_architecture_blend.png": "fig_architecture_blend.png",
    "fig_prototype_lipas_vs_flagship.png": "fig_prototype_lipas_vs_flagship.png",
    "fig_lipas_vs_diviner.png": "fig_lipas_vs_diviner.png",
    "fig_windowA_skill.png": "fig_windowA_skill.png",
    "fig_windowB_skill.png": "fig_windowB_skill.png",
    "fig_mission_timeline.png": "fig_mission_timeline.png",
}


def parse_section(path: Path):
    """Yield structured blocks from a .tex section file."""
    text = path.read_text(encoding="utf-8")
    # remove comments
    lines = []
    for line in text.splitlines():
        if re.match(r"^\s*%", line):
            continue
        lines.append(re.sub(r"(?<!\\)%.*", "", line))
    text = "\n".join(lines)

    # split figures out
    parts = re.split(r"(\\begin\{figure\}.*?\\end\{figure\})", text, flags=re.S)
    for part in parts:
        if part.startswith(r"\begin{figure}"):
            cap = None
            cidx = part.find(r"\caption")
            if cidx >= 0:
                j = cidx + len(r"\caption")
                while j < len(part) and part[j].isspace():
                    j += 1
                if j < len(part) and part[j] == "{":
                    cap_txt, _ = brace_arg(part, j)
                    cap = cap_txt
            include = re.search(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]*)\}", part)
            yield ("figure", {
                "file": include.group(1) if include else None,
                "caption": strip_tex(cap) if cap else "",
            })
            continue
        # equations
        subparts = re.split(r"(\\begin\{equation\}.*?\\end\{equation\})", part, flags=re.S)
        for sp in subparts:
            if sp.startswith(r"\begin{equation}"):
                body = re.sub(r"\\begin\{equation\}|\\end\{equation\}", "", sp)
                yield ("equation", clean_equation(body))
                continue
            # verbatim
            vparts = re.split(r"(\\begin\{verbatim\}.*?\\end\{verbatim\})", sp, flags=re.S)
            for vp in vparts:
                if vp.startswith(r"\begin{verbatim}"):
                    body = re.sub(r"\\begin\{verbatim\}|\\end\{verbatim\}", "", vp)
                    yield ("verbatim", body.strip("\n"))
                    continue
                # enumerate
                if r"\begin{enumerate}" in vp:
                    # strip enumerate env, keep item texts
                    vp2 = re.sub(r"\\begin\{enumerate\}.*?\\end\{enumerate\}", lambda m: flatten_enum(m.group(0)), vp, flags=re.S)
                    yield from emit_prose(vp2)
                else:
                    yield from emit_prose(vp)


def flatten_enum(block: str) -> str:
    items = re.findall(r"\\item(?:\[[^\]]*\])?\s*(.*?)(?=\\item|\Z)", block, re.S)
    out = []
    for i, it in enumerate(items, 1):
        # drop nested begin/end
        it = re.sub(r"\\begin\{.*?\}|\\end\{.*?\}", "", it)
        t = strip_tex(it)
        if t:
            # try RQ label
            m = re.match(r"RQ(\d)\s*(.*)", t, re.S)
            if m:
                out.append(f"RQ{m.group(1)}. {m.group(2).strip()}")
            else:
                out.append(f"{i}. {t}")
    return "\n\n".join(out)


def emit_prose(chunk: str):
    # section / subsection headings
    for m in re.finditer(
        r"\\((?:sub)*section)\*?\{([^{}]*)\}|\\paragraph\*?\{([^{}]*)\}|(?:^|\n)([^\n\\][^\n]*)",
        chunk,
    ):
        pass
    # simpler line-oriented parse
    buf = []
    for raw in chunk.splitlines():
        line = raw.strip()
        if not line:
            if buf:
                yield ("para", strip_tex(" ".join(buf)))
                buf = []
            continue
        m = re.match(r"\\(section|subsection|subsubsection)\*?\{(.+)\}\s*$", line)
        if m:
            if buf:
                yield ("para", strip_tex(" ".join(buf)))
                buf = []
            level = {"section": 1, "subsection": 2, "subsubsection": 3}[m.group(1)]
            yield ("heading", level, strip_tex(m.group(2)))
            continue
        if line.startswith(r"\appendix"):
            if buf:
                yield ("para", strip_tex(" ".join(buf)))
                buf = []
            yield ("heading", 1, "Appendix")
            continue
        if line.startswith("\\") and not line.startswith(r"\textbf") and not line.startswith(r"\textit"):
            # skip pure command lines that aren't text-bearing
            if re.match(r"^\\[a-zA-Z]+(\[[^\]]*\])?(\{.*\})?$", line) and " " not in strip_tex(line):
                # may still contain text in args handled elsewhere
                if any(k in line for k in ("noindent", "vspace", "hspace", "newpage", "clearpage", "FloatBarrier")):
                    continue
        buf.append(line)
    if buf:
        yield ("para", strip_tex(" ".join(buf)))


def add_figure(doc, meta):
    fname = meta.get("file")
    cap = meta.get("caption") or ""
    if fname:
        # strip path
        base = Path(fname).name
        path = FIG / base
        if path.exists():
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = p.add_run()
            run.add_picture(str(path), width=Inches(5.8))
            for r in p.runs:
                set_run_font(r)
    if cap:
        add_para(doc, f"Figure. {cap}", italic=True, space_after=12)


def build():
    main_tex = MAIN.read_text(encoding="utf-8")
    doc = Document()
    # default style
    style = doc.styles["Normal"]
    style.font.name = BODY_FONT
    style.font.size = Pt(BODY_PT)
    style._element.rPr.rFonts.set(qn("w:eastAsia"), BODY_FONT)
    pf = style.paragraph_format
    pf.space_after = Pt(8)
    pf.line_spacing_rule = WD_LINE_SPACING.SINGLE

    for sname in ("Heading 1", "Heading 2", "Heading 3"):
        if sname in doc.styles:
            hs = doc.styles[sname]
            hs.font.name = BODY_FONT
            hs.font.size = Pt(BODY_PT)
            hs.font.bold = True
            hs.font.color.rgb = RGBColor(0, 0, 0)
            hs._element.rPr.rFonts.set(qn("w:eastAsia"), BODY_FONT)

    title = extract_title(main_tex)
    add_para(doc, title, bold=True, size=BODY_PT, space_after=6, align=WD_ALIGN_PARAGRAPH.CENTER)
    add_para(doc, "Luka Takki", size=BODY_PT, space_after=4, align=WD_ALIGN_PARAGRAPH.CENTER)
    add_para(doc, "lukatakki123@gmail.com", size=BODY_PT, space_after=12, align=WD_ALIGN_PARAGRAPH.CENTER)

    add_para(doc, "Abstract", bold=True, space_after=4)
    add_para(doc, extract_abstract(main_tex), space_after=12)

    keywords = re.search(r"\\begin\{keyword\}(.*?)\\end\{keyword\}", main_tex, re.S)
    if keywords:
        kw = strip_tex(keywords.group(1).replace(r"\sep", ";"))
        add_para(doc, f"Keywords: {kw}", italic=True, space_after=14)

    section_files = [
        "introduction.tex",
        "methods_brief.tex",
        "results.tex",
        "discussion.tex",
        "future_work.tex",
        "conclusion.tex",
        "declarations.tex",
        "appendices.tex",
    ]

    appendix_mode = False
    letter = ord("A")

    for sf in section_files:
        path = SEC / sf
        for item in parse_section(path):
            kind = item[0]
            if kind == "heading":
                level, text = item[1], item[2]
                if text.strip().lower() == "appendix":
                    appendix_mode = True
                    continue
                if appendix_mode and level == 1:
                    text = f"Appendix {chr(letter)}. {text}"
                    letter += 1
                # Same font SIZE as body; bold only for hierarchy
                add_para(doc, text, bold=True, size=BODY_PT, space_after=6)
            elif kind == "para":
                text = item[1]
                if not text:
                    continue
                # drop leftover latex artifacts
                if text in ("t", "H", "ht") or re.fullmatch(r"\[.?\]", text):
                    continue
                if text.startswith("[") and len(text) < 8:
                    continue
                add_para(doc, text, size=BODY_PT)
            elif kind == "figure":
                add_figure(doc, item[1])
            elif kind == "equation":
                add_para(doc, item[1], italic=True, align=WD_ALIGN_PARAGRAPH.CENTER)
            elif kind == "verbatim":
                for line in item[1].splitlines() or [""]:
                    p = doc.add_paragraph()
                    p.paragraph_format.space_after = Pt(0)
                    p.paragraph_format.space_before = Pt(0)
                    run = p.add_run(line if line else " ")
                    # Same size as body; monospace for editability of commands
                    set_run_font(run, size=BODY_PT, font="Courier New")
                doc.add_paragraph()

    # ensure directory targets
    Path("/Users/lukatakki/Desktop/papers").mkdir(parents=True, exist_ok=True)
    primary = OUTS[0]
    doc.save(str(primary))
    for dest in OUTS[1:]:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(primary, dest)
        print("Wrote", dest)
    print("Wrote", primary)


if __name__ == "__main__":
    build()
