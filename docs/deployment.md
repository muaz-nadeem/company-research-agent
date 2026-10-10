# Deploy Synapse

No hosted project has been provisioned by this change. The included Render definition selects a paid starter instance; review pricing in your account before creating it. Other Docker-capable hosts work too.

1. Restore a working Supabase database connection string. Use the connection string from the actual project's dashboard; pooler region, tenant username and password must match. Never use a service-role API key as the database password.
2. Run the additive migration and, if needed, legacy import while the old API is stopped. Preserve both old thread metadata and the checkpoint database when backing up.
3. Build the image with `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` as build arguments. These are public client values. Keep `SUPABASE_SERVICE_KEY`, `DATABASE_URL`, `GOOGLE_API_KEY`, and `TAVILY_API_KEY` in runtime secrets only.
4. Run exactly one API process and instance with `APP_ENV=production`. Use stop-before-start deployment; the owner lock intentionally prevents concurrent API owners. The container applies the idempotent application migration at startup, then initializes checkpoints and starts the API.
5. Set `CORS_ORIGINS` to the exact frontend origin, and configure the same Site URL plus password-reset redirect URL in Supabase Auth. Use HTTPS.
6. Verify `/api/health`, sign in with two separate test accounts, and check ownership isolation, refresh, follow-up, clarification, delete, restart, and cancellation. Use a small research request to verify provider access.

```sh
docker build \
  --build-arg VITE_SUPABASE_URL="$VITE_SUPABASE_URL" \
  --build-arg VITE_SUPABASE_ANON_KEY="$VITE_SUPABASE_ANON_KEY" \
  -t synapse-research .
docker run --env-file .env -e APP_ENV=production -p 8000:8000 synapse-research
```

The repository's original database connection returned `tenant/user not found` during verification. No cloud migration was applied. Docker is installed on the development machine, but its daemon was not running, so image build/runtime verification remains outstanding.
