import os
import sqlite3
import time
from functools import lru_cache
from pathlib import Path

from langgraph.graph import END, StateGraph

from graph.nodes import clarify_node, clarity_node, emit, research_node, synthesis_node, validator_node
from graph.routing import route_after_clarity, route_after_validator
from graph.state import ResearchState


def _build_checkpointer():
    url = os.getenv("CHECKPOINT_DATABASE_URL") or os.getenv("DATABASE_URL")
    if url and not url.startswith('sqlite:///'):
        import psycopg
        from langgraph.checkpoint.postgres import PostgresSaver
        from psycopg.rows import dict_row
        conn = psycopg.connect(url, autocommit=True, prepare_threshold=0, row_factory=dict_row, connect_timeout=10)
        saver = PostgresSaver(conn)
        saver.setup()
        from psycopg import sql
        for role in ('anon', 'authenticated'):
            if conn.execute('SELECT 1 FROM pg_roles WHERE rolname=%s', (role,)).fetchone():
                for table in ('checkpoints', 'checkpoint_blobs', 'checkpoint_writes', 'checkpoint_migrations'):
                    conn.execute(sql.SQL('REVOKE ALL ON {} FROM {}').format(sql.Identifier(table), sql.Identifier(role)))
        return saver
    if os.getenv("APP_ENV") == "production":
        raise RuntimeError("Production requires a PostgreSQL checkpoint database")
    from langgraph.checkpoint.sqlite import SqliteSaver
    path = url.removeprefix('sqlite:///') if url else os.getenv("SQLITE_CHECKPOINT_PATH", str(Path(__file__).resolve().parent.parent / "checkpoints.db"))
    return SqliteSaver(sqlite3.connect(path, check_same_thread=False))


def instrument(name, fn):
    def node(state):
        start = time.monotonic()
        emit({"type": "stage", "stage": name, "status": "running"})
        result = fn(state)
        emit({"type": "stage", "stage": name, "status": "completed", "duration_ms": round((time.monotonic() - start) * 1000)})
        return result
    return node


def build_graph(checkpointer=None):
    builder = StateGraph(ResearchState)
    for name, fn in (("clarity", clarity_node), ("research", research_node), ("validator", validator_node), ("synthesis", synthesis_node)):
        builder.add_node(name, instrument(name, fn))
    builder.add_node("clarify", clarify_node)
    builder.set_entry_point("clarity")
    builder.add_conditional_edges("clarity", route_after_clarity, {"research": "research", "clarify": "clarify", "end": END})
    builder.add_edge("clarify", "clarity")
    builder.add_edge("research", "validator")
    builder.add_conditional_edges("validator", route_after_validator, {"research": "research", "synthesis": "synthesis"})
    builder.add_edge("synthesis", END)
    return builder.compile(checkpointer=checkpointer if checkpointer is not None else _build_checkpointer())


@lru_cache(maxsize=1)
def get_graph():
    return build_graph()
