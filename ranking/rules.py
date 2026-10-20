"""v1 rule scoring: a weighted sum of preference matches (spec section 10).

Kept deliberately simple and transparent, because v1 only needs a sensible
order and v2 replaces it with a learned model. Each preference scores 1 if
met, 0 if not, and 0.5 if the listing doesn't say: unknown is neither
rewarded nor punished. The total is divided by the sum of weights, so a
score always sits between 0 and 1.
"""

from __future__ import annotations

from core import greek
from core.models import Listing, Preference

# energy_class preferences compare positions on this scale: G is 0, A+ is 8.
ENERGY_ORDER = ["G", "F", "E", "D", "C", "B", "B+", "A", "A+"]


def _value(listing: Listing, feature: str):
    if feature == "floor_level":
        if listing.floor.floor_class == "top":
            return 99.0  # a top floor satisfies any minimum floor
        return greek.floor_level(listing.floor.floor_class)
    if feature == "energy_class":
        value = listing.energy_class.value
        return ENERGY_ORDER.index(value) if value in ENERGY_ORDER else None
    if feature == "parking":
        return None if listing.parking is None else listing.parking != "none"
    if feature in ("dual_aspect", "corner", "whole_floor"):
        return feature in listing.flags
    return getattr(listing, feature, None)


def preference_match(listing: Listing, preference: Preference) -> float:
    value = _value(listing, preference.feature)
    if value is None:
        return 0.5
    if preference.equals is not None:
        return 1.0 if value == preference.equals else 0.0
    low, high = preference.min, preference.max
    if low is not None and value < low:
        return 0.0
    if high is not None and value > high:
        return 0.0
    return 1.0


def score(listing: Listing, preferences: list[Preference]) -> float:
    total_weight = sum(p.weight for p in preferences)
    if not total_weight:
        return 0.0
    return sum(p.weight * preference_match(listing, p) for p in preferences) / total_weight
