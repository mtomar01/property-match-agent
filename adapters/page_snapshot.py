"""Build a product dataset from Spitogatos listing pages: the D68 pipeline.

Every new, refreshed or expanded dataset goes through this, not result cards
alone. For each listing page that was saved (data/private/*details_raw.jsonl):

1. The result card gives what only it has: area, sub-area, link, the date it
   was first seen, any photo link (adapters/spitogatos_cards.py).
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

The file formats are in docs/collecting.md. A page record may carry its own
crossed-out lists ("crossed") and its first photo link ("photo_url"); the
20 October pages take theirs from the revisit file (D34) when it's there.
A listing whose page couldn't be read keeps its card alone, and is counted.
"""

from __future__ import annotations

import argparse
import glob
import json
from datetime import date
from pathlib import Path

from adapters import spitogatos_cards
from adapters import spitogatos_features as features
from agent import llm
from agent.extraction import PROMPT_VERSION, apply_walking_rule, merge, parse_reading
from core import pii
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


def _lines(paths: list[Path]) -> list[dict]:
    return [json.loads(line) for path in paths for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


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
          raw_cards: list[Path] | None = None) -> dict:
    """Listings from cards plus pages. Cards come either as a Listing snapshot (cards_path) or as raw result cards."""
    problems: list[str] = []
    if raw_cards:
        cards, problems = cards_from_raw(raw_cards)
    else:
        cards = {json.loads(l)["listing_id"]: json.loads(l) for l in cards_path.read_text(encoding="utf-8").splitlines() if l.strip()}
    records = _lines(raw if isinstance(raw, list) else [raw])
    if features.REVISIT.exists():  # the 20 October pages: their crossed-out lists came later (D34)
        revisit = features.load()
        records = [r if r.get("crossed") else features.attach([r], revisit)[0] for r in records]
    client = client or _NoClient()
    rows, paid, with_page = [], {}, set()
    from adapters.spitogatos_details import parse_details
    for record in records:
        listing_id = f"spitogatos:{record['source_id']}"
        card = cards.get(listing_id)
        if card is None:
            problems.append(f"{listing_id}: no result card, so no area or link")
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
    card_only = [lid for lid in cards if lid not in with_page] if raw_cards else []
    for listing_id in card_only:  # a page that failed or wasn't reached: the card alone, counted below
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
    summary = {"listings": len(rows), "with_page": len(with_page), "card_only": len(card_only), "by_area": areas,
               "refused": problems, "known": known,
               "haiku_paid_usd": round(llm.cost_usd(MODEL, paid), 4) if paid else 0.0, "out": str(out)}
    return summary


def _paths(pattern: str) -> list[Path]:
    found = sorted(Path(p) for p in glob.glob(pattern))
    if not found:
        raise SystemExit(f"no files match {pattern}")
    return found


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build a product dataset from Spitogatos cards and listing pages (D68).")
    parser.add_argument("--pages", help="raw listing pages, a glob (default: the 100 pages of 20 October)")
    parser.add_argument("--cards", help="raw result cards, a glob; without it, cards come from data/private/snapshot.jsonl")
    parser.add_argument("--out", default=str(OUT), help="where to write the dataset")
    args = parser.parse_args()
    result = build(_paths(args.pages) if args.pages else RAW, None if args.cards else CARDS, Path(args.out),
                   raw_cards=_paths(args.cards) if args.cards else None)
    print(json.dumps(result, ensure_ascii=False, indent=1))
