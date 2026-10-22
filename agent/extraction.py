"""Extraction: the model reads a listing's description, code does the rest (D33).

The split follows the project rule "code calculates, the model reasons":

- Code reads the page's fixed parts: the table, the ticked features and the
  result card (adapters/spitogatos_details.py). It is right 98.7% of the time
  on those fields, so the model isn't asked to redo that work.
- The model reads only the description, the prose code can't parse reliably,
  and reports what the description itself states, with a quote for each fact.
- Code merges the two. When the description and the table say different
  things, the field becomes unknown (the conflict rule, D25), except price and
  size, where the table wins. Doing this in code means the model never has to
  decide which source to trust, and the rule can't drift with the prompt.
- Code also does the arithmetic: metres to the metro become minutes on foot
  (80 m a minute, rounded up), the same rule the scoring uses (D31).

The prompt lives in prompts/ with a version number; the glossary in it comes
from core/greek.py, the same table the MCP server serves.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

from core import greek, pii
from core.models import Condition, EnergyClass, Flag, Fuel, HeatingType, Parking, PropertyType
from evals.harness.labels import LABEL_FIELDS, PARKING_PRESENT, comparable

ROOT = Path(__file__).resolve().parents[1]
PROMPTS = ROOT / "prompts"
PROMPT_VERSION = "extraction_v3"
MAX_TOKENS = 2000

FLOORS = list(greek.SPECIAL_FLOORS) + [str(n) for n in range(1, 13)]
TABLE_WINS = ("price_eur", "size_m2")          # D25: the table wins for these two
CODE_ONLY = ("listing_type", "area", "sub_area")  # from the result card, never from prose
METRES_PER_MINUTE = 80

_CHOICES = {
    "property_type": PropertyType.__args__, "floor_class": tuple(FLOORS), "condition": Condition.__args__,
    "energy_class": EnergyClass.__args__, "heating_type": HeatingType.__args__, "heating_fuel": Fuel.__args__,
    "parking": Parking.__args__,
}
_INTEGERS = ("price_eur", "bedrooms", "bathrooms", "year_built", "renovated_year", "metro_minutes", "metro_metres")
_NUMBERS = ("size_m2", "metro_km")
_BOOLEANS = ("lift", "balcony", "storage")
READ_FIELDS = ("price_eur", "size_m2", "property_type", "bedrooms", "bathrooms", "floor_class", "year_built",
               "renovated_year", "condition", "energy_class", "heating_type", "heating_fuel", "parking", "lift",
               "balcony", "storage", "flags", "metro_minutes", "metro_metres", "metro_km")
EARLY = ("extraction_v1", "extraction_v2")  # before v3 there was no kilometres field and no metro glossary (D40)


def read_fields(version: str = PROMPT_VERSION) -> tuple[str, ...]:
    return tuple(f for f in READ_FIELDS if f != "metro_km") if version in EARLY else READ_FIELDS


# v2 dropped "good": the labelling guide has no such condition, so v1 offering
# it made the model turn "σε καλή κατάσταση" into a value the key never holds.
CONDITIONS_BY_VERSION = {"extraction_v1": Condition.__args__,
                         "extraction_v2": tuple(c for c in Condition.__args__ if c != "good")}


def _property(name: str, version: str) -> dict:
    if name == "condition":
        return {"enum": [*CONDITIONS_BY_VERSION.get(version, CONDITIONS_BY_VERSION["extraction_v2"]), None]}
    if name in _CHOICES:
        return {"enum": [*_CHOICES[name], None]}
    if name in _BOOLEANS:
        return {"enum": [True, False, None]}
    if name in _INTEGERS:
        return {"type": ["integer", "null"]}
    if name in _NUMBERS:
        return {"type": ["number", "null"]}
    if name == "flags":
        return {"type": "array", "items": {"enum": list(Flag.__args__)}}
    raise KeyError(name)


def schema(version: str = PROMPT_VERSION) -> dict:
    """The answer's shape. Versioned with the prompt, so an old run's cached answers still match.

    Evidence comes first, so the model quotes before it answers: each value then
    rests on words it has just copied from the listing.
    """
    fields = read_fields(version)
    return {
        "type": "object",
        "properties": {
            "evidence": {"type": "array", "items": {
                "type": "object",
                "properties": {"field": {"enum": list(fields)}, "quote": {"type": "string"}},
                "required": ["field", "quote"], "additionalProperties": False}},
            **{name: _property(name, version) for name in fields},
        },
        "required": ["evidence", *fields],
        "additionalProperties": False,
    }


SCHEMA = schema()


def glossary_text(version: str = PROMPT_VERSION) -> str:
    rows = greek.GLOSSARY_BASE if version in EARLY else greek.GLOSSARY
    return "\n".join(f"- {row['greek']}: {row['meaning']} ({row['normalised']})" for row in rows)


def system_prompt(version: str = PROMPT_VERSION) -> str:
    template = (PROMPTS / f"{version}.md").read_text(encoding="utf-8")
    return template.replace("{{GLOSSARY}}", glossary_text(version))


def user_message(description: str, seen: str | None) -> str:
    return f"Page saved on: {seen or 'unknown'}\n\n<description>\n{description.strip()}\n</description>"


def request(description: str, seen: str | None, model: str, version: str = PROMPT_VERSION) -> dict:
    """The exact request body, so the cache key and the call can't drift apart."""
    return {
        "model": model,
        "max_tokens": MAX_TOKENS,
        "system": [{"type": "text", "text": system_prompt(version), "cache_control": {"type": "ephemeral"}}],
        "messages": [{"role": "user", "content": user_message(description, seen)}],
        "output_config": {"format": {"type": "json_schema", "schema": schema(version)}},
    }


class ExtractionError(RuntimeError):
    pass


def call(client, body: dict) -> tuple[dict, object]:
    """One model call. Returns the parsed JSON and the raw response."""
    response = client.messages.create(**body)
    if response.stop_reason in ("refusal", "max_tokens"):
        raise ExtractionError(f"stopped with {response.stop_reason}")
    text = next((block.text for block in response.content if block.type == "text"), "")
    try:
        return json.loads(text), response
    except json.JSONDecodeError as err:
        raise ExtractionError(f"not JSON: {err}") from err


def _in_range(value, low, high):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) and low <= value <= high else None


def parse_reading(raw: dict) -> dict:
    """The model's answer as label fields, cleaned by code.

    Enum casing isn't guaranteed by the API, so choices are matched without
    case. Numbers outside sane ranges become unknown rather than being trusted.
    """
    fields: dict = {}
    for name in READ_FIELDS:
        value = raw.get(name)
        if name in _CHOICES and isinstance(value, str):
            lookup = {str(c).lower(): c for c in _CHOICES[name]}
            value = lookup.get(value.strip().lower())
        fields[name] = value
    fields["price_eur"] = _in_range(fields["price_eur"], 1000, 50_000_000)
    fields["size_m2"] = _in_range(fields["size_m2"], 5, 10_000)
    fields["bedrooms"] = _in_range(fields["bedrooms"], 0, 30)
    fields["bathrooms"] = _in_range(fields["bathrooms"], 0, 20)
    fields["year_built"] = _in_range(fields["year_built"], 1800, 2035)
    fields["renovated_year"] = _in_range(fields["renovated_year"], 1900, 2035)
    for name in _BOOLEANS:
        if not isinstance(fields[name], bool):
            fields[name] = None
    fields["flags"] = sorted({f for f in (fields.get("flags") or []) if f in Flag.__args__})

    minutes = _in_range(fields.pop("metro_minutes"), 1, 60)
    metres = _in_range(fields.pop("metro_metres"), 20, 5000)
    km = _in_range(fields.pop("metro_km", None), 0.02, 5)
    if metres is None and km is not None:
        metres = km * 1000  # code does the arithmetic (D40)
    fields["metro_walk_min"] = minutes if minutes is not None else (math.ceil(metres / METRES_PER_MINUTE) if metres else None)
    fields["metro_from"] = "minutes" if minutes is not None else ("distance" if metres else None)

    evidence = {}
    for item in raw.get("evidence") or []:
        name, quote = item.get("field"), (item.get("quote") or "").strip()
        if name in READ_FIELDS and quote and name not in evidence:
            evidence["metro_walk_min" if name.startswith("metro_") else name] = pii.scrub(quote)[:200]
    fields["evidence"] = evidence
    return fields


WALKING = re.compile(r"π[όο]δια|περπ[άα]τ|πεζ[ήηόο]", re.I)


def walking_stated(quote: str, description: str) -> bool:
    """Whether the description says "on foot" next to the minutes the model quoted (D41)."""
    if not quote:
        return False
    at = description.find(quote)
    span = description[max(0, at - 20): at + len(quote) + 20] if at >= 0 else quote
    return bool(WALKING.search(span))


def apply_walking_rule(fields: dict, description: str) -> dict:
    """Minutes to the metro count only when the listing says on foot (your rule, D41).

    "μόλις 5 λεπτά από το Μετρό" doesn't say how, and a 5-minute walk would say
    so. Metres and kilometres are distances, so they count as written. Done in
    code, so it holds whatever the model does.
    """
    if fields.get("metro_from") == "minutes" and not walking_stated(fields.get("evidence", {}).get("metro_walk_min", ""), description):
        fields = dict(fields, metro_walk_min=None, metro_from=None)
    return fields


def reconcile(name: str, mine, theirs):
    """Two values that differ but don't contradict each other, per the labelling guide.

    υπερυψωμένο ισόγειο is a more exact "ground", not a conflict; a ρετιρέ
    with a floor number takes the number; storage or parking the text
    mentions counts even when the feature list crosses it out (D34, D35). Returns the value to keep, or None
    when the two really disagree.
    """
    if comparable(name, mine) == comparable(name, theirs):
        return mine
    if name == "storage" and theirs is True and mine is False:
        return True  # "εσωτερική αποθήκη" is storage even when the list crosses Αποθήκη out (D34)
    if name == "parking" and mine == "none" and theirs in PARKING_PRESENT:
        return theirs  # parking the text mentions counts even when Parking is crossed out (D35)
    if name == "floor_class":
        if {mine, theirs} == {"ground", "raised_ground"}:
            return "raised_ground"
        if "top" in (mine, theirs):
            other = theirs if mine == "top" else mine
            return other if str(other).isdigit() else None
    return None


def merge(code: dict, text: dict, rule: str = "conflict") -> tuple[dict, list[str]]:
    """Combine what code read from the page with what the model read in the description.

    rule "fill": code first, the description only fills blanks (like the baseline).
    rule "conflict": as "fill", but when both have a value and they differ, the
    field becomes unknown (D25), except price and size, where the table wins.
    Flags are only ever positive, so the two lists are joined.
    Returns the fields and the names of the fields the conflict rule blanked.
    """
    if rule not in ("fill", "conflict"):
        raise ValueError(rule)
    out = {name: code.get(name) for name in LABEL_FIELDS}
    conflicts: list[str] = []
    for name in LABEL_FIELDS:
        if name in CODE_ONLY:
            continue
        mine, theirs = code.get(name), text.get(name)
        if name == "flags":
            out[name] = sorted(set(mine or []) | set(theirs or []))
            continue
        if theirs is None:
            continue
        if mine is None:
            out[name] = theirs
        elif name in TABLE_WINS:
            continue
        elif (kept := reconcile(name, mine, theirs)) is not None:
            out[name] = kept
        elif rule == "conflict":
            out[name] = None
            conflicts.append(name)
    return out, conflicts
