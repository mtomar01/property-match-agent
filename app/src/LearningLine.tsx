import { Learning } from "./api";
import { useLabels } from "./labels";

// How the order is decided (D76): the chat's wishes at first, then more and more the user's own likes and rejects.
// The leanings are in lime-deep; the line is read, never tapped. Since D97 it lives behind the bar's "details".
export function LearningLine({ learning, orderBy }: { learning: Learning | null; orderBy?: string | null }) {
  const L = useLabels();
  if (orderBy) {  // an order the user asked for is strict (D98): the taste only breaks ties
    return <p className="muted small learning">{L.orderAsked(L.orders[orderBy] ?? orderBy)}</p>;
  }
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
