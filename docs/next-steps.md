# Next steps

Written 20 October 2026, at the end of session 1.

## Where we are

- **v0 foundations done:** models, Greek normalisation, contact-detail scrubbing, 60 synthetic listings, labelling guide and templates.
- **Thin slice of v1 done:** MCP server with `search_listings` and `get_listing`, the search safety eval (20 cases, 0 breaks), CI.
- **Real data:** 484 listings (270 Spitogatos, 214 spiti24) for Egaleo, Peristeri and Chaidari, private and local only. 204 spiti24 listings match a Spitogatos one, so the duplicates eval has real material.

## Rest of v0 (about 2 days)

1. **Snapshot size.** The spec says about 400 listings across three portals. We have 484 from two; xe.gr is open decision 1.
2. **Full descriptions for the extraction set.** Result cards cut descriptions at about 300 characters. Visit about 100 listing pages, slowly, for the full text. These become the 100 extraction labels.
3. **Label 100 listings** with the guide, in `data/private/labels/`. Start with the 60 synthetic ones to calibrate (their answers are known), then the real ones.
4. **Write the 40 scripted interview chats,** half Greek, half English, covering the spec's hard cases ("around 200", "not too old", a partner's wishes, switching language).
5. **Measure self-agreement** a week later: relabel 20 blind, target 95%.

## v1 (about 3 days), evals first

1. **Interview eval harness** on the 40 chats: field accuracy, hard limit vs preference split, zero invented hard limits, asks when it should.
2. **Extraction eval harness** on the 100 labels: per-field accuracy, correct "unknown".
3. Then the features: the interview prompt (Sonnet 5.5), the extraction prompt (Haiku 5.5) with the glossary, the criteria card, `extract_listing` and the `criteria_interview` prompt on the server, the table view.

## Open decisions for you

1. **xe.gr.** Save 20 to 30 listing pages from your own browser (Save Page As, "Webpage, HTML only") into one folder and share it with me. I'll add an offline xe parser. Or skip xe.gr for now; the synthetic set covers it.
2. **Anthropic API key.** Needed from v1. Set it as `ANTHROPIC_API_KEY` where we run, with a spending limit in the Console.

Decided this session: spiti24 added (D18), agency names kept (D19), React for the front end (D20).

## For the desktop app demo

Follow `docs/connect-claude-desktop.md` once the repo is on your machine.
