// Every word the app shows, in English and Greek, in one plain dictionary (D96): no library, the two columns
// side by side so a missing line is a type error. The card's own lines (reasons, market facts) come worded from
// the server; what is here is the shell, the controls and the words for the codes the search uses.

import { createContext, useContext } from "react";
import { Card, HardLimits, Preference, SearchSummary } from "./api";

export type Lang = "en" | "el";
export type LangPref = "auto" | Lang;
export type Theme = "system" | "light" | "dark";

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

export const LABELS = {
  en: {
    lang: "en" as Lang,
    locale: "en-GB",
    // the shell
    app: "Tispi",
    newSearch: "New search",
    searches: "Searches",
    yourSearches: "Your searches",
    hideSearches: "Hide the searches",
    options: "Options",
    chat: "Chat",
    homes: "Homes",
    shortlist: "Shortlist",
    views: "Views",
    allAreas: "All areas",
    limits: "Limits",
    details: "details",
    close: "Close",
    today: "Today",
    wish: (n: number) => plural(n, "wish", "wishes"),
    homesCount: (n: number) => plural(n, "home", "homes"),
    verdictsCount: (n: number) => plural(n, "verdict", "verdicts"),
    shortlistedCount: (n: number) => `${n} shortlisted`,
    swipedLine: (swiped: number, liked: number) => `${swiped} swiped · ${liked} liked`,
    likeRate: (pct: number) => `${pct}% like rate`,
    checkinIn: (n: number) => `check-in in ${n}`,
    limitsHint: "Hard limits are checked in code and never broken. Wishes only rank. To change anything, tell Tispi in the chat.",
    covers: (areas: string[], data: string) => `Covers ${areas.join(", ")} · ${data}`,
    // the chat
    chatNew: "Tell Tispi what you're looking for",
    chatChange: "Change anything by chat",
    chatIntro: "Write the way you'd tell a friend, in Greek or English. It asks only what it needs, then the homes come up.",
    starters: ["A two bedroom flat in Egaleo, around 200k, with a balcony.", "Ψάχνω δυάρι στο Περιστέρι, μέχρι 160.000.", "A furnished one bedroom in Kypseli, up to €700 a month."],
    // D104: two chips that start a search, and two answers to "to live in or as an investment?". A tap sends the
    // words below as the user's own message, so the assistant still decides everything from the chat.
    buyChip: "Buy", rentChip: "Rent", buySays: "I want to buy", rentSays: "I want to rent",
    liveChip: "To live in", investChip: "As an investment",
    thinking: "Thinking…",
    yourMessage: "Your message",
    writeHere: "Write here…",
    changeHere: "e.g. make it 220k, or add Peristeri",
    send: "Send",
    // the deck
    loadingHomes: "Loading the homes…",
    nothingPasses: "Nothing passes every limit",
    seenAll: "You've seen every home that passes",
    backToLast: "Back to the last one",
    passLine: (n: number) => `${plural(n, "home passes", "homes pass")} the limits on the bar.`,
    widenHint: "Code counted a few ways to widen the search; pick one and Tispi will make the change.",
    tellWhat: "Tell Tispi what to change.",
    widenNone: "Widening one step doesn't add any. Tell Tispi what matters least.",
    swipeDeck: "Swipe deck",
    skippedBefore: "You skipped this one earlier.",
    theMarket: "The market",
    openOn: (source: string) => `Open on ${source} ↗`,
    syntheticListing: "Synthetic listing (no real page)",
    synthetic: "synthetic",
    noPhoto: "no photo link saved",
    home: "home",
    listedTimes: (times: number) => (times === 2 ? "Listed twice" : `Listed ${times} times`),
    listedRange: (times: string, lo: string, hi: string, cheapest: boolean) => `${times}, ${lo} to ${hi}${cheapest ? "; this is the cheapest" : ""}`,
    listedSame: (times: string) => `${times} at the same price`,
    previous: "Back to the previous home",
    previousTitle: "Back to the previous home (Backspace)",
    reject: "Reject",
    rejectTitle: "Reject (←)",
    like: "Like",
    likeTitle: "Like (→)",
    skip: "Skip this home for now",
    skipTitle: "Skip for now; it comes back later (↓)",
    cantJudge: "Can't judge this one?",
    leftSwiped: (left: number, swiped: number) => `${left} left · ${swiped} swiped`,
    learningBefore: "Order: your wishes from the chat. Your swipes start counting after 3 likes and 3 rejects.",
    learningShare: (pct: number, verdicts: number) => `Order: ${pct}% from your ${verdicts} likes and rejects`,
    countingFor: "counting for",
    against: "against",
    orderAsked: (order: string) => `Order: ${order}, as you asked. Your wishes only decide between equals.`,
    orders: { price_per_m2_asc: "cheapest €/m² first", price_eur_asc: "cheapest first", price_eur_desc: "dearest first", size_m2_desc: "biggest first",
      year_built_desc: "newest build first", days_on_market_desc: "longest on the market first", first_seen_desc: "newest listings first" } as Record<string, string>,
    whyNot: "Why not? One tap is enough; it teaches the ranking more than the swipe.",
    whatStops: "What stops you deciding? This one won't count as a like or a reject, and it comes back later.",
    other: "Other…",
    noReason: "No reason",
    keepLooking: "Keep looking at it",
    inYourWords: "In your words",
    rejectWords: "In your words, e.g. the street looks busy",
    skipWords: "In your words, e.g. only a floor plan",
    save: "Save",
    rejectReasons: [["too_dark", "Too dark"], ["too_small", "Too small"], ["bad_floor", "Bad floor"], ["needs_work", "Needs work"],
      ["too_expensive", "Too expensive"], ["bad_value", "Bad value for money"], ["wrong_area", "Wrong area"]] as [string, string][],
    cantJudgeReasons: [["photos_unclear", "Photos don't show it"], ["too_little_info", "Too little information"]] as [string, string][],
    // the check-in
    question: "A question from Tispi",
    yesDoThat: "Yes, do that",
    noKeep: "No, keep it",
    yes: "Yes",
    noKeepMessage: "No, keep it as it is",
    orAnswer: "Or answer in your words, e.g. make it 2010",
    yourAnswer: "Your answer",
    // the shortlist
    nothingLiked: "Nothing liked yet. Like a home and it lands here.",
    liked: (n: number) => `${n} liked`,
    downloadCsv: "Download CSV",
    colPrice: "Price",
    colPerM2: "€/m²",
    colFacts: "Facts",
    colArea: "Area",
    colFirstSeen: "First seen",
    colListing: "Listing",
    was: (price: string) => ` was ${price}`,
    firstSeen: "first seen",
    // options
    appearance: "Appearance",
    system: "System",
    light: "Light",
    dark: "Dark",
    appearanceHint: "Light and dark are both first class; System follows your device.",
    language: "Language",
    automatic: "Automatic",
    languageHint: "Automatic follows the language of your last message, for the chat and for the screen.",
    nowIn: (name: string) => `Now ${name}.`,
    dataLabel: "Data",
    dataHint: "Photos are linked, never stored. Nothing is kept about agents or owners.",
    about: "About Tispi",
    aboutText: "Tispi is σπίτι with its letters shuffled: a home that hasn't settled into place yet. \"Τι σπίτι;\" is the first question it asks. Every number on a card is counted by code, and nothing loosens without your yes.",
    tagline: "Tispi. Finds your home. · tispi.ai",
    // words for the codes
    floorUnknown: "floor unknown",
    topFloor: "top floor (ρετιρέ)",
    nthFloor: (n: string) => `${n}${n === "1" ? "st" : n === "2" ? "nd" : n === "3" ? "rd" : "th"} floor`,
    bed: (n: number) => `${n} bed`,
    built: (y: number) => `built ${y}`,
    renovated: (y: number) => `renovated ${y}`,
    energy: (c: string) => `energy ${c}`,
    m2: "m²",
    perM2: "/m²",
    perMonth: " / month",
    furnished: "furnished",
    unfurnished: "unfurnished",
    rent: "rent ",
    priceRange: (lo: string, hi: string) => `${lo} to ${hi}`,
    upTo: (x: string) => `up to ${x}`,
    from: (x: string) => `from ${x}`,
    types: { apartment: "apartment", maisonette: "maisonette", studio: "studio", detached_house: "house", loft: "loft", building: "whole building", apartment_complex: "apartment complex" } as Record<string, string>,
    musts: { parking: "parking", lift: "a lift", balcony: "a balcony", storage: "a storage room", furnished: "furnished" } as Record<string, string>,
    features: { price_eur: "Price", size_m2: "Size", bedrooms: "Bedrooms", bathrooms: "Bathrooms", floor_level: "Floor", year_built: "Built", renovated_year: "Renovated",
      energy_class: "Energy class", metro_walk_min: "Metro on foot", balcony: "Balcony", lift: "Lift", parking: "Parking", storage: "Storage room", furnished: "Furnished", dual_aspect: "Dual aspect",
      corner: "Corner", whole_floor: "Whole floor", move_in_ready: "Ready to move in", price_per_m2: "€/m²" } as Record<string, string>,
    weights: ["a must", "strong wish", "would like", "a bonus"],
    renovationProject: "A renovation project",
    no: (name: string) => `No ${name.toLowerCase()}`,
    orBetter: (name: string, v: string) => `${name} ${v} or better`,
    floorOrHigher: (v: string) => `Floor ${v} or higher`,
    range: (name: string, lo: string, hi: string, unit: string) => `${name} ${lo} to ${hi}${unit}`,
    atLeast: (name: string, v: string, unit: string, year: boolean) => `${name} ${year ? "from" : "at least"} ${v}${unit}`,
    nameUpTo: (name: string, v: string, unit: string) => `${name} up to ${v}${unit}`,
    sizeRange: (lo: number, hi: number) => `${lo} to ${hi} m²`,
    sizeFrom: (lo: number) => `from ${lo} m²`,
    sizeUpTo: (hi: number) => `up to ${hi} m²`,
    bedroomsRange: (lo: number, hi: number) => `${lo} to ${hi} bedrooms`,
    bedroomsMin: (lo: number) => `${lo}+ bedrooms`,
    bedroomsMax: (hi: number) => `up to ${hi} bedrooms`,
    builtFrom: (y: number) => `built from ${y}`,
    noFloors: (floors: string) => `no ${floors}`,
    perM2UpTo: (x: string) => `up to ${x}/m²`,
    groundOrLift: "ground floor or a lift",
    liftAbove: (n: number) => `lift above floor ${n}`,
    noConditions: (c: string) => `no ${c}`,
    withMust: (m: string) => `with ${m}`,
    bathroomsMin: (n: number) => `${n}+ bathrooms`,
    renovatedFrom: (y: number) => `renovated or built from ${y}`,
    floorRange: (lo: string, hi: string) => `floor ${lo} to ${hi}`,
    floorMin: (lo: string) => `floor ${lo} or higher`,
    floorMax: (hi: string) => `floor ${hi} or lower`,
    metroWithin: (n: number) => `metro within ${n} min on foot`,
    mustForType: (m: string, t: string) => `${m} for a ${t}`,
    investorMode: "investor mode",
    ground: "ground",
    mezzanine: "mezzanine",
    or: " or ",
    and: " and ",
  },
  el: {
    lang: "el" as Lang,
    locale: "el-GR",
    app: "Tispi",
    newSearch: "Νέα αναζήτηση",
    searches: "Αναζητήσεις",
    yourSearches: "Οι αναζητήσεις σου",
    hideSearches: "Κλείσιμο αναζητήσεων",
    options: "Επιλογές",
    chat: "Chat",
    homes: "Σπίτια",
    shortlist: "Λίστα",
    views: "Προβολές",
    allAreas: "Όλες οι περιοχές",
    limits: "Όρια",
    details: "λεπτομέρειες",
    close: "Κλείσιμο",
    today: "Σήμερα",
    wish: (n: number) => plural(n, "επιθυμία", "επιθυμίες"),
    homesCount: (n: number) => plural(n, "σπίτι", "σπίτια"),
    verdictsCount: (n: number) => plural(n, "κρίση", "κρίσεις"),
    shortlistedCount: (n: number) => `${n} στη λίστα`,
    swipedLine: (swiped: number, liked: number) => `${swiped} κρίσεις · ${liked} μου αρέσουν`,
    likeRate: (pct: number) => `${pct}% ναι`,
    checkinIn: (n: number) => `ερώτηση σε ${n}`,
    limitsHint: "Τα όρια ελέγχονται από κώδικα και δεν παραβιάζονται ποτέ. Οι επιθυμίες μόνο κατατάσσουν. Για να αλλάξεις κάτι, πες το στο Tispi στο chat.",
    covers: (areas: string[], data: string) => `Καλύπτει ${areas.join(", ")} · ${data}`,
    chatNew: "Πες στο Tispi τι ψάχνεις",
    chatChange: "Άλλαξε ό,τι θέλεις από το chat",
    chatIntro: "Γράψε όπως θα το έλεγες σε φίλο, ελληνικά ή αγγλικά. Ρωτάει μόνο ό,τι χρειάζεται και μετά έρχονται τα σπίτια.",
    starters: ["Ψάχνω δυάρι στο Περιστέρι, μέχρι 160.000.", "Τριάρι στο Χαϊδάρι με ασανσέρ, γύρω στις 220.", "Επιπλωμένο δυάρι για ενοικίαση στην Κυψέλη, έως 700 τον μήνα."],
    buyChip: "Αγορά", rentChip: "Ενοικίαση", buySays: "Θέλω να αγοράσω", rentSays: "Θέλω να νοικιάσω",
    liveChip: "Για να μείνω", investChip: "Ως επένδυση",
    thinking: "Σκέφτεται…",
    yourMessage: "Το μήνυμά σου",
    writeHere: "Γράψε εδώ…",
    changeHere: "π.χ. κάν' το 220 χιλ., ή πρόσθεσε Περιστέρι",
    send: "Αποστολή",
    loadingHomes: "Φορτώνονται τα σπίτια…",
    nothingPasses: "Κανένα σπίτι δεν περνά όλα τα όρια",
    seenAll: "Είδες κάθε σπίτι που περνά",
    backToLast: "Πίσω στο προηγούμενο",
    passLine: (n: number) => `${plural(n, "σπίτι περνά", "σπίτια περνούν")} τα όρια της μπάρας.`,
    widenHint: "Ο κώδικας μέτρησε μερικούς τρόπους να ανοίξει η αναζήτηση· διάλεξε έναν και το Tispi θα κάνει την αλλαγή.",
    tellWhat: "Πες στο Tispi τι να αλλάξει.",
    widenNone: "Ένα βήμα πιο ανοιχτά δεν προσθέτει κανένα. Πες στο Tispi τι μετράει λιγότερο.",
    swipeDeck: "Τράπουλα σπιτιών",
    skippedBefore: "Το προσπέρασες νωρίτερα.",
    theMarket: "Η αγορά",
    openOn: (source: string) => `Άνοιξε στο ${source} ↗`,
    syntheticListing: "Συνθετική αγγελία (χωρίς πραγματική σελίδα)",
    synthetic: "συνθετική",
    noPhoto: "χωρίς σύνδεσμο φωτογραφίας",
    home: "σπίτι",
    listedTimes: (times: number) => (times === 2 ? "Αναρτημένο δύο φορές" : `Αναρτημένο ${times} φορές`),
    listedRange: (times: string, lo: string, hi: string, cheapest: boolean) => `${times}, από ${lo} έως ${hi}${cheapest ? "· αυτή είναι η φθηνότερη" : ""}`,
    listedSame: (times: string) => `${times} στην ίδια τιμή`,
    previous: "Προηγούμενο σπίτι",
    previousTitle: "Προηγούμενο σπίτι (Backspace)",
    reject: "Όχι",
    rejectTitle: "Όχι (←)",
    like: "Μου αρέσει",
    likeTitle: "Μου αρέσει (→)",
    skip: "Παράλειψη για τώρα",
    skipTitle: "Παράλειψη· θα ξαναέρθει αργότερα (↓)",
    cantJudge: "Δεν μπορείς να κρίνεις;",
    leftSwiped: (left: number, swiped: number) => `${left} ακόμη · ${swiped} κρίσεις`,
    learningBefore: "Σειρά: οι επιθυμίες σου από το chat. Οι κρίσεις σου μετράνε μετά από 3 ναι και 3 όχι.",
    learningShare: (pct: number, verdicts: number) => `Σειρά: ${pct}% από τα ${verdicts} ναι και όχι σου`,
    countingFor: "υπέρ",
    against: "κατά",
    orderAsked: (order: string) => `Σειρά: ${order}, όπως ζήτησες. Οι επιθυμίες σου ξεχωρίζουν μόνο τα ισόπαλα.`,
    orders: { price_per_m2_asc: "φθηνότερα €/τ.μ. πρώτα", price_eur_asc: "φθηνότερα πρώτα", price_eur_desc: "ακριβότερα πρώτα", size_m2_desc: "μεγαλύτερα πρώτα",
      year_built_desc: "νεότερη κατασκευή πρώτα", days_on_market_desc: "περισσότερο στην αγορά πρώτα", first_seen_desc: "νεότερες αγγελίες πρώτα" } as Record<string, string>,
    whyNot: "Γιατί όχι; Ένα πάτημα αρκεί· μαθαίνει την κατάταξη περισσότερο από το ίδιο το όχι.",
    whatStops: "Τι σε εμποδίζει να κρίνεις; Δεν θα μετρήσει ως ναι ή όχι, και θα ξαναέρθει αργότερα.",
    other: "Άλλο…",
    noReason: "Χωρίς λόγο",
    keepLooking: "Συνέχισε να το βλέπεις",
    inYourWords: "Με δικά σου λόγια",
    rejectWords: "Με δικά σου λόγια, π.χ. ο δρόμος φαίνεται πολύβουος",
    skipWords: "Με δικά σου λόγια, π.χ. μόνο κάτοψη",
    save: "Αποθήκευση",
    rejectReasons: [["too_dark", "Σκοτεινό"], ["too_small", "Μικρό"], ["bad_floor", "Κακός όροφος"], ["needs_work", "Θέλει δουλειά"],
      ["too_expensive", "Ακριβό"], ["bad_value", "Δεν αξίζει τα λεφτά"], ["wrong_area", "Λάθος περιοχή"]] as [string, string][],
    cantJudgeReasons: [["photos_unclear", "Οι φωτογραφίες δεν το δείχνουν"], ["too_little_info", "Πολύ λίγες πληροφορίες"]] as [string, string][],
    question: "Μια ερώτηση από το Tispi",
    yesDoThat: "Ναι, κάν' το",
    noKeep: "Όχι, άσ' το",
    yes: "Ναι",
    noKeepMessage: "Όχι, άσ' το όπως είναι",
    orAnswer: "Ή απάντησε με δικά σου λόγια, π.χ. κάν' το 2010",
    yourAnswer: "Η απάντησή σου",
    nothingLiked: "Τίποτα ακόμη. Πες «μου αρέσει» σε ένα σπίτι και θα μπει εδώ.",
    liked: (n: number) => `${n} στη λίστα`,
    downloadCsv: "Κατέβασε CSV",
    colPrice: "Τιμή",
    colPerM2: "€/τ.μ.",
    colFacts: "Στοιχεία",
    colArea: "Περιοχή",
    colFirstSeen: "Πρώτη εμφάνιση",
    colListing: "Αγγελία",
    was: (price: string) => ` ήταν ${price}`,
    firstSeen: "πρώτη εμφάνιση",
    appearance: "Εμφάνιση",
    system: "Σύστημα",
    light: "Φωτεινό",
    dark: "Σκούρο",
    appearanceHint: "Φωτεινό και σκούρο είναι ισότιμα. Το «Σύστημα» ακολουθεί τη συσκευή σου.",
    language: "Γλώσσα",
    automatic: "Αυτόματα",
    languageHint: "Το «Αυτόματα» ακολουθεί τη γλώσσα του τελευταίου μηνύματός σου, στο chat και στην οθόνη.",
    nowIn: (name: string) => `Τώρα ${name}.`,
    dataLabel: "Δεδομένα",
    dataHint: "Οι φωτογραφίες συνδέονται, δεν αποθηκεύονται. Δεν κρατιέται τίποτα για μεσίτες ή ιδιοκτήτες.",
    about: "Σχετικά με το Tispi",
    aboutText: "Το Tispi είναι το σπίτι με τα γράμματα ανακατεμένα: ένα σπίτι που δεν έχει βρει ακόμη τη θέση του. «Τι σπίτι;» είναι η πρώτη του ερώτηση. Κάθε αριθμός σε μια κάρτα μετριέται από κώδικα, και τίποτα δεν χαλαρώνει χωρίς το ναι σου.",
    tagline: "Tispi. Βρίσκει το σπίτι σου. · tispi.ai",
    floorUnknown: "άγνωστος όροφος",
    topFloor: "ρετιρέ",
    nthFloor: (n: string) => `${n}ος`,
    bed: (n: number) => `${n} υπν.`,
    built: (y: number) => `${y}`,
    renovated: (y: number) => `ανακ. ${y}`,
    energy: (c: string) => `ενεργ. ${c}`,
    m2: "τ.μ.",
    perM2: "/τ.μ.",
    perMonth: " / μήνα",
    furnished: "επιπλωμένο",
    unfurnished: "χωρίς έπιπλα",
    rent: "ενοικίαση ",
    priceRange: (lo: string, hi: string) => `${lo} έως ${hi}`,
    upTo: (x: string) => `έως ${x}`,
    from: (x: string) => `από ${x}`,
    types: { apartment: "διαμέρισμα", maisonette: "μεζονέτα", studio: "γκαρσονιέρα", detached_house: "μονοκατοικία", loft: "loft", building: "ολόκληρο κτίριο", apartment_complex: "συγκρότημα" } as Record<string, string>,
    musts: { parking: "πάρκινγκ", lift: "ασανσέρ", balcony: "μπαλκόνι", storage: "αποθήκη", furnished: "επιπλωμένο" } as Record<string, string>,
    features: { price_eur: "Τιμή", size_m2: "Εμβαδόν", bedrooms: "Υπνοδωμάτια", bathrooms: "Μπάνια", floor_level: "Όροφος", year_built: "Κατασκευή", renovated_year: "Ανακαίνιση",
      energy_class: "Ενεργειακή κλάση", metro_walk_min: "Μετρό με τα πόδια", balcony: "Μπαλκόνι", lift: "Ασανσέρ", parking: "Πάρκινγκ", storage: "Αποθήκη", furnished: "Επιπλωμένο", dual_aspect: "Διαμπερές",
      corner: "Γωνιακό", whole_floor: "Ολόκληρος όροφος", move_in_ready: "Έτοιμο για να μπεις", price_per_m2: "€/τ.μ." } as Record<string, string>,
    weights: ["απαραίτητο", "ισχυρή επιθυμία", "θα ήθελα", "μπόνους"],
    renovationProject: "Για ανακαίνιση",
    no: (name: string) => `Χωρίς ${name.toLowerCase()}`,
    orBetter: (name: string, v: string) => `${name} ${v} ή καλύτερη`,
    floorOrHigher: (v: string) => `Όροφος ${v} ή πάνω`,
    range: (name: string, lo: string, hi: string, unit: string) => `${name} ${lo} έως ${hi}${unit}`,
    atLeast: (name: string, v: string, unit: string, year: boolean) => `${name} ${year ? "από" : "τουλάχιστον"} ${v}${unit}`,
    nameUpTo: (name: string, v: string, unit: string) => `${name} έως ${v}${unit}`,
    sizeRange: (lo: number, hi: number) => `${lo} έως ${hi} τ.μ.`,
    sizeFrom: (lo: number) => `από ${lo} τ.μ.`,
    sizeUpTo: (hi: number) => `έως ${hi} τ.μ.`,
    bedroomsRange: (lo: number, hi: number) => `${lo} έως ${hi} υπν.`,
    bedroomsMin: (lo: number) => `${lo}+ υπν.`,
    bedroomsMax: (hi: number) => `έως ${hi} υπν.`,
    builtFrom: (y: number) => `κατασκευή από ${y}`,
    noFloors: (floors: string) => `όχι ${floors}`,
    perM2UpTo: (x: string) => `έως ${x}/τ.μ.`,
    groundOrLift: "ισόγειο ή ασανσέρ",
    liftAbove: (n: number) => `ασανσέρ πάνω από τον ${n}ο`,
    noConditions: (c: string) => `όχι ${c}`,
    withMust: (m: string) => `με ${m}`,
    bathroomsMin: (n: number) => `${n}+ μπάνια`,
    renovatedFrom: (y: number) => `ανακαίνιση ή κατασκευή από ${y}`,
    floorRange: (lo: string, hi: string) => `όροφος ${lo} έως ${hi}`,
    floorMin: (lo: string) => `όροφος ${lo} ή πάνω`,
    floorMax: (hi: string) => `όροφος ${hi} ή κάτω`,
    metroWithin: (n: number) => `μετρό σε ${n} λεπτά με τα πόδια`,
    mustForType: (m: string, t: string) => `${m} για ${t}`,
    investorMode: "επενδυτικό",
    ground: "ισόγειο",
    mezzanine: "ημιώροφος",
    or: " ή ",
    and: " και ",
  },
};

export type Labels = typeof LABELS.en;
export const LabelsContext = createContext<Labels>(LABELS.en);
export const useLabels = () => useContext(LabelsContext);

// Greek or English from the user's own words, the client's twin of learning/ladder.py language(): Greek letters.
export function detectLanguage(text: string | null | undefined, fallback: Lang): Lang {
  if (!text) return fallback;
  const letters = text.replace(/[^\p{L}]/gu, "");
  if (!letters) return fallback;
  const greek = (text.match(/[Ͱ-Ͽἀ-῿]/g) ?? []).length;
  return greek / letters.length >= 0.5 ? "el" : "en";
}

// Areas keep their names in both languages: the data has them as the portals write them.
export const AREAS: [string, string][] = [
  ["Egaleo", "Egaleo · Αιγάλεω"],
  ["Peristeri", "Peristeri · Περιστέρι"],
  ["Chaidari", "Chaidari · Χαϊδάρι"],
];

export function money(value: number | null | undefined, L: Labels = LABELS.en): string {
  if (value == null) return "–";
  return new Intl.NumberFormat(L.locale, { style: "currency", currency: "EUR", maximumFractionDigits: 0 }).format(value);
}

export function weightWord(weight: number, L: Labels = LABELS.en): string {
  if (weight >= 0.9) return L.weights[0];
  if (weight >= 0.7) return L.weights[1];
  if (weight >= 0.4) return L.weights[2];
  return L.weights[3];
}

const UNITS = (L: Labels): Record<string, string> => ({ size_m2: ` ${L.m2}`, metro_walk_min: L.lang === "el" ? " λεπτά" : " min", price_eur: " €" });

export function preferenceText(p: Preference, L: Labels = LABELS.en): string {
  const name = L.features[p.feature] ?? p.feature;
  const unit = UNITS(L)[p.feature] ?? "";
  if (p.equals === true) return name;
  if (p.feature === "move_in_ready" && p.equals === false) return L.renovationProject;
  if (p.equals === false) return L.no(name);
  if (p.feature === "energy_class" && p.min != null) return L.orBetter(name, String(p.min));
  if (p.feature === "floor_level" && p.min != null) return L.floorOrHigher(String(p.min));
  if (p.min != null && p.max != null) return L.range(name, String(p.min), String(p.max), unit);
  if (p.min != null) return L.atLeast(name, String(p.min), unit, p.feature.endsWith("year") || p.feature === "year_built");
  if (p.max != null) return L.nameUpTo(name, String(p.max), unit);
  return name;
}

export function floorText(floor: string | null, L: Labels = LABELS.en): string {
  if (floor == null) return L.floorUnknown;
  if (floor === "top") return L.topFloor;
  if (/^\d+$/.test(floor)) return L.nthFloor(floor);
  const word = floor.replace("_", " ");
  if (L.lang === "el") return ({ ground: "ισόγειο", "semi basement": "ημιυπόγειο", basement: "υπόγειο", mezzanine: "ημιώροφος" } as Record<string, string>)[word] ?? word;
  return word;
}

const floorWord = (level: number, L: Labels) => (level <= 0 ? L.ground : level < 1 ? L.mezzanine : `${level}`);

// "€90,000 to €220,000", "up to €250,000", "from €90,000": the price as a phrase, or nothing when none is set.
export function priceText(min: number | null | undefined, max: number | null | undefined, intent?: string | null, L: Labels = LABELS.en): string {
  const rent = intent === "rent" ? L.rent : "";
  const month = intent === "rent" ? L.perMonth : "";  // a rent is a month's price (D104)
  if (min != null && max != null) return `${rent}${L.priceRange(money(min, L), money(max, L))}${month}`;
  if (max != null) return `${rent}${L.upTo(money(max, L))}${month}`;
  if (min != null) return `${rent}${L.from(money(min, L))}${month}`;
  return "";
}

// A home's own price: "€800 / month" for a rental, "€185,000" for a sale.
export function homePrice(value: number | null | undefined, listingType: string | null | undefined, L: Labels = LABELS.en): string {
  return `${money(value, L)}${listingType === "rent" && value != null ? L.perMonth : ""}`;
}

// The search is the title (D90, D91): the areas on one line, the price under them, in place of a logo.
export function titleText(card: Card | null, searched: Partial<HardLimits> | null, L: Labels = LABELS.en): { areas: string; price: string } {
  if (!card) return { areas: L.newSearch, price: "" };
  const limits = searched ?? card.hard_limits;
  return { areas: card.areas.length ? card.areas.join(" · ") : L.allAreas, price: priceText(limits.min_price_eur, limits.max_price_eur, card.intent, L) };
}

// "€90–220k" or "90–220 χιλ. €": the price in the searches list, short enough for a row.
function shortK(value: number): string {
  return value % 1000 === 0 ? `${value / 1000}` : (value / 1000).toFixed(1);
}
export function searchTitle(s: SearchSummary, L: Labels = LABELS.en): string {
  if (!s.has_card) return L.newSearch;
  const areas = s.areas.length ? s.areas.join(" · ") : L.allAreas;
  const rent = s.intent === "rent" ? L.rent : "";
  const lo = s.min_price_eur, hi = s.max_price_eur;
  let price = "";
  if (s.intent === "rent") {  // a monthly rent in full, "€350–700 / month": thousands would read 0.7k (D104)
    const n = (v: number) => v.toLocaleString(L.locale);
    if (lo != null && hi != null) price = L.lang === "el" ? `${n(lo)}–${n(hi)} €${L.perMonth}` : `€${n(lo)}–${n(hi)}${L.perMonth}`;
    else if (hi != null) price = L.upTo(money(hi, L)) + L.perMonth;
  } else if (L.lang === "el") {
    if (lo != null && hi != null) price = `${shortK(lo)}–${shortK(hi)} χιλ. €`;
    else if (hi != null) price = `έως ${shortK(hi)} χιλ. €`;
    else if (lo != null) price = `από ${shortK(lo)} χιλ. €`;
  } else {
    if (lo != null && hi != null) price = `€${shortK(lo)}–${shortK(hi)}k`;
    else if (hi != null) price = `up to €${shortK(hi)}k`;
    else if (lo != null) price = `from €${shortK(lo)}k`;
  }
  return price ? `${areas} · ${rent}${price}` : areas;
}

// "Today · 41 homes · 8 verdicts · 4 shortlisted": the counts that tell two searches apart.
export function searchSub(s: SearchSummary, L: Labels = LABELS.en, today = new Date()): string {
  const created = new Date(s.created);
  const when = created.toDateString() === today.toDateString() ? L.today : created.toLocaleDateString(L.locale, { day: "numeric", month: "short" });
  const parts = [when];
  if (s.homes != null) parts.push(L.homesCount(s.homes));
  if (s.verdicts) parts.push(L.verdictsCount(s.verdicts));
  if (s.shortlisted) parts.push(L.shortlistedCount(s.shortlisted));
  return parts.join(" · ");
}

// The bar above the deck: every hard limit other than the areas and the price, which are the title (D90, D91).
export function barText(card: Card, searched: Partial<HardLimits>, L: Labels = LABELS.en): string[] {
  const parts: string[] = [];
  const lo = searched.min_size_m2, hi = searched.max_size_m2;
  if (lo != null && hi != null) parts.push(L.sizeRange(lo, hi));
  else if (lo != null) parts.push(L.sizeFrom(lo));
  else if (hi != null) parts.push(L.sizeUpTo(hi));
  const bl = searched.min_bedrooms, bh = searched.max_bedrooms;
  if (bl != null && bh != null) parts.push(L.bedroomsRange(bl, bh));
  else if (bl != null) parts.push(L.bedroomsMin(bl));
  else if (bh != null) parts.push(L.bedroomsMax(bh));
  if (searched.min_year_built != null) parts.push(L.builtFrom(searched.min_year_built));
  if (searched.property_types?.length) parts.push(searched.property_types.map((t) => L.types[t] ?? t).join(L.or));
  if (searched.exclude_floors?.length) parts.push(L.noFloors(searched.exclude_floors.map((f) => floorText(f, L)).join(", ")));
  if (searched.max_price_per_m2 != null) parts.push(L.perM2UpTo(money(searched.max_price_per_m2, L)));
  if (searched.max_floor_without_lift != null) {
    parts.push(searched.max_floor_without_lift === 0 ? L.groundOrLift : L.liftAbove(searched.max_floor_without_lift));
  }
  if (searched.exclude_conditions?.length) parts.push(L.noConditions(searched.exclude_conditions.map((c) => c.replace("_", " ")).join(L.or)));
  // "with parking", but plain "furnished": the word is already the limit (D104)
  for (const f of searched.must_have ?? []) parts.push(f === "furnished" ? L.musts[f] : L.withMust(L.musts[f] ?? f));
  if (searched.min_bathrooms != null) parts.push(L.bathroomsMin(searched.min_bathrooms));
  if (searched.min_renovated_year != null) parts.push(L.renovatedFrom(searched.min_renovated_year));
  const fl = searched.min_floor_level, fh = searched.max_floor_level;
  if (fl != null && fh != null) parts.push(L.floorRange(floorWord(fl, L), floorWord(fh, L)));
  else if (fl != null) parts.push(L.floorMin(floorWord(fl, L)));
  else if (fh != null) parts.push(L.floorMax(floorWord(fh, L)));
  if (searched.max_metro_walk_min != null) parts.push(L.metroWithin(searched.max_metro_walk_min));
  for (const [kind, features] of Object.entries(searched.must_have_if_type ?? {})) {
    parts.push(L.mustForType(features.map((f) => L.musts[f] ?? f).join(", "), L.types[kind] ?? kind));
  }
  if (card.intent === "invest") parts.push(L.investorMode);
  return parts;
}

// "Price €155,000 to €230,000 and size 65 to 97 m²": what a widening would search, in words.
export function wideningText(patch: Record<string, number | string[]>, searched: Record<string, unknown>, L: Labels = LABELS.en): string {
  const parts: string[] = [];
  const merged = { ...searched, ...patch } as Record<string, unknown>;
  if ("max_price_eur" in patch || "min_price_eur" in patch) {
    parts.push(`${L.features.price_eur.toLowerCase()} ${L.priceRange(money(merged.min_price_eur as number, L), money(merged.max_price_eur as number, L))}`);
  }
  if ("min_size_m2" in patch || "max_size_m2" in patch) {
    const lo = merged.min_size_m2 as number | undefined, hi = merged.max_size_m2 as number | undefined;
    parts.push(lo != null && hi != null ? L.sizeRange(lo, hi) : lo != null ? L.sizeFrom(lo) : L.sizeUpTo(hi as number));
  }
  if ("min_bedrooms" in patch) parts.push(L.bedroomsMin(patch.min_bedrooms as number));
  if ("max_bedrooms" in patch) parts.push(L.bedroomsMax(patch.max_bedrooms as number));
  if ("min_year_built" in patch) parts.push(L.builtFrom(patch.min_year_built as number));
  if ("max_price_per_m2" in patch) parts.push(L.perM2UpTo(money(patch.max_price_per_m2 as number, L)));
  if ("max_floor_without_lift" in patch) parts.push(L.liftAbove(patch.max_floor_without_lift as number));
  if ("exclude_conditions" in patch) parts.push(L.lang === "el" ? "κάθε κατάσταση" : "any condition");
  if ("must_have" in patch) {
    const had = (searched.must_have as string[] | undefined) ?? [];
    const dropped = had.filter((f) => !(patch.must_have as string[]).includes(f));
    parts.push(`${dropped.map((f) => L.musts[f] ?? f).join(", ")} ${L.lang === "el" ? "ως επιθυμία, όχι όριο" : "as a wish, not a must"}`);
  }
  if ("min_bathrooms" in patch) parts.push(L.bathroomsMin(patch.min_bathrooms as number));
  if ("min_renovated_year" in patch) parts.push(L.renovatedFrom(patch.min_renovated_year as number));
  if ("min_floor_level" in patch) parts.push(L.floorMin(floorWord(patch.min_floor_level as number, L)));
  if ("max_floor_level" in patch) parts.push(L.floorMax(floorWord(patch.max_floor_level as number, L)));
  if ("max_metro_walk_min" in patch) parts.push(L.metroWithin(patch.max_metro_walk_min as number));
  if ("must_have_if_type" in patch) {
    const kept = Object.keys(patch.must_have_if_type as unknown as Record<string, string[]>);
    const dropped = Object.keys((searched.must_have_if_type as Record<string, string[]> | undefined) ?? {}).filter((k) => !kept.includes(k));
    parts.push(`${L.lang === "el" ? "χωρίς όριο για" : "no must for a"} ${dropped.map((k) => L.types[k] ?? k).join(L.or)}`);
  }
  if ("property_types" in patch) {
    const had = (searched.property_types as string[] | undefined) ?? [];
    const added = (patch.property_types as string[]).filter((t) => !had.includes(t));
    parts.push(`${L.lang === "el" ? "πρόσθεσε" : "add"} ${added.map((t) => L.types[t] ?? t).join(", ")}`);
  }
  if ("areas" in patch) {
    const all = patch.areas as string[];
    parts.push(`${L.lang === "el" ? "πρόσθεσε" : "add"} ${all[all.length - 1]}`);
  }
  const text = parts.join(L.and);
  return text.charAt(0).toUpperCase() + text.slice(1);
}

// The same widening as a message to the assistant, so it hears the change and the card follows (D61, D66).
// Always in English: it is a message to the model, which reads both, and the field names are its own.
export function wideningMessage(patch: Record<string, number | string[]>): string {
  const words: Record<string, string> = {
    max_price_eur: "top price", min_price_eur: "lowest price", min_size_m2: "minimum size", max_size_m2: "maximum size",
    min_bedrooms: "minimum bedrooms", max_bedrooms: "maximum bedrooms", min_year_built: "earliest year built",
    max_price_per_m2: "top price per m²", max_floor_without_lift: "floors of stairs without a lift",
    min_bathrooms: "minimum bathrooms", min_renovated_year: "renovated or built from", min_floor_level: "lowest floor",
    max_floor_level: "highest floor", max_metro_walk_min: "minutes to the metro",
  };
  const types = LABELS.en.types;
  const parts = Object.entries(patch).map(([name, value]) =>
    name === "property_types" ? `types ${(value as string[]).map((t) => types[t] ?? t).join(", ")}`
      : name === "areas" ? `areas ${(value as string[]).join(", ")}`
      : name === "exclude_conditions" ? "drop the condition limit"
      : name === "must_have" ? `keep ${(value as string[]).length ? (value as string[]).join(", ") : "nothing"} as a must and make the rest wishes`
      : name === "must_have_if_type" ? "drop the must for that property type"
      : `${words[name] ?? name} ${value}`);
  return `Yes, widen it: ${parts.join(", ")}.`;
}
