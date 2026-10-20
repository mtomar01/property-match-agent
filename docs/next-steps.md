# Next steps

Updated 20 October 2026, session 1.

## Where we are

- **v0 foundations done:** models, Greek normalisation, contact-detail scrubbing, 60 synthetic listings, labelling guide and templates.
- **Thin slice of v1 done:** MCP server with `search_listings` and `get_listing`, a command-line demo, the search safety eval (20 cases, 0 breaks), CI.
- **Real data:** 484 listings (270 Spitogatos, 214 spiti24) for Egaleo, Peristeri and Chaidari, private and local only. 204 spiti24 listings match a Spitogatos one, so the duplicates eval has real material.
- **Interview set done:** 40 scripted chats, 20 Greek and 20 English (`evals/datasets/interview_chats.jsonl`).
- **Extraction set collected:** full pages for 100 Spitogatos listings (33 Egaleo, 33 Peristeri, 34 Chaidari), scrubbed, in `data/private/`. Code reads each page's table and ticks (`adapters/spitogatos_details.py`), and the labelling tool is built (D24 to D27).

## Your next job: label the 100 (about 3 hours)

1. On your machine, after pulling the repo and copying `data/private/` across (or open the file I sent you): open `data/private/labels/extraction_labeller_round1.html` in Chrome or Safari.
2. Read the rules once (`docs/labelling-guide.md`, or the Rules button in the tool). The ones that matter most: conflicts are unknown, a missing tick is not a no, a WC is not a bathroom.
3. Label in sittings of 20 to 30. Press **Export done** at the end of each sitting and keep the file.
4. Send me the final export. I'll check it with `evals.harness.labels` and build the extraction eval on it.
5. **A week later:** relabel 20 blind for the self-agreement check (target 95%).
6. **Hosted batches (D28):** "Property Match Labels" (listings 1 to 20) is with an evaluator. "Property Match Labels 21–40" is the second batch. Share each by email as Contributor or Editor; label within a week or two, since they use the live site. I'll score agreement with `evals.harness.agreement`.

## v1 (about 3 days), evals first

1. **Extraction eval harness** on the 100 labels: per-field accuracy, correct "unknown", split into fields the table states (target 98%) and fields only the text states (target 85%), using the `prefilled` list in each label.
2. **Interview eval harness** on the 40 chats: field accuracy, hard limit vs preference split, zero invented hard limits, asks when it should.
3. Then the features: the extraction prompt (Haiku 5.5) with the glossary, `extract_listing` on the server, the conflict rule from D25 in code, the interview prompt (Sonnet 5.5), the criteria card, the table view (React, D20).

## Candidate fields the real pages asked for

Not in the schema yet; the labels note them so we can count them first: **rented** (a tenant in place), **lift reaches the floor**, **delivery date** for homes being built. Each is a real trap for a buyer (D24).

## Open decisions for you

1. **xe.gr.** Save 20 to 30 listing pages from your own browser (Save Page As, "Webpage, HTML only") into one folder and share it with me. I'll add an offline xe parser. Or skip xe.gr for now; the synthetic set covers it.
2. **Anthropic API key.** Needed from v1. Set it as `ANTHROPIC_API_KEY` where we run, with a spending limit in the Console.
3. **Tab suspender.** You can turn it back on. If I collect more pages later, please whitelist spitogatos.gr instead.

Decided this session: spiti24 added (D18), agency names kept (D19), React for the front end (D20), plus D21 to D28.

## For the desktop app demo

Follow `docs/connect-claude-desktop.md` once the repo is on your machine.
