import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import UUID

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from backend.auth import get_current_user
from backend.runner import RunManager
from backend.schemas import ChatRequest, ThreadUpdate
from backend.store import Store, StoreError
from graph.builder import get_graph
from graph.service import missing_api_keys


def create_app(store=None, manager_factory=RunManager, checkpointer_factory=get_graph):
    @asynccontextmanager
    async def lifespan(app):
        app.state.store = store or Store()
        app.state.store.initialize()
        # Eager readiness check: a failed database never silently becomes memory storage.
        app.state.graph = checkpointer_factory()
        with app.state.store.owner_lock():
            app.state.store.recover()
            app.state.manager = manager_factory(app.state.store)
            try:
                yield
            finally:
                app.state.manager.close()
                checkpoint = getattr(app.state.graph, "checkpointer", None)
                conn = getattr(checkpoint, "conn", None)
                if conn:
                    conn.close()
                get_graph.cache_clear()

    app = FastAPI(title="Synapse Research", version="3.0.0", lifespan=lifespan)
    app.add_middleware(CORSMiddleware,
        allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(","),
        allow_credentials=True, allow_methods=["GET", "POST", "PATCH", "DELETE"], allow_headers=["Authorization", "Content-Type"])

    @app.exception_handler(StoreError)
    async def store_error(request, exc):
        return JSONResponse(status_code=exc.status, content={"detail": str(exc)})

    @app.exception_handler(Exception)
    async def unexpected_error(request, exc):
        logging.getLogger(__name__).exception("API operation failed", exc_info=exc)
        return JSONResponse(status_code=503, content={"detail": "The service is temporarily unavailable. Your saved data has not been cleared."})

    @app.get("/api/health")
    def health():
        with app.state.store.connection() as conn:
            app.state.store.sql(conn, "SELECT 1")
        return {"status": "ready" if not missing_api_keys() else "degraded", "research_available": not missing_api_keys()}

    @app.get("/api/threads")
    def threads(user=Depends(get_current_user), archived: bool = False, q: str = Query("", max_length=200),
                limit: int = Query(100, ge=1, le=100), offset: int = Query(0, ge=0)):
        return app.state.store.threads(user["user_id"], archived, q, limit, offset)

    @app.get("/api/threads/{thread_id}/messages")
    def detail(thread_id: UUID, user=Depends(get_current_user)):
        return app.state.store.detail(user["user_id"], str(thread_id))

    @app.patch("/api/threads/{thread_id}")
    def update(thread_id: UUID, body: ThreadUpdate, user=Depends(get_current_user)):
        app.state.store.update_thread(user["user_id"], str(thread_id), body.title, body.archived)
        return {"ok": True}

    @app.delete("/api/threads/{thread_id}")
    def delete(thread_id: UUID, user=Depends(get_current_user)):
        app.state.store.delete_thread(user["user_id"], str(thread_id), app.state.graph.checkpointer.delete_thread)
        return {"ok": True}

    @app.post("/api/chat", status_code=202)
    def chat(body: ChatRequest, user=Depends(get_current_user)):
        if missing_api_keys():
            raise StoreError(503, "Research is not configured yet. You can still explore the sample brief.")
        run, created = app.state.store.begin_run(user["user_id"], body)
        if created:
            app.state.manager.submit(run)
        return run

    @app.get("/api/runs/{run_id}")
    def run(run_id: UUID, user=Depends(get_current_user)):
        return app.state.store.run(user["user_id"], str(run_id))

    @app.post("/api/runs/{run_id}/cancel")
    def cancel(run_id: UUID, user=Depends(get_current_user)):
        app.state.store.cancel(user["user_id"], str(run_id))
        return {"ok": True}

    @app.get("/api/runs/{run_id}/events")
    async def events(run_id: UUID, request: Request, user=Depends(get_current_user)):
        # Verify access before sending streaming headers. Send durable snapshots so
        # reconnection does not need to reconstruct missed token events.
        await run_in_threadpool(app.state.store.run, user["user_id"], str(run_id))

        async def stream():
            previous = None
            heartbeat = 0
            while not await request.is_disconnected():
                item = await run_in_threadpool(app.state.store.run, user["user_id"], str(run_id))
                payload = json.dumps(jsonable_encoder(item))
                if payload != previous:
                    yield f"data: {payload}\n\n"
                    previous = payload
                heartbeat += 1
                if heartbeat % 30 == 0:
                    yield ": heartbeat\n\n"
                if item["status"] not in ("queued", "running"):
                    return
                await asyncio.sleep(0.5)
        return StreamingResponse(stream(), media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
    if dist.exists():
        app.mount("/", StaticFiles(directory=dist, html=True), name="frontend")
    return app


app = create_app()
