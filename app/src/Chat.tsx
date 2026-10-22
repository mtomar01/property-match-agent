import { FormEvent, useEffect, useRef, useState } from "react";

export interface Message {
  role: "user" | "assistant";
  text: string;
}

interface Props {
  messages: Message[];
  busy: boolean;
  error: string | null;
  onSend: (text: string) => void;
}

const STARTERS = [
  "Ψάχνω δυάρι στο Περιστέρι, μέχρι 160.000.",
  "A two bedroom flat in Egaleo, around 200k, with a balcony.",
];

export function Chat({ messages, busy, error, onSend }: Props) {
  const [draft, setDraft] = useState("");
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => end.current?.scrollIntoView({ block: "end" }), [messages, busy]);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!draft.trim() || busy) return;
    onSend(draft.trim());
    setDraft("");
  };

  return (
    <section className="panel chat" aria-labelledby="chat-h">
      <h2 id="chat-h">Tell it what you're looking for</h2>
      <div className="messages" aria-live="polite">
        {messages.length === 0 && (
          <div className="empty">
            <p>Write the way you'd tell a friend, in Greek or English. It asks only what it needs, then shows the card on the right.</p>
            <div className="starters">
              {STARTERS.map((text) => (
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
        {busy && <p className="bubble assistant thinking">Thinking…</p>}
        <div ref={end} />
      </div>
      {error && <p className="error" role="alert">{error}</p>}
      <form className="composer" onSubmit={submit}>
        <label htmlFor="message" className="sr-only">Your message</label>
        <textarea
          id="message"
          rows={2}
          value={draft}
          placeholder="Γράψτε εδώ… / Write here…"
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) submit(e);
          }}
        />
        <button type="submit" className="primary" disabled={busy || !draft.trim()}>
          Send
        </button>
      </form>
    </section>
  );
}
