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
- **Condition as a filter**: "new build only" can only be a strong preference on year_built today (D46, D48).
- **Price per m² as a limit**: "μέχρι 2000 ανά τετραγωνικό" (clean test gb_3) can only be an open question today; code could filter on price_per_m2.
- **"Renovated" as a filter**: Mike's note on clean test mike_2. Today it's a preference on renovated_year, which needs a year.

## Deck

- **A cap on swipes per user per day** in the final version (Mike, D64, D66). One constant, `DAILY_CAP` in `learning/swipes.py`, off while testing.
- **A super like** (swipe up): left out for now (D64); revisit after a week of use.
- **Greek on the cards:** the reasons code writes are English templates; a Greek set is a translation table away.
- **Couples mode** (spec section 4): two people swipe the same deck, mutual likes go to a shared list.

## Listing quality from reject reasons

- **Reject reasons as data about the listing** (Mike, 24 October): a reason such as "needs work", "too dark" or "bad value for money" is a judgement about the home, not only about the user's taste. Collected across users, the reasons on one listing become a quality signal ("3 of 4 people who rejected this said needs work") that can go back into the dataset: shown on the card, used to fill an unknown condition, or weighed in ranking for everyone.
- **What it needs first:** more than one user, since one person's reasons are taste; a minimum count before a reason counts as a fact about the home; reasons tied to the listing id, never to who gave them; and a check against the listing's own fields (a "needs work" flood on a listing whose page says renovated 2024 is worth a look, not a correction).
- **Today:** the reasons are already logged per swipe with the listing id (`learning/swipes.py`), so the history is there when this is built.

## Interview

- **Either/or musts**, such as "a ground floor or a lift": recorded today as a strong preference plus an open question (el_14).
- **The "yes" path of easing a limit**: the eval tests that "no preference" keeps the card; testing a real yes needs chats whose facts say the user would loosen a limit (D50).
