from datetime import date

from core.filters import apply_hard_limits, check
from core.models import Criteria, Listing
from ranking.rules import score


def listing(n: int, **fields) -> Listing:
    data = {
        "listing_id": f"xe:{n}",
        "source": "xe",
        "url": f"https://synthetic.invalid/xe/{n}",
        "first_seen": date(2026, 10, 1),
        "last_seen": date(2026, 10, 20),
        "price_eur": 180000,
        "size_m2": 75,
        "bedrooms": 2,
        "property_type": "apartment",
        "floor": {"raw": "2ος", "class": "2"},
        "area": "Egaleo",
    }
    data.update(fields)
    return Listing.model_validate(data)


def criteria(**limits) -> Criteria:
    return Criteria(user_id="u", intent=limits.pop("intent", "buy"), areas=limits.pop("areas", []), hard_limits=limits)


def test_budget_is_inclusive():
    assert check(listing(1, price_eur=200000), criteria(max_price_eur=200000)) is None
    assert check(listing(2, price_eur=200001), criteria(max_price_eur=200000)) == ("over_budget", "price_eur")


def test_unknown_values_fail_closed_and_are_counted():
    outcome = apply_hard_limits(
        [listing(1), listing(2, price_eur=None), listing(3, bedrooms=None), listing(4, floor={})],
        criteria(max_price_eur=200000, min_bedrooms=2, exclude_floors=["basement"]),
    )
    assert [l.listing_id for l in outcome.matches] == ["xe:1"]
    assert outcome.excluded_unknown == {"price_eur": 1, "bedrooms": 1, "floor": 1}


def test_unknown_only_matters_when_a_limit_needs_it():
    assert check(listing(1, price_eur=None), criteria(min_bedrooms=2)) is None


def test_floors_rentals_types_and_areas():
    assert check(listing(1, floor={"raw": "υπόγειο", "class": "basement"}), criteria(exclude_floors=["υπόγειο"]))[0] == "excluded_floor"
    assert check(listing(2, listing_type="rent", price_eur=800), criteria(intent="buy"))[0] == "wrong_listing_type"
    assert check(listing(3), criteria(intent="rent"))[0] == "wrong_listing_type"
    assert check(listing(4, property_type="maisonette"), criteria(property_types=["apartment"]))[0] == "wrong_type"
    assert check(listing(5, area="Chaidari"), criteria(areas=["Αιγάλεω"]))[0] == "wrong_area"


def test_preferences_rank_but_never_filter():
    c = Criteria.model_validate({
        "user_id": "u", "intent": "buy",
        "hard_limits": {"max_price_eur": 200000},
        "preferences": [{"feature": "floor_level", "min": 3, "weight": 1.0}],
    })
    low, high = listing(1, floor={"raw": "1ος", "class": "1"}), listing(2, floor={"raw": "4ος", "class": "4"})
    assert len(apply_hard_limits([low, high], c).matches) == 2
    assert score(high, c.preferences) > score(low, c.preferences)


def test_unknown_preference_scores_neutral():
    c = Criteria.model_validate({"user_id": "u", "intent": "buy", "preferences": [{"feature": "balcony", "equals": True, "weight": 1}]})
    assert score(listing(1, balcony=None), c.preferences) == 0.5
    assert score(listing(2, balcony=True), c.preferences) == 1.0
