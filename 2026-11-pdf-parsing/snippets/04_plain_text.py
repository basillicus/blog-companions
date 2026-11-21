"""Plain text with pypdf, and Markdown with pymupdf4llm (article section 8).

    uv run 04_plain_text.py ../demo/demo-page.pdf
"""

import sys

import pymupdf4llm
from pypdf import PdfReader

path = sys.argv[1] if len(sys.argv) > 1 else "../demo/demo-page.pdf"

reader = PdfReader(path)
text = "\n\n".join(page.extract_text() for page in reader.pages)
print("===== pypdf =====")
print(text)
if len(text.strip()) < 50 * len(reader.pages):
    print("(almost no text: scanned pages? run OCR)")

print("===== pymupdf4llm =====")
print(pymupdf4llm.to_markdown(path))
