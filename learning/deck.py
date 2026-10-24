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
from core.models import Criteria, DuplicateCluster, Listing
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


def fold(ranked: list[Listing], duplicates: dict[str, DuplicateCluster]) -> list[Listing]:
    """One card per home (D78): of a duplicate group, the cheapest listing that passed, at the best place any of them had."""
    out, seen = [], set()
    for listing in ranked:
        group = duplicates.get(listing.listing_id)
        if group is None:
            out.append(listing)
            continue
        if group.cluster_id in seen:
            continue
        seen.add(group.cluster_id)
        members = [l for l in ranked if l.listing_id in group.listing_ids]
        out.append(min(members, key=lambda l: (l.price_eur or 10**9, ranked.index(l))))
    return out


def listed(listing: Listing, duplicates: dict[str, DuplicateCluster], by_id: dict[str, Listing]) -> dict | None:
    """"Listed 3 times, €185,000 to €199,000": the other versions of this home, as links (spec section 11)."""
    group = duplicates.get(listing.listing_id)
    if group is None:
        return None
    others = [by_id[i] for i in group.listing_ids if i != listing.listing_id and i in by_id]
    return {"times": len(group.listing_ids), "price_min": group.price_min_eur, "price_max": group.price_max_eur,
            "others": [{"listing_id": o.listing_id, "source": o.source, "url": o.url, "price_eur": o.price_eur} for o in others]}


def card(listing: Listing, criteria: Criteria, stats: AreaStats, position: int, explore: bool = False,
         skipped: bool = False, today: date | None = None, learner: Learner | None = None,
         duplicates: dict[str, DuplicateCluster] | None = None, by_id: dict[str, Listing] | None = None) -> dict:
    """One swipe card: the listing's summary, its photo link, its two reasons, its market lines and its place in the deck."""
    item = listing.summary()
    item.update(photo_url=listing.photo_urls[0] if listing.photo_urls else None,
                reasons=why_this_one(listing, criteria, {}, today),
                market=market_lines(listing, stats, today),
                listed=listed(listing, duplicates, by_id) if duplicates and by_id else None,
                preference_score=round(score(listing, criteria.preferences), 3),
                learned_score=round(learner.probability(listing, today), 3) if learner else None,
                explore_card=explore, skipped_before=skipped, deck_position=position)
    return item


def build(listings: list[Listing], criteria: Criteria, swiped_ids: set[str], start_position: int = 0,
          limit: int = 10, seed: int = 0, today: date | None = None, skipped_ids: list[str] | tuple = (),
          learner: Learner | None = None, duplicates: dict[str, DuplicateCluster] | None = None) -> dict:
    """The next cards for this user. Homes with a verdict never come back; skipped ones come back last (D71).

    With duplicates, each home shows once, and a verdict or a skip on any of its listings counts for all of them.
    """
    duplicates = duplicates or {}
    ranked = ranked_matches(listings, criteria, learner, today)
    matches = fold(ranked, duplicates)

    def group(ids) -> set[str]:  # a listing's whole duplicate group
        return {m for i in ids for m in (duplicates[i].listing_ids if i in duplicates else [i])}

    swiped, skipped = group(swiped_ids), group(skipped_ids) - group(swiped_ids)
    fresh = [l for l in matches if l.listing_id not in swiped and l.listing_id not in skipped]
    again = [l for l in matches if l.listing_id in skipped]
    stats = AreaStats.build(listings)
    by_id = {l.listing_id: l for l in listings} if duplicates else None
    queue = [(l, explore, False) for l, explore in order(fresh, seed)] + [(l, False, True) for l in again]
    cards = [card(l, criteria, stats, start_position + i, explore, was_skipped, today, learner, duplicates, by_id)
             for i, (l, explore, was_skipped) in enumerate(queue[:limit])]
    return {"cards": cards, "total_matches": len(matches), "remaining": len(fresh) + len(again),
            "skipped_waiting": len(again), "swiped_of_these": len(matches) - len(fresh) - len(again),
            "listings_folded": len(ranked) - len(matches), "learning": learner.summary() if learner else None}
