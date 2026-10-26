import { useLayoutEffect, useRef, useState } from "react";
import { Card, HardLimits, Learning, Preference } from "./api";
import { LearningLine } from "./LearningLine";
import { barText, preferenceText, useLabels, weightWord } from "./labels";

interface Props {
  card: Card;
  searched: Partial<HardLimits>;
  wishes: Preference[];
  learning: Learning | null;
}

// The limits bar: every hard limit other than the areas and the price (those are the title), as chips on
// lime-soft, with the wishes, the open questions and the learning line behind a fold-out (D61, D89, D90, D97).
// One row on every device: code measures what fits and folds the rest, so nothing is hidden by rule and
// nothing is cut off; the fold-out lists every limit in full.
export function LimitsBar({ card, searched, wishes, learning }: Props) {
  const L = useLabels();
  // the order the user asked for leads the row (D98), then every limit; firm wishes code made limits show here (D79)
  const limits = [...(card.order_by ? [L.orders[card.order_by] ?? card.order_by] : []), ...barText(card, searched, L)];
  const [open, setOpen] = useState(false);
  const [fit, setFit] = useState(limits.length);
  const row = useRef<HTMLUListElement>(null);

  useLayoutEffect(() => {
    if (!row.current) { setFit(limits.length); return; }
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
  }, [limits.join("|")]);  // eslint-disable-line react-hooks/exhaustive-deps

  if (limits.length === 0 && wishes.length === 0 && card.open_questions.length === 0 && !learning) return null;  // the title says it all
  const hidden = limits.slice(fit);
  const folded = hidden.length + wishes.length;
  // "+3" when limits are folded too (the button says how much is behind it, D89), "+1 wish" when only wishes are
  const label = !folded ? L.details : hidden.length ? `+${folded}` : `+${L.wish(wishes.length)}`;

  return (
    <section className="bar" aria-label={L.limits}>
      <div className="bar-line">
        <span className="label bar-label">{L.limits}</span>
        <ul className="bar-limits" ref={row}>
          {limits.map((text, i) => <li key={text} className={`${i >= fit ? "folded" : ""} ${card.order_by && i === 0 ? "order" : ""}`}>{text}</li>)}
        </ul>
        <button type="button" className="link more" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
          {label} {open ? "▴" : "▾"}
        </button>
      </div>
      {open && (
        <>
          <div className="dim on sheet-dim" onClick={() => setOpen(false)} aria-hidden="true" />
          <div className="bar-details" role="region" aria-label={L.limits}>
            {limits.length > 0 && (
              <ul className="bar-limits wrap">
                {limits.map((text, i) => <li key={text} className={card.order_by && i === 0 ? "order" : ""}>{text}</li>)}
              </ul>
            )}
            {wishes.length > 0 && (
              <ul className="prefs">
                {wishes.map((p, i) => (
                  <li key={`${p.feature}-${i}`}>
                    <span>{preferenceText(p, L)}</span>
                    <span className="weight">{weightWord(p.weight, L)}</span>
                  </li>
                ))}
              </ul>
            )}
            {card.open_questions.length > 0 && (
              <ul className="notes">
                {card.open_questions.map((q) => <li key={q}>{q}</li>)}
              </ul>
            )}
            <LearningLine learning={learning} orderBy={card.order_by} />
            <p className="hint">{L.limitsHint}</p>
            <button type="button" className="wide close-sheet" onClick={() => setOpen(false)}>{L.close}</button>
          </div>
        </>
      )}
    </section>
  );
}
