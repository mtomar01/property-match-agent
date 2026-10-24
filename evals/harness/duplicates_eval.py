"""The duplicates eval: does the finder merge only real duplicates, and find most of them? (spec sections 11 and 12, D78)

Two sets:

- **synthetic** (default): the 60 made-up listings and their 12 known duplicate groups
  (`data/synthetic/duplicates_truth.json`). The generator made the copies, so this is a development check,
  run twice: with photo hashes, and without them, since the real listings carry none yet.
- **labelled** (`--labels`): pairs from the frozen snapshot that you and GB marked "same home", "different
  homes" or "can't tell" on the labelling page (`build_duplicate_labels`). This is the spec's set: 60 pairs,
  targets 0.95 precision and 0.85 recall. With two labellers, a pair counts only where they agree; their
  agreement is reported too.

Precision: of the pairs the finder merged, the share that are really one home. Recall: of the real duplicate
pairs, the share it merged. A false merge hides a real option, so precision matters more (spec section 11).

    uv run python -m evals.harness.duplicates_eval
    uv run python -m evals.harness.duplicates_eval --labels mike.jsonl gb.jsonl [--snapshot PATH]
"""

from __future__ import annotations

import itertools
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from adapters.snapshot import SnapshotAdapter
from dedupe import finder

ROOT = Path(__file__).resolve().parents[2]
TRUTH = ROOT / "data" / "synthetic" / "duplicates_truth.json"
SNAPSHOT = ROOT / "data" / "private" / "snapshot.jsonl"
RESULTS = ROOT / "evals" / "results"
TARGET_PRECISION, TARGET_RECALL = 0.95, 0.85


def _pairs_of(groups) -> set[frozenset]:
    return {frozenset(p) for g in groups for p in itertools.combinations(sorted(g), 2)}


def _scores(merged: set[frozenset], truth: set[frozenset]) -> dict:
    hit = len(merged & truth)
    return {"merged_pairs": len(merged), "true_pairs": len(truth), "correct": hit,
            "precision": round(hit / len(merged), 3) if merged else None,
            "recall": round(hit / len(truth), 3) if truth else None,
            "false_merges": sorted(sorted(p) for p in merged - truth), "missed": sorted(sorted(p) for p in truth - merged)}


def synthetic() -> dict:
    listings = SnapshotAdapter().listings()
    truth = _pairs_of(c["listing_ids"] for c in json.loads(TRUTH.read_text(encoding="utf-8")))
    out = {}
    for name, photos in (("with_photos", True), ("without_photos", False)):
        merged = _pairs_of(c.listing_ids for c in finder.clusters(listings, use_photos=photos))
        out[name] = _scores(merged, truth)
    return out


def load_labels(paths: list[Path]) -> tuple[dict[frozenset, str], dict]:
    """The agreed label per pair. Two labellers who disagree, or a "can't tell", leave the pair out."""
    by_labeller = []
    for path in paths:
        rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
        by_labeller.append({frozenset((r["a"], r["b"])): r["label"] for r in rows if r.get("label")})
    keys = set().union(*by_labeller)
    agreed, both, same_answer = {}, 0, 0
    for key in keys:
        answers = [labels[key] for labels in by_labeller if key in labels]
        if len(answers) > 1:
            both += 1
            same_answer += len(set(answers)) == 1
        if len(set(answers)) == 1 and answers[0] in ("same", "different"):
            agreed[key] = answers[0]
    return agreed, {"labellers": len(paths), "pairs_labelled": len(keys), "labelled_by_both": both,
                    "agreement": round(same_answer / both, 3) if both else None, "pairs_scored": len(agreed)}


def labelled(paths: list[Path], snapshot: Path) -> dict:
    listings = SnapshotAdapter(snapshot).listings()
    verdicts = {frozenset((p.a, p.b)): p.verdict for p in finder.pairs(listings)}
    merged_groups = _pairs_of(c.listing_ids for c in finder.clusters(listings))
    agreed, info = load_labels(paths)
    truth = {k for k, v in agreed.items() if v == "same"}
    merged = {k for k in agreed if k in merged_groups}
    borderline = [k for k in agreed if verdicts.get(k) == "borderline"]
    return {**info, **_scores(merged, truth),
            "borderline": {"pairs": len(borderline), "labelled_same": sum(1 for k in borderline if agreed[k] == "same")}}


def report(out: dict) -> str:
    lines = []
    for name, s in out.items():
        if not isinstance(s, dict) or "precision" not in s:
            continue
        lines.append(f"  {name:<16} precision {s['precision']}, recall {s['recall']} ({s['correct']} of {s['merged_pairs']} merged pairs right, "
                     f"{s['true_pairs']} real pairs)" + (f"; missed {s['missed']}" if s["missed"] else "")
                     + (f"; false merges {s['false_merges']}" if s["false_merges"] else ""))
    return "\n".join(lines)


if __name__ == "__main__":
    args = sys.argv[1:]
    RESULTS.mkdir(parents=True, exist_ok=True)
    if "--labels" in args:
        start = args.index("--labels") + 1
        files = [Path(a) for a in itertools.takewhile(lambda a: not a.startswith("--"), args[start:])]
        snapshot = Path(args[args.index("--snapshot") + 1]) if "--snapshot" in args else SNAPSHOT
        out = labelled(files, snapshot)
        passed = (out["precision"] or 0) >= TARGET_PRECISION and (out["recall"] or 0) >= TARGET_RECALL
        print(f"Duplicates eval, labelled pairs ({out['pairs_scored']} scored; agreement {out['agreement']}):\n"
              + report({"labelled": out}) + f"\n  borderline {out['borderline']}\n  {'PASS' if passed else 'FAIL'} "
              f"(targets precision {TARGET_PRECISION}, recall {TARGET_RECALL})")
        public = {k: v for k, v in out.items() if k not in ("false_merges", "missed")}  # listing ids stay private
        (RESULTS / "v3-duplicates-labelled.json").write_text(json.dumps({
            "eval": "duplicates", "ran_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "data": f"labelled pairs from {snapshot.name}: counts only", **public, "passed": passed}, ensure_ascii=False, indent=1), encoding="utf-8")
        sys.exit(0 if passed else 1)
    out = synthetic()
    print("Duplicates eval, synthetic listings (12 known groups; a development check, the generator made the copies):\n" + report(out))
    (RESULTS / "v3-duplicates-synthetic.json").write_text(json.dumps({
        "eval": "duplicates", "ran_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "data": "synthetic listings", **out}, ensure_ascii=False, indent=1), encoding="utf-8")
