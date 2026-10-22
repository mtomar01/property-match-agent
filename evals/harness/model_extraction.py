"""Run the extraction prompt over the 100 collected listings and score it (D33).

This one costs money: each listing is one model call. It runs only with
Mike's approval, and every answer is cached in data/private/, so re-scoring
or changing the merge rule never pays twice. A call is repeated only when the
prompt, the schema, the model or the listing text changed.

For each run it scores two merge rules from the same answers (agent/extraction.py):
"fill" (code first, the description fills blanks) and "conflict" (D25: when
the description and the table disagree, the field is unknown).

A listing whose call fails keeps what code read from the page, so a failure
can't invent anything; failures are counted in the result.

Run:  uv run python -m evals.harness.model_extraction [MODEL] [PROMPT] [--crossed] [--limit N]
      --crossed adds the crossed-out lists from the revisit (D34) where there is one.
      --limit N calls N listings and prints them, without scoring (a dry run).
"""

from __future__ import annotations

import hashlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from adapters import spitogatos_features as features
from agent import llm
from agent.extraction import MAX_TOKENS, PROMPT_VERSION, ExtractionError, apply_walking_rule, call, merge, parse_reading, request
from evals.harness import extraction_eval
from evals.harness.build_label_tool import RAW, ROOT, SNAPSHOT
from evals.harness.code_baseline import from_page

PRIVATE = ROOT / "data" / "private" / "evals"
CACHE = PRIVATE / "model_cache"
RULES = ("fill", "conflict")
SHORT = {"claude-haiku-5-5": "haiku", "claude-sonnet-5-5": "sonnet"}


def load_inputs(raw_path: Path = RAW, snapshot_path: Path = SNAPSHOT, revisit: bool = False) -> tuple[list[dict], dict[str, dict]]:
    cards = {}
    for line in snapshot_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            card = json.loads(line)
            cards[card["listing_id"]] = card
    records = [json.loads(line) for line in raw_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if revisit:
        records = features.attach(records, features.load())
    return records, cards


def cache_key(body: dict) -> str:
    return hashlib.sha256(json.dumps(body, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def read_one(record: dict, model: str, version: str, client, cache_dir: Path) -> dict:
    """The model's reading of one description: from the cache, or from one paid call."""
    body = request(record["sections"].get("Περιγραφή", ""), record.get("seen"), model, version)
    key = cache_key(body)
    path = cache_dir / version / model / f"{record['source_id']}.json"
    if path.exists():
        saved = json.loads(path.read_text(encoding="utf-8"))
        if saved.get("key") == key and not saved.get("error"):
            return dict(saved, cached=True)
    entry = {"key": key, "listing_id": f"spitogatos:{record['source_id']}", "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    try:
        try:
            raw, response = call(client, body)
        except ExtractionError as err:
            if "max_tokens" not in str(err):
                raise
            # A long listing ran out of room: one retry with twice the room, same cache key.
            raw, response = call(client, dict(body, max_tokens=MAX_TOKENS * 2))
        entry.update(raw=raw, usage=llm.usage_dict(response.usage), stop_reason=response.stop_reason, error=None)
    except ExtractionError as err:
        entry.update(raw=None, usage={}, stop_reason=None, error=str(err))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entry, ensure_ascii=False, indent=1), encoding="utf-8")
    return dict(entry, cached=False)


def read_all(records: list[dict], model: str, version: str, client, cache_dir: Path = CACHE, workers: int = 4) -> list[dict]:
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(lambda r: read_one(r, model, version, client, cache_dir), records))


def run(model: str = "claude-haiku-5-5", version: str = PROMPT_VERSION, key_version: int = 1,
        limit: int | None = None, client=None, cache_dir: Path = CACHE, out_dir: Path = PRIVATE,
        write: bool = True, revisit: bool = False, raw_path: Path = RAW, snapshot_path: Path = SNAPSHOT,
        key_dir: Path | None = None, set_name: str | None = None) -> dict:
    records, cards = load_inputs(raw_path, snapshot_path, revisit=revisit)
    if limit:
        records = records[:limit]
    client = client or llm.client()
    readings = read_all(records, model, version, client, cache_dir)

    spent, total = {}, {}
    for entry in readings:
        llm.add_usage(total, entry.get("usage") or {})
        if not entry["cached"]:
            llm.add_usage(spent, entry.get("usage") or {})
    errors = [e["listing_id"] for e in readings if e.get("error")]
    summary = {
        "model": model, "prompt": version, "listings": len(readings), "failed_calls": len(errors),
        "usage": total, "cost_usd": round(llm.cost_usd(model, total), 4),
        "spent_this_run_usd": round(llm.cost_usd(model, spent), 4),
    }
    print(f"{model}, {version}: {len(readings)} listings, {len(errors)} failed, "
          f"cost of all answers ${summary['cost_usd']:.4f}, spent now ${summary['spent_this_run_usd']:.4f}")
    if limit or not write:
        for entry in readings:
            print(json.dumps({"listing_id": entry["listing_id"], "reading": entry.get("raw"), "error": entry.get("error")}, ensure_ascii=False))
        return summary

    name = f"{SHORT.get(model, model)}_{version.replace('extraction_', '')}" + ("+crossed" if revisit else "")
    results = {}
    for rule in RULES:
        conflicts: dict[str, int] = {}
        path = out_dir / f"predictions_{name}-{rule}.jsonl"
        with path.open("w", encoding="utf-8") as fh:
            for record, entry in zip(records, readings):
                listing_id = f"spitogatos:{record['source_id']}"
                code = from_page(record, cards.get(listing_id, {}))
                text = parse_reading(entry["raw"]) if entry.get("raw") else {}
                text = apply_walking_rule(text, record["sections"].get("Περιγραφή", "")) if text else text
                fields, blanked = merge(code, text, rule)
                for field in blanked:
                    conflicts[field] = conflicts.get(field, 0) + 1
                fh.write(json.dumps({"listing_id": listing_id, "fields": fields,
                                     "evidence": text.get("evidence", {}), "conflicts": blanked}, ensure_ascii=False) + "\n")
        extra = dict(summary, merge_rule=rule, conflicts_blanked=conflicts, crossed_out_lists=revisit)
        results[rule] = extraction_eval.run(path, key_version, f"{name}-{rule}", extra=extra, key_dir=key_dir, set_name=set_name)
        print()
    return dict(summary, results=results)


if __name__ == "__main__":
    args = sys.argv[1:]
    limit = int(args[args.index("--limit") + 1]) if "--limit" in args else None
    models = [a for a in args if a.startswith("claude-")]
    prompts = [a for a in args if a.startswith("extraction_")]
    key = int(args[args.index("--key") + 1]) if "--key" in args else 1
    run(models[0] if models else "claude-haiku-5-5", prompts[0] if prompts else PROMPT_VERSION, key_version=key,
        limit=limit, revisit="--crossed" in args)
