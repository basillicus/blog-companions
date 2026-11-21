"""The first words of a page's text layer, with font and position (article section 2).

    uv run 01_text_layer.py ../demo/demo-page.pdf
"""

import sys

import pdfplumber

path = sys.argv[1] if len(sys.argv) > 1 else "../demo/demo-page.pdf"

with pdfplumber.open(path) as pdf:
    page = pdf.pages[0]
    for w in page.extract_words(extra_attrs=["fontname", "size"])[:10]:
        print(f'{w["text"]:<10} x0={w["x0"]:6.1f} top={w["top"]:5.1f} '
              f'size={w["size"]:4.1f} {w["fontname"]}')
    if not page.chars:
        print("no text layer: this page needs OCR")
