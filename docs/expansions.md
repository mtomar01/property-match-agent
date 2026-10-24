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
- **Condition in the chat search** (planned for v3; Mike, 24 October; earlier notes D46, D48 and clean test mike_2): "χρήζει ανακαίνισης", "needs work", "renovated", "new build", "unfinished" become something the user can ask for in the chat. The listing pages now give it: in the 23 October dataset 714 of 1,000 homes state a condition (renovated 392, needs work 128, new build 104, unfinished 90), 286 don't. Plan: a `condition` feature the interview can use. By default a strong preference ("no renovation projects" ranks those homes last), because as a hard limit the 286 that don't say would be hidden too (unknown fails closed, D8). As a hard limit only when the user insists, and the assistant then says how many unknown homes that hides, with code's count. It replaces today's workarounds: "new build" as a year_built preference and "renovated" as a renovated_year preference that needs a year. The "needs work" reject reason can feed the same field later.
- **No stairs above the 1st floor** (planned for v3; Mike, 24 October): a hard limit that leaves out every home on the 2nd floor or higher without a lift, for anyone who can't or won't climb. In the 23 October dataset 477 of 1,000 homes are on the 2nd floor or higher (a ρετιρέ counts, since its floor number is often unknown); 100 of them state no lift and would go, and 6 don't say whether they have one. Those 6, and the 11 homes with no floor at all, are left out too, because a promise the listing can't confirm fails closed (D8); the assistant says how many that hides. Plan: one hard limit (`no_stairs_above` with a floor number, 1 by default) filtered in code and checked by the independent checker, in the interview schema, and phrased in the prompt for "δεν θέλω σκάλες", "I can't do stairs" and "a lift or a low floor". It replaces today's workaround, a strong preference plus an open question (interview chat el_14).
- **A price per m² limit** (planned for v3; Mike, 24 October; first seen in clean test gb_3, "μέχρι 2000 ανά τετραγωνικό"): the user can set a top €/m² in the chat. Code computes it from price and size, so all 1,000 homes in the 23 October dataset have it and none is hidden for being unknown. Plan: a `max_price_per_m2` hard limit, filtered in code and checked by the independent checker like the others, and in the interview schema and prompt. One caution for the assistant: the typical €/m² differs a lot by area (medians: Kypseli about €2,000, Egaleo €2,250, Chaidari €2,350, Peristeri €2,800, Pagrati €3,600), so one limit across areas hides far more in Pagrati than in Kypseli. check_supply already returns the median per area, so the assistant can say it with code's numbers. The "bad value for money" reject reason could later suggest this limit at a check-in.

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
