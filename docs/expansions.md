# Possible expansions

Ideas for later, kept in one place so they don't get lost. Nothing here is being built now. Each line says where the idea came from.

## Sources and areas

- **xe.gr.** The third portal. Skipped for now; it comes back together with new areas (D51). Plan: Mike saves 20 to 30 listing pages from his own browser ("Webpage, HTML only"), and an offline parser reads them.
- **More areas.** The glossary already has every Athens metro station (D40), and Pagrati is an Area for the clean test (D44). New search areas need snapshot listings first, then `SEARCH_AREAS` in `core/models.py`.
- **Rentals.** Not supported yet (Mike, D54): the assistant says so and offers to look at buying. They come back with rental listings in the snapshot.
- **Bank and servicer sites.** For investor mode, v5 (spec).

## Kinds of buyer

- **Investor mode with its own tools** (Mike, D62): ROI calculations and more for investors, on top of the criteria and data in spec section 14 (rent yield, price per m² against the area), v5. Code calculates them, as with every number here.
- **Knowing who's investing:** the interview already asks "to live in or as an investment?" when a purchase doesn't say (D54), and keeps asking so investors can be offered these tools (D62).

## Listing fields

- **Rented** ("μισθωμένο έως ..."): a tenant in place, with the end date. Seen in the labelled set and in Pagrati (D24, D45).
- **Lift reaches the floor**: some lifts stop short of the flat (D24).
- **Delivery date** for homes still being built (D24).
- **Condition in the chat search:** built in v3 (D73): move_in_ready as a strong wish, exclude_conditions only when the user insists.
- **No stairs above the 1st floor:** built in v3 (D73) as max_floor_without_lift, a hard limit filtered in code and checked independently.
- **A price per m² limit:** built in v3 (D73) as max_price_per_m2. The "bad value for money" reason now offers a €/m² wish at a check-in (D75).

## Deck

- **A cap on swipes per user per day** in the final version (Mike, D64, D66). One constant, `DAILY_CAP` in `learning/swipes.py`, off while testing.
- **A super like** (swipe up): left out for now (D64); revisit after a week of use.
- **Greek on the cards:** the reasons code writes are English templates; a Greek set is a translation table away.
- **Couples mode** (spec section 4): two people swipe the same deck, mutual likes go to a shared list.

## Learning and duplicates (found while building v3)

- **Photo hashes for duplicates** (D78): without them, reworded copies are missed (4 of 12 synthetic groups). Making them means fetching each listing's first photo once, a live-site step for Mike to approve; only the hash is kept (spec section 3).
- **The model's look at borderline pairs** (spec section 11): pairs with some evidence and nothing against are kept apart today. The 60 labelled pairs will show how many are real duplicates, and so whether a side-by-side model check is worth its cost.
- **Duplicates in the table view and `search_listings`**: today only the deck folds them.
- **A neighbourhood feature for the learned ranking** (D76): a taste for two neighbourhoods isn't learned, since the model sees no area. A per-neighbourhood like rate from the user's own swipes would cover it.
- **Greek market lines and learning line:** like the reasons, they're English templates for now.
- **An area stats panel in the app:** the figures are in `/api/areas` and the MCP tool `area_stats` (D74), not yet on screen.

## Listing quality from reject reasons

- **Reject reasons as data about the listing** (Mike, 24 October): a reason such as "needs work", "too dark" or "bad value for money" is a judgement about the home, not only about the user's taste. Collected across users, the reasons on one listing become a quality signal ("3 of 4 people who rejected this said needs work") that can go back into the dataset: shown on the card, used to fill an unknown condition, or weighed in ranking for everyone.
- **What it needs first:** more than one user, since one person's reasons are taste; a minimum count before a reason counts as a fact about the home; reasons tied to the listing id, never to who gave them; and a check against the listing's own fields (a "needs work" flood on a listing whose page says renovated 2024 is worth a look, not a correction).
- **Today:** the reasons are already logged per swipe with the listing id (`learning/swipes.py`), so the history is there when this is built.

## Interview

- **Either/or musts**, such as "a ground floor or a lift": the stairs limit covers that one since D73 (el_14 relabelled); others are still a strong preference plus an open question.
- **The "yes" path of easing a limit**: the eval tests that "no preference" keeps the card; testing a real yes needs chats whose facts say the user would loosen a limit (D50).

## Brand and UI round (agreed in the brainstorm of 25 October)

- **Name: Tispi** (said TEE-spee): σπίτι with its letters shuffled, a home that hasn't fallen into place yet; and the start of "Τι σπίτι;", the question the chat asks. Tagline, plain: "Tispi. Finds your home." / "Βρίσκει το σπίτι σου." tispi.ai is available; a proper trademark search is Mike's. Chosen over Scouty (Scout24 owns "scout" in European property), Spitaki (the spiti24 echo), Stegi, Domi, Vrisko, Kleio and Estia, and over descriptive names (PropScout, Property Finder, PropertyAgent) that were taken, generic or the wrong promise.
- **The scout is a behaviour, not a look:** Tispi goes ahead, reports what it saw with numbers, and never sells. That lives in the voice and the brand brief, never on screen: no mascot, no face, no avatar, no forest or lanterns. The one wink is the anagram, a small moment in the logo at most.
- **The brand is typographic and quiet:** a wordmark, one small abstract mark, one warm accent on calm neutrals, generous space, and a typeface with real Greek (every candidate tested on "Διαμέρισμα, 86τ.μ., Λιούμη (Αιγάλεω)"; Inter, IBM Plex Sans and Noto Sans pass).
- **Layout:** desktop with the chat on the left and the Homes and Shortlist tabs on the right, the limits bar above the right pane so the promise stays visible (D61). Phone: the chat first until the search is ready, then the deck takes the screen with the chat as a sheet from a bottom button and check-ins as sheets. Open: whether the phone flips to the deck on its own or on a tap.
- **Method:** a one-page brand brief; a Design System artifact (palette light and dark, type, spacing, logo in SVG, the real components: limits bar, card, reason and market lines, check-in, chips); mockups in the Design artifact (desktop two-pane, phone chat, phone deck, a check-in); then the build, layout first, then tokens, then components, with the phone-width browser check after each step. Skills: frontend-design, design:design-system, design:accessibility-review, design:ux-copy, design:design-critique.
- **The champions inside the code** (Mike's League of Legends theme, never on the front): Quinn the interview, Ezreal the search, Thresh the hard-limit filter, Zilean the learned ranking, Kindred the duplicate finder, Twisted Fate the explore card, Heimerdinger the API server, Varus the weights, Alistar the shortlist, Sett the data store, Teemo in the comments. Riot's coined names stay internal; the words and real names (Thresh, Kindred, Varus, Sett, Alistar, Quinn) could pass anywhere. To be recorded in the decisions log when the parts are renamed.
- **The name goes into the prompt as the voice**, which is a prompt change and needs its eval on the 40 chats (about $3.50). After the UI round.
