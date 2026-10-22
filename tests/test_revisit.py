"""The crossed-out revisit (D34): decoding the page script's output, reading crossed-out as no, and round 3."""

import pytest

from adapters.spitogatos_details import parse_details
from adapters.spitogatos_features import FEATURE_NAMES, attach, decode, fingerprint, page_script
from agent.extraction import merge, reconcile
from evals.harness.agreement_sets import choose_round3
from evals.harness.extraction_eval import score
from evals.harness.labels import ExtractionLabel


def test_the_page_script_reads_icons_and_fingerprints_its_own_list():
    script = page_script()
    assert "i-negative" in script and "i-correct" in script and "crypto.subtle.digest" in script
    assert "Ασανσέρ" in script and "textContent" in script
    assert len(fingerprint()) == 12 and fingerprint() != fingerprint(FEATURE_NAMES[:-1])


def test_decode_turns_codes_into_names_and_refuses_another_list():
    row = {"p": "1", "t": "Διαμέρισμα, 50τ.μ.", "fp": fingerprint(), "n": {"in": [0, "Κάτι νέο"], "ex": [2]}, "y": {"in": [1]}, "x": 0}
    out = decode(row, "2026-10-22")
    assert out["crossed"] == {"Εσωτερικό": ["Ασανσέρ", "Κάτι νέο"], "Εξωτερικά χαρακτηριστικά": ["Parking"]}
    assert out["ticked"] == {"Εσωτερικό": ["Αποθήκη"]} and not out["gone"]
    with pytest.raises(ValueError, match="fingerprint"):
        decode(dict(row, fp="000000000000"), "2026-10-22")


def record(**sections):
    base = {"Χαρακτηριστικά": "Τιμή\n€100.000", "Εσωτερικό": "", "Εξωτερικά χαρακτηριστικά": ""}
    base.update(sections)
    return {"source_id": "1", "seen": "2026-10-20", "sections": base}


def test_crossed_out_is_no_and_a_tick_still_wins():
    crossed = {"Εσωτερικό": ["Ασανσέρ", "Αποθήκη"], "Εξωτερικά χαρακτηριστικά": ["Parking"]}
    fields = parse_details(dict(record(), crossed=crossed)).fields
    assert fields["lift"] is False and fields["storage"] is False and fields["parking"] == "none"
    ticked = parse_details(dict(record(**{"Εσωτερικό": "Ασανσέρ"}), crossed=crossed)).fields
    assert ticked["lift"] is True
    assert "lift" not in parse_details(record()).fields  # no list, no answer


def test_attach_adds_lists_only_where_the_revisit_has_them():
    records = [record(), dict(record(), source_id="2")]
    out = attach(records, {"1": {"crossed": {"Εσωτερικό": ["Ασανσέρ"]}, "seen": "2026-10-22"}})
    assert out[0]["crossed"] == {"Εσωτερικό": ["Ασανσέρ"]} and "crossed" not in out[1]
    assert "crossed" not in records[0]  # the 20 October records are left as they were


def test_storage_the_text_mentions_beats_a_crossed_out_list():
    assert reconcile("storage", False, True) is True
    fields, blanked = merge({"storage": False}, {"storage": True}, "conflict")
    assert fields["storage"] is True and blanked == []
    assert reconcile("lift", False, True) is None  # other features still conflict (D25)


def test_round3_gives_the_other_labellers_listings_then_a_self_check():
    origin = {f"spitogatos:{i}": {"labeller": "gb" if i < 8 else "mike"} for i in range(10)}
    errors = {"spitogatos:1": 3, "spitogatos:9": 2}
    sets = choose_round3(origin, errors, sorted(origin), size=4)
    assert sets["relabel"]["mike"][0] == "spitogatos:1" and len(sets["relabel"]["mike"]) == 4
    assert sets["relabel"]["gb"][:2] == ["spitogatos:9", "spitogatos:8"]  # mike only has two
    assert len(sets["self_check"]["gb"]) == 2 and not set(sets["self_check"]["gb"]) & set(sets["relabel"]["mike"])


def test_score_can_be_limited_to_a_subset():
    key = [ExtractionLabel.model_validate({"listing_id": f"spitogatos:{i}", "labeller": "x", "labelled_at": "2026-10-21",
                                           "round": 1, "fields": {"lift": True}, "prefilled": []}) for i in (1, 2)]
    result = score(key, {"spitogatos:1": {"lift": True}}, only={"spitogatos:1"})
    assert result.listings == 1 and result.per_field["lift"]["correct"] == 1


def test_a_ticked_garden_is_a_balcony_but_a_shared_one_isnt():
    assert parse_details(record(**{"Εξωτερικά χαρακτηριστικά": "Κήπος"})).fields["balcony"] is True
    assert "balcony" not in parse_details(record(**{"Εξωτερικά χαρακτηριστικά": "Κοινόχρηστος κήπος"})).fields


def test_parking_the_text_mentions_beats_a_crossed_out_tick():
    from evals.harness.code_baseline import predict

    assert reconcile("parking", "none", "space") == "space"
    fields, blanked = merge({"parking": "none"}, {"parking": "pilotis"}, "conflict")
    assert fields["parking"] == "pilotis" and blanked == []
    crossed = dict(record(**{"Περιγραφή": "Πάρκινγκ στην πιλοτή."}), crossed={"Εξωτερικά χαρακτηριστικά": ["Parking"]})
    assert predict(crossed, {})["parking"] == "pilotis"
    assert predict(dict(record(**{"Περιγραφή": "Φωτεινό."}), crossed={"Εξωτερικά χαρακτηριστικά": ["Parking"]}), {})["parking"] == "none"
