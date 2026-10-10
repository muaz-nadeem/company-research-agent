import { Archive, ArrowUpRight, ChevronLeft, LogOut, MessageSquare, Plus, Search } from 'lucide-react';
import type { Thread } from '../api';

export default function Sidebar({ threads, selected, search, setSearch, archived, setArchived, select, newChat, close, email, signOut, signIn, sample }: {
  threads: Thread[]; selected: string | null; search: string; setSearch: (text: string) => void; archived: boolean;
  setArchived: (value: boolean) => void; select: (id: string) => void; newChat: () => void; close: () => void;
  email?: string; signOut: () => void; signIn: () => void; sample: () => void;
}) {
  const groups = new Map<string, Thread[]>();
  for (const thread of threads) {
    const date = new Date(thread.updated_at);
    const group = date.toDateString() === new Date().toDateString() ? 'Today' : date.toLocaleDateString([], { month: 'long', year: 'numeric' });
    groups.set(group, [...(groups.get(group) || []), thread]);
  }
  return <aside className="sidebar" aria-label="Conversations">
    <div className="sidebar-brand"><a href="/" onClick={e => { e.preventDefault(); newChat(); }}><span className="brand-mark small">s<span>·</span></span><span>synapse<span className="brand-caption">RESEARCH WORKSPACE</span></span></a><button className="icon-button mobile-only" aria-label="Close navigation" onClick={close}><ChevronLeft size={18} /></button></div>
    <button className="button new-chat" onClick={newChat}><Plus size={17} />New research<span>↗</span></button>
    {email && <label className="search-box"><Search size={15} /><input aria-label="Search conversations" placeholder="Search your research" value={search} onChange={e => setSearch(e.target.value)} /></label>}
    <div className="sidebar-section"><span>{archived ? 'ARCHIVED' : 'YOUR WORKSPACE'}</span>{email && <button className={`icon-button ${archived ? 'selected' : ''}`} aria-label={archived ? 'Show recent conversations' : 'Show archived conversations'} onClick={() => setArchived(!archived)}><Archive size={14} /></button>}</div>
    <nav className="thread-list">
      {[...groups.entries()].map(([group, items]) => <div key={group}><p className="thread-group">{group}</p>{items.map(thread => <button key={thread.thread_id} className={`thread ${selected === thread.thread_id ? 'active' : ''}`} onClick={() => select(thread.thread_id)} title={thread.title}><MessageSquare size={14} /><span>{thread.title}</span>{selected === thread.thread_id && <span className="thread-active-dot" />}</button>)}</div>)}
      {!threads.length && <p className="sidebar-empty">{search ? 'No matching conversations.' : archived ? 'No archived conversations.' : 'Your next good question starts here. Saved research will appear in this space.'}</p>}
    </nav>
    <button className="sample-card" onClick={sample}><span className="eyebrow">TAKE A LOOK AROUND</span><strong>A brief worth opening.<ArrowUpRight size={17} /></strong><span>Explore a sample. Follow a source.</span></button>
    <footer className="sidebar-footer">{email ? <><span className="avatar">{email[0].toUpperCase()}</span><span className="account-name" title={email}>{email}<small>Personal workspace</small></span><button className="icon-button" aria-label="Sign out" onClick={signOut}><LogOut size={16} /></button></> : <><span className="avatar">↗</span><div><strong>Make it your workspace</strong><button className="text-button" onClick={signIn}>Sign in to save your research</button></div></>}</footer>
  </aside>;
}
