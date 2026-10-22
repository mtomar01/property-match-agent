from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from core.models import Criteria, DuplicateCluster, Floor, HardLimits, Listing, Swipe


def make_listing(**overrides) -> Listing:
    data = {
        "listing_id": "xe:123456789",
        "source": "xe",
        "url": "https://www.xe.gr/property/d/123456789",
        "first_seen": date(2026, 10, 20),
        "last_seen": date(2026, 10, 27),
        "price_eur": 185000,
        "size_m2": 82,
        "bedrooms": 2,
        "floor": {"raw": "3ος", "class": "3"},
        "energy_class": {"raw": "Γ", "value": "C"},
        "heating": {"raw": "Αυτόνομη, φυσικό αέριο", "type": "independent", "fuel": "gas"},
        "area": "Egaleo",
    }
    data.update(overrides)
    return Listing.model_validate(data)


def test_spec_example_listing_round_trips():
    listing = make_listing()
    assert listing.price_per_m2 == 2256
    dumped = listing.model_dump(by_alias=True, mode="json")
    assert dumped["floor"] == {"raw": "3ος", "class": "3"}
    assert Listing.model_validate(dumped) == listing


def test_price_on_request_has_no_price_per_m2():
    assert make_listing(price_eur=None).price_per_m2 is None


def test_unknown_fields_are_refused():
    with pytest.raises(ValidationError):
        make_listing(agent_name="Γιώργος Παπαδόπουλος")


def test_contact_details_in_text_are_refused():
    with pytest.raises(ValidationError, match="contact details"):
        make_listing(description="Πληροφορίες στο 6971234567")


def test_photos_must_be_links():
    with pytest.raises(ValidationError):
        make_listing(photo_urls=["/tmp/photo.jpg"])


def test_listing_id_must_match_source():
    with pytest.raises(ValidationError):
        make_listing(listing_id="spitogatos:1", source="xe")


def test_floor_from_raw():
    assert Floor.from_raw("Ημιυπόγειο").floor_class == "semi_basement"
    with pytest.raises(ValidationError):
        Floor(raw="x", floor_class="attic")


def test_criteria_normalises_areas_and_floors():
    criteria = Criteria.model_validate(
        {
            "user_id": "u_01",
            "intent": "buy",
            "areas": ["Αιγάλεω", "aigaleo", "Peristeri"],
            "hard_limits": {"max_price_eur": 200000, "exclude_floors": ["υπόγειο", "semi_basement"]},
        }
    )
    assert criteria.areas == ["Egaleo", "Peristeri"]
    assert criteria.hard_limits.exclude_floors == ["basement", "semi_basement"]


def test_criteria_rejects_unsupported_area():
    with pytest.raises(ValidationError, match="isn't covered"):
        Criteria(user_id="u", intent="buy", areas=["Kypseli"])
    with pytest.raises(ValidationError, match="isn't covered"):  # an Area for the clean test, not for search (D46)
        Criteria(user_id="u", intent="buy", areas=["Παγκράτι"])


def test_hard_limit_ranges_must_make_sense():
    with pytest.raises(ValidationError):
        HardLimits(min_price_eur=300000, max_price_eur=200000)


def test_preference_needs_a_target():
    with pytest.raises(ValidationError):
        Criteria.model_validate({"user_id": "u", "intent": "buy", "preferences": [{"feature": "balcony", "weight": 0.5}]})


def test_swipe_reasons_only_on_reject():
    ts = datetime(2026, 10, 21, 19, 42, tzinfo=timezone.utc)
    Swipe(user_id="u", listing_id="xe:1", decision="reject", reasons=["too_dark"], deck_position=7, ts=ts)
    with pytest.raises(ValidationError):
        Swipe(user_id="u", listing_id="xe:1", decision="like", reasons=["too_dark"], deck_position=7, ts=ts)


def test_duplicate_cluster_label():
    cluster = DuplicateCluster(
        cluster_id="c1", listing_ids=["xe:1", "spitogatos:2", "spiti24:3"], price_min_eur=185000, price_max_eur=199000
    )
    assert cluster.label() == "Listed 3 times, €185k to €199k"
    with pytest.raises(ValidationError):
        DuplicateCluster(cluster_id="c2", listing_ids=["xe:1"])
