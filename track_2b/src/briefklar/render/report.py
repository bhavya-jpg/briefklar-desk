"""technical_report.md -> PDF, with the bundled fonts.  python -m briefklar.render.report IN.md OUT.pdf"""

from __future__ import annotations

import sys
from pathlib import Path

from briefklar.render.handout import _html_to_pdf, font_faces

CSS = """
@page { size: A4; margin: 17mm 17mm 18mm; @bottom-center { content: counter(page) " / " counter(pages); font-size: 8pt; color: #4A4F57; } }
html { font-size: 9.4pt; line-height: 1.38; color: #14161A; }
h1 { font-size: 19pt; line-height: 1.1; margin: 0 0 3mm; letter-spacing: -0.02em; }
h2 { font-size: 12.5pt; margin: 5mm 0 1.5mm; border-bottom: 0.6pt solid #14161A; padding-bottom: 1mm; }
h3 { font-size: 10pt; margin: 3mm 0 1mm; }
p, ul, ol { margin: 0 0 2mm; } ul, ol { padding-left: 5mm; } li { margin-bottom: 0.6mm; }
table { border-collapse: collapse; width: 100%; margin: 2mm 0 3mm; font-size: 8.6pt; }
th, td { text-align: left; padding: 1mm 2mm 1mm 0; border-bottom: 0.3pt solid #C9C5BC; vertical-align: top; }
th { font-weight: 600; } code { font-size: 8.4pt; } pre { background: #F6F4EF; padding: 2mm; font-size: 8pt; white-space: pre-wrap; }
img { max-width: 100%; } a { color: #0F6E6A; text-decoration: none; }
blockquote { margin: 2mm 0; padding: 1.5mm 3mm; border-left: 2pt solid #8F5D00; background: #FBF3DF; }
"""


def main(source: str, target: str) -> None:
    import markdown

    text = Path(source).read_text(encoding="utf-8")
    body = markdown.markdown(text, extensions=["tables", "fenced_code"])
    css, stack = font_faces()
    base = Path(source).resolve().parent.as_uri() + "/"
    html = (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><base href="{base}">'
            f"<style>{css}\nhtml{{font-family:{stack}}}\n{CSS}</style></head><body>{body}</body></html>")
    Path(target).write_bytes(_html_to_pdf(html))
    print(f"wrote {target}")


if __name__ == "__main__":
    main(*sys.argv[1:3])
