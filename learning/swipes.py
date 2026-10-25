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

from core import pii
from core.models import NOTE_MAX, Swipe

ROOT = Path(__file__).resolve().parents[1]
SWIPES_DIR = ROOT / "data" / "private" / "swipes"
DAILY_CAP: int | None = None  # cards a user may swipe a day in the final version; None means endless (D66)


class SwipeStore:
    def __init__(self, user_id: str, directory: Path = SWIPES_DIR, search: str | None = None):
        self.user_id = user_id
        # one log per search (D94): me.20261025T193000.jsonl; a store without a search id is the old single log
        self.stem = f"{user_id}.{search}" if search else user_id
        self.path = directory / f"{self.stem}.jsonl"
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
               explore_card: bool = False, ts: datetime | None = None, note: str | None = None) -> Swipe:
        if self.swiped_today() >= (DAILY_CAP or float("inf")):
            raise ValueError(f"the daily cap of {DAILY_CAP} swipes is reached; come back tomorrow")
        note = (pii.scrub(" ".join(note.split()))[:NOTE_MAX] or None) if note else None
        swipe = Swipe(user_id=self.user_id, listing_id=listing_id, decision=decision, reasons=reasons or [], note=note,
                      deck_position=deck_position, explore_card=explore_card, ts=ts or datetime.now(timezone.utc))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(swipe.model_dump_json(exclude_none=True) + "\n")
        self.load().append(swipe)
        return swipe

    @property
    def pulse_path(self) -> Path:
        return self.path.with_name(f"{self.stem}.pulse.jsonl")

    def record_pulse(self, answer: str, at: int) -> None:
        """A three-tap pulse answer (D75): a second measure beside the like rate, counts only."""
        if answer not in ("spot_on", "mixed", "not_for_me"):
            raise ValueError(f"{answer!r} isn't a pulse answer")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.pulse_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"answer": answer, "after_verdicts": at, "ts": datetime.now(timezone.utc).isoformat(timespec="seconds")}) + "\n")

    def pulse(self) -> dict[str, int]:
        if not self.pulse_path.exists():
            return {}
        rows = [json.loads(l) for l in self.pulse_path.read_text(encoding="utf-8").split("\n") if l.strip()]
        return dict(Counter(r["answer"] for r in rows))

    def archive(self) -> Path | None:
        """A new search starts clean (Mike, D75): the log moves to archive/ rather than being deleted, so the
        learned ranking can still read what was said before (too dark, needs work) across searches."""
        if not self.path.exists() and not self.pulse_path.exists():
            self._swipes = []
            return None
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        folder = self.path.parent / "archive"
        folder.mkdir(parents=True, exist_ok=True)
        moved = None
        if self.path.exists():
            moved = folder / f"{self.stem}_{stamp}.jsonl"
            self.path.rename(moved)
        if self.pulse_path.exists():
            self.pulse_path.rename(folder / f"{self.stem}_{stamp}.pulse.jsonl")
        self._swipes = []
        return moved

    def archived(self) -> list[Swipe]:
        """Swipes from earlier searches, oldest first, for the learning eval (D76). The deck learns from this search only."""
        folder = self.path.parent / "archive"
        out: list[Swipe] = []
        for path in sorted(folder.glob(f"{self.stem}_*.jsonl")) if folder.exists() else []:
            if path.name.endswith(".pulse.jsonl"):
                continue
            out += [Swipe.model_validate_json(l) for l in path.read_text(encoding="utf-8").split("\n") if l.strip()]
        return out

    def undo(self) -> Swipe | None:
        """Take back the last decision (the back button, D71): it leaves the log as if it never happened."""
        swipes = self.load()
        if not swipes:
            return None
        last = swipes.pop()
        self.path.write_text("".join(s.model_dump_json(exclude_none=True) + "\n" for s in swipes), encoding="utf-8")
        return last

    def verdicts(self) -> list[Swipe]:
        """Likes and rejects: what the like rate, the check-ins and the learning read."""
        return [s for s in self.load() if s.verdict]

    def swiped_ids(self) -> set[str]:
        """Homes with a verdict: they never come back in the deck."""
        return {s.listing_id for s in self.verdicts()}

    def skipped_ids(self) -> list[str]:
        """Homes skipped and not decided since, oldest first: they come back at the end of the deck."""
        decided, out = self.swiped_ids(), []
        for s in self.load():
            if s.decision == "skip" and s.listing_id not in decided and s.listing_id not in out:
                out.append(s.listing_id)
        return out

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
        """Counts only: no listing ids, so the numbers can be shared. Skips are counted apart, never in the like rate."""
        everything = self.load()
        swipes = [s for s in everything if s.verdict]
        likes = sum(1 for s in swipes if s.decision == "like")
        explore = [s for s in swipes if s.explore_card]
        top = [s for s in swipes if not s.explore_card]
        reasons = Counter(r for s in swipes for r in s.reasons)
        skips = [s for s in everything if s.decision == "skip"]
        days = {s.ts.date().isoformat() for s in everything}
        return {
            "swipes": len(swipes), "likes": likes, "rejects": len(swipes) - likes,
            "like_rate": round(likes / len(swipes), 3) if swipes else None,
            "explore_cards": len(explore),
            "like_rate_top": round(sum(1 for s in top if s.decision == "like") / len(top), 3) if top else None,
            "like_rate_explore": round(sum(1 for s in explore if s.decision == "like") / len(explore), 3) if explore else None,
            "reject_reasons": dict(reasons.most_common()),
            "skips": len(skips), "cant_judge": sum(1 for s in skips if s.reasons),
            "cant_judge_reasons": dict(Counter(r for s in skips for r in s.reasons).most_common()),
            "notes": sum(1 for s in everything if s.note),
            "pulse": self.pulse(),
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
