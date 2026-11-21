"""Table scores that complement the original TEDS.

* ``table_text_recall`` – share of ground-truth table cell words found
  anywhere in the prediction, whether or not the parser produced table
  markup. Plain-text parsers that keep the content get credit here.
* ``teds_matched`` / ``teds_s_matched`` – TEDS per table instead of over one
  merged tree. Each ground-truth table is paired with its best predicted
  table; unmatched ground-truth tables score 0 and unmatched predicted tables
  are counted as false positives. Tables are weighted by cell count.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from .evaluator_table import TEDSEvaluator, calc_table_score
from .normalize import clean, html_tables, phrase_recall, table_cells, tokens


def _cell_strings(table_html: str) -> List[str]:
    cells = (" ".join(tokens(clean(cell))) for cell in table_cells(table_html))
    return [cell for cell in cells if cell]


def table_text_recall(gt: str, pred: str) -> Optional[float]:
    cells = [cell for table in html_tables(gt) for cell in _cell_strings(table)]
    return phrase_recall(cells, pred)


def _size(table_html: str) -> int:
    return max(len(table_cells(table_html)), 1)


def evaluate_table_matched(gt: str, pred: str) -> Dict[str, Optional[float]]:
    gt_tables = html_tables(gt)
    if not gt_tables:
        return {"teds_matched": None, "teds_s_matched": None}
    pred_tables = html_tables(pred)
    if not pred_tables:
        return {"teds_matched": 0.0, "teds_s_matched": 0.0}

    content = TEDSEvaluator(structure_only=False)
    structure = TEDSEvaluator(structure_only=True)
    pairs = []
    for i, gt_table in enumerate(gt_tables):
        for j, pred_table in enumerate(pred_tables):
            score = calc_table_score(gt_table, pred_table, content)
            pairs.append((score, i, j))
    pairs.sort(reverse=True)

    matched: Dict[int, tuple[int, float]] = {}
    used_pred = set()
    for score, i, j in pairs:
        if score <= 0 or i in matched or j in used_pred:
            continue
        matched[i] = (j, score)
        used_pred.add(j)

    gt_sizes = [_size(table) for table in gt_tables]
    extra = sum(
        _size(table) for j, table in enumerate(pred_tables) if j not in used_pred
    )
    denominator = sum(gt_sizes) + extra

    content_total = 0.0
    structure_total = 0.0
    for i, (j, score) in matched.items():
        content_total += gt_sizes[i] * score
        structure_total += gt_sizes[i] * calc_table_score(
            gt_tables[i], pred_tables[j], structure
        )

    return {
        "teds_matched": content_total / denominator,
        "teds_s_matched": structure_total / denominator,
    }
