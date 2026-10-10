import { FormEvent, useEffect, useRef, useState } from 'react';
import { ArrowUp, Square } from 'lucide-react';

export default function Composer({ storageKey, busy, sending, stopping, clarification, disabled, send, cancel, suggestion }: {
  storageKey: string; busy: boolean; sending: boolean; stopping: boolean; clarification: boolean; disabled?: boolean;
  send: (text: string) => Promise<boolean>; cancel: () => void; suggestion: { text: string; nonce: number } | null;
}) {
  const [text, setText] = useState(() => sessionStorage.getItem(storageKey) || '');
  const input = useRef<HTMLTextAreaElement>(null);
  const key = useRef(storageKey);
  useEffect(() => { key.current = storageKey; setText(sessionStorage.getItem(storageKey) || ''); }, [storageKey]);
  useEffect(() => { if (suggestion) { setText(suggestion.text); sessionStorage.setItem(storageKey, suggestion.text); input.current?.focus(); } }, [suggestion]); // eslint-disable-line
  useEffect(() => { if (input.current) { input.current.style.height = 'auto'; input.current.style.height = `${Math.min(input.current.scrollHeight, 180)}px`; } }, [text]);
  const submit = async (event?: FormEvent) => {
    event?.preventDefault();
    if (!text.trim() || busy || sending || disabled) return;
    const submittedKey = storageKey, submittedText = text;
    if (await send(text.trim())) {
      sessionStorage.removeItem(submittedKey);
      if (key.current === submittedKey) setText(current => current === submittedText ? '' : current);
    }
  };
  return <div className="composer-wrap">
    {clarification && <div className="clarification-hint">One detail before we begin. Your reply will continue this research.</div>}
    <form className={`composer ${disabled ? 'is-disabled' : ''}`} onSubmit={submit}>
      <textarea ref={input} aria-label="Research question" rows={1} maxLength={4000} value={text}
        placeholder={clarification ? 'Add a little more context…' : 'Which company is on your mind?'} disabled={disabled}
        onChange={e => { setText(e.target.value); sessionStorage.setItem(storageKey, e.target.value); }}
        onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); void submit(); } }} />
      <div className="composer-bottom"><span>{text.length > 3500 ? `${text.length}/4000` : 'A company, a question, a place to start.'}</span>
        {busy ? <button className="send-button stop" type="button" aria-label="Stop research" disabled={stopping} onClick={cancel}><Square size={14} fill="currentColor" /></button>
          : <button className="send-button" aria-label="Send research question" disabled={!text.trim() || sending || disabled}><ArrowUp size={19} /></button>}
      </div>
    </form>
    <p className="composer-caption">{stopping ? 'Stopping after the current provider operation…' : sending ? 'Saving your question…' : busy ? 'Research continues if you switch conversations.' : 'Follow the sources. AI can miss context.'}</p>
  </div>;
}
