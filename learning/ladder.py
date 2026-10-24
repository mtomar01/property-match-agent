"""The check-in ladder: every 10 likes or rejects, one question, never silence (Mike, D75).

1. A clear pattern code found in the swipes: the assistant puts it with the counts (learning/patterns.py, D66).
2. Otherwise, a reason the user tapped, even once: "You turned one down for needing work. Show homes ready
   to move in first?" The reason is the user's own words, so one tap is enough to ask; nothing changes
   without a yes, and a yes goes through the chat like any other change (D61).
3. Otherwise, a three-tap pulse: "How are these homes so far?" Spot on / Mixed / Not for me. "Mixed" answers
   with a narrowing line built from code's counts; "Not for me" asks what's off.

Steps 2 and 3 are fixed text in Greek or English, in the language of the user's last chat message: no
model call, no wait, no cost. Only step 1 needs the assistant.
"""

from __future__ import annotations

import re
import statistics
from collections import Counter

from core.models import Criteria, Listing, Swipe
from learning.patterns import LOW_FLOORS

GREEKLISH = {"thelo", "psaxno", "spiti", "diamerisma", "mexri", "xiliades", "kai", "einai", "sto", "stin", "ena", "dio",
             "nai", "oxi", "ego", "gia", "na", "me", "kati", "poli", "orofos", "tetragonika"}
FLOOR_WORDS = {"basement": ("basement", "υπόγεια"), "semi_basement": ("semi-basement", "ημιυπόγεια"),
               "ground": ("ground-floor", "ισόγεια"), "raised_ground": ("raised ground-floor", "υπερυψωμένα"),
               "mezzanine": ("mezzanine", "ημιόροφους")}
PULSE = {"en": ("How are these homes so far?", {"spot_on": "Spot on", "mixed": "Mixed", "not_for_me": "Not for me"}),
         "el": ("Πώς σας φαίνονται τα σπίτια μέχρι τώρα;", {"spot_on": "Ακριβώς αυτά", "mixed": "Μέτρια", "not_for_me": "Όχι για μένα"})}
YES_NO = {"en": {"yes": "Yes", "no": "No, just that one"}, "el": {"yes": "Ναι", "no": "Όχι, μόνο αυτό"}}


def language(text: str | None) -> str:
    """Greek or English, from the user's own words (Greek letters, or Greeklish)."""
    text = text or ""
    letters = [c for c in text if c.isalpha()]
    greek = sum(1 for c in letters if "Ͱ" <= c <= "Ͽ" or "ἀ" <= c <= "῿")
    if letters and greek / len(letters) >= 0.5:
        return "el"
    return "el" if len(set(re.findall(r"[a-z]+", text.lower())) & GREEKLISH) >= 2 else "en"


def _homes(n: int, lang: str) -> str:
    if lang == "el":
        return "ένα σπίτι" if n == 1 else f"{n} σπίτια"
    return "one home" if n == 1 else f"{n} homes"


def reason_question(window: list[Swipe], listings: dict[str, Listing], criteria: Criteria, matches: list[Listing],
                    declined: set[str], lang: str) -> dict | None:
    """Step 2: the reason the user tapped most in this window, turned into one question with an exact change."""
    rejects = [s for s in window if s.decision == "reject"]
    counts = Counter(r for s in rejects for r in s.reasons if r not in ("too_dark", "other"))
    for reason, n in counts.most_common():
        key = f"reason:{reason}"
        if key in declined:
            continue
        built = _build(reason, n, rejects, window, listings, criteria, matches, lang)
        if built:
            return {"key": key, **built, "ladder": "reason", "options": YES_NO[lang]}
    return None


def _build(reason: str, n: int, rejects: list[Swipe], window: list[Swipe], listings: dict[str, Listing],
           criteria: Criteria, matches: list[Listing], lang: str) -> dict | None:
    tagged = [listings[s.listing_id] for s in rejects if reason in s.reasons and s.listing_id in listings]
    liked = [listings[s.listing_id] for s in window if s.decision == "like" and s.listing_id in listings]
    homes = _homes(n, lang)
    if reason == "needs_work":
        if any(p.feature == "move_in_ready" for p in criteria.preferences):
            return None
        q = {"en": f"You turned down {homes} for needing work. Show homes that are ready to move in first?",
             "el": f"Απορρίψατε {homes} επειδή ήθελε ανακαίνιση. Να δείχνω πρώτα σπίτια έτοιμα να μπείτε;"}
        say = {"en": "Yes: put homes that are ready to move in first.", "el": "Ναι: δείξε πρώτα σπίτια έτοιμα να μπω."}
        return {"reply": q[lang], "yes_message": say[lang], "feature": "move_in_ready", "kind": "preference",
                "patch": {"preferences": [{"feature": "move_in_ready", "min": None, "max": None, "equals": True, "weight": 0.8}]}}
    if reason == "bad_value":
        per_m2 = [l.price_per_m2 for l in matches if l.price_per_m2]
        if len(per_m2) < 5:
            return None
        line = int(round(statistics.median(per_m2) / 50) * 50)
        q = {"en": f"You turned down {homes} as bad value for money. Put homes under €{line:,}/m², the typical for your search, first?",
             "el": f"Απορρίψατε {homes} ως ακριβά για αυτό που είναι. Να δείχνω πρώτα σπίτια κάτω από €{line:,}/τ.μ., το συνηθισμένο για την αναζήτησή σας;"}
        say = {"en": f"Yes: put homes under €{line:,} per m² first.", "el": f"Ναι: δείξε πρώτα σπίτια κάτω από €{line:,} το τετραγωνικό."}
        return {"reply": q[lang], "yes_message": say[lang], "feature": "price_per_m2", "kind": "preference",
                "patch": {"preferences": [{"feature": "price_per_m2", "min": None, "max": line, "equals": None, "weight": 0.8}]}}
    if reason == "too_expensive":
        prices = [l.price_eur for l in (liked or matches) if l.price_eur]
        if not prices:
            return None
        line = int(round(statistics.median(prices) / 5000) * 5000)
        if criteria.hard_limits.max_price_eur and line >= criteria.hard_limits.max_price_eur:
            return None
        q = {"en": f"You turned down {homes} as too expensive. Put homes under €{line:,} first?",
             "el": f"Απορρίψατε {homes} ως ακριβό. Να δείχνω πρώτα σπίτια κάτω από €{line:,};"}
        say = {"en": f"Yes: put homes under €{line:,} first.", "el": f"Ναι: δείξε πρώτα σπίτια κάτω από €{line:,}."}
        return {"reply": q[lang], "yes_message": say[lang], "feature": "price_eur", "kind": "preference",
                "patch": {"preferences": [{"feature": "price_eur", "min": None, "max": line, "equals": None, "weight": 0.8}]}}
    if reason == "too_small":
        sizes = [l.size_m2 for l in tagged if l.size_m2]
        if not sizes:
            return None
        line = int(max(sizes) // 5 * 5 + 5)
        q = {"en": f"You turned down {homes} as too small. Put homes of {line} m² or more first?",
             "el": f"Απορρίψατε {homes} ως μικρό. Να δείχνω πρώτα σπίτια από {line} τ.μ. και πάνω;"}
        say = {"en": f"Yes: put homes of {line} m² or more first.", "el": f"Ναι: δείξε πρώτα σπίτια από {line} τ.μ. και πάνω."}
        return {"reply": q[lang], "yes_message": say[lang], "feature": "size_m2", "kind": "preference",
                "patch": {"preferences": [{"feature": "size_m2", "min": line, "max": None, "equals": None, "weight": 0.8}]}}
    if reason == "bad_floor":
        floors = [l.floor.floor_class for l in tagged if l.floor.floor_class in LOW_FLOORS
                  and l.floor.floor_class not in criteria.hard_limits.exclude_floors]
        if not floors:
            return None
        floor = Counter(floors).most_common(1)[0][0]
        en, el = FLOOR_WORDS[floor]
        q = {"en": f"You turned down {homes} for the floor. Leave out {en} homes?",
             "el": f"Απορρίψατε {homes} λόγω ορόφου. Να βγάλω τα {el};"}
        say = {"en": f"Yes: rule out {en} homes.", "el": f"Ναι: βγάλε τα {el}."}
        return {"reply": q[lang], "yes_message": say[lang], "feature": "floor", "kind": "limit",
                "patch": {"hard_limits": {"exclude_floors": [*criteria.hard_limits.exclude_floors, floor]}}}
    if reason == "wrong_area":
        areas = Counter(l.area for l in tagged if l.area)
        if not areas:
            return None
        area = areas.most_common(1)[0][0]
        covered = list(criteria.areas or [])
        if covered and area not in covered:
            return None
        q = {"en": f"You turned down {homes} for the area. Leave {area} out of the search?",
             "el": f"Απορρίψατε {homes} λόγω περιοχής. Να βγάλω την περιοχή {area} από την αναζήτηση;"}
        say = {"en": f"Yes: leave {area} out.", "el": f"Ναι: βγάλε την περιοχή {area}."}
        return {"reply": q[lang], "yes_message": say[lang], "feature": "area", "kind": "limit", "patch": {"remove_area": area}}
    return None


def pulse_question(lang: str, count: int) -> dict:
    question, options = PULSE[lang]
    return {"key": f"pulse:{count}", "reply": question, "ladder": "pulse", "options": options, "feature": None,
            "kind": "pulse", "patch": {}}


def narrowing_line(matches: list[Listing], lang: str) -> str:
    """The answer to "Mixed": how the homes split, from code's counts, and an invitation to say what matters."""
    total = len(matches)
    small = sum(1 for l in matches if l.size_m2 and l.size_m2 < 70)
    parking = sum(1 for l in matches if l.parking in ("pilotis", "space", "garage"))
    lift = sum(1 for l in matches if l.lift is True)
    if lang == "el":
        def el(n: int, one: str, many: str) -> str:
            return f"το 1 {one}" if n == 1 else f"τα {n} {many}"
        return (f"Από τα {total} σπίτια της αναζήτησης, {el(small, 'είναι', 'είναι')} κάτω από 70 τ.μ., "
                f"{el(parking, 'έχει', 'έχουν')} πάρκινγκ και {el(lift, 'έχει', 'έχουν')} ασανσέρ. "
                "Πείτε μου τι μετράει περισσότερο και θα τα βάλω πρώτα.")

    def en(n: int, one: str, many: str) -> str:
        return f"{n} {one if n == 1 else many}"
    return (f"Of the {total} homes in your search, {en(small, 'is', 'are')} under 70 m², {en(parking, 'has', 'have')} parking "
            f"and {en(lift, 'has', 'have')} a lift. Tell me what matters most and I'll put those first.")


NOT_FOR_ME = {"en": "What's off? Tell me in a few words and I'll change the search.",
              "el": "Τι δεν σας ταιριάζει; Πείτε μου με λίγα λόγια και θα αλλάξω την αναζήτηση."}
SPOT_ON = {"en": "Great, carry on.", "el": "Τέλεια, συνεχίστε."}
