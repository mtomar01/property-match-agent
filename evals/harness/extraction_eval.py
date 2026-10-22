"""Score a set of extraction predictions against a frozen answer key.

Each field of each listing lands in one of five outcomes:

- correct: same value (both blank counts, because "unknown" is an answer);
- wrong: both have a value and they differ;
- invented: the key says unknown, the prediction gives a value;
- missed: the key has a value, the prediction says unknown;
- (accuracy = correct / all.)

Invented and wrong values are the costly ones: a wrong "has a lift" lets a
listing through a hard limit, while a miss only fails closed (D8). So both
are reported on their own, not just folded into accuracy.

Fields are split the way the spec's targets are: those the page's table
states (the label's "prefilled" list, target 98%) and those only the text
states (target 85%).

Public results hold totals only. Per-listing detail stays in data/private/.

Run: uv run python -m evals.harness.extraction_eval PREDICTIONS.jsonl [KEY_VERSION] [NAME]
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from evals.harness import answer_key
from evals.harness.labels import LABEL_FIELDS, ExtractionLabel, comparable

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "evals" / "results"
PRIVATE = ROOT / "data" / "private" / "evals"
TARGETS = {"structured": 0.98, "free_text": 0.85}
OUTCOMES = ("correct", "wrong", "invented", "missed")


def _same(name: str, a, b) -> bool:
    a, b = comparable(name, a), comparable(name, b)
    if isinstance(a, float) or isinstance(b, float):
        return a is not None and b is not None and abs(a - b) < 0.01
    return a == b


def outcome(name: str, truth, guess) -> str:
    if _same(name, truth, guess):
        return "correct"
    blank = lambda v: comparable(name, v) in (None, [])  # noqa: E731
    if blank(truth):
        return "invented"
    if blank(guess):
        return "missed"
    return "wrong"


@dataclass
class Score:
    per_field: dict[str, dict[str, int]] = field(default_factory=dict)
    groups: dict[str, dict[str, int]] = field(default_factory=lambda: {g: dict.fromkeys(OUTCOMES, 0) for g in TARGETS})
    listings: int = 0
    missing_predictions: list[str] = field(default_factory=list)
    detail: list[dict] = field(default_factory=list)

    def accuracy(self, counts: dict[str, int]) -> float:
        total = sum(counts.values())
        return counts["correct"] / total if total else 0.0


def score(key: list[ExtractionLabel], predictions: dict[str, dict]) -> Score:
    result = Score(per_field={name: dict.fromkeys(OUTCOMES, 0) for name in LABEL_FIELDS})
    for label in key:
        guess = predictions.get(label.listing_id)
        if guess is None:
            result.missing_predictions.append(label.listing_id)
            guess = {}
        result.listings += 1
        for name in LABEL_FIELDS:
            truth, value = getattr(label.fields, name), guess.get(name)
            kind = outcome(name, truth, value)
            result.per_field[name][kind] += 1
            group = "structured" if name in label.prefilled else "free_text"
            result.groups[group][kind] += 1
            if kind != "correct":
                result.detail.append({"listing_id": label.listing_id, "field": name, "outcome": kind,
                                      "key": truth, "prediction": value})
    return result


def report(result: Score, name: str, manifest: dict) -> str:
    lines = [f"Extraction eval: {name}, answer key v{manifest['version']} ({result.listings} listings)"]
    for group, target in TARGETS.items():
        counts = result.groups[group]
        lines.append(f"  {group.replace('_', ' '):<11} {result.accuracy(counts):6.1%}  (target {target:.0%})  "
                     f"wrong {counts['wrong']}, invented {counts['invented']}, missed {counts['missed']}")
    lines.append("")
    lines.append(f"  {'field':<16}{'accuracy':>9}{'wrong':>7}{'invented':>10}{'missed':>8}")
    for field_name, counts in sorted(result.per_field.items(), key=lambda kv: result.accuracy(kv[1])):
        lines.append(f"  {field_name:<16}{result.accuracy(counts):9.0%}{counts['wrong']:7}{counts['invented']:10}{counts['missed']:8}")
    if result.missing_predictions:
        lines.append(f"\n  No prediction for {len(result.missing_predictions)} listings (scored as all unknown).")
    return "\n".join(lines)


def run(predictions_path: Path, version: int = 1, name: str = "code_baseline", write: bool = True) -> Score:
    key, manifest = answer_key.load(version)
    predictions = {}
    for line in predictions_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            predictions[row["listing_id"]] = row["fields"]
    result = score(key, predictions)
    print(report(result, name, manifest))
    if write:
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        public = {
            "eval": "extraction", "name": name, "ran_at": stamp, "listings": result.listings,
            "answer_key": {"version": manifest["version"], "sha256": manifest["sha256"]},
            "targets": TARGETS,
            "groups": {g: dict(c, accuracy=round(result.accuracy(c), 4)) for g, c in result.groups.items()},
            "per_field": {f: dict(c, accuracy=round(result.accuracy(c), 4)) for f, c in result.per_field.items()},
            "data": "real listings, private; totals only",
        }
        RESULTS.mkdir(parents=True, exist_ok=True)
        (RESULTS / f"v0.2-extraction-{name}.json").write_text(json.dumps(public, indent=2), encoding="utf-8")
        PRIVATE.mkdir(parents=True, exist_ok=True)
        (PRIVATE / f"detail-{name}-v{version}.json").write_text(json.dumps(result.detail, ensure_ascii=False, indent=1), encoding="utf-8")
    return result


if __name__ == "__main__":
    args = sys.argv[1:]
    run(Path(args[0]), int(args[1]) if len(args) > 1 else 1, args[2] if len(args) > 2 else "code_baseline")
