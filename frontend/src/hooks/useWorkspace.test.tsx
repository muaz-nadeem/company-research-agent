import { act, renderHook, waitFor, cleanup } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useWorkspace } from './useWorkspace';

const api = vi.hoisted(() => ({ request: vi.fn(), watchRun: vi.fn() }));
vi.mock('../api', async importOriginal => ({ ...await importOriginal<typeof import('../api')>(), ...api }));
const a = '00000000-0000-4000-8000-000000000001', b = '00000000-0000-4000-8000-000000000002';
const detail = (id: string, content = id) => ({ thread: { thread_id: id, title: content }, messages: [{ id, role: 'user', content, sources: [] }], runs: [], awaiting_clarification: false });
beforeEach(() => { history.replaceState({}, '', '/'); vi.resetAllMocks(); api.request.mockResolvedValue([]); });
afterEach(cleanup);

describe('conversation request isolation', () => {
  it('ignores a stale history response after selecting another thread', async () => {
    let resolveA: (value: unknown) => void = () => {};
    api.request.mockImplementation((path: string) => path.includes(`${a}/messages`) ? new Promise(resolve => { resolveA = resolve; }) : path.includes(`${b}/messages`) ? Promise.resolve(detail(b)) : Promise.resolve([]));
    const { result } = renderHook(() => useWorkspace('token'));
    act(() => result.current.navigate(a));
    act(() => result.current.navigate(b));
    await waitFor(() => expect(result.current.detail?.thread.thread_id).toBe(b));
    await act(async () => resolveA(detail(a)));
    expect(result.current.detail?.thread.thread_id).toBe(b);
  });

  it('does not attach a delayed submission to another conversation', async () => {
    let resolveSend: (value: unknown) => void = () => {};
    api.request.mockImplementation((path: string) => path === '/chat' ? new Promise(resolve => { resolveSend = resolve; }) : path.includes('/messages') ? Promise.resolve(detail(path.includes(a) ? a : b)) : Promise.resolve([]));
    const { result } = renderHook(() => useWorkspace('token'));
    act(() => result.current.navigate(a));
    await waitFor(() => expect(result.current.detail?.thread.thread_id).toBe(a));
    let sent: Promise<boolean>;
    act(() => { sent = result.current.send('Research A'); });
    act(() => result.current.navigate(b));
    await waitFor(() => expect(result.current.detail?.thread.thread_id).toBe(b));
    await act(async () => { resolveSend({ id: 'run-a', thread_id: a, status: 'queued' }); await sent; });
    expect(result.current.threadId).toBe(b);
    expect(result.current.detail?.thread.thread_id).toBe(b);
  });

  it('reuses the request ID when an acknowledgement is lost', async () => {
    api.request.mockImplementation((path: string) => path === '/chat' ? Promise.reject(new Error('Network lost')) : Promise.resolve([]));
    const { result } = renderHook(() => useWorkspace('token'));
    await act(async () => { await result.current.send('Research Stripe'); });
    await act(async () => { await result.current.send('Research Stripe'); });
    const sent = api.request.mock.calls.filter(call => call[0] === '/chat').map(call => JSON.parse(call[2].body));
    expect(sent[0].request_id).toBe(sent[1].request_id);
    expect(sent[0].thread_id).toBe(sent[1].thread_id);
  });
});
