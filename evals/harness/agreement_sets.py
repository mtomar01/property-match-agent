"""Pick the listings each labeller relabels for the agreement check, and build their pages.

Every labeller gets a random sample of listings that someone else labelled,
on a hosted page like the others (links and code-read values, no listing text,
no one's labels). Comparing their answers with the originals measures how
reliable the answer key is (D30). The sample is seeded, so it can be rebuilt
and checked; the chosen ids are saved next to the pages.

Run: uv run python -m evals.harness.agreement_sets [SIZE] [SEED]
     uv run python -m evals.harness.agreement_sets round2   # the listings code read worst
     uv run python -m evals.harness.agreement_sets round3   # 10 each from the revisited 50 (D34)
     uv run python -m evals.harness.agreement_sets round4   # verify: 5 each the old pages missed parking or a balcony (D36)
     uv run python -m evals.harness.agreement_sets round5   # verify: 10 with lift, parking and storage all unknown (D37)
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
    return {who: build_hosted_selection(ids, f"{display(who)}'s Cross-Check 2", OUT / f"cross-check-2-{who}.html",
                                         round_no=2)
            for who, ids in chosen.items()}


def choose_round3(origin: dict, errors: dict[str, int], pool: list[str], size: int = 10) -> dict:
    """Each labeller gets the listings where the pipeline and the other's label disagree most.

    When the other labeller has too few listings in the pool, the rest are the
    labeller's own (a self-check: same person, a few days later), never one
    already given to the other labeller.
    """
    ranked = sorted(pool, key=lambda i: (-errors.get(i, 0), i))
    labellers = sorted({origin[i]["labeller"] for i in pool})
    chosen: dict[str, list[str]] = {}
    for labeller in labellers:
        chosen[labeller] = [i for i in ranked if origin[i]["labeller"] != labeller][:size]
    self_check: dict[str, list[str]] = {}
    for labeller in labellers:
        given = {i for other, ids in chosen.items() if other != labeller for i in ids}
        missing = size - len(chosen[labeller])
        own = [i for i in ranked if origin[i]["labeller"] == labeller and i not in given][:max(missing, 0)]
        chosen[labeller] += own
        self_check[labeller] = own
    return {"relabel": chosen, "self_check": self_check}


def build_round3(size: int = 10, key_version: int = 1, run_name: str = "haiku_v2+crossed-fill") -> dict[str, Path]:
    from evals.harness import answer_key
    from evals.harness.extraction_eval import PRIVATE, load_predictions, score

    key, manifest = answer_key.load(key_version)
    sample = set(json.loads((PRIVATE.parent / "revisit" / "sample.json").read_text(encoding="utf-8"))["listing_ids"])
    round2 = json.loads((OUT / "sets_round2.json").read_text(encoding="utf-8"))["relabel"]
    pool = sorted(sample - {i for ids in round2.values() for i in ids})
    result = score(key, load_predictions(PRIVATE / f"predictions_{run_name}.jsonl"), set(pool))
    errors: dict[str, int] = defaultdict(int)
    for row in result.detail:
        errors[row["listing_id"]] += 1
    sets = choose_round3(manifest["origin"], errors, pool, size)
    (OUT / "sets_round3.json").write_text(json.dumps(dict(sets, size=size, ranked_by=f"{run_name} errors on key v{key_version}",
                                                          pool="the revisited 50, less round 2"), indent=2), encoding="utf-8")
    return {who: build_hosted_selection(ids, f"{display(who)}'s Check 3", OUT / f"check-3-{who}.html", round_no=3, revisit=True)
            for who, ids in sets["relabel"].items()}


def missed_before_d35(record: dict, label) -> list[str]:
    """Whether the pages before D35 hid parking or a balcony that the key says is there.

    Before D35 the pages never pre-filled parking, and a balcony only from a
    ticked Βεράντα, Ιδιωτικός Κήπος or a balcony area.
    """
    from evals.harness.labels import comparable

    exterior = (record["sections"].get("Εξωτερικά χαρακτηριστικά") or "").split("\n")
    shown = any(t in exterior for t in ("Βεράντα", "Ιδιωτικός Κήπος")) or any(t.startswith("(") and "τ.μ." in t for t in exterior)
    missed = []
    if comparable("parking", label.fields.parking) == "yes":
        missed.append("parking")
    if label.fields.balcony is True and not shown:
        missed.append("balcony")
    return missed


def choose_round4(pool: list[str], labellers: list[str], labelled: dict[str, set[str]], size: int = 5,
                  seed: int = 2026) -> dict[str, list[str]]:
    """A seeded random `size` for each labeller, none shared between them.

    Listings they never labelled come first; if there are too few, the rest
    are listings they labelled before (fine for checking the system's answer).
    """
    rng = random.Random(seed)
    chosen: dict[str, list[str]] = {}
    taken: set[str] = set()
    for labeller in labellers:
        fresh = sorted(i for i in pool if labeller not in labelled[i] and i not in taken)
        picks = rng.sample(fresh, min(size, len(fresh)))
        seen = sorted(i for i in pool if labeller in labelled[i] and i not in taken)
        picks += rng.sample(seen, min(size - len(picks), len(seen)))
        chosen[labeller] = sorted(picks)
        taken.update(picks)
    return chosen


def build_round4(size: int = 5, key_version: int = 2, run_name: str = "haiku_v2+crossed-fill") -> dict[str, Path]:
    """Verify pages: listings where the old pages missed parking or a balcony, with the system's new answer (D36)."""
    from evals.harness import answer_key
    from evals.harness.build_label_tool import RAW
    from evals.harness.extraction_eval import PRIVATE, load_predictions

    key, manifest = answer_key.load(key_version)
    records = {f"spitogatos:{json.loads(line)['source_id']}": json.loads(line)
               for line in RAW.read_text(encoding="utf-8").splitlines() if line.strip()}
    pool = {label.listing_id: missed for label in key if (missed := missed_before_d35(records[label.listing_id], label))}
    labelled = {i: {entry["labeller"] for entry in manifest["origin"][i]["labels"]} for i in pool}
    labellers = sorted({entry["labeller"] for o in manifest["origin"].values() for entry in o["labels"]})
    chosen = choose_round4(sorted(pool), labellers, labelled, size)
    system = load_predictions(PRIVATE / f"predictions_{run_name}.jsonl")
    (OUT / "sets_round4.json").write_text(json.dumps({
        "size": size, "seed": 2026, "pool": len(pool), "why": {i: pool[i] for ids in chosen.values() for i in ids},
        "relabel": chosen, "system": run_name, "key": key_version}, indent=2), encoding="utf-8")
    return {who: build_hosted_selection(ids, f"{display(who)}'s Check 4", OUT / f"check-4-{who}.html", round_no=4,
                                        revisit=True, system=system)
            for who, ids in chosen.items()}


def build_round5(size: int = 10, run_name: str = "haiku_v2+crossed-fill", seed: int = 2026) -> dict[str, Path]:
    """One verify page for both labellers: listings where the system says unknown for lift, parking and storage (D37).

    Those three are the features a crossed-out list answers, so a listing with
    all three unknown is where reading the list would help most. Picked at
    random, with a fixed seed, from listings not on the round 4 pages.
    """
    from evals.harness.extraction_eval import PRIVATE, load_predictions

    system = load_predictions(PRIVATE / f"predictions_{run_name}.jsonl")
    round4 = json.loads((OUT / "sets_round4.json").read_text(encoding="utf-8"))["relabel"]
    skip = {i for ids in round4.values() for i in ids}
    pool = sorted(i for i, f in system.items()
                  if i not in skip and all(f.get(name) is None for name in ("lift", "parking", "storage")))
    chosen = sorted(random.Random(seed).sample(pool, min(size, len(pool))))
    (OUT / "sets_round5.json").write_text(json.dumps({"size": size, "seed": seed, "pool": len(pool), "listings": chosen,
                                                      "system": run_name}, indent=2), encoding="utf-8")
    return {"both": build_hosted_selection(chosen, "Crossed-Out Check", OUT / "check-5.html", round_no=5,
                                           revisit=True, system=system)}


if __name__ == "__main__":
    if sys.argv[1:2] == ["round5"]:
        pages = build_round5()
    elif sys.argv[1:2] == ["round4"]:
        pages = build_round4()
    elif sys.argv[1:2] == ["round3"]:
        pages = build_round3()
    elif sys.argv[1:2] == ["round2"]:
        pages = build_round2()
    else:
        pages = build(*[int(a) for a in sys.argv[1:3]])
    for who, path in pages.items():
        print(f"{who}: {path.relative_to(ROOT)}")
