import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Check, Copy, Download, FileText } from 'lucide-react';
import type { Message, Source } from '../api';

export function exportMarkdown(content: string, sources: Source[], title = 'research-brief') {
  const body = content.replace(/\]\(#source-(S\d+)\)/g, (match, id) => {
    const source = sources.find(s => s.id === id); return source ? `](${source.url})` : match;
  }) + '\n\n## Sources\n' + sources.map(s => `- [${s.title}](${s.url}) — retrieved ${s.retrieved_at}`).join('\n');
  const url = URL.createObjectURL(new Blob([body], { type: 'text/markdown;charset=utf-8' }));
  const link = document.createElement('a'); link.href = url; link.download = `${title.replace(/[^a-z0-9-]/gi, '-').slice(0, 80)}.md`; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export default function Report({ message, selectSource, streaming = false }: { message: Message; selectSource: (source: Source) => void; streaming?: boolean }) {
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState('');
  return <article className={`report ${streaming ? 'streaming' : ''}`}>
    <div className="report-label"><span><FileText size={14} />{message.sources.length ? 'RESEARCH BRIEF' : streaming ? 'WRITING YOUR BRIEF' : 'SYNAPSE'}</span>{!streaming && <div className="report-actions">
      <button className="icon-button" aria-label="Copy response" onClick={async () => { try { await navigator.clipboard.writeText(message.content); setCopied(true); setTimeout(() => setCopied(false), 2000); } catch { setCopyError('Clipboard unavailable. Export the brief instead.'); } }}>{copied ? <Check size={15} /> : <Copy size={15} />}</button>
      <button className="icon-button" aria-label="Export response as Markdown" onClick={() => exportMarkdown(message.content, message.sources)}><Download size={15} /></button>
    </div>}</div>
    <div className="prose"><ReactMarkdown remarkPlugins={[remarkGfm]} components={{
      a: ({ href, children }) => {
        const source = message.sources.find(s => href === `#source-${s.id}` || href === s.url);
        if (source) return <button className="citation" onClick={() => selectSource(source)} aria-label={`View source ${source.id.slice(1)}: ${source.title}`}>{children}</button>;
        return <span>{children}</span>;
      },
    }}>{message.content}</ReactMarkdown></div>
    {copyError && <p role="status" className="muted">{copyError}</p>}
    {!!message.sources.length && <button className="source-summary" onClick={() => selectSource(message.sources[0])}><span className="source-dots">{message.sources.slice(0, 3).map(s => <span key={s.id}>{new URL(s.url).hostname.replace('www.', '')[0].toUpperCase()}</span>)}</span><span>{message.sources.length} source{message.sources.length !== 1 ? 's' : ''} · Explore the evidence</span><span>↗</span></button>}
  </article>;
}
