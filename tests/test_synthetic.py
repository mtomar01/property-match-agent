import json

from core import greek
from core.models import Listing
from core.synthetic import OUT_DIR, generate


def test_sixty_listings_across_three_areas_and_sources():
    listings, _ = generate()
    assert len(listings) == 60
    assert {l.source for l in listings} == {"spitogatos", "xe", "spiti24"}
    assert {l.area for l in listings} == {"Egaleo", "Peristeri", "Chaidari"}
    assert all(l.synthetic and l.url.startswith("https://synthetic.invalid/") for l in listings)


def test_deterministic():
    first, _ = generate()
    second, _ = generate()
    assert [l.model_dump() for l in first] == [l.model_dump() for l in second]


def test_duplicates_cover_both_easy_and_hard_cases():
    listings, clusters = generate()
    by_id = {l.listing_id: l for l in listings}
    assert len(clusters) == 12
    sources = [sorted({by_id[i].source for i in c.listing_ids}) for c in clusters]
    assert sum(s == ["spiti24", "spitogatos"] for s in sources) >= 4  # near exact copies
    assert sum("xe" in s for s in sources) >= 4  # reworded copies
    for cluster in clusters:
        members = [by_id[i] for i in cluster.listing_ids]
        assert len({m.area for m in members}) == 1
        assert len({m.floor.floor_class for m in members}) == 1


def test_edge_cases_for_hard_limits_exist():
    listings, _ = generate()
    sales = [l for l in listings if l.listing_type == "sale"]
    assert any(l.price_eur == 200000 for l in sales)
    assert any(l.size_m2 == 70 for l in sales)
    assert any(l.price_eur is None for l in sales)
    assert any(l.bedrooms is None for l in sales)
    assert any(l.floor.floor_class is None for l in sales)
    assert any(l.floor.floor_class == "basement" for l in sales)
    assert any(l.floor.floor_class == "semi_basement" for l in sales)
    assert sum(l.listing_type == "rent" for l in listings) == 6


def test_descriptions_are_readable_by_the_normaliser():
    """The Greek floor words we write must normalise back to the stored class."""
    listings, _ = generate()
    for listing in listings:
        if listing.floor.raw:
            assert greek.normalise_floor(listing.floor.raw) == listing.floor.floor_class


def test_committed_file_matches_generator():
    """data/synthetic/listings.jsonl must be regenerated after generator changes."""
    listings, _ = generate()
    rows = [json.loads(line) for line in (OUT_DIR / "listings.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [Listing.model_validate(r) for r in rows] == listings
