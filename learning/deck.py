"""The swipe deck: the homes that pass the card, best first, with one explore card in five (spec sections 4 and 10).

Code builds the whole deck. The hard limits are filtered in code as ever,
the order is the v1 rule score blended with what the user's own likes and
rejects teach (D76), and a card the user has already swiped never comes back. Every fifth card comes from outside the predicted top,
so the deck keeps showing the user things the ranking would bury and the
check-ins (learning/patterns.py) get evidence on both sides. Explore cards
are marked, so the swipe log says which cards were the ranking's picks.
"""

from __future__ import annotations

import random
from datetime import date

from core.filters import apply_hard_limits
from core.models import Criteria, Listing
from core.reasons import why_this_one
from learning.area_stats import AreaStats, market_lines
from learning.learned import Learner
from ranking.rules import score

EXPLORE_EVERY = 5  # one card in five comes from outside the top (spec section 10)
TOP_SHARE = 0.5  # "the top": the better half of what's left; explore cards come from the other half


def ranked_matches(listings: list[Listing], criteria: Criteria, learner: Learner | None = None,
                   today: date | None = None) -> list[Listing]:
    """The homes that pass the hard limits, best first: by the rule score, or by the blend once swipes teach (D76)."""
    matches = apply_hard_limits(listings, criteria).matches
    if learner is None:
        return sorted(matches, key=lambda l: (-score(l, criteria.preferences), l.price_per_m2 or 10**9, l.listing_id))
    return sorted(matches, key=lambda l: (-learner.blended(l, today), l.price_per_m2 or 10**9, l.listing_id))


def order(unswiped: list[Listing], seed: int) -> list[tuple[Listing, bool]]:
    """The deck order: ranked cards, with an explore card from the lower half in every fifth slot.

    Once the top half is used up, the rest follow in ranked order, unflagged:
    an explore card is a pick from outside the top, not whatever is left.
    """
    cut = max(1, round(len(unswiped) * TOP_SHARE))
    top, rest = unswiped[:cut], unswiped[cut:]
    picks = list(rest)
    random.Random(seed).shuffle(picks)
    out: list[tuple[Listing, bool]] = []
    used: set[str] = set()
    while len(out) < len(unswiped):
        if (len(out) + 1) % EXPLORE_EVERY == 0 and top:
            pick = next((l for l in picks if l.listing_id not in used), None)
            if pick is not None:
                out.append((pick, True))
                used.add(pick.listing_id)
                continue
        source = top if top else [l for l in rest if l.listing_id not in used]
        if not source:
            break
        listing = source.pop(0)
        out.append((listing, False))
        used.add(listing.listing_id)
    return out


def card(listing: Listing, criteria: Criteria, stats: AreaStats, position: int, explore: bool = False,
         skipped: bool = False, today: date | None = None, learner: Learner | None = None) -> dict:
    """One swipe card: the listing's summary, its photo link, its two reasons, its market lines and its place in the deck."""
    item = listing.summary()
    item.update(photo_url=listing.photo_urls[0] if listing.photo_urls else None,
                reasons=why_this_one(listing, criteria, {}, today),
                market=market_lines(listing, stats, today),
                preference_score=round(score(listing, criteria.preferences), 3),
                learned_score=round(learner.probability(listing, today), 3) if learner else None,
                explore_card=explore, skipped_before=skipped, deck_position=position)
    return item


def build(listings: list[Listing], criteria: Criteria, swiped_ids: set[str], start_position: int = 0,
          limit: int = 10, seed: int = 0, today: date | None = None, skipped_ids: list[str] | tuple = (),
          learner: Learner | None = None) -> dict:
    """The next cards for this user. Homes with a verdict never come back; skipped ones come back last (D71)."""
    matches = ranked_matches(listings, criteria, learner, today)
    skipped = set(skipped_ids)
    fresh = [l for l in matches if l.listing_id not in swiped_ids and l.listing_id not in skipped]
    again = [l for l in matches if l.listing_id in skipped and l.listing_id not in swiped_ids]
    stats = AreaStats.build(listings)
    queue = [(l, explore, False) for l, explore in order(fresh, seed)] + [(l, False, True) for l in again]
    cards = [card(l, criteria, stats, start_position + i, explore, was_skipped, today, learner)
             for i, (l, explore, was_skipped) in enumerate(queue[:limit])]
    return {"cards": cards, "total_matches": len(matches), "remaining": len(fresh) + len(again),
            "skipped_waiting": len(again), "swiped_of_these": len(matches) - len(fresh) - len(again),
            "learning": learner.summary() if learner else None}
