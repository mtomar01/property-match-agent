# Next steps

Updated 22 October 2026, after the first model run.

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

1. **Check 5 (D37):** "Crossed-Out Check", 10 listings where the system says unknown for lift, parking and storage. You both use the same page; share it with GB by email.
2. **Then the other 50 pages** for their crossed-out lists, if Check 5 shows the unknowns are crossed-out "no"s. Check 4 already found exactly that on #53.
3. **Sonnet 5.5 run** (about $1.50) on key v2, to see whether a bigger model earns its cost on the text fields.
4. **Interview eval harness** on the 40 chats, with a simulated user that answers only from each chat's facts.

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

Decided this session: spiti24 added (D18), agency names kept (D19), React for the front end (D20), plus D21 to D37.

## For the desktop app demo

Follow `docs/connect-claude-desktop.md` once the repo is on your machine.
