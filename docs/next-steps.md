# Next steps

Updated 21 October 2026.

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

1. **Agreement check (D30): done.** 89.6% overall (target 95%): table fields 98%, free-text fields 59%. Most disagreements are amenities GB answered and you left blank.
2. **Your notes** on how the page and description should be read. They shape the code that reads the table and the extraction prompt.
3. **Freeze the answer key:** copy the labels as they stand into one versioned file (answer key v1) that every eval run uses. The pages stay editable; later rounds become v2.
4. **Extraction eval harness:** scores any set of predictions against the frozen key, per field, with "unknown" scored as an answer, split into pre-filled and free-text fields. First run: the code-only baseline.
5. **Then the model** (needs the API key): the extraction prompt on Haiku 5.5, Sonnet 5.5 for comparison.
6. **Interview eval harness** on the 40 chats, with a simulated user that answers only from each chat's facts.
7. **Optional:** revisit the 100 pages for the crossed-out lists, so code can pre-fill "no".

## v1 features, after the evals

The extraction prompt (Haiku 5.5) with the glossary, `extract_listing` on the server, the conflict rule from D25 in code, the interview prompt (Sonnet 5.5), the criteria card, the table view (React, D20).

## Candidate fields the real pages asked for

Not in the schema yet; the labels note them so we can count them first: **rented** (a tenant in place), **lift reaches the floor**, **delivery date** for homes being built. Each is a real trap for a buyer (D24).

## Open decisions for you

1. **xe.gr.** Save 20 to 30 listing pages from your own browser (Save Page As, "Webpage, HTML only") into one folder and share it with me. I'll add an offline xe parser. Or skip xe.gr for now; the synthetic set covers it.
2. **Anthropic API key.** Needed from v1. Set it as `ANTHROPIC_API_KEY` where we run, with a spending limit in the Console.
3. **Tab suspender.** You can turn it back on. If I collect more pages later, please whitelist spitogatos.gr instead.
4. **The crossed-out revisit** (step 8 above): your go-ahead, whenever it's useful.

Decided this session: spiti24 added (D18), agency names kept (D19), React for the front end (D20), plus D21 to D30.

## For the desktop app demo

Follow `docs/connect-claude-desktop.md` once the repo is on your machine.
