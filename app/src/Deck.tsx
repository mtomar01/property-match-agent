import { useEffect, useState } from "react";
import { Checkin, Deck as DeckData, DeckCard, Decision, Learning, Widening } from "./api";
import { CANT_JUDGE_REASONS, REJECT_REASONS, floorText, money, wideningMessage, wideningText } from "./labels";

interface Props {
  deck: DeckData | null;
  card: DeckCard | null;
  checkin: Checkin | null;
  busy: boolean;
  canUndo: boolean;
  onSwipe: (card: DeckCard, decision: Decision, reasons: string[], note?: string) => void;
  onUndo: () => void;
  onAnswer: (text: string) => void;
  onTap: (answer: string) => void;
}

// One home at a time. Right to like, left to reject with a quick reason; in the middle, back and skip;
// below them "Can't judge" for a listing that doesn't let you decide (spec section 4, D71).
export function Deck({ deck, card, checkin, busy, canUndo, onSwipe, onUndo, onAnswer, onTap }: Props) {
  const [asking, setAsking] = useState<null | "reject" | "skip">(null);

  useEffect(() => setAsking(null), [card?.listing_id]);

  useEffect(() => {
    if (checkin) return;
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (target && (target.tagName === "TEXTAREA" || target.tagName === "INPUT")) return;
      if (busy) return;
      if (e.key === "Backspace" && canUndo) { e.preventDefault(); onUndo(); return; }
      if (!card) return;
      if (e.key === "ArrowRight") onSwipe(card, "like", []);
      if (e.key === "ArrowLeft") setAsking("reject");
      if (e.key === "ArrowDown") onSwipe(card, "skip", []);
      if (e.key === "Escape") setAsking(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [card, checkin, busy, canUndo, onSwipe, onUndo]);

  if (!deck) return <section className="panel deck"><p className="muted">Loading the homes…</p></section>;

  if (checkin) return <CheckinCard checkin={checkin} busy={busy} onAnswer={onAnswer} onTap={onTap} />;

  if (!card) {
    return (
      <section className="panel deck">
        <h2>{deck.total_matches === 0 ? "Nothing passes every limit" : "You've seen every home that passes"}</h2>
        {canUndo && <button type="button" className="link" disabled={busy} onClick={onUndo}>↶ Back to the last one</button>}
        <p className="muted">
          {deck.total_matches} {deck.total_matches === 1 ? "home passes" : "homes pass"} the limits on the bar.
          {deck.if_eased ? " Code counted a few ways to widen the search; pick one and the assistant will make the change." : " Tell the assistant what to change."}
        </p>
        {deck.if_eased && <Widen deck={deck} busy={busy} onAsk={onAnswer} />}
      </section>
    );
  }

  const photo = card.photo_url;
  return (
    <section className="panel deck" aria-label="Swipe deck">
      <article className="home">
        <Photo url={photo} card={card} />
        <div className="home-body">
          {card.skipped_before && <p className="hint">You skipped this one earlier.</p>}
          <div className="home-head">
            <strong className="price">{money(card.price_eur)}</strong>
            <span className="muted">{card.price_per_m2 ? `€${card.price_per_m2.toLocaleString("en-GB")}/m²` : ""}</span>
          </div>
          <p className="facts">
            {[
              card.size_m2 != null ? `${card.size_m2} m²` : null,
              card.bedrooms != null ? `${card.bedrooms} bed` : null,
              floorText(card.floor),
              [card.area, card.sub_area].filter(Boolean).join(" · "),
              card.year_built ? `built ${card.year_built}` : null,
              card.renovated_year ? `renovated ${card.renovated_year}` : null,
              card.energy_class ? `energy ${card.energy_class}` : null,
            ].filter(Boolean).join(" · ")}
          </p>
          <ul className="reasons">
            {card.reasons.map((r) => <li key={r.feature}>{r.text}</li>)}
          </ul>
          {card.market.length > 0 && (
            <ul className="market" aria-label="The market">
              {card.market.map((m) => <li key={m.feature} className={m.feature}>{m.text}</li>)}
            </ul>
          )}
          <a className="small" href={card.url} target="_blank" rel="noreferrer noopener">
            {card.synthetic ? "Synthetic listing (no real page)" : `Open on ${card.source} ↗`}
          </a>
        </div>
      </article>

      {asking === "reject" ? (
        <Reasons
          kind="reject" busy={busy} title="Why not? One tap is enough; it teaches the ranking more than the swipe."
          options={REJECT_REASONS} none="No reason"
          onPick={(reasons, note) => onSwipe(card, "reject", reasons, note)} onCancel={() => setAsking(null)}
        />
      ) : asking === "skip" ? (
        <Reasons
          kind="skip" busy={busy} title="What stops you deciding? This one won't count as a like or a reject, and it comes back later."
          options={CANT_JUDGE_REASONS} none={null}
          onPick={(reasons, note) => onSwipe(card, "skip", reasons, note)} onCancel={() => setAsking(null)}
        />
      ) : (
        <>
          <div className="swipe-buttons">
            <button type="button" className="swipe reject" disabled={busy} onClick={() => setAsking("reject")} aria-keyshortcuts="ArrowLeft">
              ← Reject
            </button>
            <div className="middle">
              <button type="button" className="icon" disabled={busy || !canUndo} onClick={onUndo} aria-label="Back to the previous home"
                title="Back to the previous home (Backspace)" aria-keyshortcuts="Backspace">↶</button>
              <button type="button" className="icon" disabled={busy} onClick={() => onSwipe(card, "skip", [])} aria-label="Skip this home for now"
                title="Skip for now; it comes back later (↓)" aria-keyshortcuts="ArrowDown">↷</button>
            </div>
            <button type="button" className="swipe like primary" disabled={busy} onClick={() => onSwipe(card, "like", [])} aria-keyshortcuts="ArrowRight">
              Like →
            </button>
          </div>
          <div className="under-buttons">
            <button type="button" className="link small" disabled={busy} onClick={() => setAsking("skip")}>Can't judge this one?</button>
            <span className="muted small">{deck.remaining} left · {deck.swipes.swipes} swiped</span>
          </div>
          <LearningLine learning={deck.learning} />
        </>
      )}
    </section>
  );
}

// How the order is decided (D76): the chat's wishes at first, then more and more the user's own likes and rejects.
function LearningLine({ learning }: { learning: Learning | null }) {
  if (!learning) {
    return <p className="muted small learning">Order: your wishes from the chat. Your swipes start counting after 3 likes and 3 rejects.</p>;
  }
  const words = (direction: "for" | "against") =>
    learning.leans.filter((l) => l.direction === direction).map((l) => l.words).join(", ");
  const liked = words("for"), disliked = words("against");
  return (
    <p className="muted small learning">
      Order: {Math.round(learning.share * 100)}% from your {learning.verdicts} likes and rejects
      {liked && <> · counting for: {liked}</>}
      {disliked && <> · against: {disliked}</>}
    </p>
  );
}

// The reason tiles for a reject or a "can't judge", with "Other…" opening a short box for the user's own words.
function Reasons({ kind, title, options, none, busy, onPick, onCancel }: {
  kind: "reject" | "skip"; title: string; options: [string, string][]; none: string | null; busy: boolean;
  onPick: (reasons: string[], note?: string) => void; onCancel: () => void;
}) {
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
          Other…
        </button>
        {none && <button type="button" className="chip" disabled={busy} onClick={() => onPick([])}>{none}</button>}
        <button type="button" className="link" onClick={onCancel}>Keep looking at it</button>
      </div>
      {other && (
        <form className="composer" onSubmit={(e) => { e.preventDefault(); onPick(["other"], note.trim() || undefined); }}>
          <label htmlFor={`${kind}-note`} className="sr-only">In your words</label>
          <input id={`${kind}-note`} className="note" autoFocus maxLength={300} value={note} onChange={(e) => setNote(e.target.value)}
            placeholder={kind === "reject" ? "In your words, e.g. the street looks busy" : "In your words, e.g. only a floor plan"} />
          <button type="submit" className="primary" disabled={busy}>Save</button>
        </form>
      )}
    </div>
  );
}

// The photo loads from the portal only while this card is on screen; nothing is downloaded or kept (D64).
function Photo({ url, card }: { url: string | null; card: DeckCard }) {
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [url]);
  if (url && !failed) {
    return <img className="photo" src={url} alt="" referrerPolicy="no-referrer" onError={() => setFailed(true)} />;
  }
  return (
    <div className="photo placeholder" aria-hidden="true">
      <span>{card.property_type?.replace("_", " ") ?? "home"}</span>
      <span className="small">{card.synthetic ? "synthetic listing" : "no photo link saved"}</span>
    </div>
  );
}

// After 10 likes or rejects, one question as a card in the deck (D66, D75). A pattern is answered in the chat; a
// tapped reason's "yes" goes through the chat too, so the assistant makes the change; "no" and the pulse are taps.
function CheckinCard({ checkin, busy, onAnswer, onTap }: {
  checkin: Checkin; busy: boolean; onAnswer: (text: string) => void; onTap: (answer: string) => void;
}) {
  const [text, setText] = useState("");
  const step = checkin.ladder ?? "pattern";
  const options = checkin.options ?? {};
  if (step === "pulse") {
    return (
      <section className="panel deck checkin" aria-label="A quick check">
        <span className="eyebrow">Quick check</span>
        <p className="checkin-text">{checkin.reply}</p>
        <div className="chips pulse">
          {Object.entries(options).map(([code, label]) => (
            <button key={code} type="button" className="chip" disabled={busy} onClick={() => onTap(code)}>{label}</button>
          ))}
        </div>
      </section>
    );
  }
  return (
    <section className="panel deck checkin" aria-label="What the assistant noticed">
      <span className="eyebrow">What I've noticed</span>
      <p className="checkin-text">{checkin.reply}</p>
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
        <button type="submit" className="primary" disabled={busy || !text.trim()}>Send</button>
      </form>
    </section>
  );
}

// Fewer than 5 homes: code's ways to widen, each counted. A click sends the change to the assistant (D63, D61).
function Widen({ deck, busy, onAsk }: { deck: DeckData; busy: boolean; onAsk: (text: string) => void }) {
  const options = Object.values(deck.if_eased ?? {})
    .filter((o: Widening) => o.matches > deck.total_matches)
    .sort((a, b) => (a.matches >= 5) === (b.matches >= 5) ? Object.keys(a.limits).length - Object.keys(b.limits).length || b.matches - a.matches : a.matches >= 5 ? -1 : 1)
    .slice(0, 4);
  if (options.length === 0) return <p className="hint">Widening one step doesn't add any. Tell the assistant what matters least.</p>;
  return (
    <div className="chips">
      {options.map((o) => (
        <button key={JSON.stringify(o.limits)} type="button" className="chip widen-option" disabled={busy} onClick={() => onAsk(wideningMessage(o.limits))}>
          {wideningText(o.limits, deck.searched_as as Record<string, unknown>)} · <strong>{o.matches} homes</strong>
        </button>
      ))}
    </div>
  );
}
