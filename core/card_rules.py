"""Mike's rules for turning what a user said into the limits the search runs on (D53, D56, D79).

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


# D79, the table Mike agreed on 25 October: a wish the user states outright ("firm") becomes a hard limit when the
# listings reliably state that field. On the 23 October dataset: floor 99%, bathrooms 98%, lift 97%, year built 94%,
# storage 93% and parking 91% state it; balcony and a recent renovation are rarely left unsaid when true (758 of the
# 759 that mention a balcony have one). Move in ready (71%, the silent ones genuinely mixed) and metro minutes (19%)
# stay wishes, and so does anything said with "ideally". One user's firm wish never loosens a stricter limit.
MUST_HAVE = ("parking", "lift", "balcony", "storage", "furnished")
# D104: furnished is a must only in a rent search. 92% of pages tick or cross it, but the 23 October sale file was
# built before the field existed, and a buyer's furniture is a separate deal anyway, so for a purchase it stays a wish.
RENT_ONLY_MUSTS = ("furnished",)


def hard_form(preference: dict) -> list[tuple[str, object]]:
    """The hard limits a firm wish becomes, or [] if it stays a wish."""
    feature = preference.get("feature")
    low, high = preference.get("min"), preference.get("max")
    if feature in MUST_HAVE and preference.get("equals") is True:
        return [("must_have", feature)]
    if feature == "bathrooms" and low is not None:
        return [("min_bathrooms", int(low))]
    if feature == "year_built" and low is not None:
        return [("min_year_built", int(low))]
    if feature == "renovated_year" and low is not None:
        return [("min_renovated_year", int(low))]
    if feature == "floor_level":
        return [(name, float(value)) for name, value in (("min_floor_level", low), ("max_floor_level", high))
                if isinstance(value, (int, float))]
    return []


def harden(raw: dict) -> dict:
    """Firm wishes on fields the listings reliably state, moved into the hard limits. The rest stay wishes."""
    limits = dict(raw.get("hard_limits") or {})
    kept, moved = [], []
    for preference in raw.get("preferences") or []:
        targets = hard_form(preference) if preference.get("firm") else []
        if preference.get("feature") in RENT_ONLY_MUSTS and raw.get("intent") != "rent":
            targets = []
        types = preference.get("only_for_types") or []
        if isinstance(types, str):  # the interview writes them comma separated (D86)
            types = [t for t in types.replace(",", " ").split() if t]
        if types:
            # D86: a must for some property types only. Only the yes/no musts can be tied to a type; anything else
            # tied to one ("renovated if it's a house") can't be promised, so it stays a wish.
            if [name for name, _ in targets] != ["must_have"]:
                kept.append(preference)
                continue
            by_type = {k: list(v) for k, v in (limits.get("must_have_if_type") or {}).items()}
            for kind in types:
                by_type[kind] = sorted({*by_type.get(kind, []), preference["feature"]})
            limits["must_have_if_type"] = by_type
            moved.append(preference["feature"])
            continue
        if not targets:
            kept.append(preference)
            continue
        for name, value in targets:
            if name == "must_have":
                limits["must_have"] = sorted({*(limits.get("must_have") or []), value})
            elif limits.get(name) is None:
                limits[name] = value
            else:  # two asks for one field: the stricter one holds
                limits[name] = max(limits[name], value) if name.startswith("min_") else min(limits[name], value)
        moved.append(preference["feature"])
    return {**raw, "hard_limits": limits, "preferences": kept, "from_wishes": moved}


def _round(value: float, step: int) -> int:
    return int(round(value / step) * step)


def search_card(raw: dict) -> dict:
    """The card the search runs on: the user's numbers, plus Mike's rules applied by code (D53, D56, D79).

    Firm wishes on reliably stated fields become hard limits first (D79).

    "Ideally" before a size or a bedroom count keeps it a limit with a margin:
    10% either side for size, one bedroom either side.

    "Around X" searches from X minus 10% to X plus 10% (a range the user gave
    widens the same way). With no minimum from the user, the lowest price is
    half the top price,
    to keep out wrecks and listings with no real price. Rounded to €5,000,
    or €50 for a monthly rent. The model never does this arithmetic.
    """
    raw = harden(raw)
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
