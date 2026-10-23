"""What the swipes say: code finds the pattern, the assistant only words it (spec section 4, D66).

After every few swipes the user's likes are compared with their rejects on
each field the listings state. A pattern counts only when nearly all the
likes sit on one side of a line and most of the rejects on the other, with
enough of each: with fewer than MIN_EACH known on a side nothing is said,
because a handful of swipes splits on some field by chance.

Each pattern comes with its evidence as counts, the exact change it would
make to the card, and how many homes that change would leave as a hard
limit. Five or more (THIN, D50) and it's offered as a limit; fewer, and the
same thing is offered as a strong preference, which ranks those homes first
without hiding the rest. The model never sees the swipes, only the pattern.
"""

from __future__ import annotations

import math
from collections import Counter
from datetime import date

from agent.interview import RENOVATED_YEARS, THIN
from core import greek
from core.filters import apply_hard_limits
from core.models import SEARCH_AREAS, Criteria, Listing, Swipe
from ranking.rules import ENERGY_ORDER

CHECKIN_EVERY = 10  # swipes between check-ins (Mike, D66)
MIN_EACH = 3  # likes and rejects that state the field before a line between them means anything
LIKES_SHARE = 0.9  # nearly all likes on one side of the line
REJECTS_SHARE = 0.6  # most rejects on the other side
MIN_REASON = 3  # the same reject reason this many times is a pattern on its own
STRONG = 0.8  # the weight of a preference a check-in adds
LOW_FLOORS = ("basement", "semi_basement", "ground", "raised_ground", "mezzanine")

# feature -> (how to read it from a listing, the step a line is rounded to, which direction can be suggested)
NUMERIC = {
    "year_built": (lambda l: l.year_built, 5, ("min",)),
    "renovated_year": (lambda l: l.renovated_year, 5, ("min",)),
    "size_m2": (lambda l: l.size_m2, 5, ("min", "max")),
    "price_eur": (lambda l: l.price_eur, 5000, ("max",)),
    "bedrooms": (lambda l: l.bedrooms, 1, ("min", "max")),
    "floor_level": (lambda l: greek.floor_level(l.floor.floor_class), 1, ("min",)),
    "metro_walk_min": (lambda l: l.metro_walk_min, 1, ("max",)),
    "energy_class": (lambda l: ENERGY_ORDER.index(l.energy_class.value) if l.energy_class.value in ENERGY_ORDER else None,
                     1, ("min",)),
}
YES_NO = {
    "balcony": lambda l: l.balcony,
    "lift": lambda l: l.lift,
    "storage": lambda l: l.storage,
    "parking": lambda l: None if l.parking is None else l.parking != "none",
}
# a line on these can be a hard limit; everything else can only rank
AS_LIMIT = {("year_built", "min"): "min_year_built", ("size_m2", "min"): "min_size_m2", ("size_m2", "max"): "max_size_m2",
            ("price_eur", "max"): "max_price_eur", ("bedrooms", "min"): "min_bedrooms", ("bedrooms", "max"): "max_bedrooms"}


def _round(value: float, step: int, direction: str) -> float:
    """Loosen the line to a round number: a minimum rounds down, a maximum rounds up."""
    return float(math.floor(value / step) * step if direction == "min" else math.ceil(value / step) * step)


def _split(likes: list[float], rejects: list[float], direction: str, step: int) -> dict | None:
    """The line that keeps nearly all likes on one side with most rejects on the other, or None."""
    if len(likes) < MIN_EACH or len(rejects) < MIN_EACH:
        return None
    best = None
    for line in sorted(set(likes) | set(rejects)):
        if direction == "min":
            likes_in, rejects_out = sum(v >= line for v in likes), sum(v < line for v in rejects)
        else:
            likes_in, rejects_out = sum(v <= line for v in likes), sum(v > line for v in rejects)
        if likes_in / len(likes) < LIKES_SHARE or rejects_out / len(rejects) < REJECTS_SHARE:
            continue
        candidate = (rejects_out, likes_in, line if direction == "max" else -line)
        if best is None or candidate > best[0]:
            best = (candidate, line)
    if best is None:
        return None
    # the line sits halfway between the groups, not on the nearest like: three likes built in 2025
    # against rejects up to 2008 give "from 2015", not "from 2025"
    edge = best[1]
    beyond = [v for v in rejects if (v < edge if direction == "min" else v > edge)]
    nearest = (max(beyond) if direction == "min" else min(beyond)) if beyond else edge
    line = _round((edge + nearest) / 2, step, direction)
    if direction == "min":
        likes_in, rejects_out = sum(v >= line for v in likes), sum(v < line for v in rejects)
    else:
        likes_in, rejects_out = sum(v <= line for v in likes), sum(v > line for v in rejects)
    return {"line": int(line) if float(line).is_integer() else line, "likes_in": likes_in, "likes": len(likes),
            "rejects_out": rejects_out, "rejects": len(rejects),
            "strength": round(likes_in / len(likes) + rejects_out / len(rejects), 3)}


def _already(criteria: Criteria, feature: str, direction: str, line) -> str | None:
    """"limit" or "preference" if the card already holds this line at least as tightly, else None."""
    limit = AS_LIMIT.get((feature, direction))
    if limit and getattr(criteria.hard_limits, limit) is not None:
        current = getattr(criteria.hard_limits, limit)
        if (direction == "min" and current >= line) or (direction == "max" and current <= line):
            return "limit"
    for p in criteria.preferences:
        if p.feature != feature:
            continue
        bound = p.min if direction == "min" else p.max
        if feature == "energy_class" and isinstance(bound, str):
            bound = ENERGY_ORDER.index(bound)
        if bound is not None and ((direction == "min" and bound >= line) or (direction == "max" and bound <= line)):
            return "preference" if p.weight < 0.9 else "limit"
    return None


def _would_leave(listings: list[Listing], criteria: Criteria, patch: dict) -> int:
    hard = {k: v for k, v in patch.items() if k != "areas"}
    tighter = criteria.model_copy(update={"hard_limits": criteria.hard_limits.model_copy(update=hard),
                                          **({"areas": patch["areas"]} if "areas" in patch else {})})
    return len(apply_hard_limits(listings, tighter).matches)


def _suggestion(feature: str, direction: str, split: dict, criteria: Criteria, listings: list[Listing],
                evidence: str, why: str = "swipes") -> dict | None:
    line = split["line"]
    held = _already(criteria, feature, direction, line)
    limit = AS_LIMIT.get((feature, direction))
    out = {"key": f"{feature}:{direction}", "feature": feature, "direction": direction, "line": line,
           "evidence": {**{k: split[k] for k in ("likes_in", "likes", "rejects_out", "rejects")}, "text": evidence, "from": why},
           "strength": split["strength"]}
    if limit:
        value = line if feature != "price_eur" else int(line)
        leaves = _would_leave(listings, criteria, {limit: value})
        out["would_leave"] = leaves
        if held == "limit":
            return None
        if leaves >= THIN:
            return {**out, "kind": "limit", "patch": {"hard_limits": {limit: value}}}
    if held:
        return None
    if feature == "energy_class":
        bound = ENERGY_ORDER[int(line)]
    else:
        bound = line
    preference = {"feature": feature, "min": None, "max": None, "equals": None, "weight": STRONG}
    preference["min" if direction == "min" else "max"] = bound
    return {**out, "kind": "preference", "patch": {"preferences": [preference]}}


def _numeric_evidence(feature: str, direction: str, split: dict) -> str:
    words = {"year_built": "built", "renovated_year": "renovated", "size_m2": "m²", "price_eur": "€", "bedrooms": "bedrooms",
             "floor_level": "floor", "metro_walk_min": "min from the metro", "energy_class": "energy class"}
    line = ENERGY_ORDER[int(split["line"])] if feature == "energy_class" else split["line"]
    side = ("from" if direction == "min" else "up to")
    unit = words[feature]
    what = f"{unit} {side} {line}" if feature in ("year_built", "renovated_year") else f"{side} {line} {unit}"
    return (f"{split['likes_in']} of {split['likes']} likes {what}; "
            f"{split['rejects_out']} of {split['rejects']} rejects the other side")


def observe(swipes: list[Swipe], listings: list[Listing], criteria: Criteria, declined: set[str] = frozenset(),
            today: date | None = None) -> list[dict]:
    """Every pattern the swipes support, strongest first. Each carries counts, a change and what it would leave."""
    today = today or date.today()
    by_id = {l.listing_id: l for l in listings}
    seen = [(by_id[s.listing_id], s) for s in swipes if s.listing_id in by_id]
    likes = [l for l, s in seen if s.decision == "like"]
    rejects = [(l, s) for l, s in seen if s.decision == "reject"]
    found: list[dict] = []

    for feature, (read, step, directions) in NUMERIC.items():
        like_values = [v for v in (read(l) for l in likes) if v is not None]
        reject_values = [v for v in (read(l) for l, _ in rejects) if v is not None]
        for direction in directions:
            split = _split(like_values, reject_values, direction, step)
            if split:
                suggestion = _suggestion(feature, direction, split, criteria, listings, _numeric_evidence(feature, direction, split))
                if suggestion:
                    found.append(suggestion)

    for feature, read in YES_NO.items():
        like_values = [v for v in (read(l) for l in likes) if v is not None]
        reject_values = [v for v in (read(l) for l, _ in rejects) if v is not None]
        if len(like_values) < MIN_EACH or len(reject_values) < MIN_EACH:
            continue
        likes_with, rejects_without = sum(like_values), sum(not v for v in reject_values)
        if likes_with / len(like_values) >= LIKES_SHARE and rejects_without / len(reject_values) >= REJECTS_SHARE:
            if not any(p.feature == feature and p.equals is True for p in criteria.preferences):
                found.append({"key": f"{feature}:equals", "feature": feature, "direction": "equals", "line": True,
                              "kind": "preference", "patch": {"preferences": [{"feature": feature, "min": None, "max": None,
                                                                              "equals": True, "weight": STRONG}]},
                              "evidence": {"likes_in": likes_with, "likes": len(like_values), "rejects_out": rejects_without,
                                           "rejects": len(reject_values), "from": "swipes",
                                           "text": f"{likes_with} of {len(like_values)} likes have a {feature.replace('_', ' ')}; "
                                                   f"{rejects_without} of {len(reject_values)} rejects don't"},
                              "strength": round(likes_with / len(like_values) + rejects_without / len(reject_values), 3)})

    found.extend(_floor_patterns(likes, rejects, criteria, listings))
    found.extend(_reason_patterns(likes, rejects, criteria, listings, today))

    found.sort(key=lambda f: (-f["strength"], f["kind"] != "limit",
                              -(f["evidence"]["likes"] + f["evidence"]["rejects"]), f["key"]))
    kept, keys = [], set()
    for f in found:  # one per key: the same change can show in the swipes and in the reject reasons
        if f["key"] not in declined and f["key"] not in keys:
            kept.append(f)
            keys.add(f["key"])
    return kept


def _floor_patterns(likes: list[Listing], rejects: list[tuple[Listing, Swipe]], criteria: Criteria,
                    listings: list[Listing]) -> list[dict]:
    """Low floors the user keeps rejecting and never likes: rule them out."""
    liked_low = Counter(l.floor.floor_class for l in likes if l.floor.floor_class in LOW_FLOORS)
    rejected_low = Counter(l.floor.floor_class for l, _ in rejects if l.floor.floor_class in LOW_FLOORS)
    floors = [f for f in LOW_FLOORS if rejected_low[f] and not liked_low[f] and f not in criteria.hard_limits.exclude_floors]
    total = sum(rejected_low[f] for f in floors)
    if not floors or total < MIN_REASON or sum(1 for l in likes if l.floor.floor_class) < MIN_EACH:
        return []
    patch = {"exclude_floors": [*criteria.hard_limits.exclude_floors, *floors]}
    leaves = _would_leave(listings, criteria, patch)
    names = ", ".join(f.replace("_", " ") for f in floors)
    evidence = {"likes_in": 0, "likes": len(likes), "rejects_out": total, "rejects": len(rejects), "from": "swipes",
                "text": f"{total} rejects on a {names} floor, no likes there"}
    base = {"key": "floor:exclude", "feature": "floor", "direction": "exclude", "line": floors, "evidence": evidence,
            "strength": round(1 + total / len(rejects), 3), "would_leave": leaves}
    if leaves >= THIN:
        return [{**base, "kind": "limit", "patch": {"hard_limits": patch}}]
    if any(p.feature == "floor_level" and p.min is not None for p in criteria.preferences):
        return []
    return [{**base, "kind": "preference",
             "patch": {"preferences": [{"feature": "floor_level", "min": 1, "max": None, "equals": None, "weight": STRONG}]}}]


def _reason_patterns(likes: list[Listing], rejects: list[tuple[Listing, Swipe]], criteria: Criteria,
                     listings: list[Listing], today: date) -> list[dict]:
    """The same reject reason again and again is a pattern in the user's own words."""
    reasons = Counter(r for _, s in rejects for r in s.reasons)
    out = []

    def add(key, feature, direction, line, kind, patch, count, text, leaves=None):
        entry = {"key": key, "feature": feature, "direction": direction, "line": line, "kind": kind, "patch": patch,
                 "evidence": {"likes_in": None, "likes": len(likes), "rejects_out": count, "rejects": len(rejects),
                              "from": "reject reasons", "text": text}, "strength": round(1 + count / len(rejects), 3)}
        if leaves is not None:
            entry["would_leave"] = leaves
        out.append(entry)

    n = reasons["too_expensive"]
    liked_prices = [l.price_eur for l in likes if l.price_eur]
    if n >= MIN_REASON and liked_prices and criteria.hard_limits.max_price_eur:
        top = int(_round(max(liked_prices), 5000, "max"))
        if top < criteria.hard_limits.max_price_eur:
            leaves = _would_leave(listings, criteria, {"max_price_eur": top})
            text = f"{n} rejects marked too expensive; your likes go up to €{max(liked_prices):,}"
            if leaves >= THIN:
                add("price_eur:max", "price_eur", "max", top, "limit", {"hard_limits": {"max_price_eur": top}}, n, text, leaves)
            else:
                add("price_eur:max", "price_eur", "max", top, "preference",
                    {"preferences": [{"feature": "price_eur", "min": None, "max": top, "equals": None, "weight": STRONG}]}, n, text, leaves)

    n = reasons["too_small"]
    liked_sizes = [l.size_m2 for l in likes if l.size_m2]
    if n >= MIN_REASON and liked_sizes:
        floor_size = _round(min(liked_sizes), 5, "min")
        if (criteria.hard_limits.min_size_m2 or 0) < floor_size:
            leaves = _would_leave(listings, criteria, {"min_size_m2": floor_size})
            text = f"{n} rejects marked too small; your smallest like is {min(liked_sizes):g} m²"
            kind = "limit" if leaves >= THIN else "preference"
            patch = ({"hard_limits": {"min_size_m2": floor_size}} if kind == "limit" else
                     {"preferences": [{"feature": "size_m2", "min": floor_size, "max": None, "equals": None, "weight": STRONG}]})
            add("size_m2:min", "size_m2", "min", floor_size, kind, patch, n, text, leaves)

    n = reasons["bad_floor"]
    if n >= MIN_REASON:
        bad = Counter(l.floor.floor_class for l, s in rejects if "bad_floor" in s.reasons and l.floor.floor_class)
        liked_floors = {l.floor.floor_class for l in likes}
        floors = [f for f, _ in bad.most_common() if f not in liked_floors and f not in criteria.hard_limits.exclude_floors]
        if floors:
            patch = {"exclude_floors": [*criteria.hard_limits.exclude_floors, *floors]}
            leaves = _would_leave(listings, criteria, patch)
            named = ", ".join(f"{f.replace('_', ' ')} ({bad[f]})" for f in floors)
            text = f"{n} rejects marked bad floor: {named}"
            if leaves >= THIN:
                add("floor:exclude", "floor", "exclude", floors, "limit", {"hard_limits": patch}, n, text, leaves)

    n = reasons["wrong_area"]
    if n >= MIN_REASON:
        areas = Counter(l.area for l, s in rejects if "wrong_area" in s.reasons and l.area)
        covered = list(criteria.areas or SEARCH_AREAS)
        if areas and len(covered) > 1:
            worst, count = areas.most_common(1)[0]
            if count == n and worst in covered and not any(l.area == worst for l in likes):
                remaining = [a for a in covered if a != worst]
                leaves = _would_leave(listings, criteria, {"areas": remaining})
                add("area:remove", "area", "remove", worst, "limit", {"areas": remaining}, n,
                    f"all {n} rejects marked wrong area are in {worst}, and no like is", leaves)

    n = reasons["needs_work"]
    if n >= MIN_REASON and not any(p.feature == "renovated_year" for p in criteria.preferences):
        since = today.year - RENOVATED_YEARS
        add("renovated_year:min", "renovated_year", "min", since, "preference",
            {"preferences": [{"feature": "renovated_year", "min": since, "max": None, "equals": None, "weight": STRONG}]},
            n, f"{n} rejects marked needs work")
    return out


def apply(criteria_raw: dict, patch: dict) -> dict:
    """The card with a suggestion's change made: the exact numbers code counted (D63)."""
    out = {**criteria_raw, "hard_limits": dict(criteria_raw.get("hard_limits") or {}),
           "preferences": list(criteria_raw.get("preferences") or [])}
    out["hard_limits"].update(patch.get("hard_limits") or {})
    if "areas" in patch:
        out["areas"] = list(patch["areas"])
    for preference in patch.get("preferences") or []:
        out["preferences"] = [p for p in out["preferences"] if p.get("feature") != preference["feature"]] + [preference]
    return out


def taken(after: dict, patch: dict) -> bool:
    """Did the card move the suggested way? Used to mark a declined suggestion so it isn't repeated."""
    hard_after = after.get("hard_limits") or {}
    for name, value in (patch.get("hard_limits") or {}).items():
        current = hard_after.get(name)
        if current is None:
            return False
        if name == "exclude_floors":
            if not set(value) <= set(current):
                return False
        elif (name.startswith("min") and current < value) or (name.startswith("max") and current > value):
            return False
    if "areas" in patch and set(after.get("areas") or []) - set(patch["areas"]):
        return False
    for preference in patch.get("preferences") or []:
        if not any(p.get("feature") == preference["feature"] for p in after.get("preferences") or []):
            return False
    return bool(patch)
