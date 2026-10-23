"""The explanation eval: is every "why this one" reason backed by the listing's fields? (spec section 12, D64)

Code writes the reasons (core/reasons.py), so the question is whether the
templates ever say something the fields don't. This checks each reason a
second time, from the summary dictionaries the deck returns rather than
the Listing model, with the rules written out again here: the work must not
grade itself. A reason passes when its feature's value is what the listing
states and the claim holds (a wish met, a price under the area's typical,
a cut, a recent year).

    uv run python -m evals.harness.explanation_eval      # 50 cards from the search safety criteria, synthetic listings
"""

from __future__ import annotations

import json
import statistics
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from adapters.snapshot import SnapshotAdapter
from agent import interview
from core.models import Criteria
from learning import deck

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "evals" / "datasets" / "search_safety.jsonl"
RESULTS = ROOT / "evals" / "results"
CARDS = 50
TARGET = 0.98
TODAY = date(2026, 10, 23)
RECENT = TODAY.year - 10
PREFERENCES = [  # wishes the eval adds, so the preference reasons get exercised on every card
    {"feature": "balcony", "equals": True, "weight": 0.7},
    {"feature": "floor_level", "min": 2, "weight": 0.6},
    {"feature": "year_built", "min": 2000, "weight": 0.5},
    {"feature": "energy_class", "min": "C", "weight": 0.5},
    {"feature": "lift", "equals": True, "weight": 0.4},
]
ENERGY = ["G", "F", "E", "D", "C", "B", "B+", "A", "A+"]
FLOOR_LEVEL = {"basement": -1, "semi_basement": -0.5, "ground": 0, "raised_ground": 0.25, "mezzanine": 0.5}


def _level(floor: str | None) -> float | None:
    if floor is None or floor == "top":
        return None
    return FLOOR_LEVEL.get(floor, float(floor) if floor.isdigit() else None)


def backed(reason: dict, home: dict, full: dict, typical: dict[str, int], criteria: dict) -> str | None:
    """Why the reason isn't backed by the fields, or None if it is. Written independently of core/reasons.py."""
    feature, value, text = reason["feature"], reason.get("value"), reason["text"]
    if reason["kind"] == "preference":
        wish = next((p for p in criteria["preferences"] if p["feature"] == feature or (p["feature"] == "floor_level" and feature == "floor")), None)
        if wish is None:
            return "names a wish the card doesn't have"
        if feature in ("balcony", "lift", "parking", "storage"):
            has = full.get(feature) if feature != "parking" else (None if full.get("parking") is None else full["parking"] != "none")
            return None if has is wish["equals"] else f"{feature} is {has}, the wish was {wish['equals']}"
        if feature == "floor":
            level = _level(home["floor"])
            return None if level is not None and level >= wish["min"] and home["floor"] == value else f"floor {home['floor']} doesn't meet {wish['min']}"
        if feature == "energy_class":
            got = home["energy_class"]
            ok = got in ENERGY and ENERGY.index(got) >= ENERGY.index(wish["min"]) and got == value
            return None if ok else f"energy {got} doesn't meet {wish['min']}"
        got = home.get(feature)
        if got is None or got != value or str(got if not isinstance(got, float) else f"{got:g}") not in text.replace(",", ""):
            return f"{feature} {got} isn't what the reason says ({value})"
        if wish.get("min") is not None and got < wish["min"]:
            return f"{feature} {got} is under the wish {wish['min']}"
        if wish.get("max") is not None and got > wish["max"]:
            return f"{feature} {got} is over the wish {wish['max']}"
        return None
    if feature == "price_per_m2":
        per_m2 = typical.get(home["area"])
        if home["price_per_m2"] != value or not per_m2 or value > per_m2 * 0.95 or reason.get("typical") != per_m2:
            return f"€/m² {home['price_per_m2']} against typical {per_m2}"
        return None
    if feature == "price_eur":
        if home["price_eur"] != value:
            return "price isn't the listing's"
        if "cut" in text:
            previous = home.get("previous_price_eur")
            return None if previous and previous > value and reason.get("previous") == previous else "no such price cut"
        top = criteria["hard_limits"].get("max_price_eur")
        return None if top and ("within" in text) == (value <= top) else "within or over is wrong"
    if feature in ("renovated_year", "year_built"):
        got = home.get(feature)
        return None if got == value and got >= RECENT and str(got) in text else f"{feature} {got} isn't recent or isn't the listing's"
    if feature == "floor":
        return None if home["floor"] == "top" == value else "not the top floor"
    if feature == "energy_class":
        return None if home["energy_class"] == value and value in ("B+", "A", "A+") else "energy class isn't B+ or better"
    if feature == "size_m2":
        return None if home["size_m2"] == value and f"{value:g}" in text else "size isn't the listing's"
    return f"unknown reason feature {feature}"


def typical_per_m2(listings: list[dict]) -> dict[str, int]:
    by_area: dict[str, list[int]] = {}
    for l in listings:
        if l["area"] and l["price_per_m2"] and l["listing_type"] == "sale":
            by_area.setdefault(l["area"], []).append(l["price_per_m2"])
    return {a: round(statistics.median(v)) for a, v in by_area.items() if len(v) >= 5}


def run(snapshot: str | None = None, write: bool = True) -> dict:
    adapter = SnapshotAdapter(snapshot) if snapshot else SnapshotAdapter()
    listings = adapter.listings()
    full = {l.listing_id: l.model_dump(mode="json") for l in listings}
    summaries = [l.summary() for l in listings]
    typical = typical_per_m2(summaries)
    sets = [json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines() if line.strip()]
    cards, checked, failures = 0, 0, []
    for entry in sets:
        if cards >= CARDS:
            break
        raw = {**entry["effective_criteria"], "preferences": PREFERENCES}
        criteria = Criteria(user_id="eval", **raw)
        built = deck.build(listings, criteria, set(), limit=6, today=TODAY)
        for card in built["cards"]:
            if cards >= CARDS:
                break
            cards += 1
            home = next(s for s in summaries if s["listing_id"] == card["listing_id"])
            if not card["reasons"]:
                failures.append({"set": entry["id"], "listing": card["listing_id"], "reason": None, "why": "no reason at all"})
            for reason in card["reasons"]:
                checked += 1
                why = backed(reason, home, full[card["listing_id"]], typical, raw)
                if why:
                    failures.append({"set": entry["id"], "listing": card["listing_id"], "reason": reason["text"], "why": why})
    share = round((checked - len([f for f in failures if f["reason"]])) / checked, 4) if checked else 0.0
    summary = {"cards": cards, "reasons": checked, "backed": share, "target": TARGET, "passed": share >= TARGET and not failures,
               "failures": failures}
    print(f"Explanation eval: {cards} cards, {checked} reasons, {share:.1%} backed by fields (target {TARGET:.0%})"
          + ("" if not failures else f"\n  failures: {json.dumps(failures, ensure_ascii=False)}"))
    if write:
        RESULTS.mkdir(parents=True, exist_ok=True)
        (RESULTS / "v2-explanations.json").write_text(json.dumps({
            "eval": "explanations", "ran_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "data": "synthetic listings; criteria from the search safety set plus five fixed wishes", **summary,
        }, ensure_ascii=False, indent=1), encoding="utf-8")
    return summary


if __name__ == "__main__":
    out = run(sys.argv[1] if len(sys.argv) > 1 else None)
    sys.exit(0 if out["passed"] else 1)
