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
TARGETS = {"field_accuracy": 0.95, "invented_hard_limits": 0}

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
If it shows a summary and asks whether it's right, say yes. Never add a wish, a limit or a detail of your own."""
SIM_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["reply"],
              "properties": {"reply": {"type": "string"}}}


# ---------------------------------------------------------------------------
# Running a chat
# ---------------------------------------------------------------------------


def language(text: str) -> str:
    letters = [c for c in text if c.isalpha()]
    greek = sum(1 for c in letters if "Ͱ" <= c <= "Ͽ" or "ἀ" <= c <= "῿")
    return "el" if letters and greek / len(letters) >= 0.5 else "en"


def simulated_answer(chat: dict, said: str, lang: str, client, cache_dir: Path | None,
                     already: list[str] | None = None) -> tuple[str, dict]:
    facts = json.dumps(chat["user_facts"], ensure_ascii=False)
    earlier = "\n".join(f"- {t}" for t in already or chat["turns"])
    body = {"model": SIM_MODEL, "max_tokens": 1500, "system": SIM_SYSTEM,  # Haiku 5.5 can think first: leave room
            "messages": [{"role": "user", "content": (f"<persona>{chat['persona']}</persona>\n<facts>{facts}</facts>\n"
                                                      f"<you_already_said>\n{earlier}\n</you_already_said>\n"
                                                      f"<language>{'Greek' if lang == 'el' else 'English'}</language>\n"
                                                      f"<assistant_said>{said}</assistant_said>")}],
            "output_config": {"format": {"type": "json_schema", "schema": SIM_SCHEMA}}}
    response = interview.call(client, body, cache_dir)
    text = "".join(b["text"] for b in response["content"] if b["type"] == "text")
    if response["stop_reason"] != "end_turn" or not text:
        raise SimulatedUserError(f"the simulated user gave no answer (stop reason {response['stop_reason']})")
    return json.loads(text)["reply"], response


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
        elif extra < EXTRA_ANSWERS and last and last.get("output"):
            text, response = simulated_answer(chat, last["output"]["reply"], lang, sim_client, sim_cache,
                                              [e["text"] for e in log if e["role"] == "user"])
            llm.add_usage(usage["simulated_user"], response["usage"])
            if not response["cached"]:
                llm.add_usage(usage["simulated_user_paid"], response["usage"])
            source, extra = "simulated", extra + 1
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
    return {float(v) for v in values if isinstance(v, (int, float))}


def quotes_tool_number(reply: str, results: list[dict], user_numbers: set[float]) -> bool:
    tool = set().union(*(_tool_numbers(r) for r in results)) if results else set()
    said = numbers_in(reply) - user_numbers
    return any(abs(n - t) <= max(1.0, 0.01 * t) for n in said for t in tool)


def _asked(turn: dict) -> set[str]:
    out = turn.get("output") or {}
    has_question = "?" in out.get("reply", "") or ";" in out.get("reply", "") or ";" in out.get("reply", "")
    return set(out.get("asking_about") or []) if out.get("action") == "ask" and has_question else set()


def behaviours(chat: dict, transcript: dict) -> dict[str, bool]:
    log = transcript["log"]
    replies = [t for t in log if t["role"] == "assistant" and t.get("output")]
    asked = set().union(*(_asked(t) for t in replies)) if replies else set()
    out = {f"ask:{topic}": topic in asked for topic in chat["must_ask"]}
    user_numbers = set().union(*(numbers_in(t["text"]) for t in log if t["role"] == "user")) if log else set()
    final = transcript["final"] or {}
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
        elif item == "confirm_change":
            last_script = max(i for i, t in enumerate(log) if t["role"] == "user" and t["source"] == "script")
            after = next((t for t in log[last_script + 1:] if t["role"] == "assistant" and t.get("output")), None)
            new_price = (final.get("hard_limits") or {}).get("max_price_eur")
            out[item] = bool(after and after["output"]["action"] == "confirm" and new_price
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


def score_chat(chat: dict, transcript: dict) -> dict:
    predicted = transcript["final"] or {"intent": None, "areas": [], "hard_limits": {}, "preferences": []}
    expected = chat["expected_criteria"]
    replies = [t for t in transcript["log"] if t["role"] == "assistant" and t.get("output")]
    return {
        "chat_id": chat["chat_id"], "language": chat["language"], "tests": chat["tests"],
        "fields": field_outcomes(expected, predicted), "preferences": preference_outcomes(expected, predicted),
        "behaviours": behaviours(chat, transcript), "confirmed": transcript["confirmed"],
        "valid_card": transcript["final_valid"], "assistant_replies": len(replies),
        "questions": sum(len(_asked(t)) for t in replies),
        "tool_calls": sum(len(t.get("tool_calls") or []) for t in replies),
        "repairs": sum(len(t.get("repairs") or []) for t in replies),
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
             f"  cost ${summary['cost_usd']:.3f} (${summary['mean_cost_per_chat_usd']:.4f} a chat)", "", "  misses:"]
    for s in scores:
        bad = [f"{k}={v}" for k, v in s["fields"].items() if v != "correct"]
        bad += [f"pref {p['feature']} {p['result']}" for p in s["preferences"] if p["result"] != "correct"]
        bad += [f"weight {p['feature']}" for p in s["preferences"] if p.get("weight") == "disagrees"]
        bad += [k for k, v in s["behaviours"].items() if not v]
        if not s["confirmed"]:
            bad.append("not confirmed")
        if bad:
            lines.append(f"    {s['chat_id']}: {', '.join(bad)}")
    return "\n".join(lines)


def load_chats(path: Path = CHATS) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def run(only: list[str] | None = None, limit: int | None = None, model: str = interview.MODEL,
        version: str = interview.PROMPT_VERSION, client=None, listings: list | None = None, write: bool = True,
        workers: int = 4) -> dict:
    chats = [c for c in load_chats() if not only or c["chat_id"] in only][:limit]
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
    name = f"{version}-{model.replace('claude-', '')}" + ("" if not (only or limit) else "-partial")
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


if __name__ == "__main__":
    args = sys.argv[1:]
    only = args[args.index("--only") + 1].split(",") if "--only" in args else None
    limit = int(args[args.index("--limit") + 1]) if "--limit" in args else None
    run(only=only, limit=limit)
