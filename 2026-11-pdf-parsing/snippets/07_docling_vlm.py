"""Docling with granite-docling, a small vision-language model, as the whole
pipeline (article section 8).

    uv run 07_docling_vlm.py ../demo/demo-page.pdf

Slow without a GPU. The output can drop or invent text: compare it with the page.
"""

import sys

from docling.datamodel import vlm_model_specs
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import VlmPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.pipeline.vlm_pipeline import VlmPipeline

path = sys.argv[1] if len(sys.argv) > 1 else "../demo/demo-page.pdf"

options = VlmPipelineOptions(vlm_options=vlm_model_specs.GRANITEDOCLING_TRANSFORMERS)
converter = DocumentConverter(format_options={
    InputFormat.PDF: PdfFormatOption(pipeline_cls=VlmPipeline, pipeline_options=options)})
print(converter.convert(path).document.export_to_markdown())
