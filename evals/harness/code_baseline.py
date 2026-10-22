"""The code-only baseline: what plain code reads from a listing, with no model.

It's the number every model has to beat (D32). Two layers:

1. The page's fixed parts, read by adapters/spitogatos_details.py: the table,
   the ticked features, plus the result card (type, bedrooms, area).
2. A handful of keyword rules on the description, for the facts your reading
   notes say a reader must catch there (D31): parking, storage, outdoor space,
   a lift, and the distance to the metro. They only fill gaps the table left.

These rules are deliberately simple and visible. The production extractor
reads prose with the model; the baseline shows how far rules alone get.

Run: uv run python -m evals.harness.code_baseline   (writes data/private/evals/)
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from adapters import spitogatos_features as features
from adapters.spitogatos_details import parse_details
from evals.harness.build_label_tool import RAW, ROOT, SNAPSHOT
from evals.harness.labels import LABEL_FIELDS

OUT = ROOT / "data" / "private" / "evals" / "predictions_code_baseline.jsonl"

NEGATION = r"(?:χωρίς|δεν\s+(?:διαθέτει|έχει|υπάρχει)|δε\s+(?:διαθέτει|έχει)|αντί)"
PARKING = re.compile(r"θέσ(?:η|εις)\s+στάθμευσης|π[άα]ρκινγκ|parking|γκαρ[άα]ζ|πιλοτ|πυλωτ", re.I)
PARKING_NONE = re.compile(NEGATION + r"\s+(?:\w+\s+){0,2}(?:θέση\s+στάθμευσης|π[άα]ρκινγκ|parking)", re.I)
STORAGE = re.compile(r"αποθήκ", re.I)
STORAGE_NONE = re.compile(NEGATION + r"\s+(?:\w+\s+){0,2}αποθήκ", re.I)
OUTDOOR = re.compile(r"μπαλκ[όο]ν|βερ[άα]ντ|ιδιωτικ\w*\s+κήπ|αποκλειστικ\w*\s+(?:χρήσ\w*\s+)?κήπ|αυλ[ήη]", re.I)
LIFT = re.compile(r"ασανσ[έε]ρ|ανελκυστ[ήη]ρ", re.I)
LIFT_NONE = re.compile(NEGATION + r"\s+(?:\w+\s+){0,3}(?:ασανσ[έε]ρ|ανελκυστ[ήη]ρ)", re.I)
METRES_TO_METRO = re.compile(r"(\d[\d.,]*)\s*(?:μ\.|μέτρ\w*|m\b)[^.\n]{0,60}?μετρ[όο]", re.I)
METRO_THEN_METRES = re.compile(r"μετρ[όο][^.\n]{0,40}?(\d[\d.,]*)\s*(?:μ\.|μέτρ\w*|m\b)", re.I)
MINUTES_TO_METRO = re.compile(r"(\d{1,2})\s*λεπτ\w*[^.\n]{0,40}?μετρ[όο]", re.I)


def _metres(text: str) -> int | None:
    """'2.000' is 2000 (Greek thousands), '1,5' is 1; anything outside 20 to 5,000 m is ignored."""
    digits = re.sub(r"\.(?=\d{3}\b)", "", text.strip(".,")).split(",")[0].split(".")[0]
    value = int(digits) if digits.isdigit() else 0
    return value if 20 <= value <= 5000 else None


def from_description(text: str) -> dict:
    """Keyword facts from the description. Missing means the rules found nothing."""
    found: dict = {}
    if PARKING_NONE.search(text):
        found["parking"] = "none"
    elif PARKING.search(text):
        found["parking"] = "pilotis" if re.search(r"πιλοτ|πυλωτ", text, re.I) else "space"
    if STORAGE_NONE.search(text):
        found["storage"] = False
    elif STORAGE.search(text):
        found["storage"] = True
    if OUTDOOR.search(text):
        found["balcony"] = True
    if LIFT_NONE.search(text) or re.search(r"αναβατ[όο]ρι", text, re.I):
        found["lift"] = False
    elif LIFT.search(text):
        found["lift"] = True
    minutes = MINUTES_TO_METRO.search(text)
    metres = METRES_TO_METRO.search(text) or METRO_THEN_METRES.search(text)
    if minutes:
        found["metro_walk_min"] = int(minutes.group(1))
    elif metres and _metres(metres.group(1)):
        found["metro_walk_min"] = -(-_metres(metres.group(1)) // 80)
    return found


def from_page(record: dict, card: dict) -> dict:
    """What code reads from the page's fixed parts (table, ticks, card), before any prose."""
    f = parse_details(record).fields
    fields = {name: None for name in LABEL_FIELDS}
    fields.update({
        "listing_type": card.get("listing_type"),
        "price_eur": f.get("price_eur", card.get("price_eur")),
        "size_m2": f.get("size_m2", card.get("size_m2")),
        "property_type": card.get("property_type"),
        "bedrooms": card.get("bedrooms"),
        "bathrooms": f.get("bathrooms", card.get("bathrooms")),
        "floor_class": f.get("floor_class"),
        "year_built": f.get("year_built"),
        "renovated_year": f.get("renovated_year"),
        "condition": f.get("condition"),
        "energy_class": f.get("energy_class"),
        "heating_type": f.get("heating_type"),
        "heating_fuel": f.get("heating_fuel"),
        "parking": f.get("parking"),
        "lift": f.get("lift"),
        "balcony": f.get("balcony"),
        "storage": f.get("storage"),
        "flags": f.get("flags") or [],
        "area": card.get("area"),
        "sub_area": card.get("sub_area"),
    })
    return fields


def predict(record: dict, card: dict) -> dict:
    """All label fields for one listing; None where code can't tell."""
    fields = from_page(record, card)
    for name, value in from_description(record["sections"].get("Περιγραφή", "")).items():
        if fields.get(name) is None:
            fields[name] = value
        elif name == "parking" and fields[name] == "none" and value != "none":
            fields[name] = value  # a mention in the text beats a crossed-out tick (D35)
        elif name == "storage" and fields[name] is False and value is True:
            fields[name] = value  # (D34)
    return fields


def run(raw_path: Path = RAW, snapshot_path: Path = SNAPSHOT, out_path: Path = OUT, revisit: bool = False) -> int:
    cards = {}
    for line in snapshot_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            card = json.loads(line)
            cards[card["listing_id"]] = card
    out_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    records = [json.loads(line) for line in raw_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if revisit:
        records = features.attach(records, features.load())
    with out_path.open("w", encoding="utf-8") as fh:
        for record in records:
            listing_id = f"spitogatos:{record['source_id']}"
            fh.write(json.dumps({"listing_id": listing_id, "fields": predict(record, cards.get(listing_id, {}))}, ensure_ascii=False) + "\n")
            count += 1
    return count


if __name__ == "__main__":
    crossed = "--crossed" in sys.argv[1:]
    out = OUT.with_name("predictions_code_baseline+crossed.jsonl") if crossed else OUT
    print(f"Wrote {run(out_path=out, revisit=crossed)} predictions to {out.relative_to(ROOT)}")
    sys.exit(0)
