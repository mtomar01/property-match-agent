import { useState } from "react";
import { useLabels } from "./labels";

interface Props {
  kind: "reject" | "skip";
  title: string;
  options: [string, string][];
  none: string | null;
  busy: boolean;
  onPick: (reasons: string[], note?: string) => void;
  onCancel: () => void;
}

// The reason chips after a reject or a "can't judge" (design system, ReasonChips; D71): one tap is the answer,
// "Other…" opens one line for the user's own words (up to 300 characters, scrubbed of contact details by the
// server). After a reject the chips sit on reject-soft; a chosen chip takes the reject border.
export function ReasonChips({ kind, title, options, none, busy, onPick, onCancel }: Props) {
  const L = useLabels();
  const [other, setOther] = useState(false);
  const [note, setNote] = useState("");
  return (
    <div className={kind === "reject" ? "reject-why" : "cant-judge"}>
      <p className="hint">{title}</p>
      <div className="chips">
        {options.map(([code, text]) => (
          <button key={code} type="button" className="chip" disabled={busy} onClick={() => onPick([code])}>{text}</button>
        ))}
        <button type="button" className={`chip ${other ? "on" : ""}`} disabled={busy} aria-expanded={other} onClick={() => setOther((o) => !o)}>
          {L.other}
        </button>
        {none && <button type="button" className="chip" disabled={busy} onClick={() => onPick([])}>{none}</button>}
        <button type="button" className="link" onClick={onCancel}>{L.keepLooking}</button>
      </div>
      {other && (
        <form className="composer" onSubmit={(e) => { e.preventDefault(); onPick(["other"], note.trim() || undefined); }}>
          <label htmlFor={`${kind}-note`} className="sr-only">{L.inYourWords}</label>
          <input id={`${kind}-note`} className="note" autoFocus maxLength={300} value={note} onChange={(e) => setNote(e.target.value)}
            placeholder={kind === "reject" ? L.rejectWords : L.skipWords} />
          <button type="submit" className={note.trim() ? "primary" : ""} disabled={busy}>{L.save}</button>
        </form>
      )}
    </div>
  );
}
