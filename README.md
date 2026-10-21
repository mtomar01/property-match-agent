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

Answer key quality: two labellers relabelled 20 of each other's listings (40 real listings, kept private). Agreement 89.6% overall against a 95% target: 98% on fields the page's table states, 59% on fields only the text states (D30).

Results files are in `evals/results/`. A mutation test checks the eval fails when the hard-limit filter is switched off.

## Docs

- `docs/spec.md`: the build spec
- `docs/decisions.md`: every design choice, the options and why
- `docs/labelling-guide.md`: rules for labelling listings
- `docs/next-steps.md`: what's next and open decisions

## Data and privacy

The public repo holds made up listings only (`data/synthetic/`). Real listings collected for personal use stay in `data/private/`, which git ignores. No agent or owner names, phone numbers, emails or photo files are ever stored.
