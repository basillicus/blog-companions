# pdf-parsers

Install a set of PDF parsers once and run them over the same PDFs to compare
their output side by side.

| Parser | Kind | Output |
|---|---|---|
| `pdftotext` | poppler CLI (system package) | plain text, layout kept |
| `pypdf` | pure Python | plain text |
| `pdfminer` | pdfminer.six | plain text |
| `pdfplumber` | built on pdfminer | plain text |
| `pymupdf` | MuPDF bindings | plain text |
| `pymupdf4llm` | MuPDF | Markdown |
| `markitdown` | Microsoft, pdfminer based | Markdown |
| `camelot` | tables only | Markdown tables |
| `xberg` | Rust core (successor of kreuzberg) | Markdown |
| `opendataloader` | Java CLI, rule-based layout | Markdown |
| `docling` | IBM, layout + table models | Markdown |
| `mineru` | layout, table, formula and OCR models | Markdown |
| `marker` | layout, OCR models | Markdown |

### AI modes

Not run by default; add `--ai`, or name them with `--only`.

| Entry | What changes |
|---|---|
| `xberg-layout` | xberg with its layout-detection model (ONNX) on top of its rules |
| `opendataloader-hybrid` | pages the Java rules are unsure about go to a local docling server |
| `docling-vlm` | a vision-language model (granite-docling) reads each page image |
| `mineru-vlm` | MinerU's own vision-language model reads each page |
| `marker-llm` | an LLM corrects marker's tables, headings, formulas and forms |

`marker-llm` calls an OpenAI-compatible endpoint: copy `config.toml.example`
to `config.toml` and set its URL and a model that accepts images. Point it at
a local server to keep your PDFs on your machine. The other modes run locally.

## Setup

```bash
uv sync                          # main environment
uv sync --project envs/marker    # marker, kept apart (see below)
```

Requires [uv](https://docs.astral.sh/uv/). `pdftotext` comes from your
distribution's poppler package and is skipped if missing. `opendataloader`
needs Java 11+ on `PATH`; with [mise](https://mise.jdx.dev/), the included
`mise.toml` provides it inside this folder (`mise install`).

## Use

```bash
cp ~/some/*.pdf pdfs/
uv run compare.py                       # all parsers, all PDFs in pdfs/
uv run compare.py doc.pdf --only docling,marker
uv run compare.py --skip mineru,marker  # just the fast ones
uv run compare.py --ai                  # defaults plus all AI modes
```

Output goes to `out/<parser>/<pdf>.md`, and `out/summary.csv` holds time,
character count and error per parser and file. Diff two parsers with e.g.
`diff out/docling/doc.md out/marker/doc.md`.

The first run of `docling`, `mineru` and `marker` downloads their models, so
time them from the second run on. To force the CPU on a machine with an AMD
GPU, run with `HIP_VISIBLE_DEVICES=` (empty); on NVIDIA, `CUDA_VISIBLE_DEVICES=`.

## Why two environments, and the torch setup

- **Marker** pins `pillow<11`, MinerU needs `pillow>=11`, so marker lives in
  `envs/marker/`. Both environments resolve to the same torch build, and uv
  links identical packages from its cache (hardlinks, or copy-on-write clones
  on btrfs), so torch is on disk once. `du` overstates this; on btrfs,
  `btrfs filesystem du -s .venv envs/marker/.venv` shows the real usage.
- **torch** comes from the PyTorch index, built for AMD GPUs (ROCm). The
  `pyproject.toml` comments explain how to switch to CPU-only or NVIDIA. torch
  wants GPU code for every AMD architecture (~12 GB); an override keeps only
  one, `gfx1151` by default. Find yours with `rocminfo | grep gfx` and change
  it in both `pyproject.toml` files. uv applies sources only to direct
  dependencies, which is why torch and the ROCm packages are listed directly.
- **GPU or not.** On one AMD iGPU (Radeon 8060S), 20 simple pages: docling
  ran 2x faster on the GPU, mineru the same, and marker 6x *slower* than on
  CPU. Measure on your own machine and PDFs with and without
  `HIP_VISIBLE_DEVICES=`.
- **marker** sees ROCm torch as "NVIDIA" and would start vLLM in Docker;
  `compare.py` sets `SURYA_INFERENCE_BACKEND=llamacpp` to prevent that.
- **MIOpen** (AMD's convolution library) can fail to tune convolutions with
  "No suitable algorithm"; `compare.py` sets `MIOPEN_FIND_MODE=FAST` to avoid it.
- **MinerU** is pinned below 4: version 4 turned the CLI into a client for a
  local document server plus a separate parse server. 3.x is a one-shot CLI.
  The script uses its `pipeline` backend; the default hybrid backend wants a
  vision-language model on GPU.

## Privacy

Every parser here runs locally, except `marker-llm`, which sends page crops to
the endpoint in `config.toml`. MinerU can call a remote service, but only
with `--api-url`/`-u`, which the script does not pass. MinerU 4 shipped with
anonymous telemetry on by default; if you ever install it, turn it off with
`mineru telemetry disable`.

To score parsers against ground truth instead of eyeballing them, use
[`../pdf-eval`](../pdf-eval), the scorer used in the article.
