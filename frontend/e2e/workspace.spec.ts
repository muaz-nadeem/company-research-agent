import { expect, test } from '@playwright/test';
import { mkdirSync } from 'node:fs';

test.beforeEach(async ({ page }) => {
  await page.route('**/api/health', route => route.fulfill({ json: { status: 'ready', research_available: true } }));
});

test('recruiter walkthrough: welcome, sample, evidence and export', async ({ page }) => {
  mkdirSync('../docs/screenshots', { recursive: true });
  await page.goto('/');
  await expect(page.getByRole('heading', { name: /Good research starts/ })).toBeVisible();
  await page.screenshot({ path: '../docs/screenshots/workspace.png', fullPage: true });
  await page.getByRole('button', { name: /Just looking/ }).click();
  await expect(page.getByRole('heading', { name: /Scale, with/ })).toBeVisible();
  await page.getByRole('button', { name: /View source 1/ }).first().click();
  await expect(page.getByLabel('Evidence panel').getByRole('link', { name: /Stripe/ })).toBeVisible();
  await page.screenshot({ path: '../docs/screenshots/evidence.png', fullPage: true });
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Export response as Markdown' }).click();
  expect((await download).suggestedFilename()).toBe('research-brief.md');
  await page.reload();
  await expect(page.getByRole('heading', { name: /Scale, with/ })).toBeVisible();
});

test('mobile navigation, sample and accessible sign-in dialog', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await expect(page.getByRole('heading', { name: /Good research starts/ })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: '../docs/screenshots/mobile.png', fullPage: true });
  await page.getByRole('button', { name: 'Open navigation' }).click();
  await page.getByRole('button', { name: /A brief worth opening/ }).click();
  await expect(page.getByRole('heading', { name: /Scale, with/ })).toBeVisible();
  await page.getByRole('button', { name: 'Close evidence panel' }).click();
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'Sign in' })).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).toHaveCount(0);
});

test('saved conversations restore on refresh and clear on sign-out', async ({ page }) => {
  const id = '00000000-0000-4000-8000-000000000001';
  const thread = { thread_id: id, title: 'Saved Stripe research', created_at: '2026-10-10', updated_at: '2026-10-10', archived_at: null };
  await page.addInitScript(() => {
    if (!sessionStorage.getItem('signed-out')) localStorage.setItem('sb-synapse-test-auth-token', JSON.stringify({
      access_token: 'test-token', refresh_token: 'test-refresh', expires_at: 4102444800, token_type: 'bearer',
      user: { id: 'test-user', email: 'researcher@example.com', aud: 'authenticated', app_metadata: {}, user_metadata: {}, created_at: '2026-10-10' },
    }));
  });
  await page.route('https://synapse-test.supabase.co/**', route => route.fulfill({ status: 204 }));
  await page.route('**/api/threads?**', route => route.fulfill({ json: [thread] }));
  await page.route(`**/api/threads/${id}/messages`, route => route.fulfill({ json: { thread, messages: [{ id: 'saved', thread_id: id, role: 'assistant', content: 'A private saved report.', status: 'sent', sources: [], created_at: '2026-10-10' }], runs: [], awaiting_clarification: false } }));
  await page.goto(`/?chat=${id}`);
  await expect(page.getByText('A private saved report.', { exact: true })).toBeVisible();
  await page.getByRole('textbox', { name: 'Research question' }).fill('Draft follow-up');
  await page.reload();
  await expect(page.getByText('A private saved report.', { exact: true })).toBeVisible();
  await expect(page.getByRole('textbox', { name: 'Research question' })).toHaveValue('Draft follow-up');
  await page.evaluate(() => sessionStorage.setItem('signed-out', '1'));
  await page.getByRole('button', { name: 'Sign out', exact: true }).click();
  await expect(page.getByText('A private saved report.', { exact: true })).toHaveCount(0);
  await expect(page.getByRole('heading', { name: /Good research starts/ })).toBeVisible();
});

test('a submitted background run becomes a saved report and survives refresh', async ({ page }) => {
  const runId = '00000000-0000-4000-8000-000000000099';
  let thread: Record<string, unknown> | null = null;
  let run: Record<string, unknown> | null = null;
  let prompt = '';
  await page.addInitScript(() => localStorage.setItem('sb-synapse-test-auth-token', JSON.stringify({
    access_token: 'test-token', refresh_token: 'refresh', expires_at: 4102444800, token_type: 'bearer',
    user: { id: 'runner-user', email: 'runner@example.com', aud: 'authenticated', app_metadata: {}, user_metadata: {}, created_at: '2026-10-10' },
  })));
  await page.route('https://synapse-test.supabase.co/**', route => route.fulfill({ status: 204 }));
  await page.route('**/api/threads?**', route => route.fulfill({ json: thread ? [thread] : [] }));
  await page.route('**/api/chat', async route => {
    const body = route.request().postDataJSON(); prompt = body.message;
    thread = { thread_id: body.thread_id, title: prompt, created_at: '2026-10-10', updated_at: '2026-10-10', archived_at: null };
    run = { id: runId, thread_id: body.thread_id, prompt, resume: false, status: 'queued', events: [], draft: '', sources: [], metrics: {}, cancel_requested: 0, created_at: '2026-10-10' };
    await route.fulfill({ status: 202, json: run });
  });
  await page.route('**/api/threads/*/messages', route => route.fulfill({ json: { thread, runs: [run], awaiting_clarification: false,
    messages: [{ id: 'question', thread_id: thread?.thread_id, role: 'user', content: prompt, sources: [], status: 'sent', created_at: '2026-10-10' },
      ...(run?.status === 'completed' ? [{ id: 'answer', thread_id: thread?.thread_id, role: 'assistant', content: 'A completed and saved brief.', sources: [], status: 'sent', created_at: '2026-10-10' }] : [])] } }));
  await page.route(`**/api/runs/${runId}`, route => route.fulfill({ json: run }));
  await page.route(`**/api/runs/${runId}/events`, async route => {
    run = { ...run, status: 'completed' };
    await route.fulfill({ contentType: 'text/event-stream', body: `data: ${JSON.stringify(run)}\n\n` });
  });
  await page.goto('/');
  await page.getByRole('textbox', { name: 'Research question' }).fill('Research Stripe');
  await page.getByRole('button', { name: 'Send research question' }).click();
  await expect(page.getByText('A completed and saved brief.', { exact: true })).toBeVisible();
  await expect(page).toHaveURL(/chat=/);
  await page.reload();
  await expect(page.getByText('A completed and saved brief.', { exact: true })).toBeVisible();
  await expect(page.getByRole('textbox', { name: 'Research question' })).toHaveValue('');
});
