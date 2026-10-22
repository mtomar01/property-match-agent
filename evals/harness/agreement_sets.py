"""Pick the listings each labeller relabels for the agreement check, and build their pages.

Every labeller gets a random sample of listings that someone else labelled,
on a hosted page like the others (links and code-read values, no listing text,
no one's labels). Comparing their answers with the originals measures how
reliable the answer key is (D30). The sample is seeded, so it can be rebuilt
and checked; the chosen ids are saved next to the pages.

Run: uv run python -m evals.harness.agreement_sets [SIZE] [SEED]
     uv run python -m evals.harness.agreement_sets round2   # the listings code read worst
"""

from __future__ import annotations

import json
import random
import sys
from collections import defaultdict
from pathlib import Path

from evals.harness.build_label_tool import ROOT, build_hosted_selection
from evals.harness.labels import check

LABELS = ROOT / "data" / "private" / "labels"
OUT = LABELS / "agreement"


def labelled_by(paths: list[Path]) -> dict[str, list[str]]:
    """Listing ids per labeller, from validated label files."""
    by_labeller: dict[str, set[str]] = defaultdict(set)
    for path in paths:
        labels, problems = check(path)
        if problems:
            raise ValueError(f"{path.name} has problems: {problems[:3]}")
        for label in labels:
            by_labeller[label.labeller].add(label.listing_id)
    return {labeller: sorted(ids) for labeller, ids in by_labeller.items()}


def choose(by_labeller: dict[str, list[str]], size: int, seed: int) -> dict[str, list[str]]:
    """For each labeller, `size` random listings labelled by someone else."""
    rng = random.Random(seed)
    chosen = {}
    for labeller in sorted(by_labeller):
        others = sorted({i for other, ids in by_labeller.items() if other != labeller for i in ids})
        chosen[labeller] = rng.sample(others, min(size, len(others)))
    return chosen


def display(handle: str) -> str:
    return handle.upper() if len(handle) <= 3 else handle.capitalize()


def build(size: int = 20, seed: int = 2026) -> dict[str, Path]:
    by_labeller = labelled_by(sorted(LABELS.glob("hosted_batch*.jsonl")))
    chosen = choose(by_labeller, size, seed)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "sets.json").write_text(json.dumps({"size": size, "seed": seed, "relabel": chosen}, indent=2), encoding="utf-8")
    pages = {}
    for labeller, ids in chosen.items():
        pages[labeller] = build_hosted_selection(ids, f"{display(labeller)}'s Agreement Set", OUT / f"agreement-{labeller}.html")
    return pages


def choose_hardest(origin: dict[str, dict], errors: dict[str, int], size: int) -> dict[str, list[str]]:
    """For each labeller, the `size` listings someone else labelled where code's reading erred most.

    `origin` maps listing id to its answer-key origin (who labelled it), and
    `errors` counts the fields the code-only baseline got wrong on each. Ties
    break on listing id, so the choice is repeatable. Round 2 of the cross-check
    (D32) aims at the listings that are hardest to read, by your choice.
    """
    labellers = sorted({o["labeller"] for o in origin.values()})
    chosen = {}
    for labeller in labellers:
        others = [i for i, o in origin.items() if o["labeller"] != labeller]
        chosen[labeller] = sorted(others, key=lambda i: (-errors.get(i, 0), i))[:size]
    return chosen


def build_round2(size: int = 20, key_version: int = 1, detail_name: str = "code_baseline") -> dict[str, Path]:
    origin = json.loads((LABELS / f"answer_key_v{key_version}.manifest.json").read_text(encoding="utf-8"))["origin"]
    detail = json.loads((ROOT / "data" / "private" / "evals" / f"detail-{detail_name}-v{key_version}.json").read_text(encoding="utf-8"))
    errors: dict[str, int] = defaultdict(int)
    for row in detail:
        errors[row["listing_id"]] += 1
    chosen = choose_hardest(origin, errors, size)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "sets_round2.json").write_text(json.dumps({"size": size, "ranked_by": f"{detail_name} errors on key v{key_version}",
                                                      "relabel": chosen}, indent=2), encoding="utf-8")
    return {who: build_hosted_selection(ids, f"{display(who)}'s Cross-Check 2", OUT / f"cross-check-2-{who}.html")
            for who, ids in chosen.items()}


if __name__ == "__main__":
    if sys.argv[1:2] == ["round2"]:
        pages = build_round2()
    else:
        pages = build(*[int(a) for a in sys.argv[1:3]])
    for who, path in pages.items():
        print(f"{who}: {path.relative_to(ROOT)}")
