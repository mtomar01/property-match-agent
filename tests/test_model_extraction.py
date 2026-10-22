"""The extraction prompt, its schema, the merge rules and the response cache, with a fake client (no paid calls)."""

import json
from types import SimpleNamespace

import pytest

from agent import llm
from agent.extraction import (READ_FIELDS, SCHEMA, ExtractionError, call, merge, parse_reading, reconcile, request,
                              schema, system_prompt)
from evals.harness.model_extraction import read_one


def blank_reading(**values):
    raw = {name: None for name in READ_FIELDS}
    raw["flags"] = []
    raw["evidence"] = []
    raw.update(values)
    return raw


class FakeClient:
    def __init__(self, raw, stop_reason="end_turn"):
        self.raw, self.stop_reason, self.calls = raw, stop_reason, 0
        self.messages = self

    def create(self, **body):
        self.calls += 1
        usage = SimpleNamespace(input_tokens=100, output_tokens=50, cache_creation_input_tokens=0, cache_read_input_tokens=1000)
        return SimpleNamespace(stop_reason=self.stop_reason, usage=usage,
                               content=[SimpleNamespace(type="text", text=json.dumps(self.raw, ensure_ascii=False))])


def walk(schema):
    yield schema
    for value in schema.values():
        if isinstance(value, dict):
            yield from walk(value)


def test_schema_stays_inside_the_structured_output_limits():
    nodes = list(walk(SCHEMA))
    unions = [n for n in nodes if isinstance(n.get("type"), list) or "anyOf" in n]
    assert len(unions) <= 16  # the API's limit on nullable fields
    assert set(SCHEMA["required"]) == set(SCHEMA["properties"])  # no optional fields
    banned = {"minimum", "maximum", "minLength", "maxLength", "multipleOf"}
    assert not any(banned & set(n) for n in nodes)
    assert all(n.get("additionalProperties") is False for n in nodes if n.get("type") == "object")
    assert list(SCHEMA["properties"])[0] == "evidence"  # quote first, then answer


def test_prompt_has_the_glossary_and_house_style():
    text = system_prompt()
    assert "{{" not in text and "fan coil" in text and "αναβατόριο" in text and "κοινόχρηστος κήπος" in text
    assert "\u2014" not in text  # no em dashes
    body = request("Διαμέρισμα με αποθήκη.", "2026-10-20", "claude-haiku-5-5")
    assert body["output_config"]["format"]["schema"] == SCHEMA
    assert "2026-10-20" in body["messages"][0]["content"] and "<description>" in body["messages"][0]["content"]


def test_each_prompt_version_keeps_its_own_schema():
    assert "good" in schema("extraction_v1")["properties"]["condition"]["enum"]
    assert "good" not in schema("extraction_v2")["properties"]["condition"]["enum"]  # the guide has no "good"
    assert "έως -1" in system_prompt("extraction_v2") and "έως -1" not in system_prompt("extraction_v1")
    v1 = request("x", None, "claude-haiku-5-5", "extraction_v1")
    assert v1["output_config"]["format"]["schema"] == schema("extraction_v1")


def test_parse_reading_cleans_what_the_model_said():
    raw = blank_reading(metro_metres=650, heating_fuel="HEAT_PUMP", energy_class="a+", year_built=3020, lift="yes",
                        flags=["corner", "nonsense"],
                        evidence=[{"field": "metro_metres", "quote": "650 μ. από το μετρό"},
                                  {"field": "storage", "quote": "τηλ 6912345678 αποθήκη"}])
    fields = parse_reading(raw)
    assert fields["metro_walk_min"] == 9  # 650 m at 80 m a minute, rounded up
    assert fields["heating_fuel"] == "heat_pump" and fields["energy_class"] == "A+"
    assert fields["year_built"] is None and fields["lift"] is None  # out of range, wrong type: unknown
    assert fields["flags"] == ["corner"]
    assert fields["evidence"]["metro_walk_min"] == "650 μ. από το μετρό"
    assert "6912345678" not in fields["evidence"]["storage"]
    assert parse_reading(blank_reading(metro_minutes=5, metro_metres=900))["metro_walk_min"] == 5  # minutes as written win


def test_merge_fill_and_conflict_rules():
    code = {"price_eur": 100000, "lift": True, "storage": None, "parking": "space", "flags": ["dual_aspect"],
            "area": "Egaleo", "heating_fuel": "gas"}
    text = {"price_eur": 95000, "lift": False, "storage": True, "parking": "pilotis", "flags": ["corner"],
            "area": "Peristeri", "heating_fuel": "heat_pump"}
    filled, none_blanked = merge(code, text, "fill")
    assert filled["lift"] is True and filled["storage"] is True and none_blanked == []
    fields, blanked = merge(code, text, "conflict")
    assert fields["lift"] is None and fields["heating_fuel"] is None  # D25: they disagree, so unknown
    assert fields["price_eur"] == 100000  # the table wins for price
    assert fields["parking"] == "space"  # pilotis and space both mean "has parking"
    assert fields["area"] == "Egaleo"  # from the card, never from prose
    assert fields["flags"] == ["corner", "dual_aspect"]
    assert sorted(blanked) == ["heating_fuel", "lift"]
    with pytest.raises(ValueError):
        merge(code, text, "vote")


def test_values_that_differ_without_contradicting_follow_the_guide():
    assert reconcile("floor_class", "ground", "raised_ground") == "raised_ground"  # more exact, not a conflict
    assert reconcile("floor_class", "4", "top") == "4"  # a ρετιρέ with a number takes the number
    assert reconcile("floor_class", "3", "1") is None
    fields, blanked = merge({"floor_class": "ground"}, {"floor_class": "raised_ground"}, "conflict")
    assert fields["floor_class"] == "raised_ground" and blanked == []


def test_answers_are_cached_and_only_a_changed_request_pays_again(tmp_path):
    record = {"source_id": "1", "seen": "2026-10-20", "sections": {"Περιγραφή": "Με αποθήκη."}}
    client = FakeClient(blank_reading(storage=True))
    first = read_one(record, "claude-haiku-5-5", "extraction_v1", client, tmp_path)
    again = read_one(record, "claude-haiku-5-5", "extraction_v1", client, tmp_path)
    assert client.calls == 1 and not first["cached"] and again["cached"] and again["raw"]["storage"] is True
    record["sections"]["Περιγραφή"] = "Χωρίς αποθήκη."
    read_one(record, "claude-haiku-5-5", "extraction_v1", client, tmp_path)
    assert client.calls == 2


def test_a_refusal_or_truncation_is_an_error_not_a_reading(tmp_path):
    with pytest.raises(ExtractionError):
        call(FakeClient(blank_reading(), stop_reason="max_tokens"), {})
    record = {"source_id": "2", "seen": None, "sections": {"Περιγραφή": "x"}}
    entry = read_one(record, "claude-haiku-5-5", "extraction_v1", FakeClient(blank_reading(), "refusal"), tmp_path)
    assert entry["raw"] is None and "refusal" in entry["error"]


class TruncatesOnce(FakeClient):
    def create(self, **body):
        self.stop_reason = "max_tokens" if self.calls == 0 else "end_turn"
        self.max_tokens = body["max_tokens"]
        return super().create(**body)


def test_a_long_listing_gets_one_retry_with_more_room_and_failures_are_retried_later(tmp_path):
    record = {"source_id": "3", "seen": None, "sections": {"Περιγραφή": "Μεγάλο κτίριο."}}
    client = TruncatesOnce(blank_reading())
    entry = read_one(record, "claude-haiku-5-5", "extraction_v2", client, tmp_path)
    assert entry["error"] is None and client.calls == 2 and client.max_tokens == 4000
    failing = FakeClient(blank_reading(), "refusal")
    read_one({"source_id": "4", "seen": None, "sections": {"Περιγραφή": "y"}}, "claude-haiku-5-5", "extraction_v2", failing, tmp_path)
    read_one({"source_id": "4", "seen": None, "sections": {"Περιγραφή": "y"}}, "claude-haiku-5-5", "extraction_v2", failing, tmp_path)
    assert failing.calls == 2  # a cached failure isn't reused


def test_cost_follows_the_price_list():
    usage = {"input_tokens": 1_000_000, "output_tokens": 1_000_000, "cache_read_input_tokens": 1_000_000}
    assert llm.cost_usd("claude-haiku-5-5", usage) == pytest.approx(0.10 + 0.50 + 0.01)


def test_v3_adds_kilometres_and_the_station_glossary_without_touching_v2():
    assert "metro_km" in schema("extraction_v3")["properties"] and "metro_km" not in schema("extraction_v2")["properties"]
    assert "Ανθούπολη" in system_prompt("extraction_v3") and "Ανθούπολη" not in system_prompt("extraction_v2")
    assert "Κηφισιά" in system_prompt("extraction_v3") and "Αεροδρόμιο" in system_prompt("extraction_v3")
    walk = list(walk_nodes(schema("extraction_v3")))
    assert len([n for n in walk if isinstance(n.get("type"), list)]) <= 16


def walk_nodes(schema_node):
    yield schema_node
    for value in schema_node.values():
        if isinstance(value, dict):
            yield from walk_nodes(value)


def test_kilometres_become_minutes_in_code():
    assert parse_reading(blank_reading(metro_km=0.6))["metro_walk_min"] == 8  # 600 m at 80 m a minute
    assert parse_reading(blank_reading(metro_km=0.6, metro_metres=450))["metro_walk_min"] == 6  # metres as written win
    assert parse_reading(blank_reading(metro_km=40))["metro_walk_min"] is None  # out of range: unknown


def test_metro_minutes_count_only_on_foot():
    from agent.extraction import apply_walking_rule

    desc = "Σε ήσυχο σημείο, μόλις 5 λεπτά από το Μετρό. Επίσης 9 λεπτά με τα πόδια από τον σταθμό Μετρό."
    vague = parse_reading(blank_reading(metro_minutes=5, evidence=[{"field": "metro_minutes", "quote": "μόλις 5 λεπτά από το Μετρό"}]))
    assert apply_walking_rule(vague, desc)["metro_walk_min"] is None  # no "on foot": doesn't count (D41)
    walk = parse_reading(blank_reading(metro_minutes=9, evidence=[{"field": "metro_minutes", "quote": "9 λεπτά με τα πόδια από τον σταθμό"}]))
    assert apply_walking_rule(walk, desc)["metro_walk_min"] == 9
    metres = parse_reading(blank_reading(metro_metres=500, evidence=[{"field": "metro_metres", "quote": "500 μέτρα από το μετρό"}]))
    assert apply_walking_rule(metres, "500 μέτρα από το μετρό")["metro_walk_min"] == 7  # a distance counts as written


def test_the_baseline_follows_the_on_foot_rule_too():
    from evals.harness.code_baseline import from_description

    assert from_description("Μόλις 5 λεπτά από το μετρό.") == {}
    assert from_description("8 λεπτά με τα πόδια από το μετρό.") == {"metro_walk_min": 8}
