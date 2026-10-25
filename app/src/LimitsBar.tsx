import { useLayoutEffect, useRef, useState } from "react";
import { Card, HardLimits, Preference } from "./api";
import { UI, barText, preferenceText, weightWord } from "./labels";

interface Props {
  card: Card;
  searched: Partial<HardLimits>;
  wishes: Preference[];
  oneRow: boolean;  // the phone: one row, the rest behind "+N ▾" (D89)
}

// The limits bar: every hard limit other than the areas and the price (those are the title), as chips on
// lime-soft, with the wishes and the open questions behind a fold-out (D61, D89, D90). Hard limits are never
// hidden by rule: on a phone code measures what fits on one row and folds the rest, so nothing is cut off.
export function LimitsBar({ card, searched, wishes, oneRow }: Props) {
  const limits = barText(card, searched);  // firm wishes code made limits show here, not in the wishes (D79)
  const [open, setOpen] = useState(false);
  const [fit, setFit] = useState(limits.length);
  const row = useRef<HTMLUListElement>(null);

  useLayoutEffect(() => {
    if (!oneRow || !row.current) { setFit(limits.length); return; }
    const measure = () => {
      const ul = row.current!;
      const chips = Array.from(ul.children) as HTMLElement[];
      const gap = parseFloat(getComputedStyle(ul).columnGap || "8") || 8;
      const room = ul.clientWidth;
      let used = 0, count = 0;
      for (const chip of chips) {
        const next = used + (count ? gap : 0) + chip.offsetWidth;
        if (next > room) break;
        used = next;
        count += 1;
      }
      setFit(count);
    };
    measure();
    const watcher = new ResizeObserver(measure);
    watcher.observe(row.current);
    return () => watcher.disconnect();
  }, [oneRow, limits.join("|")]);  // eslint-disable-line react-hooks/exhaustive-deps

  if (limits.length === 0 && wishes.length === 0 && card.open_questions.length === 0) return null;  // the title says it all
  const hidden = limits.slice(fit);
  const folded = hidden.length + wishes.length;
  // "+3" when limits are folded too (the button says how much is behind it, D89), "+1 wish" when only wishes are
  const label = !folded ? UI.details : hidden.length ? `+${folded}` : `+${UI.wish(wishes.length)}`;

  return (
    <section className={`bar ${oneRow ? "one-row" : ""}`} aria-label={UI.limits}>
      <div className="bar-line">
        {!oneRow && <span className="label bar-label">{UI.limits}</span>}
        <ul className="bar-limits" ref={row}>
          {limits.map((text, i) => <li key={text} className={i >= fit ? "folded" : ""}>{text}</li>)}
        </ul>
        <button type="button" className="link more" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
          {label} {open ? "▴" : "▾"}
        </button>
      </div>
      {open && (
        <>
          <div className="dim on sheet-dim" onClick={() => setOpen(false)} aria-hidden="true" />
          <div className="bar-details" role="region" aria-label={UI.limits}>
            {(oneRow ? limits : hidden).length > 0 && (  // the fold-out lists every limit in full on a phone
              <ul className="bar-limits wrap">
                {(oneRow ? limits : hidden).map((text) => <li key={text}>{text}</li>)}
              </ul>
            )}
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
            <p className="hint">{UI.limitsHint}</p>
            {oneRow && <button type="button" className="wide" onClick={() => setOpen(false)}>{UI.close}</button>}
          </div>
        </>
      )}
    </section>
  );
}
