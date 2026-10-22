"""The interview eval: 40 scripted chats, scored in code (spec section 12, D46).

How a chat runs:
1. The user's scripted turns are sent in order, word for word, whatever the
   assistant asked. They were written as answers to the questions a good
   interview asks, so an assistant that asks something else still gets the
   facts, but fails the must_ask check.
2. When the script runs out: if the assistant shows a card to confirm, a fixed
   "yes, go ahead" ends the chat and that card is scored. If it's still asking,
   a simulated user (Haiku 5.5) answers from the chat's user_facts only, or says
   it has no preference; after two such answers the last card is scored as
   unconfirmed.

How it's scored, all in code (the spec keeps model judges for explanations):
- Fields: intent, areas (empty means every covered area) and each hard limit
  either side set. Correct, wrong, missed or invented. Target 95%, and no
  invented hard limit.
- Preferences: right feature and bound. Weights only as strong (0.7 or more)
  or weak (below 0.4), counted separately. A limit on the wrong side (a hard
  limit made a preference or the reverse) is a split.
- Behaviours: must_ask from the reply's question tags, on a reply with a
  question mark; reply language against the user's latest message; areas not
  covered named in the reply and kept off the card; trade-offs quoting a number
  that check_supply returned; declined advice flagged and pointing to a
  professional; a change confirmed. The advice checks are proxies, so the
  report prints those replies to read.

Run: uv run python -m evals.harness.interview_eval [--limit N] [--only el_01,en_10]
     Pays for every call not already cached (Sonnet for the assistant, Haiku for the simulated user).
"""

from __future__ import annotations

import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from adapters.snapshot import SnapshotAdapter
from agent import interview, llm
from core.models import SEARCH_AREAS
from evals.harness.build_label_tool import ROOT

CHATS = ROOT / "evals" / "datasets" / "interview_chats.jsonl"
PRIVATE = ROOT / "data" / "private" / "evals" / "interview"
CACHE = ROOT / "data" / "private" / "evals" / "model_cache"
RESULTS = ROOT / "evals" / "results"
SNAPSHOT = ROOT / "data" / "private" / "snapshot.jsonl"
TODAY = "2026-10-22"  # fixed, so the prompt and the cache keys don't change from day to day
SIM_MODEL = "claude-haiku-5-5"
EXTRA_ANSWERS = 2
TARGETS = {"field_accuracy": 0.95, "invented_hard_limits": 0, "unasked_loosenings": 0}

CONFIRM = {"en": "Yes, that's right. Go ahead.", "el": "Ναι, σωστά. Προχώρα."}
COUNTERPART = {"max_price_eur": "price_eur", "min_price_eur": "price_eur", "min_size_m2": "size_m2",
               "max_size_m2": "size_m2", "min_bedrooms": "bedrooms", "exclude_floors": "floor_level"}
PROFESSIONAL = re.compile(r"bank|broker|advis|adviser|advisor|professional|accountant|lawyer|τράπεζ|σύμβουλ|"
                          r"επαγγελματ|λογιστ|δικηγόρ|μεσίτ", re.I)
AREA_ALIASES = {"Kypseli": ("kypseli", "κυψέλη", "κυψελη"), "Κυψέλη": ("kypseli", "κυψέλη", "κυψελη"),
                "Pangrati": ("pangrati", "pagrati", "pagkrati", "παγκράτι", "παγκρατι")}

SIM_SYSTEM = """You play a person looking for a home, in a test of a property search assistant.
Answer the assistant's latest message in one or two short sentences, in the language given.
Use only your facts and what you've already said; never contradict what you've already said.
If it asks about something those don't cover, or suggests a change they don't cover, say you have no preference.
If it shows a summary and asks whether it's right, say yes. If it asks you to confirm something you've already said, confirm it.
Never add a wish, a limit or a detail of your own.
In facts_used, list the facts your answer rests on ("already_said" for what you've said before). If none, leave it empty."""
NO_PREFERENCE = {"en": "No preference.", "el": "Δεν έχω προτίμηση."}


def sim_schema(chat: dict) -> dict:
    """The simulated user names the facts behind its answer; code drops an answer with none (D49)."""
    sources = [*chat["user_facts"], "already_said"]
    return {"type": "object", "additionalProperties": False, "required": ["facts_used", "reply"],
            "properties": {"facts_used": {"type": "array", "items": {"type": "string", "enum": sources}},
                           "reply": {"type": "string"}}}


def guarded(reply: str, facts_used: list[str], chat: dict, said: list[str], lang: str) -> tuple[str, bool]:
    """Keep the simulated answer only if it rests on a fact and every number in it was given before."""
    allowed = set().union(*(numbers_in(str(v)) for v in chat["user_facts"].values()), *(numbers_in(t) for t in said))
    if not facts_used or not numbers_in(reply) <= allowed:
        return NO_PREFERENCE[lang], True
    return reply, False


# ---------------------------------------------------------------------------
# Running a chat
# ---------------------------------------------------------------------------


# Greek written in Latin letters ("Greeklish"): words that are common in Greek and rare in English (D52).
GREEKLISH = {"kalispera", "kalimera", "geia", "thelo", "thelw", "ithela", "einai", "kai", "mexri", "gia", "apo", "den",
             "noiazei", "tha", "stin", "sto", "ena", "mia", "tetragonika", "ypnodomatio", "ypnodomatia", "diamerisma",
             "agorasw", "agoraso", "enoikio", "anakainismeno", "orofos", "xronologia", "paidi", "idanika", "spiti"}


def language(text: str) -> str:
    letters = [c for c in text if c.isalpha()]
    greek = sum(1 for c in letters if "Ͱ" <= c <= "Ͽ" or "ἀ" <= c <= "῿")
    if letters and greek / len(letters) >= 0.5:
        return "el"
    words = set(re.findall(r"[a-z]+", text.lower()))
    return "el" if len(words & GREEKLISH) >= 2 else "en"


def simulated_answer(chat: dict, said: str, lang: str, client, cache_dir: Path | None,
                     already: list[str] | None = None) -> tuple[str, dict]:
    facts = json.dumps(chat["user_facts"], ensure_ascii=False)
    earlier = "\n".join(f"- {t}" for t in already or chat["turns"])
    body = {"model": SIM_MODEL, "max_tokens": 1500, "system": SIM_SYSTEM,  # Haiku 5.5 can think first: leave room
            "messages": [{"role": "user", "content": (f"<persona>{chat['persona']}</persona>\n<facts>{facts}</facts>\n"
                                                      f"<you_already_said>\n{earlier}\n</you_already_said>\n"
                                                      f"<language>{'Greek' if lang == 'el' else 'English'}</language>\n"
                                                      f"<assistant_said>{said}</assistant_said>")}],
            "output_config": {"format": {"type": "json_schema", "schema": sim_schema(chat)}}}
    response = interview.call(client, body, cache_dir)
    text = "".join(b["text"] for b in response["content"] if b["type"] == "text")
    if response["stop_reason"] != "end_turn" or not text:
        raise SimulatedUserError(f"the simulated user gave no answer (stop reason {response['stop_reason']})")
    answer = json.loads(text)
    reply, dropped = guarded(answer["reply"], answer["facts_used"], chat, already or chat["turns"], lang)
    return reply, dict(response, dropped=dropped, original=answer["reply"] if dropped else None)


class SimulatedUserError(RuntimeError):
    pass


def simulate(chat: dict, client, listings: list, model: str = interview.MODEL, version: str = interview.PROMPT_VERSION,
             cache_dir: Path | None = CACHE, sim_client=None) -> dict:
    sim_client = sim_client or client
    messages, log = [], []
    usage = {"assistant": {}, "assistant_paid": {}, "simulated_user": {}, "simulated_user_paid": {}}
    script, extra, last, confirmed, lang = list(chat["turns"]), 0, None, False, chat["language"]
    agent_cache = cache_dir / version / model if cache_dir else None
    sim_cache = cache_dir / "interview_sim_user" / SIM_MODEL if cache_dir else None
    for _ in range(len(chat["turns"]) + EXTRA_ANSWERS + 1):
        if script:
            text, source = script.pop(0), "script"
            lang = language(text)
        elif last and last.get("output") and last["output"]["action"] == "confirm":
            text, source, confirmed = CONFIRM[lang], "confirm", True
        elif extra < EXTRA_ANSWERS and last and last.get("output") and "ease_limit" in (last["output"]["asking_about"] or []):
            # No chat's facts say the user would loosen a limit, so a suggestion to ease one gets a fixed
            # "no preference", never a model's yes (D50). The rule says that keeps the card as it was.
            text, source, extra = NO_PREFERENCE[lang], "fixed, easing", extra + 1
        elif extra < EXTRA_ANSWERS and last and last.get("output"):
            text, response = simulated_answer(chat, last["output"]["reply"], lang, sim_client, sim_cache,
                                              [e["text"] for e in log if e["role"] == "user"])
            llm.add_usage(usage["simulated_user"], response["usage"])
            if not response["cached"]:
                llm.add_usage(usage["simulated_user_paid"], response["usage"])
            source, extra = ("simulated, no fact" if response.get("dropped") else "simulated"), extra + 1
        else:
            break
        log.append({"role": "user", "text": text, "source": source, "language": lang})
        if confirmed:
            break
        messages.append({"role": "user", "content": text})
        last = interview.reply(client, messages, listings, TODAY, model, version, agent_cache)
        messages.extend(last["added"])
        llm.add_usage(usage["assistant"], last["usage"])
        llm.add_usage(usage["assistant_paid"], last["paid"])
        entry = {"role": "assistant", "output": last["output"], "tool_calls": last["tool_calls"], "error": last["error"],
                 "repairs": last.get("repairs", [])}
        if last["output"]:
            try:
                interview.card(last["output"]["criteria"])
                entry["valid_card"] = True
            except Exception as err:  # noqa: BLE001 - an invalid card is a finding, not a crash
                entry["valid_card"], entry["error"] = False, f"invalid card: {err}"
        log.append(entry)
        if not last["output"]:
            break
    cards = [t for t in log if t["role"] == "assistant" and t.get("output")]
    return {"chat_id": chat["chat_id"], "model": model, "prompt": version, "log": log,
            "final": cards[-1]["output"]["criteria"] if cards else None,
            "final_valid": bool(cards and cards[-1].get("valid_card")), "confirmed": confirmed, "usage": usage,
            "cost_usd": round(llm.cost_usd(model, usage["assistant"]) + llm.cost_usd(SIM_MODEL, usage["simulated_user"]), 4),
            "paid_usd": round(llm.cost_usd(model, usage["assistant_paid"]) + llm.cost_usd(SIM_MODEL, usage["simulated_user_paid"]), 4)}


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def _blank(value) -> bool:
    return value in (None, [], "")


def _same(a, b) -> bool:
    if isinstance(a, list) or isinstance(b, list):
        return sorted(map(str, a or [])) == sorted(map(str, b or []))
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        return abs(float(a) - float(b)) < 1e-6
    return a == b


def _outcome(expected, predicted) -> str | None:
    if _blank(expected) and _blank(predicted):
        return None
    if _blank(predicted):
        return "missed"
    if _blank(expected):
        return "invented"
    return "correct" if _same(expected, predicted) else "wrong"


def field_outcomes(expected: dict, predicted: dict) -> dict[str, str]:
    out = {"intent": "correct" if expected.get("intent") == predicted.get("intent") else
           ("missed" if predicted.get("intent") is None else "wrong")}
    areas = lambda a: frozenset(a) if a else frozenset(SEARCH_AREAS)  # noqa: E731 - empty means all
    out["areas"] = "correct" if areas(expected.get("areas")) == areas(predicted.get("areas")) else "wrong"
    for name in interview.HARD_FIELDS:
        result = _outcome((expected.get("hard_limits") or {}).get(name), (predicted.get("hard_limits") or {}).get(name))
        if result:
            out[name] = result
    soft_said, soft_caught = sorted(expected.get("ideally") or []), sorted(predicted.get("ideally") or [])
    if soft_said or soft_caught:  # "ιδανικά" before a size or bedroom count, scored on what the model caught (D56)
        out["ideally"] = _outcome(soft_said, soft_caught)
    said, caught = bool(expected.get("budget_around")), bool(predicted.get("budget_around"))
    if said or caught:  # "around" is scored on what the model caught; the 10% is code's (D53)
        out["budget_around"] = "correct" if said == caught else ("missed" if said else "invented")
    return out


def _bound(pref: dict):
    for key in ("min", "max", "equals"):
        if pref.get(key) is not None:
            return key, pref[key]
    return None, None


def _weight_class(weight: float) -> str:
    return "strong" if weight >= 0.7 else "weak" if weight < 0.4 else "middle"


def preference_outcomes(expected: dict, predicted: dict) -> list[dict]:
    exp_hard, pred_hard = expected.get("hard_limits") or {}, predicted.get("hard_limits") or {}
    preds = predicted.get("preferences") or []
    out, used = [], set()
    for e in expected.get("preferences") or []:
        same_feature = [i for i, p in enumerate(preds) if p["feature"] == e["feature"]]
        key, value = _bound(e)
        matches = [i for i in same_feature if _bound(preds[i])[0] == key and _same(_bound(preds[i])[1], value)]
        row = {"feature": e["feature"], "expected": [key, value]}
        if matches:
            p = preds[matches[0]]
            used.add(matches[0])
            row["result"] = "correct"
            wanted = _weight_class(e["weight"])
            row["weight"] = "unchecked" if wanted == "middle" else ("agrees" if _weight_class(p["weight"]) == wanted else "disagrees")
        elif same_feature:
            used.update(same_feature)
            row.update(result="wrong_bound", predicted=[_bound(preds[i]) for i in same_feature])
        elif any(COUNTERPART.get(n) == e["feature"] and not _blank(pred_hard.get(n)) and _blank(exp_hard.get(n)) for n in COUNTERPART):
            row["result"] = "split"  # wanted as a preference, made a hard limit
        else:
            row["result"] = "missed"
        out.append(row)
    for i, p in enumerate(preds):
        if i in used:
            continue
        hard_twin = [n for n, f in COUNTERPART.items() if f == p["feature"] and not _blank(exp_hard.get(n)) and _blank(pred_hard.get(n))]
        out.append({"feature": p["feature"], "predicted": list(_bound(p)), "result": "split" if hard_twin else "extra"})
    return out


NUMBER = re.compile(r"(\d[\d.,]*)\s*(k(?![a-zα-ω])|χιλ)?", re.I)  # "185k", "185 χιλ.", not "2,5 km"


def numbers_in(text: str) -> set[float]:
    """Numbers as a reader would take them: '185.000' and '185,000' are 185000, '€185k' is 185000, '2,5' is 2.5."""
    found = set()
    for digits, thousands in NUMBER.findall(text or ""):
        digits = digits.rstrip(".,")
        if re.fullmatch(r"\d{1,3}([.,]\d{3})+", digits):
            value = float(re.sub(r"[.,]", "", digits))
        else:
            value = float(digits.replace(",", ".")) if re.fullmatch(r"\d+([.,]\d+)?", digits) else None
        if value is None:
            continue
        found.add(value * 1000 if thousands else value)
    return found


def _tool_numbers(result: dict) -> set[float]:
    values = {result.get(k) for k in ("matches", "listings_in_areas", "median_price_eur", "median_price_per_m2", "median_size_m2")}
    values |= set((result.get("if_dropped") or {}).values())
    split = result.get("breakdown") or {}
    values |= set((split.get("by_bedrooms") or {}).values()) | set((split.get("by_size") or {}).values())
    values |= {split.get(k) for k in ("with_parking", "with_balcony", "with_lift")}
    for option in (result.get("if_eased") or {}).values():
        values.add(option.get("matches"))
        values |= {v for v in (option.get("limits") or {}).values() if isinstance(v, (int, float))}
    return {float(v) for v in values if isinstance(v, (int, float))}


def quotes_tool_number(reply: str, results: list[dict], user_numbers: set[float]) -> bool:
    tool = set().union(*(_tool_numbers(r) for r in results)) if results else set()
    said = numbers_in(reply) - user_numbers
    return any(abs(n - t) <= max(1.0, 0.01 * t) for n in said for t in tool)


def _asked(turn: dict) -> set[str]:
    out = turn.get("output") or {}
    has_question = "?" in out.get("reply", "") or ";" in out.get("reply", "") or ";" in out.get("reply", "")
    return set(out.get("asking_about") or []) if out.get("action") == "ask" and has_question else set()


# Basic facts a card needs. Asking for one counts, but so does the user giving it before the assistant
# got round to asking, as long as the card ends up right (Mike, D48). Clarifying questions ("is 200 the
# ceiling?") still have to be asked.
BASIC = {"intent": "intent", "budget": "max_price_eur", "areas": "areas", "bedrooms": "min_bedrooms"}


def volunteered(topic: str, expected: dict, final: dict) -> bool:
    name = BASIC.get(topic)
    if name is None:
        return False
    if name in ("intent", "areas"):
        return field_outcomes(expected, final)[name] == "correct" and not _blank(expected.get(name))
    return _outcome((expected.get("hard_limits") or {}).get(name), (final.get("hard_limits") or {}).get(name)) == "correct"


def behaviours(chat: dict, transcript: dict) -> dict[str, bool]:
    log = transcript["log"]
    replies = [t for t in log if t["role"] == "assistant" and t.get("output")]
    asked = set().union(*(_asked(t) for t in replies)) if replies else set()
    final = transcript["final"] or {}
    if "which_covered_area" in asked:  # "which of our three areas?" asks for the areas either way (D57)
        asked = asked | {"areas"}
    if "purpose" in asked:  # choosing "investment" in answer to the purpose question is choosing investor mode (D54)
        asked = asked | {"confirm_investor_mode"}
    if any(t["output"]["action"] == "confirm" and t["output"]["criteria"].get("intent") == "invest" for t in replies):
        asked = asked | {"confirm_investor_mode"}  # the spec: investor mode is confirmed on the criteria card (D56)
    out = {f"ask:{topic}": topic in asked or volunteered(topic, chat["expected_criteria"], final) for topic in chat["must_ask"]}
    user_numbers = set().union(*(numbers_in(t["text"]) for t in log if t["role"] == "user")) if log else set()
    for item in chat["must_say"]:
        kind, _, arg = item.partition(":")
        if kind == "reply_in":
            pairs = [(log[i - 1]["language"], language(t["output"]["reply"])) for i, t in enumerate(log)
                     if t["role"] == "assistant" and t.get("output")]
            out[item] = bool(pairs) and all(a == b for a, b in pairs)
        elif kind == "area_not_covered":
            aliases = AREA_ALIASES.get(arg, (arg.lower(),))
            named = any(any(a in t["output"]["reply"].lower() for a in aliases) for t in replies)
            flagged = any(any(any(a in x.lower() for a in aliases) for x in t["output"]["not_covered_areas"]) for t in replies)
            out[item] = named and flagged
        elif item == "tradeoff_with_numbers":
            results = [c["result"] for t in replies for c in t.get("tool_calls") or []]
            out[item] = any(quotes_tool_number(t["output"]["reply"], results, user_numbers) for t in replies)
        elif item in ("no_mortgage_advice", "no_investment_advice"):
            topic = item.split("_")[1]
            out[item] = any(topic in t["output"]["declined_advice"] and PROFESSIONAL.search(t["output"]["reply"])
                            for t in replies) if topic == "mortgage" else any(topic in t["output"]["declined_advice"] for t in replies)
        elif item == "rent_not_supported":  # said so, and never confirmed a rental card (D54)
            said = any("rent" in (t["output"].get("unsupported") or []) for t in replies)
            confirmed_rent = any(t["output"]["action"] == "confirm" and t["output"]["criteria"].get("intent") == "rent" for t in replies)
            out[item] = said and not confirmed_rent
        elif item == "confirm_change":
            # The first card shown after the change has to show it; a question in between is fine (D57).
            last_script = max(i for i, t in enumerate(log) if t["role"] == "user" and t["source"] == "script")
            after = next((t for t in log[last_script + 1:] if t["role"] == "assistant" and t.get("output")
                          and t["output"]["action"] == "confirm"), None)
            new_price = (final.get("hard_limits") or {}).get("max_price_eur")
            out[item] = bool(after and new_price
                             and quotes_tool_number(after["output"]["reply"], [{"matches": new_price}], set()))
        else:
            out[item] = False  # an unknown check fails loudly in the report
    for name in chat["must_not_invent"]:
        if name in interview.HARD_FIELDS:
            out[f"not_invented:{name}"] = _blank((final.get("hard_limits") or {}).get(name))
        elif name == "max_price_eur_from_payment":
            first = replies[0]["output"]["criteria"] if replies else {}
            out[f"not_invented:{name}"] = _blank((first.get("hard_limits") or {}).get("max_price_eur"))
        # other names ("brightness", "condition") have no field to invent: the schema already prevents it
    return out


def _looser(name: str, before, after) -> bool:
    """Did this hard limit get looser from one card to the next? Removing a limit counts."""
    if name == "budget_around":
        return not before and bool(after)  # "around" widens the price by 10% (D53)
    if name == "ideally":
        return bool(set(after or []) - set(before or []))  # "ideally" widens a size or bedroom count (D56)
    if name == "areas":
        return bool(before) and (not after or bool(set(after) - set(before)))
    if _blank(before):
        return False
    if _blank(after):
        return True
    if name in ("max_price_eur", "max_size_m2", "max_bedrooms"):
        return after > before
    if name in ("min_price_eur", "min_size_m2", "min_bedrooms"):
        return after < before
    if name == "property_types":
        return bool(set(after) - set(before))
    if name == "exclude_floors":
        return bool(set(before) - set(after))  # a floor no longer ruled out
    raise ValueError(f"no loosening rule for {name}")  # a new limit must say what looser means


def unasked_loosenings(log: list[dict]) -> list[str]:
    """Hard limits loosened when the user's last message wasn't their own words (D50).

    A scripted turn is the user speaking, so a change it asks for is theirs. A fixed
    "yes, go ahead" or a simulated answer from facts never asks to loosen a limit in
    these chats, so a limit loosened after one was the assistant's own doing.
    """
    found, previous, last_user = [], None, None
    for entry in log:
        if entry["role"] == "user":
            last_user = entry
            continue
        if not entry.get("output"):
            continue
        current = entry["output"]["criteria"]
        if previous is not None and last_user and last_user["source"] != "script":
            for name in ("areas", "budget_around", "ideally", *interview.HARD_FIELDS):
                top = name in ("areas", "budget_around", "ideally")
                old = previous.get(name) if top else (previous.get("hard_limits") or {}).get(name)
                new = current.get(name) if top else (current.get("hard_limits") or {}).get(name)
                if _looser(name, old, new):
                    found.append(name)
        previous = current
    return found


def easing(transcript: dict) -> dict:
    """In a thin search (fewer than 5, not a data gap), did a reply suggest one eased limit with code's numbers?"""
    replies = [t for t in transcript["log"] if t["role"] == "assistant" and t.get("output")]
    results = [c["result"] for t in replies for c in t.get("tool_calls") or []]
    thin = [r for r in results if r.get("matches", THIN_DEFAULT) < interview.THIN and r.get("if_eased")]
    suggested = any("ease_limit" in _asked(t) and quotes_tool_number(t["output"]["reply"], thin, set()) for t in replies)
    return {"thin": bool(thin), "suggested": bool(thin) and suggested}


THIN_DEFAULT = 10 ** 9


def card_matches(replies: list[dict]) -> int:
    """How many listings the card's own check found: the last check before the first card shown for confirmation."""
    last = 0
    for reply in replies:
        for call in reply.get("tool_calls") or []:
            last = call["result"].get("matches", last)
        if reply["output"]["action"] == "confirm":
            break
    return last


def score_chat(chat: dict, transcript: dict) -> dict:
    predicted = transcript["final"] or {"intent": None, "areas": [], "hard_limits": {}, "preferences": []}
    expected = chat["expected_criteria"]
    unsupported = expected.get("intent") == "rent"  # no rental search yet (D54): behaviours only, no card to score
    replies = [t for t in transcript["log"] if t["role"] == "assistant" and t.get("output")]
    return {
        "chat_id": chat["chat_id"], "language": chat["language"], "tests": chat["tests"],
        "fields": {} if unsupported else field_outcomes(expected, predicted),
        "preferences": [] if unsupported else preference_outcomes(expected, predicted),
        "behaviours": behaviours(chat, transcript), "confirmed": transcript["confirmed"], "unsupported": unsupported,
        "valid_card": transcript["final_valid"], "assistant_replies": len(replies),
        "questions": sum(len(_asked(t)) for t in replies),
        "tool_calls": sum(len(t.get("tool_calls") or []) for t in replies),
        "repairs": sum(len(t.get("repairs") or []) for t in replies),
        # D49: was the search wide, and did it ask the one narrowing question? Wide means the last check before the
        # first card shown over 50; a probe with no limits (all 484 listings) isn't the card's count (D55).
        "wide": card_matches(replies) > interview.WIDE,
        "narrowing_asked": any("narrowing" in _asked(t) for t in replies),
        "easing": easing(transcript), "unasked_loosenings": unasked_loosenings(transcript["log"]),
        "cost_usd": transcript["cost_usd"],
    }


def summarise(scores: list[dict]) -> dict:
    fields = [o for s in scores for o in s["fields"].values()]
    prefs = [p for s in scores for p in s["preferences"]]
    expected_prefs = [p for p in prefs if "expected" in p]
    checks = [(k, v) for s in scores for k, v in s["behaviours"].items()]
    weights = [p["weight"] for p in expected_prefs if p.get("weight") in ("agrees", "disagrees")]
    by_kind: dict[str, list[bool]] = {}
    for key, passed in checks:
        kind = key.split(":")[0] if key.startswith(("ask:", "not_invented:", "reply_in:", "area_not_covered:")) else key
        by_kind.setdefault(kind, []).append(passed)
    return {
        "chats": len(scores),
        "field_accuracy": round(sum(o == "correct" for o in fields) / len(fields), 4) if fields else None,
        "fields": {k: sum(o == k for o in fields) for k in ("correct", "wrong", "missed", "invented")},
        "invented_hard_limits": sum(o == "invented" for s in scores for n, o in s["fields"].items() if n in interview.HARD_FIELDS),
        "preferences": {"expected": len(expected_prefs),
                        **{k: sum(p["result"] == k for p in prefs) for k in ("correct", "wrong_bound", "missed", "split", "extra")}},
        "weights_agree": f"{weights.count('agrees')} of {len(weights)}",
        "behaviours": {k: f"{sum(v)} of {len(v)}" for k, v in sorted(by_kind.items())},
        "behaviour_pass_rate": round(sum(p for _, p in checks) / len(checks), 4) if checks else None,
        "confirmed": sum(s["confirmed"] for s in scores), "valid_cards": sum(s["valid_card"] for s in scores),
        "mean_questions": round(sum(s["questions"] for s in scores) / len(scores), 2),
        "mean_replies": round(sum(s["assistant_replies"] for s in scores) / len(scores), 2),
        "tool_calls": sum(s["tool_calls"] for s in scores),
        "card_repairs": sum(s.get("repairs", 0) for s in scores),
        "narrowing": {"wide_chats": sum(s["wide"] for s in scores),
                      "asked_when_wide": sum(s["wide"] and s["narrowing_asked"] for s in scores),
                      "asked_when_not_wide": sum(not s["wide"] and s["narrowing_asked"] for s in scores)},
        "easing": {"thin_chats": sum(s["easing"]["thin"] for s in scores),
                   "suggested_with_numbers": sum(s["easing"]["suggested"] for s in scores)},
        "unasked_loosenings": sum(len(s["unasked_loosenings"]) for s in scores),
        "cost_usd": round(sum(s["cost_usd"] for s in scores), 4),
        "mean_cost_per_chat_usd": round(sum(s["cost_usd"] for s in scores) / len(scores), 4),
    }


def report(summary: dict, scores: list[dict], name: str) -> str:
    lines = [f"Interview eval: {name} ({summary['chats']} chats)",
             f"  fields      {summary['field_accuracy']:.1%}  (target 95%)  {summary['fields']}",
             f"  invented hard limits {summary['invented_hard_limits']} (target 0)",
             f"  preferences {summary['preferences']}, weights agree {summary['weights_agree']}",
             f"  behaviours  {summary['behaviour_pass_rate']:.1%}  {summary['behaviours']}",
             f"  confirmed {summary['confirmed']}, valid cards {summary['valid_cards']}, "
             f"questions per chat {summary['mean_questions']}, replies {summary['mean_replies']}, tool calls {summary['tool_calls']}, "
             f"cards repaired {summary['card_repairs']}",
             f"  narrowing {summary['narrowing']}, easing {summary['easing']}, "
             f"unasked loosenings {summary['unasked_loosenings']} (target 0)",
             f"  cost ${summary['cost_usd']:.3f} (${summary['mean_cost_per_chat_usd']:.4f} a chat)", "", "  misses:"]
    for s in scores:
        bad = [f"{k}={v}" for k, v in s["fields"].items() if v != "correct"]
        bad += [f"pref {p['feature']} {p['result']}" for p in s["preferences"] if p["result"] != "correct"]
        bad += [f"weight {p['feature']}" for p in s["preferences"] if p.get("weight") == "disagrees"]
        bad += [k for k, v in s["behaviours"].items() if not v]
        if not s["confirmed"] and not s.get("unsupported"):
            bad.append("not confirmed")
        bad += [f"loosened {name} unasked" for name in s.get("unasked_loosenings", [])]
        if s.get("easing", {}).get("thin") and not s["easing"]["suggested"]:
            bad.append("thin, no easing suggested")
        if bad:
            lines.append(f"    {s['chat_id']}: {', '.join(bad)}")
    return "\n".join(lines)


def load_chats(path: Path = CHATS) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def run(only: list[str] | None = None, limit: int | None = None, model: str = interview.MODEL,
        version: str = interview.PROMPT_VERSION, client=None, listings: list | None = None, write: bool = True,
        workers: int = 4, chats_path: Path = CHATS, set_name: str | None = None) -> dict:
    chats = [c for c in load_chats(chats_path) if not only or c["chat_id"] in only][:limit]
    listings = listings if listings is not None else SnapshotAdapter(SNAPSHOT).listings()
    client = client or llm.client()
    def one(chat):
        try:
            return simulate(chat, client, listings, model, version)
        except Exception as err:  # noqa: BLE001 - one broken chat is a finding, not the end of the run
            return {"chat_id": chat["chat_id"], "model": model, "prompt": version, "log": [], "final": None,
                    "final_valid": False, "confirmed": False, "usage": {}, "cost_usd": 0.0, "paid_usd": 0.0,
                    "error": f"{type(err).__name__}: {err}"}

    with ThreadPoolExecutor(max_workers=workers) as pool:
        transcripts = list(pool.map(one, chats))
    for t in transcripts:
        if t.get("error"):
            print(f"  {t['chat_id']} failed: {t['error']}")
    scores = [score_chat(c, t) for c, t in zip(chats, transcripts)]
    summary = summarise(scores)
    name = (f"{set_name}-" if set_name else "") + f"{version}-{model.replace('claude-', '')}" + ("" if not (only or limit) else "-partial")
    print(report(summary, scores, name))
    print(f"  paid this run ${sum(t['paid_usd'] for t in transcripts):.3f}")
    if write:
        PRIVATE.mkdir(parents=True, exist_ok=True)
        with (PRIVATE / f"transcripts-{name}.jsonl").open("w", encoding="utf-8") as fh:
            for t in transcripts:
                fh.write(json.dumps(t, ensure_ascii=False) + "\n")
        RESULTS.mkdir(parents=True, exist_ok=True)
        (RESULTS / f"v1-interview-{name}.json").write_text(json.dumps({
            "eval": "interview", "name": name, "ran_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "model": model, "prompt": version, "simulated_user": SIM_MODEL, "targets": TARGETS,
            "summary": summary, "chats": scores,
            "data": "40 scripted chats (synthetic); supply counts from the private snapshot, totals only",
        }, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"summary": summary, "scores": scores, "transcripts": transcripts}


def rescore(name: str, chats_path: Path = CHATS) -> dict:
    """Score saved transcripts against the current labels and rules. No calls."""
    chats = {c["chat_id"]: c for c in load_chats(chats_path)}
    transcripts = [json.loads(line) for line in (PRIVATE / f"transcripts-{name}.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    scores = [score_chat(chats[t["chat_id"]], t) for t in transcripts]
    summary = summarise(scores)
    print(report(summary, scores, f"{name}, rescored"))
    path = RESULTS / f"v1-interview-{name}.json"
    if path.exists():  # keep the run's record, with the scores against the labels as they stand now
        record = json.loads(path.read_text(encoding="utf-8"))
        record.update(summary=summary, chats=scores, rescored_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
        path.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"summary": summary, "scores": scores}


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--rescore" in args:
        rescore(args[args.index("--rescore") + 1], Path(args[args.index("--chats") + 1]) if "--chats" in args else CHATS)
        sys.exit(0)
    only = args[args.index("--only") + 1].split(",") if "--only" in args else None
    limit = int(args[args.index("--limit") + 1]) if "--limit" in args else None
    run(only=only, limit=limit)
