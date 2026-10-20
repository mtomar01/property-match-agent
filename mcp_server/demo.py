"""Try the MCP server from the command line, without the Claude desktop app.

It starts the real property_tools server over stdio, exactly as the desktop app
does, calls search_listings and prints the results as a table.

    uv run python -m mcp_server.demo
    uv run python -m mcp_server.demo --area Peristeri --max-price 250000 --min-bedrooms 3 --no-basements
    PM_SNAPSHOT=data/private/snapshot.jsonl uv run python -m mcp_server.demo   # your private listings
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import Client, StdioServerParameters

REPO = Path(__file__).resolve().parent.parent


def build_criteria(args: argparse.Namespace) -> dict:
    limits: dict = {}
    if args.max_price:
        limits["max_price_eur"] = args.max_price
    if args.min_size:
        limits["min_size_m2"] = args.min_size
    if args.min_bedrooms:
        limits["min_bedrooms"] = args.min_bedrooms
    if args.no_basements:
        limits["exclude_floors"] = ["basement", "semi_basement"]
    return {"intent": args.intent, "areas": args.area or [], "hard_limits": limits}


async def run(criteria: dict, limit: int) -> dict:
    server = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcp_server.server"],
        cwd=str(REPO),
        env={**os.environ},
    )
    async with Client(server) as client:
        result = await client.call_tool("search_listings", {"criteria": criteria, "limit": limit})
        return json.loads(result.content[0].text)


def main() -> None:
    parser = argparse.ArgumentParser(description="Search listings through the MCP server")
    parser.add_argument("--area", action="append", help="Egaleo, Peristeri or Chaidari (repeat for more). Default: Egaleo")
    parser.add_argument("--intent", default="buy", choices=["buy", "rent", "invest"])
    parser.add_argument("--max-price", type=int, default=200000)
    parser.add_argument("--min-size", type=float)
    parser.add_argument("--min-bedrooms", type=int, default=2)
    parser.add_argument("--no-basements", action="store_true", help="exclude basements and semi-basements")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    if not args.area:
        args.area = ["Egaleo"]

    criteria = build_criteria(args)
    response = asyncio.run(run(criteria, args.limit))

    print(f"Data: {response['data']}   Criteria: {json.dumps(response['criteria_applied'], ensure_ascii=False)}")
    print(f"{response['total_matches']} matches, showing {response['returned']}\n")
    print(f"{'listing':<24}{'price €':>10}{'m²':>6}{'€/m²':>7}{'beds':>5}  {'floor':<14}{'area':<11}sub-area")
    for r in response["results"]:
        print(f"{r['listing_id']:<24}{r['price_eur']:>10,}{r['size_m2']:>6.0f}{r['price_per_m2'] or 0:>7,}"
              f"{r['bedrooms'] if r['bedrooms'] is not None else '?':>5}  {str(r['floor']):<14}{r['area']:<11}{r['sub_area'] or ''}")
    unknown = response.get("excluded_because_unknown") or {}
    if unknown:
        print(f"\nLeft out because a value is unknown: {unknown}")


if __name__ == "__main__":
    main()
