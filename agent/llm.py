"""The one place that talks to the Claude API: the key, the client, and what a call costs.

The key never lives in the repo. It comes from the ANTHROPIC_API_KEY variable,
or from ~/.config/property-match/anthropic.env on this machine only.
"""

from __future__ import annotations

import os
from pathlib import Path

KEY_FILE = Path.home() / ".config" / "property-match" / "anthropic.env"

# US dollars per million tokens, from platform.claude.com/docs/en/about-claude/pricing,
# read on 22 October 2026. A cache write (5 minutes) costs 1.25 times the input price.
PRICES: dict[str, dict[str, float]] = {
    "claude-haiku-5-5": {"input": 0.10, "output": 0.50, "cache_write": 0.125, "cache_read": 0.01},
    "claude-sonnet-5-5": {"input": 2.00, "output": 10.00, "cache_write": 2.50, "cache_read": 0.10},
}

USAGE_KEYS = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")


def api_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if key:
        return key
    if KEY_FILE.exists():
        for line in KEY_FILE.read_text(encoding="utf-8").splitlines():
            if line.startswith("ANTHROPIC_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"')
    raise RuntimeError(f"No API key: set ANTHROPIC_API_KEY or put it in {KEY_FILE}")


def client(max_retries: int = 4):
    import anthropic

    return anthropic.Anthropic(api_key=api_key(), max_retries=max_retries)


def usage_dict(usage) -> dict[str, int]:
    """The token counts of one response, as plain numbers (0 where the API left a field out)."""
    return {key: int(getattr(usage, key, 0) or 0) for key in USAGE_KEYS}


def add_usage(total: dict[str, int], usage: dict[str, int]) -> dict[str, int]:
    for key in USAGE_KEYS:
        total[key] = total.get(key, 0) + usage.get(key, 0)
    return total


def cost_usd(model: str, usage: dict[str, int]) -> float:
    price = PRICES[model]
    return (usage.get("input_tokens", 0) * price["input"]
            + usage.get("output_tokens", 0) * price["output"]
            + usage.get("cache_creation_input_tokens", 0) * price["cache_write"]
            + usage.get("cache_read_input_tokens", 0) * price["cache_read"]) / 1_000_000
