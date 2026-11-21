"""Command line: score one or more prediction folders against ground truth.

    pdf-eval PRED_DIR [PRED_DIR ...] [--gt GT_DIR] [--out OUT_DIR]

Each PRED_DIR holds ``<document_id>.md`` files (or a ``markdown/`` subfolder
with them, as in opendataloader-bench). Use ``name=path`` to set the engine
name; otherwise the folder name is used. Without ``--gt`` the bundled
DP-Bench ground truth is used.

A missing ``<document_id>.md`` counts as a failed (empty) prediction. To mark
inputs a parser cannot handle at all (for example images for a PDF-only
parser), list them in ``PRED_DIR/unsupported.txt``, one per line, as document
ids or ``tag:<tag>``. Those documents are left out of that parser's averages
and reported under coverage.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from importlib.resources import files
from pathlib import Path
from typing import Dict, FrozenSet, List, Optional, Sequence, Set, Tuple

from .evaluator_checks import CHECK_TYPES
from .ground_truth import DEFAULT_OPTIONAL, GroundTruth, load_ground_truth
from .report import markdown_table, summarize
from .score import ALL_METRICS, evaluate_document

HEADLINE_ORIGINAL = ["overall", "overall_balanced", "nid", "teds", "mhs"]
HEADLINE_NEW = [
    "text_f1",
    "text_recall",
    "text_precision",
    "text_order",
    "table_text_recall",
    "teds_matched",
    "heading_text_recall",
    "heading_f1",
    "checks_pass_rate",
]
HEADLINE_BY_TAG = [
    "text_f1",
    "text_order",
    "table_text_recall",
    "teds_matched",
    "heading_f1",
    "checks_pass_rate",
]


def bundled_ground_truth() -> Path:
    return Path(str(files("pdf_eval") / "ground_truth" / "dp-bench"))


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def _score_document(args: Tuple[GroundTruth, Path, FrozenSet[str]]) -> dict:
    gt, pred_path, optional = args
    scores, checks = evaluate_document(gt, _read(pred_path), optional)
    return {
        "document_id": gt.doc_id,
        "tags": gt.tags,
        "prediction_available": pred_path.is_file(),
        "scores": scores,
        "checks": checks,
    }


def _parse_engine(spec: str) -> Tuple[str, Path, Path]:
    """Return ``(engine name, markdown folder, engine folder)``."""

    name, sep, path = spec.partition("=")
    folder = Path(path if sep else spec)
    engine_name = name if sep else folder.resolve().name
    markdown = folder / "markdown" if (folder / "markdown").is_dir() else folder
    return engine_name, markdown, folder


def _unsupported(engine_dir: Path, documents: Sequence[GroundTruth]) -> Set[str]:
    path = engine_dir / "unsupported.txt"
    if not path.is_file():
        return set()
    ids: Set[str] = set()
    tags: Set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        entry = line.split("#", 1)[0].strip()
        if entry.startswith("tag:"):
            tags.add(entry[4:].strip())
        elif entry:
            ids.add(entry)
    return {gt.doc_id for gt in documents if gt.doc_id in ids or tags & set(gt.tags)}


def evaluate_engine(
    documents: Sequence[GroundTruth],
    pred_dir: Path,
    optional: FrozenSet[str],
    jobs: int,
) -> List[dict]:
    tasks = [(gt, pred_dir / f"{gt.doc_id}.md", optional) for gt in documents]
    if jobs == 1:
        return [_score_document(task) for task in tasks]
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        return list(pool.map(_score_document, tasks, chunksize=4))


def _write_engine(out_dir: Path, engine: str, result: dict) -> None:
    engine_dir = out_dir / engine
    engine_dir.mkdir(parents=True, exist_ok=True)
    (engine_dir / "evaluation.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    with (engine_dir / "evaluation.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["document_id", "tags", "prediction_available", *ALL_METRICS]
        )
        writer.writeheader()
        for doc in result["documents"]:
            row = {
                "document_id": doc["document_id"],
                "tags": " ".join(doc["tags"]),
                "prediction_available": doc["prediction_available"],
            }
            row.update({k: "" if v is None else v for k, v in doc["scores"].items()})
            writer.writerow(row)


def _present(summaries: Dict[str, dict], metrics: Sequence[str]) -> List[str]:
    return [
        metric
        for metric in metrics
        if any(summary[metric]["mean"] is not None for summary in summaries.values())
    ]


def _coverage_table(results: Dict[str, dict]) -> str:
    rows = ["| engine | scored | unsupported | missing output |", "|---|---|---|---|"]
    for engine, result in results.items():
        rows.append(
            f"| {engine} | {len(result['documents'])} | {len(result['unsupported'])} "
            f"| {result['missing_predictions']} |"
        )
    return "\n".join(rows)


def _checks_table(results: Dict[str, dict]) -> Optional[str]:
    totals: Dict[str, Dict[str, List[int]]] = {}
    for engine, result in results.items():
        counts: Dict[str, List[int]] = defaultdict(lambda: [0, 0])
        for doc in result["documents"]:
            for check in doc["checks"]:
                counts[check["type"]][0] += check["passed"]
                counts[check["type"]][1] += 1
        totals[engine] = counts
    kinds = [k for k in CHECK_TYPES if any(k in c for c in totals.values())]
    if not kinds:
        return None
    rows = [
        "| engine | " + " | ".join(kinds) + " |",
        "|---|" + "---|" * len(kinds),
    ]
    for engine, counts in totals.items():
        cells = [
            f"{counts[k][0] / counts[k][1]:.3f} ({counts[k][0]}/{counts[k][1]})" if counts[k][1] else "–"
            for k in kinds
        ]
        rows.append(f"| {engine} | " + " | ".join(cells) + " |")
    return "\n".join(rows)


def _write_summary(
    out_dir: Path, results: Dict[str, dict], tags: Sequence[str]
) -> str:
    summaries = {engine: result["summary"] for engine, result in results.items()}
    sections = ["## Coverage", _coverage_table(results)]

    original = _present(summaries, HEADLINE_ORIGINAL)
    if original:
        sections += ["## Original opendataloader-bench metrics", markdown_table(summaries, original)]
    new = _present(summaries, HEADLINE_NEW)
    if new:
        sections += ["## Additional metrics", markdown_table(summaries, new)]
    checks = _checks_table(results)
    if checks:
        sections += ["## Checks passed, by type", checks]

    for tag in tags:
        tagged = {
            engine: result["by_tag"][tag]
            for engine, result in results.items()
            if tag in result["by_tag"]
        }
        metrics = _present(tagged, HEADLINE_BY_TAG)
        if tagged and metrics:
            sections += [f"## Documents tagged `{tag}`", markdown_table(tagged, metrics)]

    sections.append(
        "Mean [95% bootstrap interval] #rank. n = documents the metric applies to."
    )
    report = "\n\n".join(sections)
    (out_dir / "summary.md").write_text(report + "\n", encoding="utf-8")

    metrics = ["overall_balanced", *ALL_METRICS]
    with (out_dir / "summary.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["engine", "group", "metric", "mean", "n", "ci_low", "ci_high"])
        for engine, result in results.items():
            groups = [("all", result["summary"])] + [
                (f"tag:{tag}", summary) for tag, summary in result["by_tag"].items()
            ]
            for group, summary in groups:
                for metric in metrics:
                    stats = summary[metric]
                    writer.writerow(
                        [engine, group, metric, stats["mean"], stats["n"], stats["ci_low"], stats["ci_high"]]
                    )
    return report


def _parse_optional(value: str) -> FrozenSet[str]:
    if value.strip().lower() == "none":
        return frozenset()
    return frozenset(part.strip() for part in value.split(",") if part.strip())


def _parse_args(argv: Optional[List[str]]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="pdf-eval",
        description=__doc__.split("\n\n")[0],
        epilog="\n\n".join(__doc__.split("\n\n")[1:]),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("predictions", nargs="+", help="prediction folders, optionally name=path")
    parser.add_argument("--gt", type=Path, default=None, help="ground-truth folder (default: bundled DP-Bench)")
    parser.add_argument("--out", type=Path, default=Path("pdf-eval-results"), help="output folder")
    parser.add_argument(
        "--optional",
        type=_parse_optional,
        default=DEFAULT_OPTIONAL,
        help="element categories whose text is optional, comma-separated, or 'none' "
        f"(default: {','.join(sorted(DEFAULT_OPTIONAL))})",
    )
    parser.add_argument("--jobs", type=int, default=0, help="worker processes (default: all CPUs)")
    parser.add_argument("--doc-id", default=None, help="score only this document")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> None:
    args = _parse_args(argv)
    gt_dir = args.gt or bundled_ground_truth()
    documents = load_ground_truth(gt_dir)
    if args.doc_id:
        documents = [gt for gt in documents if gt.doc_id == args.doc_id]
    if not documents:
        sys.exit(f"No ground-truth documents (.md or .json) in {gt_dir}")
    jobs = args.jobs or os.cpu_count() or 1
    tags = sorted({tag for gt in documents for tag in gt.tags})

    args.out.mkdir(parents=True, exist_ok=True)
    results: Dict[str, dict] = {}
    for spec in args.predictions:
        engine, pred_dir, engine_dir = _parse_engine(spec)
        if not pred_dir.is_dir():
            print(f"skipping {spec}: not a folder", file=sys.stderr)
            continue
        unsupported = _unsupported(engine_dir, documents)
        scored = [gt for gt in documents if gt.doc_id not in unsupported]
        docs = evaluate_engine(scored, pred_dir, args.optional, jobs)
        by_tag = {}
        for tag in tags:
            tagged = [doc["scores"] for doc in docs if tag in doc["tags"]]
            if tagged:
                by_tag[tag] = summarize(tagged, ALL_METRICS)
        result = {
            "summary": summarize([doc["scores"] for doc in docs], ALL_METRICS),
            "by_tag": by_tag,
            "optional_categories": sorted(args.optional),
            "unsupported": sorted(unsupported),
            "missing_predictions": sum(not doc["prediction_available"] for doc in docs),
            "documents": docs,
        }
        results[engine] = result
        _write_engine(args.out, engine, result)
        print(
            f"{engine}: {len(docs)} scored, {len(unsupported)} unsupported, "
            f"{result['missing_predictions']} missing",
            file=sys.stderr,
        )

    if results:
        print(_write_summary(args.out, results, tags))


if __name__ == "__main__":
    main()
