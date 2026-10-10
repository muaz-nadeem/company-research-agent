-- Run this in Supabase SQL Editor (Dashboard → SQL Editor → New query)
-- Creates the threads table used to list and persist conversations per user.
-- LangGraph checkpoint tables are created automatically by PostgresSaver.setup().

create table if not exists threads (
  id           uuid        primary key default gen_random_uuid(),
  thread_id    text        not null unique,
  user_id      uuid        not null references auth.users(id) on delete cascade,
  title        text        not null default 'New conversation',
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);

-- Index for fast per-user lookups ordered by recency
create index if not exists threads_user_updated
  on threads (user_id, updated_at desc);

-- Row-level security: users can only see and manage their own threads
alter table threads enable row level security;

create policy "users manage own threads"
  on threads for all
  using  (auth.uid() = user_id)
  with check (auth.uid() = user_id);
