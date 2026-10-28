"""Area statistics: what's typical where, worked out by code from the listings themselves (spec section 13, D74).

Three levels of "typical price per m²", from the most specific to the most general:

- similar homes: the same area, bedroom band and age band ("2 bedrooms, built before 1980, in Kypseli");
- the neighbourhood ("Λιούμη");
- the area ("Egaleo").

A card compares a home with the most specific level that has enough homes behind it, and says which level
and how many, so a figure from 8 homes is never presented like one from 200. Time on market comes from the
date the ad was published, which the listing page states (D70); a listing without it shows no such line.

Medians, not means: one €900,000 penthouse shouldn't move the typical price for everyone else.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import date

from core.models import Listing

MIN_SIMILAR = 8  # homes behind a "similar homes" figure
MIN_NEIGHBOURHOOD = 10
MIN_AREA = 5
AGE_BANDS = ((1980, "built before 1980"), (2005, "built 1980 to 2004"), (10_000, "built 2005 or later"))


def bedroom_band(bedrooms: int | None) -> str | None:
    if bedrooms is None:
        return None
    return "studio or 1 bedroom" if bedrooms <= 1 else "2 bedrooms" if bedrooms == 2 else "3 or more bedrooms"


def age_band(year_built: int | None) -> str | None:
    if year_built is None:
        return None
    return next(label for edge, label in AGE_BANDS if year_built < edge)


def similar_key(listing: Listing) -> tuple | None:
    beds, age = bedroom_band(listing.bedrooms), age_band(listing.year_built)
    if not listing.area or beds is None or age is None:
        return None
    return (listing.area, beds, age)


def days_on_market(listing: Listing) -> int | None:
    published = getattr(listing, "published", None)
    if published is None:
        return None
    return max(0, (listing.last_seen - published).days)


@dataclass
class Typical:
    per_m2: int
    level: str  # "similar", "neighbourhood" or "area"
    label: str  # "similar homes in Kypseli (2 bedrooms, built before 1980)"
    homes: int


@dataclass
class AreaStats:
    """Built once per dataset; every lookup is a dictionary read."""

    similar: dict[tuple, list[int]] = field(default_factory=dict)
    neighbourhood: dict[tuple, list[int]] = field(default_factory=dict)
    area: dict[str, list[int]] = field(default_factory=dict)
    days: dict[str, list[int]] = field(default_factory=dict)
    homes: dict[str, int] = field(default_factory=dict)
    kind: str = "sale"  # sale or rent: a rent per m² is only ever compared with other rents (D104)

    @classmethod
    def build(cls, listings: list[Listing], kind: str = "sale") -> "AreaStats":
        stats = cls(kind=kind)
        for l in listings:
            if l.listing_type != kind or not l.area:
                continue
            stats.homes[l.area] = stats.homes.get(l.area, 0) + 1
            days = days_on_market(l)
            if days is not None:
                stats.days.setdefault(l.area, []).append(days)
            if not l.price_per_m2:
                continue
            stats.area.setdefault(l.area, []).append(l.price_per_m2)
            if l.sub_area:
                stats.neighbourhood.setdefault((l.area, l.sub_area), []).append(l.price_per_m2)
            key = similar_key(l)
            if key:
                stats.similar.setdefault(key, []).append(l.price_per_m2)
        return stats

    def typical(self, listing: Listing) -> Typical | None:
        """The most specific typical €/m² with enough homes behind it, or None."""
        if listing.listing_type != self.kind:
            return None
        key = similar_key(listing)
        if key and len(self.similar.get(key, [])) >= MIN_SIMILAR:
            values = self.similar[key]
            return Typical(round(statistics.median(values)), "similar",
                           f"similar homes in {key[0]} ({key[1]}, {key[2]})", len(values))
        hood = (listing.area, listing.sub_area)
        if listing.sub_area and len(self.neighbourhood.get(hood, [])) >= MIN_NEIGHBOURHOOD:
            values = self.neighbourhood[hood]
            return Typical(round(statistics.median(values)), "neighbourhood", listing.sub_area, len(values))
        values = self.area.get(listing.area or "", [])
        if len(values) >= MIN_AREA:
            return Typical(round(statistics.median(values)), "area", listing.area, len(values))
        return None

    def summary(self) -> dict:
        """Per area: homes for sale, typical €/m², median days on market, and the neighbourhoods with enough homes."""
        out = {}
        for area, count in sorted(self.homes.items()):
            per_m2 = self.area.get(area, [])
            days = self.days.get(area, [])
            hoods = {hood: {"homes": len(v), "typical_per_m2": round(statistics.median(v))}
                     for (a, hood), v in sorted(self.neighbourhood.items()) if a == area and len(v) >= MIN_NEIGHBOURHOOD}
            out[area] = {"homes": count,
                         "typical_per_m2": round(statistics.median(per_m2)) if len(per_m2) >= MIN_AREA else None,
                         "median_days_on_market": round(statistics.median(days)) if days else None,
                         "neighbourhoods": hoods}
        return out


def months_text(days: int) -> str:
    if days < 14:
        return "listed this week" if days < 7 else "listed in the last two weeks"
    if days < 60:
        return f"on the market for {days // 7} weeks"
    months = round(days / 30.4)
    return f"on the market for {months} months" if months < 24 else f"on the market for {months // 12} years"


def market_lines(listing: Listing, stats: AreaStats, today: date | None = None) -> list[dict]:
    """Two facts about the market for a card, both calculated by code: €/m² against what's typical, and time on market."""
    lines = []
    typical = stats.typical(listing)
    if listing.price_per_m2 and typical:
        diff = (listing.price_per_m2 - typical.per_m2) / typical.per_m2
        share = round(abs(diff) * 100)
        where = "for" if typical.level == "similar" else "in"
        if share < 5:
            text = f"€{listing.price_per_m2:,}/m², about the typical €{typical.per_m2:,} {where} {typical.label}"
        else:
            text = f"€{listing.price_per_m2:,}/m², {share}% {'under' if diff < 0 else 'over'} the typical €{typical.per_m2:,} {where} {typical.label}"
        lines.append({"text": text, "feature": "price_per_m2", "value": listing.price_per_m2, "typical": typical.per_m2,
                      "level": typical.level, "homes": typical.homes, "share": share if share >= 5 else 0,
                      "direction": "about" if share < 5 else "under" if diff < 0 else "over"})
    days = days_on_market(listing)
    if days is not None:
        text = months_text(days)
        text = text[0].upper() + text[1:]
        previous = next((p.price_eur for p in reversed(listing.price_history) if p.price_eur != listing.price_eur), None)
        cut = previous is not None and listing.price_eur is not None and previous > listing.price_eur
        if cut:
            text += f", price cut from €{previous:,}"
        lines.append({"text": text, "feature": "days_on_market", "value": days,
                      **({"previous": previous} if cut else {})})
    return lines


def for_search(listings: list[Listing], criteria) -> AreaStats:
    """The stats a search compares against: rents with rents, sales with sales (D104)."""
    from core.filters import INTENT_TO_LISTING_TYPE
    return AreaStats.build(listings, INTENT_TO_LISTING_TYPE.get(getattr(criteria, "intent", None) or "buy", "sale"))
