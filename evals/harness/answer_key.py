"""Freeze the labels into a versioned answer key.

The labels live on the hosted pages, where they can still change. An eval
needs a fixed target, so this copies them as they stand into one file per
version, answer_key_v<N>.jsonl, with a manifest: a checksum, where each label
came from, who made it and under which rule version. Every eval run records
the key version and checksum it was scored against, so a score from today and
one from next month can be compared, or knowingly not (D32).

A version is never overwritten. Later rounds become v2, v3.

Run: uv run python -m evals.harness.answer_key freeze 1
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from evals.harness.labels import ExtractionLabel, check

ROOT = Path(__file__).resolve().parents[2]
LABELS = ROOT / "data" / "private" / "labels"
# Batches labelled before the crossed-out rule (D29) changed.
PRE_D29 = ("hosted_batch1", "hosted_batch2")


def key_path(version: int) -> Path:
    return LABELS / f"answer_key_v{version}.jsonl"


def freeze(version: int, sources: list[Path] | None = None, out_dir: Path = LABELS) -> Path:
    out = out_dir / f"answer_key_v{version}.jsonl"
    if out.exists():
        raise FileExistsError(f"{out.name} exists; versions are never overwritten")
    sources = sources or sorted(LABELS.glob("hosted_batch*.jsonl"))
    rows, origin = [], {}
    for path in sources:
        labels, problems = check(path)
        if problems:
            raise ValueError(f"{path.name}: {problems[:3]}")
        for label in labels:
            if label.listing_id in origin:
                raise ValueError(f"{label.listing_id} appears in {origin[label.listing_id]['file']} and {path.name}")
            origin[label.listing_id] = {
                "file": path.name, "labeller": label.labeller,
                "rules": "before D29" if path.name.startswith(PRE_D29) else "D29",
            }
            rows.append(label.model_dump(mode="json"))
    rows.sort(key=lambda r: r["listing_id"])
    text = "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows)
    out_dir.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    manifest = {
        "version": version,
        "frozen_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "listings": len(rows),
        "sources": [p.name for p in sources],
        "origin": origin,
    }
    (out_dir / f"answer_key_v{version}.manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return out


def load(version: int, directory: Path = LABELS) -> tuple[list[ExtractionLabel], dict]:
    path = directory / f"answer_key_v{version}.jsonl"
    manifest = json.loads((directory / f"answer_key_v{version}.manifest.json").read_text(encoding="utf-8"))
    if hashlib.sha256(path.read_bytes()).hexdigest() != manifest["sha256"]:
        raise ValueError(f"{path.name} changed since it was frozen")
    labels, problems = check(path)
    if problems:
        raise ValueError(problems[:3])
    return labels, manifest


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "freeze":
        path = freeze(int(sys.argv[2]))
        print(f"Froze {path.relative_to(ROOT)}")
    else:
        print(__doc__)
