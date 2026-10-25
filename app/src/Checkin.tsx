import { useState } from "react";
import { Checkin as CheckinData } from "./api";

interface Props {
  checkin: CheckinData;
  busy: boolean;
  onAnswer: (text: string) => void;
  onTap: (answer: string) => void;
}

// After 10 likes or rejects, one question on a lime-soft card labelled TISPI (design system, Checkin; D66, D75):
// a pattern code found, worded by the assistant and answered in the chat; a reason the user tapped, Yes or No;
// or the three-tap pulse. A "yes" goes through the chat so the assistant makes the change; "no" and the pulse
// are taps. On a phone the card is a sheet from the bottom; the stylesheet decides.
export function Checkin({ checkin, busy, onAnswer, onTap }: Props) {
  const [text, setText] = useState("");
  const step = checkin.ladder ?? "pattern";
  const options = checkin.options ?? {};
  return (
    <>
      <div className="dim on sheet-dim" aria-hidden="true" />
      <section className="checkin" role="dialog" aria-modal="true" aria-label="A question from Tispi">
        <span className="who">Tispi</span>
        <p className="checkin-text">{checkin.reply}</p>
        {step === "pulse" ? (
          <div className="chips pulse">
            {Object.entries(options).map(([code, label]) => (
              <button key={code} type="button" className="chip" disabled={busy} onClick={() => onTap(code)}>{label}</button>
            ))}
          </div>
        ) : (
          <>
            <div className="chips">
              {step === "reason" ? (
                <>
                  <button type="button" className="chip on" disabled={busy} onClick={() => onAnswer(checkin.yes_message ?? "Yes")}>{options.yes ?? "Yes"}</button>
                  <button type="button" className="chip" disabled={busy} onClick={() => onTap("no")}>{options.no ?? "No"}</button>
                </>
              ) : (
                <>
                  <button type="button" className="chip on" disabled={busy} onClick={() => onAnswer("Yes")}>Yes, do that</button>
                  <button type="button" className="chip" disabled={busy} onClick={() => onAnswer("No, keep it as it is")}>No, keep it</button>
                </>
              )}
            </div>
            <form className="composer" onSubmit={(e) => { e.preventDefault(); if (text.trim()) { onAnswer(text.trim()); setText(""); } }}>
              <label htmlFor="checkin-answer" className="sr-only">Your answer</label>
              <textarea id="checkin-answer" rows={1} value={text} placeholder="Or answer in your words, e.g. make it 2010" onChange={(e) => setText(e.target.value)} />
              <button type="submit" className={text.trim() ? "primary" : ""} disabled={busy || !text.trim()}>Send</button>
            </form>
          </>
        )}
      </section>
    </>
  );
}
