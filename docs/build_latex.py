#!/usr/bin/env python
"""Post-process Pandoc LaTeX output for reviewer-ready methodology document.

Replaces Mermaid code blocks with figure placeholders, cleans up the preamble,
and adds professional formatting.
"""

import re
from pathlib import Path

INPUT = Path(__file__).parent / "methodology_raw.tex"
OUTPUT = Path(__file__).parent / "methodology.tex"

# Mermaid diagram titles (matched by order of appearance)
MERMAID_TITLES = [
    "System Pipeline (8 Pillars, v7.1)",
    "Per-Timestep Computation Flow",
    "Liquidity Pillar Scoring",
    "Policy Pillar Binding-Constraint Architecture",
    "Private Credit Pillar Pipeline",
    "Weight Selection Logic",
    "ML Training Pipeline",
    "Bootstrap Confidence Interval Sources",
    "Standard Backtest Loop",
    "Walk-Forward Re-estimation Protocol",
    "Sentiment Pillar Pipeline",
]

CUSTOM_PREAMBLE = r"""\documentclass[11pt, a4paper]{article}

% ── Encoding & Fonts ──────────────────────────────────────
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage{lmodern}
\usepackage{microtype}

% ── Layout ────────────────────────────────────────────────
\usepackage[margin=2.5cm]{geometry}
\usepackage{parskip}

% ── Math ──────────────────────────────────────────────────
\usepackage{amsmath,amssymb}

% ── Tables ────────────────────────────────────────────────
\usepackage{longtable,booktabs,array}
\usepackage{calc}

% ── Graphics & Figures ────────────────────────────────────
\usepackage{graphicx}
\usepackage{float}

% ── Code listings ─────────────────────────────────────────
\usepackage{fancyvrb}
\usepackage{color,xcolor}
\DefineVerbatimEnvironment{Highlighting}{Verbatim}{commandchars=\\\{\},fontsize=\small}
\newenvironment{Shaded}{\begin{snugshade}}{\end{snugshade}}
\usepackage{framed}
\definecolor{shadecolor}{RGB}{248,249,250}

% Syntax highlight tokens (Pandoc defaults)
\newcommand{\AlertTok}[1]{\textcolor[rgb]{1.00,0.00,0.00}{\textbf{#1}}}
\newcommand{\AnnotationTok}[1]{\textcolor[rgb]{0.38,0.63,0.69}{\textbf{\textit{#1}}}}
\newcommand{\AttributeTok}[1]{\textcolor[rgb]{0.49,0.56,0.16}{#1}}
\newcommand{\BaseNTok}[1]{\textcolor[rgb]{0.25,0.63,0.44}{#1}}
\newcommand{\BuiltInTok}[1]{\textcolor[rgb]{0.00,0.50,0.00}{#1}}
\newcommand{\CharTok}[1]{\textcolor[rgb]{0.25,0.44,0.63}{#1}}
\newcommand{\CommentTok}[1]{\textcolor[rgb]{0.38,0.63,0.69}{\textit{#1}}}
\newcommand{\CommentVarTok}[1]{\textcolor[rgb]{0.38,0.63,0.69}{\textbf{\textit{#1}}}}
\newcommand{\ConstantTok}[1]{\textcolor[rgb]{0.53,0.00,0.00}{#1}}
\newcommand{\ControlFlowTok}[1]{\textcolor[rgb]{0.00,0.44,0.13}{\textbf{#1}}}
\newcommand{\DataTypeTok}[1]{\textcolor[rgb]{0.56,0.13,0.00}{#1}}
\newcommand{\DecValTok}[1]{\textcolor[rgb]{0.25,0.63,0.44}{#1}}
\newcommand{\DocumentationTok}[1]{\textcolor[rgb]{0.73,0.13,0.13}{\textit{#1}}}
\newcommand{\ErrorTok}[1]{\textcolor[rgb]{1.00,0.00,0.00}{\textbf{#1}}}
\newcommand{\ExtensionTok}[1]{#1}
\newcommand{\FloatTok}[1]{\textcolor[rgb]{0.25,0.63,0.44}{#1}}
\newcommand{\FunctionTok}[1]{\textcolor[rgb]{0.02,0.16,0.49}{#1}}
\newcommand{\ImportTok}[1]{\textcolor[rgb]{0.00,0.50,0.00}{\textbf{#1}}}
\newcommand{\InformationTok}[1]{\textcolor[rgb]{0.38,0.63,0.69}{\textbf{\textit{#1}}}}
\newcommand{\KeywordTok}[1]{\textcolor[rgb]{0.00,0.44,0.13}{\textbf{#1}}}
\newcommand{\NormalTok}[1]{#1}
\newcommand{\OperatorTok}[1]{\textcolor[rgb]{0.40,0.40,0.40}{#1}}
\newcommand{\OtherTok}[1]{\textcolor[rgb]{0.00,0.44,0.13}{#1}}
\newcommand{\PreprocessorTok}[1]{\textcolor[rgb]{0.74,0.48,0.00}{#1}}
\newcommand{\RegionMarkerTok}[1]{#1}
\newcommand{\SpecialCharTok}[1]{\textcolor[rgb]{0.25,0.44,0.63}{#1}}
\newcommand{\SpecialStringTok}[1]{\textcolor[rgb]{0.73,0.40,0.53}{#1}}
\newcommand{\StringTok}[1]{\textcolor[rgb]{0.25,0.44,0.63}{#1}}
\newcommand{\VariableTok}[1]{\textcolor[rgb]{0.10,0.09,0.49}{#1}}
\newcommand{\VerbatimStringTok}[1]{\textcolor[rgb]{0.25,0.44,0.63}{#1}}
\newcommand{\WarningTok}[1]{\textcolor[rgb]{0.38,0.63,0.69}{\textbf{\textit{#1}}}}
\newcommand{\VerbBar}{|}
\newcommand{\VERB}{\Verb[commandchars=\\\{\}]}

% ── Links ─────────────────────────────────────────────────
\usepackage[colorlinks=true, linkcolor=blue!60!black, urlcolor=blue!60!black, citecolor=blue!60!black]{hyperref}
\usepackage{bookmark}

% ── Headers & Footers ─────────────────────────────────────
\usepackage{fancyhdr}
\pagestyle{fancy}
\fancyhf{}
\fancyhead[L]{\small MAC Framework v7.1}
\fancyhead[R]{\small Confidential}
\fancyfoot[C]{\thepage}
\renewcommand{\headrulewidth}{0.4pt}

% ── Section formatting ────────────────────────────────────
\setcounter{secnumdepth}{3}
\setcounter{tocdepth}{3}

% ── Diagram placeholder command ───────────────────────────
\newcommand{\diagramplaceholder}[2]{%
  \begin{figure}[H]
  \centering
  \fbox{\parbox{0.85\textwidth}{\centering\vspace{2em}%
    \textit{Diagram: #1}\\[0.5em]%
    \small See \texttt{docs/methodologySchematics/#2}\\%
    \small Render with: \texttt{mmdc -i #2 -o #2.pdf}%
    \vspace{2em}}}
  \caption{#1}
  \end{figure}%
}

"""

TITLE_BLOCK = r"""
\title{%
  \textbf{MAC Framework: Quantitative Methodology}\\[0.5em]
  \large Market Absorption Capacity (MAC) --- Technical Specification v7.1
}
\author{Prepared for external quantitative review}
\date{\today}

\begin{document}

\maketitle
\thispagestyle{fancy}

\begin{abstract}
The Market Absorption Capacity (MAC) framework produces a composite score in $[0, 1]$ measuring the capacity of financial markets to absorb exogenous shocks without disorderly price adjustment. This document specifies the v7.1 implementation: eight scoring pillars, non-linear interaction penalties, machine-learning weight optimisation, bootstrap confidence intervals, and HMM regime detection. Walk-forward backtest on 2,813 weekly observations (1971--2025) achieves 92.3\% true positive rate across 39 crisis events.
\end{abstract}

\tableofcontents
\newpage

"""


def extract_body(content: str) -> str:
    """Extract LaTeX body between \\begin{document} and \\end{document}."""
    match = re.search(
        r'\\begin\{document\}(.*?)\\end\{document\}',
        content, flags=re.DOTALL,
    )
    if match:
        return match.group(1)
    return content


def replace_mermaid_blocks(body: str) -> str:
    """Replace Mermaid Shaded blocks with figure placeholders."""
    # Find Shaded blocks that contain flowchart or sequenceDiagram
    pattern = (
        r'\\begin\{Shaded\}\s*\\begin\{Highlighting\}\[\]\s*'
        r'(?:.*?)(?:flowchart|sequenceDiagram)(?:.*?)'
        r'\\end\{Highlighting\}\s*\\end\{Shaded\}'
    )

    counter = [0]  # Use list for closure mutability
    mmd_files = [
        "01_system_pipeline.mmd",
        "02_computation_flow.mmd",
        "03_liquidity_pillar.mmd",
        "04_policy_pillar.mmd",
        "05_private_credit_pillar.mmd",
        "06_weight_selection.mmd",
        "07_ml_training_pipeline.mmd",
        "08_uncertainty_sources.mmd",
        "09_backtest_loop.mmd",
        "10_walk_forward_protocol.mmd",
        "11_sentiment_pillar.mmd",
    ]

    def replacer(match):
        idx = counter[0]
        counter[0] += 1
        if idx < len(MERMAID_TITLES):
            title = MERMAID_TITLES[idx]
            mmd_file = mmd_files[idx] if idx < len(mmd_files) else f"diagram_{idx}.mmd"
            return f"\\diagramplaceholder{{{title}}}{{{mmd_file}}}"
        return f"\\diagramplaceholder{{Diagram {idx + 1}}}{{diagram_{idx}.mmd}}"

    result = re.sub(pattern, replacer, body, flags=re.DOTALL)
    print(f"  Replaced {counter[0]} Mermaid diagram blocks")
    return result


def fix_section_numbering(body: str) -> str:
    """Pandoc removes section numbering; re-enable by removing the
    \\setcounter{secnumdepth}{-\\maxdimen} if present."""
    return body


def clean_body(body: str) -> str:
    """Various cleanup passes on the LaTeX body."""
    # Remove the auto-generated title that Pandoc adds
    body = re.sub(r'\\maketitle\s*', '', body)

    # Remove Pandoc's TOC if present (we add our own)
    body = re.sub(
        r'\{\\setcounter\{tocdepth\}.*?\\tableofcontents.*?\}',
        '', body, flags=re.DOTALL,
    )

    # Fix double-escaped percent signs in tables
    body = body.replace('\\%\\%', '\\%')

    return body


def main():
    print(f"Reading {INPUT}...")
    content = INPUT.read_text(encoding="utf-8")

    print("Extracting document body...")
    body = extract_body(content)

    print("Cleaning body...")
    body = clean_body(body)

    print("Replacing Mermaid diagrams with figure placeholders...")
    body = replace_mermaid_blocks(body)

    print("Assembling final document...")
    final = CUSTOM_PREAMBLE + TITLE_BLOCK + body + "\n\\end{document}\n"

    print(f"Writing {OUTPUT}...")
    OUTPUT.write_text(final, encoding="utf-8")
    print(f"Done! {OUTPUT.stat().st_size / 1024:.0f} KB")
    print(f"  Upload to https://overleaf.com to compile to PDF")


if __name__ == "__main__":
    main()
