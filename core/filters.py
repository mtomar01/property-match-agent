"""Hard-limit filtering. Always code, never the model (spec section 5).

A hard limit is a promise to the user: "never show me anything over €200k".
A model can be talked out of a promise; an if-statement can't. So the filter
lives here, in plain code with tests, and the MCP tool applies it before any
result reaches the model.

Unknown values fail closed. If a listing doesn't state its price and the user
set a budget, we can't promise it's within budget, so it's excluded from the
matches. It isn't hidden, though: the count of listings excluded only because
a value was unknown is returned, so the agent can say "4 more listings don't
state a price, want to see them?" and let the user decide.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Iterable

from core import greek
from core.models import Criteria, HardLimits, Listing

INTENT_TO_LISTING_TYPE = {"buy": "sale", "invest": "sale", "rent": "rent"}


@dataclass
class FilterOutcome:
    matches: list[Listing] = field(default_factory=list)
    excluded: Counter = field(default_factory=Counter)  # reason -> count
    excluded_unknown: Counter = field(default_factory=Counter)  # field -> count

    def report(self) -> dict:
        return {
            "excluded_by_reason": dict(self.excluded),
            "excluded_because_unknown": dict(self.excluded_unknown),
        }


def check(listing: Listing, criteria: Criteria) -> tuple[str, str] | None:
    """Return (reason, field) for the first limit the listing fails, or None if it passes.

    reason is either a broken limit, such as "over_budget", or "unknown" when the
    listing doesn't state a value the limit needs.
    """
    limits: HardLimits = criteria.hard_limits

    if listing.listing_type != INTENT_TO_LISTING_TYPE[criteria.intent]:
        return ("wrong_listing_type", "listing_type")

    if criteria.areas:
        if listing.area is None:
            return ("unknown", "area")
        if listing.area not in criteria.areas:
            return ("wrong_area", "area")

    if limits.max_price_eur is not None or limits.min_price_eur is not None:
        if listing.price_eur is None:
            return ("unknown", "price_eur")
        if limits.max_price_eur is not None and listing.price_eur > limits.max_price_eur:
            return ("over_budget", "price_eur")
        if limits.min_price_eur is not None and listing.price_eur < limits.min_price_eur:
            return ("under_min_price", "price_eur")

    if limits.min_size_m2 is not None or limits.max_size_m2 is not None:
        if listing.size_m2 is None:
            return ("unknown", "size_m2")
        if limits.min_size_m2 is not None and listing.size_m2 < limits.min_size_m2:
            return ("too_small", "size_m2")
        if limits.max_size_m2 is not None and listing.size_m2 > limits.max_size_m2:
            return ("too_big", "size_m2")

    if limits.min_bedrooms is not None or limits.max_bedrooms is not None:
        if listing.bedrooms is None:
            return ("unknown", "bedrooms")
        if limits.min_bedrooms is not None and listing.bedrooms < limits.min_bedrooms:
            return ("too_few_bedrooms", "bedrooms")
        if limits.max_bedrooms is not None and listing.bedrooms > limits.max_bedrooms:
            return ("too_many_bedrooms", "bedrooms")

    if limits.property_types:
        if listing.property_type is None:
            return ("unknown", "property_type")
        if listing.property_type not in limits.property_types:
            return ("wrong_type", "property_type")

    if limits.exclude_floors:
        if listing.floor.floor_class is None:
            return ("unknown", "floor")
        if listing.floor.floor_class in limits.exclude_floors:
            return ("excluded_floor", "floor")

    if limits.min_year_built is not None:
        if listing.year_built is None:
            return ("unknown", "year_built")
        if listing.year_built < limits.min_year_built:
            return ("too_old", "year_built")

    if limits.max_price_per_m2 is not None:
        if listing.price_per_m2 is None:
            return ("unknown", "price_per_m2")
        if listing.price_per_m2 > limits.max_price_per_m2:
            return ("over_price_per_m2", "price_per_m2")

    if limits.max_floor_without_lift is not None and listing.lift is not True:
        # Stairs only matter without a lift. A floor the listing doesn't state, or a ρετιρέ with no number,
        # can't be promised to be low enough, so it fails closed like any unknown (D8, D73).
        level = greek.floor_level(listing.floor.floor_class)
        if level is None:
            return ("unknown", "floor")
        if level > limits.max_floor_without_lift:
            return ("unknown", "lift") if listing.lift is None else ("stairs_without_lift", "floor")

    if limits.exclude_conditions:
        if listing.condition is None:
            return ("unknown", "condition")
        if listing.condition in limits.exclude_conditions:
            return ("excluded_condition", "condition")

    return None


def apply_hard_limits(listings: Iterable[Listing], criteria: Criteria) -> FilterOutcome:
    outcome = FilterOutcome()
    for listing in listings:
        failure = check(listing, criteria)
        if failure is None:
            outcome.matches.append(listing)
            continue
        reason, field_name = failure
        outcome.excluded[reason] += 1
        if reason == "unknown":
            outcome.excluded_unknown[field_name] += 1
    return outcome
