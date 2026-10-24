"""Build a product dataset from Spitogatos listing pages: the D68 pipeline.

Every new, refreshed or expanded dataset goes through this, not result cards
alone. For each listing page that was saved (data/private/*details_raw.jsonl):

1. The page itself gives type and size (its title), bedrooms and bathrooms
   (its room badges) and the neighbourhood (the line under the title); the area
   is the one that was searched, which on 20 October matched the card's own
   area for 270 of 270 listings (Mike, D70). Result cards are only a check now.
   Pages saved before 24 October lack those parts and still take them from
   their card.
2. Code reads the page's table and its ticked and crossed-out features
   (adapters/spitogatos_details.py, evals/harness/code_baseline.from_page).
3. Haiku 5.5 reads the description (prompt extraction_v3), and code applies
   the on-foot rule for the metro (D41).
4. The two merge with the "fill" rule the evals measured (D33, D45): the page
   first, the description filling what the page leaves blank.
5. Every record is checked against the Listing model, so contact details or
   an impossible value are refused, not stored.

Haiku answers are cached by a hash of the request, so listings already read
for the extraction eval cost nothing; only new pages are paid for.

    uv run python -m adapters.page_snapshot              # the 100 pages of 20 October
    uv run python -m adapters.page_snapshot --cards 'data/private/collect/cards_*.jsonl' \
        --pages 'data/private/collect/pages_*.jsonl' --out data/private/snapshot_2026-10-23.jsonl

    uv run python -m adapters.page_snapshot --pages 'data/private/collect/pages_*.jsonl' \
        --check-cards 'data/private/collect/cards_*.jsonl' --limit 50     # the page-only test (D70)

The file formats are in docs/collecting.md. A page record may carry its own
crossed-out lists ("crossed") and its first photo link ("photo_url"); the
20 October pages take theirs from the revisit file (D34) when it's there.
"""

from __future__ import annotations

import argparse
import glob
import json
import re
from datetime import date, datetime
from pathlib import Path

from adapters import spitogatos_cards
from adapters import spitogatos_features as features
from agent import llm
from agent.extraction import PROMPT_VERSION, apply_walking_rule, merge, parse_reading
from core import greek, pii
from core.models import covered_areas, set_covered_areas  # noqa: F401 - re-exported for the CLI summary
from core.models import EnergyRating, Floor, Heating, Listing, PricePoint
from evals.harness.code_baseline import from_page
from evals.harness.model_extraction import CACHE, read_one

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "data" / "private"
RAW = PRIVATE / "spitogatos_details_raw.jsonl"
CARDS = PRIVATE / "snapshot.jsonl"
OUT = PRIVATE / "snapshot_pages.jsonl"
MODEL = "claude-haiku-5-5"
SAME_FIELDS = ("price_eur", "size_m2", "property_type", "bedrooms", "bathrooms", "year_built", "renovated_year",
               "condition", "parking", "lift", "balcony", "storage", "flags", "metro_walk_min")


class _NoClient:
    """Stands in for the API client until a listing isn't in the cache: then the real one is made, once."""

    def __init__(self):
        self._real = None

    @property
    def messages(self):
        if self._real is None:
            self._real = llm.client()
        return self._real.messages


def to_listing(card: dict, record: dict, fields: dict, evidence: dict, details_extra: dict) -> Listing:
    """One Listing from the card, the page and the merged fields. Raises if anything breaks the model's rules."""
    seen = date.fromisoformat(record["seen"])
    data = {k: v for k, v in card.items() if k in Listing.model_fields}
    data.update({name: fields.get(name) for name in SAME_FIELDS})
    data["flags"] = sorted(set(fields.get("flags") or []))
    details = record["sections"]
    data["floor"] = Floor(raw=details_extra.get("floor_raw") or (card.get("floor") or {}).get("raw"),
                          floor_class=fields.get("floor_class")).model_dump(by_alias=True)
    data["energy_class"] = EnergyRating(raw=details_extra.get("energy_raw"), value=fields.get("energy_class")).model_dump()
    data["heating"] = Heating(raw=details_extra.get("heating_raw"), type=fields.get("heating_type"),
                              fuel=fields.get("heating_fuel")).model_dump()
    if record.get("photo_url") and str(record["photo_url"]).startswith("https://"):
        data["photo_urls"] = [record["photo_url"]]  # the page's first photo: a link, never a file (D64)
    history = [PricePoint(**p) for p in card.get("price_history") or []]
    if details_extra.get("old_price_eur") and not history:
        history.append(PricePoint(date=seen, price_eur=details_extra["old_price_eur"]))
    if fields.get("price_eur") and (not history or history[-1].price_eur != fields["price_eur"]):
        history.append(PricePoint(date=seen, price_eur=fields["price_eur"]))
    data["price_history"] = [p.model_dump(mode="json") for p in history]
    data["description"] = pii.scrub(details.get("Περιγραφή") or card.get("description") or "") or None
    data["evidence"] = {**(card.get("evidence") or {}), **{k: pii.scrub(v)[:200] for k, v in evidence.items() if v}}
    data["last_seen"] = max(seen, date.fromisoformat(card["last_seen"])).isoformat()
    data["field_confidence"] = {}
    return Listing.model_validate(data)


PUBLISHED = re.compile(r"Δημοσίευση αγγελίας\n(\d{2}/\d{2}/\d{4})")
BEDROOM_WORDS = ("υ/δ", "υπνοδωμ", "bedroom")
BATHROOM_WORDS = ("μπ", "μπάνι", "λουτρ", "wc", "bath")
CHECKED = ("area", "sub_area", "property_type", "size_m2", "bedrooms", "bathrooms", "price_eur")


def rooms_of(text: str | None) -> tuple[int | None, int | None]:
    """Bedrooms and bathrooms from the room badges ("2 υ/δ", "1 μπ"). A bare number takes the badges' order:
    the bedroom badge comes first on the page."""
    bedrooms = bathrooms = None
    bare = []
    for line in (text or "").split("\n"):
        hit = re.search(r"(\d+)\s*(.*)", line.strip())
        if not hit:
            continue
        number, word = int(hit.group(1)), hit.group(2).lower()
        if any(w in word for w in BEDROOM_WORDS):
            bedrooms = number
        elif any(w in word for w in BATHROOM_WORDS):
            bathrooms = number
        else:
            bare.append(number)
    if bare and bedrooms is None:
        bedrooms = bare.pop(0)
    if bare and bathrooms is None:
        bathrooms = bare.pop(0)
    return bedrooms, bathrooms


def neighbourhood_of(location: str | None) -> str | None:
    """"Λιούμη, Αιγάλεω (Αθήνα - Δυτικά Προάστια)" becomes "Λιούμη"; "Παγκράτι (Αθήνα - Κέντρο)" becomes "Παγκράτι"."""
    if not location:
        return None
    first = re.sub(r"\s*\(.*\)$", "", location.split("\n")[0].strip())
    return first.split(",")[0].strip() or None


def card_from_page(record: dict) -> dict:
    """What a result card used to give, read from the page itself (D70). Raises if the page lacks its title."""
    seen = date.fromisoformat(record["seen"])
    title_line = next((l.strip() for l in (record.get("title") or "").split("\n") if spitogatos_cards.TITLE.match(l.strip())), None)
    if not title_line:
        raise ValueError("no title like 'Διαμέρισμα, 86τ.μ.' on the page")
    match = spitogatos_cards.TITLE.match(title_line)
    area = greek.normalise_area(record.get("area_query") or "")
    if area is None:
        raise ValueError(f"the searched area {record.get('area_query')!r} isn't a known area")
    bedrooms, bathrooms = rooms_of(record.get("rooms"))
    stated = PUBLISHED.search(record["sections"].get("Χαρακτηριστικά", ""))
    published = datetime.strptime(stated.group(1), "%d/%m/%Y").date() if stated else None
    from adapters.spitogatos_details import parse_details
    table = parse_details(record).fields
    return {"listing_id": f"spitogatos:{record['source_id']}", "source": "spitogatos", "url": record["url"],
            "listing_type": "sale", "first_seen": seen.isoformat(), "last_seen": seen.isoformat(),
            "published": min(published, seen).isoformat() if published else None,
            "price_eur": table.get("price_eur"), "size_m2": table.get("size_m2") or spitogatos_cards._number(match.group("size")),
            "property_type": greek.normalise_property_type(match.group("type")), "bedrooms": bedrooms, "bathrooms": bathrooms,
            "area": area, "sub_area": neighbourhood_of(record.get("location")), "title": title_line,
            "price_history": [], "photo_urls": [], "evidence": {}}


def compare(pages: dict[str, dict], cards: dict[str, dict]) -> dict:
    """How often the page-only reading agrees with the card, field by field, with the disagreements to read."""
    out = {name: {"agree": 0, "differ": 0, "page_only": 0, "card_only": 0} for name in CHECKED}
    differ = []
    for listing_id, page in pages.items():
        card = cards.get(listing_id)
        if card is None:
            continue
        for name in CHECKED:
            mine, theirs = page.get(name), card.get(name)
            if mine is None and theirs is None:
                continue
            key = "agree" if mine == theirs else "page_only" if theirs is None else "card_only" if mine is None else "differ"
            out[name][key] += 1
            if key == "differ" or key == "card_only":
                differ.append({"listing": listing_id, "field": name, "page": mine, "card": theirs})
    compared = sum(1 for lid in pages if lid in cards)
    return {"listings_compared": compared, "by_field": out, "disagreements": differ[:40]}


def _lines(paths: list[Path]) -> list[dict]:
    # split on "\n" only: splitlines() also breaks on U+2028 and U+2029, which descriptions can hold raw (run of 23 October)
    return [json.loads(line) for path in paths for line in path.read_text(encoding="utf-8").split("\n") if line.strip()]


def cards_from_raw(paths: list[Path]) -> tuple[dict[str, dict], list[str]]:
    """Raw result cards (docs/collecting.md) as Listing dicts, by listing id, with the cards that couldn't be read."""
    out, problems = {}, []
    for card in _lines(paths):
        card["card_text"] = pii.scrub(card["card_text"])
        try:
            listing = spitogatos_cards.parse_card(card, date.fromisoformat(card["seen"]))
        except Exception as err:  # noqa: BLE001 - reported, never stored
            problems.append(f"card {card.get('source_id')}: {str(err).splitlines()[0]}")
            continue
        out.setdefault(listing.listing_id, listing.model_dump(by_alias=True, mode="json"))  # first sighting wins
    return out, problems


def build(raw: Path | list[Path] = RAW, cards_path: Path | None = CARDS, out: Path = OUT, client=None, cache_dir: Path = CACHE,
          raw_cards: list[Path] | None = None, check_cards: list[Path] | None = None, limit: int | None = None) -> dict:
    """Listings from listing pages (D68, D70).

    A page saved with its title, room badges, area line and searched area is read on its own; an older page
    takes those from its card (raw_cards, or the Listing snapshot at cards_path). check_cards are only compared.
    """
    problems: list[str] = []
    if raw_cards:
        cards, problems = cards_from_raw(raw_cards)
    elif cards_path is not None and cards_path.exists():
        cards = {json.loads(l)["listing_id"]: json.loads(l) for l in cards_path.read_text(encoding="utf-8").splitlines() if l.strip()}
    else:
        cards = {}
    records = _lines(raw if isinstance(raw, list) else [raw])
    # A listing saved twice (a refetch) keeps one record: one with its title and badges first, then the newest (D70).
    best: dict[str, dict] = {}
    for r in records:
        key, have = str(r["source_id"]), best.get(str(r["source_id"]))
        if have is None or (bool(r.get("title")), r.get("seen", "")) >= (bool(have.get("title")), have.get("seen", "")):
            best[key] = r
    records = list(best.values())
    if limit:  # a test on a few per area: the first `limit` pages, spread over the areas
        by_area: dict[str, list[dict]] = {}
        for r in records:
            by_area.setdefault(r.get("area_query") or "", []).append(r)
        per_area = max(1, limit // max(1, len(by_area)))
        records = [r for group in by_area.values() for r in group[:per_area]][:limit]
    page_cards: dict[str, dict] = {}
    if features.REVISIT.exists():  # the 20 October pages: their crossed-out lists came later (D34)
        revisit = features.load()
        records = [r if r.get("crossed") else features.attach([r], revisit)[0] for r in records]
    client = client or _NoClient()
    rows, paid, with_page = [], {}, set()
    from adapters.spitogatos_details import parse_details
    for record in records:
        listing_id = f"spitogatos:{record['source_id']}"
        if record.get("title") and record.get("area_query"):  # page-only (D70)
            try:
                card = page_cards[listing_id] = card_from_page(record)
            except Exception as err:  # noqa: BLE001 - reported, never stored
                problems.append(f"{listing_id}: {str(err).splitlines()[0]}")
                continue
        else:
            card = cards.get(listing_id)
        if card is None:
            problems.append(f"{listing_id}: an older page with no result card, so no area or link")
            continue
        reading = read_one(record, MODEL, PROMPT_VERSION, client, cache_dir)
        if not reading.get("cached"):
            llm.add_usage(paid, reading.get("usage") or {})
        text = parse_reading(reading["raw"]) if reading.get("raw") else {}
        description = record["sections"].get("Περιγραφή", "")
        text = apply_walking_rule(text, description) if text else text
        code = from_page(record, card)
        fields, _ = merge(code, text, "fill")
        page = parse_details(record)
        try:
            rows.append(to_listing(card, record, fields, text.get("evidence", {}), {**page.fields, **page.extras}))
            with_page.add(listing_id)
        except Exception as err:  # noqa: BLE001 - a refused record is reported, never stored
            problems.append(f"{listing_id}: {str(err).splitlines()[0]}")
    card_only = [lid for lid in cards if lid not in with_page] if raw_cards and not page_cards else []
    for listing_id in card_only:  # older pages only: a page that failed keeps its card alone, counted below
        rows.append(Listing.model_validate(cards[listing_id]))
    out.write_text("".join(r.model_dump_json(by_alias=True) + "\n" for r in rows), encoding="utf-8")
    known = {name: sum(1 for r in rows if getattr(r, name) is not None)
             for name in ("year_built", "renovated_year", "metro_walk_min", "parking", "lift", "balcony", "storage")}
    known["floor"] = sum(1 for r in rows if r.floor.floor_class)
    known["energy_class"] = sum(1 for r in rows if r.energy_class.value)
    known["photo"] = sum(1 for r in rows if r.photo_urls)
    areas: dict[str, int] = {}
    for r in rows:
        areas[r.area or "unknown"] = areas.get(r.area or "unknown", 0) + 1
    known["bedrooms"] = sum(1 for r in rows if r.bedrooms is not None)
    known["sub_area"] = sum(1 for r in rows if r.sub_area)
    summary = {"listings": len(rows), "with_page": len(with_page), "page_only": len(page_cards), "card_only": len(card_only),
               "by_area": areas, "refused": problems, "known": known,
               "haiku_paid_usd": round(llm.cost_usd(MODEL, paid), 4) if paid else 0.0, "out": str(out)}
    if check_cards:
        summary["check_against_cards"] = compare(page_cards, cards_from_raw(check_cards)[0])
    return summary


def _paths(pattern: str) -> list[Path]:
    found = sorted(Path(p) for p in glob.glob(pattern))
    if not found:
        raise SystemExit(f"no files match {pattern}")
    return found


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build a product dataset from Spitogatos cards and listing pages (D68).")
    parser.add_argument("--pages", help="raw listing pages, a glob (default: the 100 pages of 20 October)")
    parser.add_argument("--cards", help="raw result cards, for pages saved before 24 October that lack their title and badges")
    parser.add_argument("--check-cards", help="raw result cards to compare the page-only reading against; never used as data")
    parser.add_argument("--limit", type=int, help="read only this many pages, spread over the areas (a test)")
    parser.add_argument("--out", default=str(OUT), help="where to write the dataset")
    args = parser.parse_args()
    result = build(_paths(args.pages) if args.pages else RAW, None if args.pages else CARDS, Path(args.out),
                   raw_cards=_paths(args.cards) if args.cards else None,
                   check_cards=_paths(args.check_cards) if args.check_cards else None, limit=args.limit)
    print(json.dumps(result, ensure_ascii=False, indent=1))
