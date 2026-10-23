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
