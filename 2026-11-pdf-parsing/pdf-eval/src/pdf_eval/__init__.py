"""Score PDF-to-Markdown parser output against ground-truth Markdown."""

from .ground_truth import DEFAULT_OPTIONAL, GroundTruth, load_ground_truth
from .score import ALL_METRICS, NEW_METRICS, ORIGINAL_METRICS, evaluate, evaluate_document

__all__ = [
    "evaluate",
    "evaluate_document",
    "load_ground_truth",
    "GroundTruth",
    "DEFAULT_OPTIONAL",
    "ALL_METRICS",
    "NEW_METRICS",
    "ORIGINAL_METRICS",
]
