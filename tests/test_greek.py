import pytest

from core import greek


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("υπόγειο", "basement"),
        ("ΗΜΙΥΠΟΓΕΙΟ", "semi_basement"),
        ("Ημιυπόγειο όροφος", "semi_basement"),
        ("ΗΜ/ΥΠ", "semi_basement"),
        ("ισόγειο", "ground"),
        ("ισογειο", "ground"),
        ("ΙΣ", "ground"),
        ("Υπερυψωμένο Ισόγειο", "raised_ground"),
        ("ημιόροφος", "mezzanine"),
        ("3ος", "3"),
        ("1ος όροφος", "1"),
        ("5ο", "5"),
        ("ρετιρέ", "top"),
        ("2nd", "2"),
        ("", None),
        (None, None),
        ("κάπου ψηλά", None),
    ],
)
def test_floor(raw, expected):
    assert greek.normalise_floor(raw) == expected


def test_floor_level_orders_floors():
    order = ["basement", "semi_basement", "ground", "raised_ground", "mezzanine", "1", "4"]
    levels = [greek.floor_level(f) for f in order]
    assert levels == sorted(levels)
    assert greek.floor_level("top") is None


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Α+", "A+"),
        ("ΠΕΑ: Β+", "B+"),
        ("Γ", "C"),
        ("ενεργειακή κλάση Δ", "D"),
        ("Ζ", "F"),
        ("Η", "G"),
        ("H", "G"),  # Greek Η typed on a Latin keyboard
        ("Z", "F"),
        ("ενεργειακό πιστοποιητικό: Ε", "E"),
        ("υπό έκδοση", "pending"),
        ("Δεν απαιτείται", "exempt"),
        ("", None),
        ("καλή", None),
    ],
)
def test_energy_class(raw, expected):
    assert greek.normalise_energy_class(raw) == expected


def test_energy_class_shown_in_greek():
    assert greek.energy_class_greek("C") == "Γ"
    assert greek.energy_class_greek("G") == "Η"


@pytest.mark.parametrize(
    "raw, heating_type, fuel",
    [
        ("Αυτόνομη, φυσικό αέριο", "independent", "gas"),
        ("Αυτόνομη με Πετρέλαιο", "independent", "oil"),
        ("Ατομική με Αντλία θερμότητας", "independent", "heat_pump"),
        ("κεντρική - πετρέλαιο", "central", "oil"),
        ("Ατομική με Υγραέριο", "independent", "lpg"),
        ("τζάκι", None, None),
        # Found on real detail pages: the table says "θέρμανσης", not "θερμότητας".
        ("Ατομική θέρμανση (Αντλία Θέρμανσης)", "independent", "heat_pump"),
        # "coil" contains "oil", which once turned every fan coil into oil heating.
        # A fan coil is read as a heat pump (D31).
        ("Αυτόνομη (Fan coil)", "independent", "heat_pump"),
        ("Χωρίς θέρμανση", "none", None),
    ],
)
def test_heating(raw, heating_type, fuel):
    result = greek.normalise_heating(raw)
    assert (result["type"], result["fuel"]) == (heating_type, fuel)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("πιλοτή", "pilotis"),
        ("parking πυλωτής", "pilotis"),
        ("1 Σε υπόγειο χώρο", "garage"),
        ("θέση στάθμευσης", "space"),
        ("τίποτα", None),
    ],
)
def test_parking(raw, expected):
    assert greek.normalise_parking(raw) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Διαμέρισμα, 86τ.μ.", "apartment"),
        ("Μεζονέτα, 100τ.μ.", "maisonette"),
        ("Μονοκατοικία, 60τ.μ.", "detached_house"),
        ("Συγκρότημα διαμερισμάτων, 211τ.μ.", "apartment_complex"),
        ("Loft, 68τ.μ.", "loft"),
    ],
)
def test_property_type(raw, expected):
    assert greek.normalise_property_type(raw) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [("Αιγάλεω", "Egaleo"), ("aigaleo", "Egaleo"), ("ΧΑΪΔΑΡΙ", "Chaidari"), ("Περιστέρι", "Peristeri"), ("Κυψέλη", None)],
)
def test_area(raw, expected):
    assert greek.normalise_area(raw) == expected


def test_condition():
    assert greek.normalise_condition("Χρήζει ολικής ανακαίνισης") == "needs_work"
    assert greek.normalise_condition("ΝΕΟΔΜΗΤΟ") == "new_build"
    assert greek.normalise_condition("ανακαινισμένο το 2019") == "renovated"
