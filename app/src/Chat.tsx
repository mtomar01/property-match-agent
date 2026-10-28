import { FormEvent, useEffect, useRef, useState } from "react";
import { Message } from "./api";
import { useLabels } from "./labels";

interface Props {
  messages: Message[];
  busy: boolean;
  error: string | null;
  compact?: boolean;
  intro?: string;  // what the data covers, under the opening line
  askingAbout?: string[];  // what the assistant's last reply asks: "purpose" and "intent" get tap answers (D104)
  onSend: (text: string) => void;
}

// Tap answers send their words as the user's own message, so the assistant still decides from the chat (D104).
function Choices({ options, onPick, disabled }: { options: [string, string][]; onPick: (text: string) => void; disabled: boolean }) {
  return (
    <div className="choices">
      {options.map(([label, says]) => (
        <button key={label} type="button" className="choice" disabled={disabled} onClick={() => onPick(says)}>{label}</button>
      ))}
    </div>
  );
}


export function Chat({ messages, busy, error, compact = false, intro, askingAbout = [], onSend }: Props) {
  const L = useLabels();
  const [draft, setDraft] = useState("");
  const end = useRef<HTMLDivElement>(null);

  // Braces matter: scrollIntoView returns a Promise in recent Chromium, and React would call it as the cleanup.
  useEffect(() => {
    end.current?.scrollIntoView({ block: "end" });
  }, [messages, busy]);

  const intents: [string, string][] = [[L.buyChip, L.buySays], [L.rentChip, L.rentSays]];
  const purposes: [string, string][] = [[L.liveChip, L.liveChip], [L.investChip, L.investChip]];
  const lastIsAssistant = messages.length > 0 && messages[messages.length - 1].role === "assistant";
  const quick = !busy && lastIsAssistant
    ? askingAbout.includes("purpose") ? purposes : askingAbout.includes("intent") ? intents : null
    : null;

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
            <Choices options={intents} onPick={onSend} disabled={busy} />
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
        {quick && <Choices options={quick} onPick={onSend} disabled={busy} />}
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
