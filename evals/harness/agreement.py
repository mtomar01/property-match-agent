"""How often two sets of labels agree, field by field.

Used twice: for your own relabel a week later (self-agreement, docs/labelling-guide.md)
and for a second labeller on the hosted page (D28). Agreement is the share of
fields where both labels hold the same value; both blank counts as agreeing,
because "unknown" is a real answer. Listings either labeller marked as gone
from the live site are left out.

Fields are also split into those the tool showed pre-filled from the page's
table (structured) and the rest (free text), because disagreement on free text
is where the guide's rules are most likely to be unclear.

Run: uv run python -m evals.harness.agreement first.jsonl second.jsonl
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

from evals.harness.labels import LABEL_FIELDS, ExtractionLabel, check, comparable

TARGET = 0.95


def _same(name: str, a, b) -> bool:
    a, b = comparable(name, a), comparable(name, b)
    if isinstance(a, float) or isinstance(b, float):
        return a is not None and b is not None and abs(a - b) < 0.01
    return a == b


@dataclass
class Agreement:
    listings: int = 0
    skipped_gone: int = 0
    per_field: dict[str, list[int]] = field(default_factory=dict)  # name -> [agreed, compared]
    structured: list[int] = field(default_factory=lambda: [0, 0])
    free_text: list[int] = field(default_factory=lambda: [0, 0])
    disagreements: list[tuple[str, str, object, object]] = field(default_factory=list)

    @property
    def overall(self) -> float:
        agreed = sum(a for a, _ in self.per_field.values())
        compared = sum(c for _, c in self.per_field.values())
        return agreed / compared if compared else 0.0


def compare(first: list[ExtractionLabel], second: list[ExtractionLabel]) -> Agreement:
    other = {label.listing_id: label for label in second}
    result = Agreement(per_field={name: [0, 0] for name in LABEL_FIELDS})
    for a in first:
        b = other.get(a.listing_id)
        if b is None:
            continue
        if "gone" in (a.live_page, b.live_page):
            result.skipped_gone += 1
            continue
        result.listings += 1
        for name in LABEL_FIELDS:
            va, vb = getattr(a.fields, name), getattr(b.fields, name)
            same = _same(name, va, vb)
            result.per_field[name][0] += same
            result.per_field[name][1] += 1
            bucket = result.structured if name in a.prefilled else result.free_text
            bucket[0] += same
            bucket[1] += 1
            if not same:
                result.disagreements.append((a.listing_id, name, va, vb))
    return result


def _pct(agreed: int, compared: int) -> str:
    return f"{agreed / compared:.0%}" if compared else "n/a"


def report(result: Agreement) -> str:
    lines = [
        f"Listings compared: {result.listings} (left out as gone: {result.skipped_gone})",
        f"Overall agreement: {result.overall:.1%} (target {TARGET:.0%})",
        f"Pre-filled from the table: {_pct(*result.structured)}   Free text: {_pct(*result.free_text)}",
        "",
        "Field                agreed",
    ]
    for name, (agreed, compared) in sorted(result.per_field.items(), key=lambda kv: kv[1][0] / max(kv[1][1], 1)):
        if compared:
            lines.append(f"{name:<20} {agreed}/{compared} {_pct(agreed, compared)}")
    if result.disagreements:
        lines += ["", "Disagreements (listing, field, first, second):"]
        lines += [f"  {lid}  {name}: {va!r} vs {vb!r}" for lid, name, va, vb in result.disagreements]
    return "\n".join(lines)


if __name__ == "__main__":
    first, problems_a = check(Path(sys.argv[1]))
    second, problems_b = check(Path(sys.argv[2]))
    for problem in problems_a + problems_b:
        print("problem:", problem)
    outcome = compare(first, second)
    print(report(outcome))
    sys.exit(0 if outcome.overall >= TARGET else 1)
