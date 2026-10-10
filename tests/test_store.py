from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from backend.schemas import ChatRequest
from backend.store import Store, StoreError


@pytest.fixture
def store(tmp_path):
    value = Store(f'sqlite:///{tmp_path / "app.db"}')
    value.initialize()
    return value


def body(**changes):
    return ChatRequest(**{'message': 'Research Stripe', 'thread_id': uuid4(), 'request_id': uuid4(), **changes})


def test_messages_and_sources_survive_new_store_instance(store):
    run, _ = store.begin_run('alice', body())
    sources = [{'id': 'S1', 'url': 'https://example.com', 'excerpt': 'Evidence'}]
    store.finish('alice', run['id'], 'completed', answer='A saved report', sources=sources)
    reopened = Store(store.url)
    result = reopened.detail('alice', run['thread_id'])
    assert [m['content'] for m in result['messages']] == ['Research Stripe', 'A saved report']
    assert result['messages'][1]['sources'] == sources


def test_cross_user_submit_read_update_delete_and_cancel_are_rejected(store):
    run, _ = store.begin_run('alice', body())
    operations = [lambda: store.begin_run('bob', body(thread_id=run['thread_id'])),
        lambda: store.detail('bob', run['thread_id']), lambda: store.run('bob', run['id']),
        lambda: store.update_thread('bob', run['thread_id'], title='stolen'),
        lambda: store.delete_thread('bob', run['thread_id'], lambda _: None), lambda: store.cancel('bob', run['id'])]
    for operation in operations:
        with pytest.raises(StoreError) as error:
            operation()
        assert error.value.status == 404
    assert store.threads('bob') == []


def test_submission_idempotent_and_conflicting_reuse_rejected(store):
    request = body()
    run, created = store.begin_run('alice', request)
    again, created_again = store.begin_run('alice', request)
    assert created and not created_again and again['id'] == run['id']
    assert len(store.detail('alice', run['thread_id'])['messages']) == 1
    with pytest.raises(StoreError, match='different message'):
        store.begin_run('alice', body(thread_id=request.thread_id, request_id=request.request_id, message='Different'))


def test_concurrent_duplicate_submissions_create_one_run(store):
    request = body()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: store.begin_run('alice', request), range(2)))
    assert results[0][0]['id'] == results[1][0]['id']
    assert sum(created for _, created in results) == 1


def test_only_one_run_per_thread(store):
    run, _ = store.begin_run('alice', body())
    with pytest.raises(StoreError, match='in progress'):
        store.begin_run('alice', body(thread_id=run['thread_id']))


def test_restart_marks_inflight_run_failed_and_retry_reuses_message(store):
    run, _ = store.begin_run('alice', body())
    store.recover()
    assert store.run('alice', run['id'])['status'] == 'failed'
    retried, _ = store.begin_run('alice', body(thread_id=run['thread_id'], retry_of=run['id']))
    assert retried['message_id'] == run['message_id']
    assert len(store.detail('alice', run['thread_id'])['messages']) == 1


def test_clarification_persists_and_requires_resume(store):
    run, _ = store.begin_run('alice', body())
    store.finish('alice', run['id'], 'needs_clarification', answer='Which company?')
    assert Store(store.url).detail('alice', run['thread_id'])['awaiting_clarification']
    with pytest.raises(StoreError, match='state changed'):
        store.begin_run('alice', body(thread_id=run['thread_id']))
    resumed, _ = store.begin_run('alice', body(thread_id=run['thread_id'], resume=True, message='Stripe'))
    assert resumed['resume'] == 1


def test_cancel_keeps_lock_until_worker_acknowledges_and_discards_answer(store):
    run, _ = store.begin_run('alice', body())
    store.cancel('alice', run['id'])
    with pytest.raises(StoreError):
        store.begin_run('alice', body(thread_id=run['thread_id']))
    store.finish('alice', run['id'], 'completed', answer='Do not publish this')
    detail = store.detail('alice', run['thread_id'])
    assert detail['runs'][0]['status'] == 'cancelled'
    assert len(detail['messages']) == 1


def test_delete_cleans_related_records_and_invokes_checkpoint_deletion(store):
    run, _ = store.begin_run('alice', body())
    store.finish('alice', run['id'], 'completed', answer='Report')
    deleted = []
    store.delete_thread('alice', run['thread_id'], deleted.append)
    assert deleted == [run['thread_id']]
    assert store.threads('alice') == []
    with pytest.raises(StoreError):
        store.run('alice', run['id'])


def test_checkpoint_failure_preserves_conversation(store):
    run, _ = store.begin_run('alice', body())
    store.finish('alice', run['id'], 'completed', answer='Report')
    def fail(_):
        raise RuntimeError('storage unavailable')
    with pytest.raises(RuntimeError):
        store.delete_thread('alice', run['thread_id'], fail)
    assert len(store.detail('alice', run['thread_id'])['messages']) == 2


def test_search_rename_archive_restore(store):
    run, _ = store.begin_run('alice', body())
    store.finish('alice', run['id'], 'completed', answer='Distinctive evidence text')
    assert len(store.threads('alice', search='distinctive')) == 1
    store.update_thread('alice', run['thread_id'], title='Payments research', archived=True)
    assert not store.threads('alice')
    assert store.threads('alice', archived=True)[0]['title'] == 'Payments research'
    store.update_thread('alice', run['thread_id'], archived=False)
    assert len(store.threads('alice')) == 1


def test_no_memory_fallback_in_production(monkeypatch, tmp_path):
    monkeypatch.setenv('APP_ENV', 'production')
    with pytest.raises(RuntimeError, match='PostgreSQL'):
        Store(f'sqlite:///{tmp_path / "app.db"}')
