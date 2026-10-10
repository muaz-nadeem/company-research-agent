"""Import existing owned thread checkpoints into explicit message history.

Run once after migrate.py, with the API stopped. Re-running skips imported threads.
It uses ownership from the existing threads table, never guesses owners from UUIDs.
"""
import json
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT / '.env')
from backend.store import Store, now
from graph.builder import get_graph
from langchain_core.messages import HumanMessage, AIMessage


def import_legacy(store, graph):
    imported = 0
    with store.connection() as conn:
        threads = [dict(row) for row in store.sql(conn, 'SELECT thread_id,user_id FROM threads').fetchall()]
    for thread in threads:
        tid, user = thread['thread_id'], str(thread['user_id'])
        if store.detail(user, tid)['messages']:
            continue
        config = {'configurable': {'thread_id': tid}}
        snapshot = graph.get_state(config)
        values = snapshot.values or {}
        transcript = [m for m in values.get('messages', []) if isinstance(m, (HumanMessage, AIMessage)) and isinstance(m.content, str)]
        questions = [str(intr.value) for task in snapshot.tasks for intr in task.interrupts or []]
        if not transcript:
            continue
        stamp, rid = now(), str(uuid.uuid4())
        mids = [str(uuid.uuid5(uuid.NAMESPACE_URL, f'synapse:{tid}:legacy:{i}')) for i in range(len(transcript))]
        latest_user = next((i for i in reversed(range(len(transcript))) if isinstance(transcript[i], HumanMessage)), None)
        if latest_user is None:
            continue
        with store.connection() as conn:
            store.owned(conn, user, tid, lock=True)
            if store.sql(conn, 'SELECT id FROM messages WHERE thread_id=? LIMIT 1', (tid,)).fetchone():
                continue
            store.sql(conn, 'INSERT INTO research_runs(id,thread_id,user_id,request_id,message_id,prompt,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)',
                (rid, tid, user, str(uuid.uuid4()), mids[latest_user], transcript[latest_user].content,
                 'needs_clarification' if questions else 'completed', stamp, stamp))
            for i, message in enumerate(transcript):
                # Stable sequence in timestamps preserves the old conversation ordering.
                created = stamp[:19] + f'.{i:06d}+00:00'
                store.sql(conn, 'INSERT INTO messages(id,thread_id,run_id,role,content,status,sources,created_at) VALUES(?,?,?,?,?,?,?,?)',
                    (mids[i], tid, rid, 'user' if isinstance(message, HumanMessage) else 'assistant', message.content, 'sent', json.dumps([]), created))
            if questions:
                store.sql(conn, 'INSERT INTO messages(id,thread_id,run_id,role,content,status,created_at) VALUES(?,?,?,?,?,?,?)',
                    (str(uuid.uuid4()), tid, rid, 'assistant', questions[0], 'sent', stamp[:19] + f'.{len(transcript):06d}+00:00'))
                graph.update_state(config, {'clarity_status': 'needs_clarification', 'clarification_question': questions[0],
                    'final_answer': None, 'request_message_id': mids[latest_user]}, as_node='clarity')
                # Reach the new stable interrupt node without making an LLM call.
                graph.invoke(None, config)
        imported += 1
    return imported


if __name__ == '__main__':
    store = Store()
    store.initialize()
    print(f'Imported {import_legacy(store, get_graph())} legacy conversations.')
