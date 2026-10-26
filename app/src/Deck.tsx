import { useEffect, useState } from "react";
import { Checkin as CheckinData, Deck as DeckData, DeckCard, Decision, Widening } from "./api";
import { Checkin } from "./Checkin";
import { HomeCard } from "./HomeCard";
import { useLabels, wideningMessage, wideningText } from "./labels";
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
  const L = useLabels();
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

  if (!deck) return <section className="panel deck-note"><p className="muted">{L.loadingHomes}</p></section>;

  if (!card) {
    return (
      <section className="panel deck-note">
        <h2>{deck.total_matches === 0 ? L.nothingPasses : L.seenAll}</h2>
        {canUndo && <button type="button" className="link" disabled={busy} onClick={onUndo}>{L.backToLast}</button>}
        <p className="muted">
          {L.passLine(deck.total_matches)} {deck.if_eased ? L.widenHint : L.tellWhat}
        </p>
        {deck.if_eased && <Widen deck={deck} busy={busy} onAsk={onAnswer} />}
        {checkin && <Checkin checkin={checkin} busy={busy} onAnswer={onAnswer} onTap={onTap} />}
      </section>
    );
  }

  return (
    <section className="deck" aria-label={L.swipeDeck}>
      <HomeCard card={card} />
      {checkin ? (
        <Checkin checkin={checkin} busy={busy} onAnswer={onAnswer} onTap={onTap} />
      ) : asking === "reject" ? (
        <ReasonChips
          kind="reject" busy={busy} title={L.whyNot}
          options={L.rejectReasons} none={L.noReason}
          onPick={(reasons, note) => onSwipe(card, "reject", reasons, note)} onCancel={() => setAsking(null)}
        />
      ) : asking === "skip" ? (
        <ReasonChips
          kind="skip" busy={busy} title={L.whatStops}
          options={L.cantJudgeReasons} none={null}
          onPick={(reasons, note) => onSwipe(card, "skip", reasons, note)} onCancel={() => setAsking(null)}
        />
      ) : (
        <SwipeActions
          busy={busy} canUndo={canUndo} remaining={deck.remaining} swiped={deck.swipes.swipes}
          onReject={() => setAsking("reject")} onLike={() => onSwipe(card, "like", [])} onSkip={() => onSwipe(card, "skip", [])}
          onPrevious={onUndo} onCantJudge={() => setAsking("skip")}
        />
      )}
    </section>
  );
}

// Fewer than 5 homes: code's ways to widen, each counted. A click sends the change to the assistant (D63, D61).
function Widen({ deck, busy, onAsk }: { deck: DeckData; busy: boolean; onAsk: (text: string) => void }) {
  const L = useLabels();
  const options = Object.values(deck.if_eased ?? {})
    .filter((o: Widening) => o.matches > deck.total_matches)
    .sort((a, b) => (a.matches >= 5) === (b.matches >= 5) ? Object.keys(a.limits).length - Object.keys(b.limits).length || b.matches - a.matches : a.matches >= 5 ? -1 : 1)
    .slice(0, 4);
  if (options.length === 0) return <p className="hint">{L.widenNone}</p>;
  return (
    <div className="chips">
      {options.map((o) => (
        <button key={JSON.stringify(o.limits)} type="button" className="chip widen-option" disabled={busy} onClick={() => onAsk(wideningMessage(o.limits))}>
          {wideningText(o.limits, deck.searched_as as Record<string, unknown>, L)} · <strong>{L.homesCount(o.matches)}</strong>
        </button>
      ))}
    </div>
  );
}
