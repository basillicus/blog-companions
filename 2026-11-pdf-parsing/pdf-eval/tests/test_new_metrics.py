from pytest import approx

from pdf_eval import evaluate
from pdf_eval.evaluator_heading_detection import evaluate_heading_detection
from pdf_eval.evaluator_table_content import evaluate_table_matched, table_text_recall
from pdf_eval.evaluator_text import evaluate_text
from pdf_eval.normalize import text_tokens
from pdf_eval.report import rank, summarize

PARA_A = "The quick brown fox jumps over the lazy dog near the river bank."
PARA_B = "Meanwhile a second paragraph describes something entirely different here."

TABLE_GT = (
    "<table><tr><th>Name</th><th>Value</th></tr>"
    "<tr><td>alpha</td><td>1</td></tr><tr><td>beta</td><td>2</td></tr></table>"
)
TABLE_MD = "| Name | Value |\n|---|---|\n| alpha | 1 |\n| beta | 2 |\n"
TABLE_SMALL = "<table><tr><td>x</td><td>y</td></tr></table>"


def test_markup_does_not_change_tokens():
    plain = "Efficient ﬁnancial reporting is important"
    marked = "**Efficient** [ﬁnan-\ncial](http://x.y/z) <b>reporting</b> is important"
    assert text_tokens(marked) == text_tokens(plain)
    assert text_tokens(TABLE_MD) == text_tokens(TABLE_GT)


def test_identical_text_scores_one():
    scores = evaluate_text(PARA_A, PARA_A)
    assert scores == {"text_recall": 1.0, "text_precision": 1.0, "text_f1": 1.0, "text_order": 1.0}


def test_extra_text_lowers_only_precision():
    scores = evaluate_text(PARA_A, PARA_A + "\n\nPage 3 of 10 Confidential")
    assert scores["text_recall"] == 1.0
    assert scores["text_order"] == 1.0
    assert scores["text_precision"] < 1.0


def test_missing_text_lowers_only_recall():
    scores = evaluate_text(PARA_A + "\n\n" + PARA_B, PARA_A)
    assert scores["text_precision"] == 1.0
    assert scores["text_order"] == 1.0
    assert scores["text_recall"] < 1.0


def test_wrong_order_lowers_only_order():
    scores = evaluate_text(PARA_A + "\n\n" + PARA_B, PARA_B + "\n\n" + PARA_A)
    assert scores["text_recall"] == 1.0
    assert scores["text_precision"] == 1.0
    assert scores["text_order"] < 1.0


def test_empty_prediction():
    scores = evaluate_text(PARA_A, "")
    assert scores["text_recall"] == 0.0
    assert scores["text_precision"] == 0.0
    assert scores["text_order"] is None


def test_table_text_recall_credits_plain_text_tables():
    plain = "Name Value\nalpha 1\nbeta 2"
    assert table_text_recall(TABLE_GT, plain) == 1.0
    assert evaluate(TABLE_GT, plain)["teds"] == 0.0
    assert table_text_recall(TABLE_GT, "alpha only") == approx(1 / 6)
    assert table_text_recall(PARA_A, PARA_A) is None


def test_table_text_recall_consumes_matches():
    gt = "<table><tr><td>1</td><td>1</td></tr></table>"
    assert table_text_recall(gt, "1") == 0.5


def test_teds_matched_identical_and_markdown_tables():
    scores = evaluate_table_matched(TABLE_GT, TABLE_MD)
    assert scores == {"teds_matched": 1.0, "teds_s_matched": 1.0}


def test_teds_matched_weights_missing_table_by_size():
    gt = TABLE_GT + "\n\n" + TABLE_SMALL
    only_big = evaluate_table_matched(gt, TABLE_GT)["teds_matched"]
    only_small = evaluate_table_matched(gt, TABLE_SMALL)["teds_matched"]
    assert only_big == approx(6 / 8)
    assert only_small == approx(2 / 8)


def test_teds_matched_penalizes_spurious_tables():
    scores = evaluate_table_matched(TABLE_GT, TABLE_GT + "\n\n" + TABLE_SMALL)
    assert scores["teds_matched"] == approx(6 / 8)


def test_teds_matched_without_tables():
    assert evaluate_table_matched(PARA_A, PARA_A)["teds_matched"] is None
    assert evaluate_table_matched(TABLE_GT, PARA_A)["teds_matched"] == 0.0


def test_heading_text_found_without_heading_markup():
    gt = "# Introduction\n\n" + PARA_A + "\n\n# Results\n\n" + PARA_B
    plain = "Introduction\n\n" + PARA_A + "\n\nResults\n\n" + PARA_B
    scores = evaluate_heading_detection(gt, plain)
    assert scores["heading_text_recall"] == 1.0
    assert scores["heading_f1"] == 0.0


def test_heading_precision_and_recall():
    gt = "# Introduction\n\ntext\n\n# Results\n\ntext"
    pred = "# Introduction\n\ntext\n\n# Some footer\n\n# Another footer"
    scores = evaluate_heading_detection(gt, pred)
    assert scores["heading_recall"] == 0.5
    assert scores["heading_precision"] == approx(1 / 3)


def test_heading_level_accuracy_uses_relative_levels():
    gt = "# Title\n\n## Part one\n\n## Part two"
    shifted = "## Title\n\n### Part one\n\n### Part two"
    flat = "# Title\n\n# Part one\n\n# Part two"
    assert evaluate_heading_detection(gt, shifted)["heading_level_accuracy"] == 1.0
    assert evaluate_heading_detection(gt, flat)["heading_level_accuracy"] == approx(1 / 3)
    assert evaluate_heading_detection(flat, gt)["heading_level_accuracy"] is None


def test_evaluate_returns_all_metrics():
    from pdf_eval import ALL_METRICS

    scores = evaluate("# A\n\n" + PARA_A + "\n\n" + TABLE_GT, "# A\n\n" + PARA_A + "\n\n" + TABLE_MD)
    assert list(scores) == ALL_METRICS
    assert scores["overall"] == approx(1.0)


def test_summarize_counts_and_intervals():
    docs = [{"nid": 1.0, "teds": None, "mhs": 0.5}, {"nid": 0.5, "teds": 0.0, "mhs": None}]
    summary = summarize(docs, ["nid", "teds", "mhs"])
    assert summary["nid"]["mean"] == 0.75
    assert summary["teds"]["n"] == 1
    assert summary["overall_balanced"]["mean"] == approx((0.75 + 0.0 + 0.5) / 3)
    assert summary["nid"]["ci_low"] <= 0.75 <= summary["nid"]["ci_high"]


def test_rank_shares_ties():
    summaries = {
        "a": {"nid": {"mean": 0.9}},
        "b": {"nid": {"mean": 0.9}},
        "c": {"nid": {"mean": 0.5}},
    }
    assert rank(summaries, "nid") == {"a": 1, "b": 1, "c": 3}
