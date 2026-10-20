"""Build the private extraction labeller: one HTML file with the listings inside.

Reads the collected detail pages and the private snapshot, works out what code
can read from each page (adapters/spitogatos_details.py), and writes a single
offline HTML file to data/private/labels/. Open it in a browser, label, and
export the labels as JSONL. Then check them with evals/harness/labels.py.

The file holds real listing text, so it lives in data/private/ (git ignores
it) and is never published as a web page. Contact details are scrubbed before
collection; this script checks again and refuses to build if any remain.

Run: uv run python -m evals.harness.build_label_tool
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

from adapters.spitogatos_details import parse_details, parse_table
from core import pii
from evals.harness.labels import prefill

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "private" / "spitogatos_details_raw.jsonl"
SNAPSHOT = ROOT / "data" / "private" / "snapshot.jsonl"
TEMPLATE = Path(__file__).with_name("label_tool.html")
OUT = ROOT / "data" / "private" / "labels" / "extraction_labeller_round1.html"

# Table rows that never help a label and only add noise on screen.
HIDDEN_ROWS = {"Τιμή ανά τ.μ.", "Κωδικός Συστήματος", "Κωδικός Ακινήτου", "Δημοσίευση αγγελίας", "Τελευταία ενημέρωση"}
SEED = 2026  # a fixed shuffle mixes the three areas but stays the same on every build


def _json_for_script(payload: dict) -> str:
    """JSON that can't end the <script> element it sits in, whatever the listing says."""
    text = json.dumps(payload, ensure_ascii=False)
    for char, escape in (("<", "\\u003c"), (">", "\\u003e"), ("&", "\\u0026"), (" ", "\\u2028"), (" ", "\\u2029")):
        text = text.replace(char, escape)
    return text


def build_items(raw_records: list[dict], cards: dict[str, dict]) -> list[dict]:
    items = []
    for record in raw_records:
        listing_id = f"spitogatos:{record['source_id']}"
        card = cards.get(listing_id, {})
        details = parse_details(record)
        table, _ = parse_table(record["sections"].get("Χαρακτηριστικά"))
        item = {
            "listing_id": listing_id,
            "url": record["url"],
            "title": card.get("title"),
            "area": card.get("area"),
            "table": [[key, " · ".join(values)] for key, values in table.items() if key not in HIDDEN_ROWS],
            "ticked": details.ticked,
            "extras": details.extras,
            "description": record["sections"].get("Περιγραφή", ""),
            "prefill": prefill(details, card),
        }
        # Check the listing text only: ids and links are long digit runs by design.
        text = [item["title"] or "", item["description"]] + [value for _, value in item["table"]]
        text += [line for lines in item["ticked"].values() for line in lines] + [str(v) for v in item["extras"].values()]
        if any(pii.find_pii(part) for part in text):
            raise ValueError(f"{listing_id} still holds contact details; scrub the raw file first")
        items.append(item)
    random.Random(SEED).shuffle(items)
    return items


def build(raw_path: Path = RAW, snapshot_path: Path = SNAPSHOT, out_path: Path = OUT, round_no: int = 1) -> int:
    raw_records = [json.loads(line) for line in raw_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    cards = {}
    for line in snapshot_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            card = json.loads(line)
            cards[card["listing_id"]] = card
    items = build_items(raw_records, cards)
    html = TEMPLATE.read_text(encoding="utf-8")
    if html.count("__DATA_JSON__") != 1:
        raise ValueError("the template must hold exactly one __DATA_JSON__ placeholder")
    html = html.replace("__DATA_JSON__", _json_for_script({"round": round_no, "items": items}))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return len(items)


if __name__ == "__main__":
    count = build()
    print(f"Wrote {count} listings to {OUT.relative_to(ROOT)}")
    sys.exit(0)
