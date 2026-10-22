# Next steps

Updated 22 October 2026, after answer key v4.

## Where we are

- **v0 foundations done:** models, Greek normalisation, contact-detail scrubbing, 60 synthetic listings, labelling guide and templates.
- **Thin slice of v1 done:** MCP server with `search_listings` and `get_listing`, a command-line demo, the search safety eval (20 cases, 0 breaks), CI.
- **Real data:** 484 listings (270 Spitogatos, 214 spiti24) for Egaleo, Peristeri and Chaidari, private and local only. 204 spiti24 listings match a Spitogatos one, so the duplicates eval has real material.
- **Interview set done:** 40 scripted chats, 20 Greek and 20 English (`evals/datasets/interview_chats.jsonl`).
- **Extraction set collected:** full pages for 100 Spitogatos listings (33 Egaleo, 33 Peristeri, 34 Chaidari), scrubbed, in `data/private/`. Code reads each page's table and ticks (`adapters/spitogatos_details.py`). Labelling runs on five hosted pages of 20 (D24 to D29).

## Labelling: where it stands (21 October)

- **All 100 labelled** on the hosted pages (D28): GB 60 (1 to 20, 41 to 60, 81 to 100), you 40 (21 to 40, 61 to 80). All valid, copies in `data/private/labels/`.
- **Rule versions differ:** 1 to 40 were labelled before D29; 41 to 100 after. No consistency pass, because more rounds are coming.

## Next steps

1. **Interview clean test:** 10 new chats written by you and GB, in your own words, that the prompt has never seen. For each: the opening message, the answers you'd give, and the card you'd expect.
2. **Top floor (your call):** let floor_level take "top", since listings already mark a ρετιρέ, instead of a floor number.
3. **v1 features:** `extract_listing` on the MCP server with Haiku and the code merge, the interview prompt (Sonnet), the criteria card, the table view. Metro distance comes from the description only; the map-pin distance is scrapped.

## Interview eval (22 October, D46, D47)

- 40 chats: scripted user turns, a simulated user (Haiku) for gaps, scored in code. Sonnet 5.5 with one tool, check_supply, so trade-offs use code's numbers.
- Prompt v1: fields 88.8%, 0 invented hard limits; stated bedroom counts became preferences. Prompt v2: fields 98.8%, 1 invented hard limit, behaviours 98.8%, 2.3 cents a chat.
- Prompt v3 with the narrowing question: fields 97.5%, 2 invented hard limits, both from the simulated user (D49).
- Prompt v4, suggest easing one limit and ask (D50): fields 100%, 0 invented hard limits, 0 unasked loosenings, behaviours 100%.
- Spent about $6.00 of the $100 in total.

## Pagrati clean test, scored (22 October, D45)

- As labelled: Haiku v3 + code 100% table fields, 88.2% text fields; code alone 91.2%. All four of Haiku's disagreements were facts the labels left blank.
- You confirmed the four, so Pagrati key v2: Haiku v3 + code 100% on both; code alone 91.2%. Headline stays 88.2%.

## Pagrati clean test (22 October, D44)

- 10 listings, chosen at random from the first results page, saved with their crossed-out lists. Pagrati is now an area.
- Two blind labelling pages of 5 (round 6), pre-filled only with what code reads from the table, ticks and crosses.

## Answer key v4 (22 October, D43)

- GB took the proposed value on 20 of 21 disputed values. Haiku v3 + code: 99.3% table fields, 94.8% text fields; code alone 99.1% and 93.1%; Sonnet ties at eleven times the cost.
- Spent about $1.17 of the $100.

## Prompt v3 (22 October, D40)

- Kilometres field, all 66 Athens metro stations in the glossary, rules for vehicles and several distances; minutes count only on foot, enforced in code (D41). Text fields 92.1%, metro 88%. $1.09 spent in total.

## Answer key v3 and the model comparison (22 October, D39)

- 24 crossed-out blanks filled by rule, each marked. Haiku + code: 98.9% table fields, 91.7% text fields. Sonnet ties at eleven times the cost, so Haiku stays.
- Spent $1.01 of the $100.

## Crossed-out lists for all 100 (22 October, D38)

- Haiku v2 + code: 98.9% on table fields, 87.1% on text-only fields (targets 98% and 85%). Code alone 85.7%.
- Check 5: every difference was a crossed-out lift, parking or storage; the system now agrees with Checks 4 and 5 on 418 of 420 fields.

## Check 4 (22 October, D37)

- You agreed with the system on 103 of 105 fields, GB on 102. All balconies and 4 of 5 parking answers right; the misses were crossed-out lift, parking and storage on a listing not revisited.

## Answer key v2 (22 October, D35)

- Every round combined: a value one labeller found beats a blank another left; a clash goes to the newer label. 70 of 100 listings have two or three labels.
- Haiku v2 + code with crossed-out lists: 89.9% on text fields on the revisited 50 (target 85%), 82.1% on all 100, with metro within a minute (D36).
- Round 2 agreement: 89.3% and 90.0%, parking 34 of 87 disagreements; round 3: 95.7% and 92.4%.

## The crossed-out revisit (22 October, D34)

- 50 pages, feature lists only. Code reads a crossed-out lift, storage or parking as "no".
- On those 50: misses fall from 48 to 8 (code) and from 44 to 5 (Haiku). Text fields: code 78.6%, Haiku 75.6%.
- The lists give 26 "no"s the key left blank; round 3 checks them.

## First model run (22 October, D33)

- Haiku 5.5 reads the description only; code reads the table and merges. Prompt v2 on key v1: table fields 98.2%, text fields 72.2% (code alone 73.1%).
- Of 171 disagreements with the key, about 20 look like real model mistakes; the rest are crossed-out "no"s (73), values the key left blank (57), the key predating your notes (14) and raised ground (7).
- Spent $0.155 of the $100.

## v1 features, after the evals

The extraction prompt (Haiku 5.5) with the glossary, `extract_listing` on the server, the conflict rule from D25 in code, the interview prompt (Sonnet 5.5), the criteria card, the table view (React, D20).

## Candidate fields the real pages asked for

Not in the schema yet; the labels note them so we can count them first: **rented** (a tenant in place), **lift reaches the floor**, **delivery date** for homes being built. Each is a real trap for a buyer (D24).

## Open decisions for you

1. **xe.gr.** Save 20 to 30 listing pages from your own browser (Save Page As, "Webpage, HTML only") into one folder and share it with me. I'll add an offline xe parser. Or skip xe.gr for now; the synthetic set covers it.
2. **Anthropic API key.** Working, stored outside the repo, $100 credit with a $100 monthly limit. Delete it and make a new one when the project's done, since it was pasted in chat.
3. **Tab suspender.** You can turn it back on. If I collect more pages later, please whitelist spitogatos.gr instead.

Decided this session: spiti24 added (D18), agency names kept (D19), React for the front end (D20), plus D21 to D50.

## For the desktop app demo

Follow `docs/connect-claude-desktop.md` once the repo is on your machine.
