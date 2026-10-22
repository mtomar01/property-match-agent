"""Read the fixed parts of a Spitogatos detail page into code-read fields.

Input: data/private/spitogatos_details_raw.jsonl, one page per line, read in a
normal browser at a slow pace:

    {"source_id": "...", "url": "...", "seen": "2026-10-20",
     "sections": {"Περιγραφή": ..., "Χαρακτηριστικά": ..., "Εσωτερικό": ...,
                  "Εξωτερικά χαρακτηριστικά": ..., "Κατασκευή": ..., "Κατάλληλο για": ...}}

The feature sections hold only the ticked items. Spitogatos prints unticked
ones struck through, and those were dropped while collecting.

Code calculates, the model reasons: Spitogatos prints the key/value table and
the feature ticks straight from its listing form, so code reads them. The free
text in Περιγραφή is left for the model. Two rules from the real pages:

- A ticked box is a yes. An unticked box is unknown, not a no (decision D22):
  some agencies tick nothing at all, so a missing tick proves nothing.
- A feature shown with a number replaces its label with that number. On real
  pages "(1)" under the exterior features is the parking spaces, "(15τ.μ.)"
  there is the balcony area, and "(8τ.μ.)" under the interior is the storage
  room. The descriptions confirm this mapping on every page that states it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from core import greek

TABLE_KEYS = (
    "Τιμή", "Τιμή ανά τ.μ.", "Εμβαδόν", "Εμβαδόν οικοπέδου", "Καθαρό Εμβαδόν", "Μεικτό Εμβαδόν",
    "Επίπεδα", "Όροφος", "Κουζίνες", "Μπάνια", "WC", "Σαλόνια", "Μηνιαία κοινόχρηστα",
    "Μεσιτική αμοιβή", "Σύστημα θέρμανσης", "Ενεργειακή κλάση", "Έτος κατασκευής",
    "Έτος ανακαίνισης", "Απόσταση απο τη θάλασσα", "Κωδικός Συστήματος", "Κωδικός Ακινήτου",
    "Διαθέσιμο από", "Μισθωμένο", "Μισθωμένο μέχρι", "Δημοσίευση αγγελίας", "Τελευταία ενημέρωση",
)
# How many value lines each key may have; more means an unknown key slipped in.
MAX_VALUES = {"Τιμή": 3, "Ενεργειακή κλάση": 2}
NOISE = {"Χρηματοδότησέ το"}  # the "finance it" button

INTERIOR = "Εσωτερικό"
EXTERIOR = "Εξωτερικά χαρακτηριστικά"
CONSTRUCTION = "Κατασκευή"
SUITABLE = "Κατάλληλο για"

DATE = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
EURO = re.compile(r"€\s*([\d.]+(?:,\d+)?)")
AREA = re.compile(r"^\(?([\d.,]+)\s*τ\.μ\.\)?$")
COUNT = re.compile(r"^\((\d+)\)$")
TOTAL_FLOORS = re.compile(r"\s*\(Σύνολο ορόφων:\s*(\d+)\)")

# Κατασκευή ticks, most limiting first: an unfinished home that is also
# marked new build is still unfinished. A home still being built is
# unfinished too, with its expected completion as the year built (D31).
CONDITION_TICKS = (
    ("Ημιτελές", "unfinished"),
    ("Χρήζει ανακαίνισης", "needs_work"),
    ("Νεόδμητο", "new_build"),
    ("Ανακαινισμένο", "renovated"),
)


def number(text: str) -> float:
    """Greek number format: '1.050.000' is 1050000 and '105,20' is 105.2."""
    text = text.strip()
    if "," in text:
        return float(text.replace(".", "").replace(",", "."))
    return float(text.replace(".", ""))


def parse_table(text: str | None) -> tuple[dict[str, list[str]], list[str]]:
    """Split the Χαρακτηριστικά table into {key: [value lines]} plus problems."""
    table: dict[str, list[str]] = {}
    problems: list[str] = []
    current: str | None = None
    for line in (text or "").split("\n"):
        line = line.strip()
        if not line or line in NOISE:
            continue
        if line in TABLE_KEYS:
            current = line
            table[current] = []
        elif current is None:
            problems.append(f"value before any key: {line!r}")
        else:
            table[current].append(line)
    for key, values in table.items():
        if len(values) > MAX_VALUES.get(key, 1):
            problems.append(f"{key} has {len(values)} values, an unknown key may follow it: {values}")
    return table, problems


def _items(sections: dict, name: str) -> list[str]:
    return [line.strip() for line in (sections.get(name) or "").split("\n") if line.strip()]


@dataclass
class DetailFields:
    """What code can read from one detail page. None means the page doesn't say."""

    source_id: str
    # Fields that map one to one onto a label (and onto Listing).
    fields: dict = field(default_factory=dict)
    # Facts worth showing the labeller that have no label field yet.
    extras: dict = field(default_factory=dict)
    ticked: dict = field(default_factory=dict)
    crossed: dict = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)


def parse_details(record: dict) -> DetailFields:
    sections = record.get("sections", {})
    table, problems = parse_table(sections.get("Χαρακτηριστικά"))
    out = DetailFields(source_id=str(record["source_id"]), problems=problems)
    f, x = out.fields, out.extras

    def first(key: str) -> str | None:
        values = table.get(key) or []
        return values[0] if values else None

    # Price: the first euro amount is current; a second one is the old price
    # Spitogatos shows struck out after a drop.
    prices = [int(number(m.group(1))) for v in table.get("Τιμή", []) for m in EURO.finditer(v)]
    if prices:
        f["price_eur"] = prices[0]
    if len(prices) > 1 and prices[1] != prices[0]:
        f["old_price_eur"] = prices[1]
    if any("Συζητήσιμη" in v for v in table.get("Τιμή", [])):
        x["negotiable"] = True

    size = first("Εμβαδόν")
    if size and AREA.match(size):
        f["size_m2"] = number(AREA.match(size).group(1))
    for key, name in (("Εμβαδόν οικοπέδου", "plot_m2"), ("Καθαρό Εμβαδόν", "net_m2"), ("Μεικτό Εμβαδόν", "gross_m2")):
        value = first(key)
        if value and AREA.match(value):
            x[name] = number(AREA.match(value).group(1))

    floor_raw = first("Όροφος")
    if floor_raw:
        total = TOTAL_FLOORS.search(floor_raw)
        if total:
            x["floors_in_building"] = int(total.group(1))
        floor_raw = TOTAL_FLOORS.sub("", floor_raw).strip()
        f["floor_raw"] = floor_raw
        f["floor_class"] = greek.normalise_floor(floor_raw)

    for key, name, target in (("Μπάνια", "bathrooms", f), ("WC", "wc", x), ("Επίπεδα", "levels", x)):
        value = first(key)
        if value and value.isdigit():
            target[name] = int(value)

    year = first("Έτος κατασκευής")
    if year and year.isdigit():
        f["year_built"] = int(year)
    elif year and "κατασκευή" in year:
        x["under_construction"] = True
    # "Available from" a date after the page was read, on a home built this year
    # or later (or with no year), means it's still being built: that date is
    # the expected completion (D31).
    available = DATE.search(first("Διαθέσιμο από") or "")
    seen = date.fromisoformat(record["seen"]) if record.get("seen") else None
    if available and seen:
        ready = date(int(available.group(3)), int(available.group(2)), int(available.group(1)))
        if ready > seen and (f.get("year_built") is None or f["year_built"] >= seen.year - 1):
            x["under_construction"] = True
            x["expected_completion"] = ready.isoformat()
            f["year_built"] = ready.year
    # A year built after the page was read is an expected completion too.
    if seen and f.get("year_built") and f["year_built"] > seen.year:
        x["under_construction"] = True
    renovated = first("Έτος ανακαίνισης")
    if renovated and renovated.isdigit():
        f["renovated_year"] = int(renovated)

    energy = first("Ενεργειακή κλάση")
    if energy:
        f["energy_raw"] = energy
        f["energy_class"] = greek.normalise_energy_class(energy)

    heating = greek.normalise_heating(first("Σύστημα θέρμανσης"))
    if heating["raw"]:
        f["heating_raw"] = heating["raw"]
        f["heating_type"] = heating["type"]
        f["heating_fuel"] = heating["fuel"]

    if first("Μισθωμένο") == "Ναι":
        x["rented"] = True
    if first("Μισθωμένο μέχρι"):
        x["rented_until"] = first("Μισθωμένο μέχρι")
    charge = first("Μηνιαία κοινόχρηστα")
    if charge and EURO.search(charge):
        x["service_charge_eur"] = number(EURO.search(charge).group(1))

    # Ticked features.
    interior, exterior = _items(sections, INTERIOR), _items(sections, EXTERIOR)
    construction, suitable = _items(sections, CONSTRUCTION), _items(sections, SUITABLE)
    out.ticked = {"interior": interior, "exterior": exterior, "construction": construction, "suitable": suitable}

    if "Ασανσέρ" in interior:
        f["lift"] = True
    storage_m2 = [number(AREA.match(i).group(1)) for i in interior if AREA.match(i)]
    if "Αποθήκη" in interior or storage_m2:
        f["storage"] = True
        if storage_m2:
            x["storage_m2"] = storage_m2[0]
    balcony_m2 = [number(AREA.match(i).group(1)) for i in exterior if AREA.match(i)]
    # Any private outdoor space counts as a balcony (D31).
    if "Βεράντα" in exterior or "Ιδιωτικός Κήπος" in exterior or balcony_m2:
        f["balcony"] = True
        if balcony_m2:
            x["balcony_m2"] = balcony_m2[0]
    spaces = [int(COUNT.match(i).group(1)) for i in exterior if COUNT.match(i)]
    if "Parking" in exterior or spaces:
        # A tick means a parking spot. Parking is scored as has or hasn't
        # (D31); a type named in the text is detail for the model to add.
        x["parking_ticked"] = True
        f["parking"] = "space"
        if spaces:
            x["parking_spaces"] = spaces[0]

    # Crossed-out features, when the record has them (the revisit, D34). The
    # advertiser crossed them out, so the home doesn't have them (D29). A tick
    # always wins, in case a page lists a feature twice.
    crossed = record.get("crossed") or {}
    if crossed:
        out.crossed = crossed
        if "Ασανσέρ" in crossed.get(INTERIOR, []) and "lift" not in f:
            f["lift"] = False
        if "Αποθήκη" in crossed.get(INTERIOR, []) and "storage" not in f:
            f["storage"] = False
        if "Parking" in crossed.get(EXTERIOR, []) and "parking" not in f:
            f["parking"] = "none"

    flags = []
    if "Οροφοδιαμέρισμα" in construction:
        flags.append("whole_floor")
    if "Διαμπερές" in interior:
        flags.append("dual_aspect")
    if "Γωνιακό" in exterior:
        flags.append("corner")
    if flags:
        f["flags"] = flags

    condition = next((value for tick, value in CONDITION_TICKS if tick in construction), None)
    if x.get("under_construction"):
        condition = "unfinished"
    if condition:
        f["condition"] = condition
    if "Ρετιρέ" in construction:
        x["penthouse"] = True

    return out
