"""Characters per font size, the statistic behind rule-based heading levels (article section 4).

    uv run 03_font_sizes.py ../demo/demo-page.pdf
"""

import sys
from collections import Counter

import pdfplumber

path = sys.argv[1] if len(sys.argv) > 1 else "../demo/demo-page.pdf"

with pdfplumber.open(path) as pdf:
    sizes = Counter(round(c["size"], 1) for page in pdf.pages for c in page.chars if c["text"].strip())

body = max(sizes, key=sizes.get)
larger = sorted((s for s in sizes if s > body), reverse=True)
for s in sorted(sizes, reverse=True):
    role = f"heading level {larger.index(s) + 1}" if s in larger else "body" if s == body else ""
    print(f"{s:5.1f} pt {sizes[s]:6d} chars  {role}")
