\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{elsarticle}[2026/11/02 Minimal local elsarticle stub]
\DeclareOption{preprint}{}
\DeclareOption{review}{}
\DeclareOption{1p}{}
\DeclareOption{3p}{}
\DeclareOption{5p}{}
\DeclareOption{authoryear}{\def\els@natbibopts{authoryear,round}}
\DeclareOption{number}{\def\els@natbibopts{numbers}}
\DeclareOption*{\PassOptionsToClass{\CurrentOption}{article}}
\def\els@natbibopts{authoryear,round}
\ProcessOptions\relax
\LoadClass[12pt]{article}
\RequirePackage[margin=1in]{geometry}
\RequirePackage[\els@natbibopts]{natbib}
\newcommand{\sep}{; }
\newcommand{\journal}[1]{\gdef\@journal{#1}}
\newcommand{\biboptions}[1]{\setcitestyle{#1}}
\let\@journal\@empty
\let\@address\@empty
\let\@ead\@empty
\let\@authortext\@empty
\renewcommand{\author}[2][]{\gdef\@authortext{#2}\gdef\@author{#2}}
\newcommand{\address}[2][]{\gdef\@address{#2}}
\newcommand{\ead}[1]{\gdef\@ead{\texttt{#1}}}
\newcommand{\corref}[1]{$^{\ast}$}
\newcommand{\cortext}[2][]{}
\renewenvironment{abstract}{\par\noindent\textbf{Abstract.}\ }{\par\medskip}
\newenvironment{keyword}{\par\noindent\textbf{Keywords:} }{\par\medskip}
\newenvironment{frontmatter}{}{%
  \begin{center}
    {\LARGE\@title\par}\vspace{0.8em}
    {\large\@authortext\par}\vspace{0.4em}
    \ifx\@address\@empty\else{\small\@address\par}\fi
    \ifx\@ead\@empty\else{\small\@ead\par}\fi
    \ifx\@journal\@empty\else\vspace{0.4em}\textit{\@journal}\par\fi
  \end{center}
  \vspace{0.6em}
}
\endinput
