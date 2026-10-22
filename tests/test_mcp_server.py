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


def test_lists_the_tools_and_the_interview_prompt():
    async def go():
        async with Client(mcp) as client:
            tools = sorted(t.name for t in (await client.list_tools()).tools)
            prompts = [p.name for p in (await client.list_prompts()).prompts]
            text = (await client.get_prompt("criteria_interview")).messages[0].content.text
            return tools, prompts, text

    tools, prompts, text = asyncio.run(go())
    assert tools == ["check_supply", "extract_listing", "get_listing", "search_listings"]
    assert prompts == ["criteria_interview"]
    assert "in Athens" in text and "search_listings" in text and "## Output fields" not in text


def test_search_applies_mikes_rules_in_code():
    out = call("search_listings", {"criteria": {"intent": "buy", "hard_limits": {"max_price_eur": 200000}, "budget_around": True}})
    assert out["criteria_applied"]["hard_limits"]["max_price_eur"] == 220000
    assert out["criteria_applied"]["hard_limits"]["min_price_eur"] == 180000
    assert all(180000 <= r["price_eur"] <= 220000 for r in out["results"])


def test_check_supply_counts_in_code():
    out = call("check_supply", {"criteria": {"intent": "buy", "areas": ["Egaleo"], "hard_limits": {"max_price_eur": 150000}}})
    assert out["search_limits"] == {"min_price_eur": 75000, "max_price_eur": 150000} and "matches" in out


def test_extract_listing_merges_the_page_and_the_description(monkeypatch):
    import types

    from agent import llm
    from mcp_server import server

    reading = {name: None for name in __import__("agent.extraction", fromlist=["READ_FIELDS"]).READ_FIELDS}
    reading.update(flags=[], evidence=[{"field": "storage", "quote": "με αποθήκη"}], storage=True, lift=False)

    class Fake:
        def __init__(self):
            self.messages = self

        def create(self, **body):
            usage = types.SimpleNamespace(input_tokens=1, output_tokens=1, cache_creation_input_tokens=0, cache_read_input_tokens=0)
            text = json.dumps(reading, ensure_ascii=False)
            return types.SimpleNamespace(stop_reason="end_turn", usage=usage, content=[types.SimpleNamespace(type="text", text=text)])

    monkeypatch.setattr(llm, "client", lambda: Fake())
    monkeypatch.setattr(server, "CACHE", None)
    out = call("extract_listing", {"description": "Διαμέρισμα με αποθήκη.", "known_fields": {"lift": True, "price_eur": 150000}})
    assert out["fields"]["storage"] is True and out["fields"]["lift"] is True  # the page's tick wins
    assert out["fields"]["price_eur"] == 150000 and out["evidence"]["storage"] == "με αποθήκη"


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


def test_demo_runs_over_stdio(capsys, monkeypatch):
    """The command-line demo starts the real server as a subprocess, like the desktop app."""
    import sys

    from mcp_server import demo

    monkeypatch.setattr(sys, "argv", ["demo", "--area", "Egaleo", "--max-price", "200000", "--limit", "3"])
    demo.main()
    out = capsys.readouterr().out
    assert "synthetic listings" in out and "matches, showing 3" in out
