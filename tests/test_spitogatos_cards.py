"""The card parser, tested on made-up cards with the same layout as real ones.

Real cards never go in the public repo, so these are invented, including the
phone number, which must not survive.
"""

from datetime import date

from adapters.spitogatos_cards import _number, parse_card

CARD = {
    "source": "spitogatos",
    "source_id": "1000000001",
    "url": "https://www.spitogatos.gr/aggelia/1000000001",
    "area_query": "aigaleo",
    "photo_url": None,
    "seen": "2026-10-20",
    "card_text": (
        "12\nItem 1 of 12\nΔιαμέρισμα, 86τ.μ.\nΔιαμέρισμα, 86τ.μ.\nΛιούμη (Αιγάλεω)\n\n"
        "Διαμέρισμα Προς Πώληση, όροφος: 2ος, στην περιοχή: Αιγάλεω - Λιούμη. Αποτελείται από: 2 Υ/Δ. "
        "Έχει κατασκευαστεί το 1978 και ανακαινίστηκε το 2019. Η θέρμανση του ακινήτου είναι Αυτόνομη με Φυσικό αέριο, "
        "ενεργειακό πιστοποιητικό: Γ και διαθέτει 1 θέσεις στάθμευσης (1 Στην πιλοτή). Τηλ 6970000000...\n\n"
        "2\nος\n2\nυ/δ\n1\nμπ\n\nΑνανεώθηκε: 20/10/2026\n\n€185.000\n\n€199.000"
    ),
}


def test_parses_structured_parts_and_template_sentences():
    listing = parse_card(CARD, date(2026, 10, 20))
    assert listing.listing_id == "spitogatos:1000000001"
    assert (listing.price_eur, listing.size_m2, listing.bedrooms, listing.bathrooms) == (185000, 86, 2, 1)
    assert listing.price_history[0].price_eur == 199000
    assert listing.floor.floor_class == "2"
    assert (listing.area, listing.sub_area, listing.property_type) == ("Egaleo", "Λιούμη", "apartment")
    assert (listing.year_built, listing.renovated_year) == (1978, 2019)
    assert listing.energy_class.value == "C"
    assert (listing.heating.type, listing.heating.fuel) == ("independent", "gas")
    assert listing.parking == "pilotis"


def test_phone_in_description_is_removed():
    card = dict(CARD)
    listing = parse_card(card, date(2026, 10, 20))
    assert "6970000000" not in (listing.description or "")


def test_card_without_generated_sentence_keeps_its_floor():
    card = dict(CARD, card_text=(
        "12\nItem 1 of 12\nΔιαμέρισμα, 86τ.μ.\nΔιαμέρισμα, 86τ.μ.\nΛιούμη (Αιγάλεω)\n\n"
        "3\nος\n2\nυ/δ\n1\nμπ\n\nΑνανεώθηκε: 20/10/2026\n\n€185.000\n\n€199.000"
    ))
    listing = parse_card(card, date(2026, 10, 20))
    assert (listing.floor.raw, listing.floor.floor_class) == ("3ος", "3")
    assert (listing.bedrooms, listing.bathrooms, listing.price_eur) == (2, 1, 185000)
    assert listing.price_history[0].price_eur == 199000
    assert not listing.description


def test_ground_floor_badge_and_new_build():
    card = dict(CARD, card_text="5\nΜονοκατοικία, 1.760τ.μ.\nΜονοκατοικία, 1.760τ.μ.\nΔάσος (Χαϊδάρι)\n\nΚείμενο.\n\nΙΣ\n3\nυ/δ\n\n€1.300.000\n\nΝΕΟΔΜΗΤΟ")
    listing = parse_card(card, date(2026, 10, 20))
    assert (listing.size_m2, listing.price_eur, listing.floor.floor_class) == (1760, 1300000, "ground")
    assert listing.condition == "new_build" and listing.area == "Chaidari"


def test_greek_numbers():
    assert _number("1.760") == 1760
    assert _number("105,20") == 105.2


def test_a_rental_card_reads_its_monthly_price_and_keeps_its_kind():
    """D102: a rental card's price line ends "/ μήνα"; the collector's listing_type rides on the card."""
    card = dict(CARD, listing_type="rent", card_text=CARD["card_text"].replace("€185.000\n\n€199.000", "€650 / μήνα"))
    listing = parse_card(card, date(2026, 10, 29))
    assert listing.listing_type == "rent" and listing.price_eur == 650 and listing.price_history == []
    assert parse_card(CARD, date(2026, 10, 20)).listing_type == "sale"  # an older card without the field is a sale

