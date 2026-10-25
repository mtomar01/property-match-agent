# Property Match Agent

A property search assistant for Greece: a conversation becomes clear search criteria, listings from several portals are searched and deduplicated, and a swipe deck learns your taste.

**Status:** v3, learning: the interview, a swipe deck that learns your taste from your likes and rejects, one card per home when a flat is listed more than once, market facts on every card, check-ins every 10 swipes, the shortlist and its CSV. Built, with its evals passing on development sets; the real-swipe and labelled-duplicate scores wait for your swipes and labels. The repo runs on synthetic listings only. See `docs/spec.md` for the full build spec and `docs/decisions.md` for every design choice and why.

## Run it on the synthetic data

You need [uv](https://docs.astral.sh/uv/) and Python 3.11 or newer.

```bash
uv sync                                  # install dependencies
uv run pytest                            # unit tests
uv run python -m evals.harness.run       # eval suite, prints a results table
uv run python -m core.synthetic          # regenerate the synthetic listings
uv run python -m mcp_server.demo         # search through the MCP server, prints a table
uv run python -m evals.harness.duplicates_eval    # the duplicate finder on the synthetic copies
```

Demo options: `--area Peristeri --max-price 250000 --min-bedrooms 3 --no-basements --limit 20`.

To use the MCP server from the Claude desktop app, see `docs/connect-claude-desktop.md`.

## The app: chat, swipe deck, shortlist

You need Node 18 or newer, and the Anthropic API key for the chat (`ANTHROPIC_API_KEY`, or `~/.config/property-match/anthropic.env`).

```bash
cd app && npm install && npm run build && cd ..   # build the React app once
uv run python -m api.server                       # http://127.0.0.1:8765, synthetic listings
PM_SNAPSHOT=data/private/snapshot.jsonl uv run python -m api.server   # your private listings, your machine only
uv run python -m learning.swipes me               # your like rate so far, counts only (v2's finishing line)
uv run python -m evals.harness.learning_eval --real me   # once you have about 200 swipes: learned against rules
```

How it flows (D61, D66, D74 to D79): you chat until the assistant has what it needs, then the homes come up one at a time with the hard limits on a bar above them. What you say outright about parking, a lift, a balcony, storage, bathrooms, the building or renovation year or the floor becomes a hard limit; "ideally" keeps it a wish, and so do "ready to move in" and metro minutes, which the assistant offers as a must with code's count of what that would leave. Under 5 homes, it offers the smallest widening and changes nothing without your yes. Each card says why it fits and two market facts counted by code: its price per m² against similar homes, and how long it has been on the market. A home listed more than once shows once, at its cheapest, with the other listings as links. Right to like, left to reject with a quick reason or your own words; in the middle, back and skip; and "Can't judge" when a listing's photos or details don't let you decide, which never counts against the home (D71). From 3 likes and 3 rejects the order blends in what your swipes teach, all of it from 30, and the line under the deck says how much and what it leans towards. Every fifth card comes from outside the ranking's top, so it keeps learning. Every 10 likes or rejects there's one question: a pattern code found, put by the assistant with the counts; else a reason you tapped; else "How are these homes so far?" Nothing changes until you say yes. Any change goes through the chat, New search starts the swipes from zero, and the shortlist of liked homes downloads as a CSV that opens in Google Sheets.

Each chat message is one or two Sonnet 5.5 calls, about 3 to 4 cents, and so is a pattern check-in. The deck, the reasons and market facts, the learned ranking, the duplicate finder, the swipe log, the pattern finding and the other check-in questions are code and cost nothing. Swipes and the chat are saved in `data/private/`, which git ignores. Photos load from the portal only while a card is on screen and are never stored; the public synthetic listings show a placeholder.

For changes to the app, run `npm run dev` in `app/` with the server running: Vite serves the page and passes `/api` to Python.

## Labelling real listings (private data, your machine only)

```bash
uv run python -m evals.harness.build_label_tool    # offline labelling page in data/private/labels/
uv run python -m evals.harness.labels data/private/labels/<export>.jsonl   # check exported labels
uv run python -m evals.harness.build_label_tool --hosted 20   # links-only page for extra labellers
uv run python -m evals.harness.agreement first.jsonl second.jsonl  # how often two labellers agree
```

The rules are in `docs/labelling-guide.md`.

Duplicates (D78): `uv run python -m evals.harness.build_duplicate_labels` writes a page of 60 pairs from the frozen snapshot to mark "same home" or not (add `--links-only` for a page without listing text, to share). Check the exports with `uv run python -m evals.harness.duplicates_eval --labels mike.jsonl gb.jsonl`.

## Results by version

| Version | Eval | Cases | Hard limit breaks | Recall@20 | Precision@10 |
|---|---|---|---|---|---|
| v0.1 | Search safety (synthetic) | 20 | **0** | 1.00 | 1.00 |
| v3 | Search safety, with condition, price per m², stairs and the D79 limits | 29 | **0** | 1.00 | 1.00 |

| Version | Eval | Listings | Table fields | Text-only fields | Invented values |
|---|---|---|---|---|---|
| v0.2 | Extraction, code-only baseline (answer key v1, real listings) | 100 | 98.7% (target 98%) | 73.1% (target 85%) | 43 |
| v0.2 | Extraction, Haiku 5.5, prompt v1 (description only, code merges) | 100 | 98.2% | 69.4% | 72 |
| v0.2 | Extraction, Haiku 5.5, prompt v2 | 100 | 98.2% | 72.2% | 58 |
| v0.2 | Extraction, Haiku 5.5, prompt v2, with crossed-out lists (50 revisited listings) | 50 | 98.6% | 75.6% | 53 |
| v0.2 | Extraction, code only, with crossed-out lists (same 50) | 50 | 98.9% | 78.6% | 44 |
| v0.2 | **Answer key v2** (all rounds combined, D35; metro within a minute, D36): Haiku v2 + code, crossed-out lists, 50 revisited listings | 50 | 99.1% | **89.9%** | 13 |
| v0.2 | Answer key v2: code only, crossed-out lists, same 50 | 50 | 99.6% | 87.5% | 11 |
| v0.2 | **Answer key v2: Haiku v2 + code, crossed-out lists, all 100** (D38) | 100 | 98.9% | **87.1%** | 46 |
| v0.2 | Answer key v2: code only, crossed-out lists, all 100 | 100 | 99.4% | 85.7% | 39 |
| v0.2 | **Answer key v3** (crossed-out blanks filled by rule, D39): Haiku 5.5 + code | 100 | 98.9% | **91.7%** | 22 |
| v0.2 | Answer key v3: Sonnet 5.5 + code (11x the cost, same score) | 100 | 98.9% | 91.7% | 23 |
| v0.2 | Answer key v3: Haiku 5.5 + code, **prompt v3**, minutes only on foot (D40, D41) | 100 | 98.9% | **92.1%** | 21 |
| v0.2 | Answer key v3: code only | 100 | 99.4% | 90.5% | 15 |
| v0.2 | **Answer key v4** (the key check, D43): Haiku 5.5 + code, prompt v3 | 100 | 99.3% | **94.8%** | 13 |
| v0.2 | Answer key v4: Sonnet 5.5 + code, prompt v2 (11x the cost) | 100 | 99.4% | 95.0% | 12 |
| v0.2 | Answer key v4: code only | 100 | 99.1% | 93.1% | 3 |
| v0.2 | **Clean test, Pagrati** (blind labels, prompt and rules frozen, D44, D45): Haiku 5.5 + code | 10 | 100% | **88.2%** | 4 |
| v0.2 | Clean test, Pagrati: code only | 10 | 100% | 91.2% | 2 |
| v0.2 | Clean test, Pagrati key v2 (the four blanks confirmed, D45): Haiku 5.5 + code | 10 | 100% | 100% | 0 |
| v0.2 | Clean test, Pagrati key v2: code only | 10 | 100% | 91.2% | 0 |

These 100 listings are the development set: the prompts and merge rules were shaped on them. The clean test is 10 listings from Pagrati, labelled blind and never used for tuning (D44). All four of Haiku's disagreements there are facts the description states and the labels left blank, each with a quote (D45).

Most of Haiku's "invented" values come with a quote from the description that the key left blank, and 73 of its misses are "no" answers from the crossed-out feature list, which isn't in the text. Key v1 limited what this eval could show (D33); answer key v2 combines every round's labels (D35).

Answer key quality: two labellers relabelled 20 of each other's listings (40 real listings, kept private). Agreement 89.6% overall against a 95% target: 98% on fields the page's table states, 59% on fields only the text states (D30).

| Version | Eval | Chats | Fields (target 95%) | Invented hard limits (target 0) | Preferences | Behaviours |
|---|---|---|---|---|---|---|
| v1 | Interview, Sonnet 5.5, prompt v1 (D46) | 40 | 88.8% | 0 | 15 of 16, 16 on the wrong side | 98.8% |
| v1 | Interview, prompt v2: stated numbers are hard limits, card repair in code (D47) | 40 | **98.8%** | **1** | 16 of 16 | 98.8% |
| v1 | Interview, prompt v2 rescored on Mike's flat and studio labels (D48) | 40 | 98.1% | 0 | 16 of 17 | 100% |
| v1 | Interview, prompt v3: narrowing question over 50 matches (D49) | 40 | 97.5% | 2, both from the simulated user | 17 of 17 | 98.8% |
| v1 | **Interview, prompt v4**: suggest easing one limit under 5 matches, change only after a yes (D50) | 40 | **100%** | **0** | 16 of 17 | 100% |
| v1 | Interview clean test: 10 new chats by Mike and GB, prompt v4 unchanged, as labelled (D52) | 10 | 43.5% | 2 | 4 of 7 | 66.7% |
| v1 | **Interview, prompt v5**: Mike's price, rooms and type rules in code, the purpose question, rentals not yet (D53 to D55) | 40 | **100%** | **0** | 16 of 17 | **100%** |
| v1 | **Interview clean test, prompt v5**, cards rewritten to the settled rules (D54, D55) | 10 | **82.9%** | **0** | 12 of 13 | 97.1% |
| v1 | **Interview, prompt v6**: investor mode on the card, "ιδανικά" margins in code, a bedroom maximum (D56, D57) | 40 | **100%** | **0** | 17 of 17 | **100%** |
| v1 | **Interview clean test, prompt v6**, with Mike's last two calls (D57, D58) | 10 | **97.3%** | **0** | 13 of 13 | **100%** |
| v1 | **Interview, prompt v7**: the lowest price from code, an early supply check, widening together under 5 matches (D60, D63) | 40 | **100%** | **0** | 17 of 17 | **100%** |
| v1 | **Interview clean test, prompt v7** | 10 | **97.3%** | **0** | 13 of 13 | **100%** |
| v3 | Interview, prompt v8: one-sentence search instead of a confirmation, check-ins, condition, price per m², stairs (D73, D77) | 40 | 99.4% | 1 | 16 of 16, 1 extra | 100% |
| v3 | Interview, prompt v8, the 8 new chats for condition, price per m² and stairs | 8 | 100% | 0 | 3 of 3 | 100% |
| v3 | Interview clean test, prompt v8, as labelled | 10 | 90.2% | 3 | 11 of 13 | 97.1% |
| v3 | **Interview clean test, prompt v8**, two lift wishes relabelled to the stairs limit (D77) | 10 | **95.1%** | 1 | 11 of 11 | 97.1% |
| v3 | Interview, prompt v8, moved to the frozen 23 October file, old labels (D80) | 40 / 10 / 8 | 100% / 97.5% / 97.5% | 0 | 16 of 16 / 11 of 11 / 3 of 3 | 100% / 100% / 92.3% |
| v3 | **Interview, prompt v10**: firm wishes become hard limits where listings say them (D79, D81), 23 October file | 40 | **100%** | **0** | 9 of 10 | **100%** |
| v3 | Interview, prompt v10, the 8 chats for condition, price per m² and stairs | 8 | 97.5% | 0 | 3 of 3 | 92.9% |
| v3 | Interview clean test, prompt v10 | 10 | 89.6% | 0 | 3 of 3, 2 split | 97.1% |

| Version | Eval | Size | Result | Target |
|---|---|---|---|---|
| v2 | Explanations: every "why this one" reason checked against the listing's fields (D64) | 50 cards, 100 reasons | **100%** backed | 98% |
| v3 | Explanations, with the market lines recomputed independently, and move-in-ready and €/m² wishes (D74, D79) | 50 cards, 192 reasons and market lines | **100%** backed | 98% |
| v3 | Learning: 8 simulated buyers, learn from the first swipes, rank the homes waiting after 160 (D76) | 5 runs each, frozen 20 October snapshot | AUC 0.634 rules, **0.742** learned; precision at 10 +0.110 | AUC lift 0.05, precision at 10 no lower |
| v3 | Learning, the same on the 23 October dataset | 5 runs each | AUC 0.650 rules, **0.756** learned; precision at 10 +0.170 | same |
| v3 | Duplicates, synthetic copies (development check) (D78) | 12 known groups | with photo hashes precision **1.0**, recall **1.0**; without, 1.0 and 0.67 | 0.95 and 0.85 |
| v3 | Duplicates, 60 labelled real pairs | 60 pairs | not labelled yet | 0.95 and 0.85 |
| v3 | Learning on your real swipes | about 200 | not recorded yet | a clear lift over the rules |
| v2 | Suggestions: the pattern a check-in offers from a swipe history, or silence (D66, D67) | 30 histories | precision **94.4%**, recall 94.4%, evidence counts all correct, 0 false alarms on random swipes | 80% precision, evidence always correct |
| v2 | Baseline like rate, the share of cards swiped right before any learning | about 100 real swipes | not recorded yet | recorded |

The interview set shaped prompts v2 to v4, so these are development scores (D47, D50). No limit was loosened without the user's yes in v4. On the clean test, 24 of the 35 field misses are limits the new cards add that the user never said, so the cards' rules are being settled before the score means much (D52).

Results files are in `evals/results/`. Mutation tests check that the search safety eval fails when the hard-limit filter is switched off, and that the explanation eval fails when a reason claims a balcony the listing doesn't have. The learning and synthetic duplicate scores are development scores: their buyers and copies are made up, and the learned model's features were adjusted after seeing results (D76). The app runs prompt v10 (D81). Its clean-test misses include one regression from its own new example (a lift wanted above the 1st floor read as a wish, not the stairs limit); prompt v11 fixes it and waits for its run.

## Docs

- `docs/spec.md`: the build spec
- `docs/decisions.md`: every design choice, the options and why
- `docs/labelling-guide.md`: rules for labelling listings
- `docs/next-steps.md`: what's next and open decisions
- `docs/collecting.md`: how a dataset is collected from Spitogatos and built (D68, D69)

## Data and privacy

The public repo holds made up listings only (`data/synthetic/`). Real listings collected for personal use stay in `data/private/`, which git ignores. No agent or owner names, phone numbers, emails or photo files are ever stored.
