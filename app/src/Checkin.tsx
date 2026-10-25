import { useState } from "react";
import { Checkin as CheckinData } from "./api";
import { useLabels } from "./labels";

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
  const L = useLabels();
  const [text, setText] = useState("");
  const step = checkin.ladder ?? "pattern";
  const options = checkin.options ?? {};
  return (
    <>
      <div className="dim on sheet-dim" aria-hidden="true" />
      <section className="checkin" role="dialog" aria-modal="true" aria-label={L.question}>
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
                  <button type="button" className="chip on" disabled={busy} onClick={() => onAnswer(checkin.yes_message ?? L.yes)}>{options.yes ?? L.yes}</button>
                  <button type="button" className="chip" disabled={busy} onClick={() => onTap("no")}>{options.no ?? L.noKeep}</button>
                </>
              ) : (
                <>
                  <button type="button" className="chip on" disabled={busy} onClick={() => onAnswer(L.yes)}>{L.yesDoThat}</button>
                  <button type="button" className="chip" disabled={busy} onClick={() => onAnswer(L.noKeepMessage)}>{L.noKeep}</button>
                </>
              )}
            </div>
            <form className="composer" onSubmit={(e) => { e.preventDefault(); if (text.trim()) { onAnswer(text.trim()); setText(""); } }}>
              <label htmlFor="checkin-answer" className="sr-only">{L.yourAnswer}</label>
              <textarea id="checkin-answer" rows={1} value={text} placeholder={L.orAnswer} onChange={(e) => setText(e.target.value)} />
              <button type="submit" className={text.trim() ? "primary" : ""} disabled={busy || !text.trim()}>{L.send}</button>
            </form>
          </>
        )}
      </section>
    </>
  );
}
