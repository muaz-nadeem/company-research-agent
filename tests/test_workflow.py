import sqlite3
from uuid import uuid4
from langchain_core.messages import AIMessage
from langgraph.checkpoint.sqlite import SqliteSaver

import graph.builder as builder
from graph.service import execute_run


def fake_nodes(monkeypatch):
    def clarity(state):
        last = state['messages'][-1].content
        if last == 'a company':
            return {'clarity_status': 'needs_clarification', 'clarification_question': 'Which company?'}
        return {'clarity_status': 'clear', 'company_name': last, 'user_question': last}
    monkeypatch.setattr(builder, 'clarity_node', clarity)
    monkeypatch.setattr(builder, 'research_node', lambda state: {'research_findings': 'evidence', 'sources': [], 'research_attempts': 1})
    monkeypatch.setattr(builder, 'validator_node', lambda state: {'validation_result': 'sufficient'})
    def synthesis(state):
        answer = 'Report: ' + state['user_question']
        return {'final_answer': answer, 'messages': [AIMessage(content=answer)]}
    monkeypatch.setattr(builder, 'synthesis_node', synthesis)


def run_data(prompt, tid=None, **changes):
    return {'prompt': prompt, 'thread_id': tid or str(uuid4()), 'message_id': str(uuid4()), 'resume': False, **changes}


def test_clarification_survives_database_reopen(monkeypatch, tmp_path):
    fake_nodes(monkeypatch)
    path = str(tmp_path / 'checkpoints.db')
    first = run_data('a company')
    with sqlite3.connect(path, check_same_thread=False) as conn:
        graph = builder.build_graph(SqliteSaver(conn))
        result = execute_run(first, lambda _: None, lambda: False, graph)
        assert result['status'] == 'needs_clarification'
    with sqlite3.connect(path, check_same_thread=False) as conn:
        graph = builder.build_graph(SqliteSaver(conn))
        result = execute_run(run_data('Stripe', first['thread_id'], resume=True), lambda _: None, lambda: False, graph)
        assert result['answer'] == 'Report: Stripe'


def test_followup_resets_previous_answer_and_retry_does_not_duplicate(monkeypatch, tmp_path):
    fake_nodes(monkeypatch)
    with sqlite3.connect(str(tmp_path / 'cp.db'), check_same_thread=False) as conn:
        graph = builder.build_graph(SqliteSaver(conn))
        first = run_data('Stripe')
        execute_run(first, lambda _: None, lambda: False, graph)
        followup = run_data('Competitors', first['thread_id'])
        result = execute_run(followup, lambda _: None, lambda: False, graph)
        assert result['answer'] == 'Report: Competitors'
        retried = execute_run({**followup, 'retry_of': str(uuid4())}, lambda _: None, lambda: False, graph)
        assert retried['answer'] == result['answer']
        state = graph.get_state({'configurable': {'thread_id': first['thread_id']}})
        assert len(state.values['messages']) == 4
