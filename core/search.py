"""Search: filter on hard limits in code, then rank by preferences.

This is the function behind the search_listings MCP tool. It's kept separate
from the server so tests and the future agent loop can call it directly too.
"""

from __future__ import annotations

from adapters.base import Adapter
from core.filters import apply_hard_limits
from core.models import Criteria
from ranking.rules import score

MAX_LIMIT = 50


def search(adapter: Adapter, criteria: Criteria, sources: list[str] | None = None, limit: int = 20) -> dict:
    limit = max(1, min(limit, MAX_LIMIT))
    pool = [l for l in adapter.listings() if not sources or l.source in sources]
    outcome = apply_hard_limits(pool, criteria)

    ranked = sorted(
        outcome.matches,
        key=lambda l: (-score(l, criteria.preferences), l.price_per_m2 or 10**9, l.listing_id),
    )
    results = []
    for listing in ranked[:limit]:
        item = listing.summary()
        item["preference_score"] = round(score(listing, criteria.preferences), 3)
        results.append(item)

    return {
        "total_matches": len(outcome.matches),
        "returned": len(results),
        "results": results,
        **outcome.report(),
        "searched": len(pool),
    }
