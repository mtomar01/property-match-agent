"""The learned ranking: a logistic regression on the user's likes and rejects, blended with the rules (D76)."""

from datetime import date, datetime, timezone

from core.models import Criteria, HardLimits, Listing, Swipe
from learning import deck
from learning.area_stats import AreaStats
from learning.learned import FULL_TRUST, Learner, auc, features, precision_at, FEATURES


def home(n: int, **fields) -> Listing:
    data = {"listing_id": f"xe:{n}", "source": "xe", "url": f"https://synthetic.invalid/xe/{n}",
            "first_seen": date(2026, 10, 1), "last_seen": date(2026, 10, 20), "price_eur": 150000 + n * 100,
            "size_m2": 75, "bedrooms": 2, "year_built": 1985, "property_type": "apartment",
            "floor": {"raw": "2ος", "class": "2"}, "area": "Egaleo", "sub_area": "Λιούμη"}
    data.update(fields)
    return Listing.model_validate(data)


def swipe(listing: Listing, decision: str, i: int = 0, reasons=()) -> Swipe:
    return Swipe(user_id="t", listing_id=listing.listing_id, decision=decision, reasons=list(reasons), deck_position=i,
                 ts=datetime(2026, 10, 23, 12, 0, i % 60, tzinfo=timezone.utc))


CRITERIA = Criteria(user_id="t", intent="buy", areas=["Egaleo"], hard_limits=HardLimits(max_price_eur=250000))


def balcony_lover(n: int = 20):
    homes = [home(i, balcony=i % 2 == 0) for i in range(n)]
    swipes = [swipe(h, "like" if h.balcony else "reject", i) for i, h in enumerate(homes)]
    return homes, swipes


def test_nothing_is_learned_until_there_are_three_of_each():
    homes = [home(i) for i in range(8)]
    swipes = [swipe(h, "like", i) for i, h in enumerate(homes[:6])] + [swipe(homes[6], "reject", 6), swipe(homes[7], "reject", 7)]
    assert Learner.fit(swipes, {h.listing_id: h for h in homes}, CRITERIA, AreaStats.build(homes)) is None
    skips = [swipe(h, "skip", 10 + i) for i, h in enumerate(homes)]  # a skip is no verdict (D71)
    assert Learner.fit(swipes + skips, {h.listing_id: h for h in homes}, CRITERIA, AreaStats.build(homes)) is None


def test_a_clear_taste_is_learned_and_explained():
    homes, swipes = balcony_lover()
    model = Learner.fit(swipes, {h.listing_id: h for h in homes}, CRITERIA, AreaStats.build(homes))
    with_balcony, without = home(90, balcony=True), home(91, balcony=False)
    assert model.probability(with_balcony) > 0.7 > 0.3 > model.probability(without)
    assert model.explain(1)[0][0] == "balcony"
    lean = model.summary()["leans"][0]
    assert (lean["feature"], lean["direction"], lean["words"]) == ("balcony", "for", "a balcony")


def test_the_swipes_take_over_gradually_until_thirty():
    homes, swipes = balcony_lover(16)
    model = Learner.fit(swipes, {h.listing_id: h for h in homes}, CRITERIA, AreaStats.build(homes))
    assert model.trust() == 16 / FULL_TRUST and model.summary()["share"] == round(16 / FULL_TRUST, 2)
    assert model.summary()["leans"]  # 10 or more verdicts: leanings can show
    homes, swipes = balcony_lover(40)
    assert Learner.fit(swipes, {h.listing_id: h for h in homes}, CRITERIA, AreaStats.build(homes)).trust() == 1.0


def test_few_verdicts_show_no_leanings():
    homes, swipes = balcony_lover(8)
    model = Learner.fit(swipes, {h.listing_id: h for h in homes}, CRITERIA, AreaStats.build(homes))
    assert model.summary()["leans"] == []


def test_a_reject_with_a_reason_counts_double():
    homes = [home(i, balcony=i % 2 == 0, lift=i % 3 == 0) for i in range(24)]
    plain = [swipe(h, "like" if h.balcony else "reject", i) for i, h in enumerate(homes)]
    tapped = [swipe(h, "like" if h.balcony else "reject", i, ["bad_floor"] if not h.balcony else ()) for i, h in enumerate(homes)]
    by_id, stats = {h.listing_id: h for h in homes}, AreaStats.build(homes)
    b = FEATURES.index("balcony")
    assert abs(Learner.fit(tapped, by_id, CRITERIA, stats).weights[b]) > abs(Learner.fit(plain, by_id, CRITERIA, stats).weights[b])


def test_unknown_is_neither_for_nor_against():
    x = features(home(1, balcony=None, lift=None), CRITERIA, AreaStats.build([home(2)]))
    assert x[FEATURES.index("balcony")] == 0.5 and x[FEATURES.index("lift")] == 0.5
    assert x[FEATURES.index("year_unknown")] == 0.0 and features(home(3, year_built=None), CRITERIA, AreaStats())[FEATURES.index("year_unknown")] == 1.0


def test_the_interview_score_is_a_feature_so_the_swipes_can_weigh_it():
    wished = Criteria(user_id="t", intent="buy", areas=["Egaleo"], hard_limits=HardLimits(max_price_eur=250000),
                      preferences=[{"feature": "balcony", "equals": True, "weight": 0.8}])
    assert features(home(1, balcony=True), wished, AreaStats())[FEATURES.index("stated_wishes")] == 1.0
    assert features(home(1, balcony=True), CRITERIA, AreaStats())[FEATURES.index("stated_wishes")] == 0.0


def test_auc_and_precision_at_ten():
    assert auc([0.9, 0.8, 0.2, 0.1], [1, 1, 0, 0]) == 1.0
    assert auc([0.5, 0.5], [1, 0]) == 0.5 and auc([0.3], [1]) is None
    assert precision_at([0.9, 0.1, 0.8], [1, 0, 0], k=2) == 0.5


def test_the_deck_ranks_by_the_blend_and_says_how_much_it_learned():
    homes, swipes = balcony_lover(30)
    fresh = [home(100 + i, balcony=i >= 3) for i in range(6)]  # the three with a balcony are the dearest
    everything = homes + fresh
    model = Learner.fit(swipes, {h.listing_id: h for h in everything}, CRITERIA, AreaStats.build(everything))
    built = deck.build(everything, CRITERIA, {s.listing_id for s in swipes}, limit=3, learner=model)
    assert sorted(c["listing_id"] for c in built["cards"]) == ["xe:103", "xe:104", "xe:105"]
    assert built["learning"]["verdicts"] == 30 and built["learning"]["share"] == 1.0
    assert all(c["learned_score"] is not None for c in built["cards"])
    plain = deck.build(everything, CRITERIA, {s.listing_id for s in swipes}, limit=3)
    assert plain["learning"] is None and plain["cards"][0]["learned_score"] is None
