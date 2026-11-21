"""Docling: Markdown, plus the page and box of every element (article section 8).

    uv run 05_docling_provenance.py ../demo/demo-page.pdf
    uv run 05_docling_provenance.py ../demo/scanned-page.pdf    # OCR runs automatically

The first run downloads the layout and table models.
"""

import sys

from docling.document_converter import DocumentConverter

path = sys.argv[1] if len(sys.argv) > 1 else "../demo/demo-page.pdf"

doc = DocumentConverter().convert(path).document
markdown = doc.export_to_markdown()
print(markdown)
print()

# y counts up from the bottom of the page, as in the PDF format
for item, level in doc.iterate_items():
    box = item.prov[0].bbox
    print(f"{item.label:<15} page {item.prov[0].page_no}  "
          f"x={box.l:5.1f} y={box.t:5.1f}  {getattr(item, 'text', '')[:38]}")

# page headers, footers and page numbers are not in the body, but kept here
print()
for item, level in doc.iterate_items(included_content_layers={"furniture"}):
    if getattr(item, "content_layer", None) == "furniture":
        print(f"furniture: {item.label:<12} {getattr(item, 'text', '')}")

doc.save_as_json("docling-output.json")
