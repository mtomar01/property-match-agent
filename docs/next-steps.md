# Next steps

Updated 22 October 2026.

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

1. **Cross-check round 2 (D32):** "Mike's Cross-Check 2" and "GB's Cross-Check 2", the 20 listings each where the code-only baseline was most wrong, with the D31 rules. When both are done I score agreement and build answer key v2 (D31 rules applied).
2. **First model run (Haiku 5.5),** once you approve the spend: the extraction prompt with the glossary and the D31 rules, scored against the key next to the code-only baseline (98.7% table fields, 73.1% text fields). Then Sonnet 5.5 for comparison.
3. **Interview eval harness** on the 40 chats, with a simulated user that answers only from each chat's facts.
4. **Optional:** revisit the 100 pages for the crossed-out lists, so code can read "no" from the page.

## v1 features, after the evals

The extraction prompt (Haiku 5.5) with the glossary, `extract_listing` on the server, the conflict rule from D25 in code, the interview prompt (Sonnet 5.5), the criteria card, the table view (React, D20).

## Candidate fields the real pages asked for

Not in the schema yet; the labels note them so we can count them first: **rented** (a tenant in place), **lift reaches the floor**, **delivery date** for homes being built. Each is a real trap for a buyer (D24).

## Open decisions for you

1. **xe.gr.** Save 20 to 30 listing pages from your own browser (Save Page As, "Webpage, HTML only") into one folder and share it with me. I'll add an offline xe parser. Or skip xe.gr for now; the synthetic set covers it.
2. **Anthropic API key.** Received and working. It's stored outside the repo in this environment only. Set a monthly spend limit in the Console, and approve the first model run.
3. **Tab suspender.** You can turn it back on. If I collect more pages later, please whitelist spitogatos.gr instead.
4. **The crossed-out revisit** (step 8 above): your go-ahead, whenever it's useful.

Decided this session: spiti24 added (D18), agency names kept (D19), React for the front end (D20), plus D21 to D30.

## For the desktop app demo

Follow `docs/connect-claude-desktop.md` once the repo is on your machine.
