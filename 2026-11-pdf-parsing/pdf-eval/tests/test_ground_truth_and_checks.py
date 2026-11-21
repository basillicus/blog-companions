import csv
import json

from pytest import approx, raises

from pdf_eval import GroundTruth, evaluate, load_ground_truth
from pdf_eval.cli import main
from pdf_eval.evaluator_checks import run_checks, table_grid
from pdf_eval.ground_truth import Element, render_markdown

BODY = "The quick brown fox jumps over the lazy dog near the river bank."
ELEMENTS = [
    {"category": "Header", "text": "ACME Annual Report"},
    {"category": "heading1", "text": "Results"},
    {"category": "paragraph", "text": BODY},
    {"category": "Page-Footer", "text": "2"},
]


def _write(folder, name, content):
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_text(content if isinstance(content, str) else json.dumps(content), encoding="utf-8")
    return path


def test_json_only_ground_truth_is_rendered_and_tagged(tmp_path):
    _write(tmp_path, "doc.json", {"type": "scan", "tags": ["english"], "elements": ELEMENTS})
    (gt,) = load_ground_truth(tmp_path)
    assert gt.markdown == f"ACME Annual Report\n\n# Results\n\n{BODY}\n\n2"
    assert gt.tags == ["scan", "english", "has:headers_footers", "has:headings"]
    assert [e.category for e in gt.elements] == ["header", "heading1", "paragraph", "footer"]


def test_markdown_file_stays_the_reference(tmp_path):
    _write(tmp_path, "doc.md", "corrected text")
    _write(tmp_path, "doc.json", {"elements": [{"category": "paragraph", "text": "old text"}]})
    (gt,) = load_ground_truth(tmp_path)
    assert gt.markdown == "corrected text"


def test_dp_bench_element_format(tmp_path):
    table = {"category": "Table", "content": {"text": "", "html": "<tr><td>a</td></tr>"}}
    _write(tmp_path, "doc.json", {"elements": [table]})
    (gt,) = load_ground_truth(tmp_path)
    assert gt.elements == [Element("table", "", "<tr><td>a</td></tr>")]
    assert "<td>" in gt.markdown
    assert gt.tags == ["has:tables"]


def _gt():
    elements = [Element(e["category"].lower().replace("page-", ""), e["text"]) for e in ELEMENTS]
    return GroundTruth("doc", markdown=render_markdown(elements), elements=elements)


def test_dropping_optional_text_is_not_penalized():
    scores = evaluate(_gt(), f"# Results\n\n{BODY}")
    assert scores["text_recall"] == 1.0
    assert scores["text_precision"] == 1.0
    strict = evaluate(_gt(), f"# Results\n\n{BODY}", optional=())
    assert strict["text_recall"] < 1.0


def test_keeping_optional_text_is_not_penalized():
    scores = evaluate(_gt(), f"ACME Annual Report\n\n# Results\n\n{BODY}\n\n2")
    assert scores["text_precision"] == 1.0
    assert scores["text_order"] == 1.0


def test_footer_is_removed_from_the_end():
    elements = [Element("paragraph", "We counted 2 foxes today."), Element("footer", "2")]
    gt = GroundTruth("doc", markdown=render_markdown(elements), elements=elements)
    scores = evaluate(gt, "We counted foxes today.")
    assert scores["text_recall"] == approx(4 / 5)


def test_header_marked_as_heading_is_not_a_false_heading():
    scores = evaluate(_gt(), f"# ACME Annual Report\n\n# Results\n\n{BODY}")
    assert scores["heading_precision"] == 1.0
    strict = evaluate(_gt(), f"# ACME Annual Report\n\n# Results\n\n{BODY}", optional=())
    assert strict["heading_precision"] == 0.5


def test_original_metrics_ignore_optional_setting():
    pred = f"# Results\n\n{BODY}"
    a, b = evaluate(_gt(), pred), evaluate(_gt(), pred, optional=())
    for metric in ("overall", "nid", "mhs"):
        assert a[metric] == b[metric]


PRED = """# Introduction

Total revenue rose by 12% in 2023.

| Item | 2022 | 2023 |
|---|---|---|
| Revenue | 3.9 | 4.2 |
| Costs | 2.0 | 2.5 |

## Conclusion

The end.
"""


def _passed(checks, pred=PRED):
    return [result["passed"] for result in run_checks(checks, pred)]


def test_present_absent_and_order_checks():
    assert _passed(
        [
            {"type": "present", "text": "total REVENUE rose by 12%"},
            {"type": "present", "text": "revenue fell"},
            {"type": "absent", "text": "confidential"},
            {"type": "absent", "text": "the end"},
            {"type": "order", "before": "Introduction", "after": "Conclusion"},
            {"type": "order", "before": "Conclusion", "after": "Introduction"},
        ]
    ) == [True, False, True, False, True, False]


def test_present_check_matches_whole_words_unless_fuzzy():
    assert _passed([{"type": "present", "text": "rev"}]) == [False]
    assert _passed([{"type": "present", "text": "Total revenue rose by 13%", "fuzzy": 0.9}]) == [True]


def test_heading_checks():
    assert _passed(
        [
            {"type": "heading", "text": "Conclusion"},
            {"type": "heading", "text": "Conclusion", "level": 2},
            {"type": "heading", "text": "Conclusion", "level": 1},
            {"type": "heading", "text": "The end"},
        ]
    ) == [True, True, False, False]


def test_table_checks_use_row_and_column():
    assert _passed(
        [
            {"type": "table", "cell": "4.2", "row": "Revenue", "column": "2023"},
            {"type": "table", "cell": "4.2", "row": "Costs"},
            {"type": "table", "cell": "2.5", "column": "2022"},
            {"type": "table", "cell": "3.9"},
        ]
    ) == [True, False, False, True]
    assert _passed([{"type": "table", "cell": "4.2"}], pred="Revenue 3.9 4.2") == [False]


def test_table_grid_expands_spans():
    html = (
        "<table><tr><td rowspan='2'>A</td><td colspan='2'>B</td></tr>"
        "<tr><td>c</td><td>d</td></tr></table>"
    )
    assert table_grid(html) == [["a", "b", "b"], ["a", "c", "d"]]


def test_unknown_check_type_is_an_error():
    with raises(ValueError):
        run_checks([{"type": "nonsense"}], PRED)


def test_cli_with_checks_only_document_and_unsupported_images(tmp_path, capsys):
    gt_dir = tmp_path / "gt"
    _write(gt_dir, "report.md", PRED)
    _write(gt_dir, "photo.json", {"type": "image", "checks": [{"type": "present", "text": "hello world"}]})
    _write(gt_dir, "scan.json", {"type": "scan", "checks": [{"type": "present", "text": "hello world"}]})

    good = tmp_path / "good"
    _write(good, "report.md", PRED)
    _write(good, "photo.md", "Hello, world!")
    _write(good, "scan.md", "nothing here")
    pdf_only = tmp_path / "pdf_only"
    _write(pdf_only, "report.md", PRED)
    _write(pdf_only, "unsupported.txt", "tag:image  # cannot read images\n")

    main([str(good), str(pdf_only), "--gt", str(gt_dir), "--out", str(tmp_path / "out"), "--jobs", "1"])
    report = capsys.readouterr().out
    assert "## Documents tagged `image`" in report
    assert "| pdf_only | 2 | 1 | 1 |" in report

    rows = {
        (r["engine"], r["group"], r["metric"]): r
        for r in csv.DictReader((tmp_path / "out" / "summary.csv").open())
    }
    assert float(rows[("good", "all", "checks_pass_rate")]["mean"]) == 0.5
    assert float(rows[("good", "tag:image", "checks_pass_rate")]["mean"]) == 1.0
    assert float(rows[("pdf_only", "all", "checks_pass_rate")]["mean"]) == 0.0
    assert ("pdf_only", "tag:image", "checks_pass_rate") not in rows
    assert float(rows[("good", "all", "nid")]["mean"]) == 1.0
