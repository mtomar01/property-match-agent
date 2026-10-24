"""Area statistics, the market lines on a card, and the check-in ladder's fixed questions (D74, D75)."""

from datetime import date, datetime, timezone

from core.models import Criteria, HardLimits, Listing, Swipe
from learning import ladder
from learning.area_stats import AreaStats, market_lines, months_text


def home(n: int, **fields) -> Listing:
    data = {"listing_id": f"xe:{n}", "source": "xe", "url": f"https://synthetic.invalid/xe/{n}",
            "first_seen": date(2026, 10, 1), "last_seen": date(2026, 10, 20), "price_eur": 150000, "size_m2": 75,
            "bedrooms": 2, "year_built": 1975, "property_type": "apartment", "floor": {"raw": "2ος", "class": "2"},
            "area": "Egaleo", "sub_area": "Λιούμη"}
    data.update(fields)
    return Listing.model_validate(data)


def test_the_most_specific_level_with_enough_homes_is_used():
    similar = [home(i, price_eur=150000 + i * 1000) for i in range(8)]  # 2 bedrooms, before 1980, in Egaleo
    newer = [home(100 + i, year_built=2010, sub_area="Άλλη", price_eur=225000) for i in range(3)]
    stats = AreaStats.build(similar + newer)
    typical = stats.typical(similar[0])
    assert typical.level == "similar" and typical.homes == 8 and "2 bedrooms, built before 1980" in typical.label
    # a newer home has only 3 like it and no neighbourhood of 10, so it falls back to the whole area
    fallback = stats.typical(newer[0])
    assert fallback.level == "area" and fallback.homes == 11


def test_too_few_homes_means_no_typical_and_no_line():
    stats = AreaStats.build([home(i) for i in range(4)])
    assert stats.typical(home(9)) is None
    assert [l["feature"] for l in market_lines(home(9), stats)] == []


def test_rentals_and_unknown_sizes_stay_out_of_the_figures():
    stats = AreaStats.build([home(i) for i in range(6)] + [home(50, listing_type="rent", price_eur=600)]
                            + [home(51, size_m2=None)])
    assert len(stats.area["Egaleo"]) == 6 and stats.homes["Egaleo"] == 7


def test_the_price_line_says_under_over_or_about_with_the_share():
    stats = AreaStats.build([home(i) for i in range(8)])  # all €2,000/m²
    cheap = market_lines(home(90, price_eur=120000), stats)[0]
    assert cheap["direction"] == "under" and cheap["share"] == 20 and "20% under the typical €2,000" in cheap["text"]
    near = market_lines(home(91, price_eur=152000), stats)[0]
    assert near["direction"] == "about" and near["share"] == 0 and "about the typical" in near["text"]


def test_time_on_market_needs_a_published_date_and_shows_a_cut():
    stats = AreaStats.build([home(i) for i in range(8)])
    assert all(l["feature"] != "days_on_market" for l in market_lines(home(1), stats))
    listed = home(2, published=date(2026, 4, 20), price_eur=140000,
                  price_history=[{"date": "2026-05-01", "price_eur": 155000}, {"date": "2026-10-01", "price_eur": 140000}])
    line = next(l for l in market_lines(listed, stats) if l["feature"] == "days_on_market")
    assert line["value"] == 183 and line["text"] == "On the market for 6 months, price cut from €155,000"
    assert months_text(3) == "listed this week" and months_text(30) == "on the market for 4 weeks"


def test_area_summary_counts_neighbourhoods_with_ten_homes_only():
    homes = [home(i) for i in range(10)] + [home(20 + i, sub_area="Κέντρο") for i in range(3)]
    summary = AreaStats.build(homes).summary()["Egaleo"]
    assert summary["homes"] == 13 and list(summary["neighbourhoods"]) == ["Λιούμη"]


# -- the ladder's fixed questions ----------------------------------------


def swipe(listing, decision, reasons=()):
    return Swipe(user_id="t", listing_id=listing.listing_id, decision=decision, reasons=list(reasons), deck_position=0,
                 ts=datetime(2026, 10, 23, 12, tzinfo=timezone.utc))


def criteria(**kw):
    return Criteria(user_id="t", intent="buy", areas=["Egaleo"], hard_limits=HardLimits(max_price_eur=250000, **kw))


def test_language_follows_the_users_words():
    assert ladder.language("Θέλω δυάρι στο Αιγάλεω") == "el"
    assert ladder.language("thelo spiti sto Aigaleo mexri 200") == "el"  # Greeklish
    assert ladder.language("A flat in Egaleo please") == "en"


def test_one_tapped_reason_is_enough_to_ask_and_a_declined_one_isnt_asked_again():
    homes = [home(i) for i in range(10)]
    window = [swipe(homes[0], "reject", ["needs_work"])] + [swipe(h, "like") for h in homes[1:]]
    listings = {h.listing_id: h for h in homes}
    question = ladder.reason_question(window, listings, criteria(), homes, set(), "en")
    assert question["key"] == "reason:needs_work" and "one home" in question["reply"]
    assert question["patch"]["preferences"][0] == {"feature": "move_in_ready", "min": None, "max": None, "equals": True, "weight": 0.8}
    assert ladder.reason_question(window, listings, criteria(), homes, {"reason:needs_work"}, "en") is None


def test_a_floor_reason_offers_a_limit_on_the_floor_the_user_turned_down():
    homes = [home(i, floor={"raw": "ισόγειο", "class": "ground"}) for i in range(2)] + [home(5)]
    window = [swipe(homes[0], "reject", ["bad_floor"]), swipe(homes[1], "reject", ["bad_floor"]), swipe(homes[2], "like")]
    question = ladder.reason_question(window, {h.listing_id: h for h in homes}, criteria(), homes, set(), "el")
    assert question["kind"] == "limit" and question["patch"] == {"hard_limits": {"exclude_floors": ["ground"]}}
    assert "ισόγεια" in question["reply"] and "2 σπίτια" in question["reply"]


def test_the_narrowing_line_is_counted_by_code():
    homes = [home(i, size_m2=60, lift=True) for i in range(3)] + [home(9, parking="garage")]
    assert ladder.narrowing_line(homes, "en").startswith("Of the 4 homes in your search, 3 are under 70 m², 1 has parking and 3 have a lift")
