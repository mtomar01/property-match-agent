"""Turn spiti24 result cards (collected for personal use) into Listing records.

spiti24 cards carry less than Spitogatos cards: price, any recent price drop,
type, size, area and two icon numbers (bedrooms, bathrooms). There's no floor
and no description, so those stay unknown. That's useful in itself: spiti24
is in the same group as Spitogatos and many listings appear on both, which is
the "easy duplicates" case in spec section 11.

Card layout, one listing:
    [ΝΕΟΔΜΗΤΟ]
    <photo count>
    <price> € [<drop> € στις dd/mm/yyyy] <type> <size> m2 προς πώληση <area>, <sub-area>
     <bedrooms> <bathrooms>

Run: uv run python -m adapters.spiti24_cards data/private/spiti24_cards_2026-10-20.jsonl
"""

from __future__ import annotations

import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

from core import greek, pii
from core.models import Listing

OUT = Path(__file__).resolve().parent.parent / "data" / "private" / "snapshot_spiti24.jsonl"

MAIN = re.compile(
    r"(?P<price>[\d.]+)\s*€\s*"
    r"(?:(?P<drop>[\d.]+)\s*€\s*στις\s*(?P<drop_date>\d{2}/\d{2}/\d{4})\s*)?"
    r"(?P<type>.+?)\s+(?P<size>[\d.,]+)\s*m2\s+προς πώληση\s+(?P<place>[^\n]+)"
)


def _int(text: str) -> int:
    return int(text.replace(".", ""))


def _number(text: str) -> float:
    return float(text.replace(".", "").replace(",", ".")) if "," in text else float(text.replace(".", ""))


def parse_card(card: dict, seen: date) -> Listing:
    text = card["card_text"]
    match = MAIN.search(text)
    if not match:
        raise ValueError("not a full listing card")

    price = _int(match.group("price"))
    history = []
    if match.group("drop"):
        drop_date = datetime.strptime(match.group("drop_date"), "%d/%m/%Y").date()
        history.append({"date": drop_date, "price_eur": price + _int(match.group("drop"))})

    place = match.group("place").strip()
    parts = [p.strip() for p in place.split(",")]
    area = greek.normalise_area(parts[-1]) if len(parts) > 1 else None
    area = greek.normalise_area(parts[0]) or area or greek.normalise_area(card.get("area_query", ""))
    sub_area = parts[1] if len(parts) > 1 and greek.normalise_area(parts[0]) else None

    # Two numbers after the main line are bedrooms then bathrooms. One number on
    # its own can't be told apart, so both stay unknown rather than guessed.
    tail = text[match.end():].split()
    numbers = [int(t) for t in tail if t.isdigit()]
    bedrooms = bathrooms = None
    if len(numbers) >= 2:
        bedrooms, bathrooms = numbers[0], numbers[1]

    type_raw = match.group("type")
    return Listing(
        listing_id=f"spiti24:{card['source_id']}",
        source="spiti24",
        url=card["url"],
        listing_type="sale",
        first_seen=seen,
        last_seen=seen,
        price_eur=price,
        price_history=history,
        size_m2=_number(match.group("size")),
        property_type=greek.normalise_property_type(type_raw),
        bedrooms=bedrooms,
        bathrooms=bathrooms,
        condition="new_build" if "ΝΕΟΔΜΗΤΟ" in text else None,
        area=area,
        sub_area=pii.scrub(sub_area),
        photo_urls=[card["photo_url"]] if card.get("photo_url") else [],
        title=pii.scrub(f"{type_raw}, {match.group('size')}τ.μ., {place}"),
    )


def convert(cards_path: Path, out_path: Path = OUT) -> tuple[int, list[str]]:
    problems: list[str] = []
    written = 0
    with cards_path.open(encoding="utf-8") as src, out_path.open("w", encoding="utf-8") as dst:
        for line in src:
            card = json.loads(line)
            try:
                listing = parse_card(card, date.fromisoformat(card["seen"]))
            except Exception as exc:  # noqa: BLE001 - report and carry on
                problems.append(f"{card.get('source_id')}: {exc}")
                continue
            dst.write(json.dumps(listing.model_dump(by_alias=True, mode="json"), ensure_ascii=False) + "\n")
            written += 1
    return written, problems


if __name__ == "__main__":
    count, issues = convert(Path(sys.argv[1]))
    print(f"Wrote {count} listings to {OUT}")
    for issue in issues:
        print("  skipped", issue)
