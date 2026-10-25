"""Duplicate listings: the finder's rules, the groups, one card per home, and the eval (D78)."""

import json
import re
from datetime import date

from core.models import Criteria, HardLimits, Listing
from dedupe import finder
from evals.harness import build_duplicate_labels, duplicates_eval
from learning import deck

TEXT = ("Πωλείται φωτεινό διαμέρισμα 80 τ.μ. στον 2ο όροφο, διαμπερές, με δύο υπνοδωμάτια, ανακαινισμένη κουζίνα, "
        "μεγάλο μπαλκόνι και θέση στάθμευσης, κοντά στο μετρό και σε σχολεία.")


def home(n: int, **fields) -> Listing:
    data = {"listing_id": f"xe:{n}", "source": "xe", "url": f"https://synthetic.invalid/xe/{n}",
            "first_seen": date(2026, 10, 1), "last_seen": date(2026, 10, 20), "price_eur": 180000, "size_m2": 80,
            "bedrooms": 2, "bathrooms": 1, "year_built": 1985, "property_type": "apartment",
            "floor": {"raw": "2ος", "class": "2"}, "area": "Egaleo", "sub_area": "Λιούμη", "description": None}
    data.update(fields)
    return Listing.model_validate(data)


def test_a_pair_must_agree_on_size_price_rooms_floor_year_and_bathrooms():
    a = home(1, description=TEXT)
    for change, reason in (({"size_m2": 83}, "size"), ({"price_eur": 200001}, "price"), ({"bedrooms": 3}, "bedrooms"),
                           ({"floor": {"raw": "3ος", "class": "3"}}, "floor"), ({"year_built": 1990}, "building year"),
                           ({"bathrooms": 2}, "bathrooms"), ({"area": "Peristeri"}, "area or listing type")):
        assert finder.compare(a, home(2, description=TEXT, **change)).why_not == reason
    assert finder.compare(home(4, renovated_year=2017), home(5, renovated_year=2024)).why_not == "renovation year"
    # unstated on one side is no disagreement
    assert finder.compare(a, home(3, description=TEXT, floor={}, year_built=None)).why_not is None


def test_the_three_verdicts():
    a = home(1, description=TEXT)
    assert finder.compare(a, home(2, description=TEXT, price_eur=175000)).verdict == "same"  # the same words
    assert finder.compare(home(3, photo_hashes=["abc"]), home(4, photo_hashes=["abc"], sub_area="Άλλη")).verdict == "same"
    assert finder.compare(home(3, photo_hashes=["abc"]), home(4, photo_hashes=["abc"]), use_photos=False).verdict == "borderline"
    assert finder.compare(home(5), home(6)).verdict == "borderline"  # same neighbourhood and year, nothing else
    assert finder.compare(home(5), home(6, sub_area="Άλλη")).verdict == "different"


def test_a_price_on_request_needs_a_photo_or_the_same_words():
    assert finder.compare(home(1, price_eur=None, description=TEXT), home(2, price_eur=None, description=TEXT)).verdict == "same"
    assert finder.compare(home(1, price_eur=None), home(2, price_eur=None)).verdict == "borderline"


def test_a_copy_is_the_same_price_and_size_whatever_the_neighbourhood_is_called():
    # D84: Mike's labels showed a flat listed three or four times, and the two portals naming neighbourhoods differently
    a, b = home(1, source="spitogatos", listing_id="spitogatos:1"), home(2, source="spiti24", listing_id="spiti24:2", floor={})
    third = home(3, floor={}, sub_area="Κέντρο")
    assert {p.verdict for p in finder.pairs([a, b, third])} == {"same"}
    groups = finder.clusters([a, b, third])
    assert [g.listing_ids for g in groups] == [["spiti24:2", "spitogatos:1", "xe:3"]]
    assert {p.verdict for p in finder.pairs([a, home(4, price_eur=181000)])} == {"borderline"}  # €1,000 apart: no copy


def test_a_group_never_chains_two_different_flats_together():
    # D84: a new build's flats share a template. a and b share the wording, b and c are an exact copy, but a and c
    # only look alike (82 and 80 m²): c mustn't be pulled into a and b's group through b.
    words = TEXT.replace("80 τ.μ.", "νεόδμητο")
    a = home(1, size_m2=82, description=words, sub_area="Κέντρο", year_built=None)
    b = home(2, size_m2=80, description=words, sub_area="Άλλη", year_built=None)
    c = home(3, size_m2=80, sub_area="Τρίτη", year_built=None)
    verdicts = {frozenset((p.a, p.b)): p.verdict for p in finder.pairs([a, b, c])}
    assert verdicts[frozenset(("xe:1", "xe:2"))] == "same" and verdicts[frozenset(("xe:2", "xe:3"))] == "same"
    assert verdicts[frozenset(("xe:1", "xe:3"))] != "same"
    assert [g.listing_ids for g in finder.clusters([a, b, c])] == [["xe:2", "xe:3"]]  # the exact copy is the stronger pair


def test_pairs_join_into_one_group_with_its_price_range():
    a, b, c = home(1, description=TEXT, price_eur=180000), home(2, description=TEXT, price_eur=185000), home(3, description=TEXT, price_eur=190000)
    groups = finder.clusters([a, b, c, home(9, size_m2=120)])
    assert len(groups) == 1 and groups[0].listing_ids == ["xe:1", "xe:2", "xe:3"]
    assert (groups[0].price_min_eur, groups[0].price_max_eur, groups[0].decided_by) == (180000, 190000, "code")
    assert any(e.signal == "text" for e in groups[0].evidence)


def test_the_deck_shows_a_home_once_at_its_cheapest_and_one_verdict_covers_all():
    homes = [home(1, description=TEXT, price_eur=190000), home(2, description=TEXT, price_eur=182000), home(3, size_m2=120)]
    dup = finder.index(finder.clusters(homes))
    c = Criteria(user_id="t", intent="buy", areas=["Egaleo"], hard_limits=HardLimits(max_price_eur=250000))
    built = deck.build(homes, c, set(), duplicates=dup)
    assert built["total_matches"] == 2 and built["listings_folded"] == 1
    first = next(card for card in built["cards"] if card["listing_id"] in ("xe:1", "xe:2"))
    assert first["listing_id"] == "xe:2" and first["listed"]["times"] == 2
    assert first["listed"]["others"] == [{"listing_id": "xe:1", "source": "xe", "url": "https://synthetic.invalid/xe/1", "price_eur": 190000}]
    after = deck.build(homes, c, {"xe:1"}, duplicates=dup)  # a verdict on one version settles the home
    assert [card["listing_id"] for card in after["cards"]] == ["xe:3"]


def test_a_group_member_over_the_limit_is_never_the_card():
    homes = [home(1, description=TEXT, price_eur=200000), home(2, description=TEXT, price_eur=185000)]
    c = Criteria(user_id="t", intent="buy", areas=["Egaleo"], hard_limits=HardLimits(max_price_eur=190000))
    built = deck.build(homes, c, set(), duplicates=finder.index(finder.clusters(homes)))
    assert [card["listing_id"] for card in built["cards"]] == ["xe:2"] and built["cards"][0]["listed"]["price_max"] == 200000


def test_the_synthetic_eval_finds_every_known_group_with_photos_and_merges_nothing_wrong_without():
    out = duplicates_eval.synthetic()
    assert out["with_photos"]["precision"] == 1.0 and out["with_photos"]["recall"] == 1.0
    assert out["without_photos"]["precision"] == 1.0 and out["without_photos"]["false_merges"] == []


def test_labels_count_only_where_two_labellers_agree(tmp_path):
    rows = lambda labels: "".join(json.dumps({"a": f"xe:{a}", "b": f"xe:{b}", "label": l}) + "\n" for (a, b), l in labels.items())
    mike, gb = tmp_path / "mike.jsonl", tmp_path / "gb.jsonl"
    mike.write_text(rows({(1, 2): "same", (3, 4): "different", (5, 6): "same"}), encoding="utf-8")
    gb.write_text(rows({(1, 2): "same", (3, 4): "same", (5, 6): "unsure"}), encoding="utf-8")
    agreed, info = duplicates_eval.load_labels([mike, gb])
    assert agreed == {frozenset(("xe:1", "xe:2")): "same"} and info["agreement"] == round(1 / 3, 3)


def test_the_labelling_page_is_blind_and_the_links_page_has_no_listing_text(tmp_path, monkeypatch):
    monkeypatch.setattr(build_duplicate_labels, "OUT", tmp_path)
    synthetic = duplicates_eval.ROOT / "data" / "synthetic" / "listings.jsonl"
    for links_only in (False, True):
        page = build_duplicate_labels.build(synthetic, links_only).read_text(encoding="utf-8")
        data = json.loads(re.search(r"const DATA = (.*);\n", page).group(1))
        assert data["pairs"] and all("verdict" not in json.dumps(p) for p in data["pairs"])
        assert any("text" in p["a"] for p in data["pairs"]) is (not links_only)
