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
from core.card_rules import IDEALLY, harden, search_card  # Mike's rules, in code (D53, D56, D79)
from core import greek
from core.models import Condition, Criteria, HardLimits, Intent, PreferenceFeature, PropertyType, covered_areas

ROOT = Path(__file__).resolve().parents[1]
PROMPTS = ROOT / "prompts"
PROMPT_VERSION = "interview_v12"  # D86
MODEL = "claude-sonnet-5-5"
MAX_TOKENS = 2000
MAX_TOOL_CALLS = 3  # per reply; then the model has to answer (spec section 7)
MAX_REPAIRS = 1  # a card that fails the checks goes back to the model once, with the reason (D47)
NEW_BUILD_YEARS = 5  # "new build" means built in the last five years
RENOVATED_YEARS = 5  # "renovated" with no year means renovated, or built, in the last five years (Mike, D79)
LEGACY_RENOVATED_YEARS = 10  # what prompts before v10 said (D54), kept so they still render as they ran

TOPICS = ("intent", "budget", "budget_ceiling", "total_budget", "budget_includes_costs", "areas", "which_covered_area",
          "confirm_area", "bedrooms", "rooms_meaning", "size", "property_type", "floor", "stairs_requirement",
          "year_built", "renovation", "metro_minutes", "energy_class", "parking", "balcony", "confirm_investor_mode",
          "priorities", "narrowing", "ease_limit", "purpose", "suggest_change", "bathrooms", "make_limit", "other")
UNSUPPORTED = ("rent",)  # rentals come later (Mike, D54)
WIDE = 50  # more matches than this: one optional narrowing question (Mike, D49)
THIN = 5  # fewer matches than this: suggest easing one limit a little, and ask (Mike, D50)
EASE = 0.10  # "a little": price up or size down by 10%, one bedroom fewer, one more covered area
YEAR_STEP = 5  # easing a year-built limit: five years earlier
WIDER_TYPES = {"apartment": ("maisonette", "loft")}  # types to offer when an apartment search is thin (Mike, D53)
ADVICE = ("mortgage", "investment", "legal")
FLOORS = SPECIAL_FLOORS + ("1", "2", "3")
HARD_FIELDS = ("max_price_eur", "min_price_eur", "min_size_m2", "max_size_m2", "min_bedrooms", "max_bedrooms", "property_types",
               "exclude_floors", "min_year_built", "max_price_per_m2", "max_floor_without_lift", "exclude_conditions",
               "must_have", "min_bathrooms", "min_renovated_year", "min_floor_level", "max_floor_level", "max_metro_walk_min",
               "must_have_if_type")
LIST_FIELDS = ("property_types", "exclude_floors", "exclude_conditions", "must_have")
FROM_WISHES = ("must_have", "min_bathrooms", "min_renovated_year", "min_floor_level", "max_floor_level",
               "must_have_if_type")  # code writes these from firm wishes (D79, D86)
MODEL_FIELDS = tuple(f for f in HARD_FIELDS if f not in FROM_WISHES)  # the hard limits the model writes itself
METRO_STEP = 5  # easing a metro limit: five more minutes on foot
# A firm wish that stays a wish (D79) and the hard limit it would become if the user takes the offer
OFFERS = {"move_in_ready": "exclude_conditions", "metro_walk_min": "max_metro_walk_min"}


def _nullable(kind: str) -> dict:
    return {"type": [kind, "null"]}


def _hard_limits_schema() -> dict:
    return {
        "type": "object", "additionalProperties": False, "required": list(MODEL_FIELDS),
        "properties": {
            "max_price_eur": _nullable("integer"), "min_price_eur": _nullable("integer"),
            "min_size_m2": _nullable("number"), "max_size_m2": _nullable("number"),
            "min_bedrooms": _nullable("integer"), "max_bedrooms": _nullable("integer"),
            "min_year_built": _nullable("integer"),  # from a check-in the user accepted (D66)
            "property_types": {"type": "array", "items": {"type": "string", "enum": list(get_args(PropertyType))}},
            "exclude_floors": {"type": "array", "items": {"type": "string", "enum": list(FLOORS)}},
            "max_price_per_m2": _nullable("integer"),  # D73
            "max_floor_without_lift": _nullable("integer"),  # D73
            "exclude_conditions": {"type": "array", "items": {"type": "string", "enum": list(get_args(Condition))}},
            # D79: must_have, min_bathrooms, min_renovated_year and the floor levels come from firm wishes, worked out by
            # code (core/card_rules.py), so the model never writes them. Only a metro limit the user accepts is its own.
            "max_metro_walk_min": _nullable("integer"),
        },
    }


def _preference_schema() -> dict:
    bound = {"anyOf": [{"type": "number"}, {"type": "string"}, {"type": "null"}]}
    return {
        "type": "object", "additionalProperties": False,
        "required": ["feature", "min", "max", "equals", "weight", "firm", "said", "only_for_types"],
        "properties": {"feature": {"type": "string", "enum": list(get_args(PreferenceFeature))},
                       "min": bound, "max": bound, "equals": {"enum": [True, False, None]}, "weight": {"type": "number"},
                       "firm": {"type": "boolean"},  # said outright, not "ideally": code may make it a limit (D79)
                       "said": {"type": "string"},  # the user's own words behind it, never shown (D82)
                       # D86: the property types a must applies to, comma separated, usually empty. A plain string:
                       # an array of types made the reply grammar too large for structured output.
                       "only_for_types": {"type": "string"}},
    }


def _criteria_core() -> dict:
    return {
        "intent": {"enum": [*get_args(Intent), None]},  # the same nullable enum form as extraction
        "areas": {"type": "array", "items": {"type": "string", "enum": list(covered_areas())}},
        "hard_limits": _hard_limits_schema(),
        "budget_around": {"type": "boolean"},  # the user said "around" their top price; code adds the margin (D53)
        "ideally": {"type": "array", "items": {"type": "string", "enum": list(IDEALLY)}},  # code adds the margins (D56)
        "preferences": {"type": "array", "items": _preference_schema()},  # firm ones can be limits, so supply needs them (D79)
    }


def schema() -> dict:
    """The reply format. Reasoning first, then the reply, then the card (the model writes in this order)."""
    criteria = {
        "type": "object", "additionalProperties": False,
        "required": ["intent", "areas", "hard_limits", "budget_around", "ideally", "preferences", "open_questions"],
        "properties": {**_criteria_core(), "open_questions": {"type": "array", "items": {"type": "string"}}},
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


def tool() -> dict:
    """check_supply, with the areas the loaded data covers (D69)."""
    return {**TOOL, "input_schema": {**TOOL["input_schema"], "properties": _criteria_core()}}


TOOL = {
    "name": "check_supply",
    "description": ("Count the listings in the snapshot that pass these hard limits, and how many would pass if each "
                    "limit were dropped. Code does the counting. Use it before showing a card whose asks may be hard "
                    "to meet together."),
    "input_schema": {"type": "object", "additionalProperties": False,
                     "required": ["intent", "areas", "hard_limits", "budget_around", "ideally", "preferences"],
                     "properties": _criteria_core()},
}


def areas_text(areas: tuple[str, ...] | None = None) -> str:
    """"Egaleo (Αιγάλεω), Peristeri (Περιστέρι) and Chaidari (Χαϊδάρι)": the covered areas, both spellings."""
    names = [f"{a} ({greek.AREA_GREEK[a]})" for a in (areas or covered_areas())]
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def areas_note(areas: tuple[str, ...] | None = None) -> str:
    """Where the covered areas are, so "Athens" on its own is asked about, not refused (D46, D69)."""
    areas = areas or covered_areas()
    west = [a for a in areas if a in greek.WESTERN_SUBURBS]
    centre = [a for a in areas if a in greek.CENTRAL_ATHENS]
    if west and not centre:
        where = f"All {'three' if len(west) == 3 else len(west)} are in Athens, in its western suburbs"
    elif centre and not west:
        where = "They're all in central Athens"
    else:
        join = lambda xs: xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]  # noqa: E731
        where = f"All are in Athens: {join(west)} in its western suburbs, {join(centre)} in the centre"
    which = "which of the three" if len(areas) == 3 else "which of them"
    return f'{where}, so "Athens" on its own isn\'t an area we don\'t cover: ask {which}, or whether any will do.'


def system_prompt(version: str = PROMPT_VERSION, today: str | None = None) -> str:
    day = date.fromisoformat(today) if today else date.today()
    text = (PROMPTS / f"{version}.md").read_text(encoding="utf-8")
    text = (text.replace("{{today}}", day.isoformat())
                .replace("{{areas}}", areas_text())
                .replace("{{areas_note}}", areas_note())
                .replace("{{new_build_from}}", str(day.year - NEW_BUILD_YEARS))
                .replace("{{renovated_from}}", str(day.year - (RENOVATED_YEARS if _number(version) >= 10 else LEGACY_RENOVATED_YEARS))))
    if "{{" in text:
        raise ValueError("a placeholder in the prompt wasn't filled")
    return text


def _number(version: str) -> int:
    digits = "".join(c for c in version.rsplit("_v", 1)[-1] if c.isdigit())
    return int(digits) if digits else 0


def request(messages: list[dict], today: str, model: str = MODEL, version: str = PROMPT_VERSION) -> dict:
    return {
        "model": model, "max_tokens": MAX_TOKENS,
        "system": [{"type": "text", "text": system_prompt(version, today), "cache_control": {"type": "ephemeral"}}],
        "tools": [tool()],
        "messages": list(messages),  # a copy: the history grows after the call
        "output_config": {"format": {"type": "json_schema", "schema": schema()}},
    }


def _blank(value) -> bool:
    return value in (None, [], "", {})


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
        criteria = card({**args, "preferences": args.get("preferences") or [], "open_questions": []})
    except Exception as err:  # noqa: BLE001 - the model gets the reason back
        return {"error": f"invalid criteria: {err}"}
    outcome = apply_hard_limits(listings, criteria)
    matches = outcome.matches

    def without(update: dict) -> int:
        looser = criteria.model_copy(update={"hard_limits": criteria.hard_limits.model_copy(update=update)})
        return len(apply_hard_limits(listings, looser).matches)

    if_dropped = {}
    for name in HARD_FIELDS:
        value = getattr(criteria.hard_limits, name)
        if _blank(value):
            continue
        if name == "must_have":  # one count per must-have: "without parking, 41"
            for feature in value:
                if_dropped[f"must_have:{feature}"] = without({"must_have": [f for f in value if f != feature]})
        elif name == "must_have_if_type":
            if_dropped[name] = without({name: {}})
        else:
            if_dropped[name] = without({name: [] if name in LIST_FIELDS else None})
    kind = INTENT_TO_LISTING_TYPE[criteria.intent]
    in_areas = [l for l in listings if l.listing_type == kind and (not criteria.areas or l.area in criteria.areas)]
    prices = [l.price_eur for l in in_areas if l.price_eur]
    per_m2 = [l.price_per_m2 for l in in_areas if l.price_per_m2]
    sizes = [l.size_m2 for l in in_areas if l.size_m2]
    result = {
        "search_limits": {"min_price_eur": criteria.hard_limits.min_price_eur, "max_price_eur": criteria.hard_limits.max_price_eur},
        "matches": len(matches), "if_dropped": if_dropped, "listings_in_areas": len(in_areas),
        # D79: homes left out only because the listing doesn't say, per field, so the assistant can tell the user
        "hidden_unknown": dict(outcome.excluded_unknown),
        "from_wishes": harden(args)["from_wishes"],  # firm wishes code made hard limits (D79)
        "median_price_eur": round(statistics.median(prices)) if prices else None,
        "median_price_per_m2": round(statistics.median(per_m2)) if per_m2 else None,
        "median_size_m2": round(statistics.median(sizes)) if sizes else None,
    }
    offers = if_made_limit(criteria, listings)
    if offers:
        result["if_made_limit"] = offers
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


def if_made_limit(criteria: Criteria, listings: list) -> dict:
    """For a firm wish that stays a wish (move in ready, metro minutes): what making it a hard limit would leave (D79).

    Code counts the homes that would pass and how many of those dropped only because the listing doesn't say,
    so the assistant can offer the limit with the cost in plain numbers.
    """
    out = {}
    for preference in criteria.preferences:
        if not preference.firm or preference.feature not in OFFERS:
            continue
        name = OFFERS[preference.feature]
        if name == "exclude_conditions" and preference.equals is True:
            value = sorted({*criteria.hard_limits.exclude_conditions, "needs_work", "unfinished"})
        elif name == "max_metro_walk_min" and isinstance(preference.max, (int, float)):
            value = int(preference.max)
        else:
            continue
        stricter = criteria.model_copy(update={"hard_limits": criteria.hard_limits.model_copy(update={name: value})})
        outcome = apply_hard_limits(listings, stricter)
        field = "condition" if name == "exclude_conditions" else "metro_walk_min"
        out[preference.feature] = {"limit": {name: value}, "matches": len(outcome.matches),
                                   "hidden_unknown": outcome.excluded_unknown.get(field, 0)}
    return out


def eased(criteria: Criteria, listings: list) -> dict:
    """Ways to widen a thin search, each with the count it would give. Code picks the steps (D50, D63).

    One limit at a time, a step past what the search already runs on: the top
    price up 10%, the lowest down 10%, sizes 10% wider, a bedroom either way,
    another type or area. Then "together": every number widened one step at
    once, for when no single change reaches 5 (Mike, D63). Each option carries
    the exact limits it would set, so a click in the app or a yes in the chat
    applies precisely what was counted.
    """
    limits, out = criteria.hard_limits, {}
    step = 50 if (limits.max_price_eur or 0) < 10_000 else 5000

    def count(patch: dict) -> int:
        top = {k: v for k, v in patch.items() if k == "areas"}
        hard = {k: v for k, v in patch.items() if k != "areas"}
        looser = criteria.model_copy(update={"hard_limits": limits.model_copy(update=hard), **top})
        return len(apply_hard_limits(listings, looser).matches)

    def option(patch: dict, to=None) -> dict:
        return {"to": to if to is not None else next(iter(patch.values())), "limits": patch, "matches": count(patch)}

    numbers: dict = {}
    if limits.max_price_eur:
        numbers["max_price_eur"] = max(limits.max_price_eur + step, round(limits.max_price_eur * (1 + EASE) / step) * step)
    if limits.min_price_eur:
        numbers["min_price_eur"] = min(limits.min_price_eur - step, round(limits.min_price_eur * (1 - EASE) / step) * step)
    if limits.min_size_m2:
        numbers["min_size_m2"] = min(limits.min_size_m2 - 1, round(limits.min_size_m2 * (1 - EASE)))
    if limits.max_size_m2:
        numbers["max_size_m2"] = max(limits.max_size_m2 + 1, round(limits.max_size_m2 * (1 + EASE)))
    if limits.min_bedrooms:
        numbers["min_bedrooms"] = limits.min_bedrooms - 1
    if limits.max_bedrooms is not None:
        numbers["max_bedrooms"] = limits.max_bedrooms + 1
    if limits.min_year_built:
        numbers["min_year_built"] = limits.min_year_built - YEAR_STEP
    if limits.max_price_per_m2:
        numbers["max_price_per_m2"] = max(limits.max_price_per_m2 + 50, round(limits.max_price_per_m2 * (1 + EASE) / 50) * 50)
    if limits.max_floor_without_lift is not None:
        numbers["max_floor_without_lift"] = limits.max_floor_without_lift + 1
    if limits.min_bathrooms:
        numbers["min_bathrooms"] = limits.min_bathrooms - 1
    if limits.min_renovated_year:
        numbers["min_renovated_year"] = limits.min_renovated_year - YEAR_STEP
    if limits.min_floor_level is not None and limits.min_floor_level > 0:
        numbers["min_floor_level"] = max(0, limits.min_floor_level - 1)
    if limits.max_floor_level is not None:
        numbers["max_floor_level"] = limits.max_floor_level + 1
    if limits.max_metro_walk_min:
        numbers["max_metro_walk_min"] = limits.max_metro_walk_min + METRO_STEP
    for name, value in numbers.items():
        out[name] = option({name: value})
    if len(numbers) > 1:
        out["together"] = option(dict(numbers), to="every number one step wider")
    if limits.exclude_conditions:
        out["drop_conditions"] = option({"exclude_conditions": []}, to="no condition limit")
    for feature in limits.must_have:  # D79: a must-have can't be "a little" looser, only dropped (it stays a wish)
        out[f"drop_must:{feature}"] = option({"must_have": [f for f in limits.must_have if f != feature]}, to=f"{feature} not a must")
    for kind, features in limits.must_have_if_type.items():  # D86: the same for a must tied to a property type
        out[f"drop_must_if:{kind}"] = option({"must_have_if_type": {k: v for k, v in limits.must_have_if_type.items() if k != kind}},
                                             to=f"{', '.join(features)} not a must for a {kind.replace('_', ' ')}")
    for kind, wider in WIDER_TYPES.items():
        if kind in limits.property_types:
            for extra in (t for t in wider if t not in limits.property_types):
                out[f"add_type:{extra}"] = option({"property_types": [*limits.property_types, extra]}, to=extra)
    if criteria.areas:
        for area in (a for a in covered_areas() if a not in criteria.areas):
            out[f"add_area:{area}"] = option({"areas": [*criteria.areas, area]}, to=area)
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
