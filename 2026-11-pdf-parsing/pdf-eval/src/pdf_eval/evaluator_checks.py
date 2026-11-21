"""Pass/fail checks on parser output, independent of output format.

Checks are cheap to write for new documents (no full reference text needed)
and do not reward any particular Markdown style. They live in the
``"checks"`` list of ``<id>.json``::

    {"type": "present", "text": "Total revenue rose by 12%"}
    {"type": "absent",  "text": "CONFIDENTIAL DRAFT"}
    {"type": "order",   "before": "Introduction", "after": "Conclusion"}
    {"type": "heading", "text": "2.1 Methods", "level": 2}
    {"type": "table",   "cell": "4.2", "row": "Revenue", "column": "2023"}

Text is compared after the same normalization as the text metrics (no
markup, case-folded words). Matching is exact on whole words by default;
``"fuzzy": 0.9`` accepts 90% similarity instead. ``table`` checks need real
table markup (HTML or Markdown pipes): ``cell`` must be in a table cell, and
``row`` / ``column`` (both optional) in another cell of the same row / column.
``heading`` checks need a Markdown heading; ``level`` (optional) is the exact
number of ``#``. An optional ``"id"`` names the check in the report.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from bs4 import BeautifulSoup
from rapidfuzz import fuzz

from .normalize import clean, headings, html_tables, text_tokens, tokens

CHECK_TYPES = ("present", "absent", "order", "heading", "table")


def _norm(text: str) -> str:
    return " ".join(tokens(clean(text or "")))


def _find(needle: str, haystack: str, fuzzy: float) -> Optional[int]:
    """Position of ``needle`` in ``haystack`` (both normalized), or ``None``."""

    if not needle:
        return None
    if fuzzy >= 1.0:
        index = f" {haystack} ".find(f" {needle} ")
        return index if index >= 0 else None
    alignment = fuzz.partial_ratio_alignment(needle, haystack)
    if alignment is None or alignment.score < fuzzy * 100:
        return None
    return alignment.dest_start


def _same(a: str, b: str, fuzzy: float) -> bool:
    if fuzzy >= 1.0:
        return a == b
    return fuzz.ratio(a, b) >= fuzzy * 100


def table_grid(table_html: str) -> List[List[str]]:
    """Expand ``table_html`` into a rectangular grid of normalized cell texts."""

    soup = BeautifulSoup(table_html, "html.parser")
    grid: Dict[Tuple[int, int], str] = {}
    for r, row in enumerate(soup.find_all("tr")):
        c = 0
        for cell in row.find_all(["td", "th"]):
            while (r, c) in grid:
                c += 1
            text = _norm(cell.get_text(" "))
            rowspan = max(int(cell.get("rowspan", 1) or 1), 1)
            colspan = max(int(cell.get("colspan", 1) or 1), 1)
            for dr in range(rowspan):
                for dc in range(colspan):
                    grid.setdefault((r + dr, c + dc), text)
            c += colspan
    if not grid:
        return []
    rows = max(r for r, _ in grid) + 1
    cols = max(c for _, c in grid) + 1
    return [[grid.get((r, c), "") for c in range(cols)] for r in range(rows)]


def _table_check(check: dict, tables: List[List[List[str]]], fuzzy: float) -> bool:
    cell = _norm(check.get("cell", ""))
    row_label = _norm(check.get("row", ""))
    column_label = _norm(check.get("column", ""))
    if not cell:
        return False
    for grid in tables:
        for r, row in enumerate(grid):
            for c, value in enumerate(row):
                if not _same(value, cell, fuzzy):
                    continue
                row_ok = not row_label or any(
                    _same(other, row_label, fuzzy) for k, other in enumerate(row) if k != c
                )
                column_ok = not column_label or any(
                    _same(grid[k][c], column_label, fuzzy) for k in range(len(grid)) if k != r
                )
                if row_ok and column_ok:
                    return True
    return False


def run_checks(checks: List[dict], pred: str) -> List[dict]:
    """Return ``[{"id", "type", "passed"}]`` for every check."""

    if not checks:
        return []
    text = " ".join(text_tokens(pred))
    pred_headings = headings(pred)
    tables: Optional[List[List[List[str]]]] = None

    results = []
    for index, check in enumerate(checks):
        kind = check.get("type", "present")
        fuzzy = float(check.get("fuzzy", 1.0))
        if kind == "present":
            passed = _find(_norm(check.get("text", "")), text, fuzzy) is not None
        elif kind == "absent":
            passed = _find(_norm(check.get("text", "")), text, fuzzy) is None
        elif kind == "order":
            before = _find(_norm(check.get("before", "")), text, fuzzy)
            after = _find(_norm(check.get("after", "")), text, fuzzy)
            passed = before is not None and after is not None and before < after
        elif kind == "heading":
            wanted = _norm(check.get("text", ""))
            level = check.get("level")
            passed = any(
                _same(found, wanted, fuzzy) and (level is None or found_level == int(level))
                for found_level, found in pred_headings
            )
        elif kind == "table":
            if tables is None:
                tables = [table_grid(table) for table in html_tables(pred)]
            passed = _table_check(check, tables, fuzzy)
        else:
            raise ValueError(f"unknown check type {kind!r} (expected one of {CHECK_TYPES})")
        results.append({"id": check.get("id", index), "type": kind, "passed": passed})
    return results


def pass_rate(results: List[dict]) -> Optional[float]:
    if not results:
        return None
    return sum(result["passed"] for result in results) / len(results)
