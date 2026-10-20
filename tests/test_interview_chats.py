"""The interview dataset must be well formed before any model is scored on it."""

import json
from pathlib import Path

import pytest

from core.models import Criteria

DATASET = Path(__file__).resolve().parent.parent / "evals" / "datasets" / "interview_chats.jsonl"
ROWS = [json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines() if line.strip()]
KNOWN_BEHAVIOURS = (
    "reply_in:", "area_not_covered:", "tradeoff_with_numbers", "no_mortgage_advice",
    "no_investment_advice", "confirm_change",
)


def test_forty_chats_half_greek():
    assert len(ROWS) == 40
    assert sum(r["language"] == "el" for r in ROWS) == 20
    assert len({r["chat_id"] for r in ROWS}) == 40


@pytest.mark.parametrize("row", ROWS, ids=[r["chat_id"] for r in ROWS])
def test_expected_criteria_validate(row):
    Criteria.model_validate({"user_id": "eval", **row["expected_criteria"]})


@pytest.mark.parametrize("row", ROWS, ids=[r["chat_id"] for r in ROWS])
def test_chat_shape(row):
    assert row["turns"] and all(isinstance(t, str) and t.strip() for t in row["turns"])
    for behaviour in row["must_say"]:
        assert behaviour.startswith(KNOWN_BEHAVIOURS), behaviour
    assert any(b.startswith("reply_in:") for b in row["must_say"])
