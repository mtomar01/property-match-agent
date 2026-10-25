import { useEffect, useState } from "react";
import { Checkin as CheckinData, Deck as DeckData, DeckCard, Decision, Widening } from "./api";
import { Checkin } from "./Checkin";
import { HomeCard } from "./HomeCard";
import { CANT_JUDGE_REASONS, REJECT_REASONS, wideningMessage, wideningText } from "./labels";
import { ReasonChips } from "./ReasonChips";
import { SwipeActions } from "./SwipeActions";

interface Props {
  deck: DeckData | null;
  card: DeckCard | null;
  checkin: CheckinData | null;
  busy: boolean;
  canUndo: boolean;
  onSwipe: (card: DeckCard, decision: Decision, reasons: string[], note?: string) => void;
  onUndo: () => void;
  onAnswer: (text: string) => void;
  onTap: (answer: string) => void;
}

// One home at a time (spec section 4, D71): the card, then the four actions pinned under it; a reject or a
// "can't judge" asks why in place of the actions, and a check-in takes their place too, over the card.
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

  if (!deck) return <section className="panel deck-note"><p className="muted">Loading the homes…</p></section>;

  if (!card) {
    return (
      <section className="panel deck-note">
        <h2>{deck.total_matches === 0 ? "Nothing passes every limit" : "You've seen every home that passes"}</h2>
        {canUndo && <button type="button" className="link" disabled={busy} onClick={onUndo}>Back to the last one</button>}
        <p className="muted">
          {deck.total_matches} {deck.total_matches === 1 ? "home passes" : "homes pass"} the limits on the bar.
          {deck.if_eased ? " Code counted a few ways to widen the search; pick one and the assistant will make the change." : " Tell the assistant what to change."}
        </p>
        {deck.if_eased && <Widen deck={deck} busy={busy} onAsk={onAnswer} />}
        {checkin && <Checkin checkin={checkin} busy={busy} onAnswer={onAnswer} onTap={onTap} />}
      </section>
    );
  }

  return (
    <section className="deck" aria-label="Swipe deck">
      <HomeCard card={card} />
      {checkin ? (
        <Checkin checkin={checkin} busy={busy} onAnswer={onAnswer} onTap={onTap} />
      ) : asking === "reject" ? (
        <ReasonChips
          kind="reject" busy={busy} title="Why not? One tap is enough; it teaches the ranking more than the swipe."
          options={REJECT_REASONS} none="No reason"
          onPick={(reasons, note) => onSwipe(card, "reject", reasons, note)} onCancel={() => setAsking(null)}
        />
      ) : asking === "skip" ? (
        <ReasonChips
          kind="skip" busy={busy} title="What stops you deciding? This one won't count as a like or a reject, and it comes back later."
          options={CANT_JUDGE_REASONS} none={null}
          onPick={(reasons, note) => onSwipe(card, "skip", reasons, note)} onCancel={() => setAsking(null)}
        />
      ) : (
        <SwipeActions
          busy={busy} canUndo={canUndo} remaining={deck.remaining} swiped={deck.swipes.swipes} learning={deck.learning}
          onReject={() => setAsking("reject")} onLike={() => onSwipe(card, "like", [])} onSkip={() => onSwipe(card, "skip", [])}
          onPrevious={onUndo} onCantJudge={() => setAsking("skip")}
        />
      )}
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
