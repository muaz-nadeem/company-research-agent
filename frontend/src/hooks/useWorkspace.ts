import { useCallback, useEffect, useRef, useState } from 'react';
import { activeRun, ApiError, Detail, request, Run, Submission, Thread, watchRun } from '../api';

function initialThread() { return new URLSearchParams(location.search).get('chat'); }

export function useWorkspace(token: string) {
  const [threadId, setThreadId] = useState<string | null>(initialThread);
  const [threads, setThreads] = useState<Thread[]>([]);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [run, setRun] = useState<Run | null>(null);
  const [search, setSearch] = useState('');
  const [archived, setArchived] = useState(false);
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [reconnecting, setReconnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const generation = useRef(0);
  const listGeneration = useRef(0);
  const mounted = useRef(true);
  const pending = useRef<Submission | null>(null);
  const selected = useRef(threadId);
  selected.current = threadId;
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);

  const refresh = useCallback(async () => {
    if (!token) return;
    const version = ++listGeneration.current;
    const list = await request<Thread[]>(`/threads?archived=${archived}&q=${encodeURIComponent(search)}`, token);
    if (mounted.current && version === listGeneration.current) setThreads(list);
  }, [archived, search, token]);
  useEffect(() => { const timeout = setTimeout(() => { refresh().catch(e => setError(e.message)); }, 200); return () => clearTimeout(timeout); }, [refresh]);

  const navigate = useCallback((id: string | null) => {
    generation.current++;
    selected.current = id;
    setThreadId(id); setDetail(null); setRun(null); setError(null);
    const url = new URL(location.href);
    if (id) url.searchParams.set('chat', id); else url.searchParams.delete('chat');
    url.searchParams.delete('demo');
    history.pushState({}, '', url);
  }, []);
  useEffect(() => {
    const back = () => { generation.current++; setThreadId(initialThread()); setDetail(null); setRun(null); };
    addEventListener('popstate', back);
    return () => removeEventListener('popstate', back);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    setDetail(null); setRun(null); setReconnecting(false);
    if (!threadId || !token) { setLoading(false); return; }
    setLoading(true);
    request<Detail>(`/threads/${threadId}/messages`, token, { signal: controller.signal })
      .then(data => { if (!controller.signal.aborted) { setDetail(data); setRun(data.runs[0] ?? null); } })
      .catch(e => { if (!controller.signal.aborted) setError(e.message); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [threadId, token]);

  const runningId = activeRun(run) ? run!.id : null;
  useEffect(() => {
    if (!runningId || !threadId) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    const receive = (next: Run) => {
      if (controller.signal.aborted) return;
      setReconnecting(false);
      if (!activeRun(next)) {
        request<Detail>(`/threads/${threadId}/messages`, token, { signal: controller.signal })
          .then(data => { if (!controller.signal.aborted) { setDetail(data); setRun(next); } })
          .catch(e => { if (!controller.signal.aborted) { setError(e.message); setReconnecting(true); timer = setTimeout(connect, 2500); } });
        refresh().catch(() => {});
      } else setRun(next);
    };
    const connect = async () => {
      try {
        await watchRun(runningId, token, controller.signal, receive);
        // A clean close can also be an upstream timeout; recover the latest snapshot.
        if (!controller.signal.aborted) {
          const latest = await request<Run>(`/runs/${runningId}`, token, { signal: controller.signal });
          receive(latest);
          if (activeRun(latest)) timer = setTimeout(connect, 1500);
        }
      } catch {
        if (!controller.signal.aborted) { setReconnecting(true); timer = setTimeout(connect, 2500); }
      }
    };
    void connect();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [runningId, threadId, token, refresh]);

  const send = async (message: string, retry?: Run) => {
    if (sending || activeRun(run)) return false;
    const origin = selected.current;
    const id = origin || pending.current?.thread_id || crypto.randomUUID();
    const resume = retry ? !!retry.resume : !!detail?.awaiting_clarification;
    let submission = pending.current;
    if (!submission || submission.message !== message || submission.thread_id !== id || submission.retry_of !== retry?.id) {
      submission = { message, thread_id: id, request_id: crypto.randomUUID(), resume, ...(retry ? { retry_of: retry.id } : {}) };
    }
    pending.current = submission;
    const version = generation.current;
    setSending(true); setError(null);
    try {
      const next = await request<Run>('/chat', token, { method: 'POST', body: JSON.stringify(submission) });
      pending.current = null;
      if (!mounted.current) return false;
      if (version === generation.current) {
        if (!origin) navigate(id);
        const data = await request<Detail>(`/threads/${id}/messages`, token);
        if (mounted.current && selected.current === id) { setDetail(data); setRun(data.runs[0] ?? next); }
      }
      await refresh();
      return true;
    } catch (e) {
      if (e instanceof ApiError && e.status >= 400 && e.status < 500) pending.current = null;
      if (mounted.current && version === generation.current) setError(e instanceof Error ? e.message : 'Could not send. Your draft is preserved.');
      return false;
    } finally { if (mounted.current) setSending(false); }
  };

  const update = async (id: string, changes: { title?: string; archived?: boolean }) => {
    try {
      await request(`/threads/${id}`, token, { method: 'PATCH', body: JSON.stringify(changes) });
      if (selected.current === id && changes.archived !== undefined) navigate(null);
      if (selected.current === id && changes.title) setDetail(prev => prev ? { ...prev, thread: { ...prev.thread, title: changes.title! } } : prev);
      await refresh();
    } catch (e) { setError((e as Error).message); }
  };
  const remove = async (id: string) => {
    try {
      await request(`/threads/${id}`, token, { method: 'DELETE' });
      if (selected.current === id) navigate(null);
      await refresh();
    } catch (e) { setError((e as Error).message); }
  };
  const cancel = async () => {
    if (!run) return;
    try { await request(`/runs/${run.id}/cancel`, token, { method: 'POST' }); setRun({ ...run, cancel_requested: 1 }); }
    catch (e) { setError((e as Error).message); }
  };
  return { threadId, threads, detail, run, search, setSearch, archived, setArchived, loading, sending, reconnecting,
    error, setError, navigate, send, update, remove, cancel, refresh };
}
