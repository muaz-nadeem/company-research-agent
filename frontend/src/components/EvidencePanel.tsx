import { ExternalLink, FileSearch, ListChecks, X } from 'lucide-react';
import type { Run, Source } from '../api';
import { useEffect } from 'react';

const names: Record<string, string> = { clarity: 'Understand the question', research: 'Gather source material', validator: 'Review the evidence', synthesis: 'Write the brief' };
export default function EvidencePanel({ sources, selected, run, tab, setTab, close }: {
  sources: Source[]; selected: Source | null; run: Run | null; tab: 'sources' | 'activity'; setTab: (tab: 'sources' | 'activity') => void; close: () => void;
}) {
  useEffect(() => {
    if (selected && tab === 'sources') document.querySelector('.source-card.highlighted')?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }, [selected, tab]);
  return <aside className="evidence-panel" aria-label="Evidence panel">
    <div className="panel-title"><div><p className="eyebrow">BEHIND THE BRIEF</p><h2>Show your sources.</h2></div><button className="icon-button" aria-label="Close evidence panel" onClick={close}><X size={18} /></button></div>
    <div className="panel-tabs"><button className={tab === 'sources' ? 'selected' : ''} onClick={() => setTab('sources')}><FileSearch size={14} />Sources <span>{sources.length}</span></button><button className={tab === 'activity' ? 'selected' : ''} onClick={() => setTab('activity')}><ListChecks size={14} />Activity</button></div>
    <div className="panel-scroll">
      {tab === 'sources' ? sources.length ? sources.map(source => <article key={source.id + source.url} className={`source-card ${selected?.url === source.url ? 'highlighted' : ''}`}>
        <div className="source-meta"><span>{source.id.replace('S', '').padStart(2, '0')}</span><span>{new URL(source.url).hostname.replace('www.', '')}</span></div>
        <h3><a href={source.url} target="_blank" rel="noopener noreferrer">{source.title}<ExternalLink size={13} /></a></h3>
        <p>{source.excerpt || 'No excerpt was returned for this source.'}</p>
        <footer>Published {source.published_at || 'date unavailable'}<br />Retrieved {source.retrieved_at}</footer>
      </article>) : <div className="panel-empty"><FileSearch size={28} /><h3>A trail you can follow.</h3><p>Source excerpts and dates appear here as research progresses. Select an inline citation to inspect its source.</p></div>
      : <><p className="panel-note">An inspectable record of the work. Evidence review is performed by AI, not an independent fact-checker.</p>
        {!run && <p className="muted">No live research activity in this sample.</p>}
        {run?.events.filter(e => e.type === 'stage' || e.type === 'validation').map((event, i) => <div key={i} className="activity-item"><span className={`activity-dot ${event.status === 'completed' ? 'complete' : ''}`} /><div><strong>{event.stage ? names[event.stage] || event.stage : 'Evidence review'}</strong><p>{event.message || (event.status === 'completed' ? `Completed in ${((event.duration_ms || 0) / 1000).toFixed(1)}s` : 'Started')}</p><time>{new Date(event.at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</time></div></div>)}
        {run?.metrics.duration_ms != null && <div className="run-metrics"><strong>Run details</strong><span>{(run.metrics.duration_ms / 1000).toFixed(1)}s total</span><span>{run.metrics.llm_calls ?? 0} model calls</span><span>{(run.metrics.input_tokens ?? 0) + (run.metrics.output_tokens ?? 0)} tokens</span><span>{run.metrics.estimated_llm_cost_usd != null ? `$${run.metrics.estimated_llm_cost_usd.toFixed(5)} estimated model cost` : 'Cost rates not configured'}</span></div>}
      </>}
    </div>
  </aside>;
}
