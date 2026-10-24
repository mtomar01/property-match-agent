"""Generate the public synthetic snapshot: 60 made-up listings.

Why synthetic data in the public repo: real listings belong to the portals and
the agencies (spec section 3), so the repo ships invented ones with the same
structure. Anyone can then run every eval without touching a live site.

What the generator builds on purpose:
- 3 areas (Egaleo, Peristeri, Chaidari) and 3 sources (spitogatos, xe, spiti24)
- 12 duplicates of 48 unique properties. spiti24 copies of Spitogatos listings
  are near exact (same group, same agency feed). xe copies are reworded, with
  a slightly different price and size, which is the hard case in spec section 11.
- Edge cases for hard limits: a price exactly on a budget, a size exactly on a
  minimum, a price on request, unknown bedrooms, unknown floor, basements.
- Messy Greek descriptions: capitals, missing accents, abbreviations and the
  common "πυλωτή" misspelling.

It's deterministic (fixed seed), so the evals give the same numbers every run.
URLs use the reserved .invalid domain so they can never point at a real listing.

Run: uv run python -m core.synthetic
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from core import greek
from core.models import DuplicateCluster, Listing

SEED = 2026
TODAY = date(2026, 10, 20)
OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "synthetic"

SUB_AREAS = {
    "Egaleo": ["Λιούμη", "Σωτηράκη", "Εσταυρωμένου", "Ιεράπολη", "Κέντρο"],
    "Peristeri": ["Νέα Ζωή", "Κέντρο", "Μπουρνάζι", "Νέα Σεπόλια", "Ανθούπολη"],
    "Chaidari": ["Δάσος", "Αγία Γρηγορούσα", "Προφήτης Ηλίας", "Δαφνί", "Αστυθέα"],
}
AREA_GREEK = {"Egaleo": "Αιγάλεω", "Peristeri": "Περιστέρι", "Chaidari": "Χαϊδάρι"}
PRICE_PER_M2 = {"Egaleo": (1800, 3000), "Peristeri": (1700, 3200), "Chaidari": (1700, 3000)}

FLOOR_WORDS = {
    "basement": ["υπόγειο", "ΥΠΟΓΕΙΟ", "υπογειο"],
    "semi_basement": ["ημιυπόγειο", "ΗΜΙΥΠΟΓΕΙΟ", "ημιυπογειο"],
    "ground": ["ισόγειο", "ΙΣΟΓΕΙΟ", "ισογειο"],
    "raised_ground": ["υπερυψωμένο ισόγειο", "υπερυψωμενο"],
    "1": ["1ος όροφος", "1ου ορόφου", "1ος"],
    "2": ["2ος όροφος", "2ου ορόφου", "2ος"],
    "3": ["3ος όροφος", "3ου ορόφου", "3ος"],
    "4": ["4ος όροφος", "4ου ορόφου", "4ος"],
    "5": ["5ος όροφος", "5ος"],
    "top": ["ρετιρέ", "ΡΕΤΙΡΕ", "ρετιρε"],
}
HEATING_WORDS = {
    ("independent", "gas"): ["αυτόνομη θέρμανση φυσικού αερίου", "Αυτόνομη, φυσικό αέριο", "ατομικός λέβητας φυσικού αερίου"],
    ("independent", "oil"): ["αυτόνομη θέρμανση πετρελαίου", "Αυτονομη με πετρελαιο"],
    ("independent", "heat_pump"): ["ατομική θέρμανση με αντλία θερμότητας", "αντλία θερμότητας (αυτόνομη)"],
    ("central", "oil"): ["κεντρική θέρμανση πετρελαίου", "ΚΕΝΤΡΙΚΗ ΘΕΡΜΑΝΣΗ ΠΕΤΡΕΛΑΙΟ"],
}
PARKING_WORDS = {"pilotis": ["θέση πιλοτής", "parking πυλωτής", "πιλοτή"], "garage": ["θέση σε υπόγειο γκαράζ"], "space": ["θέση στάθμευσης"]}
ENERGY_GREEK = {"A+": "Α+", "A": "Α", "B+": "Β+", "B": "Β", "C": "Γ", "D": "Δ", "E": "Ε", "F": "Ζ", "G": "Η"}


@dataclass
class Property:
    """A real-world property before it's listed on a portal."""

    key: str
    area: str
    sub_area: str
    property_type: str
    size_m2: float
    bedrooms: int | None
    bathrooms: int
    floor_class: str | None
    year_built: int
    renovated_year: int | None
    condition: str | None
    energy: str | None
    heating: tuple[str, str] | None
    parking: str | None
    lift: bool
    balcony: bool
    storage: bool
    flags: list[str]
    metro_walk_min: int | None
    price_eur: int | None
    listing_type: str = "sale"
    photo_hashes: list[str] = field(default_factory=list)


def _hash(rng: random.Random) -> str:
    return "%016x" % rng.getrandbits(64)


def _base_properties(rng: random.Random) -> list[Property]:
    props: list[Property] = []
    areas = ["Egaleo", "Peristeri", "Chaidari"]
    for i in range(48):
        area = areas[i % 3]
        ptype = rng.choices(["apartment", "maisonette", "detached_house", "studio"], weights=[80, 8, 6, 6])[0]
        size = {"studio": rng.randint(28, 40), "maisonette": rng.randint(95, 150), "detached_house": rng.randint(80, 180)}.get(
            ptype, rng.randint(45, 125)
        )
        bedrooms = 1 if ptype == "studio" else max(1, min(4, round(size / 32)))
        floor_class = rng.choices(
            ["basement", "semi_basement", "ground", "raised_ground", "1", "2", "3", "4", "5", "top"],
            weights=[3, 6, 10, 6, 16, 16, 14, 10, 5, 6],
        )[0]
        if ptype == "detached_house":
            floor_class = "ground"
        if ptype == "maisonette":
            floor_class = rng.choice(["1", "2", "3"])
        year = rng.choice([1965, 1970, 1974, 1978, 1981, 1985, 1990, 1996, 2003, 2008, 2024, 2025])
        renovated = None
        condition = None
        if year >= 2024:
            condition = "new_build"
        elif rng.random() < 0.4:
            renovated = rng.choice([2015, 2018, 2019, 2021, 2023, 2025])
            condition = "renovated"
        elif rng.random() < 0.25:
            condition = "needs_work"
        energy = rng.choice(["A+", "B", "C", "D", "E", "G", None, "pending"]) if year < 2024 else "A+"
        heating = rng.choice(list(HEATING_WORDS)) if rng.random() < 0.9 else None
        low, high = PRICE_PER_M2[area]
        ppm = rng.randint(low, high)
        if condition == "new_build":
            ppm = int(ppm * 1.35)
        if condition == "needs_work":
            ppm = int(ppm * 0.7)
        if floor_class in ("basement", "semi_basement"):
            ppm = int(ppm * 0.65)
        price = int(round(size * ppm / 1000) * 1000)
        props.append(
            Property(
                key=f"P{i:02d}",
                area=area,
                sub_area=rng.choice(SUB_AREAS[area]),
                property_type=ptype,
                size_m2=float(size),
                bedrooms=bedrooms,
                bathrooms=1 if size < 100 else 2,
                floor_class=floor_class,
                year_built=year,
                renovated_year=renovated,
                condition=condition,
                energy=energy,
                heating=heating,
                parking=rng.choice(["pilotis", "space", "garage", None, None]),
                lift=floor_class not in ("basement", "semi_basement", "ground") and rng.random() < 0.7,
                balcony=floor_class not in ("basement", "semi_basement") and rng.random() < 0.75,
                storage=rng.random() < 0.4,
                flags=[f for f, p in (("dual_aspect", 0.35), ("corner", 0.2)) if rng.random() < p],
                metro_walk_min=rng.choice([3, 5, 7, 8, 10, 12, 15, 20, None]),
                price_eur=price,
                photo_hashes=[_hash(rng) for _ in range(3)],
            )
        )

    # Deliberate edge cases for the hard-limit evals.
    edge = props[0]  # Egaleo
    edge.property_type, edge.size_m2, edge.bedrooms, edge.floor_class, edge.price_eur = "apartment", 70.0, 2, "2", 200000
    props[3].property_type, props[3].size_m2, props[3].bedrooms, props[3].floor_class, props[3].price_eur = (
        "apartment", 69.0, 2, "3", 175000)
    props[6].price_eur = None  # price on request
    props[9].bedrooms = None  # bedrooms not stated
    props[12].floor_class = None  # floor not stated
    props[15].property_type, props[15].floor_class, props[15].size_m2, props[15].bedrooms, props[15].price_eur = (
        "apartment", "semi_basement", 82.0, 2, 98000)
    props[18].property_type, props[18].floor_class, props[18].size_m2, props[18].bedrooms, props[18].price_eur = (
        "apartment", "basement", 75.0, 2, 72000)
    props[21].property_type, props[21].size_m2, props[21].bedrooms, props[21].floor_class, props[21].price_eur = (
        "apartment", 85.0, 2, "1", 201000)  # just over a 200k budget
    # Cheap basements are old buildings: keep the edge cases realistic.
    for idx, year, energy in ((15, 1978, "E"), (18, 1972, "G")):
        props[idx].year_built, props[idx].energy, props[idx].condition, props[idx].renovated_year = year, energy, None, None
        props[idx].lift, props[idx].balcony = False, False

    # Six rentals, monthly rent in price_eur.
    for idx in (30, 31, 32, 33, 34, 35):
        p = props[idx]
        p.listing_type = "rent"
        p.property_type = "apartment"
        p.size_m2 = float(rng.randint(45, 95))
        p.bedrooms = max(1, round(p.size_m2 / 35))
        p.price_eur = int(round(p.size_m2 * rng.uniform(9.0, 13.5) / 10) * 10)
    return props


def _describe(p: Property, rng: random.Random, style: str) -> str:
    """Write a messy Greek description. style is 'agency', 'portal' or 'owner'."""
    type_word = {
        "apartment": rng.choice(["διαμέρισμα", "Διαμέρισμα", "ΔΙΑΜΕΡΙΣΜΑ"]),
        "studio": "γκαρσονιέρα",
        "maisonette": rng.choice(["μεζονέτα", "ΜΕΖΟΝΕΤΑ"]),
        "detached_house": "μονοκατοικία",
    }[p.property_type]
    deal = "ενοικιάζεται" if p.listing_type == "rent" else rng.choice(["πωλείται", "Πωλείται", "ΠΩΛΕΙΤΑΙ"])
    size = rng.choice([f"{p.size_m2:g} τ.μ.", f"{p.size_m2:g}τμ", f"{p.size_m2:g} τετραγωνικά"])
    parts: list[str] = []
    area_bit = f"{AREA_GREEK[p.area]} - {p.sub_area}" if rng.random() < 0.7 else p.sub_area
    floor_bit = rng.choice(FLOOR_WORDS[p.floor_class]) if p.floor_class else ""

    if style == "portal":
        parts.append(f"{type_word.capitalize()} προς {'ενοικίαση' if p.listing_type == 'rent' else 'πώληση'}, {area_bit}.")
        parts.append(f"Εμβαδόν {size}" + (f", {floor_bit}." if floor_bit else "."))
    else:
        opener = f"{deal} {type_word} {size}"
        if floor_bit:
            opener += f" {floor_bit}"
        opener += f" στην περιοχή {area_bit}."
        parts.append(opener if style == "agency" else opener.lower())

    if p.bedrooms is not None:
        parts.append(rng.choice([f"{p.bedrooms} υ/δ", f"{p.bedrooms} Υ/Δ", f"{p.bedrooms} υπνοδωμάτια"]) + f", {p.bathrooms} μπάνιο.")
    else:
        parts.append("Διαθέτει σαλόνι, κουζίνα και μπάνιο.")
    if p.condition == "new_build":
        parts.append(rng.choice(["Νεόδμητο", "ΝΕΟΔΜΗΤΟ", "νεόδμητη κατασκευή"]) + f" {p.year_built}.")
    else:
        parts.append(rng.choice([f"Κατασκευή {p.year_built}.", f"Έτος κατασκευής: {p.year_built}.", f"κατασκευης {p.year_built}"]))
    if p.renovated_year:
        parts.append(rng.choice([f"Ανακαινισμένο το {p.renovated_year}.", f"ανακαινιση {p.renovated_year}", f"πλήρως ανακαινισμένο ({p.renovated_year})."]))
    if p.condition == "needs_work":
        parts.append(rng.choice(["Χρήζει ανακαίνισης.", "χρηζει ανακαινισης", "θέλει ανακαίνιση"]))
    if p.heating:
        parts.append(rng.choice(HEATING_WORDS[p.heating]).capitalize() + ".")
    if p.energy == "pending":
        parts.append("ΠΕΑ: υπό έκδοση.")
    elif p.energy:
        parts.append(rng.choice([f"ΠΕΑ: {ENERGY_GREEK[p.energy]}", f"Ενεργειακή κλάση {ENERGY_GREEK[p.energy]}"]) + ".")
    extras = []
    if "dual_aspect" in p.flags:
        extras.append(rng.choice(["διαμπερές", "ΔΙΑΜΠΕΡΕΣ"]))
    if "corner" in p.flags:
        extras.append("γωνιακό")
    if p.lift:
        extras.append(rng.choice(["ασανσέρ", "ανελκυστήρας"]))
    if p.balcony:
        extras.append(rng.choice(["μπαλκόνια", "βεράντα"]))
    if p.storage:
        extras.append("αποθήκη")
    if p.parking:
        extras.append(rng.choice(PARKING_WORDS[p.parking]))
    if extras:
        parts.append("Διαθέτει " + ", ".join(extras) + ".")
    if p.metro_walk_min is not None:
        parts.append(rng.choice([f"{p.metro_walk_min} λεπτά από το μετρό.", f"Μετρό σε {p.metro_walk_min}'", f"κοντά στο μετρό ({p.metro_walk_min} λεπτά με τα πόδια)"]))
    if p.price_eur is None:
        parts.append("Τιμή κατόπιν επικοινωνίας.")
    return " ".join(parts)


def _to_listing(p: Property, source: str, number: int, rng: random.Random, *, price: int | None, size: float, text: str,
                hashes: list[str], first_seen: date, published: date | None = None) -> Listing:
    listing_id = f"{source}:SYN{number:04d}"
    title_type = {"apartment": "Διαμέρισμα", "studio": "Γκαρσονιέρα", "maisonette": "Μεζονέτα", "detached_house": "Μονοκατοικία"}[p.property_type]
    return Listing(
        listing_id=listing_id,
        source=source,
        url=f"https://synthetic.invalid/{source}/SYN{number:04d}",
        listing_type=p.listing_type,
        synthetic=True,
        first_seen=first_seen,
        last_seen=TODAY,
        published=published,
        price_eur=price,
        size_m2=size,
        property_type=p.property_type,
        bedrooms=p.bedrooms,
        bathrooms=p.bathrooms,
        floor={"raw": FLOOR_WORDS[p.floor_class][0] if p.floor_class else None, "class": p.floor_class},
        year_built=p.year_built,
        renovated_year=p.renovated_year,
        condition=p.condition,
        energy_class={"raw": "υπό έκδοση" if p.energy == "pending" else ENERGY_GREEK.get(p.energy or ""), "value": p.energy},
        heating={"raw": HEATING_WORDS[p.heating][0], "type": p.heating[0], "fuel": p.heating[1]} if p.heating else {},
        parking=p.parking,
        lift=p.lift,
        balcony=p.balcony,
        storage=p.storage,
        flags=p.flags,
        area=p.area,
        sub_area=p.sub_area,
        metro_walk_min=p.metro_walk_min,
        photo_hashes=hashes,
        title=f"{title_type}, {size:g}τ.μ., {p.sub_area} ({AREA_GREEK[p.area]})",
        description=text,
    )


def generate(seed: int = SEED) -> tuple[list[Listing], list[DuplicateCluster]]:
    rng = random.Random(seed)
    # Published dates come from their own generator, so adding them (D74) left every other field as it was.
    dates = random.Random(seed + 1)
    props = _base_properties(rng)
    sources = ["spitogatos", "xe", "spiti24"]
    listings: list[Listing] = []
    by_key: dict[str, list[Listing]] = {}
    number = 1

    def add(p: Property, source: str, **kw) -> None:
        nonlocal number
        if dates.random() < 0.85:  # most real pages state when the ad went up; some don't
            kw["published"] = kw["first_seen"] - timedelta(days=min(900, int(dates.expovariate(1 / 120))))
        listing = _to_listing(p, source, number, rng, **kw)
        number += 1
        listings.append(listing)
        by_key.setdefault(p.key, []).append(listing)

    originals: dict[str, tuple[str, str]] = {}
    for i, p in enumerate(props):
        source = sources[i % 3]
        style = {"spitogatos": "portal", "xe": "agency", "spiti24": "owner"}[source]
        text = _describe(p, rng, style)
        first_seen = TODAY - timedelta(days=rng.randint(0, 60))
        add(p, source, price=p.price_eur, size=p.size_m2, text=text, hashes=p.photo_hashes, first_seen=first_seen)
        originals[p.key] = (source, text)

    # 12 duplicates: 6 near exact spiti24 copies of Spitogatos listings,
    # 6 reworded xe copies of Spitogatos or spiti24 listings.
    spitogatos_keys = [p.key for p in props if originals[p.key][0] == "spitogatos" and p.listing_type == "sale"]
    other_keys = [p.key for p in props if originals[p.key][0] in ("spitogatos", "spiti24") and p.listing_type == "sale"
                  and p.price_eur is not None and p.key not in spitogatos_keys[:6]]
    prop_by_key = {p.key: p for p in props}
    for key in spitogatos_keys[:6]:
        p = prop_by_key[key]
        _, text = originals[key]
        add(p, "spiti24", price=p.price_eur, size=p.size_m2, text=text, hashes=p.photo_hashes,
            first_seen=TODAY - timedelta(days=rng.randint(0, 30)))
    for key in other_keys[:6]:
        p = prop_by_key[key]
        price = int(round(p.price_eur * rng.uniform(0.95, 1.08) / 1000) * 1000)
        size = p.size_m2 + rng.choice([-1, 0, 1, 2])
        text = _describe(p, rng, "agency")
        hashes = [p.photo_hashes[0], _hash(rng), _hash(rng)]  # one shared photo, rest new
        add(p, "xe", price=price, size=size, text=text, hashes=hashes, first_seen=TODAY - timedelta(days=rng.randint(0, 30)))

    clusters = []
    for key, group in by_key.items():
        if len(group) > 1:
            prices = [l.price_eur for l in group if l.price_eur]
            clusters.append(DuplicateCluster(
                cluster_id=f"truth-{key}",
                listing_ids=[l.listing_id for l in group],
                price_min_eur=min(prices) if prices else None,
                price_max_eur=max(prices) if prices else None,
                decided_by="human",
            ))
    return listings, clusters


def write(out_dir: Path = OUT_DIR) -> Path:
    listings, clusters = generate()
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "listings.jsonl"
    with path.open("w", encoding="utf-8") as fh:
        for listing in listings:
            fh.write(json.dumps(listing.model_dump(by_alias=True, mode="json"), ensure_ascii=False) + "\n")
    truth = [c.model_dump(mode="json") for c in clusters]
    (out_dir / "duplicates_truth.json").write_text(json.dumps(truth, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    written = write()
    listings, clusters = generate()
    by_source = {s: sum(l.source == s for l in listings) for s in ("spitogatos", "xe", "spiti24")}
    by_area = {a: sum(l.area == a for l in listings) for a in greek.AREA_ALIASES}
    print(f"Wrote {len(listings)} listings to {written}")
    print(f"By source: {by_source}")
    print(f"By area: {by_area}")
    print(f"Duplicate clusters: {len(clusters)}")
