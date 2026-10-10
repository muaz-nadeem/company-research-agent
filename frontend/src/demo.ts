import type { Detail } from './api';

const stamp = '2025-02-27T12:00:00Z';
export const demo: Detail = {
  thread: { thread_id: 'demo', title: 'Stripe · 2024 business brief', created_at: stamp, updated_at: stamp, archived_at: null },
  awaiting_clarification: false,
  runs: [],
  messages: [
    { id: 'demo-user', thread_id: 'demo', role: 'user', content: 'Give me a concise brief on Stripe’s 2024 payment volume and the questions I should investigate next.', status: 'sent', sources: [], created_at: stamp },
    { id: 'demo-report', thread_id: 'demo', role: 'assistant', status: 'sent', created_at: stamp,
      content: `## Scale, with a few important distinctions.\n\nStripe reported **$1.4 trillion in total payment volume in 2024**, a **38% increase** over the prior year. These figures describe payments processed, not Stripe’s own revenue. [1](#source-S1)\n\n### At a glance\n\n| Measure | Reported result | Period |\n| --- | --- | --- |\n| Total payment volume | $1.4 trillion | 2024 |\n| Year-over-year growth | 38% | 2024 vs. 2023 |\n\nBoth figures come from Stripe’s company announcement. [1](#source-S1)\n\n### Questions for the next research pass\n\n- How much growth came from existing customers versus new customers?\n- How did the product and geographic mix change?\n- What do independent sources say about competitive pressure?\n\n### Evidence limitations\n\nThis historical sample uses one company-published source. It does not establish current performance, independently corroborate the figures, or estimate Stripe’s revenue.`,
      sources: [{ id: 'S1', title: 'Stripe’s total payment volume reaches $1.4T', url: 'https://stripe.com/newsroom/news/stripe-2024-update', excerpt: 'Stripe reported $1.4 trillion in total payment volume for 2024 and 38% growth from the prior year. This is a paraphrase of the company announcement.', published_at: '2025-02-27', retrieved_at: '2026-10-10' }] },
  ],
};
