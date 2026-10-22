"""The interview: a chat that ends in a criteria card (spec sections 7 and 9).

Sonnet 5.5 runs the conversation. Each reply is structured output: the text
the user sees, whether it asks or asks to confirm, tags for what it asks, and
the card as it stands. Code reads the card, so it's checked with the same
Pydantic models the search uses (core/models.py); a card that fails them is
an error, never a search.

The model has one tool, check_supply. Code counts how many snapshot listings
pass the card's hard limits and how many would pass with each limit dropped,
so when asks conflict the model explains the trade-off with numbers that code
calculated, not numbers it guessed (D46).

Every call is cached by a hash of its request, like the extraction calls, so a
rerun with the same prompt replays the same chats for free.
"""

from __future__ import annotations

import hashlib
import json
import statistics
from collections import Counter
from datetime import date
from pathlib import Path
from typing import get_args

from agent import llm
from core.filters import INTENT_TO_LISTING_TYPE, apply_hard_limits
from core.greek import SPECIAL_FLOORS
from core.card_rules import IDEALLY, search_card  # Mike's price, size and bedroom rules, in code (D53, D56)
from core.models import SEARCH_AREAS, Criteria, HardLimits, Intent, PreferenceFeature, PropertyType

ROOT = Path(__file__).resolve().parents[1]
PROMPTS = ROOT / "prompts"
PROMPT_VERSION = "interview_v7"
MODEL = "claude-sonnet-5-5"
MAX_TOKENS = 2000
MAX_TOOL_CALLS = 3  # per reply; then the model has to answer (spec section 7)
MAX_REPAIRS = 1  # a card that fails the checks goes back to the model once, with the reason (D47)
NEW_BUILD_YEARS = 5  # "new build" means built in the last five years
RENOVATED_YEARS = 10  # "renovated" with no year means renovated in the last ten years (Mike, D54)

TOPICS = ("intent", "budget", "budget_ceiling", "total_budget", "budget_includes_costs", "areas", "which_covered_area",
          "confirm_area", "bedrooms", "rooms_meaning", "size", "property_type", "floor", "stairs_requirement",
          "year_built", "renovation", "metro_minutes", "energy_class", "parking", "balcony", "confirm_investor_mode",
          "priorities", "narrowing", "ease_limit", "purpose", "other")
UNSUPPORTED = ("rent",)  # rentals come later (Mike, D54)
WIDE = 50  # more matches than this: one optional narrowing question (Mike, D49)
THIN = 5  # fewer matches than this: suggest easing one limit a little, and ask (Mike, D50)
EASE = 0.10  # "a little": price up or size down by 10%, one bedroom fewer, one more covered area
WIDER_TYPES = {"apartment": ("maisonette", "loft")}  # types to offer when an apartment search is thin (Mike, D53)
ADVICE = ("mortgage", "investment", "legal")
FLOORS = SPECIAL_FLOORS + ("1", "2", "3")
HARD_FIELDS = ("max_price_eur", "min_price_eur", "min_size_m2", "max_size_m2", "min_bedrooms", "max_bedrooms", "property_types",
               "exclude_floors")


def _nullable(kind: str) -> dict:
    return {"type": [kind, "null"]}


def _hard_limits_schema() -> dict:
    return {
        "type": "object", "additionalProperties": False, "required": list(HARD_FIELDS),
        "properties": {
            "max_price_eur": _nullable("integer"), "min_price_eur": _nullable("integer"),
            "min_size_m2": _nullable("number"), "max_size_m2": _nullable("number"),
            "min_bedrooms": _nullable("integer"), "max_bedrooms": _nullable("integer"),
            "property_types": {"type": "array", "items": {"type": "string", "enum": list(get_args(PropertyType))}},
            "exclude_floors": {"type": "array", "items": {"type": "string", "enum": list(FLOORS)}},
        },
    }


def _criteria_core() -> dict:
    return {
        "intent": {"enum": [*get_args(Intent), None]},  # the same nullable enum form as extraction
        "areas": {"type": "array", "items": {"type": "string", "enum": list(SEARCH_AREAS)}},
        "hard_limits": _hard_limits_schema(),
        "budget_around": {"type": "boolean"},  # the user said "around" their top price; code adds the margin (D53)
        "ideally": {"type": "array", "items": {"type": "string", "enum": list(IDEALLY)}},  # code adds the margins (D56)
    }


def schema() -> dict:
    """The reply format. Reasoning first, then the reply, then the card (the model writes in this order)."""
    bound = {"anyOf": [{"type": "number"}, {"type": "string"}, {"type": "null"}]}
    preference = {
        "type": "object", "additionalProperties": False, "required": ["feature", "min", "max", "equals", "weight"],
        "properties": {"feature": {"type": "string", "enum": list(get_args(PreferenceFeature))},
                       "min": bound, "max": bound, "equals": {"enum": [True, False, None]}, "weight": {"type": "number"}},
    }
    criteria = {
        "type": "object", "additionalProperties": False,
        "required": ["intent", "areas", "hard_limits", "budget_around", "ideally", "preferences", "open_questions"],
        "properties": {**_criteria_core(), "preferences": {"type": "array", "items": preference},
                       "open_questions": {"type": "array", "items": {"type": "string"}}},
    }
    properties = {
        "reasoning": {"type": "string"},
        "reply": {"type": "string"},
        "action": {"type": "string", "enum": ["ask", "confirm"]},
        "asking_about": {"type": "array", "items": {"type": "string", "enum": list(TOPICS)}},
        "not_covered_areas": {"type": "array", "items": {"type": "string"}},
        "declined_advice": {"type": "array", "items": {"type": "string", "enum": list(ADVICE)}},
        "unsupported": {"type": "array", "items": {"type": "string", "enum": list(UNSUPPORTED)}},
        "criteria": criteria,
    }
    return {"type": "object", "additionalProperties": False, "required": list(properties), "properties": properties}


TOOL = {
    "name": "check_supply",
    "description": ("Count the listings in the snapshot that pass these hard limits, and how many would pass if each "
                    "limit were dropped. Code does the counting. Use it before showing a card whose asks may be hard "
                    "to meet together."),
    "input_schema": {"type": "object", "additionalProperties": False,
                     "required": ["intent", "areas", "hard_limits", "budget_around", "ideally"],
                     "properties": _criteria_core()},
}


def system_prompt(version: str = PROMPT_VERSION, today: str | None = None) -> str:
    day = date.fromisoformat(today) if today else date.today()
    text = (PROMPTS / f"{version}.md").read_text(encoding="utf-8")
    text = (text.replace("{{today}}", day.isoformat())
                .replace("{{areas}}", "Egaleo (Αιγάλεω), Peristeri (Περιστέρι) and Chaidari (Χαϊδάρι)")
                .replace("{{new_build_from}}", str(day.year - NEW_BUILD_YEARS))
                .replace("{{renovated_from}}", str(day.year - RENOVATED_YEARS)))
    if "{{" in text:
        raise ValueError("a placeholder in the prompt wasn't filled")
    return text


def request(messages: list[dict], today: str, model: str = MODEL, version: str = PROMPT_VERSION) -> dict:
    return {
        "model": model, "max_tokens": MAX_TOKENS,
        "system": [{"type": "text", "text": system_prompt(version, today), "cache_control": {"type": "ephemeral"}}],
        "tools": [TOOL],
        "messages": list(messages),  # a copy: the history grows after the call
        "output_config": {"format": {"type": "json_schema", "schema": schema()}},
    }


def _blank(value) -> bool:
    return value in (None, [], "")


def card(raw: dict) -> Criteria:
    """The card the search runs on, as a Criteria. Raises if it breaks the rules the search relies on."""
    raw = search_card(raw)
    limits = {k: v for k, v in (raw.get("hard_limits") or {}).items() if not _blank(v)}
    preferences = [{k: v for k, v in p.items() if v is not None} for p in raw.get("preferences") or []]
    return Criteria(user_id="interview", intent=raw.get("intent") or "buy", areas=raw.get("areas") or [],
                    hard_limits=HardLimits(**limits), preferences=preferences,
                    open_questions=raw.get("open_questions") or [])


def check_supply(args: dict, listings: list) -> dict:
    """What code tells the model about supply. Counts and medians only, no listings."""
    try:
        criteria = card({**args, "preferences": [], "open_questions": []})
    except Exception as err:  # noqa: BLE001 - the model gets the reason back
        return {"error": f"invalid criteria: {err}"}
    matches = apply_hard_limits(listings, criteria).matches
    if_dropped = {}
    for name in HARD_FIELDS:
        if not _blank(getattr(criteria.hard_limits, name)):
            looser = criteria.model_copy(update={"hard_limits": criteria.hard_limits.model_copy(
                update={name: [] if name in ("property_types", "exclude_floors") else None})})
            if_dropped[name] = len(apply_hard_limits(listings, looser).matches)
    kind = INTENT_TO_LISTING_TYPE[criteria.intent]
    in_areas = [l for l in listings if l.listing_type == kind and (not criteria.areas or l.area in criteria.areas)]
    prices = [l.price_eur for l in in_areas if l.price_eur]
    per_m2 = [l.price_per_m2 for l in in_areas if l.price_per_m2]
    sizes = [l.size_m2 for l in in_areas if l.size_m2]
    result = {
        "search_limits": {"min_price_eur": criteria.hard_limits.min_price_eur, "max_price_eur": criteria.hard_limits.max_price_eur},
        "matches": len(matches), "if_dropped": if_dropped, "listings_in_areas": len(in_areas),
        "median_price_eur": round(statistics.median(prices)) if prices else None,
        "median_price_per_m2": round(statistics.median(per_m2)) if per_m2 else None,
        "median_size_m2": round(statistics.median(sizes)) if sizes else None,
    }
    if len(matches) > WIDE:
        result["breakdown"] = breakdown(matches)
    of_kind = sum(1 for l in listings if l.listing_type == kind)
    if len(matches) < THIN and of_kind:
        result["if_eased"] = eased(criteria, listings)
    if not in_areas:
        result["note"] = (f"The snapshot has no {'rental' if kind == 'rent' else 'sale'} listings in these areas yet. "
                          "That's a gap in the data, not in the user's criteria.")
    if not of_kind:
        result["note"] += " Easing a limit won't help."
    return result


def eased(criteria: Criteria, listings: list) -> dict:
    """Each hard limit eased a little, one at a time, with the count it would give. Code picks the steps (D50)."""
    limits, out = criteria.hard_limits, {}
    rent = criteria.intent == "rent"
    step = 50 if rent else 5000

    def count(**update) -> int:
        looser = criteria.model_copy(update={"hard_limits": limits.model_copy(update=update)}) if update else criteria
        return len(apply_hard_limits(listings, looser).matches)

    if limits.max_price_eur:
        to = max(limits.max_price_eur + step, round(limits.max_price_eur * (1 + EASE) / step) * step)
        out["max_price_eur"] = {"to": to, "matches": count(max_price_eur=to)}
    if limits.min_size_m2:
        to = min(limits.min_size_m2 - 1, round(limits.min_size_m2 * (1 - EASE)))
        out["min_size_m2"] = {"to": to, "matches": count(min_size_m2=to)}
    if limits.max_size_m2:
        to = max(limits.max_size_m2 + 1, round(limits.max_size_m2 * (1 + EASE)))
        out["max_size_m2"] = {"to": to, "matches": count(max_size_m2=to)}
    if limits.min_bedrooms:
        out["min_bedrooms"] = {"to": limits.min_bedrooms - 1, "matches": count(min_bedrooms=limits.min_bedrooms - 1)}
    for kind, wider in WIDER_TYPES.items():
        if kind in limits.property_types:
            for extra in (t for t in wider if t not in limits.property_types):
                out[f"add_type:{extra}"] = {"to": extra, "matches": count(property_types=[*limits.property_types, extra])}
    if criteria.areas:
        for area in (a for a in SEARCH_AREAS if a not in criteria.areas):
            wider = criteria.model_copy(update={"areas": [*criteria.areas, area]})
            out[f"add_area:{area}"] = {"to": area, "matches": len(apply_hard_limits(listings, wider).matches)}
    return out


def breakdown(matches: list) -> dict:
    """How the matches split, so a narrowing question can use real numbers. Code counts; unknowns are counted too."""
    def band(value, edges, labels):
        if value is None:
            return "unknown"
        return next((label for edge, label in zip(edges, labels) if value < edge), labels[-1])

    bedrooms, sizes = Counter(), Counter()
    for listing in matches:
        bedrooms[band(listing.bedrooms, (2, 3), ("0 to 1", "2", "3 or more"))] += 1
        sizes[band(listing.size_m2, (60, 90), ("under 60 m2", "60 to 89 m2", "90 m2 or more"))] += 1
    return {
        "by_bedrooms": dict(bedrooms), "by_size": dict(sizes),
        "with_parking": sum(1 for l in matches if l.parking in ("pilotis", "space", "garage")),
        "with_balcony": sum(1 for l in matches if l.balcony is True),
        "with_lift": sum(1 for l in matches if l.lift is True),
    }


def cache_key(body: dict) -> str:
    return hashlib.sha256(json.dumps(body, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _blocks(content) -> list[dict]:
    """Response content as the plain blocks the API accepts back in the history."""
    out = []
    for block in content:
        kind = block["type"] if isinstance(block, dict) else block.type
        get = (lambda k: block[k]) if isinstance(block, dict) else (lambda k: getattr(block, k))
        if kind == "text":
            out.append({"type": "text", "text": get("text")})
        elif kind == "tool_use":
            out.append({"type": "tool_use", "id": get("id"), "name": get("name"), "input": get("input")})
    return out


def call(client, body: dict, cache_dir: Path | None) -> dict:
    """One API call, from the cache when this exact request was made before."""
    key = cache_key(body)
    path = cache_dir / f"{key}.json" if cache_dir else None
    if path and path.exists():
        return dict(json.loads(path.read_text(encoding="utf-8")), cached=True)
    response = client.messages.create(**body)
    saved = {"content": _blocks(response.content), "stop_reason": response.stop_reason,
             "usage": llm.usage_dict(response.usage)}
    if path and response.stop_reason != "max_tokens":  # a cut-off answer isn't kept, so a retry can pay to fix it
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(saved, ensure_ascii=False, indent=1), encoding="utf-8")
    return dict(saved, cached=False)


def reply(client, messages: list[dict], listings: list, today: str, model: str = MODEL,
          version: str = PROMPT_VERSION, cache_dir: Path | None = None) -> dict:
    """The assistant's next reply: tool calls if it wants them, then the structured answer.

    Returns the parsed output, the messages to append to the history, the tool
    calls with their results, and the usage (all calls, and only the paid ones).
    """
    history, added, tools_used, repairs = list(messages), [], [], []
    usage, paid = {}, {}
    for _ in range(MAX_TOOL_CALLS + MAX_REPAIRS + 1):
        body = request(history, today, model, version)
        if len(tools_used) >= MAX_TOOL_CALLS:
            body = dict(body, tool_choice={"type": "none"})
        response = call(client, body, cache_dir)
        llm.add_usage(usage, response["usage"])
        if not response["cached"]:
            llm.add_usage(paid, response["usage"])
        assistant = {"role": "assistant", "content": response["content"]}
        history.append(assistant)
        added.append(assistant)
        uses = [b for b in response["content"] if b["type"] == "tool_use"]
        if response["stop_reason"] == "tool_use" and uses:
            results = []
            for use in uses:
                outcome = check_supply(use["input"], listings) if use["name"] == "check_supply" else {"error": "unknown tool"}
                tools_used.append({"input": use["input"], "result": outcome})
                results.append({"type": "tool_result", "tool_use_id": use["id"], "content": json.dumps(outcome)})
            history.append({"role": "user", "content": results})
            added.append(history[-1])
            continue
        text = "".join(b["text"] for b in response["content"] if b["type"] == "text")
        out = {"added": added, "tool_calls": tools_used, "usage": usage, "paid": paid, "repairs": repairs,
               "stop_reason": response["stop_reason"], "output": None, "error": None}
        try:
            out["output"] = json.loads(text)
        except json.JSONDecodeError:
            out["error"] = f"no JSON answer (stop reason {response['stop_reason']})"
            return out
        problem = card_problem(out["output"]["criteria"], out["output"].get("action"))
        if problem and len(repairs) < MAX_REPAIRS:
            repairs.append(problem)
            history.append({"role": "user", "content": repair_message(problem)})
            added.append(history[-1])
            continue
        return out
    raise RuntimeError("unreachable: the last round runs with tools switched off")


def card_problem(raw: dict, action: str | None = None) -> str | None:
    """Why the search couldn't run on this card, or None if it can."""
    if action == "confirm" and raw.get("intent") in UNSUPPORTED:
        return "rentals aren't supported yet: say so and don't confirm a rental card (D54)"
    if action == "confirm" and not (raw.get("hard_limits") or {}).get("max_price_eur"):
        return "a card shown for confirmation needs a top price (max_price_eur): use the user's, or ask for it"  # D53
    try:
        card(raw)
    except Exception as err:  # noqa: BLE001 - the reason goes back to the model
        return str(err).split("\n    For further information")[0]
    return None


def repair_message(problem: str) -> str:
    return (f"<code_check>The card failed the search's checks: {problem}. Answer again with the card fixed. "
            "This message comes from code, not from the user: don't mention it in your reply.</code_check>")
