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

1. **Cross-check round 2 (D32):** "Mike's Cross-Check 2" and "GB's Cross-Check 2" are ready, with the D31 rules (the header now says round 2). When both are done I score agreement.
2. **Answer key v2:** round 2's labels, the D31 rules applied, and, if you agree, a review of the places where Haiku quotes a value the key lacks (about 80): a page with the listing link, the field, the two values without saying which is the model's, and the quote. You pick; the key stays human-made.
3. **The crossed-out revisit:** 73 of Haiku's 79 misses, the same gap as the baseline's, are "no" answers from the crossed-out list. Your go-ahead, since it touches the live site.
4. **Sonnet 5.5 run** (about $1.50) once key v2 exists. Comparing models on key v1 would mostly measure the key.
5. **Interview eval harness** on the 40 chats, with a simulated user that answers only from each chat's facts.

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
4. **The crossed-out revisit** (step 3 above): your go-ahead.
5. **Internal storage:** two listings have storage crossed out in the feature list but "εσωτερική αποθήκη" (a storage room inside the flat) in the text. Is that storage, or a conflict (unknown)?

Decided this session: spiti24 added (D18), agency names kept (D19), React for the front end (D20), plus D21 to D33.

## For the desktop app demo

Follow `docs/connect-claude-desktop.md` once the repo is on your machine.
