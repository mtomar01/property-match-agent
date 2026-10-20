"""The spiti24 card parser, tested on invented cards with the real layout."""

from datetime import date

import pytest

from adapters.spiti24_cards import parse_card


def card(text: str) -> dict:
    return {"source_id": "90000001", "url": "https://www.spiti24.gr/90000001", "area_query": "aigaleo",
            "photo_url": None, "seen": "2026-10-20", "card_text": text}


def test_full_card():
    listing = parse_card(card("22\n207.000 € Διαμέρισμα 86 m2 προς πώληση Αιγάλεω, Λιούμη\n 2 1"), date(2026, 10, 20))
    assert (listing.listing_id, listing.price_eur, listing.size_m2) == ("spiti24:90000001", 207000, 86)
    assert (listing.area, listing.sub_area, listing.property_type) == ("Egaleo", "Λιούμη", "apartment")
    assert (listing.bedrooms, listing.bathrooms) == (2, 1)
    assert listing.floor.floor_class is None  # spiti24 cards don't show the floor


def test_price_drop_becomes_history():
    listing = parse_card(card("23\n179.000 € 16.000 € στις 11/10/2026 Διαμέρισμα 45 m2 προς πώληση Αιγάλεω, Σωτηράκη\n 2 1"), date(2026, 10, 20))
    assert listing.price_eur == 179000
    assert listing.price_history[0].price_eur == 195000
    assert listing.price_history[0].date == date(2026, 10, 11)


def test_region_first_and_new_build():
    listing = parse_card(card("ΝΕΟΔΜΗΤΟ\n10\n492.000 € Διαμέρισμα 120 m2 προς πώληση Αθήνα - Δυτικά Προάστια, Περιστέρι\n 3 2"), date(2026, 10, 20))
    assert (listing.area, listing.sub_area, listing.condition) == ("Peristeri", None, "new_build")


def test_one_number_is_ambiguous_so_both_unknown():
    listing = parse_card(card("6\n265.000 € Διαμέρισμα 73 m2 προς πώληση Αιγάλεω, Λιούμη\n 1"), date(2026, 10, 20))
    assert listing.bedrooms is None and listing.bathrooms is None


def test_types_and_big_numbers():
    listing = parse_card(card("25\n1.300.000 € Κτίριο 1.760 m2 προς πώληση Χαϊδάρι, Δάσος\n 2"), date(2026, 10, 20))
    assert (listing.price_eur, listing.size_m2, listing.property_type) == (1300000, 1760, "building")
    studio = parse_card(card("7\n125.000 € Studio/Γκαρσονιέρα 29 m2 προς πώληση Περιστέρι, Τσαλαβούτα\n 1 1"), date(2026, 10, 20))
    assert studio.property_type == "studio"
    complex_ = parse_card(card("7\n750.000 € Συγκρότημα 600 m2 προς πώληση Αιγάλεω, Λιούμη\n 12 9"), date(2026, 10, 20))
    assert complex_.property_type == "apartment_complex"


def test_mini_card_is_rejected():
    with pytest.raises(ValueError):
        parse_card(card("170.000 € | 80 τ.μ."), date(2026, 10, 20))
