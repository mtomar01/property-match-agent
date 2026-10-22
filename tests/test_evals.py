"""Tests for the eval itself: it must pass on good search and fail on broken search."""

import asyncio
import json

import core.search
from adapters.snapshot import SnapshotAdapter
from core.filters import FilterOutcome
from evals.harness import build_search_safety
from evals.harness.checks import breaks
from evals.harness.run import run_search_safety


def test_dataset_matches_the_independent_checker():
    """If the synthetic data changes, the frozen expected ids must be rebuilt and reviewed."""
    adapter = SnapshotAdapter()
    rows = [json.loads(line) for line in build_search_safety.DATASET.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 20
    for row in rows:
        expected = sorted(l.listing_id for l in adapter.listings() if not breaks(l.summary(), row["effective_criteria"]))
        assert row["expected_ids"] == expected, row["id"]


def test_search_safety_passes_with_zero_breaks():
    report = asyncio.run(run_search_safety())
    assert report["total_breaks"] == 0
    assert report["count_mismatches"] == 0


def test_eval_catches_a_broken_filter(monkeypatch):
    """Mutation test: switch the hard-limit filter off and the eval must fail.

    An eval that can't fail proves nothing, so this checks it fails for the
    right reason when search ignores the limits.
    """

    def no_filter(listings, criteria):
        return FilterOutcome(matches=list(listings))

    monkeypatch.setattr(core.search, "apply_hard_limits", no_filter)
    report = asyncio.run(run_search_safety())
    assert report["total_breaks"] > 0


def test_checker_flags_unknown_values():
    criteria = {"intent": "buy", "hard_limits": {"max_price_eur": 200000}}
    assert breaks({"listing_type": "sale", "price_eur": None}, criteria)
    assert not breaks({"listing_type": "sale", "price_eur": 200000}, criteria)
