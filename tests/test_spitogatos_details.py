"""The detail-page parser, on invented pages in the shape real ones have."""

from adapters.spitogatos_details import number, parse_details, parse_table

TABLE = "\n".join([
    "Τιμή", "€162.000 ", "€175.000", " (Συζητήσιμη)", "Χρηματοδότησέ το",
    "Τιμή ανά τ.μ.", "€1.687,5",
    "Εμβαδόν", "96τ.μ.",
    "Εμβαδόν οικοπέδου", "250τ.μ.",
    "Επίπεδα", "1",
    "Όροφος", "2ος (Σύνολο ορόφων: 4)",
    "Μπάνια", "1",
    "WC", "1",
    "Σύστημα θέρμανσης", "Αυτόνομη (Αντλία Θέρμανσης)",
    "Ενεργειακή κλάση", "Β+", "50%-75%",
    "Έτος κατασκευής", "1979",
    "Έτος ανακαίνισης", "2024",
    "Μισθωμένο", "Ναι",
    "Κωδικός Συστήματος", "99999999",
])


def page(**sections) -> dict:
    base = {"Περιγραφή": "Invented text.", "Χαρακτηριστικά": TABLE}
    base.update(sections)
    return {"source_id": "99999999", "url": "https://synthetic.invalid/1", "seen": "2026-10-20", "sections": base}


def test_number_reads_greek_format():
    assert number("1.050.000") == 1050000
    assert number("105,20") == 105.2


def test_table_reads_every_key_and_flags_unknown_ones():
    table, problems = parse_table(TABLE)
    assert table["Όροφος"] == ["2ος (Σύνολο ορόφων: 4)"]
    assert problems == []
    _, problems = parse_table("Εμβαδόν\n80τ.μ.\nΘέα σε πάρκο\nΝαι")
    assert problems and "unknown key" in problems[0]


def test_table_fields():
    fields = parse_details(page()).fields
    assert fields["price_eur"] == 162000 and fields["old_price_eur"] == 175000
    assert fields["size_m2"] == 96
    assert (fields["floor_raw"], fields["floor_class"]) == ("2ος", "2")
    assert fields["bathrooms"] == 1  # the WC is not a bathroom
    assert (fields["heating_type"], fields["heating_fuel"]) == ("independent", "heat_pump")
    assert fields["energy_class"] == "B+"
    assert (fields["year_built"], fields["renovated_year"]) == (1979, 2024)


def test_extras_carry_facts_without_a_label_field():
    extras = parse_details(page()).extras
    assert extras["negotiable"] and extras["rented"]
    assert extras["floors_in_building"] == 4 and extras["plot_m2"] == 250 and extras["wc"] == 1


def test_ticked_features_are_yes_and_missing_ones_stay_unknown():
    details = parse_details(page(**{
        "Εσωτερικό": "Ασανσέρ\n(6τ.μ.)\nΔιαμπερές",
        "Εξωτερικά χαρακτηριστικά": "(2)\n(12τ.μ.)\nΓωνιακό",
        "Κατασκευή": "Οροφοδιαμέρισμα\nΑνακαινισμένο",
    }))
    f, x = details.fields, details.extras
    assert f["lift"] is True and f["storage"] is True and f["balcony"] is True
    assert (x["storage_m2"], x["balcony_m2"], x["parking_spaces"]) == (6, 12, 2)
    assert f["flags"] == ["whole_floor", "dual_aspect", "corner"]
    assert f["condition"] == "renovated"

    bare = parse_details(page(**{"Εσωτερικό": "Φωτεινό", "Εξωτερικά χαρακτηριστικά": "Θέα"})).fields
    for name in ("lift", "storage", "balcony", "flags", "condition"):
        assert name not in bare  # unknown, never False


def test_under_construction_has_no_year_and_counts_as_unfinished():
    table = TABLE.replace("Έτος κατασκευής\n1979", "Έτος κατασκευής\nΥπό κατασκευή")
    details = parse_details(page(**{"Χαρακτηριστικά": table}))
    assert "year_built" not in details.fields
    assert details.extras["under_construction"] and details.fields["condition"] == "unfinished"


def test_unfinished_beats_new_build():
    details = parse_details(page(**{"Κατασκευή": "Νεόδμητο\nΗμιτελές"}))
    assert details.fields["condition"] == "unfinished"


def test_energy_exempt_and_no_heating():
    table = TABLE.replace("Β+\n50%-75%", "Εξαιρείται από την υποχρεωτική έκδοση ΠΕΑ").replace(
        "Αυτόνομη (Αντλία Θέρμανσης)", "Χωρίς θέρμανση")
    fields = parse_details(page(**{"Χαρακτηριστικά": table})).fields
    assert fields["energy_class"] == "exempt"
    assert (fields["heating_type"], fields["heating_fuel"]) == ("none", None)


def test_available_later_means_still_being_built_and_completion_is_the_year():
    table = TABLE.replace("Έτος κατασκευής\n1979", "Έτος κατασκευής\n2026") + "\nΔιαθέσιμο από\n30/12/2027"
    details = parse_details(page(**{"Χαρακτηριστικά": table, "Κατασκευή": "Νεόδμητο"}))
    assert details.fields["year_built"] == 2027 and details.fields["condition"] == "unfinished"
    assert details.extras["expected_completion"] == "2027-12-30"


def test_available_later_on_an_old_home_is_not_construction():
    table = TABLE + "\nΔιαθέσιμο από\n01/03/2027"  # built 1979, perhaps rented until then
    details = parse_details(page(**{"Χαρακτηριστικά": table}))
    assert details.fields["year_built"] == 1979 and "under_construction" not in details.extras


def test_parking_tick_is_a_parking_spot_and_a_private_garden_is_a_balcony():
    details = parse_details(page(**{"Εξωτερικά χαρακτηριστικά": "Parking\nΙδιωτικός Κήπος"}))
    assert details.fields["parking"] == "space" and details.fields["balcony"] is True


def test_a_future_year_built_is_still_being_built():
    table = TABLE.replace("Έτος κατασκευής\n1979", "Έτος κατασκευής\n2027")
    details = parse_details(page(**{"Χαρακτηριστικά": table}))
    assert details.fields["year_built"] == 2027 and details.fields["condition"] == "unfinished"
