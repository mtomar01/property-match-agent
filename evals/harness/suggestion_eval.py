"""The suggestions eval: does code read the right pattern from a swipe history, or stay quiet? (spec section 12, D66)

Thirty swipe histories on the synthetic listings, each written by a rule
that stands for one taste ("likes homes built from 2010 on", "rejects low
floors as bad floor", "swipes at random"). The expected answer is the key
of the change a check-in should offer, or none. The eval runs the pattern
finder (learning/patterns.py) on each history and scores:

- precision: of the histories where code offered a change, the share where
  it was the expected one (a change on a random history is a false alarm);
- recall: of the histories with a pattern, the share where code found it;
- evidence: the counts in the suggestion, recounted here from the swipes and
  the listings with the rule written a second time. Always correct, or the
  eval fails.

    uv run python -m evals.harness.suggestion_eval build   # write the dataset (deterministic)
    uv run python -m evals.harness.suggestion_eval         # score
"""

from __future__ import annotations

import json
import random
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from adapters.snapshot import SnapshotAdapter
from core.models import Criteria, Swipe
from learning import deck, patterns

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "evals" / "datasets" / "swipe_histories.jsonl"
RESULTS = ROOT / "evals" / "results"
TODAY = date(2026, 10, 23)
TS = datetime(2026, 10, 23, 12, 0, tzinfo=timezone.utc)
TARGET_PRECISION = 0.80
ENERGY = ["G", "F", "E", "D", "C", "B", "B+", "A", "A+"]
FLOOR_LEVEL = {"basement": -1, "semi_basement": -0.5, "ground": 0, "raised_ground": 0.25, "mezzanine": 0.5}

CARDS = {
    "all": {"intent": "buy", "areas": [], "hard_limits": {"max_price_eur": 300000, "min_price_eur": 100000}},
    "egaleo": {"intent": "buy", "areas": ["Egaleo"], "hard_limits": {"max_price_eur": 250000, "min_price_eur": 100000}},
    "two_areas": {"intent": "buy", "areas": ["Egaleo", "Peristeri"], "hard_limits": {"max_price_eur": 300000, "min_price_eur": 100000}},
    "flats": {"intent": "buy", "areas": [], "hard_limits": {"max_price_eur": 300000, "min_price_eur": 100000, "property_types": ["apartment"]}},
}


def _level(floor):
    if floor is None or floor == "top":
        return None
    return FLOOR_LEVEL.get(floor, float(floor) if floor.isdigit() else None)


# Each taste: how the user swipes a listing (decision, reasons), and the keys a check-in may offer for it.
# A taste can read two ways ("high floors" is also "no low floors"), so a list of acceptable keys.
TASTES = {
    "recent_builds": (lambda l, r: ("like" if (l.year_built or 0) >= 2010 else "reject", []), ["year_built:min"]),
    "big_homes": (lambda l, r: ("like" if (l.size_m2 or 0) >= 100 else "reject", []), ["size_m2:min"]),
    "small_homes": (lambda l, r: ("like" if (l.size_m2 or 999) <= 70 else "reject", []), ["size_m2:max"]),
    "balcony_only": (lambda l, r: ("like" if l.balcony else "reject", []), ["balcony:equals"]),
    "high_floors": (lambda l, r: ("like" if (_level(l.floor.floor_class) or -9) >= 2 else "reject", []), ["floor_level:min", "floor:exclude"]),
    "good_energy": (lambda l, r: ("like" if l.energy_class.value in ENERGY[ENERGY.index("B"):] else "reject", []), ["energy_class:min"]),
    "cheap": (lambda l, r: ("like" if (l.price_eur or 0) <= 180000 else "reject", []), ["price_eur:max"]),
    "says_too_expensive": (lambda l, r: ("like" if (l.price_eur or 0) <= 180000 else "reject", ["too_expensive"] if (l.price_eur or 0) > 180000 else []), ["price_eur:max"]),
    "hates_low_floors": (lambda l, r: ("reject", ["bad_floor"]) if l.floor.floor_class in patterns.LOW_FLOORS else ("like" if r.random() < 0.6 else "reject", []), ["floor:exclude"]),
    "not_peristeri": (lambda l, r: ("reject", ["wrong_area"]) if l.area == "Peristeri" else ("like" if r.random() < 0.6 else "reject", []), ["area:remove"]),
    "wants_renovated": (lambda l, r: ("like" if (l.renovated_year or 0) >= 2016 else "reject", ["needs_work"] if (l.renovated_year or 0) < 2016 else []), ["renovated_year:min"]),
    "random": (lambda l, r: (r.choice(["like", "reject", "reject"]), []), []),
    "likes_everything": (lambda l, r: ("like", []), []),
    "random_with_reasons": (lambda l, r: (("reject", [r.choice(["too_dark", "other"])]) if r.random() < 0.6 else ("like", [])), []),
}
# the reject reason a taste states, when it states one: the pattern then needs that reason three times
STATED = {"says_too_expensive": "too_expensive", "hates_low_floors": "bad_floor", "not_peristeri": "wrong_area", "wants_renovated": "needs_work"}
MIN_EACH = 3  # likes and rejects a history must hold before anything can be read from it (the finder's own minimum)

PLAN = [  # (history id, taste, card, swipes, seed): 30 histories, a third of them with nothing to find
    ("sh01", "recent_builds", "all", 24, 1), ("sh02", "recent_builds", "flats", 24, 2), ("sh03", "big_homes", "all", 14, 3),
    ("sh04", "big_homes", "two_areas", 12, 4), ("sh05", "small_homes", "all", 24, 5), ("sh06", "balcony_only", "all", 12, 6),
    ("sh07", "balcony_only", "egaleo", 20, 7), ("sh08", "high_floors", "all", 14, 8), ("sh09", "high_floors", "flats", 12, 9),
    ("sh10", "good_energy", "all", 14, 10), ("sh11", "cheap", "all", 12, 11), ("sh12", "cheap", "two_areas", 14, 12),
    ("sh13", "says_too_expensive", "all", 12, 13), ("sh14", "says_too_expensive", "egaleo", 11, 14),
    ("sh15", "hates_low_floors", "all", 20, 15), ("sh16", "hates_low_floors", "two_areas", 30, 16),
    ("sh17", "not_peristeri", "two_areas", 16, 17), ("sh18", "not_peristeri", "all", 20, 18),
    ("sh19", "wants_renovated", "all", 14, 19), ("sh20", "wants_renovated", "flats", 14, 20),
    ("sh21", "random", "all", 12, 21), ("sh22", "random", "all", 14, 22), ("sh23", "random", "egaleo", 11, 23),
    ("sh24", "random", "flats", 14, 24), ("sh25", "random", "two_areas", 12, 25), ("sh26", "random", "all", 20, 26),
    ("sh27", "likes_everything", "all", 12, 27), ("sh28", "random_with_reasons", "all", 14, 28),
    ("sh29", "random_with_reasons", "two_areas", 12, 29), ("sh30", "random", "all", 10, 30),
]


def build(out: Path = DATASET) -> Path:
    listings = SnapshotAdapter().listings()
    rows = []
    for history_id, taste, card_name, count, seed in PLAN:
        rule, expected = TASTES[taste]
        criteria = Criteria(user_id="eval", **CARDS[card_name])
        order = deck.order([l for l in deck.ranked_matches(listings, criteria)], seed)[:count]
        rng = random.Random(seed)
        swipes = []
        for i, (listing, explore) in enumerate(order):
            decision, reasons = rule(listing, rng)
            swipes.append({"listing_id": listing.listing_id, "decision": decision, "reasons": reasons, "deck_position": i,
                           "explore_card": explore})
        # a history with too little on one side has nothing to read yet: the right answer is silence
        likes = sum(1 for s in swipes if s["decision"] == "like")
        rejects = len(swipes) - likes
        stated = sum(1 for s in swipes if STATED.get(taste) in s["reasons"]) if taste in STATED else None
        enough = likes >= MIN_EACH and rejects >= MIN_EACH if stated is None else stated >= MIN_EACH and likes >= MIN_EACH
        rows.append({"id": history_id, "taste": taste if enough else f"{taste} (too few to read)", "card": card_name,
                     "criteria": CARDS[card_name], "swipes": swipes, "expected": expected if enough else []})
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    return out


def recount(suggestion: dict, history: dict, by_id: dict) -> str | None:
    """The suggestion's counts, done again from the swipes with the rule written a second time. None if they agree."""
    likes = [by_id[s["listing_id"]] for s in history["swipes"] if s["decision"] == "like"]
    rejects = [(by_id[s["listing_id"]], s) for s in history["swipes"] if s["decision"] == "reject"]
    ev, feature, direction, line = suggestion["evidence"], suggestion["feature"], suggestion["direction"], suggestion["line"]
    read = {
        "year_built": lambda l: l.year_built, "renovated_year": lambda l: l.renovated_year, "size_m2": lambda l: l.size_m2,
        "price_eur": lambda l: l.price_eur, "bedrooms": lambda l: l.bedrooms, "metro_walk_min": lambda l: l.metro_walk_min,
        "floor_level": lambda l: _level(l.floor.floor_class),
        "energy_class": lambda l: ENERGY.index(l.energy_class.value) if l.energy_class.value in ENERGY else None,
        "balcony": lambda l: l.balcony, "lift": lambda l: l.lift, "storage": lambda l: l.storage,
        "parking": lambda l: None if l.parking is None else l.parking != "none",
    }
    if ev["from"] == "reject reasons":
        reason = {"price_eur": "too_expensive", "size_m2": "too_small", "floor": "bad_floor", "area": "wrong_area",
                  "renovated_year": "needs_work"}[feature]
        count = sum(1 for _, s in rejects if reason in s["reasons"])
        return None if count == ev["rejects_out"] and ev["rejects"] == len(rejects) else f"{reason} count {count} vs {ev['rejects_out']}"
    if feature == "floor":
        liked = {l.floor.floor_class for l in likes}
        bad = sum(1 for l, _ in rejects if l.floor.floor_class in line)
        if any(f in liked for f in line):
            return "a ruled-out floor was liked"
        return None if bad == ev["rejects_out"] else f"floor count {bad} vs {ev['rejects_out']}"
    values = read[feature]
    like_values = [v for v in (values(l) for l in likes) if v is not None]
    reject_values = [v for v in (values(l) for l, _ in rejects) if v is not None]
    if direction == "equals":
        likes_in, rejects_out = sum(1 for v in like_values if v), sum(1 for v in reject_values if not v)
    elif direction == "min":
        likes_in, rejects_out = sum(1 for v in like_values if v >= line), sum(1 for v in reject_values if v < line)
    else:
        likes_in, rejects_out = sum(1 for v in like_values if v <= line), sum(1 for v in reject_values if v > line)
    got = (likes_in, len(like_values), rejects_out, len(reject_values))
    said = (ev["likes_in"], ev["likes"], ev["rejects_out"], ev["rejects"])
    return None if got == said else f"counts {got} vs {said}"


def run(write: bool = True) -> dict:
    listings = SnapshotAdapter().listings()
    by_id = {l.listing_id: l for l in listings}
    rows = [json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines() if line.strip()]
    scored = []
    for history in rows:
        criteria = Criteria(user_id="eval", **history["criteria"])
        swipes = [Swipe(user_id="eval", ts=TS, **s) for s in history["swipes"]]
        found = patterns.observe(swipes, listings, criteria, today=TODAY)
        top = found[0] if found else None
        entry = {"id": history["id"], "taste": history["taste"], "expected": history["expected"],
                 "offered": top["key"] if top else None, "kind": top["kind"] if top else None,
                 "evidence": top["evidence"]["text"] if top else None, "others": [f["key"] for f in found[1:4]]}
        expected = history["expected"]
        entry["right"] = (top["key"] in expected) if top else not expected
        entry["evidence_ok"] = recount(top, history, by_id) if top else None
        scored.append(entry)
    offered = [s for s in scored if s["offered"]]
    with_pattern = [s for s in scored if s["expected"]]
    precision = round(sum(1 for s in offered if s["right"]) / len(offered), 3) if offered else None
    recall = round(sum(1 for s in with_pattern if s["right"]) / len(with_pattern), 3) if with_pattern else None
    false_alarms = [s["id"] for s in scored if s["offered"] and not s["expected"]]
    wrong = [s["id"] for s in scored if s["offered"] and s["expected"] and not s["right"]]
    missed = [s["id"] for s in scored if s["expected"] and not s["offered"]]
    evidence_wrong = [(s["id"], s["evidence_ok"]) for s in scored if s["evidence_ok"]]
    summary = {"histories": len(scored), "offered": len(offered), "precision": precision, "recall": recall,
               "false_alarms": false_alarms, "wrong_change": wrong, "missed": missed, "evidence_wrong": evidence_wrong,
               "passed": (precision or 0) >= TARGET_PRECISION and not evidence_wrong}
    print(f"Suggestion eval: {len(scored)} histories, {len(offered)} with a change offered\n"
          f"  precision {precision:.1%} (target {TARGET_PRECISION:.0%}), recall {recall:.1%}\n"
          f"  false alarms {false_alarms}, wrong change {wrong}, missed {missed}\n"
          f"  evidence recounted: {'all correct' if not evidence_wrong else evidence_wrong}")
    for s in scored:
        if not s["right"]:
            print(f"    {s['id']} {s['taste']}: expected {s['expected'] or 'nothing'}, offered {s['offered']} ({s['evidence']}); next {s['others']}")
    if write:
        RESULTS.mkdir(parents=True, exist_ok=True)
        (RESULTS / "v2-suggestions.json").write_text(json.dumps({
            "eval": "suggestions", "ran_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "data": "30 swipe histories written by taste rules on the synthetic listings", "summary": summary, "histories": scored,
        }, ensure_ascii=False, indent=1), encoding="utf-8")
    return summary


if __name__ == "__main__":
    if sys.argv[1:2] == ["build"]:
        print(f"Wrote {build().relative_to(ROOT)}")
    else:
        sys.exit(0 if run()["passed"] else 1)
