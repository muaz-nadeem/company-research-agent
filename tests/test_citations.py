from graph.nodes import normalize_citations


def test_plain_and_linked_citations_only_resolve_to_retrieved_sources():
    sources = [{'id': 'S1'}, {'id': 'S3'}]
    result = normalize_citations('Fact [1, 3]. Other [S1]. Bad [99]. Linked [3](#source-S3). Bad [9](#source-S9).', sources)
    assert 'Fact [1](#source-S1) [3](#source-S3)' in result
    assert 'Other [1](#source-S1)' in result
    assert result.count('[source unavailable]') == 2
    assert 'Linked [3](#source-S3)' in result


def test_citations_do_not_rewrite_regular_markdown_links():
    assert normalize_citations('[1](https://example.com)', [{'id': 'S1'}]) == '[1](https://example.com)'
