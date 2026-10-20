"""The MCP server, called through a real MCP client (in-process)."""

import asyncio
import json

import pytest
from mcp import Client

from adapters.snapshot import SnapshotAdapter, SnapshotError
from mcp_server.server import mcp


def call(tool: str, args: dict) -> dict:
    async def go():
        async with Client(mcp) as client:
            result = await client.call_tool(tool, args)
            assert not result.is_error, result.content
            return json.loads(result.content[0].text)

    return asyncio.run(go())


def test_lists_the_two_tools():
    async def go():
        async with Client(mcp) as client:
            return sorted(t.name for t in (await client.list_tools()).tools)

    assert asyncio.run(go()) == ["get_listing", "search_listings"]


def test_spec_demo_query():
    """'Find me a two bedroom flat in Egaleo under €200k'."""
    response = call("search_listings", {"criteria": {"areas": ["Egaleo"], "hard_limits": {"max_price_eur": 200000, "min_bedrooms": 2}}})
    assert response["total_matches"] > 0
    for item in response["results"]:
        assert item["area"] == "Egaleo" and item["price_eur"] <= 200000 and item["bedrooms"] >= 2
    assert response["data"] == "synthetic listings"


def test_reports_what_unknown_values_excluded():
    response = call("search_listings", {"criteria": {"hard_limits": {"max_price_eur": 500000}}})
    assert response["excluded_because_unknown"].get("price_eur", 0) >= 1


def test_get_listing_marks_description_untrusted():
    record = call("get_listing", {"listing_id": "spitogatos:SYN0001"})
    assert "description_untrusted" in record and "description" not in record
    assert call("get_listing", {"listing_id": "xe:nope"})["error"].startswith("No listing")


def test_limit_is_capped():
    response = call("search_listings", {"criteria": {}, "limit": 500})
    assert response["returned"] <= 50


def test_snapshot_refuses_bad_lines(tmp_path):
    bad = tmp_path / "bad.jsonl"
    bad.write_text('{"listing_id": "xe:1", "source": "xe", "agent_phone": "6971234567"}\n', encoding="utf-8")
    with pytest.raises(SnapshotError, match="line 1"):
        SnapshotAdapter(bad)
