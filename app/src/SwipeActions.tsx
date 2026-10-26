import { PreviousIcon, SkipIcon } from "./Icons";
import { useLabels } from "./labels";

interface Props {
  busy: boolean;
  canUndo: boolean;
  remaining: number;
  swiped: number;
  onReject: () => void;
  onLike: () => void;
  onSkip: () => void;
  onPrevious: () => void;
  onCantJudge: () => void;
}

// Four controls in one row (design system, SwipeActions; D88): previous on the far left, Reject and Like together
// in the middle, skip on the far right. The two verdicts are words and differ in fill; the two icons are the only
// actions that are not words. Below, "Can't judge this one?" and the counts. The learning line moved to the bar's
// fold-out (D97): it explains, it does not act, so it sits with the other explanations.
export function SwipeActions({ busy, canUndo, remaining, swiped, onReject, onLike, onSkip, onPrevious, onCantJudge }: Props) {
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
    </div>
  );
}
