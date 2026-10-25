"""Duplicate listings: the same home listed more than once, found by code (spec section 11, D78).

The same flat often appears several times, listed by different agencies, with different photos, words and
prices. Showing it three times wastes three swipes; merging two different flats hides a real option, which
is worse. So the finder is built for precision: it merges only on strong evidence and leaves the rest apart.

Each pair in the same area is compared on the spec's signals:

- **must agree** (or the pair is never a duplicate): size within 2 m², price within 10% (when both state one),
  and bedrooms, floor and property type the same wherever both listings state them;
- **must not disagree**: a building or renovation year more than 2 years apart, or a different number of
  bathrooms;
- **evidence**: a shared photo hash, the description's wording (the share of 3-word runs the two texts share),
  the same neighbourhood, the same building year, the same price.

Then one of three verdicts:

- **same**: a shared photo hash; or wording at least 0.6 alike; or wording at least 0.3 alike with the same
  neighbourhood, the same stated floor and the same stated building year; or a **copy**: the same price to the
  euro and the same size to the m² (D84). Spiti24 and Spitogatos belong to the same group and carry many such
  copies, often with no description on the spiti24 side, so wording can't find them. A copy needs neither the
  same neighbourhood name (the two portals write them differently) nor to be the only match (one flat is often
  listed three or four times): Mike's 60 labelled pairs showed both guards cost real duplicates and caught none;
- **borderline**: nothing contradicts and there's some evidence (wording at least 0.15 alike, or the same
  neighbourhood and building year). Kept apart: the spec gives these to the model, side by side;
- **different**: everything else.

On Mike's labels (D83, D84): 41 of 41 merges right, recall 0.91. That's a development score, since the copy rule
was set from those same labels.
"""

from __future__ import annotations

import itertools
import re
from dataclasses import dataclass, field

from core.models import DuplicateCluster, DuplicateEvidence, Listing

SIZE_GAP = 2.0
PRICE_GAP = 0.10
YEAR_GAP = 2
SAME_TEXT = 0.6
SAME_TEXT_WITH_PLACE = 0.3
BORDERLINE_TEXT = 0.15


def _runs(text: str | None, n: int = 3) -> set[tuple[str, ...]]:
    words = re.findall(r"\w+", (text or "").lower())
    return {tuple(words[i:i + n]) for i in range(len(words) - n + 1)}


def text_overlap(a: str | None, b: str | None) -> float:
    """The share of 3-word runs the two descriptions share (Jaccard): 1.0 for the same text, near 0 for unrelated ones."""
    ra, rb = _runs(a), _runs(b)
    if not ra or not rb:
        return 0.0
    return len(ra & rb) / len(ra | rb)


def _both(a, b) -> bool:
    return a is not None and b is not None


@dataclass
class Pair:
    a: str
    b: str
    verdict: str  # "same", "borderline" or "different"
    text: float
    evidence: list[DuplicateEvidence] = field(default_factory=list)
    why_not: str | None = None

    def as_dict(self) -> dict:
        return {"a": self.a, "b": self.b, "verdict": self.verdict, "text": round(self.text, 3),
                "evidence": [e.model_dump() for e in self.evidence], "why_not": self.why_not}


def compare(a: Listing, b: Listing, use_photos: bool = True) -> Pair:
    """One pair, judged on the signals above."""
    def no(reason: str, text: float = 0.0) -> Pair:
        return Pair(a.listing_id, b.listing_id, "different", text, why_not=reason)

    if a.area != b.area or a.listing_type != b.listing_type:
        return no("area or listing type")
    if not _both(a.size_m2, b.size_m2) or abs(a.size_m2 - b.size_m2) > SIZE_GAP:
        return no("size")
    priced = _both(a.price_eur, b.price_eur)
    if priced and abs(a.price_eur - b.price_eur) > PRICE_GAP * max(a.price_eur, b.price_eur):
        return no("price")
    for name in ("bedrooms", "property_type"):
        if _both(getattr(a, name), getattr(b, name)) and getattr(a, name) != getattr(b, name):
            return no(name)
    fa, fb = a.floor.floor_class, b.floor.floor_class
    if _both(fa, fb) and fa != fb:
        return no("floor")
    if _both(a.year_built, b.year_built) and abs(a.year_built - b.year_built) > YEAR_GAP:
        return no("building year")
    if _both(a.bathrooms, b.bathrooms) and a.bathrooms != b.bathrooms:
        return no("bathrooms")
    if _both(a.renovated_year, b.renovated_year) and abs(a.renovated_year - b.renovated_year) > YEAR_GAP:
        return no("renovation year")

    text = text_overlap(a.description, b.description)
    photo = use_photos and bool(set(a.photo_hashes) & set(b.photo_hashes))
    same_place = bool(a.sub_area) and a.sub_area == b.sub_area
    same_year = _both(a.year_built, b.year_built) and a.year_built == b.year_built
    same_floor = _both(fa, fb)
    evidence = [DuplicateEvidence(signal="area", detail=f"both in {a.area}" + (f", {a.sub_area}" if same_place else "")),
                DuplicateEvidence(signal="size", detail=f"{a.size_m2:g} and {b.size_m2:g} m²"),
                DuplicateEvidence(signal="price", detail=f"€{a.price_eur:,} and €{b.price_eur:,}" if priced else "a price on request")]
    if same_floor:
        evidence.append(DuplicateEvidence(signal="floor", detail=f"both floor {fa}"))
    if text:
        evidence.append(DuplicateEvidence(signal="text", detail=f"descriptions {text:.0%} alike"))
    if photo:
        evidence.append(DuplicateEvidence(signal="photo_hash", detail="a photo in common"))

    if photo or text >= SAME_TEXT or (priced and text >= SAME_TEXT_WITH_PLACE and same_place and same_floor and same_year):
        verdict = "same"  # with a price on request, only a photo or the same wording is enough
    elif text >= BORDERLINE_TEXT or (same_place and same_year):
        verdict = "borderline"
    else:
        verdict = "different"
    return Pair(a.listing_id, b.listing_id, verdict, text, evidence)


def _copy(a: Listing, b: Listing) -> bool:
    return a.price_eur is not None and a.price_eur == b.price_eur and a.size_m2 == b.size_m2


def pairs(listings: list[Listing], use_photos: bool = True) -> list[Pair]:
    """Every pair in the same area that passes the must-agree checks, judged. Pairs that fail them aren't returned."""
    by_area: dict[tuple, list[Listing]] = {}
    for l in listings:
        if l.area and l.size_m2:
            by_area.setdefault((l.area, l.listing_type), []).append(l)
    out, homes = [], {l.listing_id: l for l in listings}
    for group in by_area.values():
        group.sort(key=lambda l: l.size_m2)
        for i, a in enumerate(group):
            for b in itertools.takewhile(lambda b: b.size_m2 - a.size_m2 <= SIZE_GAP, group[i + 1:]):
                pair = compare(a, b, use_photos)
                if pair.why_not is None:
                    out.append(pair)
    # A copy: the same price to the euro and size to the m², in a pair that already passed every must-agree check (D84)
    for p in out:
        if p.verdict != "same" and _copy(homes[p.a], homes[p.b]):
            p.verdict = "same"
            p.evidence.append(DuplicateEvidence(signal="price", detail="the same price and size to the euro and m²"))
    return out


def _strength(pair: Pair, homes: dict[str, Listing]) -> tuple:
    """Strongest evidence first: a shared photo, then an exact copy, then wording (a new build's flats share a template)."""
    photo = any(e.signal == "photo_hash" for e in pair.evidence)
    return (photo, _copy(homes[pair.a], homes[pair.b]), pair.text)


def clusters(listings: list[Listing], use_photos: bool = True) -> list[DuplicateCluster]:
    """The "same" pairs grouped into homes, each with its price range (D84).

    A group only grows when the newcomer is "same" with every listing already in it. Chaining (a like b, b like c,
    so a like c) let one copy pull a different flat of the same new build into the group, so it's not allowed:
    strongest pairs are joined first, and a pair that would join two different homes stays apart.
    """
    by_id = {l.listing_id: l for l in listings}
    found = [p for p in pairs(listings, use_photos) if p.verdict == "same"]
    same = {frozenset((p.a, p.b)): p for p in found}
    group_of: dict[str, set[str]] = {}
    for pair in sorted(found, key=lambda p: _strength(p, by_id), reverse=True):
        left, right = group_of.get(pair.a, {pair.a}), group_of.get(pair.b, {pair.b})
        if left is right or not all(frozenset((x, y)) in same for x in left for y in right):
            continue
        merged = left | right
        for member in merged:
            group_of[member] = merged
    out, seen = [], set()
    for group in group_of.values():
        if id(group) in seen:
            continue
        seen.add(id(group))
        members = sorted(group)
        prices = [by_id[m].price_eur for m in members if by_id[m].price_eur]
        evidence = [e for key, p in same.items() if key <= group for e in p.evidence]
        out.append(DuplicateCluster(cluster_id="dup-" + members[0].replace(":", "-"), listing_ids=members,
                                    evidence=_unique(evidence), price_min_eur=min(prices) if prices else None,
                                    price_max_eur=max(prices) if prices else None, decided_by="code"))
    return sorted(out, key=lambda c: c.cluster_id)


def _unique(evidence: list[DuplicateEvidence]) -> list[DuplicateEvidence]:
    seen, out = set(), []
    for e in evidence:
        if (e.signal, e.detail) not in seen:
            seen.add((e.signal, e.detail))
            out.append(e)
    return out


def index(found: list[DuplicateCluster]) -> dict[str, DuplicateCluster]:
    """Each listing in a cluster, pointing at its cluster."""
    return {lid: c for c in found for lid in c.listing_ids}
