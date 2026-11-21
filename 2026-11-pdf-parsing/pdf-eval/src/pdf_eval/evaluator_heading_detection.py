"""Heading scores that complement the original MHS.

* ``heading_text_recall`` – share of ground-truth heading words found anywhere
  in the prediction, whether or not they are marked as headings.
* ``heading_precision`` / ``heading_recall`` / ``heading_f1`` – predicted
  headings matched one-to-one to ground-truth headings by fuzzy text match.
* ``heading_level_accuracy`` – among matched headings, the share whose level
  agrees. Levels are compared by rank within each document, so a parser that
  uses ``##`` and ``###`` where the ground truth uses ``#`` and ``##`` is not
  penalised. ``None`` when the ground truth uses a single level.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence

from rapidfuzz import fuzz

from .normalize import Phrase, headings, phrase_recall

MATCH_THRESHOLD = 80.0


def _level_ranks(levels: List[int]) -> Dict[int, int]:
    return {level: rank for rank, level in enumerate(sorted(set(levels)))}


def _matches_any(text: str, candidates: Sequence[str]) -> bool:
    return any(fuzz.ratio(text, other) >= MATCH_THRESHOLD for other in candidates)


def evaluate_heading_detection(
    gt: str, pred: str, optional: Sequence[Phrase] = ()
) -> Dict[str, Optional[float]]:
    """Score headings in ``pred``; predicted headings that are optional text
    (for example a running page header marked as a heading) are ignored."""

    gt_headings = headings(gt)
    if not gt_headings:
        return {
            "heading_text_recall": None,
            "heading_precision": None,
            "heading_recall": None,
            "heading_f1": None,
            "heading_level_accuracy": None,
        }

    gt_texts = [text for _, text in gt_headings]
    optional_texts = [phrase.text for phrase in optional]
    pred_headings = [
        (level, text)
        for level, text in headings(pred)
        if _matches_any(text, gt_texts) or not _matches_any(text, optional_texts)
    ]
    text_recall = phrase_recall([text for _, text in gt_headings], pred)

    pairs = []
    for i, (_, gt_text) in enumerate(gt_headings):
        for j, (_, pred_text) in enumerate(pred_headings):
            score = fuzz.ratio(gt_text, pred_text)
            if score >= MATCH_THRESHOLD:
                pairs.append((score, i, j))
    pairs.sort(reverse=True)

    matched: Dict[int, int] = {}
    used_pred = set()
    for _, i, j in pairs:
        if i in matched or j in used_pred:
            continue
        matched[i] = j
        used_pred.add(j)

    recall = len(matched) / len(gt_headings)
    precision = len(matched) / len(pred_headings) if pred_headings else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    level_accuracy: Optional[float] = None
    gt_levels = [level for level, _ in gt_headings]
    if len(set(gt_levels)) > 1 and matched:
        gt_rank = _level_ranks(gt_levels)
        pred_rank = _level_ranks([pred_headings[j][0] for j in matched.values()])
        agree = sum(
            gt_rank[gt_headings[i][0]] == pred_rank[pred_headings[j][0]]
            for i, j in matched.items()
        )
        level_accuracy = agree / len(matched)

    return {
        "heading_text_recall": text_recall,
        "heading_precision": precision,
        "heading_recall": recall,
        "heading_f1": f1,
        "heading_level_accuracy": level_accuracy,
    }
