"""Freeze the labels into a versioned answer key.

The labels live on the hosted pages, where they can still change. An eval
needs a fixed target, so this copies them as they stand into one file per
version, answer_key_v<N>.jsonl, with a manifest: a checksum, where each label
came from, who made it and under which rule version. Every eval run records
the key version and checksum it was scored against, so a score from today and
one from next month can be compared, or knowingly not (D32).

A version is never overwritten. Later rounds become v2, v3.

From v2 a listing can have several labels (the original, a cross-check, a
check round). They are combined field by field (D35): a value one labeller
found beats a blank another left, because the rounds showed blanks are mostly
misses; when two labels give different values, the newer one wins, because
it was made under the newer rules. The manifest records, per listing, every
label used and which fields were settled each way.

Run: uv run python -m evals.harness.answer_key freeze 1
     uv run python -m evals.harness.answer_key freeze 2   # combined, from every round
     uv run python -m evals.harness.answer_key freeze 3   # v2 plus crossed-out blanks filled by rule (D39)
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from evals.harness.labels import LABEL_FIELDS, ExtractionLabel, check, comparable

ROOT = Path(__file__).resolve().parents[2]
LABELS = ROOT / "data" / "private" / "labels"
# Batches labelled before the crossed-out rule (D29) changed.
PRE_D29 = ("hosted_batch1", "hosted_batch2")
# Every human label file, oldest first, for the combined keys (v2 on).
ROUNDS = ("hosted_batch1_gb", "hosted_batch2_mike", "hosted_batch3_gb", "hosted_batch4_mike", "hosted_batch5_gb",
          "agreement/relabel_mike", "agreement/relabel_gb", "round2_mike", "round2_gb", "round3_mike", "round3_gb")


def rules_of(name: str) -> str:
    if name.startswith(PRE_D29):
        return "before D29"
    if name.startswith("round6"):
        return "D41"  # the Pagrati clean test, labelled under every rule to date (D44)
    return "D31" if name.startswith(("round2", "round3")) else "D29"


def _blank(name: str, value) -> bool:
    return comparable(name, value) in (None, [])


def combine(labels: list[ExtractionLabel]) -> tuple[ExtractionLabel, dict]:
    """One label from several for the same listing, oldest first (see the module note)."""
    newest = labels[-1]
    fields, filled, newest_won = {}, [], []
    for name in LABEL_FIELDS:
        values = [getattr(label.fields, name) for label in labels]
        present = [v for v in values if not _blank(name, v)]
        if not present:
            fields[name] = values[-1]
            continue
        fields[name] = present[-1]
        if _blank(name, values[-1]):
            filled.append(name)
        elif len({json.dumps(comparable(name, v), sort_keys=True) for v in present}) > 1:
            newest_won.append(name)
    evidence: dict = {}
    for label in labels:
        evidence.update(label.evidence)
    combined = newest.model_copy(update={
        "fields": newest.fields.model_copy(update=fields),
        "labeller": "+".join(dict.fromkeys(label.labeller for label in labels)),
        "evidence": evidence,
        "notes": " | ".join(label.notes for label in labels if label.notes),
        "pii": any(label.pii for label in labels),
        "price_history": next((label.price_history for label in reversed(labels) if label.price_history), []),
    })
    return combined, {"filled_from_older": filled, "newest_won": newest_won}


def freeze_combined(version: int, names: tuple[str, ...] = ROUNDS, out_dir: Path = LABELS) -> Path:
    out = out_dir / f"answer_key_v{version}.jsonl"
    if out.exists():
        raise FileExistsError(f"{out.name} exists; versions are never overwritten")
    by_listing: dict[str, list[tuple[str, ExtractionLabel]]] = {}
    for name in names:
        path = out_dir / f"{name}.jsonl"
        labels, problems = check(path)
        if problems:
            raise ValueError(f"{path.name}: {problems[:3]}")
        for label in labels:
            by_listing.setdefault(label.listing_id, []).append((name, label))
    rows, origin = [], {}
    for listing_id, entries in sorted(by_listing.items()):
        label, how = combine([label for _, label in entries])
        newest_name, newest = entries[-1]
        origin[listing_id] = {
            "file": newest_name, "labeller": newest.labeller, "rules": rules_of(newest_name.split("/")[-1]),
            "labels": [{"file": n, "labeller": l.labeller, "rules": rules_of(n.split("/")[-1])} for n, l in entries],
            **how,
        }
        rows.append(label.model_dump(mode="json"))
    text = "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows)
    out.write_text(text, encoding="utf-8")
    manifest = {
        "version": version, "frozen_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(), "listings": len(rows),
        "sources": list(names), "combined": True, "origin": origin,
    }
    (out_dir / f"answer_key_v{version}.manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return out


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
                "rules": rules_of(path.name),
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


RULE_FILLED = {  # label field: (feature list, feature name, the "no" value)
    "lift": ("Εσωτερικό", "Ασανσέρ", False),
    "storage": ("Εσωτερικό", "Αποθήκη", False),
    "parking": ("Εξωτερικά χαρακτηριστικά", "Parking", "none"),
}
RULE_NOTE = "Crossed out in the feature list; filled by rule D29 (key v3, D39)"


def fill_crossed_out(label: ExtractionLabel, crossed: dict, description: str) -> tuple[ExtractionLabel, list[str]]:
    """Fill a blank lift, storage or parking with "no" where the page crosses it out (D39).

    Only when the label is blank, the feature is crossed out, and the
    description doesn't mention it: a mention in the text wins over a cross
    for parking and storage (D34, D35), and a lift the text mentions against a
    crossed-out one is a conflict, which stays unknown (D25).
    """
    from evals.harness.code_baseline import LIFT, PARKING, STORAGE

    mentions = {"lift": LIFT, "storage": STORAGE, "parking": PARKING}
    fields, evidence, filled = {}, dict(label.evidence), []
    for name, (section, feature, no) in RULE_FILLED.items():
        if getattr(label.fields, name) is not None or feature not in crossed.get(section, []):
            continue
        if mentions[name].search(description or ""):
            continue
        fields[name] = no
        evidence[name] = RULE_NOTE
        filled.append(name)
    if not filled:
        return label, []
    return label.model_copy(update={"fields": label.fields.model_copy(update=fields), "evidence": evidence}), filled


def freeze_rule_filled(version: int = 3, base: int = 2, out_dir: Path = LABELS) -> Path:
    """Key v3: key v2 with crossed-out blanks filled by rule, every fill recorded."""
    import json as _json

    from adapters import spitogatos_features as features
    from evals.harness.build_label_tool import RAW

    out = out_dir / f"answer_key_v{version}.jsonl"
    if out.exists():
        raise FileExistsError(f"{out.name} exists; versions are never overwritten")
    labels, base_manifest = load(base, out_dir)
    lists = features.load()
    descriptions = {f"spitogatos:{r['source_id']}": r["sections"].get("Περιγραφή", "")
                    for r in (_json.loads(line) for line in RAW.read_text(encoding="utf-8").splitlines() if line.strip())}
    rows, origin = [], {}
    for label in labels:
        row = lists.get(label.listing_id.split(":", 1)[1])
        filled_label, filled = fill_crossed_out(label, row["crossed"] if row else {}, descriptions.get(label.listing_id, ""))
        origin[label.listing_id] = dict(base_manifest["origin"][label.listing_id], filled_by_rule=filled)
        rows.append(filled_label.model_dump(mode="json"))
    text = "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows)
    out.write_text(text, encoding="utf-8")
    manifest = {
        "version": version, "frozen_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(), "listings": len(rows),
        "derived_from": {"version": base, "sha256": base_manifest["sha256"]},
        "rule": "D39: a blank lift, storage or parking is 'no' where the page crosses it out and the text doesn't mention it",
        "filled_by_rule": sum(len(o["filled_by_rule"]) for o in origin.values()),
        "sources": base_manifest.get("sources"), "combined": True, "origin": origin,
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
        version = int(sys.argv[2])
        path = freeze(version) if version == 1 else freeze_combined(version) if version == 2 else freeze_rule_filled(version, version - 1)
        print(f"Froze {path.relative_to(ROOT)}")
    else:
        print(__doc__)
