"""Before and after the crossed-out lists, on the 50 revisited listings only (D34).

Scores prediction files that already exist, so it makes no model calls. The
same 50 listings are scored with and without the crossed-out lists, so the
difference is the lists' effect and nothing else.

Run: uv run python -m evals.harness.revisit_eval
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from evals.harness import answer_key
from evals.harness.extraction_eval import PRIVATE, RESULTS, load_predictions, score

SAMPLE = PRIVATE.parent / "revisit" / "sample.json"
RUNS = [
    ("code only", "predictions_code_baseline.jsonl"),
    ("code only, crossed-out lists", "predictions_code_baseline+crossed.jsonl"),
    ("Haiku v2, fill", "predictions_haiku_v2-fill.jsonl"),
    ("Haiku v2, fill, crossed-out lists", "predictions_haiku_v2+crossed-fill.jsonl"),
    ("Haiku v2, conflict", "predictions_haiku_v2-conflict.jsonl"),
    ("Haiku v2, conflict, crossed-out lists", "predictions_haiku_v2+crossed-conflict.jsonl"),
]


def run(key_version: int = 1, write: bool = True) -> dict:
    key, manifest = answer_key.load(key_version)
    only = set(json.loads(SAMPLE.read_text(encoding="utf-8"))["listing_ids"])
    table = {}
    for label, filename in RUNS:
        result = score(key, load_predictions(PRIVATE / filename), only)
        table[label] = {group: dict(counts, accuracy=round(result.accuracy(counts), 4)) for group, counts in result.groups.items()}
        free, structured = table[label]["free_text"], table[label]["structured"]
        print(f"{label:<40} table {structured['accuracy']:6.1%}   text {free['accuracy']:6.1%}   "
              f"invented {free['invented']:3}  missed {free['missed']:3}  wrong {free['wrong']:3}")
    if write:
        out = {"eval": "extraction, revisit subset", "listings": len(only), "ran_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "answer_key": {"version": manifest["version"], "sha256": manifest["sha256"]}, "runs": table,
               "data": "real listings, private; totals only"}
        (RESULTS / "v0.2-extraction-revisit50.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    return table


if __name__ == "__main__":
    run()
