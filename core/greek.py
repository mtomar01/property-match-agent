"""Greek listing terms and their normalised values (spec section 6).

Everything here is plain code, not the model: these are fixed vocabularies, so a
lookup table is cheaper, faster and fully testable. The model only gets involved
for free text that a table cannot read.

Matching ignores case and Greek accents, so "ΙΣΟΓΕΙΟ", "ισόγειο" and "ισογειο"
all normalise the same way.
"""

from __future__ import annotations

import re
import unicodedata

# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------


def fold(text: str) -> str:
    """Lower-case and strip accents and diaeresis, so matching is forgiving."""
    decomposed = unicodedata.normalize("NFD", text.strip().lower())
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return stripped.replace("ς", "σ")  # final sigma behaves like sigma


# ---------------------------------------------------------------------------
# Floors
# ---------------------------------------------------------------------------

SPECIAL_FLOORS = ("basement", "semi_basement", "ground", "raised_ground", "mezzanine", "top")

# Ordered: longer, more specific terms first ("ημιυπογειο" before "υπογειο").
_FLOOR_TERMS: list[tuple[str, str]] = [
    ("ημιυπογειο", "semi_basement"),
    ("ημ/υπ", "semi_basement"),
    ("υπογειο", "basement"),
    ("υπερυψωμενο", "raised_ground"),
    ("ισογειο", "ground"),
    ("ημιοροφοσ", "mezzanine"),
    ("ρετιρε", "top"),
    ("semi-basement", "semi_basement"),
    ("semi basement", "semi_basement"),
    ("basement", "basement"),
    ("raised ground", "raised_ground"),
    ("ground", "ground"),
    ("mezzanine", "mezzanine"),
    ("penthouse", "top"),
]

# Short badges Spitogatos shows on result cards.
_FLOOR_BADGES = {"ισ": "ground", "υπ": "basement", "ημ/υπ": "semi_basement", "ημ": "mezzanine"}

_ORDINAL = re.compile(r"^\s*(\d{1,2})\s*(οσ|ο|ος|st|nd|rd|th)?\b")


def normalise_floor(raw: str | None) -> str | None:
    """Return a floor class: a special value from SPECIAL_FLOORS or "1", "2", ...

    Returns None when the text doesn't say, so callers can treat it as unknown
    rather than guessing.
    """
    if raw is None or not str(raw).strip():
        return None
    text = fold(str(raw))
    if text in _FLOOR_BADGES:
        return _FLOOR_BADGES[text]
    for term, value in _FLOOR_TERMS:
        if term in text:
            return value
    match = _ORDINAL.match(text)
    if match:
        number = int(match.group(1))
        return "ground" if number == 0 else str(number)
    return None


def floor_level(floor_class: str | None) -> float | None:
    """A number for comparing floors: basement -1, ground 0, mezzanine 0.5 and so on.

    "top" has no fixed number, so it returns None and callers handle it explicitly.
    """
    levels = {"basement": -1.0, "semi_basement": -0.5, "ground": 0.0, "raised_ground": 0.25, "mezzanine": 0.5}
    if floor_class is None or floor_class == "top":
        return None
    if floor_class in levels:
        return levels[floor_class]
    return float(floor_class) if floor_class.isdigit() else None


# ---------------------------------------------------------------------------
# Energy class
# ---------------------------------------------------------------------------

ENERGY_CLASSES = ("A+", "A", "B+", "B", "C", "D", "E", "F", "G")

# Greek scale Α+ Α Β+ Β Γ Δ Ε Ζ Η maps to the Latin A+ to G scale.
# Listings often type Greek capitals with Latin keys, so Latin "Z" and "H" are
# read as the Greek Ζ and Η (there is no Z or H on the Latin scale).
_ENERGY_LETTERS = {
    "α": "A", "a": "A",
    "β": "B", "b": "B",
    "γ": "C", "c": "C",
    "δ": "D", "d": "D",
    "ε": "E", "e": "E",
    "ζ": "F", "z": "F", "f": "F",
    "η": "G", "h": "G", "g": "G",
}

_ENERGY_PENDING = ("υπο εκδοση", "υπο εκδοσι", "pending", "εκκρεμει")
_ENERGY_EXEMPT = ("δεν απαιτειται", "εξαιρειται", "not required", "exempt")


def normalise_energy_class(raw: str | None) -> str | None:
    """Return "A+" to "G", "pending", "exempt", or None when unknown."""
    if raw is None or not str(raw).strip():
        return None
    text = fold(str(raw))
    if any(term in text for term in _ENERGY_PENDING):
        return "pending"
    if any(term in text for term in _ENERGY_EXEMPT):
        return "exempt"
    # Drop labels like "ΠΕΑ:", "ενεργειακη κλαση", "energy class".
    text = re.sub(r"(πεα|ενεργειακ\w*|κλασ\w*|πιστοποιητικ\w*|energy|class|:)", " ", text).strip()
    match = re.search(r"(?<![a-zα-ω])([a-hzα-ω])\s*(\+)?(?![a-zα-ω])", text)
    if not match:
        return None
    letter = _ENERGY_LETTERS.get(match.group(1))
    if letter is None:
        return None
    if match.group(2) and letter in ("A", "B"):
        return letter + "+"
    return letter


_LATIN_TO_GREEK_ENERGY = {"A+": "Α+", "A": "Α", "B+": "Β+", "B": "Β", "C": "Γ", "D": "Δ", "E": "Ε", "F": "Ζ", "G": "Η"}


def energy_class_greek(value: str | None) -> str | None:
    """Show a stored Latin class to Greek users with Greek letters."""
    return _LATIN_TO_GREEK_ENERGY.get(value or "", value)


# ---------------------------------------------------------------------------
# Heating
# ---------------------------------------------------------------------------

_HEATING_TYPES = [
    ("αυτονομ", "independent"),
    ("ατομικ", "independent"),
    ("independent", "independent"),
    ("κεντρικ", "central"),
    ("central", "central"),
    ("χωρισ θερμανση", "none"),
    ("no heating", "none"),
]

_HEATING_FUELS = [
    ("φυσικο αεριο", "gas"),
    ("φυσικου αεριου", "gas"),
    ("natural gas", "gas"),
    ("πετρελαι", "oil"),
    ("oil", "oil"),
    ("αντλια θερμοτητασ", "heat_pump"),
    ("heat pump", "heat_pump"),
    ("υγραεριο", "lpg"),
    ("ρευμα", "electric"),
    ("ηλεκτρικ", "electric"),
    ("electric", "electric"),
    ("ξυλ", "wood"),
    ("pellet", "wood"),
    ("fan coil", "other"),
]


def normalise_heating(raw: str | None) -> dict:
    """Return {"raw", "type", "fuel"}. Unknown parts are None, never guessed."""
    if raw is None or not str(raw).strip():
        return {"raw": None, "type": None, "fuel": None}
    text = fold(str(raw))
    heating_type = next((value for term, value in _HEATING_TYPES if term in text), None)
    fuel = next((value for term, value in _HEATING_FUELS if term in text), None)
    return {"raw": str(raw).strip(), "type": heating_type, "fuel": fuel}


# ---------------------------------------------------------------------------
# Parking
# ---------------------------------------------------------------------------

_PARKING = [
    ("πιλοτ", "pilotis"),
    ("πυλωτ", "pilotis"),  # common misspelling
    ("pilotis", "pilotis"),
    ("υπογειο χωρο", "garage"),
    ("κλειστο χωρο", "garage"),
    ("γκαραζ", "garage"),
    ("garage", "garage"),
    ("θεση σταθμευσησ", "space"),
    ("θεσεισ σταθμευσησ", "space"),
    ("ανοιχτο χωρο", "space"),
    ("καλυμμενο χωρο", "space"),
    ("parking", "space"),
    ("χωρισ σταθμευση", "none"),
]


def normalise_parking(raw: str | None) -> str | None:
    if raw is None or not str(raw).strip():
        return None
    text = fold(str(raw))
    return next((value for term, value in _PARKING if term in text), None)


# ---------------------------------------------------------------------------
# Property type and condition
# ---------------------------------------------------------------------------

_PROPERTY_TYPES = [
    ("συγκροτημα διαμερισματων", "apartment_complex"),
    ("οροφοδιαμερισμα", "apartment"),
    ("διαμερισμα", "apartment"),
    ("γκαρσονιερα", "studio"),
    ("studio", "studio"),
    ("μεζονετα", "maisonette"),
    ("maisonette", "maisonette"),
    ("μονοκατοικια", "detached_house"),
    ("loft", "loft"),
    ("κτιριο", "building"),
    ("πολυκατοικια", "building"),
    ("apartment", "apartment"),
    ("flat", "apartment"),
    ("house", "detached_house"),
]


def normalise_property_type(raw: str | None) -> str | None:
    if raw is None or not str(raw).strip():
        return None
    text = fold(str(raw))
    return next((value for term, value in _PROPERTY_TYPES if term in text), None)


_CONDITIONS = [
    ("χρηζει ολικησ ανακαινισησ", "needs_work"),
    ("χρηζει ανακαινισησ", "needs_work"),
    ("needs renovation", "needs_work"),
    ("ημιτελεσ", "unfinished"),
    ("υπο κατασκευη", "new_build"),
    ("νεοδμητ", "new_build"),
    ("new build", "new_build"),
    ("ανακαινισμεν", "renovated"),
    ("ανακαινιστηκε", "renovated"),
    ("renovated", "renovated"),
]


def normalise_condition(raw: str | None) -> str | None:
    if raw is None or not str(raw).strip():
        return None
    text = fold(str(raw))
    return next((value for term, value in _CONDITIONS if term in text), None)


# ---------------------------------------------------------------------------
# Areas
# ---------------------------------------------------------------------------

# Canonical English names, with the spellings people actually use.
AREA_ALIASES: dict[str, list[str]] = {
    "Egaleo": ["egaleo", "aigaleo", "aegaleo", "αιγαλεω"],
    "Peristeri": ["peristeri", "περιστερι"],
    "Chaidari": ["chaidari", "haidari", "xaidari", "χαιδαρι"],
}


def normalise_area(raw: str | None) -> str | None:
    """Map any spelling of a supported municipality to its canonical name."""
    if raw is None or not str(raw).strip():
        return None
    text = fold(str(raw))
    for canonical, aliases in AREA_ALIASES.items():
        if any(alias in text for alias in aliases):
            return canonical
    return None


# ---------------------------------------------------------------------------
# Glossary (served as an MCP resource and pasted into the extraction prompt)
# ---------------------------------------------------------------------------

GLOSSARY: list[dict[str, str]] = [
    {"greek": "υπόγειο", "meaning": "basement", "normalised": "floor class basement"},
    {"greek": "ημιυπόγειο", "meaning": "semi-basement", "normalised": "floor class semi_basement"},
    {"greek": "ισόγειο", "meaning": "ground floor", "normalised": "floor class ground"},
    {"greek": "υπερυψωμένο", "meaning": "raised ground floor", "normalised": "floor class raised_ground"},
    {"greek": "ημιόροφος", "meaning": "mezzanine", "normalised": "floor class mezzanine"},
    {"greek": "1ος, 2ος, 3ος", "meaning": "1st, 2nd, 3rd floor", "normalised": "floor class 1, 2, 3"},
    {"greek": "ρετιρέ", "meaning": "top floor set back with a terrace", "normalised": "floor class top"},
    {"greek": "οροφοδιαμέρισμα", "meaning": "flat taking up a whole floor", "normalised": "flag whole_floor"},
    {"greek": "μεζονέτα", "meaning": "maisonette", "normalised": "type maisonette"},
    {"greek": "διαμπερές", "meaning": "dual aspect", "normalised": "flag dual_aspect"},
    {"greek": "γωνιακό", "meaning": "corner", "normalised": "flag corner"},
    {"greek": "προσανατολισμός", "meaning": "orientation", "normalised": "orientation"},
    {"greek": "ανελκυστήρας, ασανσέρ", "meaning": "lift", "normalised": "lift"},
    {"greek": "αυτόνομη / ατομική θέρμανση", "meaning": "independent heating", "normalised": "heating independent"},
    {"greek": "κεντρική θέρμανση", "meaning": "central heating", "normalised": "heating central"},
    {"greek": "πιλοτή, θέση στάθμευσης", "meaning": "parking under the building, parking space", "normalised": "parking pilotis, space"},
    {"greek": "αποθήκη", "meaning": "storage room", "normalised": "storage"},
    {"greek": "ανακαινισμένο (2019)", "meaning": "renovated (in 2019)", "normalised": "renovated_year"},
    {"greek": "χρήζει ανακαίνισης", "meaning": "needs renovation", "normalised": "condition needs_work"},
    {"greek": "νεόδμητο", "meaning": "new build", "normalised": "condition new_build"},
    {"greek": "ΠΕΑ: Α+ to Η, υπό έκδοση", "meaning": "energy certificate class, or pending", "normalised": "energy_class A+ to G, pending"},
]
