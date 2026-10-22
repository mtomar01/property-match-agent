"""The answer key check (D42): values where answer key v3 and the listing seem to disagree.

Builds one hosted page listing each disputed value: the listing link, the few
words from its description that matter, the key's value and the proposed
one. The person checking picks which is right, or types another value; each
choice saves to the page's store. `apply` then turns the choices into answer
key v4, recording every change.

The proposed value is the system's reading, but for the metro it is written
as the listing gives it (metres as written, or minutes on foot), so code does
the conversion (D31, D41). The page carries only short quotes, never a whole
description.

Run: uv run python -m evals.harness.key_check build
     uv run python -m evals.harness.key_check apply DECISIONS_DIR   # after the check
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from evals.harness import answer_key
from evals.harness.build_label_tool import RAW, ROOT, SNAPSHOT, _json_for_script, _load
from evals.harness.extraction_eval import PRIVATE, load_predictions, score

TEMPLATE = ROOT / "evals" / "harness" / "key_check_tool.html"
OUT = ROOT / "data" / "private" / "labels" / "agreement" / "key-check.html"
FIELDS = ("metro_walk_min", "floor_class", "storage")
GROUPS = {
    "metro_walk_min": ("Metro", "Minutes count only on foot (με τα πόδια). A distance counts as written, in metres."),
    "floor_class": ("Floor", "The guide says υπερυψωμένο ισόγειο is raised ground, even when the table says Ισόγειο."),
    "storage": ("Storage", "An εσωτερική αποθήκη counts as storage, even when Αποθήκη is crossed out (D34)."),
}
METRE = re.compile(r"(\d[\d.,]*)\s*(?:m\b|μ\.?|μέτρ\w*)", re.I)
KM = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:χλμ|χιλιόμετρ\w*|km)", re.I)


def metro_as_written(quote: str, minutes: int | None) -> int | None:
    """The metro distance in the form the listing gives it: metres as written, else minutes."""
    if km := KM.search(quote or ""):
        return round(float(km.group(1).replace(",", ".")) * 1000)
    if metres := METRE.search(quote or ""):
        digits = re.sub(r"[.,](?=\d{3}\b)", "", metres.group(1)).split(",")[0].split(".")[0]
        if digits.isdigit() and 20 <= int(digits) <= 5000:
            return int(digits)
    return minutes


def show(field: str, value) -> str:
    if value is None:
        return "blank"
    if field == "metro_walk_min":
        return f"{value} m ({-(-value // 80)} min)" if value > 60 else f"{value} min"
    if field == "storage":
        return "yes" if value else "no"
    return str(value).replace("_", " ")


def items(key_version: int = 3, run_name: str = "haiku_v3+crossed-fill") -> list[dict]:
    key, _ = answer_key.load(key_version)
    labels = {label.listing_id: label for label in key}
    system = load_predictions(PRIVATE / f"predictions_{run_name}.jsonl")
    evidence = {json.loads(line)["listing_id"]: json.loads(line)["evidence"]
                for line in (PRIVATE / f"predictions_{run_name}.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()}
    descriptions = {f"spitogatos:{json.loads(line)['source_id']}": json.loads(line)["sections"].get("Περιγραφή", "")
                    for line in RAW.read_text(encoding="utf-8").splitlines() if line.strip()}
    numbers = {item["listing_id"]: (n, item["url"]) for n, item in enumerate(_load(RAW, SNAPSHOT), start=1)}
    out = []
    for row in score(key, system).detail:
        name, listing_id = row["field"], row["listing_id"]
        if name not in FIELDS:
            continue
        quote = evidence[listing_id].get(name, "") or labels[listing_id].evidence.get(name, "")
        proposed = row["prediction"]
        if name == "metro_walk_min":
            proposed = metro_as_written(quote, proposed)
            if not quote:  # the system found no metro distance: show the sentence that mentions the metro
                found = re.search(r"[^.•\n]{0,90}(?:μετρ[όο]|metro)[^.•\n]{0,30}", descriptions[listing_id], re.I)
                quote = found.group(0).strip() if found else ""
        number, url = numbers[listing_id]
        out.append({
            "id": f"{name}-{listing_id.split(':')[1]}", "group": name, "number": number, "listing_id": listing_id, "url": url,
            "quote": quote[:160], "key_value": row["key"], "key_show": show(name, row["key"]),
            "proposed_value": proposed, "proposed_show": show(name, proposed),
        })
    order = {name: i for i, name in enumerate(FIELDS)}
    return sorted(out, key=lambda i: (order[i["group"]], i["number"]))


def build(out_path: Path = OUT) -> Path:
    chosen = items()
    payload = {"groups": [{"field": f, "title": GROUPS[f][0], "rule": GROUPS[f][1]} for f in FIELDS],
               "items": chosen}
    html = TEMPLATE.read_text(encoding="utf-8")
    if html.count("__DATA_JSON__") != 1:
        raise ValueError("the template must hold exactly one __DATA_JSON__ placeholder")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html.replace("__DATA_JSON__", _json_for_script(payload)), encoding="utf-8")
    return out_path


if __name__ == "__main__":
    if sys.argv[1:2] == ["build"]:
        path = build()
        print(f"{len(items())} values, page at {path.relative_to(ROOT)}")
    else:
        print(__doc__)
