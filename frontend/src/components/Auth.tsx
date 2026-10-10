import { FormEvent, useState } from 'react';
import { ArrowRight, X } from 'lucide-react';
import { supabase } from '../supabase';

export default function Auth({ close }: { close: () => void }) {
  const [mode, setMode] = useState<'signin' | 'signup' | 'reset'>('signin');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!supabase) return;
    setLoading(true); setError(''); setSuccess('');
    try {
      const result = mode === 'signin' ? await supabase.auth.signInWithPassword({ email, password })
        : mode === 'signup' ? await supabase.auth.signUp({ email, password })
        : await supabase.auth.resetPasswordForEmail(email, { redirectTo: location.origin + '/?reset=1' });
      if (result.error) throw result.error;
      if (mode === 'signup') setSuccess('Check your email to confirm your account.');
      if (mode === 'reset') setSuccess('If this account exists, a password reset link is on its way.');
      if (mode === 'signin') close();
    } catch (e) { setError((e as Error).message); }
    finally { setLoading(false); }
  };
  return <div className="auth-content">
    <button className="icon-button modal-close" onClick={close} aria-label="Close sign in"><X size={18} /></button>
    <div className="brand-mark">s<span>·</span></div>
    <p className="eyebrow">YOUR RESEARCH, REMEMBERED</p>
    <h2>{mode === 'signup' ? 'Make room for better questions.' : mode === 'reset' ? 'Let’s get you back in.' : 'Pick up where you left off.'}</h2>
    <p className="muted">Save briefs, follow the evidence, and build on every conversation.</p>
    {!supabase ? <p className="notice">Live accounts are not configured in this build. The sample brief is available without an account.</p> :
      <form onSubmit={submit} className="auth-form">
        <label>Email<input autoFocus type="email" autoComplete="email" required value={email} onChange={e => setEmail(e.target.value)} placeholder="you@example.com" /></label>
        {mode !== 'reset' && <label>Password<input type="password" autoComplete={mode === 'signin' ? 'current-password' : 'new-password'} minLength={8} required value={password} onChange={e => setPassword(e.target.value)} /></label>}
        {error && <p role="alert" className="error-text">{error}</p>}
        {success && <p role="status" className="notice">{success}</p>}
        <button className="button primary" disabled={loading}>{loading ? 'One moment…' : mode === 'signin' ? 'Sign in' : mode === 'signup' ? 'Create account' : 'Send reset link'}<ArrowRight size={16} /></button>
        <button type="button" className="text-button" onClick={() => { setMode(mode === 'signin' ? 'signup' : 'signin'); setError(''); setSuccess(''); }}>{mode === 'signin' ? 'New here? Create an account' : 'Already have an account? Sign in'}</button>
        {mode === 'signin' && <button type="button" className="text-button" onClick={() => setMode('reset')}>Forgot password?</button>}
      </form>}
  </div>;
}
