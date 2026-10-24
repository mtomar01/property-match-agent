"""The learning eval: does the learned ranking order the waiting homes better than the rules alone? (spec section 12, D76)

The spec's set is 200 or more real swipes. Until there are that many, eight simulated buyers stand in. Each
has a hidden taste written here, over the listing's raw fields and in its own code, that the interview only
partly caught (their stated wishes are what the rules rank by). Each buyer's verdict on every home that passes
their card comes from the hidden taste with noise, so even a perfect model can't score 1.0.

The split is by time, as the spec asks. The buyer swipes the deck as it is before any learning: the rule order,
with an explore card in every fifth slot. The ranking learns from their first swipes, then orders the homes
still waiting after 160 swipes, which it has never seen. That's the deck's real job: choosing the next cards.
Both orders are scored on the same waiting homes:

- **rules**: the v1 score from the stated wishes alone (no learning). With no stated wish, every home ties: 0.5.
- **learned**: the deck's blend after the training swipes (the swipes take over fully from 30, D76).

AUC is how often a liked home scores above a rejected one (0.5 is chance). Precision at 10 is the share of likes
among the 10 waiting homes each order puts first: the next ten cards. The target, set before the first run: a
mean AUC lift of 0.05 or more over the rules, with precision at 10 no lower. Each buyer runs five times with
fresh noise and explore picks, and the scores are the mean.

One buyer's taste is a neighbourhood, which the model has no feature for. It's there on purpose, to show what
the model can't learn.

    uv run python -m evals.harness.learning_eval                     # simulated buyers, the frozen 20 October snapshot
    uv run python -m evals.harness.learning_eval --snapshot PATH     # another frozen file
    uv run python -m evals.harness.learning_eval --real me           # your own swipes, this search and archived ones
"""

from __future__ import annotations

import json
import math
import random
import statistics
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from adapters.snapshot import SnapshotAdapter
from core.models import Criteria, HardLimits, Listing, Swipe
from learning import deck
from learning.area_stats import AreaStats
from learning.learned import Learner, auc, precision_at
from learning.swipes import SwipeStore
from ranking.rules import score as rule_score

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / "data" / "private" / "snapshot.jsonl"  # the frozen 20 October snapshot every eval uses
RESULTS = ROOT / "evals" / "results"
SWIPED = 160  # swipes before the waiting homes are ranked
CURVE = (10, 20, 30, 60, SWIPED)
MIN_WAITING = 40
REPEATS = 5
TARGET_LIFT = 0.05
LIKE_SHARE = 0.4  # each buyer likes about 4 homes in 10 of those that pass their card
SHARPNESS = 4.0  # how cleanly the hidden taste decides: higher means less noise
TS = datetime(2026, 10, 24, 12, tzinfo=timezone.utc)

STOREY = {"basement": -1, "semi_basement": -0.5, "ground": 0, "raised_ground": 0.25, "mezzanine": 0.5}
READY = {"renovated", "new_build", "good"}


def storey(listing: Listing) -> float | None:
    floor = listing.floor.floor_class
    if floor is None or floor == "top":
        return None
    return STOREY.get(floor, float(floor) if floor.isdigit() else None)


def _median_per_m2(listings: list[Listing]) -> dict[str, float]:
    by_area: dict[str, list[int]] = {}
    for l in listings:
        if l.price_per_m2 and l.area:
            by_area.setdefault(l.area, []).append(l.price_per_m2)
    return {a: statistics.median(v) for a, v in by_area.items()}


def _top_hoods(listings: list[Listing], n: int = 2) -> set[str]:
    return {h for h, _ in Counter(l.sub_area for l in listings if l.sub_area).most_common(n)}


# Each buyer: the card the interview gave (limits and the wishes it caught) and the taste it didn't fully catch.
# A taste is a score from raw fields; unknown values count as nothing either way.
def buyers(listings: list[Listing]) -> list[dict]:
    typical = _median_per_m2(listings)
    hoods = _top_hoods(listings)

    def space(l):
        return 1.2 * ((l.size_m2 or 75) >= 85) + 0.6 * ((l.size_m2 or 0) / max(1, l.bedrooms or 1) >= 40) - 0.8 * (storey(l) == 0)

    def value(l):
        if not l.price_per_m2 or l.area not in typical:
            return 0.0
        return -2.0 * (l.price_per_m2 / typical[l.area] - 1)

    def high_up(l):
        s = storey(l)
        return 0.0 if s is None else 1.5 * (s >= 3) - 1.5 * (s <= 0)

    def move_in(l):
        return 0.0 if l.condition is None else 1.4 if l.condition in READY else -1.6 if l.condition in ("needs_work", "unfinished") else 0.3

    def family(l):
        return 1.3 * ((l.bedrooms or 0) >= 3) + 0.8 * ((l.bathrooms or 0) >= 2)

    def neighbourhood(l):
        return 1.8 * (l.sub_area in hoods)

    def thrifty(l):
        return -2.0 * ((l.price_eur or 200000) / 200000) - 0.6 * ((l.size_m2 or 0) > 100)

    def mixed(l):
        s = storey(l)
        return (0.9 * ((l.size_m2 or 0) >= 70) + 0.9 * (s is not None and s >= 2 and (l.size_m2 or 0) >= 70)
                + (0.0 if l.condition is None else 0.8 if l.condition in READY else -0.8))

    def wish(feature, weight, **bound):
        return {"feature": feature, "weight": weight, **bound}

    return [
        {"name": "space", "max_price": 300000, "taste": space, "wishes": [wish("size_m2", 0.6, min=80)]},
        {"name": "value", "max_price": 300000, "taste": value, "wishes": []},
        {"name": "high_up", "max_price": 280000, "taste": high_up, "wishes": [wish("floor_level", 0.5, min=2)]},
        {"name": "move_in", "max_price": 260000, "taste": move_in, "wishes": []},
        {"name": "family", "max_price": 350000, "taste": family, "wishes": [wish("bedrooms", 0.7, min=3)]},
        {"name": "neighbourhood", "max_price": 300000, "taste": neighbourhood, "wishes": [], "unlearnable": True},
        {"name": "thrifty", "max_price": 250000, "taste": thrifty, "wishes": [wish("price_eur", 0.5, max=180000)]},
        {"name": "mixed", "max_price": 300000, "taste": mixed, "wishes": [wish("size_m2", 0.5, min=70)]},
    ]


def criteria_for(buyer: dict) -> Criteria:
    return Criteria(user_id=f"sim_{buyer['name']}", intent="buy", areas=[],
                    hard_limits=HardLimits(max_price_eur=buyer["max_price"], min_price_eur=60000),
                    preferences=buyer["wishes"])


def verdicts(buyer: dict, homes: list[Listing], seed: int) -> dict[str, float]:
    """The buyer's like (1) or reject (0) on every home: the hidden taste, plus noise."""
    tastes = [buyer["taste"](l) for l in homes]
    cut = sorted(tastes)[int(len(tastes) * (1 - LIKE_SHARE))]
    spread = statistics.pstdev(tastes) or 1.0
    rng = random.Random(seed)
    return {l.listing_id: 1.0 if rng.random() < 1 / (1 + math.exp(-SHARPNESS * (t - cut) / spread)) else 0.0
            for l, t in zip(homes, tastes)}


def one_run(buyer: dict, listings: list[Listing], by_id: dict, stats: AreaStats, criteria: Criteria, seed: int) -> dict:
    shown = [l for l, _ in deck.order(deck.ranked_matches(listings, criteria), seed)]
    likes = verdicts(buyer, shown, seed)
    swiped = min(SWIPED, len(shown) - MIN_WAITING)
    log = [Swipe(user_id=criteria.user_id, listing_id=l.listing_id, decision="like" if likes[l.listing_id] else "reject",
                 deck_position=i, ts=TS) for i, l in enumerate(shown[:swiped])]
    waiting = shown[swiped:]
    labels = [likes[l.listing_id] for l in waiting]
    rules = [rule_score(l, criteria.preferences) for l in waiting]
    curve = []
    for k in CURVE:
        if k > swiped:
            continue
        learner = Learner.fit(log[:k], by_id, criteria, stats)
        learned = [learner.blended(l) for l in waiting] if learner else rules
        curve.append({"train": k, "learned_active": learner is not None,
                      "auc_rules": auc(rules, labels), "auc_learned": auc(learned, labels),
                      "p10_rules": precision_at(rules, labels), "p10_learned": precision_at(learned, labels)})
    return {"matches": len(shown), "swiped": swiped, "waiting": len(waiting), "like_share": round(statistics.mean(likes.values()), 2),
            "waiting_likes": int(sum(labels)), "curve": curve}


def _mean_point(points: list[dict]) -> dict:
    """One point of the curve, averaged over the repeats (an AUC with one side missing is left out)."""
    out = {"train": points[0]["train"], "learned_active": sum(1 for p in points if p["learned_active"])}
    for key in ("auc_rules", "auc_learned", "p10_rules", "p10_learned"):
        values = [p[key] for p in points if p[key] is not None]
        out[key] = round(statistics.mean(values), 3) if values else None
    return out


def simulated(snapshot: Path) -> dict:
    listings = [l for l in SnapshotAdapter(snapshot).listings() if l.listing_type == "sale"]
    by_id = {l.listing_id: l for l in listings}
    stats = AreaStats.build(listings)
    rows = []
    for i, buyer in enumerate(buyers(listings)):
        criteria = criteria_for(buyer)
        runs = [one_run(buyer, listings, by_id, stats, criteria, seed=100 + 10 * i + r) for r in range(REPEATS)]
        curve = [_mean_point([run["curve"][j] for run in runs]) for j in range(len(runs[0]["curve"]))]
        rows.append({"buyer": buyer["name"], "matches": runs[0]["matches"], "swiped": runs[0]["swiped"],
                     "waiting": runs[0]["waiting"], "like_share": round(statistics.mean(r["like_share"] for r in runs), 2),
                     "waiting_likes": round(statistics.mean(r["waiting_likes"] for r in runs)),
                     "unlearnable": buyer.get("unlearnable", False), "curve": curve, "final": curve[-1]})
    finals = [r["final"] for r in rows]
    lift = statistics.mean(f["auc_learned"] - f["auc_rules"] for f in finals)
    p10 = statistics.mean(f["p10_learned"] - f["p10_rules"] for f in finals)
    at_30 = [next(c for c in r["curve"] if c["train"] == 30) for r in rows]
    learnable = [r["final"] for r in rows if not r["unlearnable"]]
    summary = {
        "buyers": len(rows), "swiped": SWIPED, "repeats": REPEATS,
        "mean_auc_rules": round(statistics.mean(f["auc_rules"] for f in finals), 3),
        "mean_auc_learned": round(statistics.mean(f["auc_learned"] for f in finals), 3),
        "mean_auc_lift": round(lift, 3), "mean_p10_lift": round(p10, 3),
        "mean_auc_learned_after_30": round(statistics.mean(c["auc_learned"] for c in at_30), 3),
        "mean_auc_lift_after_30": round(statistics.mean(c["auc_learned"] - c["auc_rules"] for c in at_30), 3),
        "buyers_with_lift": sum(1 for f in finals if f["auc_learned"] > f["auc_rules"]),
        "learnable_buyers_with_lift": sum(1 for f in learnable if f["auc_learned"] > f["auc_rules"]),
        "target": f"mean AUC lift >= {TARGET_LIFT}, precision at 10 no lower",
        "passed": lift >= TARGET_LIFT and p10 >= 0,
    }
    return {"summary": summary, "buyers": rows}


def real(user_id: str, snapshot: Path | None) -> dict:
    """Your own likes and rejects, this search and archived ones, oldest first; the last 20% are the test."""
    store = SwipeStore(user_id)
    swipes = sorted([s for s in store.archived() + store.load() if s.verdict], key=lambda s: s.ts)
    listings = SnapshotAdapter(snapshot).listings() if snapshot else SnapshotAdapter().listings()
    by_id = {l.listing_id: l for l in listings}
    swipes = [s for s in swipes if s.listing_id in by_id]
    if len(swipes) < 20:
        return {"summary": {"swipes": len(swipes), "note": "fewer than 20 likes and rejects on this dataset: nothing to measure yet"}}
    state = ROOT / "data" / "private" / "state" / f"{user_id}.json"
    card = json.loads(state.read_text(encoding="utf-8")).get("card") if state.exists() else None
    top = (card or {}).get("hard_limits", {}).get("max_price_eur") or max(by_id[s.listing_id].price_eur or 0 for s in swipes)
    criteria = Criteria(user_id=user_id, intent="buy", areas=[], hard_limits=HardLimits(max_price_eur=top),
                        preferences=[p for p in (card or {}).get("preferences", []) if p.get("weight")])
    cut = int(len(swipes) * 0.8)
    test = swipes[cut:]
    homes = [by_id[s.listing_id] for s in test]
    labels = [1.0 if s.decision == "like" else 0.0 for s in test]
    rules = [rule_score(l, criteria.preferences) for l in homes]
    learner = Learner.fit(swipes[:cut], by_id, criteria, AreaStats.build(listings))
    learned = [learner.blended(l) for l in homes] if learner else rules
    note = "" if len(test) >= 20 else "under 20 test swipes: read this as a first look, not a result"
    return {"summary": {"swipes": len(swipes), "likes": int(sum(1 for s in swipes if s.decision == "like")), "train": cut,
                        "test": len(test), "learned_active": learner is not None,
                        "auc_rules": auc(rules, labels), "auc_learned": auc(learned, labels), "note": note}}


def report(out: dict, name: str) -> str:
    s = out["summary"]
    if "buyers" not in out:
        return f"Learning eval, real swipes: {json.dumps(s, ensure_ascii=False)}"
    lines = [f"Learning eval: {name} ({s['buyers']} simulated buyers; learn from the first swipes, rank the homes waiting after "
             f"{s['swiped']}; mean of {s['repeats']} runs)",
             f"{'buyer':<15}{'waiting':>8}{'AUC rules':>11}{'AUC learned':>13}{'P@10 rules':>12}{'P@10 learned':>14}  AUC after 10/20/30/60/160"]
    for r in out["buyers"]:
        f = r["final"]
        curve = "/".join(f"{c['auc_learned']:.2f}" for c in r["curve"])
        lines.append(f"{r['buyer'] + (' *' if r['unlearnable'] else ''):<15}{r['waiting']:>8}{f['auc_rules']:>11.3f}{f['auc_learned']:>13.3f}"
                     f"{f['p10_rules']:>12.2f}{f['p10_learned']:>14.2f}  {curve}")
    lines.append(f"mean AUC {s['mean_auc_rules']} rules, {s['mean_auc_learned']} learned (lift {s['mean_auc_lift']:+.3f}; "
                 f"{s['mean_auc_lift_after_30']:+.3f} after 30 swipes); precision at 10 lift {s['mean_p10_lift']:+.3f}; "
                 f"{s['buyers_with_lift']} of {s['buyers']} buyers better. {'PASS' if s['passed'] else 'FAIL'} ({s['target']})")
    lines.append("* a neighbourhood taste: the model has no feature for it, so no lift is expected")
    return "\n".join(lines)


if __name__ == "__main__":
    args = sys.argv[1:]
    snapshot = Path(args[args.index("--snapshot") + 1]) if "--snapshot" in args else None
    if "--real" in args:
        print(report(real(args[args.index("--real") + 1], snapshot), "real"))
        sys.exit(0)
    path = snapshot or SNAPSHOT
    if not path.exists():
        sys.exit(f"{path} isn't here: the learning eval needs a frozen snapshot of real listings (the synthetic 60 are too few)")
    out = simulated(path)
    name = "frozen 20 October snapshot" if path == SNAPSHOT else path.name
    print(report(out, name))
    RESULTS.mkdir(parents=True, exist_ok=True)
    suffix = "" if path == SNAPSHOT else "-" + path.stem
    (RESULTS / f"v3-learning{suffix}.json").write_text(json.dumps({
        "eval": "learning", "ran_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "data": f"{name}: counts and scores only, no listing ids", **out,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    sys.exit(0 if out["summary"]["passed"] else 1)
