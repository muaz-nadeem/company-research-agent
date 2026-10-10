import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import Composer from './Composer';
afterEach(() => { cleanup(); sessionStorage.clear(); });
const props = { storageKey: 'draft:user:a', busy: false, sending: false, stopping: false, clarification: false, cancel: vi.fn(), suggestion: null };
it('keeps a draft when sending fails', async () => {
  render(<Composer {...props} send={async () => false} />);
  fireEvent.change(screen.getByRole('textbox'), { target: { value: 'My unsent question' } });
  fireEvent.click(screen.getByRole('button', { name: 'Send research question' }));
  await waitFor(() => expect(screen.getByRole('textbox')).toHaveValue('My unsent question'));
  expect(sessionStorage.getItem(props.storageKey)).toBe('My unsent question');
});
it('restores the right draft when conversations change', () => {
  sessionStorage.setItem('draft:user:b', 'Question B');
  const { rerender } = render(<Composer {...props} send={async () => true} />);
  fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Question A' } });
  rerender(<Composer {...props} storageKey="draft:user:b" send={async () => true} />);
  expect(screen.getByRole('textbox')).toHaveValue('Question B');
  expect(sessionStorage.getItem('draft:user:a')).toBe('Question A');
});
