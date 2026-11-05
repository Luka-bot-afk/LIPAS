#!/usr/bin/env python3
"""Patch draft27 ASR + arXiv manuscripts for combined Summer Window S + Storm Window C."""
from __future__ import annotations

from pathlib import Path

ROOT = Path("/Users/lukatakki/Documents/L.I.P.A.S. V3")

ABSTRACT = r"""LIPAS (Lunar Impact and Predictive Analysis System) is a hybrid forecasting and decision-support platform that combines machine learning with physics-based computational models to predict the Moon's space-weather conditions. These conditions include temperature, radiation, dust activity, micrometeorite impacts, solar storms, and moonquakes. By unifying space-weather data products from NASA and the National Oceanic and Atmospheric Administration (NOAA) alongside OMNI2 data, the LIPAS platform processes the data through a temporal Long Short-Term Memory (LSTM) neural network. Users can view the LIPAS space-weather predictions via an interactive, web-based dashboard for any lunar location.

This study addresses three research questions. First, it documents how the hybrid LIPAS model was developed and what was learned in that process. Second, it examines whether a unified multi-hazard system can support operational decision-making in a controlled mission simulation used alongside existing public NASA and NOAA products. Third, it tests whether the locked hybrid improves prediction for selected hazards relative to selected replicated public baselines and physics-only references. The quantitative evaluation now reports a combined summer 2026 Window~S (17~June to 4~August; 138 site-days after a three-day gap) and a one-month disturbed Window~C (1--28~May 2024; 84 site-days), under an updated serve policy with storm-aware adaptive gating; the locked train-2 weights are unchanged. The contribution evaluated here is a hazard-specific hybrid architecture inside a lunar decision-support framework; LIPAS is assessed as a forecasting tool used alongside specialist NASA and NOAA models, not as a replacement for them.
"""

WINDOWS_BLOCK = r"""\subsection{Locked evaluation windows}

\begin{multicols}{2}
The locked quantitative evaluation uses two windows at the same three sites ($0^{\circ}$N $0^{\circ}$E, Apollo~11, and Nobile Rim), the same locked train-2 model, the same serve blend $[0.4,0.0,0,0,0,0]$, and the same storm-aware adaptive gating. Summer Window~S combines the former June--July and July--August 2026 intervals into one approximately two-month evaluation (17~June to 4~August 2026; 138 site-days after excluding the 15--17~July gap in the available daily series). Storm Window~C covers one month of the May 2024 disturbed interval (1--28~May 2024; 84 site-days). Skill 96 = zero site RMSE, not a percent score.
\end{multicols}

\subsubsection{Summer Window S (combined June--August 2026)}

\begin{multicols}{2}
Window~S spans 17~June to 4~August 2026 at the three study sites (138 site-days; about 62\% dayside). It merges what were previously reported as separate Windows~A and~B so that the quiet-to-mixed summer period can be read as a single longer evaluation rather than two short fortnights. The available daily series ends on 4~August (including the Perseids peak day); the three calendar days 15--17~July are missing and are excluded from the RMSE. The late-June radiation spike remains inside this combined window. Micrometeorites use the MEM~3 seasonal background with AMS shower modulation on the LIPAS path and the seasonal MEM~3 envelope without that shower term on the replica.

Over the combined summer span, solar activity shows a modest hybrid gain (RMSE 11.46 versus 11.62, about 1.4\%). Radiation remains replica-led by a small margin (0.987 versus 0.982). Temperature, moonquakes, and dust tie on the shared physics path (34.7, 1.14, and 0.436). The micrometeorite channel uses blend weight zero and is not an independent win (0.0 versus 0.629 for the replica). The combined numbers average the stronger solar gain that appeared in the predominantly dayside July--August sub-interval with the near-tie June--July sub-interval; they do not invent a new training run.
\end{multicols}

\begin{center}
\centering
\includegraphics[width=\textwidth,height=0.30\textheight,keepaspectratio]{figures/fig_windowS_skill.png}
\captionof{figure}{Summer Window~S skill from per-site RMSE (17~June to 4~August 2026; 138 site-days). E = $0^{\circ}$N $0^{\circ}$E; A = Apollo~11; N = Nobile Rim. Navy is LIPAS; orange is the replica.}
\label{fig:winSskill}
\end{center}

\begin{center}
\centering
\includegraphics[width=\textwidth,height=0.26\textheight,keepaspectratio]{figures/fig_windowS_radiation.png}
\captionof{figure}{Summer Window~S radiation (17~June to 4~August 2026; site-day mean). LIPAS, the GOES-plus-physics reference, and the evaluation labels. The shaded band marks the 15--17~July gap; the late-June spike is the embedded disturbed interval inside this longer window.}
\label{fig:winSrad}
\end{center}

\begin{center}
\centering
\begin{tabular}{@{}lccc@{}}
\toprule
Hazard & Hybrid & Replica & Outcome \\
\midrule
Solar activity & 11.46 & 11.62 & Hybrid lower by about 1.4\% \\
Radiation (mSv) & 0.987 & 0.982 & Replica lower \\
Temperature ($^\circ$C) & 34.7 & 34.7 & Tie, shared physics path \\
Moonquakes / day & 1.14 & 1.14 & Tie, shared physics path \\
Micrometeorites & 0.0 & 0.629 & Not an independent win \\
Dust (g\,cm$^{-3}$) & 0.436 & 0.436 & Tie, shared physics path \\
\bottomrule
\end{tabular}
\captionof{table}{Summer Window~S RMSE, 17~June to 4~August 2026 (combined former A+B), 138 site-days.}
\label{tab:winS}
\end{center}

\begin{center}
\centering
\includegraphics[width=\textwidth,height=0.18\textheight,keepaspectratio]{figures/fig_windowS_meteors.png}
\captionof{figure}{Summer Window~S study-site mean micrometeorite flux (17~June to 4~August 2026). LIPAS includes the shower-timing term. The comparison curve is MEM~3 without it. The Perseids peak falls on 4~August at the end of the available series.}
\label{fig:meteors}
\end{center}

\subsubsection{Storm Window C (May 2024)}

\begin{multicols}{2}
Window~C covers 1 to 28~May 2024 at the same three sites (84 site-days). Space-weather drivers are elevated relative to the quietest parts of the 2026 summer window. Storm-aware adaptive gating zeros the solar and radiation machine-learning weights when the regime is storm-like or when live radiation input is at or above 0.20~mSv. Solar activity therefore ties across hybrid, physics, and replica (RMSE 14.65). Radiation remains replica-led (0.199 versus 0.182). Temperature, moonquakes, and dust tie on the shared physics path; micrometeorite scores remain circular under blend weight zero. Extending the earlier 4--17~May disturbed core to a full May month keeps the storm context while matching the one-month reporting length used for Window~S's summer span.
\end{multicols}

\begin{center}
\centering
\includegraphics[width=\textwidth,height=0.24\textheight,keepaspectratio]{figures/fig_windowC_skill.png}
\captionof{figure}{Storm Window~C skill from per-site RMSE (1 to 28~May 2024; 84 site-days). Same site letters and replica as Window~S.}
\label{fig:winCskill}
\end{center}

\begin{center}
\centering
\begin{tabular}{@{}lccc@{}}
\toprule
Hazard & Hybrid & Replica & Outcome \\
\midrule
Solar activity & 14.65 & 14.65 & Tie (adaptive gate to physics) \\
Radiation (mSv) & 0.199 & 0.182 & Replica lower (disturbed month) \\
Temperature ($^\circ$C) & 40.72 & 40.72 & Tie, shared physics path \\
Moonquakes / day & 1.31 & 1.31 & Tie, shared physics path \\
Micrometeorites & 0.0 & 0.604 & Shower term only \\
Dust (g\,cm$^{-3}$) & 0.546 & 0.546 & Tie, shared physics path \\
\bottomrule
\end{tabular}
\captionof{table}{Storm Window~C RMSE, 1 to 28~May 2024, disturbed historical month, 84 site-days.}
\label{tab:winC}
\end{center}

\vspace{-0.85\baselineskip}
"""


def replace_between(text: str, start: str, end: str, new: str) -> str:
    i = text.find(start)
    j = text.find(end, i)
    if i < 0 or j < 0:
        raise SystemExit(f"anchors not found: {start!r} .. {end!r}")
    return text[:i] + new + text[j:]


def patch_body(path: Path) -> None:
    text = path.read_text(encoding="utf-8")

    # Results locked windows block: from subsection through meteors / before Operational mission
    text = replace_between(
        text,
        "\\subsection{Locked evaluation windows}",
        "\\subsection{Operational mission simulation}",
        WINDOWS_BLOCK + "\n",
    )

    # Methods / phase wording
    replacements = [
        (
            "All reported quantitative evaluations in Windows A, B, and C, the mission simulation, and the ablation used the locked production model from the second training run.",
            "All reported quantitative evaluations in Summer Window~S, Storm Window~C, the mission simulation, and the ablation used the locked production model from the second training run.",
        ),
        (
            "Windows A, B, and C are separate locked evaluation periods for the served hybrid against the study labels on those dates and are reported apart from the chronological hold-out test.",
            "Summer Window~S and Storm Window~C are locked evaluation periods for the served hybrid against the study labels on those dates and are reported apart from the chronological hold-out test.",
        ),
        (
            "The Window B micrometeorite comparison used the MEM 3 seasonal background with American Meteor Society (AMS) shower modulation for LIPAS, while the replicated comparison omitted that additional shower term. This tests the effect of explicitly representing shower timing during the Perseid period, not general superiority over NASA's complete meteoroid-modeling framework.",
            "The Summer Window~S micrometeorite comparison used the MEM 3 seasonal background with American Meteor Society (AMS) shower modulation for LIPAS, while the replicated comparison omitted that additional shower term. This tests the effect of explicitly representing shower timing during the Perseid period at the end of the summer span, not general superiority over NASA's complete meteoroid-modeling framework.",
        ),
        (
            "Window A covered 17 June--14 July 2026 (predominantly mixed illumination, with an embedded radiation spike); Window B covered 18 July--14 August 2026 (predominantly lunar day); and Window C covered 4--17 May 2024 (a disturbed historical interval). For Window B micrometeorites, LIPAS used MEM 3 with American Meteor Society (AMS) shower-calendar modulation, while the replicated comparison did not apply that AMS shower calendar.",
            "Summer Window~S covered 17 June--4 August 2026 as one combined evaluation (138 site-days after a 15--17 July gap; mixed-to-dayside summer conditions with an embedded late-June radiation spike and the Perseids peak on 4 August). Storm Window~C covered 1--28 May 2024 (84 site-days; a one-month disturbed historical interval). For Window~S micrometeorites, LIPAS used MEM 3 with American Meteor Society (AMS) shower-calendar modulation, while the replicated comparison did not apply that AMS shower calendar.",
        ),
        (
            "For Window B, the replicated comparison used MEM",
            "For Window~S, the replicated comparison used MEM",
        ),
        (
            "Figures~\\ref{fig:proto} and~\\ref{fig:diviner} are the April check only; they are not repeated in Windows A, B, and C.",
            "Figures~\\ref{fig:proto} and~\\ref{fig:diviner} are the April check only; they are not repeated in Windows~S and~C.",
        ),
        (
            "The ablation study keeps the locked model fixed and uses a quiet 5--18 July 2026 interval (42 site-days; overlapping late Window A and the start of Window B).",
            "The ablation study keeps the locked model fixed and uses a quiet 5--18 July 2026 interval (42 site-days; overlapping the mid-summer portion of Window~S).",
        ),
        # Discussion / conclusion window refs
        (
            "Every quantitative claim in Windows A, B, and C, the mission simulation and the ablation therefore rests on the locked production model from the second training run.",
            "Every quantitative claim in Windows~S and~C, the mission simulation and the ablation therefore rests on the locked production model from the second training run.",
        ),
        (
            "Identical RMSE values (39.9, 1.32 and 0.543 in Window A; 24.7, 0.776 and 0.167 in Window B) are therefore expected by construction.",
            "Identical RMSE values on those channels in Window~S (34.7, 1.14 and 0.436) and Window~C (40.72, 1.31 and 0.546) are therefore expected by construction.",
        ),
        (
            "Solar activity provides the clearest evidence that the learned correction and heliophysics inputs can add predictive information. It is the channel with the largest learned weight (0.4), and the hybrid RMSE was lower than the replica in Window B (4.93 versus 5.71) and only marginally in the mixed Window A (14.15 versus 14.17); Window C ties on solar because adaptive gating routes that channel through physics. Because the solar gain is clearest in the dayside Window B and still present, though small, in the mixed Window A, it is less likely to be an artefact of a single quiet fortnight. It remains modest, however, and it is based on three locked windows at three sites (84 site-days in A and B, 42 in the disturbed Window C).",
            "Solar activity provides the clearest evidence that the learned correction and heliophysics inputs can add predictive information. It is the channel with the largest learned weight (0.4), and over the combined summer Window~S the hybrid RMSE was lower than the replica (11.46 versus 11.62, about 1.4\%); Window~C ties on solar because adaptive gating routes that channel through physics. Combining the former June--July and July--August intervals into one summer window makes the modest solar gain harder to dismiss as an artefact of a single quiet fortnight, while still showing that the gain is concentrated in the more dayside later sub-interval. It remains modest, however, and it is based on two locked windows at three sites (138 site-days in Window~S, 84 in the disturbed Window~C).",
        ),
        (
            "Radiation did not improve. The replica had lower RMSE in Window A (1.26 versus 1.26 for the hybrid), in the predominantly dayside Window B (0.0040 versus 0.0259), and in disturbed Window C (0.194 versus 0.214). In Window B both errors are small in absolute terms, but the replica is still clearly ahead.",
            "Radiation did not improve. The replica had lower RMSE in summer Window~S (0.982 versus 0.987) and in the one-month disturbed Window~C (0.182 versus 0.199).",
        ),
        (
            "The hybrid RMSE of 0.0 in all three windows is therefore circular and is not an independent win; the replica errors (0.606 in Window A, 0.663 in Window B, and 0.622 in Window C) measure the absence of the shower term rather than a deficiency of the MEM 3 framework. The separation between the two curves as the Perseids approached in Window B illustrates the effect of adding shower timing to a seasonal background model.",
            "The hybrid RMSE of 0.0 in both windows is therefore circular and is not an independent win; the replica errors (0.629 in Window~S and 0.604 in Window~C) measure the absence of the shower term rather than a deficiency of the MEM 3 framework. The separation between the two curves as the Perseids approached at the end of Window~S illustrates the effect of adding shower timing to a seasonal background model.",
        ),
        (
            "Fourth, the quantitative evidence covers three locked windows, three sites and one locked model; Window C supplies a disturbed historical interval, while the 2026 windows include mixed and predominantly dayside conditions.",
            "Fourth, the quantitative evidence covers two locked windows, three sites and one locked model; Window~C supplies a one-month disturbed historical interval, while Window~S supplies an approximately two-month summer 2026 evaluation that mixes illumination regimes.",
        ),
        (
            "Window C begins storm-interval RMSE reporting, but radiation still trails the replica there and in the 2026 windows.",
            "Window~C begins one-month storm-interval RMSE reporting, but radiation still trails the replica there and in summer Window~S.",
        ),
        (
            "The modest solar gain should also be tested over longer periods and additional sites.",
            "The modest solar gain in Window~S should also be tested over additional years and sites beyond the present summer span.",
        ),
        (
            "The third research question asked whether the locked hybrid improves prediction performance relative to replicated public baselines and physics-only references. The answer is mixed. Solar activity improved modestly in Window B and only marginally in Window A, with Window C tying on solar under adaptive gating; radiation did not; temperature, moonquakes and dust tied because they share a physics construction with their references; and the micrometeorite contrast, under blend weight zero, describes the shower term rather than independent skill.",
            "The third research question asked whether the locked hybrid improves prediction performance relative to replicated public baselines and physics-only references. The answer is mixed. Solar activity improved modestly over the combined summer Window~S, with Window~C tying on solar under adaptive gating; radiation did not; temperature, moonquakes and dust tied because they share a physics construction with their references; and the micrometeorite contrast, under blend weight zero, describes the shower term rather than independent skill.",
        ),
        # Appendix
        (
            "The short RMSE tables for Windows A, B, and C are in \\texttt{reported\\_window\\_rmse.md}. The daily rows are in the numerical PDF. If the preview is blank, the Download option opens the file. April rows start after the cover page. Window A daily rows start at the 28-day mixed-interval heading. Window B daily rows start at the 18 July table. Window C daily rows cover 4--17 May 2024.",
            "The short RMSE tables for Windows~S and~C are in \\texttt{reported\\_window\\_rmse.md}. The daily rows are in the numerical PDF. If the preview is blank, the Download option opens the file. April rows start after the cover page. Window~S daily rows cover 17~June--4~August 2026 (combined former A+B). Window~C daily rows cover 1--28~May 2024.",
        ),
        (
            "Window A is 17 June to 14 July 2026 (84 site-days, predominantly mixed). Window B is 18 July to 14 August 2026 (84 site-days, mostly lunar day). Window C is 4 to 17 May 2024 (42 site-days, disturbed historical interval).",
            "Summer Window~S is 17 June to 4 August 2026 (138 site-days after the 15--17 July gap; mixed-to-dayside). Storm Window~C is 1 to 28 May 2024 (84 site-days, disturbed historical month).",
        ),
    ]

    # System overview: slight clarification on evaluation windows
    replacements.append(
        (
            "The locked production model was subsequently evaluated using the framework in Section 4.",
            "The locked production model was subsequently evaluated using the framework in Section~4, including the combined summer Window~S and the one-month storm Window~C reported in Section~5.",
        )
    )
    replacements.append(
        (
            "Storm-aware adaptive gating additionally zeros the solar and radiation machine-learning weights when the space-weather regime is storm-like or when the live radiation input is at or above 0.20 mSv, routing those channels through the physics path under disturbed conditions.",
            "Storm-aware adaptive gating additionally zeros the solar and radiation machine-learning weights when the space-weather regime is storm-like or when the live radiation input is at or above 0.20~mSv, routing those channels through the physics path under disturbed conditions. That gate is what produces the solar ties in Storm Window~C: the hybrid, physics, and replica paths coincide once machine learning is switched off for those channels.",
        )
    )

    for old, new in replacements:
        if old not in text:
            print(f"WARN missing in {path.name}: {old[:80]}...")
        else:
            text = text.replace(old, new)

    # Fix leftover Window A/B table label refs if any remain in mission/ablation text
    text = text.replace("Table~\\ref{tab:winB}", "Table~\\ref{tab:winS}")
    text = text.replace("Table~\\ref{tab:winA}", "Table~\\ref{tab:winS}")
    text = text.replace("Fig.~\\ref{fig:winAskill}", "Fig.~\\ref{fig:winSskill}")
    text = text.replace("Fig.~\\ref{fig:winBskill}", "Fig.~\\ref{fig:winSskill}")
    text = text.replace("Fig.~\\ref{fig:winArad}", "Fig.~\\ref{fig:winSrad}")

    path.write_text(text, encoding="utf-8")
    print("patched", path)


def main() -> None:
    for d in ["draft27_asr", "draft27_arxiv"]:
        (ROOT / "papers" / d / "abstract.tex").write_text(ABSTRACT, encoding="utf-8")
        print("wrote abstract", d)
        patch_body(ROOT / "papers" / d / "body.tex")


if __name__ == "__main__":
    main()
