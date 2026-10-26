"""The deck, the reasons on its cards, the swipe log and the patterns code reads from it (D64, D66)."""

from datetime import date, datetime, timezone

import pytest

from adapters.snapshot import SnapshotAdapter
from core.models import Criteria, HardLimits, Swipe
from core.reasons import typical_price_per_m2, why_this_one
from learning import deck, patterns, swipes
from ranking.rules import preference_match

TODAY = date(2026, 10, 23)


@pytest.fixture(scope="module")
def listings():
    return SnapshotAdapter().listings()


def criteria(**kw):
    prefs = kw.pop("preferences", [])
    hard = {"max_price_eur": 250000, "min_price_eur": 100000, **kw}
    return Criteria(user_id="t", intent="buy", areas=["Egaleo"], hard_limits=HardLimits(**hard), preferences=prefs)


def swipe(listing, decision, i=0, reasons=(), explore=False):
    return Swipe(user_id="t", listing_id=listing.listing_id, decision=decision, reasons=list(reasons), deck_position=i,
                 explore_card=explore, ts=datetime(2026, 10, 23, 12, 0, i, tzinfo=timezone.utc))


# -- reasons ----------------------------------------------------------------


def test_reasons_rest_on_fields_the_listing_states(listings):
    c = criteria(preferences=[{"feature": "balcony", "equals": True, "weight": 0.7},
                              {"feature": "floor_level", "min": 2, "weight": 0.5}])
    typical = typical_price_per_m2(listings)
    for listing in deck.ranked_matches(listings, c):
        reasons = why_this_one(listing, c, typical, TODAY)
        assert 1 <= len(reasons) <= 2 and len({r["feature"] for r in reasons}) == len(reasons)
        for r in reasons:
            if r["kind"] == "preference":
                pref = next(p for p in c.preferences if p.feature == r["feature"] or (p.feature == "floor_level" and r["feature"] == "floor"))
                assert preference_match(listing, pref) == 1.0
            if r["feature"] == "balcony":
                assert listing.balcony is True and r["text"] == "Balcony, as you asked"
            if r["feature"] == "price_per_m2":
                assert listing.price_per_m2 == r["value"] < r["typical"] * 0.95
            if r["feature"] == "renovated_year":
                assert listing.renovated_year == r["value"] >= TODAY.year - 10


def test_a_preference_the_home_fails_or_cannot_show_gives_no_reason(listings):
    c = criteria(preferences=[{"feature": "balcony", "equals": True, "weight": 0.9}])
    without = next(l for l in listings if l.balcony is False)
    assert all(r["feature"] != "balcony" for r in why_this_one(without, c, {}, TODAY))
    unknown = next(l for l in listings if l.parking is None)
    c = criteria(preferences=[{"feature": "parking", "equals": True, "weight": 0.9}])
    assert all(r["feature"] != "parking" for r in why_this_one(unknown, c, {}, TODAY))
    assert why_this_one(unknown, c, {}, TODAY), "a card never goes out without a reason"


# -- deck -------------------------------------------------------------------


def test_an_order_the_user_asked_for_is_strict_and_uninterrupted(listings):
    """D98: "cheapest per m² first" sorts the whole deck by that value; no explore card breaks the order, a home
    without the value comes last, and the wishes only decide between equals."""
    c = criteria(preferences=[{"feature": "balcony", "equals": True, "weight": 0.9}])
    strict = Criteria(**{**c.model_dump(), "order_by": "price_per_m2_asc"})
    ranked = deck.ranked_matches(listings, strict)
    values = [l.price_per_m2 for l in ranked]
    known = [v for v in values if v is not None]
    assert known == sorted(known) and values[:len(known)] == known  # ascending, unknowns last
    built = deck.build(listings, strict, set(), limit=10, seed=3)
    assert built["order_by"] == "price_per_m2_asc"
    assert not any(card["explore_card"] for card in built["cards"])
    shown = [card["price_per_m2"] for card in built["cards"]]
    assert shown == sorted(shown)
    biggest = deck.ranked_matches(listings, Criteria(**{**c.model_dump(), "order_by": "size_m2_desc"}))
    sizes = [l.size_m2 for l in biggest if l.size_m2 is not None]
    assert sizes == sorted(sizes, reverse=True)
    assert deck.build(listings, c, set(), limit=10, seed=3)["order_by"] is None  # no order asked: ranked as usual


def test_the_deck_keeps_every_limit_skips_swiped_cards_and_explores_one_in_five(listings):
    c = Criteria(user_id="t", intent="buy", hard_limits=HardLimits(max_price_eur=300000, min_price_eur=100000))
    first = deck.build(listings, c, set(), limit=10, today=TODAY)
    ids = [card["listing_id"] for card in first["cards"]]
    assert len(ids) == len(set(ids)) == 10
    assert [card["explore_card"] for card in first["cards"]] == [False] * 4 + [True] + [False] * 4 + [True]
    assert all(100000 <= card["price_eur"] <= 300000 for card in first["cards"])
    assert [card["deck_position"] for card in first["cards"]] == list(range(10))
    ranked = deck.ranked_matches(listings, c)
    assert ids[0] == ranked[0].listing_id and ranked.index(next(l for l in ranked if l.listing_id == ids[4])) >= len(ranked) // 2
    again = deck.build(listings, c, set(ids[:3]), start_position=3, limit=5, today=TODAY)
    assert not set(a["listing_id"] for a in again["cards"]) & set(ids[:3]) and again["cards"][0]["deck_position"] == 3
    assert again["remaining"] == first["total_matches"] - 3


# -- swipes -----------------------------------------------------------------


def test_the_swipe_log_appends_counts_and_caps(tmp_path, monkeypatch):
    store = swipes.SwipeStore("t", tmp_path)
    store.record("spitogatos:SYN0001", "like", deck_position=0)
    store.record("spitogatos:SYN0002", "reject", ["too_dark", "too_small"], 1, explore_card=True)
    store.record("spitogatos:SYN0003", "like", deck_position=2)
    reloaded = swipes.SwipeStore("t", tmp_path)
    assert reloaded.swiped_ids() == {"spitogatos:SYN0001", "spitogatos:SYN0002", "spitogatos:SYN0003"}
    assert reloaded.liked_ids() == ["spitogatos:SYN0001", "spitogatos:SYN0003"]
    stats = reloaded.stats()
    assert stats["swipes"] == 3 and stats["likes"] == 2 and stats["like_rate"] == 0.667
    assert stats["like_rate_top"] == 1.0 and stats["like_rate_explore"] == 0.0 and stats["reject_reasons"] == {"too_dark": 1, "too_small": 1}
    with pytest.raises(ValueError):
        store.record("spitogatos:SYN0001", "like", ["too_dark"])  # reasons only on a reject
    monkeypatch.setattr(swipes, "DAILY_CAP", 3)
    with pytest.raises(ValueError, match="daily cap"):
        store.record("spitogatos:SYN0004", "like")
    report = swipes.report("t", tmp_path, tmp_path / "out.json")
    assert report["like_rate"] == 0.667 and "listing" not in str(report)


# -- patterns ---------------------------------------------------------------


def test_a_clear_taste_for_recent_builds_is_found_with_the_line_between_the_groups(listings):
    c = criteria()
    matches = deck.ranked_matches(listings, c)
    log = [swipe(l, "like" if (l.year_built or 0) >= 2010 else "reject", i) for i, l in enumerate(matches[:11])]
    found = patterns.observe(log, listings, c, today=TODAY)
    top = found[0]
    assert top["feature"] == "year_built" and top["direction"] == "min"
    assert 2010 <= top["line"] <= 2015, top  # between the newest reject (2008) and the oldest like (2025), rounded to 5
    assert top["evidence"]["likes_in"] == top["evidence"]["likes"] == 3 and top["evidence"]["rejects_out"] == top["evidence"]["rejects"] == 8
    assert top["kind"] == "preference" and top["would_leave"] < patterns.THIN  # too few would remain for a limit
    assert top["patch"]["preferences"][0] == {"feature": "year_built", "min": top["line"], "max": None, "equals": None, "weight": 0.8}


def test_a_limit_is_offered_when_enough_homes_would_remain(listings):
    c = Criteria(user_id="t", intent="buy", hard_limits=HardLimits(max_price_eur=300000, min_price_eur=100000))
    matches = deck.ranked_matches(listings, c)
    log = [swipe(l, "like" if (l.size_m2 or 0) >= 100 else "reject", i) for i, l in enumerate(matches[:14])]
    found = {f["key"]: f for f in patterns.observe(log, listings, c, today=TODAY)}
    size = found["size_m2:min"]
    assert size["kind"] == "limit" and size["would_leave"] >= patterns.THIN
    assert size["patch"] == {"hard_limits": {"min_size_m2": size["line"]}} and size["line"] % 5 == 0
    assert patterns.apply({"hard_limits": {"max_price_eur": 300000}, "preferences": []}, size["patch"])["hard_limits"]["min_size_m2"] == size["line"]


def test_too_few_swipes_or_no_split_say_nothing(listings):
    c = criteria()
    matches = deck.ranked_matches(listings, c)
    assert patterns.observe([swipe(l, "like", i) for i, l in enumerate(matches[:4])], listings, c, today=TODAY) == []
    alternate = [swipe(l, "like" if i % 2 else "reject", i) for i, l in enumerate(matches[:10])]
    keys = {f["key"] for f in patterns.observe(alternate, listings, c, today=TODAY)}
    assert "year_built:min" not in keys


def test_reject_reasons_and_low_floors_make_patterns_of_their_own(listings):
    c = Criteria(user_id="t", intent="buy", hard_limits=HardLimits(max_price_eur=300000, min_price_eur=100000))
    matches = deck.ranked_matches(listings, c)
    low = [l for l in matches if l.floor.floor_class in patterns.LOW_FLOORS][:3]
    high = [l for l in matches if l.floor.floor_class and l.floor.floor_class.isdigit()][:4]
    log = [swipe(l, "reject", i, ["bad_floor"]) for i, l in enumerate(low)] + [swipe(l, "like", 10 + i) for i, l in enumerate(high)]
    found = {f["key"]: f for f in patterns.observe(log, listings, c, today=TODAY)}
    floors = found["floor:exclude"]
    assert floors["kind"] == "limit" and set(floors["line"]) == {l.floor.floor_class for l in low}
    assert floors["would_leave"] >= patterns.THIN and "exclude_floors" in floors["patch"]["hard_limits"]
    pricey = [swipe(l, "reject", i, ["too_expensive"]) for i, l in enumerate(matches[-3:])]
    cheap = [swipe(l, "like", 10 + i) for i, l in enumerate(sorted(matches, key=lambda l: l.price_eur)[:3])]
    found = {f["key"]: f for f in patterns.observe(pricey + cheap, listings, c, today=TODAY)}
    top_like = max(l.price_eur for l in sorted(matches, key=lambda l: l.price_eur)[:3])
    assert found["price_eur:max"]["line"] % 5000 == 0 and found["price_eur:max"]["line"] >= top_like
    by_id = {l.listing_id: l for l in listings}
    from_reasons = patterns._reason_patterns([by_id[s.listing_id] for s in cheap], [(by_id[s.listing_id], s) for s in pricey], c, listings, TODAY)
    assert from_reasons[0]["key"] == "price_eur:max" and "3 rejects marked too expensive" in from_reasons[0]["evidence"]["text"]


def test_a_declined_or_already_held_suggestion_is_not_repeated(listings):
    c = criteria()
    matches = deck.ranked_matches(listings, c)
    log = [swipe(l, "like" if (l.year_built or 0) >= 2010 else "reject", i) for i, l in enumerate(matches[:11])]
    assert all(f["key"] != "year_built:min" for f in patterns.observe(log, listings, c, {"year_built:min"}, today=TODAY))
    held = criteria(preferences=[{"feature": "year_built", "min": 2015, "weight": 0.9}])
    assert all(f["key"] != "year_built:min" for f in patterns.observe(log, listings, held, today=TODAY))
    assert patterns.taken({"hard_limits": {"min_year_built": 2015}, "preferences": []}, {"hard_limits": {"min_year_built": 2015}})
    assert patterns.taken({"hard_limits": {"min_year_built": 2020}, "preferences": []}, {"hard_limits": {"min_year_built": 2015}})
    assert not patterns.taken({"hard_limits": {"min_year_built": None}, "preferences": []}, {"hard_limits": {"min_year_built": 2015}})
    assert not patterns.taken({"preferences": []}, {"preferences": [{"feature": "balcony", "equals": True}]})


def test_skips_and_cant_judge_are_no_verdict_and_undo_takes_the_last_one_back(tmp_path):
    store = swipes.SwipeStore("t", tmp_path)
    store.record("spitogatos:SYN0001", "like")
    store.record("spitogatos:SYN0002", "skip", ["photos_unclear"])
    store.record("spitogatos:SYN0003", "skip")
    store.record("spitogatos:SYN0004", "reject", ["other"], note="Η κουζίνα είναι πολύ μικρή, τηλ 6912345678")
    stats = store.stats()
    assert (stats["swipes"], stats["likes"], stats["rejects"], stats["like_rate"]) == (2, 1, 1, 0.5)  # skips aren't verdicts
    assert (stats["skips"], stats["cant_judge"], stats["cant_judge_reasons"], stats["notes"]) == (2, 1, {"photos_unclear": 1}, 1)
    assert store.load()[-1].note.startswith("Η κουζίνα") and "6912345678" not in store.load()[-1].note
    assert store.swiped_ids() == {"spitogatos:SYN0001", "spitogatos:SYN0004"}
    assert store.skipped_ids() == ["spitogatos:SYN0002", "spitogatos:SYN0003"]
    undone = store.undo()
    assert undone.listing_id == "spitogatos:SYN0004" and len(swipes.SwipeStore("t", tmp_path).load()) == 3  # rewritten on disk
    store.record("spitogatos:SYN0002", "like")  # decided later: no longer waiting as a skip
    assert store.skipped_ids() == ["spitogatos:SYN0003"]
    with pytest.raises(ValueError):
        store.record("spitogatos:SYN0005", "skip", ["too_dark"])  # a reject reason isn't a can't-judge reason
    with pytest.raises(ValueError):
        store.record("spitogatos:SYN0005", "reject", ["too_small"], note="a note needs other")


def test_skipped_homes_come_back_last_and_patterns_ignore_them(listings):
    c = Criteria(user_id="t", intent="buy", hard_limits=HardLimits(max_price_eur=300000, min_price_eur=100000))
    ranked = deck.ranked_matches(listings, c)
    first = ranked[0].listing_id
    built = deck.build(listings, c, set(), limit=len(ranked), today=TODAY, skipped_ids=[first])
    assert built["cards"][-1]["listing_id"] == first and built["cards"][-1]["skipped_before"]
    assert built["remaining"] == len(ranked) and built["skipped_waiting"] == 1
    log = [swipe(l, "like" if (l.size_m2 or 0) >= 100 else "reject", i) for i, l in enumerate(ranked[:14])]
    skips = [Swipe(user_id="t", listing_id=l.listing_id, decision="skip", deck_position=20 + i, ts=log[0].ts) for i, l in enumerate(ranked[14:30])]
    assert patterns.observe(log + skips, listings, c, today=TODAY) == patterns.observe(log, listings, c, today=TODAY)


def test_a_move_in_ready_wish_gets_its_own_reason_not_a_crash(listings):
    # D79: the card's reasons once looked for a field called move_in_ready and crashed the deck
    c = criteria(preferences=[{"feature": "move_in_ready", "equals": True, "weight": 0.9},
                              {"feature": "price_per_m2", "max": 3000, "weight": 0.5}])
    shown = [r for listing in deck.ranked_matches(listings, c) for r in why_this_one(listing, c, {}, TODAY)]
    ready = [r for r in shown if r["feature"] == "move_in_ready"]
    assert ready and all(r["text"].startswith("Ready to move in: ") and r["value"] in ("renovated", "new_build", "good") for r in ready)
    assert all("/m², you asked for up to €3,000/m²" in r["text"] for r in shown if r["feature"] == "price_per_m2")
