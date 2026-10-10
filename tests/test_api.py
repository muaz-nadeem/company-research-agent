from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient
from backend.auth import get_current_user
from backend.main import create_app
from backend.store import Store


class Manager:
    def __init__(self, store): self.submissions = []
    def submit(self, run): self.submissions.append(run)
    def close(self): pass


def test_authenticated_api_isolation_and_idempotency(tmp_path, monkeypatch):
    monkeypatch.setenv('GOOGLE_API_KEY', 'test')
    monkeypatch.setenv('TAVILY_API_KEY', 'test')
    store = Store(f'sqlite:///{tmp_path / "app.db"}')
    graph = SimpleNamespace(checkpointer=SimpleNamespace(delete_thread=lambda _: None))
    app = create_app(store, Manager, lambda: graph)
    current_user = {'user_id': 'alice'}
    app.dependency_overrides[get_current_user] = lambda: current_user
    with TestClient(app) as client:
        payload = {'message': 'Research Stripe', 'thread_id': str(uuid4()), 'request_id': str(uuid4())}
        created = client.post('/api/chat', json=payload)
        assert created.status_code == 202
        run = created.json()
        assert client.post('/api/chat', json=payload).json()['id'] == run['id']
        assert len(app.state.manager.submissions) == 1
        current_user['user_id'] = 'bob'
        assert client.get(f'/api/threads/{run["thread_id"]}/messages').status_code == 404
        assert client.get(f'/api/runs/{run["id"]}/events').status_code == 404
        assert client.post(f'/api/runs/{run["id"]}/cancel').status_code == 404
        assert client.post('/api/chat', json={**payload, 'request_id': str(uuid4())}).status_code == 404
        assert client.post('/api/chat', json={**payload, 'message': '  '}).status_code == 422
        assert client.get('/api/threads').json() == []


def test_missing_auth_rejected(tmp_path):
    app = create_app(Store(f'sqlite:///{tmp_path / "db"}'), Manager, lambda: SimpleNamespace())
    with TestClient(app) as client:
        assert client.get('/api/threads').status_code in (401, 403)
