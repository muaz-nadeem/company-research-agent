-- Additive migration. Existing thread records and checkpoints are preserved.
BEGIN;
CREATE TABLE IF NOT EXISTS public.threads (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), thread_id text UNIQUE NOT NULL,
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  title text NOT NULL DEFAULT 'New research', created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE public.threads ADD COLUMN IF NOT EXISTS archived_at timestamptz;
CREATE INDEX IF NOT EXISTS threads_user_updated ON public.threads(user_id, updated_at DESC);
CREATE TABLE IF NOT EXISTS public.research_runs (
  id text PRIMARY KEY, thread_id text NOT NULL REFERENCES public.threads(thread_id) ON DELETE CASCADE,
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE, request_id text NOT NULL,
  message_id text NOT NULL, prompt text NOT NULL, resume integer NOT NULL DEFAULT 0, retry_of text,
  status text NOT NULL CHECK (status IN ('queued','running','completed','needs_clarification','failed','cancelled')),
  events text NOT NULL DEFAULT '[]', draft text NOT NULL DEFAULT '', sources text NOT NULL DEFAULT '[]',
  metrics text NOT NULL DEFAULT '{}', error text, cancel_requested integer NOT NULL DEFAULT 0,
  created_at text NOT NULL, updated_at text NOT NULL, UNIQUE(user_id,request_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_run ON public.research_runs(thread_id) WHERE status IN ('queued','running');
CREATE TABLE IF NOT EXISTS public.messages (
  id text PRIMARY KEY, thread_id text NOT NULL REFERENCES public.threads(thread_id) ON DELETE CASCADE,
  run_id text REFERENCES public.research_runs(id) ON DELETE CASCADE,
  role text NOT NULL CHECK (role IN ('user','assistant')), content text NOT NULL,
  status text NOT NULL DEFAULT 'sent', sources text NOT NULL DEFAULT '[]', created_at text NOT NULL
);
CREATE INDEX IF NOT EXISTS messages_thread_created ON public.messages(thread_id,created_at);
ALTER TABLE public.threads ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.research_runs ENABLE ROW LEVEL SECURITY;
-- Access to application data goes through the API's ownership checks.
REVOKE ALL ON public.threads, public.messages, public.research_runs FROM anon, authenticated;
COMMIT;
