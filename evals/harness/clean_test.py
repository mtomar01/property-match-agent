"""The clean test (D44, D45): the extraction system on listings nothing was tuned on.

The prompts and merge rules were shaped on the first 100 listings, so their
score is a development score. The clean test is a fresh batch from an area
the prompt has never seen, labelled blind (pre-filled only with what code
reads from the page). This module turns the hosted pages' saved labels into
label files, freezes them as the set's own answer key, then scores the code
baseline and Haiku + code against it, with the prompt and rules unchanged.

Run: uv run python -m evals.harness.clean_test pagrati            # pull files must already be saved
     uv run python -m evals.harness.clean_test pagrati --score    # pays for the model calls not yet cached
     uv run python -m evals.harness.clean_test pagrati --key 2    # saved predictions against key v2, free
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from evals.harness import answer_key, code_baseline, extraction_eval, model_extraction
from evals.harness.build_label_tool import ROOT
from evals.harness.labels import check

SETS = {"pagrati": ROOT / "data" / "private" / "pagrati"}


def label_files(folder: Path, round_no: int = 6) -> list[Path]:
    """One label file per labeller from the pulled store documents (pulled/<who>/.../items/*.json)."""
    out = []
    for who_dir in sorted((folder / "pulled").iterdir()):
        docs = [json.loads(f.read_text(encoding="utf-8")) for f in sorted(who_dir.rglob("*.json"))]
        rows = [d.get("data", d) for d in docs]
        path = answer_key.LABELS / f"round{round_no}_{who_dir.name}.jsonl"
        path.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows), encoding="utf-8")
        labels, problems = check(path)
        if problems:
            raise ValueError(f"{path.name}: {problems[:3]}")
        out.append(path)
    return out


def freeze(folder: Path, sources: list[Path]) -> Path:
    """The set's own answer key, v1, next to its data. Never overwritten."""
    return answer_key.freeze(1, sources, out_dir=folder)


def score(name: str) -> dict:
    folder = SETS[name]
    raw, snapshot, out = folder / "details_raw.jsonl", folder / "snapshot.jsonl", folder / "evals"
    out.mkdir(parents=True, exist_ok=True)
    baseline = out / "predictions_code_baseline.jsonl"
    code_baseline.run(raw, snapshot, baseline)
    results = {"code": extraction_eval.run(baseline, 1, "code_baseline", key_dir=folder, set_name=name)}
    results["haiku"] = model_extraction.run("claude-haiku-5-5", key_version=1, out_dir=out, raw_path=raw,
                                            snapshot_path=snapshot, key_dir=folder, set_name=name)
    return results


def rescore(name: str, key_version: int) -> dict:
    """Score the saved predictions against another version of the set's key. No model calls."""
    folder = SETS[name]
    return {run: extraction_eval.run(folder / "evals" / f"predictions_{run}.jsonl", key_version, run,
                                     key_dir=folder, set_name=name)
            for run in ("code_baseline", "haiku_v3-fill", "haiku_v3-conflict")}


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] not in SETS:
        print(__doc__)
        sys.exit(1)
    folder = SETS[args[0]]
    if not (folder / "answer_key_v1.jsonl").exists():
        files = label_files(folder)
        print(f"Froze {freeze(folder, files).relative_to(ROOT)} from {', '.join(f.name for f in files)}")
    if "--score" in args:
        score(args[0])
    if "--key" in args:
        rescore(args[0], int(args[args.index("--key") + 1]))
