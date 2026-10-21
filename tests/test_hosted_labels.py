"""The hosted labelling page and label agreement, on invented listings only."""

import json
import re

import pytest
from pydantic import ValidationError

from evals.harness.agreement import compare
from evals.harness.build_label_tool import HOSTED_KEYS, build_hosted
from evals.harness.labels import ExtractionLabel

DESCRIPTION = "Invented description that must never reach the hosted page."


def write_inputs(tmp_path, n=3):
    raw, cards = [], []
    for i in range(n):
        sid = f"9000000{i}"
        raw.append({
            "source_id": sid, "url": f"https://synthetic.invalid/{sid}", "seen": "2026-10-20",
            "sections": {"Περιγραφή": DESCRIPTION, "Χαρακτηριστικά": "Τιμή\n€150.000\nΕμβαδόν\n70τ.μ.",
                         "Εσωτερικό": "Ασανσέρ"},
        })
        cards.append({"listing_id": f"spitogatos:{sid}", "title": "Διαμέρισμα, 70τ.μ.", "area": "Chaidari", "bedrooms": 2})
    raw_path, snap_path = tmp_path / "raw.jsonl", tmp_path / "snap.jsonl"
    raw_path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in raw), encoding="utf-8")
    snap_path.write_text("\n".join(json.dumps(c, ensure_ascii=False) for c in cards), encoding="utf-8")
    return raw_path, snap_path


def test_hosted_page_carries_links_and_facts_only(tmp_path):
    raw_path, snap_path = write_inputs(tmp_path)
    out = tmp_path / "hosted.html"
    assert build_hosted(2, 0, raw_path, snap_path, out) == out
    html = out.read_text(encoding="utf-8")
    payload = json.loads(re.search(r'<script type="application/json" id="data">(.*?)</script>', html, re.S).group(1))
    assert len(payload["items"]) == 2
    for item in payload["items"]:
        assert set(item) <= set(HOSTED_KEYS)
        assert item["prefill"]["price_eur"] == 150000 and item["prefill"]["lift"] is True
    assert DESCRIPTION not in html and "Ασανσέρ" not in html
    assert "<!doctype" not in html.lower() and "<body" not in html  # the artifact skeleton is added at publish
    assert "<title>Property Match Labels</title>" in html and "__TITLE__" not in html


def test_a_later_batch_is_its_own_page_numbered_in_the_full_order(tmp_path):
    raw_path, snap_path = write_inputs(tmp_path, n=5)
    out = build_hosted(2, 2, raw_path, snap_path, tmp_path / "batch2.html")
    html = out.read_text(encoding="utf-8")
    payload = json.loads(re.search(r'<script type="application/json" id="data">(.*?)</script>', html, re.S).group(1))
    assert [item["number"] for item in payload["items"]] == [3, 4]
    assert "<title>Property Match Labels 3–4</title>" in html


def test_batch_one_keeps_the_file_its_page_was_published_from():
    from evals.harness.build_label_tool import hosted_path

    assert hosted_path(20, 0).name == "property-match-labels.html"
    assert hosted_path(20, 20).name == "property-match-labels-21-40.html"


def label(listing, **fields):
    base = {"price_eur": 150000, "floor_class": "2", "parking": None}
    base.update(fields.pop("fields", {}))
    record = {"listing_id": listing, "labeller": "mt", "labelled_at": "2026-10-21", "round": 1,
              "fields": base, "prefilled": ["price_eur", "floor_class"]}
    record.update(fields)
    return ExtractionLabel.model_validate(record)


def test_live_page_status_is_checked():
    assert label("spitogatos:1", live_page="changed").live_page == "changed"
    with pytest.raises(ValidationError):
        label("spitogatos:1", live_page="moved")


def test_agreement_counts_blanks_as_answers_and_skips_gone_listings():
    first = [label("spitogatos:1"), label("spitogatos:2"), label("spitogatos:3")]
    second = [
        label("spitogatos:1"),
        label("spitogatos:2", fields={"floor_class": "raised_ground", "parking": "pilotis"}),
        label("spitogatos:3", live_page="gone"),
    ]
    result = compare(first, second)
    assert result.listings == 2 and result.skipped_gone == 1
    assert result.per_field["price_eur"] == [2, 2]
    assert result.per_field["floor_class"] == [1, 2]  # pre-filled field
    assert result.per_field["parking"] == [1, 2]  # free-text field
    assert result.per_field["lift"] == [2, 2]  # both blank agrees
    assert result.structured == [3, 4]
    assert {(d[0], d[1]) for d in result.disagreements} == {("spitogatos:2", "floor_class"), ("spitogatos:2", "parking")}


def test_agreement_sets_sample_only_other_peoples_listings_and_repeat():
    from evals.harness.agreement_sets import choose

    by = {"a": [f"spitogatos:{i}" for i in range(0, 30)], "b": [f"spitogatos:{i}" for i in range(30, 50)]}
    first = choose(by, 10, seed=7)
    assert first == choose(by, 10, seed=7)  # seeded, so it can be rebuilt and checked
    assert not set(first["a"]) & set(by["a"]) and not set(first["b"]) & set(by["b"])
    assert len(first["a"]) == 10 and len(set(first["a"])) == 10


def test_selection_page_keeps_full_order_numbers_and_no_labels(tmp_path):
    from evals.harness.build_label_tool import build_hosted_selection

    raw_path, snap_path = write_inputs(tmp_path, n=4)
    out = build_hosted_selection(["spitogatos:90000003", "spitogatos:90000000"], "Someone's Agreement Set",
                                 tmp_path / "set.html", raw_path, snap_path)
    html = out.read_text(encoding="utf-8")
    payload = json.loads(re.search(r'<script type="application/json" id="data">(.*?)</script>', html, re.S).group(1))
    assert [item["listing_id"] for item in payload["items"]] == ["spitogatos:90000003", "spitogatos:90000000"]
    assert all(set(item) <= set(HOSTED_KEYS) for item in payload["items"])
    with pytest.raises(ValueError):
        build_hosted_selection(["spitogatos:1"], "x", tmp_path / "bad.html", raw_path, snap_path)
