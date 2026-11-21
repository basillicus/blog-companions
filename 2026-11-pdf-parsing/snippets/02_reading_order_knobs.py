"""One parameter, three reading orders: pdfminer.six's boxes_flow (article section 4).

    uv run 02_reading_order_knobs.py ../demo/demo-page.pdf
"""

import sys

from pdfminer.high_level import extract_text
from pdfminer.layout import LAParams

path = sys.argv[1] if len(sys.argv) > 1 else "../demo/demo-page.pdf"

for flow in (0.5, -1.0, None):
    print(f"===== boxes_flow={flow} =====")
    print(extract_text(path, laparams=LAParams(boxes_flow=flow)))
