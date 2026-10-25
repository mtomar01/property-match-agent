"""Build the search safety dataset: 23 criteria sets with their expected matches.

The criteria are written by hand to hit the risky cases (budgets exactly on a
price, Greek area and floor names, rentals, unknown values, an impossible
search). The expected matches are computed once with the independent checker
over the synthetic snapshot and frozen into the file, so any later change to
search or to the synthetic data shows up as a diff to review. Since D59 they're
computed on the limits the search actually runs on (effective_criteria): the
criteria plus Mike's lowest-price rule, so that limit is never broken either.

Run: uv run python -m evals.harness.build_search_safety
"""

from __future__ import annotations

import json
from pathlib import Path

from adapters.snapshot import SnapshotAdapter
from core.card_rules import search_card
from evals.harness.checks import breaks

DATASET = Path(__file__).resolve().parent.parent / "datasets" / "search_safety.jsonl"

CASES: list[tuple[str, str, dict]] = [
    ("ss01", "Spec demo: two bed flat in Egaleo under 200k",
     {"intent": "buy", "areas": ["Egaleo"], "hard_limits": {"max_price_eur": 200000, "min_bedrooms": 2, "property_types": ["apartment"]}}),
    ("ss02", "Budget exactly equal to a listed price (200,000 is allowed, 201,000 is not)",
     {"intent": "buy", "areas": ["Egaleo", "Peristeri"], "hard_limits": {"max_price_eur": 200000}}),
    ("ss03", "Minimum size exactly 70 (70 allowed, 69 not)",
     {"intent": "buy", "hard_limits": {"min_size_m2": 70, "max_price_eur": 250000}}),
    ("ss04", "Greek area names",
     {"intent": "buy", "areas": ["Αιγάλεω", "Χαϊδάρι"], "hard_limits": {"max_price_eur": 300000}}),
    ("ss05", "Exclude basement and semi-basement, given in Greek",
     {"intent": "buy", "hard_limits": {"exclude_floors": ["υπόγειο", "ημιυπόγειο"], "max_price_eur": 150000}}),
    ("ss06", "Exclude ground floors too",
     {"intent": "buy", "areas": ["Peristeri"], "hard_limits": {"exclude_floors": ["basement", "semi_basement", "ground"]}}),
    ("ss07", "Rent, not buy: sale listings must never appear",
     {"intent": "rent", "hard_limits": {"max_price_eur": 1000}}),
    ("ss08", "Rent with a bedroom minimum",
     {"intent": "rent", "hard_limits": {"min_bedrooms": 2}}),
    ("ss09", "Maisonettes only",
     {"intent": "buy", "hard_limits": {"property_types": ["maisonette"]}}),
    ("ss10", "Three bedrooms or more in Chaidari",
     {"intent": "buy", "areas": ["Chaidari"], "hard_limits": {"min_bedrooms": 3}}),
    ("ss11", "Price band",
     {"intent": "buy", "hard_limits": {"min_price_eur": 150000, "max_price_eur": 220000}}),
    ("ss12", "Size band",
     {"intent": "buy", "hard_limits": {"min_size_m2": 60, "max_size_m2": 90}}),
    ("ss13", "Tight budget: price on request must not slip in",
     {"intent": "buy", "hard_limits": {"max_price_eur": 120000}}),
    ("ss14", "No limits at all except intent: every sale listing",
     {"intent": "buy"}),
    ("ss15", "Impossible: 4 bedrooms under 100k",
     {"intent": "buy", "hard_limits": {"max_price_eur": 100000, "min_bedrooms": 4}}),
    ("ss16", "Everything at once",
     {"intent": "buy", "areas": ["Egaleo", "Peristeri", "Chaidari"],
      "hard_limits": {"max_price_eur": 260000, "min_size_m2": 65, "min_bedrooms": 2, "property_types": ["apartment", "maisonette"],
                      "exclude_floors": ["basement", "semi_basement"]}}),
    ("ss17", "Preferences must not loosen limits",
     {"intent": "buy", "areas": ["Egaleo"], "hard_limits": {"max_price_eur": 180000},
      "preferences": [{"feature": "floor_level", "min": 3, "weight": 1.0}, {"feature": "balcony", "equals": True, "weight": 0.8}]}),
    ("ss18", "Investor intent searches sales",
     {"intent": "invest", "areas": ["Peristeri"], "hard_limits": {"max_price_eur": 150000}}),
    ("ss19", "Studios and apartments, small",
     {"intent": "buy", "hard_limits": {"property_types": ["studio", "apartment"], "max_size_m2": 50}}),
    ("ss20", "Mixed spelling of the same area",
     {"intent": "buy", "areas": ["aigaleo", "Egaleo", "ΑΙΓΑΛΕΩ"], "hard_limits": {"min_bedrooms": 1}}),
    ("ss21", "Price per m² limit: a home with no size has no price per m² and must not slip in (D73)",
     {"intent": "buy", "hard_limits": {"max_price_eur": 300000, "max_price_per_m2": 2400}}),
    ("ss22", "No stairs above the 1st floor without a lift; an unstated floor or lift fails closed (D73)",
     {"intent": "buy", "hard_limits": {"max_price_eur": 300000, "max_floor_without_lift": 1}}),
    ("ss23", "No homes that need work; an unstated condition fails closed (D73)",
     {"intent": "buy", "hard_limits": {"max_price_eur": 300000, "exclude_conditions": ["needs_work", "unfinished"]}}),
    ("ss24", "Parking and a lift are musts; an unstated parking fails closed (D79)",
     {"intent": "buy", "hard_limits": {"max_price_eur": 350000, "must_have": ["parking", "lift"]}}),
    ("ss25", "At least 2 bathrooms (D79)",
     {"intent": "buy", "hard_limits": {"max_price_eur": 350000, "min_bathrooms": 2}}),
    ("ss26", "Renovated or built from 2021; a home that says neither fails closed (D79)",
     {"intent": "buy", "hard_limits": {"max_price_eur": 350000, "min_renovated_year": 2021}}),
    ("ss27", "Floor 2 to 4; a top floor with no number fails closed (D79)",
     {"intent": "buy", "hard_limits": {"max_price_eur": 350000, "min_floor_level": 2, "max_floor_level": 4}}),
    ("ss28", "The metro within 10 minutes on foot, taken as a limit; an unstated walk fails closed (D79)",
     {"intent": "buy", "hard_limits": {"max_price_eur": 350000, "max_metro_walk_min": 10}}),
    ("ss29", "Firm wishes become limits in code; an 'ideally' wish only ranks (D79)",
     {"intent": "buy", "hard_limits": {"max_price_eur": 350000},
      "preferences": [{"feature": "parking", "equals": True, "weight": 0.7, "firm": True},
                      {"feature": "renovated_year", "min": 2021, "weight": 0.8, "firm": True},
                      {"feature": "balcony", "equals": True, "weight": 0.6, "firm": False}]}),
]


def build() -> Path:
    adapter = SnapshotAdapter()
    rows = []
    for case_id, description, criteria in CASES:
        # The limits the search runs on: the criteria as given, plus Mike's rules in code (a lowest price, D53, D59).
        effective = {k: v for k, v in search_card(criteria).items() if k != "from_wishes"}
        expected = [
            l.listing_id for l in adapter.listings()
            if not breaks(l.summary(), effective)
        ]
        rows.append({"id": case_id, "description": description, "criteria": criteria,
                     "effective_criteria": effective, "expected_ids": sorted(expected)})
    DATASET.parent.mkdir(parents=True, exist_ok=True)
    with DATASET.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return DATASET


if __name__ == "__main__":
    path = build()
    for line in path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        print(f"{row['id']}  {len(row['expected_ids']):>3} expected  {row['description']}")
