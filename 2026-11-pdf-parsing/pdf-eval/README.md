# pdf-eval

Score document parser output (PDFs, scans, images → Markdown) against ground truth.

It computes the original [opendataloader-bench](https://github.com/opendataloader-project/opendataloader-bench)
metrics (NID, TEDS, MHS, identical results) plus additional metrics that say
*why* a parser scored badly, pass/fail checks for your own documents, results
per document type, and confidence intervals. The 200-document DP-Bench ground
truth is bundled, but any ground-truth folder works.

Dependencies: `rapidfuzz`, `apted`, `beautifulsoup4`, `lxml`. Python ≥ 3.10.

## Usage

```sh
uv tool install ./pdf-eval        # or: pip install ./pdf-eval

# one folder per parser, containing <document_id>.md for each ground-truth document
pdf-eval out/docling out/marker plain=out/pypdf --out results
pdf-eval out/docling out/marker --gt my-ground-truth/
```

Writes `results/summary.md` (also printed), `results/summary.csv`, and per
parser `results/<parser>/evaluation.{json,csv}` with every score and check
result per document.

From Python:

```python
from pdf_eval import evaluate, load_ground_truth

scores = evaluate(gt_markdown, predicted_markdown)   # dict, None = not applicable
```

## Ground truth

A ground-truth folder holds, per document id (the input file name without
extension, so `scan_017.png` → `scan_017`), `<id>.md` and/or `<id>.json`:

- `<id>.md`: full reference Markdown. Tables as HTML or Markdown pipes, headings as `#`.
- `<id>.json`: document type and tags, typed elements and/or checks:

```json
{
  "type": "scan",
  "tags": ["german", "invoice"],
  "elements": [
    {"category": "header", "text": "ACME GmbH · Rechnung"},
    {"category": "heading1", "text": "Rechnung 2024-117"},
    {"category": "paragraph", "text": "Vielen Dank für Ihren Auftrag."},
    {"category": "table", "html": "<table><tr><td>Summe</td><td>1.200 €</td></tr></table>"},
    {"category": "footer", "text": "Seite 1 von 2"}
  ],
  "checks": [
    {"type": "present", "text": "Vielen Dank für Ihren Auftrag"},
    {"type": "table", "cell": "1.200 €", "row": "Summe"}
  ]
}
```

Every part is optional, so there are three ways to cover a document:

| You write | You get |
|---|---|
| `<id>.md` only | all reference metrics, as in opendataloader-bench |
| `<id>.json` with `elements` | the same, plus header/footer/figure text treated as optional (see below) |
| `<id>.json` with only `checks` | `checks_pass_rate`; the quickest way to add new PDFs or images |

If both files exist, `<id>.md` stays the reference text and the elements only
mark which parts are headers, footers and so on. Element categories:
`heading1`…`heading6` (or `title`), `paragraph`, `list`, `table` (with
`html`), `caption`, `footnote`, `equation`, `header`, `footer`, `figure`,
`chart`, or anything else (treated as body text). DP-Bench's
`reference.json` format is accepted; split it with
`python -m pdf_eval.ground_truth reference.json out_dir/`.

### Optional text

Parsers disagree on whether page headers, footers, page numbers and text
inside figures belong in the output, and neither choice is wrong. With typed
elements, text from these categories is removed from both the ground truth
and the output before the additional metrics are computed, so keeping it or
dropping it does not matter. Choose categories with `--optional
header,footer,figure,chart` (the default) or `--optional none`. The original
metrics always use the full reference.

On DP-Bench this matters: its reference includes headers and footers, which
favored parsers that keep them. Parsers that drop them, like docling and marker,
looked worse on text recall before this change.

### Checks

Pass/fail statements about the output. They don't depend on Markdown style and
need no full transcription, so they suit new documents and images:

| Check | Passes when |
|---|---|
| `{"type": "present", "text": …}` | the text appears (whole words) |
| `{"type": "absent", "text": …}` | the text does not appear, e.g. a watermark |
| `{"type": "order", "before": …, "after": …}` | both appear, in this order (reading order, columns) |
| `{"type": "heading", "text": …, "level": 2}` | it is a Markdown heading; `level` optional, exact number of `#` |
| `{"type": "table", "cell": …, "row": …, "column": …}` | `cell` is in a table, with `row` in the same row and `column` in the same column (both optional; spans are expanded) |

Text is compared after normalization (no markup, case-insensitive). Add
`"fuzzy": 0.9` to accept 90% similarity, useful for OCR. An optional `"id"`
names a check in `evaluation.json`.

To keep checks fair, write them from the document itself, not from one
parser's output. Cover each document type with several checks.
`examples/newspaper-image/` has a checks-only ground truth for a scanned
newspaper front page (headlines and reading order across columns).

### Document types and unsupported inputs

Results are broken down by tag. Tags come from `type` and `tags` in
`<id>.json`, plus automatic ones derived from the ground truth: `has:tables`,
`has:headings`, `has:equations`, `has:figures`, `has:headers_footers`.

A missing `<id>.md` in a parser's output counts as a failure (empty output).
If a parser cannot handle some inputs at all (for example a PDF-only parser
and images), list them in `<parser folder>/unsupported.txt` as document ids
or `tag:<tag>` lines. They are left out of that parser's averages and shown
under coverage, so compare such parsers within each tag section.

## Metrics

All scores are in [0, 1], higher is better. A metric is `None` (and left out
of averages) when the ground truth has nothing for it to measure, for example
table metrics on a document without tables.

### Original (opendataloader-bench)

| Metric | Measures |
|---|---|
| `nid`, `nid_s` | Edit-distance similarity of the whole text (`_s`: tables removed) |
| `teds`, `teds_s` | Tree edit distance of all tables merged into one tree (`_s`: structure only) |
| `mhs`, `mhs_s` | Tree edit distance of headings and the text under them (`_s`: structure only) |
| `overall` | Per document, the mean of whichever of `nid`, `teds`, `mhs` apply |

### Additional

Text is first stripped of Markdown/HTML markup, Unicode-normalized, words
hyphenated across line breaks are rejoined, and it is split into lower-case
words. Formatting differences therefore no longer count as errors. Optional
text is removed from both sides (see above).

| Metric | Measures |
|---|---|
| `text_recall` | Share of ground-truth words present in the output (missing text) |
| `text_precision` | Share of output words present in the ground truth (garbage, duplicated or invented text) |
| `text_f1` | Harmonic mean of the two |
| `text_order` | Order similarity of only the words both share, so missing or extra text does not affect it |
| `table_text_recall` | Share of ground-truth table cell words found anywhere in the output, with or without table markup |
| `teds_matched`, `teds_s_matched` | TEDS per table: each ground-truth table paired with its best predicted table, weighted by cell count; extra predicted tables count against the score |
| `heading_text_recall` | Share of ground-truth heading words found anywhere in the output |
| `heading_precision`, `heading_recall`, `heading_f1` | Predicted headings matched one-to-one to ground-truth headings (fuzzy text match ≥ 80); optional text marked as a heading is ignored |
| `heading_level_accuracy` | Among matched headings, share at the right relative level. Needs ground truth with more than one level; DP-Bench only uses `#`, so it is always `None` there |
| `checks_pass_rate` | Share of the document's checks that pass |
| `overall_balanced` | Mean of the `nid`, `teds` and `mhs` means, so reading order, tables and headings weigh equally. `overall` instead lets documents with tables and headings dominate |

### Reading the summary

Each cell is `mean [95% interval] #rank`. The interval comes from resampling
documents (bootstrap); when two parsers' intervals overlap heavily, the
benchmark cannot tell them apart. Table metrics rest on only 42 DP-Bench
documents, so their intervals are wide. `n` is the number of documents a
metric applies to.

How to read a weak score:

- low `nid` but high `text_recall` and `text_order` → the text is there, but the output has extra text or formatting noise; check `text_precision`
- `teds` = 0 but high `table_text_recall` → table content was extracted as plain text, without table markup
- `mhs` = 0 but high `heading_text_recall` → headings are in the text but not marked as headings

## License

Apache-2.0. See `NOTICE` for the code and data this builds on.
