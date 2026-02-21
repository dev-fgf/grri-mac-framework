#!/usr/bin/env python
"""Post-process Pandoc HTML output for the GRRI Historical Extension Paper.

Reuses the same professional styling as build_html.py with GRRI-specific
title footer and file paths.
"""

import re
import html
from pathlib import Path

INPUT = Path(__file__).parent / "grri_raw.html"
OUTPUT = Path(__file__).parent / "grri_extension_paper.html"

# Import CSS and scripts from the MAC build, adjusting the footer
from build_html import CUSTOM_CSS as _MAC_CSS, MERMAID_SCRIPT

CUSTOM_CSS = _MAC_CSS.replace(
    'content: "MAC Framework v7.1 — Confidential"',
    'content: "GRRI Historical Extension — Confidential Draft  |  GRS © FGF"',
)

# Diagonal watermark on every printed page
CUSTOM_CSS += r"""
    /* ── Confidential Draft watermark ──────────────────────── */
    @media print {
      body::after {
        content: "CONFIDENTIAL DRAFT";
        position: fixed;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%) rotate(-35deg);
        font-size: 4em;
        font-family: "Helvetica Neue", Arial, sans-serif;
        font-weight: 700;
        color: rgba(200, 0, 0, 0.09);
        letter-spacing: 0.1em;
        pointer-events: none;
        z-index: 9999;
        white-space: nowrap;
        -webkit-print-color-adjust: exact;
        print-color-adjust: exact;
      }
    }
    /* On-screen watermark too */
    body::after {
      content: "CONFIDENTIAL DRAFT";
      position: fixed;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%) rotate(-35deg);
      font-size: 4em;
      font-family: "Helvetica Neue", Arial, sans-serif;
      font-weight: 700;
      color: rgba(200, 0, 0, 0.07);
      letter-spacing: 0.1em;
      pointer-events: none;
      z-index: 9999;
      white-space: nowrap;
    }
"""

# Reuse the same fix/replace/add functions
from build_html import fix_mermaid_blocks, replace_css as _replace_css, add_scripts


def replace_css(content: str) -> str:
    """Replace Pandoc default CSS with professional styling (GRRI footer)."""
    pattern = r'(<style>)(.*?)(</style>)'
    return re.sub(pattern, rf'\1\n{CUSTOM_CSS}\n\3', content, count=1, flags=re.DOTALL)


def main():
    print(f"Reading {INPUT}...")
    content = INPUT.read_text(encoding="utf-8")

    print("Replacing CSS with professional styling...")
    content = replace_css(content)

    print("Fixing Mermaid diagram blocks...")
    mermaid_count = len(re.findall(r'<pre class="mermaid">', content))
    content = fix_mermaid_blocks(content)
    print(f"  Fixed {mermaid_count} Mermaid diagrams")

    print("Adding Mermaid.js script...")
    content = add_scripts(content)

    print(f"Writing {OUTPUT}...")
    OUTPUT.write_text(content, encoding="utf-8")
    print(f"Done! Open {OUTPUT} in a browser to view.")
    print(f"  File size: {OUTPUT.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
