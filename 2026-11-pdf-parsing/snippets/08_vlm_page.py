"""Ask a vision-language model behind an OpenAI-compatible API to write pages
as Markdown (article section 7). See ../docs/vlm.md for servers, models and
settings.

    uv run 08_vlm_page.py ../demo/scanned-page.jpg --model gemma4-31b
    uv run 08_vlm_page.py report.pdf --pages 1-3 --dpi 200 --model qwen3-vl > report.md

The endpoint comes from --base-url or OPENAI_BASE_URL, the key from
OPENAI_API_KEY (any string for local servers that ignore it).
"""

import argparse
import base64
import io
import os
import sys
from collections import Counter
from pathlib import Path

import pypdfium2 as pdfium
from openai import OpenAI
from PIL import Image

PROMPT = ("Convert this page to Markdown. Use # for headings, a Markdown table "
          "for tables, and keep the reading order. Output only the Markdown.")


def page_images(path, pages, dpi, max_side):
    """Yield (page number, PNG bytes) for a PDF, or the image itself."""
    if path.suffix.lower() != ".pdf":
        images = [(1, Image.open(path))]
    else:
        pdf = pdfium.PdfDocument(path)
        numbers = pages or range(1, len(pdf) + 1)
        images = ((n, pdf[n - 1].render(scale=dpi / 72).to_pil()) for n in numbers)
    for n, img in images:
        img = img.convert("RGB")
        img.thumbnail((max_side, max_side))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        yield n, buf.getvalue()


def parse_pages(spec):
    """'1-3,7' -> [1, 2, 3, 7]"""
    out = []
    for part in spec.split(","):
        a, _, b = part.partition("-")
        out += range(int(a), int(b or a) + 1)
    return out


def warnings_for(text, finish_reason):
    found = []
    if finish_reason == "length":
        found.append("output cut off at max_tokens")
    lines = [l.strip() for l in text.splitlines() if len(l.strip()) > 20]
    repeated = [l for l, k in Counter(lines).items() if k >= 3]
    if repeated:
        found.append(f"{len(repeated)} line(s) repeated 3+ times, e.g. {repeated[0][:60]!r}")
    return found


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", type=Path, help="PDF or page image")
    ap.add_argument("--model", required=True)
    ap.add_argument("--base-url", default=os.environ.get("OPENAI_BASE_URL", "http://127.0.0.1:8080/v1"))
    ap.add_argument("--pages", type=parse_pages, help="e.g. 1-3,7 (default: all)")
    ap.add_argument("--dpi", type=int, default=150, help="render resolution for PDF pages")
    ap.add_argument("--max-side", type=int, default=2048, help="downscale images larger than this")
    ap.add_argument("--max-tokens", type=int, default=8192)
    ap.add_argument("--timeout", type=float, default=900, help="seconds per page")
    ap.add_argument("--prompt", default=PROMPT)
    args = ap.parse_args()

    client = OpenAI(base_url=args.base_url, api_key=os.environ.get("OPENAI_API_KEY", "none"),
                    timeout=args.timeout, max_retries=0)
    for n, png in page_images(args.file, args.pages, args.dpi, args.max_side):
        image = "data:image/png;base64," + base64.b64encode(png).decode()
        response = client.chat.completions.create(
            model=args.model,
            temperature=0,
            max_tokens=args.max_tokens,
            messages=[{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": image}},
                {"type": "text", "text": args.prompt},
            ]}],
        )
        choice = response.choices[0]
        text = choice.message.content or ""
        text = text.removeprefix("```markdown").removeprefix("```md").removesuffix("```").strip()
        for w in warnings_for(text, choice.finish_reason):
            print(f"page {n}: WARNING {w}", file=sys.stderr)
        print(f"<!-- page {n} -->\n{text}\n")


if __name__ == "__main__":
    main()
