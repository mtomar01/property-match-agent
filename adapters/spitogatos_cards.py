"""Turn Spitogatos result cards (collected for personal use) into Listing records.

Input: data/private/spitogatos_cards_<date>.jsonl, one card per line, as read
from the results pages in a normal browser at a slow pace.
Output: data/private/snapshot.jsonl, which PM_SNAPSHOT can point the server at.

Code calculates, the model reasons: this parser only reads the parts of a card
that have a fixed structure (title, badges, price) plus the template sentences
Spitogatos writes itself ("Έχει κατασκευαστεί το 1969 ..."). Anything written
freely by an agency stays in the description for the model's extraction step
in v1, and its fields stay unknown until then.

Run: uv run python -m adapters.spitogatos_cards data/private/spitogatos_cards_2026-10-20.jsonl
"""

from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path

from core import greek, pii
from core.models import Listing

OUT = Path(__file__).resolve().parent.parent / "data" / "private" / "snapshot.jsonl"

TITLE = re.compile(r"^(?P<type>.+?),\s*(?P<size>[\d.,]+)\s*τ\.μ\.$")
PRICE = re.compile(r"^€\s*(?P<price>[\d.]+)$")
TEMPLATE = {
    "year_built": re.compile(r"κατασκευαστεί το (\d{4})"),
    "renovated_year": re.compile(r"ανακαινίστηκε το (\d{4})"),
    "heating": re.compile(r"θέρμανση του ακινήτου είναι ([^,.]+?)(?:,|\.| ενώ|$)"),
    "energy_class": re.compile(r"ενεργειακό πιστοποιητικό:\s*([^\s,.]+)"),
    "parking": re.compile(r"θέσεις στάθμευσης \(([^)]+)\)"),
}
FLOOR_BADGES = {"ΙΣ", "ΥΠ", "ΗΜ/ΥΠ", "ΗΜ"}


def _number(text: str) -> float:
    """'1.760' is 1760 and '105,20' is 105.2 (Greek thousands and decimals)."""
    text = text.strip()
    if "," in text:
        return float(text.replace(".", "").replace(",", "."))
    return float(text.replace(".", ""))


def parse_card(card: dict, seen: date) -> Listing:
    lines = [line.strip() for line in card["card_text"].split("\n")]
    lines = [line for line in lines if line and not re.fullmatch(r"Item \d+ of \d+", line)]
    if lines and lines[0].isdigit():
        lines = lines[1:]  # photo count

    title_idx = next(i for i, line in enumerate(lines) if TITLE.match(line))
    title = lines[title_idx]
    match = TITLE.match(title)
    rest = lines[title_idx + 1:]
    if rest and rest[0] == title:
        rest = rest[1:]  # the title is printed twice
    sub_area_line = rest[0] if rest else ""
    description = rest[1] if len(rest) > 1 else ""
    tail = rest[2:]

    floor_raw = bedrooms = bathrooms = None
    prices: list[int] = []
    badges: list[str] = []
    for i, token in enumerate(tail):
        nxt = tail[i + 1] if i + 1 < len(tail) else ""
        if token in FLOOR_BADGES:
            floor_raw = token
        elif token.isdigit() and nxt == "ος":
            floor_raw = f"{token}ος"
        elif token.isdigit() and nxt == "υ/δ":
            bedrooms = int(token)
        elif token.isdigit() and nxt == "μπ":
            bathrooms = int(token)
        elif PRICE.match(token):
            prices.append(int(PRICE.match(token).group("price").replace(".", "")))
        elif token.isupper() and token.isalpha():
            badges.append(token)  # e.g. ΝΕΟΔΜΗΤΟ

    evidence: dict[str, str] = {}
    found: dict[str, str] = {}
    for field, pattern in TEMPLATE.items():
        hit = pattern.search(description)
        if hit:
            found[field] = hit.group(1).strip()
            evidence[field] = hit.group(0)[:80]

    sub_area = re.sub(r"\s*\(.*\)$", "", sub_area_line) or None
    area = greek.normalise_area(sub_area_line) or greek.normalise_area(card.get("area_query", ""))
    condition = "new_build" if "ΝΕΟΔΜΗΤΟ" in badges else greek.normalise_condition(description)

    listing = Listing(
        listing_id=f"spitogatos:{card['source_id']}",
        source="spitogatos",
        url=card["url"],
        listing_type="sale",
        first_seen=seen,
        last_seen=seen,
        price_eur=prices[0] if prices else None,
        price_history=[{"date": seen, "price_eur": p} for p in prices[1:2]],
        size_m2=_number(match.group("size")),
        property_type=greek.normalise_property_type(match.group("type")),
        bedrooms=bedrooms,
        bathrooms=bathrooms,
        floor={"raw": floor_raw, "class": greek.normalise_floor(floor_raw)},
        year_built=int(found["year_built"]) if "year_built" in found else None,
        renovated_year=int(found["renovated_year"]) if "renovated_year" in found else None,
        condition=condition,
        energy_class={"raw": found.get("energy_class"), "value": greek.normalise_energy_class(found.get("energy_class"))},
        heating=greek.normalise_heating(found.get("heating")),
        parking=greek.normalise_parking(found.get("parking")),
        area=area,
        sub_area=sub_area,
        photo_urls=[card["photo_url"]] if card.get("photo_url") else [],
        title=title,
        description=pii.scrub(description),
        field_confidence={field: 1.0 for field in found},
        evidence={k: pii.scrub(v) for k, v in evidence.items()},
    )
    return listing


def convert(cards_path: Path, out_path: Path = OUT) -> tuple[int, list[str]]:
    problems: list[str] = []
    written = 0
    with cards_path.open(encoding="utf-8") as src, out_path.open("w", encoding="utf-8") as dst:
        for line in src:
            card = json.loads(line)
            card["card_text"] = pii.scrub(card["card_text"])
            try:
                listing = parse_card(card, date.fromisoformat(card["seen"]))
            except Exception as exc:  # noqa: BLE001 - report and carry on
                problems.append(f"{card.get('source_id')}: {exc}")
                continue
            dst.write(json.dumps(listing.model_dump(by_alias=True, mode="json"), ensure_ascii=False) + "\n")
            written += 1
    return written, problems


if __name__ == "__main__":
    source = Path(sys.argv[1])
    count, issues = convert(source)
    print(f"Wrote {count} listings to {OUT}")
    for issue in issues:
        print("  skipped", issue)
