"""Transactional application storage, independent of agent checkpoints."""
import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat()


class StoreError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


class Store:
    def __init__(self, url=None):
        self.url = url or os.getenv("APP_DATABASE_URL") or os.getenv("DATABASE_URL") or "sqlite:///research.db"
        self.postgres = self.url.startswith(("postgres://", "postgresql://"))
        if os.getenv("APP_ENV") == "production" and not self.postgres:
            raise RuntimeError("Production requires PostgreSQL; configure DATABASE_URL")
        if not self.postgres and not self.url.startswith("sqlite:///"):
            raise RuntimeError("Use a PostgreSQL URL or sqlite:///path")

    @contextmanager
    def connection(self):
        if self.postgres:
            import psycopg
            from psycopg.rows import dict_row
            conn = psycopg.connect(self.url, row_factory=dict_row, connect_timeout=10)
        else:
            path = self.url.removeprefix("sqlite:///")
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(path, timeout=20)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("BEGIN IMMEDIATE")
        try:
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    def sql(self, conn, query, args=()):
        return conn.execute(query.replace("?", "%s") if self.postgres else query, args)

    def initialize(self):
        with self.connection() as conn:
            if self.postgres:
                # Apply versioned PostgreSQL migration explicitly before startup.
                self.sql(conn, "SELECT archived_at FROM threads LIMIT 1")
                self.sql(conn, "SELECT id FROM research_runs LIMIT 1")
            else:
                for query in SQLITE_SCHEMA.split(";"):
                    if query.strip():
                        conn.execute(query)

    @contextmanager
    def owner_lock(self):
        """Prevent a second API process from recovering another process's active runs."""
        if self.postgres:
            import psycopg
            conn = psycopg.connect(self.url, autocommit=True, connect_timeout=10)
            try:
                acquired = conn.execute("SELECT pg_try_advisory_lock(739291, 1)").fetchone()[0]
                if not acquired:
                    raise RuntimeError("Another Synapse worker is active; run a single API process")
                yield
            finally:
                conn.close()
        else:
            from filelock import FileLock
            with FileLock(self.url.removeprefix('sqlite:///') + '.owner.lock', timeout=0):
                yield

    def owned(self, conn, user, tid, lock=False):
        query = "SELECT * FROM threads WHERE thread_id=? AND user_id=?"
        if lock and self.postgres:
            query += " FOR UPDATE"
        row = self.sql(conn, query, (tid, user)).fetchone()
        if row is None:
            raise StoreError(404, "Conversation not found")
        return dict(row)

    def threads(self, user, archived=False, search="", limit=100, offset=0):
        with self.connection() as conn:
            rows = self.sql(conn,
                "SELECT thread_id,title,created_at,updated_at,archived_at FROM threads "
                "WHERE user_id=? AND archived_at IS " + ("NOT NULL" if archived else "NULL") +
                " AND (LOWER(title) LIKE ? OR EXISTS (SELECT 1 FROM messages m WHERE "
                "m.thread_id=threads.thread_id AND LOWER(m.content) LIKE ?)) "
                "ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                (user, f"%{search.lower()}%", f"%{search.lower()}%", limit, offset)).fetchall()
            return [dict(r) for r in rows]

    def detail(self, user, tid):
        with self.connection() as conn:
            thread = self.owned(conn, user, tid)
            messages = [dict(r) for r in self.sql(conn,
                "SELECT * FROM messages WHERE thread_id=? ORDER BY created_at,id", (tid,)).fetchall()]
            for message in messages:
                message["sources"] = json.loads(message["sources"])
            runs = [self.decode_run(r) for r in self.sql(conn,
                "SELECT * FROM research_runs WHERE thread_id=? ORDER BY created_at DESC", (tid,)).fetchall()]
            return {"thread": thread, "messages": messages, "runs": runs,
                    "awaiting_clarification": bool(runs and runs[0]["status"] == "needs_clarification")}

    def update_thread(self, user, tid, title=None, archived=None):
        with self.connection() as conn:
            self.owned(conn, user, tid, lock=True)
            if archived is not None and self.sql(conn,
                    "SELECT id FROM research_runs WHERE thread_id=? AND status IN ('queued','running')", (tid,)).fetchone():
                raise StoreError(409, "Stop the active research before archiving")
            if title is not None:
                self.sql(conn, "UPDATE threads SET title=? WHERE thread_id=?", (title, tid))
            if archived is not None:
                self.sql(conn, "UPDATE threads SET archived_at=? WHERE thread_id=?", (now() if archived else None, tid))

    def delete_thread(self, user, tid, delete_checkpoints):
        with self.connection() as conn:
            self.owned(conn, user, tid, lock=True)
            if self.sql(conn, "SELECT id FROM research_runs WHERE thread_id=? AND status IN ('queued','running')", (tid,)).fetchone():
                raise StoreError(409, "Stop the active research before deleting")
            # If checkpoint deletion fails, preserve the visible conversation for retry.
            delete_checkpoints(tid)
            self.sql(conn, "DELETE FROM threads WHERE thread_id=? AND user_id=?", (tid, user))

    def begin_run(self, user, body):
        tid, request_id = str(body.thread_id or uuid.uuid4()), str(body.request_id)
        with self.connection() as conn:
            if self.postgres:
                self.sql(conn, "SELECT pg_advisory_xact_lock(hashtextextended(?, 0))", (user,))
            previous = self.sql(conn, "SELECT * FROM research_runs WHERE user_id=? AND request_id=?", (user, request_id)).fetchone()
            if previous:
                previous = self.decode_run(previous)
                if (previous["prompt"] != body.message or (body.thread_id and previous["thread_id"] != tid)
                        or bool(previous["resume"]) != body.resume or previous["retry_of"] != (str(body.retry_of) if body.retry_of else None)):
                    raise StoreError(409, "Request ID already used for a different message")
                return previous, False
            active = self.sql(conn, "SELECT COUNT(*) AS count FROM research_runs WHERE user_id=? AND status IN ('queued','running')", (user,)).fetchone()["count"]
            if active >= int(os.getenv("MAX_ACTIVE_RUNS_PER_USER", "2")):
                raise StoreError(429, "You already have research in progress. Wait for a run to finish.")
            daily = self.sql(conn, "SELECT COUNT(*) AS count FROM research_runs WHERE user_id=? AND created_at>=?", (user, now()[:10])).fetchone()["count"]
            if daily >= int(os.getenv("MAX_DAILY_RUNS_PER_USER", "50")):
                raise StoreError(429, "Daily research limit reached. Come back tomorrow.")
            exists = self.sql(conn, "SELECT user_id FROM threads WHERE thread_id=?", (tid,)).fetchone()
            if exists:
                thread = self.owned(conn, user, tid, lock=True)
                if thread["archived_at"]:
                    raise StoreError(409, "Restore this conversation before sending a message")
            else:
                if body.resume or body.retry_of:
                    raise StoreError(404, "Conversation not found")
                self.sql(conn, "INSERT INTO threads(thread_id,user_id,title,created_at,updated_at) VALUES(?,?,?,?,?)",
                         (tid, user, body.message[:100], now(), now()))
            if self.sql(conn, "SELECT id FROM research_runs WHERE thread_id=? AND status IN ('queued','running')", (tid,)).fetchone():
                raise StoreError(409, "This conversation already has research in progress")
            latest = self.sql(conn, "SELECT * FROM research_runs WHERE thread_id=? ORDER BY created_at DESC LIMIT 1", (tid,)).fetchone()
            if not body.retry_of and bool(latest and latest["status"] == "needs_clarification") != body.resume:
                raise StoreError(409, "Conversation state changed. Reload before sending")
            run_id, stamp = str(uuid.uuid4()), now()
            if body.retry_of:
                if (not latest or latest["id"] != str(body.retry_of) or latest["status"] not in ("failed", "cancelled")
                        or latest["prompt"] != body.message or bool(latest["resume"]) != body.resume):
                    raise StoreError(409, "Only the latest failed or stopped request can be retried")
                message_id = latest["message_id"]
                self.sql(conn, "UPDATE messages SET status='sent' WHERE id=?", (message_id,))
            else:
                message_id = str(uuid.uuid4())
                self.sql(conn, "INSERT INTO messages(id,thread_id,role,content,status,created_at) VALUES(?,?,?,?,?,?)",
                         (message_id, tid, "user", body.message, "sent", stamp))
            self.sql(conn,
                "INSERT INTO research_runs(id,thread_id,user_id,request_id,message_id,prompt,resume,retry_of,status,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (run_id, tid, user, request_id, message_id, body.message, int(body.resume), str(body.retry_of) if body.retry_of else None, "queued", stamp, stamp))
            self.sql(conn, "UPDATE threads SET updated_at=? WHERE thread_id=?", (stamp, tid))
            return self.decode_run(self.sql(conn, "SELECT * FROM research_runs WHERE id=?", (run_id,)).fetchone()), True

    @staticmethod
    def decode_run(row):
        data = dict(row)
        for key in ("events", "sources", "metrics"):
            data[key] = json.loads(data[key])
        return data

    def run(self, user, rid):
        with self.connection() as conn:
            row = self.sql(conn, "SELECT * FROM research_runs WHERE id=? AND user_id=?", (rid, user)).fetchone()
            if not row:
                raise StoreError(404, "Research run not found")
            return self.decode_run(row)

    def write_progress(self, user, rid, events, draft, sources):
        with self.connection() as conn:
            self.sql(conn, "UPDATE research_runs SET status='running',events=?,draft=?,sources=?,updated_at=? "
                     "WHERE id=? AND user_id=? AND status IN ('queued','running')",
                     (json.dumps(events), draft, json.dumps(sources), now(), rid, user))

    def finish(self, user, rid, status, answer="", error=None, sources=None, metrics=None):
        with self.connection() as conn:
            row = self.sql(conn, "SELECT * FROM research_runs WHERE id=? AND user_id=?", (rid, user)).fetchone()
            if not row or row["status"] not in ("running", "queued"):
                return
            stamp = now()
            if row["cancel_requested"]:
                status, answer, error = "cancelled", "", "Research stopped. You can retry this request."
            if answer:
                self.sql(conn, "INSERT INTO messages(id,thread_id,run_id,role,content,status,sources,created_at) VALUES(?,?,?,?,?,?,?,?)",
                    (str(uuid.uuid4()), row["thread_id"], rid, "assistant", answer, "sent", json.dumps(sources or []), stamp))
            if status in ("failed", "cancelled"):
                self.sql(conn, "UPDATE messages SET status=? WHERE id=?", (status, row["message_id"]))
            self.sql(conn, "UPDATE research_runs SET status=?,error=?,sources=?,metrics=?,updated_at=? WHERE id=?",
                     (status, error, json.dumps(sources or []), json.dumps(metrics or {}), stamp, rid))
            self.sql(conn, "UPDATE threads SET updated_at=? WHERE thread_id=?", (stamp, row["thread_id"]))

    def cancel(self, user, rid):
        with self.connection() as conn:
            if not self.sql(conn, "SELECT id FROM research_runs WHERE id=? AND user_id=?", (rid, user)).fetchone():
                raise StoreError(404, "Research run not found")
            self.sql(conn, "UPDATE research_runs SET cancel_requested=1 WHERE id=? AND status IN ('queued','running')", (rid,))

    def recover(self):
        with self.connection() as conn:
            self.sql(conn, "UPDATE messages SET status='failed' WHERE id IN "
                     "(SELECT message_id FROM research_runs WHERE status IN ('queued','running'))")
            self.sql(conn, "UPDATE research_runs SET status='failed',error=?,updated_at=? WHERE status IN ('queued','running')",
                     ("The server restarted during research. Retry to continue from the saved checkpoint.", now()))


SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS threads (
 thread_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, title TEXT NOT NULL,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL, archived_at TEXT
);
CREATE INDEX IF NOT EXISTS threads_user_updated ON threads(user_id,updated_at DESC);
CREATE TABLE IF NOT EXISTS research_runs (
 id TEXT PRIMARY KEY, thread_id TEXT NOT NULL REFERENCES threads(thread_id) ON DELETE CASCADE,
 user_id TEXT NOT NULL, request_id TEXT NOT NULL, message_id TEXT NOT NULL, prompt TEXT NOT NULL,
 resume INTEGER NOT NULL DEFAULT 0, retry_of TEXT, status TEXT NOT NULL,
 events TEXT NOT NULL DEFAULT '[]', draft TEXT NOT NULL DEFAULT '', sources TEXT NOT NULL DEFAULT '[]',
 metrics TEXT NOT NULL DEFAULT '{}', error TEXT, cancel_requested INTEGER NOT NULL DEFAULT 0,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL, UNIQUE(user_id,request_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_run ON research_runs(thread_id) WHERE status IN ('queued','running');
CREATE TABLE IF NOT EXISTS messages (
 id TEXT PRIMARY KEY, thread_id TEXT NOT NULL REFERENCES threads(thread_id) ON DELETE CASCADE,
 run_id TEXT REFERENCES research_runs(id) ON DELETE CASCADE, role TEXT NOT NULL,
 content TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'sent', sources TEXT NOT NULL DEFAULT '[]', created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS messages_thread_created ON messages(thread_id,created_at);
"""
