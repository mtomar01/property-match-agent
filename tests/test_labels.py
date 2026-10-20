"""Extraction labels and the labelling tool, on invented listings only."""

import json
import re

import pytest
from pydantic import ValidationError

from adapters.spitogatos_details import parse_details
from evals.harness.build_label_tool import _json_for_script, build, build_items
from evals.harness.labels import ExtractionLabel, check, prefill

TABLE = "Τιμή\n€180.000\nΕμβαδόν\n80τ.μ.\nΌροφος\n2ος\nΜπάνια\n1\nΕνεργειακή κλάση\nΓ"
CARD = {
    "listing_id": "spitogatos:99999999", "listing_type": "sale", "title": "Διαμέρισμα, 80τ.μ.",
    "property_type": "apartment", "bedrooms": 2, "bathrooms": 2, "price_eur": 185000, "size_m2": 80,
    "floor": {"raw": "1ος", "class": "1"}, "area": "Egaleo", "sub_area": "Κέντρο",
}


def raw(description="Invented text near the metro.", **sections) -> dict:
    return {
        "source_id": "99999999", "url": "https://synthetic.invalid/99999999", "seen": "2026-10-20",
        "sections": {"Περιγραφή": description, "Χαρακτηριστικά": TABLE, "Εξωτερικά χαρακτηριστικά": "Parking", **sections},
    }


def label(**overrides) -> dict:
    record = {
        "listing_id": "spitogatos:99999999", "labeller": "mike", "labelled_at": "2026-10-21", "round": 1,
        "fields": {"price_eur": 180000, "floor_class": "raised_ground", "parking": "pilotis", "flags": ["corner"]},
        "evidence": {"parking": "θέση στάθμευσης στην πιλοτή"}, "notes": "", "prefilled": ["price_eur"],
    }
    record.update(overrides)
    return record


def test_prefill_prefers_the_table_and_never_fills_free_text_fields():
    values = prefill(parse_details(raw()), CARD)
    assert values["bathrooms"] == 1 and values["floor_class"] == "2"  # table, not card
    assert values["bedrooms"] == 2 and values["area"] == "Egaleo"  # only the card has these
    assert values["energy_class"] == "C"
    assert "parking" not in values and "metro_walk_min" not in values  # a tick isn't a parking type
    assert "lift" not in values  # unticked is unknown, so blank


def test_a_good_label_validates():
    parsed = ExtractionLabel.model_validate(label())
    assert parsed.fields.parking == "pilotis" and parsed.fields.lift is None


@pytest.mark.parametrize("overrides", [
    {"notes": "the agent's mobile is 6912345678"},
    {"evidence": {"parking": "email me at someone@example.com"}},
    {"evidence": {"brightness": "φωτεινό"}},
    {"fields": {"floor_class": "first"}},
    {"fields": {"energy_class": "Γ"}},  # labels use Latin letters
    {"prefilled": ["agent_name"]},
])
def test_bad_labels_are_refused(overrides):
    with pytest.raises(ValidationError):
        ExtractionLabel.model_validate(label(**overrides))


def test_check_reports_duplicates_and_unknown_ids(tmp_path):
    path = tmp_path / "labels.jsonl"
    lines = [label(), label(), label(listing_id="spitogatos:11111111"), {"listing_id": "broken"}]
    path.write_text("\n".join(json.dumps(line) for line in lines), encoding="utf-8")
    labels, problems = check(path, known_ids={"spitogatos:99999999"})
    assert len(labels) == 3
    assert any("labelled twice" in p for p in problems)
    assert any("not in the snapshot" in p for p in problems)
    assert any(p.startswith("line 4") for p in problems)


def test_listing_text_cannot_break_out_of_the_page():
    hostile = "Ωραίο σπίτι </script><script>alert(1)</script> & <b>"
    text = _json_for_script({"items": [{"description": hostile}]})
    assert "</script" not in text.lower() and "<" not in text
    assert json.loads(text)["items"][0]["description"] == hostile


def test_build_refuses_unscrubbed_contact_details():
    with pytest.raises(ValueError, match="contact details"):
        build_items([raw(description="Καλέστε στο 6912345678")], {CARD["listing_id"]: CARD})


def test_build_writes_one_offline_page(tmp_path):
    raw_path, snap_path, out = tmp_path / "raw.jsonl", tmp_path / "snap.jsonl", tmp_path / "out" / "tool.html"
    raw_path.write_text(json.dumps(raw(), ensure_ascii=False) + "\n", encoding="utf-8")
    snap_path.write_text(json.dumps(CARD, ensure_ascii=False) + "\n", encoding="utf-8")
    assert build(raw_path, snap_path, out) == 1
    html = out.read_text(encoding="utf-8")
    data = re.search(r'<script type="application/json" id="data">(.*?)</script>', html, re.S).group(1)
    payload = json.loads(data)
    assert payload["round"] == 1 and payload["items"][0]["prefill"]["price_eur"] == 180000
    assert "http" not in re.sub(r'"url": "[^"]+"', "", data)  # no external resources besides the listing link
    assert "<link" not in html and "src=" not in html


def test_the_public_template_is_a_valid_label():
    from pathlib import Path

    template = json.loads((Path(__file__).resolve().parent.parent / "evals/datasets/templates/extraction_label.json").read_text(encoding="utf-8"))
    ExtractionLabel.model_validate({k: v for k, v in template.items() if not k.startswith("_doc")})
