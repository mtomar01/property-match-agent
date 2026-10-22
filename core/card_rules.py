"""Mike's rules for turning what a user said into the limits the search runs on (D53, D56).

They're arithmetic, so they live here, in one tested function that the
interview, the MCP server and the web app all call. A model only writes down
what it heard (a price, "around", "ideally"); this module does the sums.
"""

from __future__ import annotations

MARGIN = 0.10  # "around X" means X minus to X plus 10% (Mike, D53)
LOWEST_SHARE = 0.5  # lowest price, half the top: keeps out wrecks and no-price ads, hides little else (Mike, D53, D60)
IDEALLY = ("size", "bedrooms")  # "ιδανικά" before these keeps them limits, widened by code (Mike, D56)
SIZE_MARGIN = 0.10  # ideally 30 to 50 m² searches 27 to 55
BEDROOM_MARGIN = 1  # ideally 1 bedroom searches 0 to 2


def _round(value: float, step: int) -> int:
    return int(round(value / step) * step)


def search_card(raw: dict) -> dict:
    """The card the search runs on: the user's numbers, plus Mike's rules applied by code (D53, D56).

    "Ideally" before a size or a bedroom count keeps it a limit with a margin:
    10% either side for size, one bedroom either side.

    "Around X" searches from X minus 10% to X plus 10% (a range the user gave
    widens the same way). With no minimum from the user, the lowest price is
    half the top price,
    to keep out wrecks and listings with no real price. Rounded to €5,000,
    or €50 for a monthly rent. The model never does this arithmetic.
    """
    limits = dict(raw.get("hard_limits") or {})
    ideally = set(raw.get("ideally") or [])
    if "size" in ideally:  # "ideally 30 to 50 m²": 10% either side (D56)
        if limits.get("min_size_m2"):
            limits["min_size_m2"] = round(limits["min_size_m2"] * (1 - SIZE_MARGIN))
        if limits.get("max_size_m2"):
            limits["max_size_m2"] = round(limits["max_size_m2"] * (1 + SIZE_MARGIN))
    if "bedrooms" in ideally and limits.get("min_bedrooms") is not None:  # "ideally 1 bedroom": one either side
        said = limits["min_bedrooms"]
        limits["max_bedrooms"] = max(limits.get("max_bedrooms") or said, said) + BEDROOM_MARGIN
        limits["min_bedrooms"] = said - BEDROOM_MARGIN if said > BEDROOM_MARGIN else None
    top, low = limits.get("max_price_eur"), limits.get("min_price_eur")
    if not top:
        return {**raw, "hard_limits": limits}
    step = 50 if top < 10_000 else 5000  # a monthly rent or a sale price: the size of the number decides
    if raw.get("budget_around"):
        low = _round(low * (1 - MARGIN), step) if low else _round(top * (1 - MARGIN), step)
        top = _round(top * (1 + MARGIN), step)
    if not low:
        low = _round(top * LOWEST_SHARE, step)
    limits.update(max_price_eur=top, min_price_eur=min(low, top))
    return {**raw, "hard_limits": limits}
