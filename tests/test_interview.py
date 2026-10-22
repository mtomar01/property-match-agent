"""The interview prompt, its tool, the chat runner and the scoring, with fake clients (no paid calls)."""

import json
from types import SimpleNamespace

from adapters.snapshot import SnapshotAdapter
from agent import interview
from core.filters import apply_hard_limits
from core.models import Criteria, HardLimits
from evals.harness import interview_eval as ev


def usage():
    return SimpleNamespace(input_tokens=100, output_tokens=50, cache_creation_input_tokens=0, cache_read_input_tokens=0)


def answer(reply="Ok?", action="ask", asking=(), criteria=None, declined=(), not_covered=()):
    return {"reasoning": "", "reply": reply, "action": action, "asking_about": list(asking),
            "not_covered_areas": list(not_covered), "declined_advice": list(declined),
            "criteria": criteria or {"intent": "buy", "areas": [], "hard_limits": {n: None for n in interview.HARD_FIELDS},
                                     "preferences": [], "open_questions": []}}


def card(intent="buy", areas=(), prefs=(), **limits):
    hard = {n: None for n in interview.HARD_FIELDS}
    hard.update(property_types=[], exclude_floors=[])
    hard.update(limits)
    return {"intent": intent, "areas": list(areas), "hard_limits": hard, "preferences": list(prefs), "open_questions": []}


class Scripted:
    """A fake API client that returns the given responses in order."""

    def __init__(self, responses):
        self.responses, self.bodies = list(responses), []
        self.messages = self

    def create(self, **body):
        self.bodies.append(body)
        item = self.responses.pop(0)
        if isinstance(item, dict) and item.get("tool"):
            block = SimpleNamespace(type="tool_use", id=f"t{len(self.bodies)}", name="check_supply", input=item["tool"])
            return SimpleNamespace(content=[block], stop_reason="tool_use", usage=usage())
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=json.dumps(item, ensure_ascii=False))],
                               stop_reason="end_turn", usage=usage())


def walk(node):
    yield node
    for value in node.values():
        if isinstance(value, dict):
            yield from walk(value)


def test_schema_stays_inside_the_structured_output_limits():
    nodes = list(walk(interview.schema()))
    nullable = [n for n in nodes if isinstance(n.get("type"), list) or "anyOf" in n or None in (n.get("enum") or [])]
    assert len(nullable) <= 16
    assert all(n.get("additionalProperties") is False and set(n["required"]) == set(n["properties"])
               for n in nodes if n.get("type") == "object")
    assert list(interview.schema()["properties"])[0] == "reasoning"
    assert interview.schema()["properties"]["criteria"]["properties"]["areas"]["items"]["enum"] == ["Egaleo", "Peristeri", "Chaidari"]


def test_prompt_is_filled_in_and_borrows_nothing_from_the_test_chats():
    text = interview.system_prompt(today="2026-10-22")
    assert "{{" not in text and "2026-10-22" in text and "min 2021" in text and "—" not in text
    for chat in ev.load_chats():
        for turn in chat["turns"]:
            assert turn not in text


def test_check_supply_counts_in_code_and_says_what_each_limit_costs():
    listings = SnapshotAdapter().listings()  # the synthetic set
    args = {"intent": "buy", "areas": ["Egaleo"], "hard_limits": {"max_price_eur": 150000, "min_bedrooms": 3}}
    result = interview.check_supply(args, listings)
    criteria = Criteria(user_id="t", intent="buy", areas=["Egaleo"], hard_limits=HardLimits(max_price_eur=150000, min_bedrooms=3))
    assert result["matches"] == len(apply_hard_limits(listings, criteria).matches)
    assert set(result["if_dropped"]) == {"max_price_eur", "min_bedrooms"}
    assert all(n >= result["matches"] for n in result["if_dropped"].values())
    assert "error" in interview.check_supply({"intent": "buy", "areas": ["Kypseli"], "hard_limits": {}}, listings)
    assert "note" in interview.check_supply({"intent": "rent", "areas": ["Egaleo"], "hard_limits": {}}, [])


def test_a_reply_can_check_supply_first_and_is_cached(tmp_path):
    final = answer("Δεν υπάρχει τίποτα με όλα αυτά. Χαλαρώνουμε κάτι;", criteria=card(max_price_eur=100000))
    client = Scripted([{"tool": {"intent": "buy", "areas": [], "hard_limits": {"max_price_eur": 100000}}}, final])
    messages = [{"role": "user", "content": "Μέχρι 100.000"}]
    out = interview.reply(client, messages, SnapshotAdapter().listings(), "2026-10-22", cache_dir=tmp_path)
    assert out["output"]["reply"].startswith("Δεν") and len(out["tool_calls"]) == 1
    assert [m["role"] for m in out["added"]] == ["assistant", "user", "assistant"]
    assert out["added"][1]["content"][0]["type"] == "tool_result"
    again = interview.reply(Scripted([]), messages, SnapshotAdapter().listings(), "2026-10-22", cache_dir=tmp_path)
    assert again["output"] == out["output"] and again["paid"] == {}  # replayed from the cache, nothing paid


def test_a_chat_follows_the_script_then_confirms_or_asks_the_simulated_user():
    chat = {"chat_id": "x", "language": "en", "persona": "p", "turns": ["Peristeri, up to 200k.", "Two bedrooms."],
            "user_facts": {"bedrooms": "2"}}
    agent = Scripted([answer("How many bedrooms?", asking=["bedrooms"]),
                      answer("Here's the card. Shall I search?", action="confirm", criteria=card(areas=["Peristeri"]))])
    t = ev.simulate(chat, agent, [], cache_dir=None)
    assert [e["source"] for e in t["log"] if e["role"] == "user"] == ["script", "script", "confirm"]
    assert t["confirmed"] and t["final"]["areas"] == ["Peristeri"]
    asking = Scripted([answer("Any floor you'd rule out?", asking=["floor"])] * 4)
    sim = Scripted([{"reply": "No preference."}, {"reply": "No preference."}])
    t = ev.simulate(dict(chat, turns=["Peristeri, up to 200k."]), asking, [], cache_dir=None, sim_client=sim)
    assert [e["source"] for e in t["log"] if e["role"] == "user"] == ["script", "simulated", "simulated"]
    assert not t["confirmed"]


def test_fields_count_empty_areas_as_all_and_catch_invented_limits():
    expected = card(areas=[], max_price_eur=200000)
    predicted = card(areas=["Egaleo", "Peristeri", "Chaidari"], max_price_eur=200000, min_size_m2=50)
    assert ev.field_outcomes(expected, predicted) == {"intent": "correct", "areas": "correct",
                                                      "max_price_eur": "correct", "min_size_m2": "invented"}
    assert ev.field_outcomes(card(property_types=["apartment"]), card())["property_types"] == "missed"


def test_preferences_match_on_feature_and_bound_and_spot_a_split():
    pref = {"feature": "year_built", "min": 2000, "max": None, "equals": None, "weight": 0.7}
    rows = ev.preference_outcomes(card(prefs=[pref]), card(prefs=[dict(pref, weight=0.5)]))
    assert rows == [{"feature": "year_built", "expected": ["min", 2000], "result": "correct", "weight": "disagrees"}]
    assert ev.preference_outcomes(card(prefs=[pref]), card(prefs=[dict(pref, min=1995)]))[0]["result"] == "wrong_bound"
    as_pref = {"feature": "bedrooms", "min": 2, "max": None, "equals": None, "weight": 0.8}
    rows = ev.preference_outcomes(card(min_bedrooms=2), card(prefs=[as_pref]))
    assert rows == [{"feature": "bedrooms", "predicted": ["min", 2], "result": "split"}]


def test_numbers_are_read_the_way_people_write_them():
    assert ev.numbers_in("€185k, 185.000 € or 185,000; 2,5 km; 12 listings") >= {185000.0, 2.5, 12.0}
    results = [{"matches": 0, "if_dropped": {"min_size_m2": 7}, "median_price_eur": 210000}]
    assert ev.quotes_tool_number("Dropping the size limit gives 7 listings.", results, {130.0, 4.0})
    assert not ev.quotes_tool_number("You asked for 130 m² and 4 bedrooms.", results, {130.0, 4.0})
    assert ev.quotes_tool_number("The median here is about €210k.", results, set())


def test_behaviours_need_the_question_the_language_and_the_named_area():
    chat = {"must_ask": ["which_covered_area"], "must_say": ["area_not_covered:Κυψέλη", "reply_in:el"], "must_not_invent": ["min_size_m2"]}
    log = [{"role": "user", "text": "Κυψέλη ή Αιγάλεω", "source": "script", "language": "el"},
           {"role": "assistant", "output": answer("Η Κυψέλη δεν καλύπτεται ακόμα. Σας κάνει το Αιγάλεω;",
                                                  asking=["which_covered_area"], not_covered=["Κυψέλη"])}]
    result = ev.behaviours(chat, {"log": log, "final": card(areas=["Egaleo"])})
    assert result == {"ask:which_covered_area": True, "area_not_covered:Κυψέλη": True, "reply_in:el": True,
                      "not_invented:min_size_m2": True}
    log[1]["output"]["reply"] = "Kypseli isn't covered yet. Is Egaleo ok?"
    result = ev.behaviours(chat, {"log": log, "final": card(areas=["Egaleo"])})
    assert result["reply_in:el"] is False and result["area_not_covered:Κυψέλη"] is True
    assert ev.language("Θέλω δύο υπνοδωμάτια στο Egaleo.") == "el" and ev.language("Two bedrooms in Αιγάλεω please") == "en"


def test_a_card_the_search_cant_run_on_goes_back_to_the_model_once():
    bad = card(prefs=[{"feature": "floor_level", "min": "top", "max": None, "equals": None, "weight": 0.7}])
    good = card(prefs=[{"feature": "floor_level", "min": 4, "max": None, "equals": None, "weight": 0.7}])
    client = Scripted([answer("Card?", "confirm", criteria=bad), answer("Card?", "confirm", criteria=good)])
    out = interview.reply(client, [{"role": "user", "content": "x"}], [], "2026-10-22")
    assert out["output"]["criteria"] == good and len(out["repairs"]) == 1 and "energy_class" in out["repairs"][0]
    assert "<code_check>" in client.bodies[1]["messages"][-1]["content"]
    stubborn = Scripted([answer("Card?", "confirm", criteria=bad)] * 2)
    out = interview.reply(stubborn, [{"role": "user", "content": "x"}], [], "2026-10-22")
    assert out["output"]["criteria"] == bad and len(stubborn.bodies) == 2  # one repair, then the eval counts it


def test_the_simulated_user_knows_what_it_already_said():
    chat = {"chat_id": "x", "language": "en", "persona": "p", "turns": ["One bedroom in Peristeri."], "user_facts": {}}
    sim = Scripted([{"reply": "No preference."}])
    ev.simulated_answer(chat, "Anything else?", "en", sim, None, ["One bedroom in Peristeri.", "Yes."])
    assert "<you_already_said>\n- One bedroom in Peristeri.\n- Yes.\n</you_already_said>" in sim.bodies[0]["messages"][0]["content"]


def test_a_basic_fact_the_user_gave_unasked_counts_but_a_clarification_must_be_asked():
    chat = {"must_ask": ["budget", "budget_ceiling"], "must_say": [], "must_not_invent": [],
            "expected_criteria": card(max_price_eur=200000)}
    log = [{"role": "user", "text": "Buying, up to 200k.", "source": "script", "language": "en"},
           {"role": "assistant", "output": answer("Here's the card. Right?", "confirm", criteria=card(max_price_eur=200000))}]
    result = ev.behaviours(chat, {"log": log, "final": card(max_price_eur=200000)})
    assert result == {"ask:budget": True, "ask:budget_ceiling": False}
    assert ev.behaviours(chat, {"log": log, "final": card(max_price_eur=250000)})["ask:budget"] is False
