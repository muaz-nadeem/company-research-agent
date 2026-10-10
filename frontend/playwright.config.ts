import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './e2e', timeout: 30000, fullyParallel: false, workers: 1,
  use: { baseURL: 'http://127.0.0.1:5180', headless: true, viewport: { width: 1440, height: 1000 }, screenshot: 'only-on-failure', video: 'on', trace: 'retain-on-failure' },
  webServer: { command: 'pnpm dev --host 127.0.0.1 --port 5180 --strictPort', url: 'http://127.0.0.1:5180', reuseExistingServer: false,
    env: { VITE_SUPABASE_URL: 'https://synapse-test.supabase.co', VITE_SUPABASE_ANON_KEY: 'public-test-key' } },
});
