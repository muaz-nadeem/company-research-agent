import { FormEvent, ReactNode, useEffect, useRef, useState } from 'react';
import type { Session } from '@supabase/supabase-js';
import { Archive, ArrowRight, ArrowUpRight, BookOpen, Check, ChevronDown, FileText, Globe2, Menu, MoreHorizontal, PanelRight, Pencil, Plus, RotateCcw, Search, ShieldCheck, Sparkles, Trash2, X } from 'lucide-react';
import { activeRun, Source } from './api';
import { useAuth } from './hooks/useAuth';
import { useWorkspace } from './hooks/useWorkspace';
import { supabase } from './supabase';
import { demo } from './demo';
import Auth from './components/Auth';
import Sidebar from './components/Sidebar';
import Composer from './components/Composer';
import Report from './components/Report';
import EvidencePanel from './components/EvidencePanel';

function Modal({ children, close, label }: { children: ReactNode; close: () => void; label: string }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => { ref.current?.showModal(); }, []);
  return <dialog ref={ref} className="modal" aria-label={label} onCancel={close} onClick={e => { if (e.target === ref.current) close(); }}>{children}</dialog>;
}

function PasswordReset({ close }: { close: () => void }) {
  const [password, setPassword] = useState('');
  const [message, setMessage] = useState('');
  const [saving, setSaving] = useState(false);
  const save = async (e: FormEvent) => {
    e.preventDefault(); setSaving(true);
    const result = await supabase?.auth.updateUser({ password });
    setSaving(false);
    if (result?.error) setMessage(result.error.message); else close();
  };
  return <form className="modal-form" onSubmit={save}><h2>Choose a new password</h2><label>New password<input type="password" autoComplete="new-password" required minLength={8} value={password} onChange={e => setPassword(e.target.value)} /></label>{message && <p role="alert">{message}</p>}<button className="button primary" disabled={saving}>Save password</button></form>;
}

export default function App() {
  const { session, ready } = useAuth();
  if (!ready) return <div className="boot"><span className="brand-mark">s<span>·</span></span><p>Opening your workspace…</p></div>;
  // Account changes unmount every conversation hook and abort outstanding reads.
  return <Workspace key={session?.user.id || 'guest'} session={session} />;
}

function Workspace({ session }: { session: Session | null }) {
  const work = useWorkspace(session?.access_token || '');
  const [demoMode, setDemoMode] = useState(new URLSearchParams(location.search).has('demo'));
  const [authOpen, setAuthOpen] = useState(false);
  const [resetOpen, setResetOpen] = useState(!!session && new URLSearchParams(location.search).has('reset'));
  const [navOpen, setNavOpen] = useState(false);
  const [panelOpen, setPanelOpen] = useState(false);
  const [panelTab, setPanelTab] = useState<'sources' | 'activity'>('sources');
  const [selectedSource, setSelectedSource] = useState<Source | null>(null);
  const [sourceSet, setSourceSet] = useState<Source[] | null>(null);
  const [suggestion, setSuggestion] = useState<{ text: string; nonce: number } | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [dialog, setDialog] = useState<'rename' | 'delete' | null>(null);
  const [title, setTitle] = useState('');
  const [health, setHealth] = useState<string | null>(null);
  const scroll = useRef<HTMLDivElement>(null);
  const nearBottom = useRef(true);
  const detail = demoMode ? demo : work.detail;
  const run = demoMode ? null : work.run;
  const busy = activeRun(run);
  const messages = detail?.messages || [];
  const latestSources = [...messages].reverse().find(message => message.sources.length)?.sources || [];
  const sources = sourceSet || (busy && run?.sources.length ? run.sources : latestSources);
  const empty = messages.length === 0 && !work.loading && !busy;

  useEffect(() => {
    const controller = new AbortController();
    fetch('/api/health', { signal: controller.signal }).then(r => { if (!r.ok) throw new Error(); return r.json(); })
      .then(h => setHealth(h.research_available ? null : 'Live research is not configured. Explore the sample brief in the meantime.'))
      .catch(() => { if (!controller.signal.aborted) setHealth('Live research is temporarily unavailable. The sample brief is still here to explore.'); });
    return () => controller.abort();
  }, []);
  useEffect(() => { setSourceSet(null); setSelectedSource(null); setMenuOpen(false); nearBottom.current = true; }, [work.threadId, demoMode]);
  useEffect(() => { if (nearBottom.current && scroll.current) scroll.current.scrollTop = scroll.current.scrollHeight; }, [messages.length, run?.draft]);
  useEffect(() => {
    const keydown = (e: KeyboardEvent) => { if (e.key === 'Escape') { setNavOpen(false); setPanelOpen(false); setMenuOpen(false); } };
    const pop = () => setDemoMode(new URLSearchParams(location.search).has('demo'));
    addEventListener('keydown', keydown); addEventListener('popstate', pop);
    return () => { removeEventListener('keydown', keydown); removeEventListener('popstate', pop); };
  }, []);
  const newChat = () => { setDemoMode(false); work.navigate(null); setNavOpen(false); setSourceSet(null); };
  const sample = () => { setDemoMode(true); setNavOpen(false); setPanelOpen(true); setPanelTab('sources'); setSourceSet(null); const url = new URL(location.href); url.searchParams.delete('chat'); url.searchParams.set('demo', '1'); history.pushState({}, '', url); };
  const selectSource = (source: Source, set: Source[]) => { setSourceSet(set); setSelectedSource(source); setPanelOpen(true); setPanelTab('sources'); };
  const choose = (text: string) => { if (!session) setAuthOpen(true); else { newChat(); setSuggestion({ text, nonce: Date.now() }); } };
  const signOut = async () => {
    const userId = session?.user.id;
    const { error } = await supabase!.auth.signOut();
    if (error) { work.setError(error.message); return; }
    for (const key of Object.keys(sessionStorage)) if (key.startsWith(`draft:${userId}:`)) sessionStorage.removeItem(key);
    history.replaceState({}, '', '/');
  };
  const closeReset = () => { setResetOpen(false); const url = new URL(location.href); url.searchParams.delete('reset'); history.replaceState({}, '', url); };

  return <div className={`app ${navOpen ? 'nav-open' : ''} ${panelOpen ? 'panel-open' : ''}`}>
    {navOpen && <button className="nav-scrim" aria-label="Close navigation" onClick={() => setNavOpen(false)} />}
    <Sidebar threads={session ? work.threads : []} selected={demoMode ? null : work.threadId} search={work.search} setSearch={work.setSearch} archived={work.archived} setArchived={work.setArchived}
      select={id => { setDemoMode(false); work.navigate(id); setNavOpen(false); }} newChat={newChat} close={() => setNavOpen(false)} email={session?.user.email}
      signOut={() => void signOut()} signIn={() => setAuthOpen(true)} sample={sample} />
    <main className="main">
      <header className="workspace-header"><div className="header-location"><button className="icon-button mobile-only" aria-label="Open navigation" onClick={() => setNavOpen(true)}><Menu size={20} /></button><span className="breadcrumb">Workspace</span><span className="breadcrumb-slash">/</span><span className="header-title">{detail?.thread.title || 'New research'}</span></div>
        <div className="header-actions">{session && !demoMode && <span className="saved-status"><span />{work.sending ? 'Saving…' : busy ? 'Researching' : 'Private workspace'}</span>}
          <button className={`icon-button ${panelOpen ? 'selected' : ''}`} aria-label="Toggle evidence panel" onClick={() => setPanelOpen(!panelOpen)}><PanelRight size={18} /></button>
          {detail && !demoMode && <div className="menu-anchor"><button className="icon-button" aria-label="Conversation options" aria-expanded={menuOpen} onClick={() => setMenuOpen(!menuOpen)}><MoreHorizontal size={19} /></button>{menuOpen && <div className="dropdown"><button onClick={() => { setTitle(detail.thread.title); setDialog('rename'); setMenuOpen(false); }}><Pencil size={14} />Rename</button><button disabled={busy} onClick={() => { void work.update(detail.thread.thread_id, { archived: !detail.thread.archived_at }); setMenuOpen(false); }}><Archive size={14} />{detail.thread.archived_at ? 'Restore' : 'Archive'}</button><button className="danger" disabled={busy} onClick={() => { setDialog('delete'); setMenuOpen(false); }}><Trash2 size={14} />Delete</button></div>}</div>}
          {!session && <button className="button compact" onClick={() => setAuthOpen(true)}>Sign in<ArrowUpRight size={14} /></button>}
        </div>
      </header>
      {demoMode && <div className="demo-banner"><BookOpen size={15} /><span>Sample brief · Historical 2024 data · No live AI calls</span><button onClick={session ? newChat : () => setAuthOpen(true)}>Start your own<ArrowRight size={14} /></button></div>}
      {!demoMode && health && <div className="notice service-notice">{health}<button className="text-button" onClick={sample}>Open sample</button></div>}
      {work.error && !demoMode && <div role="alert" className="error-banner"><span>{work.error}</span><button className="icon-button" aria-label="Dismiss error" onClick={() => work.setError(null)}><X size={16} /></button></div>}
      <div ref={scroll} className={`workspace-scroll ${empty ? 'welcome-scroll' : ''}`} onScroll={() => { if (scroll.current) nearBottom.current = scroll.current.scrollHeight - scroll.current.scrollTop - scroll.current.clientHeight < 120; }}>
        {empty && <section className="welcome"><div className="welcome-kicker"><span className="sparkle-badge"><Sparkles size={14} /></span>A LITTLE CURIOSITY GOES A LONG WAY</div><h1>Good research starts<br />with a <em>better question.</em></h1><p className="welcome-description">Get to know a company. Connect the dots.<br />Build a clearer picture, with the evidence to back it up.</p>
          <div className="suggestion-grid"><button onClick={() => choose('Prepare a business brief on Stripe: products, recent developments, and open questions.')}><span className="suggestion-icon"><FileText size={20} /></span><strong>Get the company brief<ArrowUpRight size={15} /></strong><span>The business, the momentum,<br />and what’s worth watching.</span><small>Try researching Stripe</small></button><button onClick={() => choose('Compare Shopify and BigCommerce: target customers, products, and recent developments.')}><span className="suggestion-icon"><Globe2 size={20} /></span><strong>Explore the landscape<ArrowUpRight size={15} /></strong><span>Understand the players<br />and what sets them apart.</span><small>Try a competitor comparison</small></button><button onClick={() => choose('Research NVIDIA’s latest earnings using official filings. Explain the reporting period and key risks.')}><span className="suggestion-icon"><Search size={20} /></span><strong>Follow a development<ArrowUpRight size={15} /></strong><span>Go deeper on a headline,<br />a funding round, or a shift.</span><small>Try an earnings deep dive</small></button></div>
          <div className="welcome-trust"><span><ShieldCheck size={14} />Sources you can inspect</span><span><Check size={14} />Conversations you can return to</span></div>
          {!session && <button className="sample-link" onClick={sample}>Just looking? Explore a sample brief<ArrowRight size={15} /></button>}
        </section>}
        {work.loading && !demoMode && <div className="loading-state" role="status"><div className="skeleton wide" /><div className="skeleton" /><div className="skeleton" /><p>Loading your saved research…</p></div>}
        <div className="conversation">{messages.map(message => message.role === 'user' ? <div className="user-message" key={message.id}><div className="user-label">YOU <time>{new Date(message.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</time></div><p>{message.content}</p>{message.status !== 'sent' && <small>{message.status === 'failed' ? 'Research interrupted' : 'Research stopped'} · Your question is saved</small>}</div> : <Report key={message.id} message={message} selectSource={source => selectSource(source, message.sources)} />)}
          {busy && run && <div className="run-progress" role="status"><div className="run-status"><span className="pulse-dot" /><strong>{work.reconnecting ? 'Reconnecting to your research…' : run.cancel_requested ? 'Stopping research…' : 'Building a clearer picture'}</strong><button className="text-button" onClick={() => { setPanelOpen(true); setPanelTab('activity'); }}>View activity<ArrowUpRight size={13} /></button></div><div className="stage-track">{['clarity', 'research', 'validator', 'synthesis'].map((stage, i) => { const event = [...run.events].reverse().find(e => e.stage === stage); return <span key={stage} className={event?.status || ''}>{event?.status === 'completed' ? <Check size={12} /> : <span>{i + 1}</span>}{['Understand', 'Research', 'Review', 'Write'][i]}</span>; })}</div></div>}
          {busy && run?.draft && <Report streaming message={{ id: run.id, thread_id: run.thread_id, role: 'assistant', content: run.draft, sources: run.sources, status: 'streaming', created_at: run.created_at }} selectSource={source => selectSource(source, run.sources)} />}
          {run && ['failed', 'cancelled'].includes(run.status) && <div className="retry-card" role="status"><div><strong>{run.status === 'failed' ? 'This research needs another try.' : 'Research stopped.'}</strong><p>{run.error}</p></div><button className="button" disabled={work.sending} onClick={() => void work.send(run.prompt, run)}><RotateCcw size={14} />Retry</button></div>}
        </div>
      </div>
      {demoMode ? <div className="demo-footer"><div><strong>There’s more behind every good question.</strong><p>Start a research conversation of your own.</p></div><button className="button primary" onClick={session ? newChat : () => setAuthOpen(true)}>New research<Plus size={16} /></button></div>
        : session ? <Composer storageKey={`draft:${session.user.id}:${work.threadId || 'new'}`} busy={busy} sending={work.sending} stopping={!!run?.cancel_requested && busy} clarification={!!detail?.awaiting_clarification} disabled={work.loading || !!detail?.thread.archived_at} send={text => work.send(text)} cancel={() => void work.cancel()} suggestion={suggestion} />
        : <div className="guest-composer"><button onClick={() => setAuthOpen(true)}><span>Which company is on your mind?</span><span className="send-button"><ArrowRight size={18} /></span></button><p>Sign in to research. Explore the sample without an account.</p></div>}
      <footer className="workspace-footer"><span>SYNAPSE <span> / </span> RESEARCH WITH PERSPECTIVE</span><span>Built for the curious<ChevronDown size={11} /></span></footer>
    </main>
    {panelOpen && <EvidencePanel sources={sources} selected={selectedSource} run={run} tab={panelTab} setTab={setPanelTab} close={() => setPanelOpen(false)} />}
    {authOpen && <Modal close={() => setAuthOpen(false)} label="Sign in"><Auth close={() => setAuthOpen(false)} /></Modal>}
    {resetOpen && <Modal close={closeReset} label="Reset password"><PasswordReset close={closeReset} /></Modal>}
    {dialog && detail && <Modal close={() => setDialog(null)} label={dialog === 'rename' ? 'Rename conversation' : 'Delete conversation'}><form className="modal-form" onSubmit={e => { e.preventDefault(); if (dialog === 'rename') void work.update(detail.thread.thread_id, { title }); else void work.remove(detail.thread.thread_id); setDialog(null); }}><h2>{dialog === 'rename' ? 'Give this research a name.' : 'Delete this conversation?'}</h2>{dialog === 'rename' ? <label>Conversation title<input autoFocus value={title} maxLength={120} required onChange={e => setTitle(e.target.value)} /></label> : <p>Its messages, sources, and agent memory will be permanently removed.</p>}<div className="modal-actions"><button type="button" className="button" onClick={() => setDialog(null)}>Cancel</button><button className={`button ${dialog === 'delete' ? 'destructive' : 'primary'}`} disabled={dialog === 'rename' && !title.trim()}>{dialog === 'rename' ? 'Save name' : 'Delete conversation'}</button></div></form></Modal>}
  </div>;
}
