import { useEffect, useState } from "react";
import { Checkin, Deck as DeckData, DeckCard, Widening } from "./api";
import { REJECT_REASONS, floorText, money, wideningMessage, wideningText } from "./labels";

interface Props {
  deck: DeckData | null;
  card: DeckCard | null;
  checkin: Checkin | null;
  busy: boolean;
  onSwipe: (card: DeckCard, decision: "like" | "reject", reasons: string[]) => void;
  onAnswer: (text: string) => void;
}

// One home at a time. Right to like, left to reject, with a quick reason on a reject (spec section 4).
export function Deck({ deck, card, checkin, busy, onSwipe, onAnswer }: Props) {
  const [asking, setAsking] = useState(false);

  useEffect(() => setAsking(false), [card?.listing_id]);

  useEffect(() => {
    if (!card || checkin) return;
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (target && (target.tagName === "TEXTAREA" || target.tagName === "INPUT")) return;
      if (busy) return;
      if (e.key === "ArrowRight") onSwipe(card, "like", []);
      if (e.key === "ArrowLeft") setAsking(true);
      if (e.key === "Escape") setAsking(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [card, checkin, busy, onSwipe]);

  if (!deck) return <section className="panel deck"><p className="muted">Loading the homes…</p></section>;

  if (checkin) return <CheckinCard checkin={checkin} busy={busy} onAnswer={onAnswer} />;

  if (!card) {
    return (
      <section className="panel deck">
        <h2>{deck.total_matches === 0 ? "Nothing passes every limit" : "You've seen every home that passes"}</h2>
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
          <a className="small" href={card.url} target="_blank" rel="noreferrer noopener">
            {card.synthetic ? "Synthetic listing (no real page)" : `Open on ${card.source} ↗`}
          </a>
        </div>
      </article>

      {asking ? (
        <div className="reject-why">
          <p className="hint">Why not? One tap is enough; it teaches the ranking more than the swipe.</p>
          <div className="chips">
            {REJECT_REASONS.map(([code, text]) => (
              <button key={code} type="button" className="chip" disabled={busy} onClick={() => onSwipe(card, "reject", [code])}>{text}</button>
            ))}
            <button type="button" className="chip" disabled={busy} onClick={() => onSwipe(card, "reject", [])}>No reason</button>
            <button type="button" className="link" onClick={() => setAsking(false)}>Keep looking at it</button>
          </div>
        </div>
      ) : (
        <div className="swipe-buttons">
          <button type="button" className="swipe reject" disabled={busy} onClick={() => setAsking(true)} aria-keyshortcuts="ArrowLeft">
            ← Reject
          </button>
          <span className="muted small">{deck.remaining} left · {deck.swipes.swipes} swiped</span>
          <button type="button" className="swipe like primary" disabled={busy} onClick={() => onSwipe(card, "like", [])} aria-keyshortcuts="ArrowRight">
            Like →
          </button>
        </div>
      )}
    </section>
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

// After a run of swipes: what the assistant noticed, as a card in the deck. The answer goes through the chat (D66).
function CheckinCard({ checkin, busy, onAnswer }: { checkin: Checkin; busy: boolean; onAnswer: (text: string) => void }) {
  const [text, setText] = useState("");
  return (
    <section className="panel deck checkin" aria-label="What the assistant noticed">
      <span className="eyebrow">What I've noticed</span>
      <p className="checkin-text">{checkin.reply}</p>
      <div className="chips">
        <button type="button" className="chip on" disabled={busy} onClick={() => onAnswer("Yes")}>Yes, do that</button>
        <button type="button" className="chip" disabled={busy} onClick={() => onAnswer("No, keep it as it is")}>No, keep it</button>
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
