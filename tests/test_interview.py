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


def card(intent="buy", areas=(), prefs=(), budget_around=False, **limits):
    hard = {n: None for n in interview.HARD_FIELDS}
    hard.update(property_types=[], exclude_floors=[])
    hard.update(limits)
    return {"intent": intent, "areas": list(areas), "hard_limits": hard, "budget_around": budget_around,
            "preferences": list(prefs), "open_questions": []}


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
    criteria = Criteria(user_id="t", intent="buy", areas=["Egaleo"],
                        hard_limits=HardLimits(max_price_eur=150000, min_price_eur=75000, min_bedrooms=3))  # half the top, added by code
    assert result["matches"] == len(apply_hard_limits(listings, criteria).matches)
    assert set(result["if_dropped"]) == {"max_price_eur", "min_price_eur", "min_bedrooms"}
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
                      answer("Here's the card. Shall I search?", action="confirm", criteria=card(areas=["Peristeri"], max_price_eur=200000))])
    t = ev.simulate(chat, agent, [], cache_dir=None)
    assert [e["source"] for e in t["log"] if e["role"] == "user"] == ["script", "script", "confirm"]
    assert t["confirmed"] and t["final"]["areas"] == ["Peristeri"]
    asking = Scripted([answer("Any floor you'd rule out?", asking=["floor"])] * 4)
    sim = Scripted([{"facts_used": [], "reply": "No preference."}] * 2)
    t = ev.simulate(dict(chat, turns=["Peristeri, up to 200k."]), asking, [], cache_dir=None, sim_client=sim)
    assert [e["source"] for e in t["log"] if e["role"] == "user"] == ["script", "simulated, no fact", "simulated, no fact"]
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
    bad = card(max_price_eur=150000, prefs=[{"feature": "floor_level", "min": "top", "max": None, "equals": None, "weight": 0.7}])
    good = card(max_price_eur=150000, prefs=[{"feature": "floor_level", "min": 4, "max": None, "equals": None, "weight": 0.7}])
    client = Scripted([answer("Card?", "confirm", criteria=bad), answer("Card?", "confirm", criteria=good)])
    out = interview.reply(client, [{"role": "user", "content": "x"}], [], "2026-10-22")
    assert out["output"]["criteria"] == good and len(out["repairs"]) == 1 and "energy_class" in out["repairs"][0]
    assert "<code_check>" in client.bodies[1]["messages"][-1]["content"]
    stubborn = Scripted([answer("Card?", "confirm", criteria=bad)] * 2)
    out = interview.reply(stubborn, [{"role": "user", "content": "x"}], [], "2026-10-22")
    assert out["output"]["criteria"] == bad and len(stubborn.bodies) == 2  # one repair, then the eval counts it


def test_the_simulated_user_knows_what_it_already_said():
    chat = {"chat_id": "x", "language": "en", "persona": "p", "turns": ["One bedroom in Peristeri."], "user_facts": {}}
    sim = Scripted([{"facts_used": [], "reply": "No preference."}])
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


def test_a_wide_search_comes_with_a_breakdown_code_counted():
    listings = SnapshotAdapter().listings()  # 54 synthetic listings for sale
    wide = interview.check_supply({"intent": "buy", "areas": [], "hard_limits": {}}, listings)
    assert wide["matches"] > interview.WIDE
    assert sum(wide["breakdown"]["by_bedrooms"].values()) == sum(wide["breakdown"]["by_size"].values()) == wide["matches"]
    narrow = interview.check_supply({"intent": "buy", "areas": ["Egaleo"], "hard_limits": {}}, listings)
    assert narrow["matches"] <= interview.WIDE and "breakdown" not in narrow
    assert ev.quotes_tool_number(f"{wide['breakdown']['with_balcony']} of them have a balcony.", [wide], set())


def test_a_simulated_answer_with_no_fact_behind_it_becomes_no_preference():
    chat = {"chat_id": "x", "language": "el", "persona": "p", "turns": ["Μέχρι 150.000 στο Χαϊδάρι."], "user_facts": {"budget": "150.000 €"}}
    assert ev.guarded("Τουλάχιστον τρία υπνοδωμάτια.", [], chat, chat["turns"], "el") == ("Δεν έχω προτίμηση.", True)
    assert ev.guarded("Θέλω 3 υπνοδωμάτια.", ["budget"], chat, chat["turns"], "el")[1] is True  # a number nobody gave
    assert ev.guarded("Ναι, μέχρι 150.000.", ["budget"], chat, chat["turns"], "el") == ("Ναι, μέχρι 150.000.", False)
    assert set(ev.sim_schema(chat)["properties"]["facts_used"]["items"]["enum"]) == {"budget", "already_said"}


def test_a_thin_search_comes_with_eased_limits_code_counted():
    listings = SnapshotAdapter().listings()
    thin = interview.check_supply({"intent": "buy", "areas": ["Egaleo"], "hard_limits": {"max_price_eur": 150000, "min_bedrooms": 3}}, listings)
    assert thin["matches"] < interview.THIN
    eased = thin["if_eased"]
    assert eased["max_price_eur"]["to"] == 165000 and eased["min_bedrooms"]["to"] == 2
    assert {"add_area:Peristeri", "add_area:Chaidari"} <= set(eased)
    assert all(option["matches"] >= thin["matches"] for option in eased.values())
    gap = interview.check_supply({"intent": "rent", "areas": [], "hard_limits": {"max_price_eur": 900}},
                                 [l for l in listings if l.listing_type == "sale"])
    assert "if_eased" not in gap and "won't help" in gap["note"]


def test_a_limit_loosened_after_a_yes_from_the_harness_is_caught():
    first = card(areas=["Peristeri"], min_size_m2=120, max_price_eur=150000)
    looser = card(areas=["Peristeri"], max_price_eur=150000)
    log = [{"role": "user", "text": "Over 120 m², under 150k, Peristeri.", "source": "script", "language": "en"},
           {"role": "assistant", "output": answer("0 match. Ease the size?", "ask", ["ease_limit"], first)},
           {"role": "user", "text": "No preference.", "source": "simulated, no fact", "language": "en"},
           {"role": "assistant", "output": answer("Done. Search?", "confirm", criteria=looser)}]
    assert ev.unasked_loosenings(log) == ["min_size_m2"]
    log[2]["source"] = "script"  # the user's own words asked for it
    assert ev.unasked_loosenings(log) == []
    assert ev._looser("areas", ["Peristeri"], []) and not ev._looser("areas", [], ["Peristeri"])


def test_a_suggestion_to_ease_a_limit_gets_a_fixed_no_preference():
    chat = {"chat_id": "x", "language": "en", "persona": "p", "turns": ["Peristeri, over 120 m², under 150k."], "user_facts": {}}
    agent = Scripted([answer("0 pass. Adding Egaleo gives 2. Shall I?", asking=["ease_limit"]),
                      answer("Keeping it. Search?", "confirm", criteria=card(areas=["Peristeri"], max_price_eur=150000))])
    t = ev.simulate(chat, agent, [], cache_dir=None, sim_client=Scripted([]))  # the model user is never called
    assert [(e["source"], e["text"]) for e in t["log"] if e["role"] == "user"][1] == ("fixed, easing", "No preference.")


def test_a_chat_from_the_writing_page_becomes_an_eval_chat():
    from evals.harness.interview_clean_test import to_chat

    doc = {"chat_no": 2, "language": "el", "turns": ["Ψάχνω κάτι στο Περιστέρι, γύρω στις 200.", "Μέχρι 200 το πολύ.", "", ""],
           "facts": "Bedrooms: δύο\nΔεν θέλω ισόγειο", "intent": "buy", "areas": ["Peristeri"], "not_covered": "Κουκάκι, Πατήσια",
           "hard_limits": {"max_price_eur": 200000}, "property_types": [], "exclude_floors": ["ground"],
           "preferences": [{"feature": "balcony", "bound": "yes", "value": "", "weight": "0.7"},
                           {"feature": "energy_class", "bound": "min", "value": "c", "weight": "0.6"},
                           {"feature": "metro_walk_min", "bound": "max", "value": "", "weight": "0.6"}],
           "must": ["budget_ceiling", "say:tradeoff_with_numbers"], "notes": ""}
    chat = to_chat(doc, "mike")
    assert chat["chat_id"] == "clean_mike_2" and chat["turns"] == doc["turns"][:2]
    assert chat["user_facts"] == {"bedrooms": "δύο", "fact_2": "Δεν θέλω ισόγειο"}
    assert chat["expected_criteria"]["hard_limits"] == {"max_price_eur": 200000, "exclude_floors": ["ground"]}
    assert chat["expected_criteria"]["preferences"] == [{"feature": "balcony", "weight": 0.7, "equals": True},
                                                        {"feature": "energy_class", "weight": 0.6, "min": "C"}]
    assert chat["must_ask"] == ["budget_ceiling"]
    assert chat["must_say"] == ["reply_in:el", "tradeoff_with_numbers", "area_not_covered:Κουκάκι", "area_not_covered:Πατήσια"]


def test_greeklish_counts_as_greek():
    assert ev.language("Kalispera chat, tha ithela ena diamerisma na agorasw") == "el"
    assert ev.language("den me noiazei o orofos") == "el"
    assert ev.language("Hi, I'd like a flat in Egaleo with a balcony, up to 200k.") == "en"
    assert ev.language("From 40 sqm and 2 bedrooms at least") == "en"


def test_mikes_budget_rules_are_applied_by_code():
    around = interview.search_card(card(max_price_eur=200000, budget_around=True))["hard_limits"]
    assert (around["min_price_eur"], around["max_price_eur"]) == (180000, 220000)
    ceiling = interview.search_card(card(max_price_eur=200000))["hard_limits"]
    assert (ceiling["min_price_eur"], ceiling["max_price_eur"]) == (100000, 200000)  # half the top (D60)
    invest = interview.search_card(card(intent="invest", max_price_eur=150000))["hard_limits"]
    assert invest["min_price_eur"] == 75000  # the same half for an investment
    small = interview.search_card(card(intent="rent", max_price_eur=900))["hard_limits"]
    assert small["min_price_eur"] == 450  # a monthly figure rounds to €50
    stated = interview.search_card(card(intent="rent", max_price_eur=800, min_price_eur=700))["hard_limits"]
    assert stated["min_price_eur"] == 700  # the user's own minimum wins
    assert interview.search_card(card())["hard_limits"].get("min_price_eur") is None  # no top price, nothing to derive


def test_a_confirmed_card_needs_a_top_price():
    assert "top price" in interview.card_problem(card(), "confirm")
    assert interview.card_problem(card(), "ask") is None
    assert interview.card_problem(card(max_price_eur=600), "confirm") is None


def test_a_year_needs_a_number_and_a_balcony_a_yes_or_no():
    year = {"feature": "renovated_year", "min": None, "max": None, "equals": True, "weight": 0.5}
    assert "needs a number" in interview.card_problem(card(max_price_eur=200000, prefs=[year]), "confirm")
    balcony = {"feature": "balcony", "min": 1, "max": None, "equals": None, "weight": 0.5}
    assert "yes or no" in interview.card_problem(card(max_price_eur=200000, prefs=[balcony]), "confirm")


def test_a_thin_apartment_search_can_offer_maisonettes_and_lofts():
    listings = SnapshotAdapter().listings()
    thin = interview.check_supply({"intent": "buy", "areas": ["Egaleo"], "budget_around": False,
                                   "hard_limits": {"max_price_eur": 90000, "property_types": ["apartment"]}}, listings)
    assert thin["matches"] < interview.THIN and {"add_type:maisonette", "add_type:loft"} <= set(thin["if_eased"])
    assert thin["search_limits"] == {"min_price_eur": 45000, "max_price_eur": 90000}


def test_around_is_scored_as_what_the_model_caught_and_a_silent_switch_is_loosening():
    said = dict(card(max_price_eur=200000), budget_around=True)
    assert ev.field_outcomes(said, card(max_price_eur=200000))["budget_around"] == "missed"
    assert "budget_around" not in ev.field_outcomes(card(max_price_eur=200000), card(max_price_eur=200000))
    log = [{"role": "user", "text": "Up to 200k.", "source": "script", "language": "en"},
           {"role": "assistant", "output": answer("Card?", "confirm", criteria=card(max_price_eur=200000))},
           {"role": "user", "text": "No preference.", "source": "simulated, no fact", "language": "en"},
           {"role": "assistant", "output": answer("Card?", "confirm", criteria=dict(card(max_price_eur=200000), budget_around=True))}]
    assert ev.unasked_loosenings(log) == ["budget_around"]


def test_rentals_are_refused_in_code_and_the_eval_checks_it_was_said():
    assert "rentals" in interview.card_problem(card(intent="rent", max_price_eur=800), "confirm")
    chat = {"must_ask": [], "must_say": ["rent_not_supported"], "must_not_invent": [], "expected_criteria": card(intent="rent")}
    said = dict(answer("Δεν υποστηρίζουμε ακόμα ενοικιάσεις. Θέλετε να δούμε αγορά;", criteria=card(intent="rent")), unsupported=["rent"])
    log = [{"role": "user", "text": "Ενοικίαση στο Χαϊδάρι, 700-800.", "source": "script", "language": "el"},
           {"role": "assistant", "output": said}]
    assert ev.behaviours(chat, {"log": log, "final": card(intent="rent")}) == {"rent_not_supported": True}
    scored = ev.score_chat(dict(chat, chat_id="r", language="el", tests=[]), {"log": log, "final": card(intent="rent"),
                                                                              "confirmed": False, "final_valid": True, "cost_usd": 0})
    assert scored["fields"] == {} and scored["unsupported"]


def test_answering_the_purpose_question_counts_as_choosing_investor_mode():
    chat = {"must_ask": ["confirm_investor_mode", "purpose"], "must_say": [], "must_not_invent": [],
            "expected_criteria": card(intent="invest", max_price_eur=180000)}
    log = [{"role": "user", "text": "Αγορά, 180 χιλιάδες.", "source": "script", "language": "el"},
           {"role": "assistant", "output": answer("Για να μείνετε ή ως επένδυση;", asking=["purpose"])}]
    assert ev.behaviours(chat, {"log": log, "final": card(intent="invest", max_price_eur=180000)}) == \
        {"ask:confirm_investor_mode": True, "ask:purpose": True}


def test_the_prompt_fills_in_the_renovated_year():
    text = interview.system_prompt(today="2026-10-22")
    assert "renovated_year with min 2016" in text and "rent" in text


def test_wide_means_the_cards_own_check_not_a_probe():
    probe = {"input": {}, "result": {"matches": 484}}
    own = {"input": {}, "result": {"matches": 8}}
    replies = [{"output": answer("Card?", "confirm", criteria=card(max_price_eur=150000)), "tool_calls": [probe, own]}]
    assert ev.card_matches(replies) == 8


def test_ideally_keeps_size_and_bedrooms_as_limits_with_code_margins():
    soft = dict(card(max_price_eur=200000, min_size_m2=30, max_size_m2=50, min_bedrooms=1), ideally=["size", "bedrooms"])
    limits = interview.search_card(soft)["hard_limits"]
    assert (limits["min_size_m2"], limits["max_size_m2"]) == (27, 55)
    assert limits["min_bedrooms"] is None and limits["max_bedrooms"] == 2  # ideally 1 bedroom: 0 to 2
    two = interview.search_card(dict(card(max_price_eur=200000, min_bedrooms=2), ideally=["bedrooms"]))["hard_limits"]
    assert (two["min_bedrooms"], two["max_bedrooms"]) == (1, 3)
    plain = interview.search_card(card(max_price_eur=200000, min_bedrooms=2))["hard_limits"]
    assert plain["min_bedrooms"] == 2 and plain.get("max_bedrooms") is None


def test_a_maximum_bedroom_count_filters_in_code():
    from core.filters import check
    from core.models import Listing
    listings = SnapshotAdapter().listings()
    big = next(l for l in listings if l.bedrooms and l.bedrooms >= 3)
    criteria = Criteria(user_id="t", intent=("rent" if big.listing_type == "rent" else "buy"), hard_limits=HardLimits(max_bedrooms=2))
    assert check(big, criteria) == ("too_many_bedrooms", "bedrooms")


def test_investor_mode_is_confirmed_on_the_card():
    chat = {"must_ask": ["confirm_investor_mode"], "must_say": [], "must_not_invent": [],
            "expected_criteria": card(intent="invest", max_price_eur=150000)}
    log = [{"role": "user", "text": "An investment to rent out, around 150k.", "source": "script", "language": "en"},
           {"role": "assistant", "output": answer("Investor mode, up to 150k. Right?", "confirm", criteria=card(intent="invest", max_price_eur=150000))}]
    assert ev.behaviours(chat, {"log": log, "final": card(intent="invest", max_price_eur=150000)}) == {"ask:confirm_investor_mode": True}


def test_v6_knows_athens_and_lets_the_users_year_win():
    text = interview.system_prompt("interview_v6", today="2026-10-22")
    assert "in Athens" in text and "min 2015" in text and "ideally" in text and "investor mode\" on the card" in text


def test_every_hard_limit_has_a_loosening_rule():
    for name in interview.HARD_FIELDS:
        sample = ["ground"] if name in ("exclude_floors", "property_types") else 2
        ev._looser(name, sample, sample)  # raises for a limit with no rule
    assert ev._looser("max_bedrooms", 2, 3) and not ev._looser("max_bedrooms", 3, 2)
