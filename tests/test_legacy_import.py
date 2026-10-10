import sqlite3
from uuid import uuid4
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from backend.store import Store, now
from graph.builder import build_graph
from scripts.import_legacy import import_legacy


def test_legacy_import_preserves_order_and_is_idempotent(tmp_path):
    store = Store(f'sqlite:///{tmp_path / "app.db"}')
    store.initialize()
    tid = str(uuid4())
    with store.connection() as conn:
        store.sql(conn, 'INSERT INTO threads(thread_id,user_id,title,created_at,updated_at) VALUES(?,?,?,?,?)', (tid, 'alice', 'Old chat', now(), now()))
    with sqlite3.connect(str(tmp_path / 'cp.db'), check_same_thread=False) as conn:
        graph = build_graph(SqliteSaver(conn))
        graph.update_state({'configurable': {'thread_id': tid}}, {'messages': [HumanMessage(content='Old question'), AIMessage(content='Old answer')], 'final_answer': 'Old answer'}, as_node='synthesis')
        assert import_legacy(store, graph) == 1
        assert import_legacy(store, graph) == 0
    assert [message['content'] for message in store.detail('alice', tid)['messages']] == ['Old question', 'Old answer']
