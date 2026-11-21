"""Run several PDF parsers over the same PDFs and write their output side by side.

    uv run compare.py [PDF_OR_DIR ...] [--only a,b] [--skip a,b] [--out DIR]

With no paths it parses every PDF in pdfs/. For each parser and PDF it writes
out/<parser>/<pdf stem>.md, plus out/summary.csv with time, size and errors.
The first run of docling, mineru and marker downloads their models, so their
times only mean something from the second run on.

Entries ending in -vlm, -llm, -layout or -hybrid are the AI modes of a parser
and only run when named with --only (or --ai for all of them). marker-llm needs
an OpenAI-compatible endpoint in config.toml (see config.toml.example).
"""

import argparse
import csv
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import tomllib
from pathlib import Path

HERE = Path(__file__).parent

# On AMD GPUs, MIOpen's exhaustive convolution tuning can fail with "No suitable
# algorithm"; the fast find mode avoids it. Inherited by mineru and marker too.
os.environ.setdefault("MIOPEN_FIND_MODE", "FAST")
# marker's model library (surya) takes torch seeing a GPU to mean NVIDIA and
# starts vLLM in Docker. That is true for ROCm too, so pick llama.cpp instead;
# set SURYA_INFERENCE_BACKEND=vllm yourself on an NVIDIA machine with Docker.
os.environ.setdefault("SURYA_INFERENCE_BACKEND", "llamacpp")


def run(cmd):
    """Run a CLI parser in its own process group and kill the group afterwards:
    marker starts helper model servers that would otherwise outlive it."""
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, start_new_session=True)
    try:
        out, err = proc.communicate()
    finally:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    if proc.returncode:
        raise subprocess.CalledProcessError(proc.returncode, cmd, out, err)


def read_md(folder):
    """Return the largest .md file a CLI parser wrote somewhere under folder."""
    files = sorted(Path(folder).rglob("*.md"), key=lambda p: p.stat().st_size)
    if not files:
        raise RuntimeError("parser wrote no markdown")
    return files[-1].read_text()


def pdftotext(pdf):
    if not shutil.which("pdftotext"):
        raise RuntimeError("pdftotext not installed (poppler)")
    return subprocess.run(["pdftotext", "-layout", str(pdf), "-"],
                          check=True, capture_output=True, text=True).stdout


def pypdf(pdf):
    from pypdf import PdfReader
    return "\n\n".join(page.extract_text() for page in PdfReader(pdf).pages)


def pdfminer(pdf):
    from pdfminer.high_level import extract_text
    return extract_text(pdf)


def pdfplumber(pdf):
    import pdfplumber
    with pdfplumber.open(pdf) as doc:
        return "\n\n".join(page.extract_text() or "" for page in doc.pages)


def pymupdf(pdf):
    import pymupdf
    with pymupdf.open(pdf) as doc:
        return "\n\n".join(page.get_text() for page in doc)


def pymupdf4llm(pdf):
    import pymupdf4llm
    return pymupdf4llm.to_markdown(str(pdf))


def markitdown(pdf):
    from markitdown import MarkItDown
    return MarkItDown().convert(str(pdf)).text_content


def camelot(pdf):
    """Tables only: camelot does not extract running text."""
    import camelot
    tables = camelot.read_pdf(str(pdf), pages="all", flavor="lattice")
    if not tables.n:
        tables = camelot.read_pdf(str(pdf), pages="all", flavor="stream")
    return "\n\n".join(t.df.to_markdown(index=False) for t in tables)


def load_config():
    path = HERE / "config.toml"
    return tomllib.loads(path.read_text()) if path.exists() else {}


def xberg(pdf, layout=False):
    import asyncio
    import xberg
    from xberg.api import ExtractInput, LayoutDetectionConfig
    config = xberg.ExtractionConfig(
        output_format="markdown", layout=LayoutDetectionConfig() if layout else None,
        # Without this the layout model runs but the Markdown ignores it.
        use_layout_for_markdown=layout)
    result = asyncio.run(xberg.extract(ExtractInput(uri=str(Path(pdf).resolve())),
                                       config=config))
    if result.errors:
        raise RuntimeError(result.errors[0])
    return result.results[0].content


def xberg_layout(pdf):
    """xberg with its layout-detection model (ONNX) instead of rules alone."""
    return xberg(pdf, layout=True)


def opendataloader(pdf, **hybrid):
    # Runs a bundled Java CLI: needs Java 11+ on PATH (see mise.toml).
    import opendataloader_pdf
    with tempfile.TemporaryDirectory() as tmp:
        opendataloader_pdf.convert(str(pdf), output_dir=tmp, format="markdown",
                                   quiet=True, **hybrid)
        return read_md(tmp)


_hybrid_server = None


def opendataloader_hybrid(pdf):
    """Pages the Java rules are unsure about go to a local docling server."""
    global _hybrid_server
    if _hybrid_server is None:
        from opendataloader_pdf import HybridServer
        _hybrid_server = HybridServer()
        _hybrid_server.start()
    return opendataloader(pdf, hybrid="docling-fast", hybrid_url=_hybrid_server.url)


def _stop_hybrid_server():
    global _hybrid_server
    if _hybrid_server is not None:
        _hybrid_server.stop()
        _hybrid_server = None


# Run after a parser has done all PDFs, so its models free the GPU before the
# next parser starts; marker crashed when it ran beside the docling server.
opendataloader_hybrid.teardown = _stop_hybrid_server


_docling_converter = None


def docling(pdf):
    global _docling_converter
    if _docling_converter is None:
        from docling.document_converter import DocumentConverter
        _docling_converter = DocumentConverter()
    return _docling_converter.convert(pdf).document.export_to_markdown()


_docling_vlm_converter = None


def docling_vlm(pdf):
    """A vision-language model (granite-docling) reads each page image."""
    global _docling_vlm_converter
    if _docling_vlm_converter is None:
        from docling.datamodel import vlm_model_specs
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import VlmPipelineOptions
        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling.pipeline.vlm_pipeline import VlmPipeline
        options = VlmPipelineOptions(vlm_options=vlm_model_specs.GRANITEDOCLING_TRANSFORMERS)
        _docling_vlm_converter = DocumentConverter(format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_cls=VlmPipeline,
                                             pipeline_options=options)})
    return _docling_vlm_converter.convert(pdf).document.export_to_markdown()


def mineru(pdf, backend="pipeline"):
    # pipeline backend by default: the hybrid default wants a vision model.
    with tempfile.TemporaryDirectory() as tmp:
        run(["mineru", "-p", str(pdf), "-o", tmp, "-b", backend])
        return read_md(tmp)


def mineru_vlm(pdf):
    """MinerU's own vision-language model reads each page (transformers)."""
    return mineru(pdf, backend="vlm-engine")


def marker(pdf, *extra):
    # Lives in its own environment, see envs/marker/pyproject.toml.
    with tempfile.TemporaryDirectory() as tmp:
        run(["uv", "run", "--project", str(HERE / "envs" / "marker"), "marker_single",
             str(pdf), "--output_dir", tmp, "--output_format", "markdown",
             "--disable_image_extraction", "--disable_tqdm", *extra])
        return read_md(tmp)


def marker_llm(pdf):
    """marker plus an LLM that fixes tables, headers, formulas and forms. The
    model must accept images: marker sends it crops of the page."""
    llm = load_config().get("llm")
    if not llm:
        raise RuntimeError("no [llm] section in config.toml, see config.toml.example")
    return marker(pdf, "--use_llm",
                  "--llm_service", "marker.services.openai.OpenAIService",
                  "--openai_base_url", llm["base_url"],
                  "--openai_model", llm["model"],
                  "--openai_api_key", llm.get("api_key") or "none",
                  # Local vision models often need more than marker's 30 s default.
                  "--timeout", str(llm.get("timeout", 300)))


DEFAULT = [
    pdftotext, pypdf, pdfminer, pdfplumber, pymupdf, pymupdf4llm, markitdown,
    camelot, xberg, opendataloader, docling, mineru, marker,
]
AI_MODES = [xberg_layout, opendataloader_hybrid, docling_vlm, mineru_vlm, marker_llm]
PARSERS = {f.__name__.replace("_", "-"): f for f in DEFAULT + AI_MODES}


def collect_pdfs(paths):
    pdfs = []
    for p in map(Path, paths):
        pdfs += sorted(p.rglob("*.pdf")) if p.is_dir() else [p]
    return pdfs


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("paths", nargs="*", default=[HERE / "pdfs"])
    ap.add_argument("--only", help="comma-separated parsers to run")
    ap.add_argument("--skip", help="comma-separated parsers to leave out")
    ap.add_argument("--ai", action="store_true", help="also run the AI modes")
    ap.add_argument("--out", type=Path, default=HERE / "out")
    args = ap.parse_args()

    pool = DEFAULT + AI_MODES if args.ai else DEFAULT
    names = (args.only.split(",") if args.only
             else [f.__name__.replace("_", "-") for f in pool])
    names = [n for n in names if n not in (args.skip or "").split(",")]
    unknown = set(names) - set(PARSERS)
    if unknown:
        sys.exit(f"unknown parser(s): {', '.join(sorted(unknown))}; "
                 f"available: {', '.join(PARSERS)}")
    pdfs = collect_pdfs(args.paths)
    if not pdfs:
        sys.exit(f"no PDFs found in {', '.join(map(str, args.paths))}")

    rows = []
    for name in names:
        (args.out / name).mkdir(parents=True, exist_ok=True)
        for pdf in pdfs:
            start = time.perf_counter()
            try:
                text, error = PARSERS[name](pdf), ""
            except subprocess.CalledProcessError as e:
                text, error = "", (e.stderr or str(e)).strip().splitlines()[-1]
            except Exception as e:
                text, error = "", f"{type(e).__name__}: {e}"
            seconds = time.perf_counter() - start
            (args.out / name / f"{pdf.stem}.md").write_text(text)
            rows.append({"parser": name, "file": pdf.name,
                         "seconds": f"{seconds:.2f}", "chars": len(text),
                         "error": error})
            status = f"ERROR {error}" if error else f"{len(text):>8} chars"
            print(f"{name:<14} {pdf.name:<40} {seconds:7.2f}s  {status}", flush=True)
        if hasattr(PARSERS[name], "teardown"):
            PARSERS[name].teardown()

    with open(args.out / "summary.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"\noutput in {args.out}/<parser>/, summary in {args.out / 'summary.csv'}")


if __name__ == "__main__":
    main()
