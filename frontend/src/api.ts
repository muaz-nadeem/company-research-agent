export type Source = { id: string; title: string; url: string; excerpt: string; retrieved_at: string; published_at?: string | null };
export type Message = { id: string; thread_id: string; run_id?: string; role: 'user' | 'assistant'; content: string; status: string; sources: Source[]; created_at: string };
export type Thread = { thread_id: string; title: string; created_at: string; updated_at: string; archived_at: string | null };
export type RunEvent = { type: string; stage?: string; status?: string; message?: string; result?: string; duration_ms?: number; at: string };
export type Run = { id: string; thread_id: string; prompt: string; resume: boolean; status: string; events: RunEvent[]; draft: string; error: string | null; sources: Source[]; cancel_requested: number; metrics: Record<string, number | null>; created_at: string };
export type Detail = { thread: Thread; messages: Message[]; runs: Run[]; awaiting_clarification: boolean };
export type Submission = { message: string; thread_id: string; request_id: string; resume: boolean; retry_of?: string };
export const activeRun = (run?: Run | null) => !!run && ['queued', 'running'].includes(run.status);

export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message); }
}

export async function request<T>(path: string, token: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api${path}`, { ...options, headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}`, ...options.headers } });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new ApiError(typeof body.detail === 'string' ? body.detail : `Request failed (${response.status})`, response.status);
  }
  return response.json();
}

export async function watchRun(id: string, token: string, signal: AbortSignal, onRun: (run: Run) => void) {
  const response = await fetch(`/api/runs/${id}/events`, { headers: { Authorization: `Bearer ${token}` }, signal });
  if (!response.ok || !response.body) throw new Error('Connection interrupted');
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n');
      const frames = buffer.split('\n\n');
      buffer = frames.pop() ?? '';
      for (const frame of frames) {
        const data = frame.split('\n').filter(line => line.startsWith('data:')).map(line => line.slice(5).trim()).join('\n');
        if (data) onRun(JSON.parse(data));
      }
    }
  } finally { reader.releaseLock(); }
}
