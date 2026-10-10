# Verification record · 10 October 2026

## Automated checks

- Backend suite: 31 tests passed, including model JSON blocks and citation normalization.
- Frontend interaction suite: 5 passed. Covers stale thread loads, navigation during submit, idempotent retransmission, preserved drafts, and per-thread draft restoration.
- Playwright: 4 passed. Desktop sample/citation/export, mobile drawer/dialog, saved-chat refresh/sign-out, and send → run completion → persisted report → refresh. Cloud authentication and API responses are intercepted in these tests.
- Production TypeScript/Vite build: passed. Markdown/auth code is split into separate chunks; no oversized-chunk warning on the final build.
- Local API `/api/health`: ready, research available.
- Both local SQLite databases: `PRAGMA integrity_check` returned `ok` after the drive interruption.
- Offline evaluation harness: five fixture cases completed. These are not real quality measurements.

## Live checks and limits

Real Gemini/Tavily calls completed both a single-pass response and a four-call agent workflow for Stripe and Microsoft research. A longer evaluation exposed a transient provider ServerError, inconsistent citation formatting, and a JSON decoding failure. Citation normalization and JSON-mode output were added in response; retry checks are recorded in the evaluation output. Linear returned a clarification request rather than inventing private financials. No claim of superior answer accuracy is made.

The five-case evaluation is diagnostic, not a release gate that proves factual accuracy. Some generated reports still include tangential estimates or need source-by-source review. The application exposes citations and uncertainty; an LLM validator does not turn generated prose into independently verified facts.

Cloud PostgreSQL migration could not run: the configured Supabase connection returned `tenant/user not found`. The database credentials were not changed and no cloud migration was applied. Cross-device persistence, hosted authentication, and production PostgreSQL behavior remain unverified until the connection is repaired.

Docker CLI is present but its daemon is not running. The Dockerfile/Render definition are prepared; an image build and hosted deployment have not been verified. No hosting account was selected during implementation.

A temporary E: drive interruption caused a file-read failure during one build and a result-file write failure during evaluation. The drive recovered, the databases passed integrity checks, and the production build was rerun successfully. Evaluation writes now replace a temporary file atomically and support resuming completed cases.
