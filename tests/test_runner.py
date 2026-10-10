from threading import Event
from uuid import uuid4
from backend.runner import RunManager
from backend.schemas import ChatRequest
from backend.store import Store


def test_worker_survives_client_departure_and_commits_output(tmp_path):
    store = Store(f'sqlite:///{tmp_path / "app.db"}')
    store.initialize()
    run, _ = store.begin_run('alice', ChatRequest(message='Research Stripe', request_id=uuid4()))
    entered, release = Event(), Event()
    def execute(run, progress, cancelled):
        progress({'type': 'stage', 'stage': 'research', 'status': 'running'})
        entered.set()
        assert release.wait(5)
        progress({'type': 'delta', 'text': 'Saved output'})
        return {'status': 'completed', 'answer': 'Saved output', 'sources': [], 'metrics': {'duration_ms': 10}}
    manager = RunManager(store, execute)
    manager.submit(run)
    assert entered.wait(5)
    # A separate store connection represents reconnecting from a different client.
    assert Store(store.url).run('alice', run['id'])['status'] == 'running'
    release.set()
    manager.close()
    assert store.detail('alice', run['thread_id'])['messages'][-1]['content'] == 'Saved output'


def test_worker_failure_keeps_question_and_marks_retryable(tmp_path):
    store = Store(f'sqlite:///{tmp_path / "app.db"}')
    store.initialize()
    run, _ = store.begin_run('alice', ChatRequest(message='Research Stripe', request_id=uuid4()))
    def fail(*args):
        raise RuntimeError('Provider unavailable')
    manager = RunManager(store, fail)
    manager.submit(run)
    manager.close()
    detail = store.detail('alice', run['thread_id'])
    assert detail['runs'][0]['status'] == 'failed'
    assert detail['messages'][0]['content'] == 'Research Stripe'
