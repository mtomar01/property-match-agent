import { Learning } from "./api";
import { PreviousIcon, SkipIcon } from "./Icons";
import { useLabels } from "./labels";

interface Props {
  busy: boolean;
  canUndo: boolean;
  remaining: number;
  swiped: number;
  learning: Learning | null;
  onReject: () => void;
  onLike: () => void;
  onSkip: () => void;
  onPrevious: () => void;
  onCantJudge: () => void;
}

// Four controls in one row (design system, SwipeActions; D88): previous on the far left, Reject and Like together
// in the middle, skip on the far right. The two verdicts are words and differ in fill; the two icons are the only
// actions that are not words. Below, "Can't judge this one?" and the counts; then the learning line (D76).
export function SwipeActions({ busy, canUndo, remaining, swiped, learning, onReject, onLike, onSkip, onPrevious, onCantJudge }: Props) {
  const L = useLabels();
  return (
    <div className="actions">
      <div className="swipe-buttons">
        <button type="button" className="icon-btn ring" disabled={busy || !canUndo} onClick={onPrevious} aria-label={L.previous}
          title={L.previousTitle} aria-keyshortcuts="Backspace"><PreviousIcon /></button>
        <button type="button" className="swipe reject" disabled={busy} onClick={onReject} aria-keyshortcuts="ArrowLeft" title={L.rejectTitle}>
          {L.reject}
        </button>
        <button type="button" className="swipe like primary" disabled={busy} onClick={onLike} aria-keyshortcuts="ArrowRight" title={L.likeTitle}>
          {L.like}
        </button>
        <button type="button" className="icon-btn ring" disabled={busy} onClick={onSkip} aria-label={L.skip}
          title={L.skipTitle} aria-keyshortcuts="ArrowDown"><SkipIcon /></button>
      </div>
      <div className="under-buttons">
        <button type="button" className="link small" disabled={busy} onClick={onCantJudge}>{L.cantJudge}</button>
        <span className="muted small tabular">{L.leftSwiped(remaining, swiped)}</span>
      </div>
      <LearningLine learning={learning} />
    </div>
  );
}

// How the order is decided (D76): the chat's wishes at first, then more and more the user's own likes and rejects.
// The leanings are in lime-deep; the line is read, never tapped.
export function LearningLine({ learning }: { learning: Learning | null }) {
  const L = useLabels();
  if (!learning) {
    return <p className="muted small learning">{L.learningBefore}</p>;
  }
  const words = (direction: "for" | "against") =>
    learning.leans.filter((l) => l.direction === direction).map((l) => l.words).join(", ");
  const liked = words("for"), disliked = words("against");
  return (
    <p className="muted small learning">
      {L.learningShare(Math.round(learning.share * 100), learning.verdicts)}
      {liked && <> · {L.countingFor}: <b className="lean">{liked}</b></>}
      {disliked && <> · {L.against}: <b className="lean">{disliked}</b></>}
    </p>
  );
}
