"""Run the eval suite and print a results table.

Today the suite has one eval, search safety: does search_listings ever return
a listing that breaks a hard limit? Target: zero breaks, every time.

The harness talks to the real MCP server through an MCP client, the same way
the Claude desktop app does, so it tests what users actually get, not an
internal function. Checks use the independent checker in checks.py.

Run:  uv run python -m evals.harness.run [--version v0.1]
Exit code is 1 if any hard limit is broken, so CI can fail the build.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from mcp import Client

from evals.harness.checks import breaks
from mcp_server.server import adapter, mcp

ROOT = Path(__file__).resolve().parent.parent
DATASET = ROOT / "datasets" / "search_safety.jsonl"
RESULTS = ROOT / "results"
TOP_K = 20


def _git_commit() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    except Exception:  # noqa: BLE001 - outside a git checkout is fine
        return None


async def _search(client: Client, criteria: dict, limit: int) -> dict:
    result = await client.call_tool("search_listings", {"criteria": criteria, "limit": limit})
    if result.is_error:
        raise RuntimeError(result.content[0].text if result.content else "tool error")
    return json.loads(result.content[0].text)


async def run_search_safety() -> dict:
    cases = [json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows = []
    async with Client(mcp) as client:
        for case in cases:
            response = await _search(client, case["criteria"], TOP_K)
            returned = response["results"]
            ids = [r["listing_id"] for r in returned]
            expected = set(case["expected_ids"])
            broken = {r["listing_id"]: breaks(r, case.get("effective_criteria", case["criteria"])) for r in returned}
            broken = {k: v for k, v in broken.items() if v}
            denominator = min(TOP_K, len(expected))
            recall = (len(set(ids) & expected) / denominator) if denominator else (1.0 if not ids else 0.0)
            top10 = ids[:10]
            precision = (sum(i in expected for i in top10) / len(top10)) if top10 else None
            rows.append({
                "id": case["id"],
                "description": case["description"],
                "expected": len(expected),
                "total_matches": response["total_matches"],
                "returned": len(ids),
                "breaks": len(broken),
                "break_details": broken,
                "recall_at_20": round(recall, 3),
                "precision_at_10": None if precision is None else round(precision, 3),
                "excluded_because_unknown": response.get("excluded_because_unknown", {}),
            })
    scored_precision = [r["precision_at_10"] for r in rows if r["precision_at_10"] is not None]
    return {
        "eval": "search_safety",
        "cases": len(rows),
        "total_breaks": sum(r["breaks"] for r in rows),
        "mean_recall_at_20": round(sum(r["recall_at_20"] for r in rows) / len(rows), 3),
        "mean_precision_at_10": round(sum(scored_precision) / len(scored_precision), 3) if scored_precision else None,
        "count_mismatches": sum(r["total_matches"] != r["expected"] for r in rows),
        "rows": rows,
    }


def print_table(report: dict) -> None:
    header = f"{'case':<6}{'expected':>9}{'matches':>9}{'returned':>9}{'breaks':>8}{'recall@20':>11}{'prec@10':>9}  description"
    print(header)
    print("-" * len(header))
    for r in report["rows"]:
        precision = "n/a" if r["precision_at_10"] is None else f"{r['precision_at_10']:.2f}"
        print(f"{r['id']:<6}{r['expected']:>9}{r['total_matches']:>9}{r['returned']:>9}{r['breaks']:>8}"
              f"{r['recall_at_20']:>11.2f}{precision:>9}  {r['description']}")
    print("-" * len(header))
    status = "PASS" if report["total_breaks"] == 0 else "FAIL"
    print(f"Search safety: {status}. Hard limit breaks: {report['total_breaks']} (target 0). "
          f"Mean recall@20: {report['mean_recall_at_20']:.2f}. Mean precision@10: {report['mean_precision_at_10']:.2f}. "
          f"Count mismatches: {report['count_mismatches']}.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Property Match Agent evals")
    parser.add_argument("--version", default="v0.1", help="label saved with the results")
    parser.add_argument("--no-save", action="store_true", help="print only, don't write a results file")
    args = parser.parse_args()

    report = asyncio.run(run_search_safety())
    report.update({
        "version": args.version,
        "commit": _git_commit(),
        "ran_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "data": "synthetic" if adapter().is_synthetic else "private snapshot",
    })
    print_table(report)

    if not args.no_save:
        RESULTS.mkdir(parents=True, exist_ok=True)
        out = RESULTS / f"{args.version}-search_safety.json"
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Saved {out.relative_to(ROOT.parent)}")
    return 0 if report["total_breaks"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
