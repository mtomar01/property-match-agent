# Property Match Agent

A property search assistant for Greece: a conversation becomes clear search criteria, listings from several portals are searched and deduplicated, and a swipe deck learns your taste.

**Status:** v0 foundations. The repo runs on synthetic listings only. See `docs/spec.md` for the full build spec and `docs/decisions.md` for every design choice and why.

## Run it on the synthetic data

You need [uv](https://docs.astral.sh/uv/) and Python 3.11 or newer.

```bash
uv sync                                  # install dependencies
uv run pytest                            # unit tests
uv run python -m evals.harness.run       # eval suite, prints a results table
uv run python -m core.synthetic          # regenerate the synthetic listings
uv run python -m mcp_server.demo         # search through the MCP server, prints a table
```

Demo options: `--area Peristeri --max-price 250000 --min-bedrooms 3 --no-basements --limit 20`.

To use the MCP server from the Claude desktop app, see `docs/connect-claude-desktop.md`.

## Labelling real listings (private data, your machine only)

```bash
uv run python -m evals.harness.build_label_tool    # offline labelling page in data/private/labels/
uv run python -m evals.harness.labels data/private/labels/<export>.jsonl   # check exported labels
uv run python -m evals.harness.build_label_tool --hosted 20   # links-only page for extra labellers
uv run python -m evals.harness.agreement first.jsonl second.jsonl  # how often two labellers agree
```

The rules are in `docs/labelling-guide.md`.

## Results by version

| Version | Eval | Cases | Hard limit breaks | Recall@20 | Precision@10 |
|---|---|---|---|---|---|
| v0.1 | Search safety (synthetic) | 20 | **0** | 1.00 | 1.00 |

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

The interview set shaped prompts v2 to v4, so these are development scores (D47, D50). No limit was loosened without the user's yes in v4. On the clean test, 24 of the 35 field misses are limits the new cards add that the user never said, so the cards' rules are being settled before the score means much (D52).

Results files are in `evals/results/`. A mutation test checks the eval fails when the hard-limit filter is switched off.

## Docs

- `docs/spec.md`: the build spec
- `docs/decisions.md`: every design choice, the options and why
- `docs/labelling-guide.md`: rules for labelling listings
- `docs/next-steps.md`: what's next and open decisions

## Data and privacy

The public repo holds made up listings only (`data/synthetic/`). Real listings collected for personal use stay in `data/private/`, which git ignores. No agent or owner names, phone numbers, emails or photo files are ever stored.
