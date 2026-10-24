"""Pydantic models for the four core records in spec section 6.

Two design rules run through this file:

1. **Unknown is a value, not a guess.** Optional fields default to None, and
   None means "the listing doesn't say". Search treats unknown carefully (see
   core/filters.py) instead of assuming the best case.
2. **Privacy is enforced by the schema.** Listings forbid extra fields, so an
   adapter can't sneak in an agent name or phone field, and free text is
   rejected if it still contains a phone number or email. Adapters must scrub
   with core.pii.scrub first. The check fails closed: bad data is refused,
   not silently stored.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from core import greek, pii

Source = Literal["spitogatos", "xe", "spiti24", "link"]
Intent = Literal["buy", "rent", "invest"]
ListingType = Literal["sale", "rent"]
PropertyType = Literal[
    "apartment", "studio", "maisonette", "detached_house", "loft", "building", "apartment_complex"
]
Condition = Literal["needs_work", "unfinished", "new_build", "renovated", "good"]
EnergyClass = Literal["A+", "A", "B+", "B", "C", "D", "E", "F", "G", "pending", "exempt"]
ENERGY_LETTERS = ("A+", "A", "B+", "B", "C", "D", "E", "F", "G")
HeatingType = Literal["independent", "central", "none"]
Fuel = Literal["gas", "oil", "heat_pump", "lpg", "electric", "wood", "other"]
Parking = Literal["pilotis", "space", "garage", "none"]
Flag = Literal["whole_floor", "dual_aspect", "corner"]
Area = Literal["Egaleo", "Peristeri", "Chaidari", "Pagrati", "Kypseli"]  # Pagrati 22 October (D44), Kypseli 23 October (D69)
# Areas the search covers by default: the frozen snapshot the evals run on has listings for these only.
SEARCH_AREAS: tuple[str, ...] = ("Egaleo", "Peristeri", "Chaidari")
_covered: tuple[str, ...] = SEARCH_AREAS


def covered_areas() -> tuple[str, ...]:
    """The areas the search covers right now: the default three, or what the loaded dataset holds (D69)."""
    return _covered


def set_covered_areas(areas) -> tuple[str, ...]:
    """Cover the areas a dataset has listings for. The app and the MCP server call this when they load data."""
    global _covered
    known = Area.__args__
    chosen = tuple(a for a in known if a in set(areas))
    if not chosen:
        raise ValueError("a dataset has to cover at least one known area")
    _covered = chosen
    return _covered
RejectReason = Literal[
    "too_dark", "too_small", "bad_floor", "needs_work", "too_expensive", "bad_value", "wrong_area", "other"
]


class _Strict(BaseModel):
    """Base for stored records: unknown fields are an error, not ignored."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


# ---------------------------------------------------------------------------
# Listing parts
# ---------------------------------------------------------------------------


class Floor(_Strict):
    raw: str | None = None
    floor_class: str | None = Field(default=None, alias="class")

    @field_validator("floor_class")
    @classmethod
    def _valid_class(cls, value: str | None) -> str | None:
        if value is None or value in greek.SPECIAL_FLOORS or value.isdigit():
            return value
        raise ValueError(f"unknown floor class {value!r}")

    @classmethod
    def from_raw(cls, raw: str | None) -> "Floor":
        return cls(raw=raw, floor_class=greek.normalise_floor(raw))


class EnergyRating(_Strict):
    raw: str | None = None
    value: EnergyClass | None = None

    @classmethod
    def from_raw(cls, raw: str | None) -> "EnergyRating":
        return cls(raw=raw, value=greek.normalise_energy_class(raw))


class Heating(_Strict):
    raw: str | None = None
    type: HeatingType | None = None
    fuel: Fuel | None = None

    @classmethod
    def from_raw(cls, raw: str | None) -> "Heating":
        return cls(**greek.normalise_heating(raw))


class PricePoint(_Strict):
    date: date
    price_eur: int = Field(gt=0)


# ---------------------------------------------------------------------------
# Listing
# ---------------------------------------------------------------------------


class Listing(_Strict):
    """One normalised record per source listing."""

    listing_id: str = Field(pattern=r"^(spitogatos|xe|spiti24|link):[A-Za-z0-9_-]+$")
    source: Source
    url: str
    listing_type: ListingType = "sale"
    synthetic: bool = False

    first_seen: date
    last_seen: date

    price_eur: int | None = Field(default=None, gt=0, description="None means price on request")
    price_history: list[PricePoint] = Field(default_factory=list)
    size_m2: float | None = Field(default=None, gt=0)
    price_per_m2: int | None = None

    property_type: PropertyType | None = None
    bedrooms: int | None = Field(default=None, ge=0)
    bathrooms: int | None = Field(default=None, ge=0)
    floor: Floor = Field(default_factory=Floor)
    year_built: int | None = Field(default=None, ge=1800, le=2035)
    renovated_year: int | None = Field(default=None, ge=1900, le=2035)
    condition: Condition | None = None
    energy_class: EnergyRating = Field(default_factory=EnergyRating)
    heating: Heating = Field(default_factory=Heating)
    parking: Parking | None = None
    lift: bool | None = None
    balcony: bool | None = None
    storage: bool | None = None
    flags: list[Flag] = Field(default_factory=list)

    area: Area | None = None
    sub_area: str | None = None
    metro_walk_min: int | None = Field(default=None, ge=0)

    photo_urls: list[str] = Field(default_factory=list)
    photo_hashes: list[str] = Field(default_factory=list)

    title: str | None = None
    description: str | None = Field(
        default=None, description="Untrusted listing text, scrubbed of contact details"
    )

    field_confidence: dict[str, float] = Field(default_factory=dict)
    evidence: dict[str, str] = Field(default_factory=dict)

    @field_validator("title", "description", "sub_area")
    @classmethod
    def _no_contact_details(cls, value: str | None) -> str | None:
        found = pii.find_pii(value)
        if found:
            raise ValueError("contains contact details; run core.pii.scrub before storing")
        return value

    @field_validator("photo_urls")
    @classmethod
    def _links_only(cls, value: list[str]) -> list[str]:
        for url in value:
            if not url.startswith(("http://", "https://")):
                raise ValueError("photos are stored as links to the source, never as files")
        return value

    @field_validator("field_confidence")
    @classmethod
    def _confidence_range(cls, value: dict[str, float]) -> dict[str, float]:
        for field, score in value.items():
            if not 0.0 <= score <= 1.0:
                raise ValueError(f"confidence for {field} must be between 0 and 1")
        return value

    @model_validator(mode="after")
    def _derived_fields(self) -> "Listing":
        if not self.listing_id.startswith(f"{self.source}:"):
            raise ValueError("listing_id must start with its source, e.g. xe:123")
        if self.price_eur and self.size_m2:
            self.price_per_m2 = round(self.price_eur / self.size_m2)
        else:
            self.price_per_m2 = None
        if self.last_seen < self.first_seen:
            raise ValueError("last_seen is before first_seen")
        return self

    def summary(self) -> dict:
        """The short form used in search results and on swipe cards."""
        return {
            "listing_id": self.listing_id,
            "source": self.source,
            "url": self.url,
            "listing_type": self.listing_type,
            "title": self.title,
            "price_eur": self.price_eur,
            "size_m2": self.size_m2,
            "price_per_m2": self.price_per_m2,
            "bedrooms": self.bedrooms,
            "floor": self.floor.floor_class,
            "area": self.area,
            "sub_area": self.sub_area,
            "year_built": self.year_built,
            "renovated_year": self.renovated_year,
            "energy_class": self.energy_class.value,
            "property_type": self.property_type,
            "first_seen": self.first_seen.isoformat(),
            "previous_price_eur": next((p.price_eur for p in reversed(self.price_history)
                                        if p.price_eur != self.price_eur), None),  # the shortlist shows price changes (spec)
            "synthetic": self.synthetic,
        }


# ---------------------------------------------------------------------------
# Criteria
# ---------------------------------------------------------------------------


class HardLimits(_Strict):
    """Limits that are never broken. Filtered in code, never by the model."""

    max_price_eur: int | None = Field(default=None, gt=0)
    min_price_eur: int | None = Field(default=None, gt=0)
    min_size_m2: float | None = Field(default=None, gt=0)
    max_size_m2: float | None = Field(default=None, gt=0)
    min_bedrooms: int | None = Field(default=None, ge=0)
    max_bedrooms: int | None = Field(default=None, ge=0)  # D56: "ideally 1 bedroom" searches 0 to 2
    min_year_built: int | None = Field(default=None, ge=1800, le=2035)  # D66: "built from 2015 on", from a check-in
    property_types: list[PropertyType] = Field(default_factory=list)
    exclude_floors: list[str] = Field(default_factory=list)

    @field_validator("exclude_floors")
    @classmethod
    def _floor_classes(cls, value: list[str]) -> list[str]:
        cleaned = []
        for item in value:
            floor_class = item if (item in greek.SPECIAL_FLOORS or item.isdigit()) else greek.normalise_floor(item)
            if floor_class is None:
                raise ValueError(f"can't read floor {item!r}")
            cleaned.append(floor_class)
        return cleaned

    @model_validator(mode="after")
    def _ranges(self) -> "HardLimits":
        if self.min_price_eur and self.max_price_eur and self.min_price_eur > self.max_price_eur:
            raise ValueError("min_price_eur is above max_price_eur")
        if self.min_size_m2 and self.max_size_m2 and self.min_size_m2 > self.max_size_m2:
            raise ValueError("min_size_m2 is above max_size_m2")
        if self.min_bedrooms is not None and self.max_bedrooms is not None and self.min_bedrooms > self.max_bedrooms:
            raise ValueError("min_bedrooms is above max_bedrooms")
        return self


PreferenceFeature = Literal[
    "price_eur", "size_m2", "bedrooms", "bathrooms", "floor_level", "year_built", "renovated_year",
    "energy_class", "metro_walk_min", "balcony", "lift", "parking", "storage",
    "dual_aspect", "corner", "whole_floor",
]


YES_NO_FEATURES = ("balcony", "lift", "parking", "storage", "dual_aspect", "corner", "whole_floor")  # D53


class Preference(_Strict):
    """A weighted wish. Scored, never filtered.

    The feature list is closed on purpose: the interview model must map what a
    user says onto features the listings actually have, and anything else
    ("bright", "quiet street") goes into open_questions instead of being
    invented as a field. energy_class bounds are letters, e.g. min "B".
    """

    feature: PreferenceFeature
    min: float | str | None = None
    max: float | str | None = None
    equals: bool | None = None
    weight: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _has_target(self) -> "Preference":
        if self.min is None and self.max is None and self.equals is None:
            raise ValueError("a preference needs min, max or equals")
        if self.feature in YES_NO_FEATURES and (self.min is not None or self.max is not None):
            raise ValueError(f"{self.feature} is yes or no: use equals")
        if self.feature not in YES_NO_FEATURES and self.equals is not None:
            raise ValueError(f"{self.feature} needs a number (min or max), not yes or no")
        for bound in (self.min, self.max):
            if isinstance(bound, str) and (self.feature != "energy_class" or bound not in ENERGY_LETTERS):
                raise ValueError("text bounds are only for energy_class letters, A+ to G")
        return self


class Criteria(_Strict):
    user_id: str
    intent: Intent
    areas: list[Area] = Field(default_factory=list)
    hard_limits: HardLimits = Field(default_factory=HardLimits)
    preferences: list[Preference] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    version: int = Field(default=1, ge=1)
    confirmed_by_user: bool = False

    @field_validator("areas", mode="before")
    @classmethod
    def _canonical_areas(cls, value: list[str]) -> list[str]:
        out = []
        for raw in value or []:
            canonical = greek.normalise_area(raw)
            if canonical is None or canonical not in covered_areas():
                raise ValueError(f"area {raw!r} isn't covered yet ({', '.join(covered_areas())})")
            if canonical not in out:
                out.append(canonical)
        return out


# ---------------------------------------------------------------------------
# Swipe and duplicates
# ---------------------------------------------------------------------------


# "Can't judge": the user skipped because the listing didn't let them decide, not because of the home (D71).
SkipReason = Literal["photos_unclear", "too_little_info", "other"]
REJECT_REASONS: tuple[str, ...] = RejectReason.__args__
SKIP_REASONS: tuple[str, ...] = SkipReason.__args__
NOTE_MAX = 300


class Swipe(_Strict):
    """One decision on one card. A skip is no verdict: it counts in no like rate and teaches no ranking (D71)."""

    user_id: str
    listing_id: str
    decision: Literal["like", "reject", "skip"]
    reasons: list[str] = Field(default_factory=list)
    note: str | None = Field(default=None, max_length=NOTE_MAX)  # the user's words after "Other…", scrubbed
    deck_position: int = Field(ge=0)
    explore_card: bool = False
    ts: datetime

    @model_validator(mode="after")
    def _reasons_fit_the_decision(self) -> "Swipe":
        allowed = {"like": (), "reject": REJECT_REASONS, "skip": SKIP_REASONS}[self.decision]
        wrong = [r for r in self.reasons if r not in allowed]
        if wrong:
            raise ValueError(f"{', '.join(wrong)} isn't a reason for a {self.decision}")
        if self.note and "other" not in self.reasons:
            raise ValueError('a note goes with the reason "other"')
        if self.note and pii.find_pii(self.note):
            raise ValueError("the note contains contact details; scrub it first")
        return self

    @property
    def verdict(self) -> bool:
        return self.decision in ("like", "reject")


class DuplicateEvidence(_Strict):
    signal: Literal["area", "size", "floor", "price", "bedrooms", "text", "photo_hash"]
    detail: str


class DuplicateCluster(_Strict):
    """Listings that look like the same property, with the evidence and price range."""

    cluster_id: str
    listing_ids: list[str] = Field(min_length=2)
    evidence: list[DuplicateEvidence] = Field(default_factory=list)
    price_min_eur: int | None = None
    price_max_eur: int | None = None
    decided_by: Literal["code", "model", "human"] = "code"

    @field_validator("listing_ids")
    @classmethod
    def _unique(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("a listing appears twice in the cluster")
        return value

    def label(self) -> str:
        """Plain-English summary, such as "Listed 3 times, €185k to €199k"."""
        text = f"Listed {len(self.listing_ids)} times"
        if self.price_min_eur and self.price_max_eur:
            low, high = round(self.price_min_eur / 1000), round(self.price_max_eur / 1000)
            text += f", €{low}k" if low == high else f", €{low}k to €{high}k"
        return text
