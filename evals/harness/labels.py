"""Extraction labels: the record Mike writes for each listing, and its checks.

A label is the answer key for one listing: what the listing states, anywhere
on the page (table, ticks or text), with null for "doesn't say" and null for
"says two different things" (see docs/labelling-guide.md).

Pre-filling: the labeller shows the values code read from the page's table
and ticks, so Mike checks them instead of retyping them. Free-text fields
start blank on purpose, so a guess from code can't anchor the label. Each
label records which fields were pre-filled and which of those Mike changed,
which later splits the eval into "structured" and "free text" fields and
shows how often the portal's own table was wrong.

Check a file:  uv run python -m evals.harness.labels data/private/labels/<file>.jsonl
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from adapters.spitogatos_details import DetailFields
from core import greek, pii
from core.models import (
    Area, Condition, EnergyClass, Flag, Fuel, HeatingType, ListingType, Parking, PropertyType,
)

FREE_TEXT_ONLY = ("parking", "metro_walk_min")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LabelFields(_Strict):
    listing_type: ListingType | None = None
    price_eur: int | None = Field(default=None, gt=0)
    size_m2: float | None = Field(default=None, gt=0)
    property_type: PropertyType | None = None
    bedrooms: int | None = Field(default=None, ge=0)
    bathrooms: int | None = Field(default=None, ge=0)
    floor_class: str | None = None
    year_built: int | None = Field(default=None, ge=1800, le=2035)
    renovated_year: int | None = Field(default=None, ge=1900, le=2035)
    condition: Condition | None = None
    energy_class: EnergyClass | None = None
    heating_type: HeatingType | None = None
    heating_fuel: Fuel | None = None
    parking: Parking | None = None
    lift: bool | None = None
    balcony: bool | None = None
    storage: bool | None = None
    flags: list[Flag] = Field(default_factory=list)
    area: Area | None = None
    sub_area: str | None = None
    metro_walk_min: int | None = Field(default=None, ge=0)

    @field_validator("floor_class")
    @classmethod
    def _floor(cls, value: str | None) -> str | None:
        if value is None or value in greek.SPECIAL_FLOORS or value.isdigit():
            return value
        raise ValueError(f"unknown floor class {value!r}")


LABEL_FIELDS = tuple(LabelFields.model_fields)
PARKING_PRESENT = ("pilotis", "space", "garage")


def comparable(name: str, value):
    """The form in which two answers for one field are compared (D31).

    Parking is scored as has or hasn't: a parking spot under any name counts,
    and its type is detail. Minutes to the metro accept the distance as the
    listing states it: a value above 60 is metres, turned into minutes at
    80 m a minute, rounded up. Flags compare as a set.
    """
    if name == "parking":
        return "yes" if value in PARKING_PRESENT else ("no" if value == "none" else None)
    if name == "metro_walk_min" and isinstance(value, (int, float)) and value > 60:
        return -(-int(value) // 80)
    if name == "flags":
        return sorted(value or [])
    return value


class OldPrice(_Strict):
    price_eur: int = Field(gt=0)
    date: dt.date | None = None


class ExtractionLabel(_Strict):
    listing_id: str = Field(pattern=r"^(spitogatos|xe|spiti24|link):[A-Za-z0-9_-]+$")
    labeller: str = Field(min_length=1)
    labelled_at: dt.date
    round: int = Field(ge=1)
    pii: bool = False
    fields: LabelFields
    price_history: list[OldPrice] = Field(default_factory=list)
    evidence: dict[str, str] = Field(default_factory=dict)
    notes: str = ""
    prefilled: list[str] = Field(default_factory=list)
    changed_from_code: list[str] = Field(default_factory=list)
    # Labels made from the live page (hosted tool, D28): did it still match our copy?
    live_page: Literal["matches", "changed", "gone"] | None = None

    @field_validator("evidence")
    @classmethod
    def _evidence(cls, value: dict[str, str]) -> dict[str, str]:
        for name, phrase in value.items():
            if name not in LABEL_FIELDS and name != "price_history":
                raise ValueError(f"evidence for unknown field {name!r}")
            if pii.find_pii(phrase):
                raise ValueError(f"evidence for {name} contains contact details")
        return value

    @field_validator("notes")
    @classmethod
    def _notes(cls, value: str) -> str:
        if pii.find_pii(value):
            raise ValueError("notes contain contact details")
        return value

    @field_validator("prefilled", "changed_from_code")
    @classmethod
    def _known_fields(cls, value: list[str]) -> list[str]:
        unknown = [name for name in value if name not in LABEL_FIELDS and name != "old_price_eur"]
        if unknown:
            raise ValueError(f"unknown fields {unknown}")
        return value


def prefill(details: DetailFields, card: dict) -> dict:
    """The values code can read, keyed by label field. Missing means blank in the tool.

    The detail page's table wins over the result card, because the card is a
    shorter print of the same form. Fields in FREE_TEXT_ONLY are never filled.
    """
    f = details.fields
    values = {
        "listing_type": card.get("listing_type"),
        "price_eur": f.get("price_eur", card.get("price_eur")),
        "old_price_eur": f.get("old_price_eur"),
        "size_m2": f.get("size_m2", card.get("size_m2")),
        "property_type": card.get("property_type"),
        "bedrooms": card.get("bedrooms"),
        "bathrooms": f.get("bathrooms", card.get("bathrooms")),
        "floor_class": f.get("floor_class", (card.get("floor") or {}).get("class")),
        "year_built": f.get("year_built"),
        "renovated_year": f.get("renovated_year"),
        "condition": f.get("condition"),
        "energy_class": f.get("energy_class"),
        "heating_type": f.get("heating_type"),
        "heating_fuel": f.get("heating_fuel"),
        "lift": f.get("lift"),
        "balcony": f.get("balcony"),
        "storage": f.get("storage"),
        "flags": f.get("flags"),
        "area": card.get("area"),
        "sub_area": card.get("sub_area"),
    }
    return {name: value for name, value in values.items() if value not in (None, [], "")}


def check(path: Path, known_ids: set[str] | None = None) -> tuple[list[ExtractionLabel], list[str]]:
    """Validate a labels file. Returns the labels and a list of problems."""
    labels: list[ExtractionLabel] = []
    problems: list[str] = []
    seen: set[str] = set()
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            label = ExtractionLabel.model_validate(json.loads(line))
        except Exception as exc:  # noqa: BLE001 - report every bad line
            problems.append(f"line {number}: {exc}")
            continue
        if label.listing_id in seen:
            problems.append(f"line {number}: {label.listing_id} labelled twice")
        if known_ids is not None and label.listing_id not in known_ids:
            problems.append(f"line {number}: {label.listing_id} is not in the snapshot")
        seen.add(label.listing_id)
        labels.append(label)
    return labels, problems


if __name__ == "__main__":
    found, issues = check(Path(sys.argv[1]))
    print(f"{len(found)} valid labels, {len(issues)} problems")
    for issue in issues:
        print("  ", issue)
    flagged = [label.listing_id for label in found if label.pii]
    if flagged:
        print("Flagged for contact details that weren't scrubbed:", ", ".join(flagged))
    sys.exit(1 if issues else 0)
