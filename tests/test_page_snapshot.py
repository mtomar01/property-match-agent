"""The D68 pipeline: a result card plus a listing page become one checked Listing (no private data, no calls)."""

import pytest

from adapters.page_snapshot import to_listing
from adapters.snapshot import SnapshotAdapter


@pytest.fixture()
def card():
    listing = SnapshotAdapter().listings()[0]
    return listing.model_dump(by_alias=True, mode="json")


def test_the_page_fills_what_the_card_left_out_and_the_page_price_wins(card):
    record = {"seen": "2026-10-20", "sections": {"Περιγραφή": "Πλήρως ανακαινισμένο διαμέρισμα, κοντά στο μετρό."}}
    fields = {"price_eur": card["price_eur"] - 5000, "size_m2": card["size_m2"], "property_type": "apartment", "bedrooms": 2,
              "bathrooms": 1, "floor_class": "3", "year_built": 1978, "renovated_year": 2022, "energy_class": "C",
              "heating_type": "independent", "heating_fuel": "gas", "parking": "pilotis", "lift": True, "balcony": True,
              "storage": False, "flags": ["corner"], "metro_walk_min": 6, "condition": "renovated"}
    listing = to_listing(card, record, fields, {"renovated_year": "ανακαινισμένο το 2022"}, {"floor_raw": "3ος", "energy_raw": "Γ"})
    assert (listing.year_built, listing.renovated_year, listing.metro_walk_min) == (1978, 2022, 6)
    assert listing.floor.floor_class == "3" and listing.energy_class.value == "C" and listing.heating.fuel == "gas"
    assert listing.price_eur == card["price_eur"] - 5000 and listing.price_history[-1].price_eur == listing.price_eur
    assert listing.area == card["area"] and listing.url == card["url"] and listing.evidence["renovated_year"].startswith("ανακαινισμένο")
    assert listing.description.startswith("Πλήρως")


def test_contact_details_in_a_page_are_scrubbed_never_stored(card):
    record = {"seen": "2026-10-20", "sections": {"Περιγραφή": "Τηλ. 6912345678, info@example.gr. Φωτεινό διαμέρισμα."}}
    listing = to_listing(card, record, {"price_eur": card["price_eur"], "size_m2": card["size_m2"]}, {}, {})
    assert "6912345678" not in listing.description and "@" not in listing.description


def test_raw_cards_and_pages_build_a_dataset_and_a_missing_page_keeps_its_card(tmp_path, monkeypatch):
    import json

    from adapters import page_snapshot
    from test_spitogatos_cards import CARD

    kypseli = dict(CARD, source_id="1000000002", url="https://www.spitogatos.gr/aggelia/1000000002", area_query="kypseli",
                   card_text=CARD["card_text"].replace("Λιούμη (Αιγάλεω)", "Κυψέλη (Αθήνα - Κέντρο)"))
    cards = tmp_path / "cards_kypseli.jsonl"
    cards.write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in (CARD, kypseli)), encoding="utf-8")
    page = {"source_id": "1000000002", "url": kypseli["url"], "seen": "2026-10-23", "photo_url": "https://example.invalid/1.jpg",
            "sections": {"Περιγραφή": "Ανακαινισμένο διαμέρισμα. Τηλ 6970000000.", "Χαρακτηριστικά": "Τιμή\n€185.000\nΈτος κατασκευής\n1972"},
            "crossed": {"Εσωτερικό": ["Ασανσέρ"]}}
    pages = tmp_path / "pages_kypseli.jsonl"
    pages.write_text(json.dumps(page, ensure_ascii=False) + "\n", encoding="utf-8")
    monkeypatch.setattr(page_snapshot, "read_one", lambda *a, **k: {"raw": None, "cached": True})  # no model call in tests
    out = tmp_path / "snapshot.jsonl"
    summary = page_snapshot.build([pages], None, out, raw_cards=[cards])
    assert summary["listings"] == 2 and summary["with_page"] == 1 and summary["card_only"] == 1
    assert summary["by_area"] == {"Egaleo": 1, "Kypseli": 1}
    rows = {json.loads(l)["listing_id"]: json.loads(l) for l in out.read_text(encoding="utf-8").splitlines()}
    built = rows["spitogatos:1000000002"]
    assert built["area"] == "Kypseli" and built["year_built"] == 1972 and built["lift"] is False  # crossed out on the page
    assert built["photo_urls"] == ["https://example.invalid/1.jpg"] and "6970000000" not in built["description"]


def test_the_covered_areas_follow_the_data_and_the_prompt_says_where_they_are():
    from agent import interview
    from adapters.snapshot import data_areas
    from core import models

    assert interview.areas_note().startswith("All three are in Athens, in its western suburbs")
    try:
        models.set_covered_areas(["Pagrati", "Egaleo", "Kypseli"])
        assert models.covered_areas() == ("Egaleo", "Pagrati", "Kypseli")
        assert models.Criteria(user_id="t", intent="buy", areas=["Κυψέλη"]).areas == ["Kypseli"]
        assert "Pagrati and Kypseli in the centre" in interview.areas_note()
        assert interview.tool()["input_schema"]["properties"]["areas"]["items"]["enum"] == ["Egaleo", "Pagrati", "Kypseli"]
    finally:
        models.set_covered_areas(models.SEARCH_AREAS)
    with pytest.raises(ValueError):
        models.Criteria(user_id="t", intent="buy", areas=["Kypseli"])  # the default three again
    assert sorted(data_areas(SnapshotAdapter().listings())) == ["Chaidari", "Egaleo", "Peristeri"]
