"""An independent hard-limit checker for the search safety eval.

This deliberately does NOT import core/filters.py. If the eval reused the
filter it's testing, a bug in the filter would also be a bug in the check and
the eval would pass anyway: the work would be grading itself. So the rules are
written a second time here, as plainly as possible, working on the result
dictionaries the MCP tool returns rather than on the Listing model.

A returned listing with an unknown value under a hard limit counts as a break:
the user asked for a promise the system can't keep for that listing.
"""

from __future__ import annotations

import unicodedata

_AREAS = {
    "egaleo": "Egaleo", "aigaleo": "Egaleo", "αιγαλεω": "Egaleo",
    "peristeri": "Peristeri", "περιστερι": "Peristeri",
    "chaidari": "Chaidari", "haidari": "Chaidari", "χαιδαρι": "Chaidari",
    "pagrati": "Pagrati", "pangrati": "Pagrati", "παγκρατι": "Pagrati",
    "kypseli": "Kypseli", "kipseli": "Kypseli", "κυψελη": "Kypseli",
}
_FLOORS = {"υπογειο": "basement", "ημιυπογειο": "semi_basement", "ισογειο": "ground"}
_LISTING_TYPE = {"buy": "sale", "invest": "sale", "rent": "rent"}
# Storeys to climb, written out again here rather than imported (raised ground and mezzanine are a few steps up).
_STOREY = {"basement": -1, "semi_basement": -0.5, "ground": 0, "raised_ground": 0.25, "mezzanine": 0.5}


def _plain(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def _area(name: str) -> str:
    return _AREAS.get(_plain(name), name)


def _floor(name: str) -> str:
    return _FLOORS.get(_plain(name), name)


def breaks(result: dict, criteria: dict) -> list[str]:
    """Every hard limit this returned listing breaks (empty list means it's fine)."""
    limits = criteria.get("hard_limits", {}) or {}
    found: list[str] = []

    wanted_type = _LISTING_TYPE[criteria.get("intent", "buy")]
    if result.get("listing_type") != wanted_type:
        found.append(f"listing_type {result.get('listing_type')} is not {wanted_type}")

    areas = {_area(a) for a in criteria.get("areas", []) or []}
    if areas and result.get("area") not in areas:
        found.append(f"area {result.get('area')} not in {sorted(areas)}")

    price = result.get("price_eur")
    if limits.get("max_price_eur") is not None and (price is None or price > limits["max_price_eur"]):
        found.append(f"price {price} breaks max {limits['max_price_eur']}")
    if limits.get("min_price_eur") is not None and (price is None or price < limits["min_price_eur"]):
        found.append(f"price {price} breaks min {limits['min_price_eur']}")

    size = result.get("size_m2")
    if limits.get("min_size_m2") is not None and (size is None or size < limits["min_size_m2"]):
        found.append(f"size {size} breaks min {limits['min_size_m2']}")
    if limits.get("max_size_m2") is not None and (size is None or size > limits["max_size_m2"]):
        found.append(f"size {size} breaks max {limits['max_size_m2']}")

    bedrooms = result.get("bedrooms")
    if limits.get("min_bedrooms") is not None and (bedrooms is None or bedrooms < limits["min_bedrooms"]):
        found.append(f"bedrooms {bedrooms} breaks min {limits['min_bedrooms']}")
    if limits.get("max_bedrooms") is not None and (bedrooms is None or bedrooms > limits["max_bedrooms"]):
        found.append(f"bedrooms {bedrooms} breaks max {limits['max_bedrooms']}")

    types = limits.get("property_types") or []
    if types and result.get("property_type") not in types:
        found.append(f"type {result.get('property_type')} not in {types}")

    excluded = {_floor(f) for f in limits.get("exclude_floors") or []}
    if excluded and (result.get("floor") is None or result.get("floor") in excluded):
        found.append(f"floor {result.get('floor')} is excluded or unknown")

    year = result.get("year_built")
    if limits.get("min_year_built") is not None and (year is None or year < limits["min_year_built"]):
        found.append(f"year built {year} breaks min {limits['min_year_built']}")

    per_m2 = result.get("price_per_m2")
    if limits.get("max_price_per_m2") is not None and (per_m2 is None or per_m2 > limits["max_price_per_m2"]):
        found.append(f"price per m2 {per_m2} breaks max {limits['max_price_per_m2']}")

    climb = limits.get("max_floor_without_lift")
    if climb is not None and result.get("lift") is not True:
        storey = _STOREY.get(result.get("floor"), None) if not str(result.get("floor") or "").isdigit() else int(result["floor"])
        if storey is None or storey > climb:
            found.append(f"floor {result.get('floor')} without a known lift breaks {climb} floors of stairs")

    banned = set(limits.get("exclude_conditions") or [])
    if banned and (result.get("condition") is None or result.get("condition") in banned):
        found.append(f"condition {result.get('condition')} is excluded or unknown")

    return found
