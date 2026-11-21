"""Score one prediction against one ground-truth document."""

from __future__ import annotations

from statistics import fmean
from typing import Dict, Iterable, List, Optional, Tuple, Union

from .evaluator_checks import pass_rate, run_checks
from .evaluator_heading_detection import evaluate_heading_detection
from .evaluator_heading_level import evaluate_heading_level
from .evaluator_reading_order import evaluate_reading_order
from .evaluator_table import evaluate_table
from .evaluator_table_content import evaluate_table_matched, table_text_recall
from .evaluator_text import evaluate_text
from .ground_truth import DEFAULT_OPTIONAL, GroundTruth

ORIGINAL_METRICS = ["overall", "nid", "nid_s", "teds", "teds_s", "mhs", "mhs_s"]
NEW_METRICS = [
    "text_recall",
    "text_precision",
    "text_f1",
    "text_order",
    "table_text_recall",
    "teds_matched",
    "teds_s_matched",
    "heading_text_recall",
    "heading_precision",
    "heading_recall",
    "heading_f1",
    "heading_level_accuracy",
    "checks_pass_rate",
]
ALL_METRICS = ORIGINAL_METRICS + NEW_METRICS

Scores = Dict[str, Optional[float]]


def evaluate_document(
    gt: Union[str, GroundTruth],
    pred: str,
    optional: Iterable[str] = DEFAULT_OPTIONAL,
) -> Tuple[Scores, List[dict]]:
    """Return ``(scores, check results)`` for ``pred`` against ``gt``.

    ``gt`` is reference Markdown or a :class:`GroundTruth`. Text from element
    categories in ``optional`` neither counts as missing nor as extra in the
    new metrics; the original metrics always use the full reference.
    """

    if not isinstance(gt, GroundTruth):
        gt = GroundTruth(doc_id="", markdown=gt or "")
    pred = pred or ""
    scores: Scores = dict.fromkeys(ALL_METRICS)

    reference = gt.markdown
    if reference is not None:
        nid, nid_s = evaluate_reading_order(reference, pred)
        teds, teds_s = evaluate_table(reference, pred)
        mhs, mhs_s = evaluate_heading_level(reference, pred)
        applicable = [value for value in (nid, teds, mhs) if value is not None]
        scores.update(
            overall=fmean(applicable) if applicable else None,
            nid=nid,
            nid_s=nid_s,
            teds=teds,
            teds_s=teds_s,
            mhs=mhs,
            mhs_s=mhs_s,
        )
        phrases = gt.optional_phrases(optional)
        scores.update(evaluate_text(reference, pred, phrases))
        scores["table_text_recall"] = table_text_recall(reference, pred)
        scores.update(evaluate_table_matched(reference, pred))
        scores.update(evaluate_heading_detection(reference, pred, phrases))

    checks = run_checks(gt.checks, pred)
    scores["checks_pass_rate"] = pass_rate(checks)
    return scores, checks


def evaluate(
    gt: Union[str, GroundTruth],
    pred: str,
    optional: Iterable[str] = DEFAULT_OPTIONAL,
) -> Scores:
    """Return every metric for ``pred`` against ``gt``; ``None`` means not applicable.

    ``overall`` is computed exactly as in opendataloader-bench (mean of the
    applicable NID, TEDS and MHS scores), so results stay comparable.
    """

    return evaluate_document(gt, pred, optional)[0]
