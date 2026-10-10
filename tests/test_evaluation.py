from evals.run import citation_metrics, run_case


def test_unknown_citation_ids_are_flagged():
    metrics = citation_metrics('A [1](#source-S1) B [9](#source-S9)', [{'id': 'S1'}])
    assert metrics['invalid_citations'] == 1


def test_offline_results_cannot_be_mistaken_for_measured_quality():
    rows = run_case({'id': 'fixture', 'company': 'Example', 'question': 'Example?', 'rubric': ['Evidence']}, offline=True)
    assert len(rows) == 2
    assert all(row['offline_fixture'] and row['human_review']['accuracy_0_to_4'] is None for row in rows)
