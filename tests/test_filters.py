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


def test_energy_preference_uses_letters():
    c = Criteria.model_validate({"user_id": "u", "intent": "buy", "preferences": [{"feature": "energy_class", "min": "B", "weight": 1}]})
    good = listing(1, energy_class={"raw": "Β+", "value": "B+"})
    bad = listing(2, energy_class={"raw": "Δ", "value": "D"})
    assert score(good, c.preferences) == 1.0 and score(bad, c.preferences) == 0.0


def test_unknown_preference_feature_is_refused():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Criteria.model_validate({"user_id": "u", "intent": "buy", "preferences": [{"feature": "brightness", "min": 3, "weight": 1}]})


def test_price_per_m2_limit_needs_both_price_and_size():
    c = criteria(max_price_per_m2=2000)
    assert check(listing(1, price_eur=150000, size_m2=80), c) is None  # 1,875
    assert check(listing(2, price_eur=170000, size_m2=80), c) == ("over_price_per_m2", "price_per_m2")  # 2,125
    assert check(listing(3, price_eur=150000, size_m2=None), c) == ("unknown", "price_per_m2")


def test_no_stairs_limit_lets_a_lift_through_and_fails_closed_on_unknowns():
    c = criteria(max_floor_without_lift=1)
    floor = lambda f: {"raw": f, "class": f}  # noqa: E731
    assert check(listing(1, floor=floor("1"), lift=False), c) is None  # one floor of stairs is allowed
    assert check(listing(2, floor=floor("4"), lift=True), c) is None  # a lift makes any floor fine
    assert check(listing(3, floor=floor("3"), lift=False), c) == ("stairs_without_lift", "floor")
    assert check(listing(4, floor=floor("3"), lift=None), c) == ("unknown", "lift")
    assert check(listing(5, floor=floor("top"), lift=False), c) == ("unknown", "floor")  # a ρετιρέ's height is unknown
    assert check(listing(6, floor={"raw": None, "class": None}, lift=True), c) is None
    assert check(listing(7, floor={"raw": None, "class": None}, lift=None), c) == ("unknown", "floor")
    ground_or_lift = criteria(max_floor_without_lift=0)
    assert check(listing(8, floor=floor("raised_ground"), lift=False), ground_or_lift) == ("stairs_without_lift", "floor")
    assert check(listing(9, floor=floor("ground"), lift=False), ground_or_lift) is None


def test_condition_limit_and_the_move_in_ready_wish():
    from core.models import Preference
    c = criteria(exclude_conditions=["needs_work", "unfinished"])
    assert check(listing(1, condition="renovated"), c) is None
    assert check(listing(2, condition="needs_work"), c) == ("excluded_condition", "condition")
    assert check(listing(3, condition=None), c) == ("unknown", "condition")
    wish = [Preference(feature="move_in_ready", equals=True, weight=0.8)]
    assert score(listing(4, condition="new_build"), wish) == 1.0
    assert score(listing(5, condition="needs_work"), wish) == 0.0
    assert score(listing(6, condition=None), wish) == 0.5  # unknown: neither rewarded nor punished


# -- D79: what a user says outright becomes a hard limit for fields listings reliably state --------


def test_must_haves_fail_closed_on_an_unstated_value():
    c = criteria(max_price_eur=200000, must_have=["parking", "lift"])
    assert check(listing(1, parking="space", lift=True), c) is None
    assert check(listing(2, parking="none", lift=True), c) == ("no_parking", "parking")
    assert check(listing(3, parking=None, lift=True), c) == ("unknown", "parking")
    assert check(listing(4, parking="garage", lift=False), c) == ("no_lift", "lift")


def test_bathrooms_floor_levels_and_metro():
    assert check(listing(1, bathrooms=1), criteria(min_bathrooms=2)) == ("too_few_bathrooms", "bathrooms")
    assert check(listing(2, bathrooms=None), criteria(min_bathrooms=2)) == ("unknown", "bathrooms")
    band = criteria(min_floor_level=2, max_floor_level=4)
    assert check(listing(3), band) is None  # the 2nd floor
    assert check(listing(4, floor={"raw": "1ος", "class": "1"}), band) == ("floor_too_low", "floor")
    assert check(listing(5, floor={"raw": "6ος", "class": "6"}), band) == ("floor_too_high", "floor")
    assert check(listing(6, floor={"raw": "ρετιρέ", "class": "top"}), band) == ("unknown", "floor")  # no number (D51)
    assert check(listing(7, metro_walk_min=12), criteria(max_metro_walk_min=10)) == ("far_from_metro", "metro_walk_min")
    assert check(listing(8), criteria(max_metro_walk_min=10)) == ("unknown", "metro_walk_min")


def test_renovated_since_is_a_renovation_or_a_build_from_that_year():
    since = criteria(min_renovated_year=2021)
    assert check(listing(1, renovated_year=2022), since) is None
    assert check(listing(2, year_built=2024), since) is None  # a new build counts
    assert check(listing(3, renovated_year=2017), since) == ("renovated_earlier", "renovated_year")
    assert check(listing(4, condition="needs_work"), since) == ("needs_work", "condition")
    assert check(listing(5, condition="renovated"), since) == ("unknown", "renovated_year")  # renovated, but when?


def test_firm_wishes_become_limits_and_soft_ones_stay_wishes():
    from core.card_rules import search_card
    raw = {"intent": "buy", "hard_limits": {"max_price_eur": 200000, "min_year_built": 2010},
           "preferences": [{"feature": "parking", "equals": True, "weight": 0.6, "firm": True},
                           {"feature": "balcony", "equals": True, "weight": 0.6, "firm": False},
                           {"feature": "year_built", "min": 2000, "weight": 0.7, "firm": True},
                           {"feature": "floor_level", "min": 2, "max": 4, "weight": 0.6, "firm": True},
                           {"feature": "lift", "equals": False, "weight": 0.5, "firm": True},
                           {"feature": "metro_walk_min", "max": 10, "weight": 0.8, "firm": True}]}
    applied = search_card(raw)
    limits = applied["hard_limits"]
    assert limits["must_have"] == ["parking"] and limits["min_floor_level"] == 2 and limits["max_floor_level"] == 4
    assert limits["min_year_built"] == 2010  # a looser firm wish never loosens a stricter limit
    assert [p["feature"] for p in applied["preferences"]] == ["balcony", "lift", "metro_walk_min"]
    assert applied["from_wishes"] == ["parking", "year_built", "floor_level"]


def test_a_must_for_some_property_types_only():
    # D86: parking a must if it's a house; apartments don't need it; a house that doesn't say fails closed
    c = criteria(max_price_eur=400000, property_types=["apartment", "detached_house"], must_have_if_type={"detached_house": ["parking"]})
    assert check(listing(1, parking="none"), c) is None  # an apartment without parking is fine
    assert check(listing(2, property_type="detached_house", parking="garage"), c) is None
    assert check(listing(3, property_type="detached_house", parking="none"), c) == ("no_parking", "parking")
    assert check(listing(4, property_type="detached_house", parking=None), c) == ("unknown", "parking")
    assert check(listing(5, property_type=None), c) == ("unknown", "property_type")


def test_a_firm_wish_tied_to_a_type_becomes_a_must_for_that_type_only():
    from core.card_rules import search_card
    raw = {"intent": "buy", "hard_limits": {"max_price_eur": 300000},
           "preferences": [{"feature": "parking", "equals": True, "weight": 0.9, "firm": True, "only_for_types": ["detached_house", "building"]},
                           {"feature": "renovated_year", "min": 2021, "weight": 0.8, "firm": True, "only_for_types": ["detached_house"]}]}
    applied = search_card(raw)
    assert applied["hard_limits"]["must_have_if_type"] == {"detached_house": ["parking"], "building": ["parking"]}
    assert "must_have" not in applied["hard_limits"] and "min_renovated_year" not in applied["hard_limits"]
    assert [p["feature"] for p in applied["preferences"]] == ["renovated_year"]  # can't be promised for one type: a wish


def test_the_interview_writes_the_types_as_one_string():
    from core.card_rules import search_card
    raw = {"intent": "buy", "hard_limits": {"max_price_eur": 300000},
           "preferences": [{"feature": "parking", "equals": True, "weight": 0.9, "firm": True, "only_for_types": "detached_house"},
                           {"feature": "balcony", "equals": True, "weight": 0.6, "firm": False, "only_for_types": ""}]}
    applied = search_card(raw)
    assert applied["hard_limits"]["must_have_if_type"] == {"detached_house": ["parking"]}
    assert [p["feature"] for p in applied["preferences"]] == ["balcony"]


def test_furnished_is_a_must_in_a_rent_search_only():
    # D104: said outright by a renter, furnished hides the unfurnished and the silent; for a buyer it stays a wish
    from core.card_rules import search_card
    wish = {"feature": "furnished", "equals": True, "weight": 0.8, "firm": True}
    rent = search_card({"intent": "rent", "hard_limits": {"max_price_eur": 800}, "preferences": [wish]})
    assert rent["hard_limits"]["must_have"] == ["furnished"] and rent["preferences"] == []
    buy = search_card({"intent": "buy", "hard_limits": {"max_price_eur": 200000}, "preferences": [wish]})
    assert "must_have" not in buy["hard_limits"] and [p["feature"] for p in buy["preferences"]] == ["furnished"]
    soft = search_card({"intent": "rent", "hard_limits": {"max_price_eur": 800}, "preferences": [dict(wish, firm=False)]})
    assert "must_have" not in soft["hard_limits"]
    c = criteria(intent="rent", max_price_eur=800, must_have=["furnished"])
    flat = dict(listing_type="rent", price_eur=700)
    assert check(listing(1, furnished=True, **flat), c) is None
    assert check(listing(2, furnished=False, **flat), c) == ("no_furnished", "furnished")
    assert check(listing(3, **flat), c) == ("unknown", "furnished")  # a page that says neither fails closed
    assert check(listing(4, furnished=True), c) is not None  # a sale never reaches a rent search


def test_a_furnished_wish_ranks_furnished_homes_first():
    from core.models import Preference
    wish = Preference(feature="furnished", equals=True, weight=1)
    assert score(listing(1, furnished=True), [wish]) > score(listing(2), [wish]) > score(listing(3, furnished=False), [wish])
