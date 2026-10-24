"""The learned ranking: a small logistic regression on the user's own likes and rejects (spec section 10, D76).

The interview's weights are a guess at taste; swipes are taste itself. This model reads each home as a
handful of features, learns from the user's verdicts which ones go with a like, and turns that into a
probability. It's blended with the rule score: the swipes count for nothing at first and for everything
from 30 verdicts on, so a few early swipes can't overturn what the user said in the chat. Even then the
chat still counts: the rule score is one of the model's features, so the swipes learn how much the stated
wishes matter. Without it, the learning eval found the model overruling a good interview at 30 (D76).

Why logistic regression, written out in plain Python: a few hundred swipes and about twenty features is
tiny, the weights can be read and explained ("balcony counts for you, ground floors count against"), and
it needs no new dependency. Hard limits are untouched: the model only reorders homes that already passed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

from core import greek
from core.models import MOVE_IN_READY, Criteria, Listing, Swipe
from learning.area_stats import AreaStats, days_on_market
from ranking.rules import ENERGY_ORDER, score as rule_score

FULL_TRUST = 30  # verdicts at which the learned score takes over completely (spec section 10)
MIN_EACH = 3  # likes and rejects before anything is learned
L2 = 1.0
STEPS = 400
RATE = 0.3

REASON_WEIGHT = 2.0  # a reject with a tapped reason counts double: the user said why (spec section 10)
CLIP = 5.0  # a home far outside what the user has swiped can't swing the score without bound

FEATURES = (
    "price_vs_top", "per_m2_vs_typical", "size", "bedrooms", "bathrooms", "low_floor", "high_floor", "top_floor", "floor_unknown",
    "age", "year_unknown", "renovated_recently", "energy", "energy_unknown", "balcony", "parking", "lift", "storage",
    "metro_close", "move_in_ready", "long_on_market", "stated_wishes",
)
WORDS = {  # each feature in plain words, for "what the ranking has learned"
    "price_vs_top": "a higher price", "per_m2_vs_typical": "a higher price per m² than similar homes",
    "size": "more space", "bedrooms": "more bedrooms", "bathrooms": "a second bathroom", "low_floor": "a low floor (mezzanine or below)",
    "high_floor": "a high floor (4th or above)", "top_floor": "a top floor", "floor_unknown": "no stated floor",
    "age": "a newer building", "year_unknown": "no stated year", "renovated_recently": "a renovation in the last 10 years",
    "energy": "a better energy class", "energy_unknown": "no stated energy class", "balcony": "a balcony",
    "parking": "parking", "lift": "a lift", "storage": "a storage room", "metro_close": "the metro within 10 minutes",
    "move_in_ready": "ready to move in", "long_on_market": "6 months or more on the market",
    "stated_wishes": "the wishes you gave in the chat",
}


def _yes_no(value) -> float:
    return 0.5 if value is None else 1.0 if value else 0.0


def features(listing: Listing, criteria: Criteria, stats: AreaStats, today: date | None = None) -> list[float]:
    """One home as numbers. Unknown is 0.5 on a yes/no, or its own flag, never a guess."""
    today = today or date.today()
    top = criteria.hard_limits.max_price_eur
    typical = stats.typical(listing)
    level = greek.floor_level(listing.floor.floor_class)
    energy = ENERGY_ORDER.index(listing.energy_class.value) if listing.energy_class.value in ENERGY_ORDER else None
    days = days_on_market(listing)
    return [
        (listing.price_eur / top) if listing.price_eur and top else 0.8,
        (listing.price_per_m2 / typical.per_m2 - 1) if listing.price_per_m2 and typical else 0.0,
        (listing.size_m2 or 75) / 100,
        (listing.bedrooms if listing.bedrooms is not None else 2) / 3,
        _yes_no(None if listing.bathrooms is None else listing.bathrooms >= 2),
        1.0 if level is not None and level <= 0.5 else 0.0,
        1.0 if level is not None and level >= 4 else 0.0,
        1.0 if listing.floor.floor_class == "top" else 0.0,
        1.0 if listing.floor.floor_class is None else 0.0,
        ((listing.year_built - 1970) / 50) if listing.year_built else 0.0,
        0.0 if listing.year_built else 1.0,
        1.0 if listing.renovated_year and listing.renovated_year >= today.year - 10 else 0.0,
        (energy / 8) if energy is not None else 0.0,
        0.0 if energy is not None else 1.0,
        _yes_no(listing.balcony),
        _yes_no(None if listing.parking is None else listing.parking != "none"),
        _yes_no(listing.lift),
        _yes_no(listing.storage),
        1.0 if listing.metro_walk_min is not None and listing.metro_walk_min <= 10 else 0.0,
        _yes_no(None if listing.condition is None else listing.condition in MOVE_IN_READY),
        1.0 if days is not None and days >= 180 else 0.0,
        rule_score(listing, criteria.preferences),  # the interview's own score: the swipes learn how much it counts
    ]


@dataclass
class Learner:
    weights: list[float]
    bias: float
    means: list[float]
    scales: list[float]
    trained_on: int
    criteria: Criteria
    stats: AreaStats

    @classmethod
    def fit(cls, swipes: list[Swipe], listings: dict[str, Listing], criteria: Criteria, stats: AreaStats,
            today: date | None = None) -> "Learner | None":
        """Train on likes and rejects. None until there are MIN_EACH of each, since one side alone teaches nothing."""
        verdicts = [s for s in swipes if s.decision in ("like", "reject") and s.listing_id in listings]
        rows = [features(listings[s.listing_id], criteria, stats, today) for s in verdicts]
        ys = [1.0 if s.decision == "like" else 0.0 for s in verdicts]
        sample = [REASON_WEIGHT if s.decision == "reject" and s.reasons else 1.0 for s in verdicts]
        likes = sum(ys)
        if likes < MIN_EACH or len(ys) - likes < MIN_EACH:
            return None
        n, k, total = len(rows), len(FEATURES), sum(sample)
        means = [sum(x[j] for x in rows) / n for j in range(k)]
        scales = [max(1e-6, math.sqrt(sum((x[j] - means[j]) ** 2 for x in rows) / n)) for j in range(k)]
        xs = [[(x[j] - means[j]) / scales[j] for j in range(k)] for x in rows]
        w, b = [0.0] * k, 0.0
        for _ in range(STEPS):  # plain gradient descent with an L2 penalty: small data, so it converges in a blink
            grad_w, grad_b = [L2 * wj / total for wj in w], 0.0
            for x, y, weight in zip(xs, ys, sample):
                err = weight * (_sigmoid(b + sum(wj * xj for wj, xj in zip(w, x))) - y)
                grad_b += err / total
                for j in range(k):
                    grad_w[j] += err * x[j] / total
            w = [wj - RATE * gj for wj, gj in zip(w, grad_w)]
            b -= RATE * grad_b
        return cls(w, b, means, scales, n, criteria, stats)

    def probability(self, listing: Listing, today: date | None = None) -> float:
        x = features(listing, self.criteria, self.stats, today)
        z = self.bias + sum(w * max(-CLIP, min(CLIP, (xj - m) / s))
                            for w, xj, m, s in zip(self.weights, x, self.means, self.scales))
        return _sigmoid(z)

    def trust(self) -> float:
        return min(1.0, self.trained_on / FULL_TRUST)

    def blended(self, listing: Listing, today: date | None = None) -> float:
        """The deck's score: the rules' score and the learned probability, mixed by how many verdicts there are."""
        w = self.trust()
        return (1 - w) * rule_score(listing, self.criteria.preferences) + w * self.probability(listing, today)

    def explain(self, top: int = 3) -> list[tuple[str, float]]:
        """The features that move the score most, for "what I've learned" and for interviews."""
        return sorted(zip(FEATURES, self.weights), key=lambda fw: -abs(fw[1]))[:top]

    def summary(self, top: int = 3, floor: float = 0.3) -> dict:
        """For the app: how much of the order the swipes decide, and the clearest leanings in plain words.

        A leaning shows only with 10 or more verdicts and a weight of at least `floor` (on the standardised scale),
        so a handful of swipes doesn't get presented as a taste.
        """
        leans = [] if self.trained_on < 10 else [
            {"feature": f, "words": WORDS[f], "direction": "for" if w > 0 else "against", "weight": round(w, 2)}
            for f, w in self.explain(top) if abs(w) >= floor]
        return {"verdicts": self.trained_on, "share": round(self.trust(), 2), "leans": leans}


def _sigmoid(z: float) -> float:
    if z < -30:
        return 0.0
    if z > 30:
        return 1.0
    return 1 / (1 + math.exp(-z))


def auc(scores: list[float], labels: list[float]) -> float | None:
    """How often a like is scored above a reject (0.5 is chance, 1.0 perfect). Ties count half."""
    pos = [s for s, y in zip(scores, labels) if y == 1]
    neg = [s for s, y in zip(scores, labels) if y == 0]
    if not pos or not neg:
        return None
    wins = sum(1.0 if p > q else 0.5 if p == q else 0.0 for p in pos for q in neg)
    return wins / (len(pos) * len(neg))


def precision_at(scores: list[float], labels: list[float], k: int = 10) -> float | None:
    """The share of likes among the k highest scored homes."""
    if not scores:
        return None
    ranked = sorted(zip(scores, labels), key=lambda sl: -sl[0])[:k]
    return sum(y for _, y in ranked) / len(ranked)
