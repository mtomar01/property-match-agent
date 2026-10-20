"""Build the private snapshot from every collected source.

Reads the card files in data/private/, converts each source with its own
parser, and writes one merged data/private/snapshot.jsonl for PM_SNAPSHOT.
Everything here stays local: data/private/ is gitignored.

Run: uv run python -m adapters.private_snapshot
"""

from __future__ import annotations

from pathlib import Path

from adapters import spiti24_cards, spitogatos_cards

PRIVATE = Path(__file__).resolve().parent.parent / "data" / "private"
PARSERS = {"spitogatos": spitogatos_cards.convert, "spiti24": spiti24_cards.convert}


def build() -> Path:
    merged = PRIVATE / "snapshot.jsonl"
    lines: list[str] = []
    for source, convert in PARSERS.items():
        for cards in sorted(PRIVATE.glob(f"{source}_cards_*.jsonl")):
            part = PRIVATE / f"snapshot_{source}.jsonl"
            count, problems = convert(cards, part)
            print(f"{source}: {count} listings from {cards.name}" + (f", {len(problems)} skipped" if problems else ""))
            lines += part.read_text(encoding="utf-8").splitlines()
    merged.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {len(lines)} listings to {merged}")
    return merged


if __name__ == "__main__":
    build()
