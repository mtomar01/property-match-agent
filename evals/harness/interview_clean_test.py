"""The interview clean test (D51): chats Mike and GB wrote on the "Interview Chats" page.

The page saves each chat under chats/<writer id>/items/chat_<n>. Pull them with
the ArtifactData tool into a folder (pulled/<writer>/.../chat_<n>.json), then
this turns them into the same JSONL as evals/datasets/interview_chats.jsonl and
runs the eval on them with the prompt unchanged.

The cards are then rewritten to the rules Mike settled (FIXES, D54); the
cards as written are kept beside them in chats_as_written.jsonl.

Run: uv run python -m evals.harness.interview_clean_test build PULLED_DIR
     uv run python -m evals.harness.interview_clean_test run        # pays for the calls
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from evals.harness.build_label_tool import ROOT

OUT = ROOT / "data" / "private" / "interview_clean" / "chats.jsonl"
NUMBER_FIELDS = ("max_price_eur", "min_price_eur", "min_size_m2", "max_size_m2", "min_bedrooms")


def facts(text: str) -> dict[str, str]:
    """'Bedrooms: two at least' lines become {'bedrooms': 'two at least'}; a line without a colon keeps a number."""
    out = {}
    for i, line in enumerate(l.strip() for l in (text or "").splitlines()):
        if not line:
            continue
        key, sep, value = line.partition(":")
        name = re.sub(r"\W+", "_", key.strip().lower()).strip("_") if sep else f"fact_{i + 1}"
        out[name or f"fact_{i + 1}"] = value.strip() if sep else line
    return out


def preference(p: dict) -> dict | None:
    bound, value = p.get("bound"), (p.get("value") or "").strip()
    out = {"feature": p["feature"], "weight": float(p.get("weight") or 0.6)}
    if bound in ("yes", "no"):
        return dict(out, equals=bound == "yes")
    if not value:
        return None
    number = re.sub(r"[^\d.]", "", value.replace(",", "."))
    out[bound] = value.upper() if p["feature"] == "energy_class" else (float(number) if "." in number else int(number))
    return out


def to_chat(doc: dict, writer: str) -> dict:
    turns = [t.strip() for t in doc.get("turns") or [] if t and t.strip()]
    limits = {k: v for k, v in (doc.get("hard_limits") or {}).items() if k in NUMBER_FIELDS and v}
    if doc.get("property_types"):
        limits["property_types"] = doc["property_types"]
    if doc.get("exclude_floors"):
        limits["exclude_floors"] = doc["exclude_floors"]
    must = doc.get("must") or []
    not_covered = [a.strip() for a in re.split(r"[,;/]| or | ή ", doc.get("not_covered") or "") if a.strip()]
    return {
        "chat_id": f"clean_{writer}_{doc['chat_no']}", "language": doc.get("language") or "en",
        "persona": f"Written by {writer}", "tests": ["clean_test"], "turns": turns,
        "user_facts": facts(doc.get("facts", "")),
        "expected_criteria": {"intent": doc.get("intent") or None, "areas": doc.get("areas") or [], "hard_limits": limits,
                              "preferences": [p for p in map(preference, doc.get("preferences") or []) if p],
                              "open_questions": []},
        "must_ask": [m for m in must if not m.startswith("say:")],
        "must_say": [f"reply_in:{doc.get('language') or 'en'}"] + [m[4:] for m in must if m.startswith("say:")]
                    + [f"area_not_covered:{a}" for a in not_covered],
        "must_not_invent": [], "notes": doc.get("notes", ""),
    }


def pref(feature: str, weight: float, **bound) -> dict:
    return {"feature": feature, "weight": weight, **bound}


MIKE_4_TOP = 400000  # the loan plus savings, reached only by asking (Mike, D54)
APT = ["apartment"]
GROUND_FLOORS = ["basement", "semi_basement", "ground", "raised_ground"]
# The cards rewritten to the rules Mike settled on 22 October (D53, D54). Each entry replaces those parts of a
# card and says why; everything else stays as written. The cards as written are kept beside them.
FIXES = {
    "clean_gb_1": ({"hard_limits": {"max_price_eur": 200000, "min_bedrooms": 2, "max_floor_without_lift": 0,
                                    "min_bathrooms": 2, "must_have": ["parking"]}, "budget_around": True,
                    "preferences": [],
                    "must_ask": ["intent", "budget", "areas", "bedrooms", "purpose"]},
                   "around 200 is ±10% in code; 70-120 m² wasn't said; bathrooms and parking were; no ceiling or year question; "
                   "'αν είναι σε όροφο, να έχει ασανσέρ' is the stairs limit at 0 since D73 (D77); two bathrooms and parking said "
                   "outright are limits since D79"),
    "clean_gb_3": ({"user_facts": {"purpose": "Επένδυση, για να το νοικιάσω"},
                    "hard_limits": {"max_price_eur": 180000, "property_types": APT, "max_price_per_m2": 2000},
                    "must_ask": ["intent", "budget", "areas", "confirm_investor_mode", "purpose"]},
                   "an investment the chat doesn't say, so the purpose question finds it; lowest price from code; no costs or year question; "
                   "'up to 2000 per m²' is a hard limit since D73"),
    "clean_gb_5": ({"hard_limits": {"max_price_eur": 250000, "min_bedrooms": 3, "min_bathrooms": 2, "must_have": ["parking"]},
                    "preferences": [],
                    "must_ask": ["intent", "budget", "areas", "bedrooms", "purpose"]},
                   "grader slip: 3 δωμάτια, 2 bathrooms and parking were said, outright, so limits since D79; lowest price from code; "
                   "no ceiling or costs question"),
    "clean_mike_2": ({"hard_limits": {"max_price_eur": 150000, "max_bedrooms": 1, "exclude_floors": GROUND_FLOORS,
                                      "min_renovated_year": 2021},
                      "budget_around": True, "preferences": []},
                     "around 150k is ±10% in code; 20-50 m² wasn't said; 'one bedroom but studios are fine' is up to 1 bedroom "
                     "(Mike, D58); 'renovated' said outright is renovated or built in the last 5 years, a limit (Mike, D79)"),
    "clean_mike_3": ({"areas": [], "hard_limits": {"max_price_eur": 200000, "min_size_m2": 30, "max_size_m2": 50, "min_bedrooms": 1,
                                                    "property_types": APT, "min_renovated_year": 2021},
                      "budget_around": True, "ideally": ["bedrooms", "size"], "preferences": []},
                     "1 bedroom was said; διαμέρισμα is apartment only; 'tha ithela na einai anakainismeno' is renovated in the "
                     "last 5 years, said outright, so a limit (D79); "
                     "'idanika' keeps size and bedrooms as limits with code's margins, and makes the price 'around' (D56)"),
    "clean_mike_4": ({"user_facts": {"budget": "A loan of up to 350k plus about 50k of my own, so up to 400k"},
                      "hard_limits": {"max_price_eur": MIKE_4_TOP, "min_size_m2": 40, "min_bedrooms": 2, "property_types": APT,
                                      "must_have": ["balcony"], "min_floor_level": 4},
                      "preferences": [],
                      "must_ask": ["budget_ceiling", "purpose"]},
                     "400k only by asking whether savings come on top of the loan (the fact lets the simulated user answer); "
                     "apartment only; 100 m² wasn't said; lowest price from code; high floors start at 4 (Mike, D58); 'I like high "
                     "floors and big balconies' is said outright, with no 'ideally', so both are limits since D79"),
    "clean_mike_5": ({"hard_limits": {"max_price_eur": 250000, "max_floor_without_lift": 1},
                      "preferences": [pref("balcony", 0.9, equals=True),
                                      pref("metro_walk_min", 0.6, max=10), pref("renovated_year", 0.7, min=2021)],
                      "must_ask": ["areas", "metro_minutes", "confirm_investor_mode"]},
                     "σπίτι names no type; ideally renovated was said; an investment said unprompted is confirmed first (spec); no costs question; "
                     "'πάνω από 1ο όροφο βεβαιώσου ότι έχει ασανσέρ' is the stairs limit at 1 since D73 (D77); 'ιδανικά ανακαινισμένο' "
                     "stays a wish (last 5 years since D79); the balcony is wanted only above the 1st floor, a condition no limit "
                     "can express, so it stays a strong wish"),
}


def fixed(chat: dict) -> tuple[dict, str | None]:
    """The chat with its card rewritten to the settled rules (rentals: only the behaviour is checked)."""
    chat = json.loads(json.dumps(chat))
    if chat["expected_criteria"]["intent"] == "rent":
        chat["must_say"].append("rent_not_supported")
        chat["must_ask"] = []  # no rental search yet, so no rental questions either
        return chat, "rentals aren't supported yet: the assistant says so; the card and its questions aren't scored"
    change = FIXES.get(chat["chat_id"])
    if not change:
        return chat, None
    parts, why = change
    for key, value in parts.items():
        if key in ("must_ask", "user_facts"):
            chat[key] = value
        elif key == "hard_limits":
            chat["expected_criteria"]["hard_limits"] = {k: v for k, v in value.items() if v is not None}
        else:
            chat["expected_criteria"][key] = value
    return chat, why


def build(pulled: Path, out: Path = OUT) -> Path:
    chats = []
    for writer_dir in sorted(p for p in pulled.iterdir() if p.is_dir()):
        for f in sorted(writer_dir.rglob("chat_*.json")):
            doc = json.loads(f.read_text(encoding="utf-8"))
            doc = doc.get("data", doc)
            if doc.get("turns") and any(t.strip() for t in doc["turns"]) and doc.get("intent"):
                chats.append(to_chat(doc, writer_dir.name))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.with_name("chats_as_written.jsonl").write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in chats), encoding="utf-8")
    rows, changes = [], {}
    for chat in chats:
        row, why = fixed(chat)
        rows.append(row)
        if why:
            changes[chat["chat_id"]] = why
    out.write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in rows), encoding="utf-8")
    out.with_name("changes.json").write_text(json.dumps(changes, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


if __name__ == "__main__":
    if sys.argv[1:2] == ["build"]:
        print(f"Wrote {build(Path(sys.argv[2])).relative_to(ROOT)}")
    elif sys.argv[1:2] == ["run"]:
        from evals.harness import interview_eval
        interview_eval.run(chats_path=OUT, set_name="clean")
    else:
        print(__doc__)
