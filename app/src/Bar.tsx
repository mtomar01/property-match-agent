import { useState } from "react";
import { Card, HardLimits, Preference } from "./api";
import { barText, preferenceText, weightWord } from "./labels";

// The card lives on as one line above the deck: every hard limit, always visible (D61). Details fold out, read only.
export function Bar({ card, searched, wishes }: { card: Card; searched: Partial<HardLimits>; wishes: Preference[] }) {
  const [open, setOpen] = useState(false);
  const limits = barText(card, searched);  // firm wishes code made limits show here, not in the wishes (D79)
  return (
    <section className="bar" aria-label="What the deck searches">
      <div className="bar-line">
        <ul className="bar-limits">
          {limits.map((text) => <li key={text}>{text}</li>)}
        </ul>
        <button type="button" className="link" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
          {wishes.length ? `+${wishes.length} wish${wishes.length === 1 ? "" : "es"}` : "details"} {open ? "▴" : "▾"}
        </button>
      </div>
      {open && (
        <div className="bar-details">
          <p className="hint">Hard limits are checked in code and never broken. Wishes only rank. To change anything, tell the assistant.</p>
          {wishes.length > 0 && (
            <ul className="prefs">
              {wishes.map((p, i) => (
                <li key={`${p.feature}-${i}`}>
                  <span>{preferenceText(p)}</span>
                  <span className="weight">{weightWord(p.weight)}</span>
                </li>
              ))}
            </ul>
          )}
          {card.open_questions.length > 0 && (
            <ul className="notes">
              {card.open_questions.map((q) => <li key={q}>{q}</li>)}
            </ul>
          )}
        </div>
      )}
    </section>
  );
}
