import { FormEvent, useEffect, useRef, useState } from "react";
import { Message } from "./api";
import { useLabels } from "./labels";

interface Props {
  messages: Message[];
  busy: boolean;
  error: string | null;
  compact?: boolean;
  intro?: string;  // what the data covers, under the opening line
  onSend: (text: string) => void;
}


export function Chat({ messages, busy, error, compact = false, intro, onSend }: Props) {
  const L = useLabels();
  const [draft, setDraft] = useState("");
  const end = useRef<HTMLDivElement>(null);

  // Braces matter: scrollIntoView returns a Promise in recent Chromium, and React would call it as the cleanup.
  useEffect(() => {
    end.current?.scrollIntoView({ block: "end" });
  }, [messages, busy]);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!draft.trim() || busy) return;
    onSend(draft.trim());
    setDraft("");
  };

  return (
    <section className={`panel chat ${compact ? "compact" : ""}`} aria-labelledby="chat-h">
      <h2 id="chat-h">{compact ? L.chatChange : L.chatNew}</h2>
      <div className="messages" aria-live="polite">
        {messages.length === 0 && (
          <div className="empty">
            <p>{L.chatIntro}</p>
            {intro && <p className="hint">{intro}</p>}
            <div className="starters">
              {L.starters.map((text) => (
                <button key={text} type="button" className="starter" onClick={() => setDraft(text)}>
                  {text}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m, i) => (
          <p key={i} className={`bubble ${m.role}`}>
            {m.text}
          </p>
        ))}
        {busy && <p className="bubble assistant thinking">{L.thinking}</p>}
        <div ref={end} />
      </div>
      {error && <p className="error" role="alert">{error}</p>}
      <form className="composer" onSubmit={submit}>
        <label htmlFor="message" className="sr-only">{L.yourMessage}</label>
        <textarea
          id="message"
          rows={2}
          value={draft}
          placeholder={compact ? L.changeHere : L.writeHere}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) submit(e);
          }}
        />
        <button type="submit" className={draft.trim() ? "primary" : ""} disabled={busy || !draft.trim()}>
          {L.send}
        </button>
      </form>
    </section>
  );
}
