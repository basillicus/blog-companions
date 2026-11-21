"""Aggregate per-document scores into per-engine summaries and rankings.

Each metric is averaged only over the documents where it applies, and the
document count is reported next to it. Confidence intervals come from
resampling documents (bootstrap), so they show how much a mean would move
on a different sample of similar documents.

``overall_balanced`` weights reading order, tables and headings equally
(mean of the three per-metric means). The original ``overall`` averages per
document instead, so documents with tables and headings dominate it.
"""

from __future__ import annotations

import random
from statistics import fmean
from typing import Dict, List, Optional, Sequence

BALANCED_COMPONENTS = ("nid", "teds", "mhs")
BOOTSTRAP_SAMPLES = 1000
BOOTSTRAP_SEED = 0

Scores = Dict[str, Optional[float]]


def _mean_of(documents: Sequence[Scores], metric: str) -> Optional[float]:
    values = [doc[metric] for doc in documents if doc.get(metric) is not None]
    return fmean(values) if values else None


def _balanced(documents: Sequence[Scores]) -> Optional[float]:
    means = [_mean_of(documents, metric) for metric in BALANCED_COMPONENTS]
    present = [value for value in means if value is not None]
    return fmean(present) if present else None


def _statistic(documents: Sequence[Scores], metric: str) -> Optional[float]:
    if metric == "overall_balanced":
        return _balanced(documents)
    return _mean_of(documents, metric)


def _percentile(sorted_values: List[float], fraction: float) -> float:
    index = min(int(fraction * len(sorted_values)), len(sorted_values) - 1)
    return sorted_values[index]


def summarize(documents: Sequence[Scores], metrics: Sequence[str]) -> Dict[str, dict]:
    """Return ``{metric: {mean, n, ci_low, ci_high}}`` for one engine."""

    rng = random.Random(BOOTSTRAP_SEED)
    resamples = [
        [documents[rng.randrange(len(documents))] for _ in documents]
        for _ in range(BOOTSTRAP_SAMPLES)
    ] if documents else []

    summary = {}
    for metric in ["overall_balanced", *metrics]:
        mean = _statistic(documents, metric)
        if metric == "overall_balanced":
            n = len(documents)
        else:
            n = sum(1 for doc in documents if doc.get(metric) is not None)
        boot = sorted(
            value
            for value in (_statistic(sample, metric) for sample in resamples)
            if value is not None
        )
        summary[metric] = {
            "mean": mean,
            "n": n,
            "ci_low": _percentile(boot, 0.025) if boot else None,
            "ci_high": _percentile(boot, 0.975) if boot else None,
        }
    return summary


def rank(summaries: Dict[str, Dict[str, dict]], metric: str) -> Dict[str, int]:
    """Rank engines by mean of ``metric`` (1 = best); ties share a rank."""

    means = {
        engine: summary[metric]["mean"]
        for engine, summary in summaries.items()
        if summary.get(metric, {}).get("mean") is not None
    }
    ordered = sorted(means.values(), reverse=True)
    return {engine: ordered.index(value) + 1 for engine, value in means.items()}


def _cell(stats: dict) -> str:
    if stats["mean"] is None:
        return "–"
    if stats["ci_low"] is None:
        return f"{stats['mean']:.3f}"
    return f"{stats['mean']:.3f} [{stats['ci_low']:.2f}–{stats['ci_high']:.2f}]"


def markdown_table(summaries: Dict[str, Dict[str, dict]], metrics: Sequence[str]) -> str:
    """Engines as rows, metrics as columns, sorted by the first metric."""

    first = metrics[0]
    engines = sorted(
        summaries,
        key=lambda engine: -(summaries[engine][first]["mean"] or 0.0),
    )
    counts = {
        metric: max(summaries[engine][metric]["n"] for engine in engines)
        for metric in metrics
    }
    header = "| engine | " + " | ".join(f"{m} (n={counts[m]})" for m in metrics) + " |"
    divider = "|---|" + "---|" * len(metrics)
    ranks = {metric: rank(summaries, metric) for metric in metrics}
    rows = []
    for engine in engines:
        cells = []
        for metric in metrics:
            position = ranks[metric].get(engine)
            suffix = f" #{position}" if position else ""
            cells.append(_cell(summaries[engine][metric]) + suffix)
        rows.append(f"| {engine} | " + " | ".join(cells) + " |")
    return "\n".join([header, divider, *rows])
