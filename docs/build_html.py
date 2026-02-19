#!/usr/bin/env python
"""Post-process Pandoc HTML output for reviewer-ready methodology document.

Fixes Mermaid diagram rendering, adds professional CSS, MathJax, and
print-friendly styling.
"""

import re
import html
from pathlib import Path

INPUT = Path(__file__).parent / "methodology_raw.html"
OUTPUT = Path(__file__).parent / "methodology.html"

CUSTOM_CSS = r"""
    /* ── Professional academic styling ─────────────────────── */
    html {
      color: #1a1a1a;
      background-color: #fff;
    }
    body {
      margin: 0 auto;
      max-width: 52em;
      padding: 40px 60px 80px 60px;
      font-family: "Georgia", "Times New Roman", serif;
      font-size: 11.5pt;
      line-height: 1.6;
      text-rendering: optimizeLegibility;
      font-kerning: normal;
    }
    h1, h2, h3, h4 {
      font-family: "Helvetica Neue", "Arial", sans-serif;
      color: #1a1a1a;
      margin-top: 1.8em;
      margin-bottom: 0.5em;
    }
    h1 { font-size: 1.8em; border-bottom: 2px solid #2c3e50; padding-bottom: 0.3em; }
    h2 { font-size: 1.4em; border-bottom: 1px solid #bdc3c7; padding-bottom: 0.2em; }
    h3 { font-size: 1.15em; }
    h4 { font-size: 1.0em; font-style: italic; }

    /* Title block */
    header#title-block-header {
      text-align: center;
      margin-bottom: 2em;
      padding-bottom: 1em;
      border-bottom: 3px double #2c3e50;
    }
    header#title-block-header h1 {
      font-size: 2.0em;
      border-bottom: none;
      margin-bottom: 0.2em;
    }

    /* Table of contents */
    nav#TOC {
      background: #f8f9fa;
      border: 1px solid #dee2e6;
      border-radius: 4px;
      padding: 1em 1.5em;
      margin: 1.5em 0 2em 0;
      font-family: "Helvetica Neue", "Arial", sans-serif;
      font-size: 0.9em;
    }
    nav#TOC > ul { margin: 0; }
    nav#TOC a { color: #2c3e50; text-decoration: none; }
    nav#TOC a:hover { text-decoration: underline; }

    /* Tables */
    table {
      border-collapse: collapse;
      width: 100%;
      margin: 1em 0;
      font-size: 0.92em;
    }
    thead tr {
      background: #2c3e50;
      color: white;
    }
    th, td {
      padding: 8px 12px;
      text-align: left;
      border-bottom: 1px solid #dee2e6;
    }
    tbody tr:nth-child(even) {
      background: #f8f9fa;
    }
    tbody tr:hover {
      background: #e9ecef;
    }

    /* Code and pre */
    code {
      font-family: "SF Mono", "Consolas", "Monaco", monospace;
      font-size: 0.88em;
      background: #f4f4f4;
      padding: 1px 4px;
      border-radius: 3px;
    }
    pre {
      background: #f8f9fa;
      border: 1px solid #dee2e6;
      border-radius: 4px;
      padding: 12px 16px;
      overflow-x: auto;
      font-size: 0.85em;
    }
    pre code {
      background: none;
      padding: 0;
    }

    /* Mermaid diagrams */
    .mermaid-container {
      background: #fafbfc;
      border: 1px solid #e1e4e8;
      border-radius: 6px;
      padding: 16px;
      margin: 1.5em 0;
      text-align: center;
      overflow-x: auto;
    }

    /* Math */
    .MathJax_Display { margin: 1em 0 !important; }

    /* Blockquotes */
    blockquote {
      border-left: 4px solid #2c3e50;
      margin: 1em 0;
      padding: 0.5em 1em;
      background: #f8f9fa;
      font-style: italic;
    }

    /* Horizontal rules */
    hr {
      border: none;
      border-top: 1px solid #dee2e6;
      margin: 2em 0;
    }

    /* Links */
    a { color: #2980b9; text-decoration: none; }
    a:hover { text-decoration: underline; }

    /* Strong/emphasis in tables */
    strong { font-weight: 700; }

    /* Footer */
    body > p:last-of-type {
      font-style: italic;
      color: #666;
      border-top: 1px solid #dee2e6;
      padding-top: 1em;
      margin-top: 3em;
      font-size: 0.9em;
    }

    /* ── Print styles ──────────────────────────────────────── */
    @media print {
      body {
        max-width: none;
        padding: 0;
        font-size: 10pt;
        line-height: 1.4;
      }
      h1, h2, h3 { page-break-after: avoid; }
      table, figure, .mermaid-container { page-break-inside: avoid; }
      thead { display: table-header-group; }
      nav#TOC { display: none; }
      a { color: #1a1a1a; }
      a[href^="http"]::after {
        content: none;  /* Don't print URLs inline */
      }
      thead tr {
        background: #ddd !important;
        color: #1a1a1a !important;
        -webkit-print-color-adjust: exact;
        print-color-adjust: exact;
      }
      tbody tr:nth-child(even) {
        background: #f5f5f5 !important;
        -webkit-print-color-adjust: exact;
        print-color-adjust: exact;
      }
      .mermaid-container {
        border: 1px solid #ccc;
      }
    }

    @page {
      margin: 2cm;
      @bottom-center {
        content: "MAC Framework v7.1 — Confidential";
        font-size: 8pt;
        color: #999;
      }
    }
"""

MERMAID_SCRIPT = """
<script type="module">
  import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';
  mermaid.initialize({
    startOnLoad: true,
    theme: 'base',
    themeVariables: {
      primaryColor: '#e8f4fd',
      primaryBorderColor: '#2980b9',
      secondaryColor: '#fdf2e9',
      tertiaryColor: '#eafaf1',
      fontFamily: '"Helvetica Neue", Arial, sans-serif',
      fontSize: '13px'
    },
    flowchart: { curve: 'basis', padding: 15 },
    sequence: { actorMargin: 50, messageMargin: 40 }
  });
</script>
"""


def fix_mermaid_blocks(content: str) -> str:
    """Convert Pandoc mermaid output to Mermaid.js-compatible format.

    Pandoc generates: <pre class="mermaid"><code>...escaped...</code></pre>
    Mermaid.js needs: <pre class="mermaid">...unescaped...</pre>
    """
    pattern = r'<pre class="mermaid"><code>(.*?)</code></pre>'

    def replace_block(match):
        code = match.group(1)
        # Unescape HTML entities that Pandoc introduced
        code = html.unescape(code)
        return (
            f'<div class="mermaid-container">\n'
            f'<pre class="mermaid">\n{code}\n</pre>\n'
            f'</div>'
        )

    return re.sub(pattern, replace_block, content, flags=re.DOTALL)


def replace_css(content: str) -> str:
    """Replace Pandoc default CSS with professional styling."""
    # Find the <style> block and replace its contents
    pattern = r'(<style>)(.*?)(</style>)'
    return re.sub(pattern, rf'\1\n{CUSTOM_CSS}\n\3', content, count=1, flags=re.DOTALL)


def add_scripts(content: str) -> str:
    """Add Mermaid.js script before </body>."""
    return content.replace('</body>', f'{MERMAID_SCRIPT}\n</body>')


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
