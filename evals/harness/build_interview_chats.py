"""Write evals/datasets/interview_chats.jsonl: 40 scripted interview chats.

Invented personas only. Each chat has the user's turns in order, the facts a
simulated user can answer from, the criteria a perfect interview would end
with, and the behaviours to check (must_ask, must_say, must_not_invent).

The chats are hand-written; this file is the readable source for the JSONL.
"New build" is year_built from five years back, 2021 in these chats, in both languages (D46).
Mike's rules (D48): "flat" means an apartment or a maisonette, never a detached house or a building;
"studio" means a small apartment of about 30 to 40 m², so studio or apartment, with a size preference up to 40 m².
D53: "around X" is X plus or minus 10%, applied by code, so the assistant no longer asks whether it's the ceiling
(el_01, en_02); "δωμάτια" means bedrooms, so it no longer asks rooms or bedrooms (el_09).

Run: uv run python -m evals.harness.build_interview_chats evals/datasets/interview_chats.jsonl
"""

import json
import sys
from pathlib import Path

OUT = Path(sys.argv[1])

def crit(intent="buy", areas=(), limits=None, prefs=(), questions=()):
    return {"intent": intent, "areas": list(areas), "hard_limits": limits or {}, "preferences": list(prefs), "open_questions": list(questions)}

def pref(feature, weight, **kw):
    return {"feature": feature, "weight": weight, **kw}

C = []

def chat(chat_id, language, persona, tests, turns, facts, expected, must_ask=(), must_say=(), must_not_invent=(), notes=""):
    C.append({
        "chat_id": chat_id, "language": language, "persona": persona, "tests": list(tests),
        "turns": turns, "user_facts": facts, "expected_criteria": expected,
        "must_ask": list(must_ask), "must_say": list(must_say), "must_not_invent": list(must_not_invent), "notes": notes,
    })

# ---------------------------------------------------------------- Greek (20)

chat("el_01", "el", "Ζευγάρι, πρώτο σπίτι, δουλεύουν στο κέντρο", ["ambiguous_budget", "greek_room_count"],
     ["Γεια, ψάχνουμε τριάρι στο Αιγάλεω, γύρω στις 200.", "Μέχρι 200 χιλιάδες, δεν μπορούμε παραπάνω.", "Ναι, διαμέρισμα."],
     {"budget": "Μέχρι 200.000 €, όχι παραπάνω", "type": "Διαμέρισμα", "bedrooms": "Τριάρι, δηλαδή 2 υπνοδωμάτια"},
     crit("buy", ["Egaleo"], {"max_price_eur": 200000, "min_bedrooms": 2, "property_types": ["apartment"]}),
     must_ask=[], must_say=["reply_in:el"], must_not_invent=["min_size_m2", "exclude_floors"],
     notes="'Γύρω στις 200' is ambiguous: ask whether 200k is the ceiling. 'Τριάρι' is three rooms, so 2 bedrooms.")

chat("el_02", "el", "Νέος επαγγελματίας, μόνος", ["greek_room_count", "floor_exclusion"],
     ["Θέλω ένα δυάρι στο Περιστέρι, μέχρι 150.000. Ισόγειο σε καμία περίπτωση."],
     {"budget": "150.000 € max", "floor": "Όχι ισόγειο"},
     crit("buy", ["Peristeri"], {"max_price_eur": 150000, "min_bedrooms": 1, "exclude_floors": ["ground"]}),
     must_say=["reply_in:el"], must_not_invent=["min_size_m2"],
     notes="'Δυάρι' is two rooms, so 1 bedroom. 'Σε καμία περίπτωση' makes the ground floor a hard exclusion. Basements are not mentioned in the opening, so they are not added unless the user confirms.")

chat("el_03", "el", "Φοιτήτρια μεταπτυχιακού με συγκάτοικο", ["rent"],
     ["Ψάχνω για ενοικίαση στο Χαϊδάρι, μέχρι 700 τον μήνα, με δύο υπνοδωμάτια."],
     {"budget": "700 € τον μήνα", "bedrooms": "2"},
     crit("rent", ["Chaidari"], {"max_price_eur": 700, "min_bedrooms": 2}),
     must_say=["reply_in:el"],
     notes="Rent intent; price is monthly.")

chat("el_04", "el", "Οικογένεια με δύο παιδιά", ["vague_age"],
     ["Θέλουμε 3 υπνοδωμάτια στο Περιστέρι, μέχρι 250 χιλιάδες, και να μην είναι πολύ παλιό.", "Ιδανικά μετά το 2000, αλλά δεν είναι απόλυτο."],
     {"budget": "250.000 €", "age": "Ιδανικά χτισμένο μετά το 2000, όχι απόλυτο"},
     crit("buy", ["Peristeri"], {"max_price_eur": 250000, "min_bedrooms": 3}, [pref("year_built", 0.7, min=2000)]),
     must_ask=["year_built"], must_say=["reply_in:el"], must_not_invent=["min_size_m2"],
     notes="'Όχι πολύ παλιό' needs a year. 'Δεν είναι απόλυτο' makes it a preference, not a hard limit.")

chat("el_05", "el", "Δουλεύει στο Σύνταγμα, χωρίς αυτοκίνητο", ["vague_metro"],
     ["Αιγάλεω ή Περιστέρι, μέχρι 180.000, κοντά στο μετρό.", "Το πολύ 10 λεπτά με τα πόδια."],
     {"budget": "180.000 €", "metro": "Μέχρι 10 λεπτά περπάτημα"},
     crit("buy", ["Egaleo", "Peristeri"], {"max_price_eur": 180000}, [pref("metro_walk_min", 0.9, max=10)]),
     must_ask=["metro_minutes"], must_say=["reply_in:el"],
     notes="'Κοντά στο μετρό' needs minutes; the spec default is 10.")

chat("el_06", "el", "Μένει στην Κυψέλη, θέλει να μείνει κοντά", ["unsupported_area"],
     ["Ψάχνω διαμέρισμα στην Κυψέλη ή στο Αιγάλεω, μέχρι 170.000.", "Εντάξει, ας δούμε το Αιγάλεω."],
     {"budget": "170.000 €", "areas": "Κυψέλη ή Αιγάλεω; αν η Κυψέλη δεν καλύπτεται, μόνο Αιγάλεω"},
     crit("buy", ["Egaleo"], {"max_price_eur": 170000, "property_types": ["apartment"]}),
     must_say=["area_not_covered:Κυψέλη", "reply_in:el"],
     notes="Kypseli isn't covered yet. Say so plainly and carry on with Egaleo; never silently drop it.")

chat("el_07", "el", "Αγοραστής με αλλεργία στην υγρασία", ["floor_exclusion"],
     ["Μέχρι 130.000, τουλάχιστον 60 τετραγωνικά, οπουδήποτε από τις τρεις περιοχές. Υπόγειο ή ημιυπόγειο σε καμία περίπτωση."],
     {"budget": "130.000 €", "size": "60 τ.μ. και πάνω"},
     crit("buy", [], {"max_price_eur": 130000, "min_size_m2": 60, "exclude_floors": ["basement", "semi_basement"]}),
     must_say=["reply_in:el"],
     notes="'Οποιαδήποτε από τις τρεις' means no area limit.")

chat("el_08", "el", "Ζευγάρι, διαφορετικές προτεραιότητες", ["partner_wishes"],
     ["Εγώ θέλω οπωσδήποτε μπαλκόνι, η γυναίκα μου θέλει θέση πάρκινγκ. Χαϊδάρι, μέχρι 220.000, δύο υπνοδωμάτια.", "Το πάρκινγκ είναι πολύ σημαντικό για εκείνη, το μπαλκόνι για μένα."],
     {"budget": "220.000 €", "partner": "Εκείνη θέλει πάρκινγκ, εγώ μπαλκόνι, και τα δύο σημαντικά"},
     crit("buy", ["Chaidari"], {"max_price_eur": 220000, "min_bedrooms": 2},
          [pref("balcony", 0.9, equals=True), pref("parking", 0.9, equals=True)],
          ["Are a balcony and parking deal breakers, or strong preferences?"]),
     must_say=["reply_in:el"], must_not_invent=["min_size_m2"],
     notes="Capture both partners' wishes. Neither has a hard-limit field, so they are strong preferences plus an open question.")

chat("el_09", "el", "Αγοραστής που μιλάει καθομιλουμένη", ["budget_slang"],
     ["Έχω ένα 180άρι, θέλω κάτι με δύο δωμάτια στο Περιστέρι.", "Δύο υπνοδωμάτια εννοώ."],
     {"budget": "180.000 €", "rooms": "Δύο υπνοδωμάτια"},
     crit("buy", ["Peristeri"], {"max_price_eur": 180000, "min_bedrooms": 2}),
     must_ask=[], must_say=["reply_in:el"],
     notes="'180άρι' is 180,000 €. 'Δύο δωμάτια' is ambiguous (two bedrooms or a δυάρι), so ask; the scripted answer is two bedrooms.")

chat("el_10", "el", "Ελληνοαυστραλός, αλλάζει γλώσσα", ["language_switch"],
     ["Γεια σας, ψάχνω σπίτι στο Αιγάλεω ή στο Περιστέρι.", "Actually, can we continue in English? Budget up to 220k, at least 75 square metres."],
     {"budget": "220,000 €", "size": "75 m2 minimum"},
     crit("buy", ["Egaleo", "Peristeri"], {"max_price_eur": 220000, "min_size_m2": 75}),
     must_say=["reply_in:en"],
     notes="Switch to English when the user does, and keep the criteria from both languages.")

chat("el_11", "el", "Αγοραστής με αντικρουόμενες απαιτήσεις", ["conflicting_asks"],
     ["Θέλω μεγάλο σπίτι, πάνω από 120 τετραγωνικά, νεόδμητο, κάτω από 150 χιλιάδες, στο Περιστέρι."],
     {"budget": "150.000 €", "size": "120+", "age": "Νεόδμητο αν γίνεται"},
     crit("buy", ["Peristeri"], {"max_price_eur": 150000, "min_size_m2": 120}, [pref("year_built", 0.6, min=2021)]),
     must_say=["tradeoff_with_numbers", "reply_in:el"],
     notes="New builds in Peristeri run well above 2,500 €/m², so 120 m² under 150k is unlikely. Show the trade-off with numbers instead of returning nothing.")

chat("el_12", "el", "Σκέφτεται με βάση τη δόση", ["budget_as_payment"],
     ["Μπορώ να πληρώνω δόση γύρω στα 700 τον μήνα, τι μπορώ να βρω στο Αιγάλεω;", "Δεν ξέρω ακριβώς, ας πούμε μέχρι 170 χιλιάδες τιμή σπιτιού."],
     {"budget": "Δόση 700 €/μήνα, τελικά λέει 170.000 € τιμή"},
     crit("buy", ["Egaleo"], {"max_price_eur": 170000}),
     must_ask=["total_budget"], must_say=["no_mortgage_advice", "reply_in:el"], must_not_invent=["max_price_eur_from_payment"],
     notes="Don't turn a monthly payment into a price yourself (that's mortgage advice); ask for the price ceiling.")

chat("el_13", "el", "Οικογένεια που θέλει αυλή", ["property_types"],
     ["Μεζονέτα ή μονοκατοικία στο Χαϊδάρι, μέχρι 350.000."],
     {"budget": "350.000 €"},
     crit("buy", ["Chaidari"], {"max_price_eur": 350000, "property_types": ["maisonette", "detached_house"]}),
     must_say=["reply_in:el"], must_not_invent=["min_bedrooms"])

chat("el_14", "el", "Αγοράζει για την ηλικιωμένη μητέρα του", ["essential_without_field"],
     ["Θέλω διαμέρισμα για τη μητέρα μου στο Περιστέρι, μέχρι 160.000. Δυσκολεύεται στις σκάλες.", "Ή ισόγειο ή να έχει ασανσέρ, ένα από τα δύο οπωσδήποτε."],
     {"budget": "160.000 €", "access": "Ισόγειο ή ασανσέρ, απαραίτητο"},
     crit("buy", ["Peristeri"], {"max_price_eur": 160000, "property_types": ["apartment"], "max_floor_without_lift": 0}),
     must_ask=["stairs_requirement"], must_say=["reply_in:el"],
     notes="'Ground floor OR a lift' is the no-stairs limit with 0 floors to climb (D73). Before D73 it was a strong lift preference plus an open question, because no limit could express it.")

chat("el_15", "el", "Θέλει να νοικιάσει σε φοιτητές", ["investor_intent"],
     ["Θέλω να αγοράσω κάτι μικρό στο Αιγάλεω για να το νοικιάζω σε φοιτητές, μέχρι 100.000.", "Ναι, είναι επένδυση, δεν θα μείνω εγώ."],
     {"budget": "100.000 €", "purpose": "Επένδυση, ενοικίαση σε φοιτητές"},
     crit("invest", ["Egaleo"], {"max_price_eur": 100000}),
     must_ask=["confirm_investor_mode"], must_say=["no_investment_advice", "reply_in:el"],
     notes="Investor mode only after the user confirms it. No advice on whether it's a good investment.")

chat("el_16", "el", "Ξέρει ακριβώς τι θέλει", ["size_range"],
     ["Διαμέρισμα 70 με 90 τετραγωνικά, Αιγάλεω, μέχρι 190.000, 2 υπνοδωμάτια."],
     {},
     crit("buy", ["Egaleo"], {"max_price_eur": 190000, "min_size_m2": 70, "max_size_m2": 90, "min_bedrooms": 2, "property_types": ["apartment"]}),
     must_say=["reply_in:el"],
     notes="Everything is stated; the agent should ask nothing and go straight to the criteria card.")

chat("el_17", "el", "Δεν θέλει μαστορέματα", ["renovation"],
     ["Θέλω κάτι ανακαινισμένο μετά το 2015, δεν θέλω να κάνω μαστορέματα. Περιστέρι ή Χαϊδάρι, μέχρι 200.000."],
     {"budget": "200.000 €", "renovation": "Ανακαίνιση μετά το 2015"},
     crit("buy", ["Peristeri", "Chaidari"], {"max_price_eur": 200000}, [pref("renovated_year", 0.8, min=2015)]),
     must_say=["reply_in:el"],
     notes="Renovation year is a preference. New builds also satisfy 'no works'; the agent can mention that.")

chat("el_18", "el", "Προσέχει την ενεργειακή κλάση", ["energy_class"],
     ["Θέλω τουλάχιστον Β ενεργειακή κλάση, δύο υπνοδωμάτια, μέχρι 230.000, στο Αιγάλεω."],
     {"budget": "230.000 €"},
     crit("buy", ["Egaleo"], {"max_price_eur": 230000, "min_bedrooms": 2}, [pref("energy_class", 0.8, min="B")]),
     must_say=["reply_in:el"],
     notes="Greek Β is Latin B.")

chat("el_19", "el", "Μπερδεύει τιμή και έξοδα", ["budget_includes_costs"],
     ["Έχω 160 χιλιάδες μαζί με τα έξοδα, ψάχνω στο Χαϊδάρι.", "Σωστά, εννοώ ότι η τιμή του σπιτιού πρέπει να είναι μέχρι 150."],
     {"budget": "160.000 € με τα έξοδα, άρα τιμή ακινήτου μέχρι 150.000 €"},
     crit("buy", ["Chaidari"], {"max_price_eur": 150000}),
     must_ask=["budget_includes_costs"], must_say=["reply_in:el"],
     notes="Purchase costs (tax, notary, agent) sit on top of the price. Ask, don't compute silently.")

chat("el_20", "el", "Απλώς χαζεύει", ["vague_start"],
     ["Τι υπάρχει στο Περιστέρι;", "Για αγορά, μέχρι 250 χιλιάδες, δύο υπνοδωμάτια τουλάχιστον."],
     {"intent": "Αγορά", "budget": "250.000 €", "bedrooms": "2+"},
     crit("buy", ["Peristeri"], {"max_price_eur": 250000, "min_bedrooms": 2}),
     must_ask=["intent", "budget"], must_say=["reply_in:el"],
     notes="Don't search before knowing buy or rent and a budget.")

# ---------------------------------------------------------------- English (20)

chat("en_01", "en", "Spec demo user", ["spec_demo"],
     ["Find me a two bedroom flat in Egaleo under €200k with a balcony."],
     {},
     crit("buy", ["Egaleo"], {"max_price_eur": 200000, "min_bedrooms": 2, "property_types": ["apartment", "maisonette"]}, [pref("balcony", 0.6, equals=True)]),
     must_say=["reply_in:en"], must_not_invent=["min_size_m2", "exclude_floors"],
     notes="The demo query from the spec. 'Under €200k' is read as up to 200,000; a balcony is a wish, not a limit.")

chat("en_02", "en", "Expat couple, first purchase", ["ambiguous_budget"],
     ["We're looking at Peristeri, budget around 200.", "200k is the absolute maximum.", "Two bedrooms please."],
     {"budget": "200,000 € absolute max", "bedrooms": "2"},
     crit("buy", ["Peristeri"], {"max_price_eur": 200000, "min_bedrooms": 2}),
     must_ask=["bedrooms"], must_say=["reply_in:en"])

chat("en_03", "en", "Renter relocating for work", ["rent"],
     ["I want to rent in Peristeri, up to 900 a month, at least 60 square metres."],
     {},
     crit("rent", ["Peristeri"], {"max_price_eur": 900, "min_size_m2": 60}),
     must_say=["reply_in:en"])

chat("en_04", "en", "Buyer wary of old buildings", ["vague_age"],
     ["Something in Chaidari under 230k, not too old.", "Built after 1990 ideally."],
     {"age": "After 1990, ideally"},
     crit("buy", ["Chaidari"], {"max_price_eur": 230000}, [pref("year_built", 0.7, min=1990)]),
     must_ask=["year_built"], must_say=["reply_in:en"])

chat("en_05", "en", "Commuter without a car", ["vague_metro"],
     ["Egaleo, two bedrooms, under 210k, near the metro.", "15 minutes walk at most."],
     {"metro": "15 minutes max on foot"},
     crit("buy", ["Egaleo"], {"max_price_eur": 210000, "min_bedrooms": 2}, [pref("metro_walk_min", 0.9, max=15)]),
     must_ask=["metro_minutes"], must_say=["reply_in:en"])

chat("en_06", "en", "Wants central Athens", ["unsupported_area"],
     ["Kypseli or Pangrati, one bedroom, under 150k.", "OK, which of yours is closest?", "Peristeri then."],
     {"areas": "Kypseli or Pangrati; settles on Peristeri when told those aren't covered"},
     crit("buy", ["Peristeri"], {"max_price_eur": 150000, "min_bedrooms": 1}),
     must_ask=["which_covered_area"], must_say=["area_not_covered:Kypseli", "area_not_covered:Pangrati", "reply_in:en"],
     notes="Say clearly that neither area is covered. Don't silently swap in western suburbs.")

chat("en_07", "en", "Wants light, hates basements", ["floor_exclusion", "no_field"],
     ["No basements, no semi-basements and no ground floor. I want light. Egaleo or Peristeri, under 190k."],
     {},
     crit("buy", ["Egaleo", "Peristeri"], {"max_price_eur": 190000, "exclude_floors": ["basement", "semi_basement", "ground"]}, [],
          ["'Light' isn't a listing field; use a higher floor as a proxy?"]),
     must_say=["reply_in:en"], must_not_invent=["brightness"],
     notes="'Light' has no field. Don't invent one; offer a proxy (floor level, dual aspect) as a question.")

chat("en_08", "en", "Couple split between two areas", ["partner_wishes"],
     ["I'd like Chaidari for the green, my partner prefers Peristeri for the metro. Up to 240k, 2 bedrooms."],
     {"areas": "Both are fine to search"},
     crit("buy", ["Chaidari", "Peristeri"], {"max_price_eur": 240000, "min_bedrooms": 2}, [],
          ["Search both areas and compare, or does one partner's choice win?"]),
     must_say=["reply_in:en"])

chat("en_09", "en", "Greek-English speaker who switches", ["language_switch"],
     ["Hi, I'm looking in Egaleo, up to 180k.", "Μπορούμε να συνεχίσουμε στα ελληνικά; Θέλω δύο υπνοδωμάτια."],
     {"bedrooms": "2"},
     crit("buy", ["Egaleo"], {"max_price_eur": 180000, "min_bedrooms": 2}),
     must_say=["reply_in:el"])

chat("en_10", "en", "Big, cheap and central", ["conflicting_asks"],
     ["I want 4 bedrooms, over 130 square metres, under 160k, close to the metro, in Egaleo.", "10 minutes walk."],
     {"metro": "10 minutes"},
     crit("buy", ["Egaleo"], {"max_price_eur": 160000, "min_bedrooms": 4, "min_size_m2": 130}, [pref("metro_walk_min", 0.7, max=10)]),
     must_ask=["metro_minutes"], must_say=["tradeoff_with_numbers", "reply_in:en"])

chat("en_11", "en", "Thinks in monthly payments", ["budget_as_payment"],
     ["My bank says I can afford 900 a month. What can I get in Peristeri?", "Let's say the flat itself up to 210k."],
     {"budget": "900 €/month, then 210,000 € price"},
     crit("buy", ["Peristeri"], {"max_price_eur": 210000, "property_types": ["apartment", "maisonette"]}),
     must_ask=["total_budget"], must_say=["no_mortgage_advice", "reply_in:en"], must_not_invent=["max_price_eur_from_payment"])

chat("en_12", "en", "Growing family", ["multiple_limits"],
     ["Three bedrooms or more, at least 90 square metres, under 280k, Chaidari or Egaleo."],
     {},
     crit("buy", ["Chaidari", "Egaleo"], {"max_price_eur": 280000, "min_bedrooms": 3, "min_size_m2": 90}),
     must_say=["reply_in:en"])

chat("en_13", "en", "Parent buying for a student", ["implicit_area"],
     ["A small studio for my daughter, she's starting at the University of West Attica. Under 90k.", "Yes, Egaleo is perfect."],
     {"area": "Near the university; Egaleo is fine when suggested"},
     crit("buy", ["Egaleo"], {"max_price_eur": 90000, "property_types": ["studio", "apartment"]}, [pref("size_m2", 0.6, max=40)]),
     must_ask=["confirm_area"], must_say=["reply_in:en"],
     notes="The agent may suggest Egaleo because of the campus, but must confirm before using it.")

chat("en_14", "en", "Only wants new builds", ["no_field"],
     ["New build only, Peristeri, up to 300k, 2 bedrooms."],
     {},
     crit("buy", ["Peristeri"], {"max_price_eur": 300000, "min_bedrooms": 2}, [pref("year_built", 1.0, min=2021)],
          ["'New build only' can't be a hard filter yet; treat as a strong preference?"]),
     must_say=["reply_in:en"], must_not_invent=["condition"],
     notes="Schema gap: no hard 'condition' limit. Record as a strong preference and say so.")

chat("en_15", "en", "Buy to let", ["investor_intent"],
     ["I want to buy something to rent out to students in Egaleo, max 110k.", "Yes, purely an investment."],
     {"purpose": "Investment, renting to students"},
     crit("invest", ["Egaleo"], {"max_price_eur": 110000}),
     must_ask=["confirm_investor_mode"], must_say=["no_investment_advice", "reply_in:en"])

chat("en_16", "en", "Parking is a bonus", ["nice_to_have"],
     ["At least 80 square metres in Chaidari, under 250k. Parking would be a bonus."],
     {},
     crit("buy", ["Chaidari"], {"max_price_eur": 250000, "min_size_m2": 80}, [pref("parking", 0.3, equals=True)]),
     must_say=["reply_in:en"],
     notes="'A bonus' is a low-weight preference, never a limit.")

chat("en_17", "en", "Energy-conscious buyer", ["energy_class"],
     ["Energy class B or better, Egaleo or Peristeri, under 240k."],
     {},
     crit("buy", ["Egaleo", "Peristeri"], {"max_price_eur": 240000}, [pref("energy_class", 0.8, min="B")]),
     must_say=["reply_in:en"])

chat("en_18", "en", "Wants a top floor", ["floor_preference"],
     ["Under 150k anywhere in your three areas, at least 2 bedrooms, top floor ideally."],
     {},
     crit("buy", [], {"max_price_eur": 150000, "min_bedrooms": 2}, [pref("floor_level", 0.6, min=4)]),
     must_say=["reply_in:en"],
     notes="'Ideally' makes it a preference. A ρετιρέ also counts as top.")

chat("en_19", "en", "Changes their mind", ["revision"],
     ["Peristeri, 2 bedrooms, max 200k.", "Actually, make it 220k, I've talked to the bank."],
     {"budget": "220,000 € after revision"},
     {**crit("buy", ["Peristeri"], {"max_price_eur": 220000, "min_bedrooms": 2}), "version": 2},
     must_say=["confirm_change", "reply_in:en"],
     notes="The later turn wins; the criteria card shows the change and asks to confirm.")

chat("en_20", "en", "Has no idea where to start", ["vague_start"],
     ["Help me find a home.", "Buying. Up to 200k.", "Egaleo or Peristeri, 2 bedrooms."],
     {"intent": "Buy", "budget": "200,000 €", "areas": "Egaleo or Peristeri", "bedrooms": "2"},
     crit("buy", ["Egaleo", "Peristeri"], {"max_price_eur": 200000, "min_bedrooms": 2}),
     must_ask=["intent", "budget", "areas"], must_say=["reply_in:en"])

# Mike's rules applied to every chat (D54), so each change is one visible rule rather than 40 hand edits:
# - rentals aren't supported yet: the assistant says so, and the card isn't scored;
# - a purchase that doesn't say whether it's to live in or an investment gets the purpose question;
# - ruling out the basement also rules out the semi-basement, and the ground floor the raised ground.
PURPOSE_STATED = {"el_14", "en_13", "el_15", "en_15"}  # "for my mother", "for my daughter", "to rent out"
FLOOR_FAMILY = {"basement": "semi_basement", "ground": "raised_ground"}
for row in C:
    expected = row["expected_criteria"]
    if expected["intent"] == "rent":
        row["must_say"].append("rent_not_supported")
    elif row["chat_id"] not in PURPOSE_STATED:
        row["must_ask"].append("purpose")
    floors = expected["hard_limits"].get("exclude_floors")
    if floors:
        expected["hard_limits"]["exclude_floors"] = floors + [FLOOR_FAMILY[f] for f in floors if f in FLOOR_FAMILY and FLOOR_FAMILY[f] not in floors]

assert len(C) == 40, len(C)
with OUT.open("w", encoding="utf-8") as fh:
    for row in C:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
print(f"wrote {len(C)} chats to {OUT}")
