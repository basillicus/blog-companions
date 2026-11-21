"""Text recall, precision and order, computed on markup-free word tokens.

NID mixes three different failures into one number: missing text, extra
text (headers, footers, garbage) and wrong order. These scores separate them:

* ``text_recall``    – share of ground-truth words found in the prediction.
* ``text_precision`` – share of predicted words that are in the ground truth.
* ``text_f1``        – harmonic mean of the two.
* ``text_order``     – order similarity of the words both sides share, so
  missing or extra words do not affect it.

Optional text (by default page headers, footers and text inside figures) is
removed from both sides first, so keeping or dropping it does not matter.
"""

from __future__ import annotations

from collections import Counter
from typing import Dict, List, Optional, Sequence

from rapidfuzz.distance import Indel

from .normalize import Phrase, remove_phrases, text_tokens


def _keep_shared(sequence: List[str], shared: Counter) -> List[str]:
    budget = Counter(shared)
    kept = []
    for token in sequence:
        if budget[token] > 0:
            kept.append(token)
            budget[token] -= 1
    return kept


def _f1(precision: Optional[float], recall: Optional[float]) -> Optional[float]:
    if precision is None or recall is None:
        return None
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def evaluate_text(
    gt: str, pred: str, optional: Sequence[Phrase] = ()
) -> Dict[str, Optional[float]]:
    """Score ``pred`` against ``gt``; ``optional`` text is removed from both first."""

    gt_tokens = remove_phrases(text_tokens(gt), optional)
    if not gt_tokens:
        return {
            "text_recall": None,
            "text_precision": None,
            "text_f1": None,
            "text_order": None,
        }

    pred_tokens = remove_phrases(text_tokens(pred), optional)
    shared = Counter(gt_tokens) & Counter(pred_tokens)
    matched = sum(shared.values())

    recall = matched / len(gt_tokens)
    precision = matched / len(pred_tokens) if pred_tokens else 0.0

    order: Optional[float] = None
    if matched:
        order = Indel.normalized_similarity(
            _keep_shared(gt_tokens, shared), _keep_shared(pred_tokens, shared)
        )

    return {
        "text_recall": recall,
        "text_precision": precision,
        "text_f1": _f1(precision, recall),
        "text_order": order,
    }
