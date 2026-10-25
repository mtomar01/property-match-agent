"""Two "why this one" reasons for a swipe card, from listing fields only (spec section 4, D64).

The spec had the model write these. Code writes them instead: each reason is
a template filled with a field the listing states, so it can't invent a
feature, it costs nothing, and the explanation eval can check every reason
against the field it names. The order is fixed: the preferences the home
meets come first, strongest wish first, then market facts code can verify
(price per m² against the area's typical, a price cut, a recent renovation).

Each reason carries the feature and value it rests on, so a reader can see
the evidence and the eval can re-check it.
"""

from __future__ import annotations

import statistics
from datetime import date

from core import greek
from core.models import Criteria, Listing, Preference
from ranking.rules import ENERGY_ORDER, preference_match

MAX_REASONS = 2
RECENT_YEARS = 10  # a renovation or a build in the last ten years is worth a word on its own
TYPICAL_MARGIN = 0.05  # "under the typical price": at least 5% under the area's median per m²
TYPICAL_MIN = 5  # a typical price needs at least five listings behind it

FEATURE_WORDS = {
    "balcony": "Balcony", "lift": "Lift", "parking": "Parking", "storage": "Storage room",
    "dual_aspect": "Dual aspect", "corner": "Corner flat", "whole_floor": "Whole floor",
}
CONDITION_WORDS = {"renovated": "renovated", "new_build": "new build", "good": "in good condition",
                   "needs_work": "needs work", "unfinished": "unfinished"}


def typical_price_per_m2(listings: list[Listing]) -> dict[str, int]:
    """The median price per m² per area, from the listings that state both price and size."""
    by_area: dict[str, list[int]] = {}
    for listing in listings:
        if listing.area and listing.price_per_m2 and listing.listing_type == "sale":
            by_area.setdefault(listing.area, []).append(listing.price_per_m2)
    return {area: round(statistics.median(values)) for area, values in by_area.items() if len(values) >= TYPICAL_MIN}


def _bound_text(preference: Preference) -> str:
    low, high = preference.min, preference.max
    if preference.feature == "energy_class":
        return f"{low} or better" if low is not None else f"{high} or worse"
    if low is not None and high is not None:
        return f"{low:g} to {high:g}"
    return f"at least {low:g}" if low is not None else f"up to {high:g}"


def _preference_reason(listing: Listing, preference: Preference) -> dict | None:
    if preference_match(listing, preference) < 1.0:
        return None
    feature = preference.feature
    if feature in FEATURE_WORDS:
        if preference.equals is False:
            return {"text": f"No {FEATURE_WORDS[feature].lower()}, as you asked", "feature": feature, "value": False}
        detail = f" ({listing.parking})" if feature == "parking" and listing.parking not in (None, "none") else ""
        return {"text": f"{FEATURE_WORDS[feature]}{detail}, as you asked", "feature": feature, "value": True}
    if feature == "floor_level":
        floor = listing.floor.floor_class
        name = f"{floor}{'st' if floor == '1' else 'nd' if floor == '2' else 'rd' if floor == '3' else 'th'} floor" if floor.isdigit() \
            else floor.replace("_", " ")
        return {"text": f"{name[0].upper()}{name[1:]}, you asked for floor {_bound_text(preference)}", "feature": "floor",
                "value": floor, "level": greek.floor_level(floor)}
    if feature == "energy_class":
        return {"text": f"Energy class {listing.energy_class.value}, you asked for {_bound_text(preference)}",
                "feature": "energy_class", "value": listing.energy_class.value}
    if feature == "move_in_ready":  # worked out from the condition the listing states (D73), not a field of its own
        words = CONDITION_WORDS.get(listing.condition, listing.condition)
        if preference.equals is False:
            return {"text": f"A project: {words}, as you asked", "feature": "move_in_ready", "value": listing.condition}
        return {"text": f"Ready to move in: {words}, as you asked", "feature": "move_in_ready", "value": listing.condition}
    if feature == "price_per_m2":
        return {"text": f"€{listing.price_per_m2:,}/m², you asked for up to €{preference.max:,.0f}/m²" if preference.max is not None
                else f"€{listing.price_per_m2:,}/m², you asked for {_bound_text(preference)} per m²",
                "feature": "price_per_m2", "value": listing.price_per_m2}
    value = getattr(listing, feature)
    units = {"size_m2": " m²", "metro_walk_min": " min on foot", "price_eur": " €"}.get(feature, "")
    names = {"size_m2": "", "metro_walk_min": "Metro ", "price_eur": "", "year_built": "Built ", "renovated_year": "Renovated ",
             "bedrooms": "Bedrooms: ", "bathrooms": "Bathrooms: "}
    shown = f"{value:,}" if feature == "price_eur" else f"{value:g}" if isinstance(value, float) else str(value)
    if feature == "price_eur":
        shown = f"€{shown}"
    return {"text": f"{names.get(feature, '')}{shown}{units}, you asked for {_bound_text(preference)}", "feature": feature, "value": value}


def _fact_reasons(listing: Listing, typical: dict[str, int], today: date) -> list[dict]:
    """Notable facts about the home itself. Price per m² and time on market are market lines now (D74)."""
    facts = []
    if listing.renovated_year and listing.renovated_year >= today.year - RECENT_YEARS:
        facts.append({"text": f"Renovated in {listing.renovated_year}", "feature": "renovated_year", "value": listing.renovated_year})
    elif listing.year_built and listing.year_built >= today.year - RECENT_YEARS:
        facts.append({"text": f"Built in {listing.year_built}", "feature": "year_built", "value": listing.year_built})
    if listing.floor.floor_class == "top":
        facts.append({"text": "Top floor (ρετιρέ)", "feature": "floor", "value": "top"})
    if listing.energy_class.value in ENERGY_ORDER[-3:]:  # B+ or better
        facts.append({"text": f"Energy class {listing.energy_class.value}", "feature": "energy_class", "value": listing.energy_class.value})
    return facts


def _fallback(listing: Listing, criteria: Criteria) -> list[dict]:
    """True, plain facts for a card with no wish met and nothing remarkable: never an empty card."""
    out = []
    top = criteria.hard_limits.max_price_eur
    if listing.price_eur and top:
        out.append({"text": f"€{listing.price_eur:,}, {'within' if listing.price_eur <= top else 'over'} your €{top:,}",
                    "feature": "price_eur", "value": listing.price_eur})
    if listing.size_m2:
        out.append({"text": f"{listing.size_m2:g} m²" + (f" in {listing.sub_area}" if listing.sub_area else ""),
                    "feature": "size_m2", "value": listing.size_m2})
    return out


def why_this_one(listing: Listing, criteria: Criteria, typical: dict[str, int] | None = None,
                 today: date | None = None) -> list[dict]:
    """Up to two reasons, each resting on a field the listing states."""
    today = today or date.today()
    reasons = []
    for preference in sorted(criteria.preferences, key=lambda p: -p.weight):
        reason = _preference_reason(listing, preference)
        if reason and reason["feature"] not in {r["feature"] for r in reasons}:
            reasons.append(dict(reason, kind="preference", weight=preference.weight))
    for fact in _fact_reasons(listing, typical or {}, today):
        if fact["feature"] not in {r["feature"] for r in reasons}:
            reasons.append(dict(fact, kind="fact"))
    for fact in _fallback(listing, criteria):
        if fact["feature"] not in {r["feature"] for r in reasons}:
            reasons.append(dict(fact, kind="fallback"))
    return reasons[:MAX_REASONS]
