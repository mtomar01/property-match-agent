"""The swipe log: one line per decision, on this machine only (spec section 6, D64).

Swipes are the user's own record of taste, so they live in data/private/,
which git ignores, as JSON lines that append without rewriting. The like
rate they give is v2's finishing line (spec section 13): the share of cards
swiped right before anything is learned, which the learned ranking in v3
has to beat.

A daily cap is one constant here, off while testing (Mike, D64, D66).
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

from core.models import Swipe

ROOT = Path(__file__).resolve().parents[1]
SWIPES_DIR = ROOT / "data" / "private" / "swipes"
DAILY_CAP: int | None = None  # cards a user may swipe a day in the final version; None means endless (D66)


class SwipeStore:
    def __init__(self, user_id: str, directory: Path = SWIPES_DIR):
        self.user_id = user_id
        self.path = directory / f"{user_id}.jsonl"
        self._swipes: list[Swipe] | None = None

    def load(self) -> list[Swipe]:
        if self._swipes is None:
            self._swipes = []
            if self.path.exists():
                for line in self.path.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        self._swipes.append(Swipe.model_validate_json(line))
        return self._swipes

    def record(self, listing_id: str, decision: str, reasons: list[str] | None = None, deck_position: int = 0,
               explore_card: bool = False, ts: datetime | None = None) -> Swipe:
        if self.swiped_today() >= (DAILY_CAP or float("inf")):
            raise ValueError(f"the daily cap of {DAILY_CAP} swipes is reached; come back tomorrow")
        swipe = Swipe(user_id=self.user_id, listing_id=listing_id, decision=decision, reasons=reasons or [],
                      deck_position=deck_position, explore_card=explore_card, ts=ts or datetime.now(timezone.utc))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(swipe.model_dump_json() + "\n")
        self.load().append(swipe)
        return swipe

    def swiped_ids(self) -> set[str]:
        return {s.listing_id for s in self.load()}

    def liked_ids(self) -> list[str]:
        seen, out = set(), []
        for swipe in self.load():
            if swipe.decision == "like" and swipe.listing_id not in seen:
                seen.add(swipe.listing_id)
                out.append(swipe.listing_id)
        return out

    def swiped_today(self, today: date | None = None) -> int:
        today = today or datetime.now(timezone.utc).date()
        return sum(1 for s in self.load() if s.ts.date() == today)

    def stats(self) -> dict:
        """Counts only: no listing ids, so the numbers can be shared."""
        swipes = self.load()
        likes = sum(1 for s in swipes if s.decision == "like")
        explore = [s for s in swipes if s.explore_card]
        top = [s for s in swipes if not s.explore_card]
        reasons = Counter(r for s in swipes for r in s.reasons)
        days = {s.ts.date().isoformat() for s in swipes}
        return {
            "swipes": len(swipes), "likes": likes, "rejects": len(swipes) - likes,
            "like_rate": round(likes / len(swipes), 3) if swipes else None,
            "explore_cards": len(explore),
            "like_rate_top": round(sum(1 for s in top if s.decision == "like") / len(top), 3) if top else None,
            "like_rate_explore": round(sum(1 for s in explore if s.decision == "like") / len(explore), 3) if explore else None,
            "reject_reasons": dict(reasons.most_common()),
            "days": len(days), "first": min(days) if days else None, "last": max(days) if days else None,
        }


def report(user_id: str, directory: Path = SWIPES_DIR, out: Path | None = None) -> dict:
    """The baseline like rate for the README (counts only). Run: uv run python -m learning.swipes USER."""
    stats = SwipeStore(user_id, directory).stats()
    record = {"eval": "like_rate", "ranking": "rules (v1 weights)", "user": "one real user" if user_id != "test" else user_id,
              "ran_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), **stats}
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
    return record


if __name__ == "__main__":
    import sys

    user = sys.argv[1] if len(sys.argv) > 1 else "me"
    target = ROOT / "evals" / "results" / "v2-like-rate.json"
    print(json.dumps(report(user, out=target), ensure_ascii=False, indent=1))
    print(f"written to {target.relative_to(ROOT)} (counts only)")
