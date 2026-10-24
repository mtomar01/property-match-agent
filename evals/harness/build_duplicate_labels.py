"""Build the duplicate labelling page: 60 pairs from the frozen snapshot, to mark "same home" or not (D78).

The spec's duplicates set is 60 labelled pairs across the portals (section 12). The pairs are drawn from the
finder's own candidates so the sample holds enough real duplicates to measure: up to 24 it would merge, up to
18 borderline, and the rest close pairs it keeps apart (same area, size within 2 m², price within 10%). The
page never shows which is which: the labels are blind.

Two pages, both offline single files:

- the full page (`duplicate_pairs.html`): the facts and each description, for you on your machine;
- the links-only page (`--links-only`): the facts and the two links, no listing text, so it can be passed to
  GB like the hosted extraction page (D28). The labeller opens both listings on the portal.

Labels export as JSONL; check them with `uv run python -m evals.harness.duplicates_eval --labels FILE ...`.

    uv run python -m evals.harness.build_duplicate_labels
    uv run python -m evals.harness.build_duplicate_labels --links-only
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

from adapters.snapshot import SnapshotAdapter
from core import pii
from core.models import Listing
from dedupe import finder

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / "data" / "private" / "snapshot.jsonl"
OUT = ROOT / "data" / "private" / "labels" / "duplicates"
SEED = 2026
TAKE = {"same": 24, "borderline": 18, "different": 18}
PAIRS = 60


def side(listing: Listing, with_text: bool) -> dict:
    out = {"id": listing.listing_id, "source": listing.source, "url": listing.url, "price": listing.price_eur,
           "size": listing.size_m2, "bedrooms": listing.bedrooms, "bathrooms": listing.bathrooms,
           "floor": listing.floor.raw or listing.floor.floor_class, "year": listing.year_built,
           "area": listing.area, "neighbourhood": listing.sub_area, "condition": listing.condition, "title": listing.title}
    if with_text:
        text = (listing.description or "")[:700]
        if pii.find_pii(text) or pii.find_pii(listing.title or ""):
            raise ValueError(f"{listing.listing_id} still holds contact details; scrub the snapshot first")
        out["text"] = text
    return out


def sample(listings: list[Listing], seed: int = SEED) -> list[tuple[str, str]]:
    """Up to 60 candidate pairs, stratified by the finder's verdict, in a fixed shuffled order."""
    rng = random.Random(seed)
    found = finder.pairs(listings)
    chosen = []
    for verdict, take in TAKE.items():
        group = sorted(((p.a, p.b) for p in found if p.verdict == verdict))
        rng.shuffle(group)
        chosen += group[:take]
    if len(chosen) < PAIRS:  # a small dataset: top up from whatever is left
        rest = sorted({(p.a, p.b) for p in found} - set(chosen))
        rng.shuffle(rest)
        chosen += rest[:PAIRS - len(chosen)]
    rng.shuffle(chosen)
    return chosen[:PAIRS]


def build(snapshot: Path = SNAPSHOT, links_only: bool = False) -> Path:
    listings = SnapshotAdapter(snapshot).listings()
    by_id = {l.listing_id: l for l in listings}
    items = [{"pair": f"p{i:02d}", "a": side(by_id[a], not links_only), "b": side(by_id[b], not links_only)}
             for i, (a, b) in enumerate(sample(listings), start=1)]
    payload = json.dumps({"pairs": items, "page": "links" if links_only else "full", "snapshot": snapshot.name}, ensure_ascii=False)
    for char, escape in (("<", "\\u003c"), (">", "\\u003e"), ("&", "\\u0026"), (" ", "\\u2028"), (" ", "\\u2029")):
        payload = payload.replace(char, escape)
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / ("duplicate_pairs_links.html" if links_only else "duplicate_pairs.html")
    path.write_text(PAGE.replace("__DATA__", payload), encoding="utf-8")
    return path


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Duplicate Pairs</title>
<style>
:root { --bg:#f7f6f3; --card:#fff; --ink:#1d1d1b; --muted:#6b6a65; --line:#dedcd5; --accent:#2f5d50; --pick:#e3efe9; }
@media (prefers-color-scheme: dark) { :root { --bg:#191918; --card:#232321; --ink:#ecebe6; --muted:#a3a29b; --line:#3a3936; --accent:#8cc5b2; --pick:#24372f; } }
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--ink); font:15px/1.45 system-ui, sans-serif; }
main { max-width: 1040px; margin: 0 auto; padding: 16px; }
header { display:flex; gap:12px; align-items:center; flex-wrap:wrap; margin-bottom:12px; }
h1 { font-size:20px; margin:0 12px 0 0; }
.muted { color:var(--muted); }
.pair { background:var(--card); border:1px solid var(--line); border-radius:10px; padding:14px; margin:12px 0; }
.sides { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
@media (max-width: 700px) { .sides { grid-template-columns:1fr; } }
.side { border:1px solid var(--line); border-radius:8px; padding:10px; overflow-wrap:anywhere; }
.side dl { display:grid; grid-template-columns:auto 1fr; gap:2px 10px; margin:8px 0; }
.side dt { color:var(--muted); }
.side dd { margin:0; }
.text { white-space:pre-wrap; font-size:13px; max-height:180px; overflow:auto; border-top:1px solid var(--line); padding-top:6px; }
.choices { display:flex; gap:8px; flex-wrap:wrap; margin-top:10px; align-items:center; }
button { font:inherit; padding:7px 12px; border-radius:7px; border:1px solid var(--line); background:var(--card); color:var(--ink); cursor:pointer; }
button.on { background:var(--pick); border-color:var(--accent); }
input { font:inherit; padding:6px 8px; border-radius:6px; border:1px solid var(--line); background:var(--card); color:var(--ink); }
.note { flex:1; min-width:180px; }
a { color:var(--accent); }
</style></head>
<body><main>
<header><h1>Duplicate pairs</h1>
<label>Your name <input id="who" placeholder="mike or gb"></label>
<span id="count" class="muted"></span>
<button id="export">Export labels</button></header>
<p class="muted">Are A and B the same home, listed twice? Open both links when the facts aren't enough: photos decide most pairs.
"Can't tell" is fine when a listing is gone or the photos don't show it.</p>
<div id="list"></div>
</main>
<script>
const DATA = __DATA__;
const KEY = "pm-duplicates-" + DATA.page + "-" + DATA.snapshot;
let saved = {};
try { saved = JSON.parse(localStorage.getItem(KEY) || "{}"); } catch (e) { saved = {}; }
function store() { try { localStorage.setItem(KEY, JSON.stringify(saved)); } catch (e) {} }
const ROWS = [["price", "Price", v => v == null ? "on request" : "€" + v.toLocaleString("en-GB")], ["size", "Size", v => v + " m²"],
  ["bedrooms", "Bedrooms"], ["bathrooms", "Bathrooms"], ["floor", "Floor"], ["year", "Built"], ["area", "Area"],
  ["neighbourhood", "Neighbourhood"], ["condition", "Condition"]];
function sideHtml(label, s) {
  const el = document.createElement("div"); el.className = "side";
  const h = document.createElement("div");
  const a = document.createElement("a"); a.href = s.url; a.target = "_blank"; a.rel = "noopener"; a.textContent = label + " · " + s.source + " ↗";
  h.appendChild(a); el.appendChild(h);
  if (s.title) { const t = document.createElement("div"); t.className = "muted"; t.textContent = s.title; el.appendChild(t); }
  const dl = document.createElement("dl");
  for (const [k, name, fmt] of ROWS) {
    const dt = document.createElement("dt"); dt.textContent = name;
    const dd = document.createElement("dd"); const v = s[k];
    dd.textContent = v == null || v === "" ? (k === "price" ? "on request" : "not stated") : (fmt ? fmt(v) : String(v));
    dl.append(dt, dd);
  }
  el.appendChild(dl);
  if (s.text) { const tx = document.createElement("div"); tx.className = "text"; tx.textContent = s.text; el.appendChild(tx); }
  return el;
}
function render() {
  const list = document.getElementById("list"); list.textContent = "";
  for (const p of DATA.pairs) {
    const box = document.createElement("section"); box.className = "pair";
    const head = document.createElement("div"); head.className = "muted"; head.textContent = "Pair " + p.pair.slice(1);
    const sides = document.createElement("div"); sides.className = "sides";
    sides.append(sideHtml("A", p.a), sideHtml("B", p.b));
    const choices = document.createElement("div"); choices.className = "choices";
    for (const [value, text] of [["same", "Same home"], ["different", "Different homes"], ["unsure", "Can't tell"]]) {
      const b = document.createElement("button"); b.type = "button"; b.textContent = text;
      if ((saved[p.pair] || {}).label === value) b.className = "on";
      b.onclick = () => { saved[p.pair] = { ...(saved[p.pair] || {}), label: value }; store(); render(); };
      choices.appendChild(b);
    }
    const note = document.createElement("input"); note.className = "note"; note.placeholder = "Note (optional)";
    note.value = (saved[p.pair] || {}).note || "";
    note.onchange = () => { saved[p.pair] = { ...(saved[p.pair] || {}), note: note.value.slice(0, 300) }; store(); };
    choices.appendChild(note);
    box.append(head, sides, choices); list.appendChild(box);
  }
  const done = DATA.pairs.filter(p => (saved[p.pair] || {}).label).length;
  document.getElementById("count").textContent = done + " of " + DATA.pairs.length + " labelled";
}
document.getElementById("who").value = saved.__who || "";
document.getElementById("who").onchange = e => { saved.__who = e.target.value.trim(); store(); };
document.getElementById("export").onclick = () => {
  const who = (saved.__who || "").replace(/[^a-z0-9_-]/gi, "") || "labeller";
  const lines = DATA.pairs.filter(p => (saved[p.pair] || {}).label).map(p => JSON.stringify({
    pair: p.pair, a: p.a.id, b: p.b.id, label: saved[p.pair].label, note: saved[p.pair].note || null, labeller: who, snapshot: DATA.snapshot }));
  const blob = new Blob([lines.join("\\n") + "\\n"], { type: "application/json" });
  const link = document.createElement("a"); link.href = URL.createObjectURL(blob); link.download = "duplicates_" + who + ".jsonl"; link.click();
};
render();
</script></body></html>
"""


if __name__ == "__main__":
    args = sys.argv[1:]
    snapshot = Path(args[args.index("--snapshot") + 1]) if "--snapshot" in args else SNAPSHOT
    print(f"Wrote {build(snapshot, links_only='--links-only' in args)}")
