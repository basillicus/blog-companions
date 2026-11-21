# PDF parsing, from glyphs to knowledge: companion code

Everything behind the article *PDF parsing, from glyphs to knowledge*
*(article link TBD)*: the demo page, its scans, the answer keys, the output
of every parser, the scorer, and runnable versions of every code example.
Use it to reproduce the article, or as a starting point for testing parsers
on your own documents.

> **Note:** Provided as-is to reproduce the results in the article. Lockfiles
> document the exact versions tested; this snapshot is not actively
> maintained.
>
> **Download only this folder:** grab `2026-11-pdf-parsing.zip` from the
> [release](https://github.com/basillicus/blog-companions/releases/tag/2026-11-pdf-parsing/v1),
> or run a sparse checkout (see the [repository README](../README.md)).

| Folder | What it holds |
|---|---|
| [`demo/`](demo) | The demo page (HTML source, born-digital PDF, fake scan, damaged scan), the answer keys and checks, every parser's output, and the full scores |
| [`snippets/`](snippets) | The article's code examples as scripts, numbered in article order |
| [`parsers/`](parsers) | A script that installs and runs sixteen parsers and parser modes on the same PDFs |
| [`pdf-eval/`](pdf-eval) | The scorer: text, order, table, heading and check metrics against an answer key |
| [`docs/vlm.md`](docs/vlm.md) | Running vision-language models for parsing: servers, models, image size, prompts, settings, checks |

## Quick start

Requires [uv](https://docs.astral.sh/uv/).

```bash
cd snippets
uv run 01_text_layer.py ../demo/demo-page.pdf     # glyphs, fonts and positions
uv run 02_reading_order_knobs.py                  # one parameter, three reading orders
uv run 05_docling_provenance.py                   # layout and table models, with boxes
uv run 05_docling_provenance.py ../demo/scanned-page.pdf   # same call, OCR kicks in
```

The first `uv run` installs the snippet dependencies (Docling pulls in
PyTorch, a few GB). The first Docling run downloads its models.

## The snippets

| Script | Article section | Needs |
|---|---|---|
| `01_text_layer.py` | 2, what is inside a PDF | |
| `02_reading_order_knobs.py` | 4, rules on the text layer | |
| `03_font_sizes.py` | 4, headings from font sizes | |
| `04_plain_text.py` | 8, plain text and Markdown | |
| `05_docling_provenance.py` | 5 and 8, layout and table models | models download on first run |
| `06_tesseract.sh` | 6, OCR | `tesseract` binary |
| `07_docling_vlm.py` | 7 and 8, granite-docling | a GPU helps a lot |
| `08_vlm_page.py` | 7 and 8, any VLM | an OpenAI-compatible endpoint, see [`docs/vlm.md`](docs/vlm.md) |
| `09_edit_distance.py` | 9, measuring | |
| `10_extract.py` | 11, structured extraction and grounding | an OpenAI-compatible endpoint |

`08_vlm_page.py` goes beyond the article's minimal call: it renders PDF
pages, sends one request per page, and warns when the output was cut off or
repeats itself.

```bash
export OPENAI_BASE_URL=http://127.0.0.1:8080/v1   # your server
uv run 08_vlm_page.py ../demo/scanned-page.pdf --model <model-name>
uv run 10_extract.py ../demo/outputs/docling/demo-page.md --model <model-name>
```

## Scoring parsers

```bash
uv tool install ./pdf-eval
pdf-eval demo/outputs/pypdf demo/outputs/docling demo/outputs/pdfplumber \
  --gt demo/ground-truth --out results
```

This writes `results/summary.md` with every metric per parser. The scores
for all parsers in the article are already in
[`demo/scores/summary.md`](demo/scores/summary.md). They are scores of one
page, useful to see *how* each parser fails, not to rank them.

To test parsers on your own documents:

1. Put 20 to 50 representative PDFs in `parsers/pdfs/`, including the ugly ones.
2. Run the parsers: `cd parsers && uv sync && uv run compare.py` (see
   [`parsers/README.md`](parsers/README.md) for GPU setup and the AI modes).
3. Write an answer key or a few checks per document in the format described
   in [`pdf-eval/README.md`](pdf-eval/README.md); the files in
   `demo/ground-truth/` are examples.
4. Score: `pdf-eval parsers/out/* --gt my-ground-truth --out results`.

## The demo page

`demo/demo-page.html` is the source; `demo/make_demo.sh` prints it to PDF
with Chromium and makes the scans with ImageMagick. The page is fictional:
a lake, four sampling stations, two columns, a table without ruling lines,
a footnote, a running header and a page number, which is enough to make
every kind of parser fail somewhere.

Parser outputs in `demo/outputs/` come from one run on 18 November 2026.
`vlm-gemma4/` is Gemma 4 31B called with the article's minimal VLM
snippet; `damaged-page.md` there is its reading of the blotted scan.
Marker crashed on both pages in that environment and has no output.

## Licence

Code: Apache-2.0 (see [`LICENSE`](LICENSE)). `pdf-eval` includes code from
opendataloader-bench and PubTabNet and DP-Bench ground truth; see
[`pdf-eval/NOTICE`](pdf-eval/NOTICE). The Literata font in `demo/fonts/` is
under the SIL Open Font License ([`demo/fonts/LICENSE-Literata.txt`](demo/fonts/LICENSE-Literata.txt)).
Each parser has its own licence; PyMuPDF and pymupdf4llm are AGPL-3.0 or
commercial.
