# Design decisions

One entry per decision: what we had to choose, the options, the choice and why. Newest at the bottom. This doubles as interview prep, so each entry ends with the one line to say out loud.

---

## D1. Repo layout: the spec's folders plus `core/`

- **Options:** put the shared models inside `mcp_server/`; one big package; the spec's top-level folders plus a small shared package.
- **Choice:** the spec's layout, plus `core/` for the models, Greek normalisation, filters and search.
- **Why:** the agent, the MCP server, the adapters and the evals all need the same Listing and Criteria models. If they lived inside the server, the evals and the agent would depend on the server's internals.
- **Say:** "Shared domain code lives in one place, and every client, including the eval harness, imports it rather than copying it."

## D2. Tooling: uv, Python 3.11+, pytest

- **Options:** pip with requirements files, Poetry, uv.
- **Choice:** uv with a lock file, Python 3.11 or newer, pytest. The project isn't packaged; modules run with `python -m`.
- **Why:** one fast tool installs Python, manages dependencies and runs commands, and `uv.lock` makes installs repeatable on your machine, in CI and here. The desktop app config also uses uv to start the server.
- **Say:** "Locked dependencies, so the eval numbers on my laptop and in CI come from the same code."

## D3. MCP SDK v2, where FastMCP is now called MCPServer

- **Context:** the spec says FastMCP. The current official Python SDK (2.3) renamed FastMCP to `MCPServer` and changed some APIs.
- **Options:** pin `mcp<2` and use FastMCP as written; use v2.
- **Choice:** v2, pinned to `>=2.3,<3`.
- **Why:** same idea, current code. Starting a new project on the old major version means migrating later.
- **Say:** "I followed the spec's intent, not its word, when the SDK moved on."

## D4. Pydantic models: unknown is `None`, extra fields are an error

- **Choice:** every optional fact defaults to `None`, meaning "the listing doesn't say". Models set `extra="forbid"`.
- **Why:** `None` keeps "unknown" separate from a guess, which the spec requires ("says unknown rather than guessing"). Forbidding extra fields means no adapter can quietly add an `agent_phone` field.
- **Say:** "The schema distinguishes unknown from false, and refuses fields it doesn't know."

## D5. Privacy is enforced by the schema and fails closed

- **Options:** trust each adapter to drop contact details; check in the schema as well.
- **Choice:** `core/pii.py` scrubs phones and emails, and the Listing model refuses any title or description that still contains one. A snapshot with a phone in it fails to load.
- **How the phone rule works:** any run of 9 or more digits, allowing spaces, dots and dashes, or digits after "τηλ" or "tel". Prices top out at 7 digits (1.050.000), so they survive.
- **Proof it matters:** in the first 270 real cards, one description carried an agency's mobile number, and a 9-digit typo at that.
- **Limit:** personal names have no fixed shape, so code can't catch them reliably. They're handled by policy: descriptions stay in the private snapshot only, and extracted fields never include names. Agency brand names stay (see D19).
- **Say:** "Privacy isn't a reminder in a prompt. Bad data is refused at load time."

## D6. Energy classes stored as Latin letters

- **Choice:** store A+ to G, show Greek letters to Greek users. Latin "Z" and "H" in a listing are read as the Greek Ζ (F) and Η (G).
- **Why:** listings often type Greek capitals on a Latin keyboard. There's no Z or H on the Latin scale, so the only sensible reading is the Greek letter.
- **Say:** "One canonical form in code, the local form on screen."

## D7. Hard limits are filtered in code, inside the MCP tool

- **Options:** ask the model to respect limits; filter in the agent loop; filter in the server.
- **Choice:** in the server's `search_listings` tool, before results reach any model.
- **Why:** every client gets the guarantee, including the Claude desktop app, which runs none of our agent code. A model can be talked out of a limit; an if statement can't.
- **Say:** "Breaking a budget is the costliest mistake, so it's enforced where no prompt can reach it."

## D8. Unknown values fail closed, but are counted

- **Context:** a listing with no stated price, when the user set a budget.
- **Options:** include it (optimistic), drop it silently, drop it and report it.
- **Choice:** leave it out of the matches and return `excluded_because_unknown`, for example `{"price_eur": 1}`.
- **Why:** including it would break the promise. Dropping it silently hides options. Reporting lets the agent say "one more listing doesn't state a price, want to see it?" and lets the user decide.
- **Say:** "Fail closed, but be transparent about what was held back."

## D9. Areas and listing type are hard filters too

- **Choice:** areas the user names are a hard limit, and intent sets the listing type (buy and invest search sales, rent searches rentals).
- **Why:** a sale at €180,000 must never appear in a search for rents under €1,000. Area is the most common reject reason in property search, so it's treated as a promise.

## D10. v1 ranking: weighted preference matches, unknown scores 0.5

- **Choice:** each preference scores 1 if met, 0 if not, 0.5 if the listing doesn't say, weighted and averaged. Preferences only rank; they never filter.
- **Why:** simple and explainable, and v2 replaces it with a learned model. 0.5 neither rewards nor punishes a missing fact.

## D11. Synthetic data for the public repo

- **Choice:** 60 invented listings from a fixed seed: 3 areas, 3 sources, 12 known duplicates (6 near exact spiti24 copies, 6 reworded xe copies), and edge cases on purpose (a price exactly on a budget, a size exactly on a minimum, price on request, unknown bedrooms, unknown floor, basements, rentals). URLs use the reserved `.invalid` domain.
- **Why:** real listings belong to the portals and agencies. Synthetic ones with the same structure let anyone run every eval, and the known duplicates become free ground truth for the dedupe eval in v3.
- **Say:** "The public data was designed to hit the edges, not just to look realistic."

## D12. The search safety eval doesn't grade itself

- **Choices:**
  - The checker in `evals/harness/checks.py` is written separately from `core/filters.py`. If the eval reused the filter, a bug in one would hide in the other.
  - The harness calls the real MCP server through an MCP client, exactly like the desktop app.
  - Expected matches are frozen into the dataset, so any change shows up as a diff to review.
  - A mutation test switches the filter off and asserts that the eval then fails.
- **Result v0.1:** 20 cases, 0 hard limit breaks, recall@20 1.00, precision@10 1.00 on synthetic data. Also 0 breaks on the 270 real listings.
- **Say:** "A perfect score only means something if the test can fail, so I proved it can."

## D13. Data sources: Spitogatos yes, xe.gr no

- **Context:** you asked me to browse Spitogatos and xe.gr in your Chrome for real listings.
- **What the sites say (read 20 October 2026):**
  - **xe.gr robots.txt** names Anthropic's `Claude-User` agent (Claude fetching pages for a person) and disallows it everywhere except a few editorial pages. It also disallows search and results pages for every bot. Its terms (section 9) need written permission for reuse.
  - **Spitogatos robots.txt** only disallows map search, annual reports, the account area and a list of bad bots, none of them Claude. Its terms (section 11) allow saving content electronically for personal, non-commercial use.
- **Choice:** collected Spitogatos at a slow pace (a few seconds between pages, three result pages per area, 270 listings). Did not collect xe.gr. Browsing it through your Chrome would still be Claude acting for you, just under Chrome's name, so it would route round an opt-out that names us.
- **Follow-up (same day):** you said browsing xe.gr through Claude in Chrome is fine for the POC. I still didn't. The opt-out names Claude acting for a user, which is exactly what Claude in Chrome is, and your own project rule is "respect robots.txt".
- **The route that works:** you browse xe.gr yourself, as a normal visitor, and save 20 to 30 listing pages. I parse the saved files offline. That's personal use under xe.gr's terms, and Claude never requests a page from xe.gr.
- **Longer term:** ask xe.gr for permission, which fits the plan to work with the platforms.
- **Say:** "I read the robots.txt and the terms before collecting anything, and one site said no to my agent specifically, so I didn't."

## D14. Real card parsing: code reads structure, the model will read prose

- **Choice:** `adapters/spitogatos_cards.py` parses the fixed parts of a card (title, size, badges, price, previous price) and the sentences Spitogatos generates from its own form ("Έχει κατασκευαστεί το 1978..."). Free text written by agencies stays in the description, and those fields stay unknown until the v1 extraction step.
- **Coverage on 270 real cards:** price, size, type and area 100%, floor 98%, bedrooms 96%, year built 17%, energy class 1%. The low numbers are the case for model extraction.
- **Data quality example worth mentioning:** one card's badge says 4th floor while its own description says 3rd. The labelling guide says label what the listing says and note the conflict.

## D15. Keep scrubbed descriptions in the private snapshot

- **Options:** store only normalised facts (strictest reading of the spec); also keep the scrubbed description, privately.
- **Choice:** keep it, privately.
- **Why:** the extraction eval needs the source text, and "why this one" reasons need evidence to point at. Spitogatos's terms allow saving for personal use, and contact details are scrubbed first.

## D16. Models

- **Choice (yours):** Sonnet 5.5 (`claude-sonnet-5-5`) for the conversation and suggestions, Haiku 5.5 (`claude-haiku-5-5`) for bulk extraction. The extraction eval decides whether Haiku is good enough.
- **Why:** extraction runs once per listing at volume, so cost matters most there. The conversation is where judgement matters.

## D17. Build in the cloud, demo on your machine

- **Choice:** build and test in this environment, push to GitHub, clone locally for the desktop app.
- **Why:** the Claude desktop app starts local MCP servers, so the demo has to run where the app is. Commits use the GitHub no-reply address so your personal email never appears in a public repo.

## D18. spiti24 added

- **What it says (read 20 October 2026):** robots.txt disallows only `/wp-admin/` for every agent, plus a list of bad bots, none of them Claude. Its terms allow saving content electronically for personal, non-commercial use, the same wording as Spitogatos.
- **Collected:** 3 result pages per area at the same slow pace, 214 full cards. Mini promoted cards (just price and size) were skipped.
- **What its cards carry:** price, any price drop with its date, type, size, area and sub-area, bedrooms and bathrooms. No floor and no description, so those stay unknown, and a search that excludes floors leaves spiti24 listings out (fail closed, D8).
- **Finding:** 204 of the 214 spiti24 listings match a Spitogatos listing on area, size within 1 m² and exact price. 176 match exactly one. 28 match several, usually units in the same new development with the same price and size. That's the duplicates eval handed to us: easy pairs, plus genuinely hard ones where "same building" isn't "same flat".
- **Real-data check:** search safety on the merged 484 listings: 0 hard limit breaks.

## D19. Agency brand names stay in private descriptions

- **Context:** contact details are scrubbed. The question was whether to strip agency names too.
- **Choice (yours):** keep them.
- **Why:** the product sends people back to the agency and the platform rather than around them. Every card links to the original listing, and keeping the agency's name supports that.
- **The line we still hold:** the spec's "never store agent or owner names" is about people. No personal name goes into a structured field, and phones and emails are always scrubbed.
- **Say:** "We're a front door to the portals and agencies, not a way round them."

## D20. Front end: a small React app

- **Choice (yours):** React with Vite and TypeScript, kept basic, in this repo under `app/`.
- **Considered:** Lovable (fast, but the code is harder to own and explain) and Open WebUI (a chat app, MCP over HTTP only, branding required above 50 users; useful as an extra MCP client in a demo).
- **When:** with the v1 table view, after the interview and extraction evals exist. The spec warns the UI can eat the schedule, so it stays thin until v3.

## Front end background (decided in D20)

- **Your lean:** a small React app. Also considered: Lovable, Open WebUI.
- **Open WebUI:** a good self-hosted chat interface, and it now supports MCP natively, but only over Streamable HTTP, so our stdio server would need an HTTP transport or the mcpo proxy. It's built for chat, so the swipe deck, criteria card and shortlist would mean working against it. Since v0.6.6 its licence also requires keeping its branding above 50 users. It's useful as a second MCP client for a demo, not as the product.
- **My recommendation:** a small React app (Vite), kept basic, in this repo. A swipe deck is a custom interaction, and interviewers can read every line.
