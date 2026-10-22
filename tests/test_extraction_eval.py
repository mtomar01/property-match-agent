"""Answer key, extraction scoring and the code-only baseline, on invented data only."""

import json

import pytest

from evals.harness import answer_key
from evals.harness.agreement_sets import choose_hardest
from evals.harness.code_baseline import from_description, predict
from evals.harness.extraction_eval import outcome, score
from evals.harness.labels import ExtractionLabel


def label(listing, labeller="mt", prefilled=("price_eur",), **fields):
    return ExtractionLabel.model_validate({
        "listing_id": listing, "labeller": labeller, "labelled_at": "2026-10-21", "round": 1,
        "fields": fields, "prefilled": list(prefilled),
    })


def write(path, labels):
    path.write_text("".join(json.dumps(l.model_dump(mode="json"), ensure_ascii=False) + "\n" for l in labels), encoding="utf-8")


def test_outcomes_separate_wrong_invented_and_missed():
    assert outcome("lift", None, None) == "correct"  # both unknown is an answer
    assert outcome("lift", True, False) == "wrong"
    assert outcome("lift", None, True) == "invented"
    assert outcome("lift", True, None) == "missed"
    assert outcome("parking", "pilotis", "space") == "correct"  # has or hasn't (D31)
    assert outcome("metro_walk_min", 650, 9) == "correct"  # 650 m is 9 minutes


def test_score_splits_table_fields_from_text_fields():
    key = [label("spitogatos:1", price_eur=100000, lift=True), label("spitogatos:2", price_eur=200000)]
    result = score(key, {"spitogatos:1": {"price_eur": 100000, "lift": None}})
    assert result.groups["structured"]["correct"] == 1 and result.groups["structured"]["missed"] == 1
    assert result.per_field["lift"]["missed"] == 1
    assert result.missing_predictions == ["spitogatos:2"]


def test_freeze_writes_once_and_load_checks_the_checksum(tmp_path):
    src = tmp_path / "hosted_batch1_x.jsonl"
    write(src, [label("spitogatos:2", price_eur=1), label("spitogatos:1", price_eur=2)])
    path = answer_key.freeze(1, [src], out_dir=tmp_path)
    labels, manifest = answer_key.load(1, tmp_path)
    assert [l.listing_id for l in labels] == ["spitogatos:1", "spitogatos:2"]  # sorted, stable
    assert manifest["origin"]["spitogatos:1"]["rules"] == "before D29"
    with pytest.raises(FileExistsError):
        answer_key.freeze(1, [src], out_dir=tmp_path)
    path.write_text(path.read_text(encoding="utf-8").replace('"price_eur": 2', '"price_eur": 3'), encoding="utf-8")
    with pytest.raises(ValueError, match="changed"):
        answer_key.load(1, tmp_path)


def test_freeze_refuses_a_listing_labelled_twice(tmp_path):
    a, b = tmp_path / "hosted_batch3_a.jsonl", tmp_path / "hosted_batch4_b.jsonl"
    write(a, [label("spitogatos:1")])
    write(b, [label("spitogatos:1")])
    with pytest.raises(ValueError, match="appears in"):
        answer_key.freeze(1, [a, b], out_dir=tmp_path)


@pytest.mark.parametrize("text, expected", [
    ("Διαθέτει θέση στάθμευσης και αποθήκη.", {"parking": "space", "storage": True}),
    ("Πάρκινγκ στην πιλοτή.", {"parking": "pilotis"}),
    ("Χωρίς πάρκινγκ, δεν διαθέτει ανελκυστήρα.", {"parking": "none", "lift": False}),
    ("Μεγάλη βεράντα και ιδιωτικός κήπος.", {"balcony": True}),
    ("Μόλις 2.000 μέτρα από τον σταθμό μετρό.", {"metro_walk_min": 25}),
    ("8 λεπτά με τα πόδια από το μετρό.", {"metro_walk_min": 8}),
    ("Φωτεινό και ήσυχο.", {}),
])
def test_description_rules(text, expected):
    assert from_description(text) == expected


def test_description_fills_only_what_the_table_left_blank():
    record = {"source_id": "1", "seen": "2026-10-20", "sections": {
        "Περιγραφή": "Χωρίς ασανσέρ. Αποθήκη στο υπόγειο.", "Χαρακτηριστικά": "Τιμή\n€100.000",
        "Εσωτερικό": "Ασανσέρ"}}
    fields = predict(record, {"bedrooms": 2})
    assert fields["lift"] is True  # the tick stands; the conflict is the model's job (D25)
    assert fields["storage"] is True and fields["bedrooms"] == 2 and fields["price_eur"] == 100000


def test_round2_takes_the_listings_code_read_worst_from_the_other_labeller():
    origin = {f"spitogatos:{i}": {"labeller": "a" if i < 5 else "b"} for i in range(10)}
    errors = {"spitogatos:1": 5, "spitogatos:3": 2, "spitogatos:7": 4, "spitogatos:9": 1}
    chosen = choose_hardest(origin, errors, size=2)
    assert chosen["b"] == ["spitogatos:1", "spitogatos:3"]
    assert chosen["a"] == ["spitogatos:7", "spitogatos:9"]


def test_combining_labels_keeps_a_found_value_and_lets_the_newer_label_settle_a_clash():
    old = label("spitogatos:1", labeller="gb", parking="none", balcony=True, lift=True, floor_class="2")
    new = label("spitogatos:1", labeller="mike", parking=None, balcony=None, lift=False, floor_class="2")
    combined, how = answer_key.combine([old, new])
    assert combined.fields.parking == "none" and combined.fields.balcony is True  # a blank doesn't erase a value
    assert combined.fields.lift is False  # they clash, the newer label wins
    assert combined.labeller == "gb+mike"
    assert sorted(how["filled_from_older"]) == ["balcony", "parking"] and how["newest_won"] == ["lift"]


def test_a_combined_key_records_every_label_it_used(tmp_path):
    write(tmp_path / "hosted_batch3_gb.jsonl", [label("spitogatos:1", labeller="gb", lift=True), label("spitogatos:2", labeller="gb")])
    write(tmp_path / "round2_mike.jsonl", [label("spitogatos:1", labeller="mike", lift=None, storage=True)])
    answer_key.freeze_combined(2, ("hosted_batch3_gb", "round2_mike"), out_dir=tmp_path)
    labels, manifest = answer_key.load(2, tmp_path)
    one = {l.listing_id: l for l in labels}["spitogatos:1"]
    assert one.fields.lift is True and one.fields.storage is True
    assert [entry["file"] for entry in manifest["origin"]["spitogatos:1"]["labels"]] == ["hosted_batch3_gb", "round2_mike"]
    assert manifest["origin"]["spitogatos:1"]["rules"] == "D31" and manifest["origin"]["spitogatos:2"]["rules"] == "D29"


def test_metro_within_a_minute_is_correct():
    assert outcome("metro_walk_min", 8, 9) == "correct"  # 700 m typed as 8, code says 9
    assert outcome("metro_walk_min", 650, 10) == "correct"  # 650 m is 9 minutes
    assert outcome("metro_walk_min", 5, 7) == "wrong"
    assert outcome("metro_walk_min", None, 9) == "invented"


def test_key_v3_fills_only_silent_crossed_out_blanks_and_marks_them():
    crossed = {"Εσωτερικό": ["Ασανσέρ", "Αποθήκη"], "Εξωτερικά χαρακτηριστικά": ["Parking"]}
    blank = label("spitogatos:1", lift=None, storage=None, parking=None)
    filled, names = answer_key.fill_crossed_out(blank, crossed, "Φωτεινό διαμέρισμα.")
    assert (filled.fields.lift, filled.fields.storage, filled.fields.parking) == (False, False, "none")
    assert sorted(names) == ["lift", "parking", "storage"] and "D29" in filled.evidence["lift"]
    said, names = answer_key.fill_crossed_out(blank, crossed, "Με θέση στάθμευσης και εσωτερική αποθήκη.")
    assert said.fields.parking is None and said.fields.storage is None and names == ["lift"]  # the text wins (D34, D35)
    kept, names = answer_key.fill_crossed_out(label("spitogatos:1", lift=True), crossed, "")
    assert kept.fields.lift is True and "lift" not in names  # a labeller's answer is never overwritten
