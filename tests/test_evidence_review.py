import graph.nodes as nodes


def test_only_approved_claims_reach_synthesis(monkeypatch):
    monkeypatch.setattr(nodes, 'ask_json', lambda *_: {'validation_result': 'sufficient', 'reasoning': 'Only first claim supported',
        'retry_recommended': False, 'approved_claim_indices': [0, 0, 99, {}, True], 'unsupported_claims': ['Second claim']})
    state = {'user_question': 'Question', 'sources': [{'id': 'S1'}], 'claims': [
        {'text': 'Supported', 'source_ids': ['S1']}, {'text': 'Unsupported', 'source_ids': ['S1']}]}
    result = nodes.validator_node(state)
    assert result['claims'] == [state['claims'][0]]
    assert result['validation_result'] == 'insufficient'


def test_no_approved_claims_is_not_reported_as_sufficient(monkeypatch):
    monkeypatch.setattr(nodes, 'ask_json', lambda *_: {'validation_result': 'sufficient', 'approved_claim_indices': []})
    result = nodes.validator_node({'user_question': 'Question', 'sources': [{'id': 'S1'}], 'claims': []})
    assert result['validation_result'] == 'insufficient'
    assert 'No claims passed' in result['validation_feedback']
