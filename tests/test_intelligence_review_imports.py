import phase0.intelligence as intelligence
from phase0.intelligence import candidates, review


def test_candidate_io_exports_remain_compatible() -> None:
    assert intelligence._write_candidates is candidates.write_candidates
    assert intelligence._write_review_csv is candidates.write_review_csv
    assert intelligence._read_candidate_rows is candidates.read_candidate_rows


def test_review_exports_remain_compatible() -> None:
    assert intelligence.review_intelligence_candidates is review.review_intelligence_candidates
    assert intelligence._source_excerpt is review._source_excerpt
    assert intelligence._contains_any is review._contains_any
    assert intelligence._review_suggestion is review._review_suggestion
    assert intelligence._write_review_report is review._write_review_report
