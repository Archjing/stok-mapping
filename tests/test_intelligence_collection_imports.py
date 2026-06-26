import phase0.intelligence as intelligence
from phase0.intelligence import collection


def test_collection_public_exports_remain_compatible() -> None:
    assert intelligence.collect_intelligence is collection.collect_intelligence
    assert intelligence.import_local_intelligence is collection.import_local_intelligence


def test_collection_private_helpers_remain_compatible() -> None:
    assert intelligence._candidate_id is collection._candidate_id
    assert intelligence._candidate_row is collection._candidate_row
    assert intelligence._topic_tags_from_text is collection._topic_tags_from_text
    assert intelligence._strategy_tags_from_topics is collection._strategy_tags_from_topics
    assert intelligence._dedupe_rows is collection._dedupe_rows
    assert intelligence._write_collect_report is collection._write_collect_report
    assert intelligence._title_from_markdown is collection._title_from_markdown
    assert intelligence._relative_source is collection._relative_source
    assert intelligence._rows_from_local_file is collection._rows_from_local_file
    assert intelligence._collect_local_dir is collection._collect_local_dir
    assert intelligence._fetch_rss is collection._fetch_rss
    assert intelligence._fetch_arxiv is collection._fetch_arxiv
    assert intelligence._fetch_openalex is collection._fetch_openalex
    assert intelligence._fetch_crossref is collection._fetch_crossref
