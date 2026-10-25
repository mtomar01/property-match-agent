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

## D21. Preferences use a closed list of features

- **Context:** a preference names a feature to rank on, such as `floor_level` with `min: 3`. The model writes these cards, so it can invent a feature, such as "brightness", that no listing field carries.
- **Options:** accept any name and ignore the ones ranking doesn't know; accept a closed list and refuse the rest.
- **Choice:** a closed list (`PreferenceFeature` in `core/models.py`), the 16 features ranking can actually score. Energy class bounds use letters ("B" or better), not numbers.
- **Why:** an unknown feature would score 0.5 on every listing forever, so the user's wish would be silently dropped while the card still showed it. Refusing it makes the agent either map the wish to a real feature or keep it as an open question. Two interview chats (`el_14`, `en_14`) test the honest version of this.
- **Say:** "If the ranking can't score it, the schema won't accept it, so the agent can't pretend a wish is being used."

## D22. An unticked feature box means unknown, not no

- **Context:** a Spitogatos page lists every feature in its form and strikes through the ones the agency didn't tick.
- **Options:** read a struck-through lift as "no lift"; read it as "not stated".
- **Choice:** a tick is a yes, a missing tick is unknown. A "no" comes only from the text ("δεν διαθέτει ασανσέρ").
- **Why:** ticks are incomplete. On the 100 real pages, one maisonette ticks a single interior feature, and some texts describe parking that isn't ticked. Reading a missing tick as "no" would state facts the listing never gave. Unknown already fails closed in search (D8), so this costs nothing in safety.
- **Say:** "Absence of a tick is absence of evidence. Only the listing saying 'no' counts as no."

## D23. Advertisers who trade under a personal name are redacted

- **Context:** D19 keeps agency brands in private descriptions. One of the 100 pages is advertised under a plain first name and surname.
- **Choice:** brands and registered companies stay, including ones built from surnames with a company form (Ο.Ε., ΙΚΕ). A bare personal name as the advertiser is replaced with "[advertiser name removed]" before saving.
- **Why:** the spec's rule is about people. A personal name is a person's name whatever it's used for.
- **Say:** "A company name is a brand. A person's name is personal data, even on an advert."

## D24. Full pages for the extraction set, collected slowly in your Chrome

- **What:** 100 Spitogatos listing pages (33 Egaleo, 33 Peristeri, 34 Chaidari), opened in your own browser five at a time. A small script read six named sections (description, table, interior, exterior, construction, suitable for) and dropped struck-through features. Phones and emails were scrubbed before anything was saved, to `data/private/` only.
- **Why this way:** the same terms basis as D15 and D18 (personal use, normal browsing pace), and result cards cut descriptions at about 300 characters, which is too short to label.
- **A practical snag:** your tab suspender parked the tab mid-run and changed its ID. Navigating without fixed waits, re-reading the tab list when a call failed, and you pausing the suspender fixed it.
- **What the real pages taught us:**
  - Two bugs in the Greek heating normaliser: "Fan coil" was read as oil, because "coil" contains "oil", and Spitogatos's own wording "Αντλία Θέρμανσης" gave no fuel. Three fan coil flats in the private snapshot were labelled as oil heating. Both are fixed and tested.
  - The page and its own text often disagree: the price (the table is newer after a drop), the floor (a raised ground floor shown as Ισόγειο), the year of renovation, the number of bathrooms, the energy class (Α++ in the text, which the table can't hold), the size (a house whose stated area includes its basement).
  - Traps for a buyer that no field holds yet: rented with a tenant in place, a lift that stops one floor below the flat, a goods lift (αναβατόριο) instead of a lift, "available now" on a flat delivered in 2027, a "not eligible for Σπίτι μου" note.
- **Say:** "A hundred real pages found two bugs that 197 tests on synthetic data missed. That's why the evals need real labels."

## D25. When a listing contradicts itself, the label is unknown

- **Context:** the table says one thing and the text another (D24).
- **Options:** trust the table; trust the text; mark it unknown.
- **Choice:** unknown, with both values in the notes. Two exceptions: the price (the table is what the portal updates on a price drop) and the size (the table is the number the listing is sold on).
- **Why:** we can't tell which is true, and unknown fails closed in search, so a user with a hard limit never gets a listing on a coin toss. Later the extraction pipeline will do the same: code reads the table, the model reads the text, and a disagreement becomes unknown with both values kept as evidence.
- **Say:** "When the listing argues with itself, we don't pick a side. We say unknown and show both."

## D26. The labeller pre-fills only what code read

- **Options:** a blank form (slow, three hours becomes six); everything pre-filled, including guesses from the text (fast, but you'd anchor on the guesses); only the table and ticks pre-filled.
- **Choice:** the third. Free-text fields (parking type, minutes to the metro, and any field the table leaves out) start blank. Each label records which fields were pre-filled and which of those you changed.
- **Why:** checking a printed table is quick and safe. Anything the model will have to read from text must come from you, or the eval would grade the model against code's guesses. The "changed" list also measures how often the portal's own table is wrong.
- **Say:** "Pre-fill what's printed, never what's inferred, and log every correction."

## D27. A local HTML labeller, not a spreadsheet or a hosted page

- **Options:** a spreadsheet; a hosted page; one offline HTML file.
- **Choice:** one offline HTML file, built from the private data by `evals/harness/build_label_tool.py` into `data/private/labels/`. It shows the page's table, ticks and description side by side with the form, highlights numbers and key words, saves as you go in the browser, and exports JSONL in the label format. `evals/harness/labels.py` validates the export.
- **Why:** descriptions run to 3,000 characters, which a spreadsheet cell handles badly. A hosted page would publish scraped listings. An offline file keeps the data on your machine, needs no install, and exports exactly the format the eval reads. Listing text is untrusted, so the page only ever inserts it as text, never as HTML.
- **Say:** "The labelling tool is part of the eval. It's built to make the right label the easy one."

## D28. Extra labellers work from the live page, on a hosted page with no listing text

- **Context:** you asked whether other people could label too, online.
- **Options:** host the full tool (it would pass scraped descriptions to other people); send the offline file privately (the same copies, just fewer); a hosted page with links and facts only.
- **Choice:** links and facts only, published as a private Claude page with a shared store, for 20 listings (the first 20 in your own labelling order, so your labels cover them early). Labellers open each listing on Spitogatos and read it there.
- **Who sees what:** each labeller writes only under their own path in the store, and the store's rules let only you read everyone's labels, so each labeller stays blind to the others. Checked after publishing with a test write read back at a labeller's access level: they see nothing of anyone else's.
- **Trade-off:** live listings change and disappear, so each label records whether the page still matched our 20 October copy (matches, changed, gone). Gone listings are left out of the agreement score. Labelling needs to happen within a week or two.
- **Measuring it:** `evals/harness/agreement.py` scores two label sets field by field, split into pre-filled and free-text fields. The same script runs your own relabel a week later.
- **Batches:** each batch of 20 is its own page with its own store (listings 1 to 20, then 21 to 40, numbered in the full labelling order), so starting a new batch never changes a page someone is labelling on.
- **Say:** "Extra labellers go to the source. We share links and facts, never someone else's writing, and the store keeps each labeller blind to the others."

## D29. Crossed-out features are a no (revises D22)

- **What changed:** you've listed homes on Spitogatos yourself, and the advertiser has to cross a feature out on purpose. So a feature has three states: ticked (yes), crossed out (no), and not stated (unknown). In your words, not stated means the amenity is in none of the three places: not in the description, not in the table, not in the ticked or crossed list. D22 had merged crossed out with not stated, on my assumption about how the form works.
- **How it showed up:** your grader, reading the live pages, answered "no" where the old rule said blank. The collector had also dropped crossed-out items, so neither your offline tool nor the pre-fill can see them yet.
- **Now:** the hosted page for listings 41 to 60 says crossed out is no, and its parking rule is tighter (a spot under the pilotis is always pilotis). The pages for 1 to 20 and 21 to 40 keep their old wording, because people were labelling on them. The offline tool and the pre-fill change once the 100 pages' feature lists are read again with crossed-out items kept, which waits for your go-ahead to visit the live site.
- **To watch:** agencies that upload through an automatic feed may send "no" for every field they left empty. Once we have the crossed-out lists, we count how often one contradicts the description.
- **Say:** "The person who'd filled in the form knew what the cross meant. Ask the domain expert, not just the page."


## D30. Agreement check: each labeller relabels 20 of the other's listings

- **Choice (yours):** 20 random listings GB labelled go to you, and 20 random listings you labelled go to GB, each on its own hosted page. Same pages as before: links and code-read values, never the other person's answers.
- **How they're picked:** `evals/harness/agreement_sets.py` samples with a fixed seed (2026) and saves the chosen ids, so the sets can be rebuilt and checked.
- **One caveat:** some sampled listings come from the batches labelled before D29 (13 of GB's 20, 7 of yours), so agreement is reported for before and after D29 separately. A disagreement there may be the old wording, not the labeller.
- **No consistency pass on 1 to 40 (yours):** more labelling rounds are coming anyway.
- **Result (21 October):** 89.6% overall on 40 listings (target 95%). Table fields 98%, free-text fields 59%. Before and after D29 alike (89.5% and 89.8%), so the rule change isn't the cause. Of 87 disagreements, 57 are amenities (lift, storage, balcony, parking) where GB gave an answer and you left it blank (41 "no", 16 "yes"), all in the same direction whoever labelled first. The rest: 13 on new builds (year built, condition), 8 on minutes to the metro, 4 on parking type. The labellers aren't careless; they read the page differently, which the reading notes should settle.
- **Say:** "Two people, twenty listings each, blind. That's the number that tells you whether the answer key can be trusted."

## D31. Your reading notes, after the first cross-check

- **What you settled:** a crossed-out amenity is "no" (as in D29). Photos don't count as evidence, for now. A home still being built takes its expected completion year, and its condition is unfinished (not new build). Minutes to the metro only when the description gives the distance. Θέση στάθμευσης, πάρκινγκ, parking and γκαράζ all mean a parking spot. A fan coil means the heating runs on a heat pump. Μπαλκόνι, βεράντα, ιδιωτικός κήπος, αυλή all count as a balcony. And many descriptions mention parking or a storage room that the pre-fill didn't catch.
- **What changed in code:** fan coil reads as a heat pump. A home whose table says "under construction", whose year built is in the future, or which is "available from" a later date is unfinished, with that date's year as its year built. A parking tick is a parking spot, and a private garden tick is a balcony.
- **How answers are compared:** parking is has or hasn't, so pilotis against space is no longer a disagreement. Metro values above 60 are metres, turned into minutes at 80 m a minute, because you typed the distance as the listing gave it (500, 650). With these rules, round 1 agreement is 90.1% (table fields 98%, text fields 62%).
- **Say:** "The domain expert wrote the reading rules; the code and the scoring follow them, and each rule is a line you can point to."

## D32. Answer key v1, the extraction eval and the code-only baseline

- **Answer key v1:** the 100 labels frozen as they stood on 22 October (`evals/harness/answer_key.py`), with a checksum and, for each listing, who labelled it and under which rules (40 before D29, 60 after). Versions are never overwritten; later rounds become v2. Known weakness: v1 was labelled before your reading notes, so on new builds it says "new build" where the rules now say "unfinished".
- **The eval** (`evals/harness/extraction_eval.py`) puts every field in one of four outcomes: correct (both unknown counts), wrong, invented (a value where the key says unknown) and missed. Invented and wrong are reported on their own, because a wrong "has a lift" lets a listing through a hard limit while a miss only fails closed. Fields split into those the table states (target 98%) and those only the text states (target 85%). Public results hold totals only.
- **The code-only baseline** (`evals/harness/code_baseline.py`): the table and ticks, plus a few visible keyword rules on the description for the facts your notes say a reader must catch. Score on v1: table fields 98.7% (target met), text fields 73.1% (target 85%). 75 of its 90 misses are "no" answers on parking, lift and storage, which the labellers read from the crossed-out list that code never saved; the crossed-out revisit would fix exactly these. Its inventions are mostly balconies, parking and metro distances found in the text where the labels left the field blank, and 8 of its 12 wrong values are new builds, where key v1 predates the "unfinished" rule.
- **Round 2 of the cross-check (your choice):** each of you relabels the 20 listings the other labelled where the baseline was most wrong, on pages carrying the D31 rules. 13 of GB's and 6 of yours are listings you each saw in round 1; they still compare with the other person's original label.
- **Say:** "Before any model, a frozen key, a scorer that separates harmless misses from dangerous inventions, and a rules baseline at 98.7% and 73.1%. The model has to earn its place on the text fields."


## D33. The extraction prompt: the model reads the prose, code does the rest

- **Who does what:** code reads the page's table, ticks and result card, where it's right 98.7% of the time. The model (Haiku 5.5) reads only the description and reports what the description itself states. Code merges the two. Why: "code calculates, the model reasons". The model never sees the table, so it can't copy it, and every disagreement between the description and the table is visible to code instead of being settled silently inside the model.
- **Quote first, then answer:** the answer is structured output (a JSON schema the API enforces), and its first part is a list of evidence quotes, one per filled field. Each value then rests on words the model has just copied from the listing, and checking a run takes minutes: read the quote next to the disputed value. No confidence score yet, because a model's own confidence isn't calibrated; accuracy per field is measured instead.
- **Code does the arithmetic and the checks:** metres to the metro become minutes (80 m a minute, rounded up, the same rule as the scoring), choices are matched without case, numbers outside sane ranges become unknown, and quotes are scrubbed of contact details.
- **The conflict rule (D25) lives in code,** and two variants are scored from the same answers: "fill" (code first, the description fills blanks) and "conflict" (when they disagree, unknown; the table wins for price and size). Differences the guide says aren't conflicts are reconciled in code: υπερυψωμένο ισόγειο is a more exact "ground", and a ρετιρέ with a floor number takes the number.
- **Versioned and reproducible:** prompts live in `prompts/` with a version and a changelog line (`prompts/CHANGELOG.md`); the glossary in the prompt comes from `core/greek.py`, the same table the MCP server serves, now with your D31 terms. Every answer is cached by a hash of the exact request (model, prompt, schema, listing text), so re-scoring never pays twice. The API no longer takes a temperature setting, so two runs can differ slightly; the cache makes a scored run exactly re-scorable. A failed call keeps what code read (it fails closed), and a long listing that runs out of room gets one retry with twice the room.
- **Results on answer key v1** (100 listings):

  | | Table fields | Text-only fields | Invented |
  |---|---|---|---|
  | Code only (D32) | 98.7% | 73.1% | 43 |
  | Haiku, prompt v1, fill | 98.2% | 69.4% | 72 |
  | Haiku, prompt v2, fill | 98.2% | 72.2% | 58 |
  | Haiku, prompt v2, conflict | 97.5% | 72.2% | 58 |

- **What the disagreements say:** of prompt v2's 171 disagreements with the key, 73 are "no" answers from the crossed-out list, which isn't in the text; 57 are values Haiku quotes from the description that the key left blank (parking, balconies, metro distances, "δεν έχει ασανσέρ"); 14 are where the key predates your notes (unfinished, fan coil); 7 are "ground" in the key where the guide says raised ground. Only about 20 look like real model mistakes. So key v1, not the model, limits what this eval can show.
- **Prompt v2 fixed two of my mistakes:** v1 offered a "good" condition the guide doesn't have, so "σε πολύ καλή κατάσταση" became a value the key never holds (17 cases); and it read "ασανσέρ έως -1" (the lift goes down to the basement) as no lift (3 cases). Both fixes are rules from the guide or plain Greek, not examples, but they were found by reading this set's errors, so v2's score is slightly optimistic. A fresh batch of listings will be the clean test.
- **Fill or conflict:** against key v1, "fill" scores higher on table fields, because when the text disagreed with the table the labellers mostly kept the table's value, while D25 says leave it blank. Either the rule or the labels should change; key v2 decides.
- **Cost:** $0.155 for everything today (a 2-listing dry run, prompt v1 and prompt v2 on 100 listings): under a tenth of a cent per listing.
- **Say:** "The first model run looked worse than regex. The quotes showed why: most 'errors' were gaps in the answer key. An eval can't tell a good model from a good regex until the key is right, so the next step was the key, not the prompt."

## D34. The crossed-out revisit: 50 pages, and round 3

- **What:** with your go-ahead for 50 of the 100, I reopened 50 listing pages on 22 October (picked at random with a fixed seed: 17 Egaleo, 17 Peristeri, 16 Chaidari) at the D24 pace, a few seconds between pages. A small script read only the four feature lists and each feature's icon: a tick (`i-correct`) or a cross (`i-negative`). Nothing else on the page was read. To move the lists here without retyping Greek, the script returned numbers from a fixed list of feature names (`adapters/spitogatos_features.py`) plus a fingerprint the page computed from that list, so a copying slip would have been caught. All 50 rows matched. The script lived in the tab's session storage and went when the tab closed.
- **What the pages showed:** all 50 still live. Five advertisers crossed out nothing at all and one crossed out only a handful, so crossing out is a deliberate choice (D29 holds) and "not stated" is real.
- **Against answer key v1:** the crossed-out lists agree with the key wherever the key has a value, except one parking case where the text mentions parking and the key followed the text. They also give 26 "no" answers the key left blank (lift 8, parking 10, storage 8), mostly listings labelled before D29.
- **Code now reads them:** a crossed-out Ασανσέρ is no lift, Αποθήκη no storage, Parking no parking; a tick always wins. Only these three: a crossed-out garden doesn't mean no balcony, because a balcony is any private outdoor space.
- **Your storage rule:** "εσωτερική αποθήκη" counts as storage even when Αποθήκη is crossed out. The merge keeps the text's "yes" over the crossed-out "no" for storage only; the guide and the labelling pages say so.
- **Results on those 50 listings** (key v1, no new model calls; Haiku's answers came from the cache):

  | | Text-only fields | Missed | Invented |
  |---|---|---|---|
  | Code only | 72.1% | 48 | 21 |
  | Code only, crossed-out lists | 78.6% | 8 | 44 |
  | Haiku v2, fill | 69.5% | 44 | 31 |
  | Haiku v2, fill, crossed-out lists | 75.6% | 5 | 53 |

  Misses fall by about 40. "Invented" rises by about 22: mostly the crossed-out "no"s the key left blank. Table fields don't change (98.9% and 98.6%).
- **Round 3, 10 each (your choice):** from the 50, less round 2's listings, ranked by where Haiku with the crossed-out lists disagrees most with the key. You get GB's 10. Only 7 of yours were left, so GB gets those 7 plus 3 of his own as a self-check (the guide's "agree with yourself" test). The pages pre-fill the crossed-out "no"s like the table's values; parking still isn't pre-filled.
- **Say:** "Most of the misses weren't a reading problem. The page states 'no' with an icon, and my first collector threw it away. Revisiting 50 pages cut misses from 48 to 8."

## D35. "You're losing parking and balconies": the pages were, and answer key v2

- **Your observation:** parking (παρκινγκ, θέση στάθμευσης, γκαράζ) and balconies (βεράντα, μπαλκόνι, κήπος) were being lost, from the ticks, the text or both.
- **Where they were lost:** not in the pipeline. Against your 60 new labels, code plus Haiku found 24 of 25 parking spots and all 45 balconies. They were lost on the labelling pages: the pre-fill never showed parking (a rule from before parking was scored as has or hasn't), and it missed 11 of the 45 balconies, those only in the text or behind a ticked "Κήπος", which code didn't count.
- **Fixes:** the pages pre-fill parking from its tick (space) or cross (none); a ticked Κήπος is a balcony (a shared garden still isn't); parking the text mentions beats a crossed-out tick, as your label did, the same as storage (D34). The guide and the page rules say so.
- **The labels had the same blind spot:** round 2 agreement was 89.3% (your relabels) and 90.0% (GB's), with text fields at 63% and 65%. Parking alone was 34 of the 87 disagreements, mostly one of you writing "no" for a crossed-out Parking and the other leaving it blank, or one finding parking in the ticks or text and the other not. Round 3 agreed better: 95.7% (you) and 92.4% (GB). GB's self-check matched himself on every table field and 8 of 10 text fields.
- **Answer key v2** (`answer_key.py`, frozen 22 October): every human label, combined per listing. 70 listings have two or three labels. A value one labeller found beats a blank another left, because the rounds showed blanks are mostly misses; when labels give different values, the newer one wins, because it follows the newer rules. That filled 22 parking values, 10 metro, 8 lift, 6 storage and 5 balconies; the newer label settled 18 clashes, 8 of them condition (the new-build rule). The manifest lists every label used per listing. 12 listings still rest on one label made before D29.
- **Results on key v2** (no new model calls):

  | | Listings | Table fields | Text-only fields | Missed | Invented |
  |---|---|---|---|---|---|
  | Code only | 100 | 98.9% | 70.4% | 123 | 15 |
  | Code, crossed-out lists | 100 | 99.4% | 79.6% | 73 | 19 |
  | Haiku v2 + code, crossed-out lists | 100 | 98.9% | 81.2% | 56 | 26 |
  | Code, crossed-out lists | the 50 revisited | 99.6% | 86.3% | 17 | 11 |
  | Haiku v2 + code, crossed-out lists | the 50 revisited | 99.1% | **88.7%** | 7 | 13 |

  On the revisited half, both targets are met. On the other half, 46 of Haiku's 49 misses are parking, lift and storage: the crossed-out lists not read yet.
- **What's left on the revisited half:** metro, mostly rounding (700 m typed as 8 minutes where code works out 9) and labels left blank where the text gives a distance; three older labels that say "no storage" where the text has εσωτερική αποθήκη (D34 came after them).
- **Say:** "Two labellers looked unreliable on parking, and the model looked worse than regex. Both were the same bug: the labelling tool hid parking. Fix the tool, combine the two readers so a found value beats a blank, and the pipeline clears the 85% target."

## D36. Metro within a minute, and a check that the system now catches parking and balconies

- **Metro (your call):** answers within a minute on foot count as the same. Labellers and code turn metres into minutes slightly differently (700 m typed as 8, code says 9), and a minute doesn't change what a buyer sees. One shared function, `labels.same`, now decides agreement for both the agreement check and the extraction eval, so the two can't drift apart.
- **Results on key v2 with this rule** (text-only fields): Haiku v2 + code with crossed-out lists 89.9% on the 50 revisited listings (code alone 87.5%), 82.1% on all 100. Table fields unchanged (99.1%, 98.9%).
- **Round 4, a check rather than a label (your choice):** before revisiting the other 50 pages, you each check 5 random listings where the old pages hid parking or a balcony that answer key v2 says is there (55 such listings; picked with a fixed seed, never shared between you; listings you never labelled first, so GB, who has seen most listings, gets 2 new and 3 he has seen). These are "verify" pages: they pre-fill the whole system's answer (table, ticks and text, tagged "system"), not just what code reads, because the question is whether the system is right. In all 10 the system now shows the parking or balcony the old pages missed; your check says whether that, and everything else, is right on the live page.
- **Why pre-filling the system's answer is fine here:** D26 kept pre-fills to what code reads, so a guess couldn't anchor a label. A verify page isn't building the answer key; it measures the system, and the people checking it are the ones who know the rules best.
- **Say:** "I didn't take my own fix on trust. The two people who spotted the problem checked ten random cases of it against the live pages."

## D37. Check 4 confirms the parking and balcony fix; Check 5 tests the crossed-out gap

- **Check 4 result:** you both checked the same five listings (on GB's page). Of 105 fields each, you agreed with the system's answer on 103 and GB on 102. All five balconies and four of five parking answers were right. The only misses were on #53 (1120680865): lift and parking crossed out on the live page (storage too, for GB), and that listing is one of the 50 not revisited, so the system never saw its crossed-out list.
- **Check 5 (your call):** ten listings, five each (you then asked for a split; listings each of you never labelled come first): listings where the system says unknown for lift, parking and storage all at once, the three features a crossed-out list answers. Only 13 listings in the 100 are like that; ten were picked at random with a fixed seed, leaving out the round 4 pages. One (#81, on your page) is a revisited listing whose advertiser crossed out nothing, so unknown is right there: a control. The page pre-fills the system's answer, tagged "system", as in round 4.
- **Why:** to show, on the live pages, whether the unknowns are crossed-out "no"s the system can't see, before deciding on the other 50 pages.
- **Say:** "I let the two people who'd judge the fix pick the test: the listings where the system knows least."

## D38. Check 5, and the crossed-out lists for all 100

- **Check 5 result:** every difference between your checks and the system was a crossed-out lift, parking or storage the system called unknown, 26 in all; every other field agreed, and the control listing (a revisited page with nothing crossed out) matched on every field. Across Checks 4 and 5 you marked 37 of the 39 crossed-out lift, parking and storage features "no" and left 2 blank; none "yes". D29 holds.
- **The fix (your go-ahead):** I read the crossed-out lists on the other 50 pages, the same way as D34: feature names and icons only, a few seconds apart, the script checked by its fingerprint (all 50 matched), the tab closed after. The first 50 were read this morning, so I didn't reopen them. All 100 listings now have their lists; 5 advertisers crossed out nothing.
- **Results on key v2, all 100 listings** (no new model calls):

  | | Table fields | Text-only fields | Missed | Invented |
  |---|---|---|---|---|
  | Code only, crossed-out lists | 99.4% | 85.7% | 27 | 39 |
  | Haiku v2 + code, crossed-out lists | 98.9% | **87.1%** | 11 | 46 |

  Both targets are met on the whole set. Against your Check 4 and 5 labels the system now agrees on 418 of 420 fields; the two left are storage you left blank where Αποθήκη is crossed out.
- **What "invented" is now:** 24 of the 46 are lift, parking or storage crossed out on the page where answer key v2 is blank, mostly listings resting on one label made before D29. 10 are metro distances the description gives and the key left blank. The rest are scattered.
- **Say:** "Two people checked fifteen listings and found the same gap every time. Reading one more part of the page closed it: misses went from 56 to 11, and the pipeline passed its target on all 100."

## D39. Answer key v3, and Haiku against Sonnet

- **Answer key v3 (your call):** key v2 with a blank lift, storage or parking filled as "no" where the page crosses it out and the description doesn't mention it. A mention in the text still wins for parking and storage (D34, D35), and a lift the text mentions against a cross stays unknown (D25). Nothing a labeller answered is changed. 24 values were filled (10 parking, 9 lift, 5 storage) on 13 listings; each carries the note "filled by rule D29" in its evidence, and the manifest lists them per listing with the checksum of the key it came from. Why it's fair: in Checks 4 and 5 you both marked 37 of 39 crossed-out features "no" and none "yes".
- **Results on key v3, all 100 listings** (same prompt, same merge with code, crossed-out lists read):

  | | Table fields | Text-only fields | Missed | Invented | Cost for 100 |
  |---|---|---|---|---|---|
  | Code only | 99.4% | 90.5% | 27 | 15 | $0 |
  | Haiku 5.5 + code | 98.9% | **91.7%** | 11 | 22 | $0.078 |
  | Sonnet 5.5 + code | 98.9% | **91.7%** | 10 | 23 | $0.85 |

- **Haiku stays.** Sonnet costs eleven times as much for the same score. The two disagree on 17 of 2,100 fields and each is right about half the time (Haiku on condition and metro, Sonnet on year built). This is what the spec planned: the small model for bulk extraction, the bigger one for the conversation.
- **What's left is mostly the key and two rules, not the model:** 10 metro distances the description gives that the key left blank; 6 floors the key calls "ground" where the text says υπερυψωμένο ισόγειο, which the guide says is raised ground; 3 storage "no"s where the text has εσωτερική αποθήκη, from labels made before D34; 5 condition answers, mostly new build against unfinished.
- **A caution for interviews:** prompt v2 and the merge rules were shaped by reading these 100 listings' errors, so 91.7% is the score on a development set. A fresh batch, labelled blind, is the clean test.
- **Spend so far:** $1.01 of the $100 (Haiku runs $0.155, the Sonnet run $0.85).
- **Say:** "I ran the bigger model and it tied. That's a result: the cheap model is the right one here, and I can show why with numbers."

## D40. Prompt v3: the metro, and every Athens station

- **Why not a phrase list:** Haiku already found a metro distance in 23 of the 25 descriptions that give one; most metro "errors" were blanks in the key. A list of phrases would make the model behave like the regex and miss whatever isn't on the list. So v3 fixes the specific gaps instead.
- **What v3 changes:** a kilometres field ("0,8 χλμ.") that code turns into metres and then minutes, so code still does the arithmetic; all 66 Athens metro stations on Lines 1 to 3 and the line names (πράσινη, ηλεκτρικός, ΗΣΑΠ, κόκκινη, μπλε) in the glossary, because you plan to search more areas. They're kept once in `core/greek.py` (`METRO_STATIONS`, checked against the published station list on 22 October 2026; Line 4 is still being built), so search can use the same list. Rules written down: a station named instead of the word μετρό counts; an area's name alone doesn't, even when a station shares it; minutes by car or bus aren't on foot; when a sentence gives several distances, only the metro's.
- **No test listing in the prompt:** my first draft quoted three of our listings word for word; I replaced them with invented examples, because the spec keeps worked examples out of the test set. A check found no new quote from the 100 listings in the prompt.
- **Versions stay reproducible:** v1 and v2 keep the glossary and fields they ran with, so their cached answers still match (re-running v2 cost $0).
- **Result on key v3:** text-only fields 91.9% (v2 91.7%), metro 87% (85%), table fields 98.9%. Kilometres fixed (and that listing's balcony). Haiku already took the metro's 1500 m over a university's 650 m; the key's 650 is wrong and waits for the key check. A few other fields flipped between runs (two condition answers, one flag): the API has no temperature setting, so small run-to-run noise is expected.
- **Open:** "on foot" made v3 skip minutes that don't say how ("μόλις 5 λεπτά από το Μετρό", "10 λεπτά από τον σταθμό «Άγιος Αντώνιος»"). Whether those count as walking is your call.
- **Not doing:** walking distance from the map pin, scrapped (your call). The key check for the metro blanks waits.
- **Cost:** $0.083. Spend so far $1.09 of the $100.
- **Say:** "I didn't tell the model where to look; I fixed what it couldn't express. It had nowhere to put kilometres."

## D41. Metro minutes count only on foot, enforced in code

- **Your rule:** "μόλις 5 λεπτά από το Μετρό", or any minutes that don't say how, don't count: a 5-minute walk would say so. Metres and kilometres are distances, so they count as written; minutes by car or bus never count (D40).
- **Why in code, not a v4 prompt:** v3 already followed this most of the time but still took "6 λεπτά απο Μετρό Αιγάλεω". A check in code holds whatever the model does and costs nothing: when the model's metro answer came from minutes, code looks at the words it quoted in the description, plus a few characters either side, for "πόδια", "περπάτημα" or "πεζή". If none is there, the minutes are dropped. The code-only baseline follows the same rule.
- **Result on key v3** (no new model calls): Haiku v3 + code 92.1% on text-only fields, metro 88%; code alone 91.3%. Every "με τα πόδια" case kept; the key's two minute-based values both say on foot, so the key needs no change for this rule.
- **The guide and the labelling pages** now say it.
- **Say:** "When a rule is crisp, I put it in code. The model reads; code decides what counts."

## D42. The answer key check

- **What:** one page, "Answer Key Check", with the 21 values where answer key v3 and the listing seem to disagree: 12 metro (8 blanks where the description gives a distance, the 650 m that belongs to a university, two "500 m" typed as 5 minutes, and one 8 minutes the system can't find), 6 floors (ground against υπερυψωμένο ισόγειο) and 3 storage (εσωτερική αποθήκη). Each shows the listing link, the few words from its description that matter, the key's value and the proposed one. You pick, or type another value; each choice saves at once. Floor and storage have a "use the proposed value for all" button, because each is one rule.
- **Why this shape:** the proposed value is the system's reading, but metro is written the way the listing gives it (790 m rather than 10 minutes), so code converts and the key stops holding home-made conversions. The page carries short quotes only, never a whole description (the spirit of D28).
- **Next:** your choices become answer key v4, with every change recorded.

## D43. Answer key v4 from the key check

- **GB's decisions on the 21 values:** the proposed value on 20 (all 6 floors as raised ground, all 3 storage as yes, 11 metro values with metres as written), the key's value on 1 (8 minutes where "600 μέτρα" covers the town hall and the metro stop together).
- **Answer key v4** is key v3 with those 20 changes; the manifest lists each change per listing (from, to, choice) and the one kept, and every changed value carries a note in its evidence.
- **Results on key v4, all 100 listings** (no new model calls): Haiku v3 + code 99.3% on table fields, **94.8%** on text-only fields; code alone 99.1% and 93.1%; Sonnet v2 + code 99.4% and 95.0%, still eleven times the cost.

## D44. A clean test set: 10 blind-labelled listings from Pagrati

- **Why:** the prompts and merge rules were shaped on the first 100 listings, so 94.8% is a development score. The honest number comes from listings nothing was tuned on. A new area also tests whether the system holds up outside the three western suburbs.
- **What:** on 22 October I opened Spitogatos' first results page for homes for sale in Pagrati (30 cards), picked 10 at random with seed 2026 and saved their pages slowly in your Chrome, at least 3 seconds apart. Contact details are scrubbed as before, and each page's crossed-out feature list is saved with it from the start, so no revisit is needed.
- **Pagrati is now an area:** in `core/models.py`, with its spellings (Παγκράτι, Pangrati, Pagkrati) in `core/greek.py` and on the labelling page's area menu. The metro glossary already covers every Athens station (D40).
- **Blind labelling:** two pages of 5, split at random with seed 2026 (`split_at_random`, so no listing goes to both of you). They pre-fill only what code reads from the table, ticks and crosses, as in rounds 1 to 3, never the model's reading, so nothing the model says can anchor a label.
- **Frozen until scored:** prompt v3 and the merge rules don't change before the test runs. Then Haiku v3 + code reads the 10 (about a cent) and is scored against your labels.
- **Caveat:** 10 listings is small. There are about 50 text-only fields, so one wrong field moves that score by about 2 points. It's a sanity check that the development score isn't overfitted, not a precise number.
- **Say:** "I tuned on one set and tested on listings from another part of Athens that the prompt had never seen."

## D45. The clean test, scored

- **How:** your 10 blind labels became the Pagrati set's own answer key (v1, kept next to its data, never mixed with the 100). The code baseline and Haiku v3 + code ran with the prompt and merge rules unchanged since D41. `evals/harness/clean_test.py` does it in one command. Cost $0.008.
- **As labelled:** Haiku v3 + code 100% on table fields and **88.2%** on the 34 text-only fields (target 85%); code alone 100% and 91.2%.
- **What the misses are:** all four of Haiku's disagreements are facts the description states and the labels left blank ("δύο μπαλκόνια", "500 μέτρα από μετρό Αγ. Ιωάννη", "1 ευρύχωρο υπνοδωμάτιο", "1 χλμ από τη στάση μετρό Ευαγγελισμός"). None is a wrong value. Code alone also misses "χρήζει ανακαίνισης", which Haiku catches.
- **What it shows:** no new kind of error on an area the prompt never saw. The development score wasn't the product of tuning to the first 100. As in D35, a single labeller's blanks are mostly misses.
- **The honest number:** 88.2% stays the headline. A key corrected only where the system disagrees can only go up, because a fact both the labeller and the system missed is never looked at.
- **Pagrati key v2:** you confirmed all four in chat. Key v2 is key v1 with those four values (metro as written, 500 m and 1,000 m), each change recorded in its manifest. Scored with the saved answers, no new calls: Haiku v3 + code **100%** on table and text fields; code alone stays at 91.2%, because its rules don't read a bedroom count from the text or a distance in kilometres, and they miss "χρήζει ανακαίνισης". (I first guessed 97.1% for code; the run showed that was wrong.)
- **Say:** "On unseen listings, every disagreement was a fact my labellers missed and the model found, with a quote."

## D46. The interview eval

- **What it tests:** the interview prompt (Sonnet 5.5) on the 40 scripted chats. Each chat ends in a criteria card, scored against the card a perfect interview ends with.
- **How a chat runs:** the user's scripted turns go in order, word for word, whatever the assistant asked. They were written as answers to the questions a good interview asks, so an assistant that asks something else still gets the facts, but fails the must_ask check. When the script runs out, a card shown for confirmation gets a fixed "yes, go ahead", and that card is scored. If the assistant is still asking, a simulated user (Haiku 5.5) answers from the chat's facts only, or says it has no preference. After two such answers the last card is scored as unconfirmed.
- **Why scripted first, simulated second:** a fully simulated user would be a second model that can drift, add wishes or switch language on its own. The script keeps the test the same on every run. The model user only fills gaps, and only from facts.
- **Every reply is structured output:** the text the user sees, "ask" or "confirm", a tag for each thing it asks, areas it can't cover, advice it declined, and the card. Code checks the card with the same Pydantic models the search uses, so a card the search can't run on is an error the eval counts.
- **One tool, check_supply:** code counts how many snapshot listings pass the card's hard limits, and how many would pass with each limit dropped. When asks conflict, the model explains the trade-off with numbers code calculated. It runs on the private snapshot of 484 real listings, because the synthetic 60 are too thin to tell a hard search from an easy one. The transcripts stay private; the results file holds totals.
- **Scored in code, no model judge:** the spec keeps model judges for explanation quality. Fields (intent, areas, each hard limit set on either side) are correct, wrong, missed or invented; target 95% and no invented hard limit. Preferences need the right feature and bound; weights are checked only as strong or weak, and reported apart. Behaviours are checked from the tags, the reply text and the tool results: a question asked (with a question mark, Greek ";" included), the reply's language against the user's latest message, an area not covered named and kept off the card, a trade-off that quotes a number check_supply returned, declined advice flagged and pointing to a professional, a change confirmed. The advice checks are proxies, so I read those replies too.
- **Search areas:** Pagrati is an Area for the clean test (D44), but it has no search listings, so a criteria card can't ask for it. `SEARCH_AREAS` in `core/models.py` is the list the interview and the search use.
- **Two label fixes before the first run:** "new build" was 2020 in one chat and 2023 in another. It's now one rule, built in the last five years (2021 here), in the dataset and in the prompt, where code fills the year in.
- **Cost:** every call is cached by a hash of its request, so rescoring or a rerun with the same prompt is free.
- **First run, prompt v1, all 40 chats** ($1.21, about 3 cents a chat): fields **88.8%** (target 95%), **0 invented hard limits**, preferences 15 of 16 right on feature and bound, weights 13 of 13 in the right class, behaviours 98.8% (21 of 22 asks, all 40 language checks, all three areas not covered, both trade-offs with code's numbers, all four advice cases). Every chat ended with a confirmed card, 39 of them valid.
- **What v1 got wrong:** 16 of the 18 missed fields are one mistake. My prompt said "a hard limit only when stated as one", so "a two bedroom flat" became a preference. One more missed bedroom count came from the simulated user (below), and one missed intent from the prompt. Also: intent left blank when the user gave a price but didn't say "buy" (and an offer to "search both buy and rent", which a card can't do), "top floor" written as a word where the search needs a floor number (the one invalid card), and one question tag defined loosely.
- **Two harness bugs it showed:** the simulated user didn't know what the script had already said, so it once said "no preference on bedrooms" after the user asked for one bedroom; and it agreed to a change its facts didn't cover. Both fixed before the next run.
- **Say:** "The interview is scored like a form: every field it fills is checked in code, and the costly mistake, an invented hard limit, has a target of zero."

## D47. Interview prompt v2, card repair in code

- **Prompt v2, from the v1 misses:** a number given for price, size or bedrooms is a hard limit unless the user softens it ("ideally", "if possible"); intent comes from the price (tens of thousands is a purchase, a monthly figure is rent) and is asked only when unclear; floor_level takes floor numbers only, and "top floor" goes in an open question; clearer budget tags. The examples are invented ("a three bedroom house", "no mezzanine"), none from the 40 chats.
- **Card repair in code:** code checks every card with the search's own models. A card that fails goes back to the model once with the reason, marked as coming from code. If it fails again, it's an error the eval counts. In production that means the search never receives a card it can't run.
- **Simulated user:** now knows everything the user has already said, and says "no preference" to a change its facts don't cover.
- **Result, all 40 chats** ($0.93, 2.3 cents a chat): fields **98.8%** (target 95%, v1 88.8%), **1 invented hard limit** (target 0, v1 0), preferences 16 of 16 (v1 15, with 16 on the wrong side), weights 13 of 13, behaviours 98.8%, every card valid and confirmed, no repairs needed. Questions per chat fell from 1.65 to 1.1.
- **The three misses, for your call:**
  - en_11, invented property type: "the flat itself up to 210k" became an apartment-only limit. The user means "the home", not a type. I count it as a real miss.
  - en_13, property type: the model kept "studio", said no studio in Egaleo is listed, and offered to open it to apartments. It marked that reply as "confirm", so the harness's fixed "yes" kept the card. The label expects studio or apartment, which the user never asked for.
  - en_20, must_ask budget: the model asked intent and area first (two questions a reply), and the script gave the budget before it was asked.
- **Development score:** v2 was shaped on these 40 chats, as prompt v3 was on the 100 listings. The honest number needs new chats written by someone who hasn't seen the prompt.

## D48. Your rules for the three interview misses

- **"Flat" means an apartment or a maisonette**, never a detached house or a building. en_01 and en_11 now expect both types. "Διαμέρισμα" still means apartment only, until you say otherwise.
- **"Studio" means a small apartment of about 30 to 40 m²**, so en_13 expects studio or apartment, with a size preference of up to 40 m² (a preference, because "around" isn't a limit).
- **A basic fact the user gives unasked counts:** for intent, budget, area and bedrooms, must_ask also passes when the user gave it before the assistant asked, as long as the card ends up right. Clarifying questions ("is 200 the ceiling?") still have to be asked.
- **Next:** prompt v3 with these rules, run once you've decided on the narrowing question (one optional question when more than 50 listings match).

## D49. The narrowing question, prompt v3 and the simulated user's guard

- **Your rule:** when more than 50 listings pass, the assistant asks one optional question to narrow them: a deal breaker or a big plus. Code adds a breakdown to check_supply (bedrooms, size bands, how many have parking, a balcony, a lift), so the question uses real numbers: "124 match: 57 have 0 to 1 bedrooms, 50 have 2, 10 have 3 or more".
- **Prompt v3** also carries D48 ("flat", "διαμέρισμα", "studio"), always checks supply before a card, and treats a reply that offers a choice as a question.
- **Result, all 40 chats** ($1.36, 3.4 cents a chat): fields 97.5%, **2 invented hard limits**, preferences 17 of 17, behaviours 98.8%. The narrowing question went to all 18 wide chats and to none of the others. No field was missed in a wide chat. It cost 0.45 more questions and about 1 cent more a chat, and on these chats it couldn't add anything, because the simulated user has no extra wishes to give.
- **Why the misses happened:** three of the four came from the simulated user. It invented "at least three bedrooms, we're a family" and "at least two" (el_13, el_19), and it said "you choose whichever works best", after which the assistant dropped the 120 m² minimum (el_11) and widened the area (en_03, where the snapshot has no rentals at all).
- **The guard, in code:** the simulated user now names the facts its answer rests on. An answer with none, or with a number nobody gave, is replaced by a fixed "no preference" and marked in the transcript.
- **Prompt v4:** only the user loosens a hard limit, areas included, and only by saying which one and how; "you choose" or "no preference" isn't that. A snapshot with no listings of a kind is a data gap: say so once and keep the card. check_supply's note says the same.

## D50. Suggest easing one limit, then ask (prompt v4)

- **Your rule:** under 5 matches, the assistant suggests easing the one hard limit that frees the most listings, and asks. The card changes only after a yes to that change, or when the user names a change themselves. "You choose" or "no preference" isn't a yes, so the card stays.
- **Code works out "a little":** check_supply returns if_eased under 5 matches: price up 10% (rounded to €5,000, or €50 for rent), size down or up 10%, one bedroom fewer, each other covered area added, each with the count it would give. The model picks and asks; it never makes up a step or a count. When the snapshot has no listings of that kind at all (no rentals yet), there's nothing to ease: it says so once and keeps the card.
- **Eval, in code:** in a thin chat, a reply tagged ease_limit has to quote one of code's eased numbers; and a hard limit, areas included, that gets looser after anything but the user's own scripted words is an "unasked loosening", target 0.
- **One more harness fix:** in the first v4 run, the simulated user answered "yes, add Egaleo" (el_11), which its facts don't support, and the assistant correctly widened the area after that yes. No chat's facts say the user would loosen a limit, so a suggestion to ease one now gets a fixed "no preference". The rerun reused the cache and cost one cent; the first run's results are kept beside it.
- **Result, all 40 chats** ($1.29, 3.2 cents a chat): fields **100%**, **0 invented hard limits**, **0 unasked loosenings**, preferences 16 of 17, weights 13 of 13, behaviours 100%. Narrowing asked in 18 of 18 wide chats and no others; easing suggested with code's numbers in both thin chats. The one miss is en_18's "top floor ideally": floor 3 or above, where the label says 4.
- **Still a development score:** v2 to v4 were shaped on these 40 chats. The clean test is 10 new chats you and GB write.
- **Say:** "The model suggests, code counts, the user decides. A limit only moves when the user says yes to a specific change."

## D51. Your answers on the open list (22 October)

- **Clean test for the interview:** yes. You and GB each write 5 new chats on the "Interview Chats" page (round 7), without looking at the prompt or the 40 chats. For each: the messages in order, what you'd answer if asked anything else, the card it should end with, and what the assistant should ask or say. Each writer's chats save under their own id; only the owner reads everyone's. `interview_clean_test.py` turns them into the eval's format, and prompt v4 runs on them once, unchanged.
- **"Top floor" stays a floor number.** A ρετιρέ is the last floor of its building, and that can be the 1st floor, so "top" says nothing about height. Someone who wants the top floor wants height, so floor_level with a number is the right proxy. The en_18 label (4 and up) stays.
- **xe.gr: skipped for now.** It comes back when we add areas.
- **Possible expansions** now have their own list, `docs/expansions.md`: xe.gr, more areas, rentals, investor versus live-in buyer, a rented field, lift reaches the floor, delivery date, condition as a filter, either/or musts.
- **API key:** stays until the project is done, then delete it and make a new one.

## D52. The interview clean test, first run

- **What ran:** prompt v4, unchanged, on the 10 chats you and GB wrote (5 each, 8 Greek, 1 of them Greeklish, 2 English). Cost $1.10, 11 cents a chat: these conversations run longer than the 40 (4.5 replies, 6 questions a chat), so my "under 50 cents" was wrong.
- **One scoring fix first:** Greeklish ("Kalispera chat, tha ithela…") now counts as Greek in the language check. Without it, a Greek reply to a Greeklish message would fail. The model never sees this check.
- **As labelled:** fields **43.5%**, 2 invented hard limits, asks 22 of 38, every reply in the user's language, narrowing asked in all 5 wide chats and no others, no limit loosened without a yes.
- **What the 35 field misses are,** checked against the chat text:
  - **24 are limits the cards add that the user never said.** A minimum price on 9 of 10 cards; a few percent above the stated budget (around 200 to 220k, 900 to 950, a 350k loan to 400k); size ranges nobody mentioned; extra types (loft or maisonette for "διαμέρισμα", against D51); extra floors ruled out ("no basement and ground" also ruling out semi-basement and raised ground).
  - **3 are slips in the cards:** "για αγορά" labelled as an investment (gb_3), and "2 δωμάτια" and "3 δωμάτια" left off two cards (gb_4, gb_5).
  - **4 are real system misses:** a "500-600" rent turned into a soft preference, so the card had no price ceiling at all (gb_2); "σε όροφο" not turned into ruling out the ground floors (gb_2); "τουλάχιστον 2 δωμάτια" left off after the rooms-or-bedrooms question went round in circles (gb_1); "studios are fine" not turned into studio as a type (mike_2).
  - **3 are judgement calls:** whether a "700-800" range sets a minimum, and whether "ιδανικά 30 to 50 m²" is a limit or a wish.
  - **1 is the harness:** no chat filled in "if it asks about anything else", so the simulated user could never confirm investor mode (mike_5).
- **Other findings:** parking and a lift stated in gb_1 didn't reach the card; one card had "renovated_year equals true", which code should refuse (a year needs a number); two chats ended unconfirmed because the assistant kept asking and the simulated user had no facts to answer from.
- **Why I haven't rescored:** the cards follow different rules from the ones the system was built to (only what the user says; D46 to D51), so 43.5% mostly measures that gap. Once you settle the rules, the saved transcripts are rescored for free.

## D53. Your rules for prices, rooms and types (interview v5, built, not run)

- **"Around X" means X plus or minus 10%.** The model only marks that the user said "around" (budget_around); code widens the price. A range the user gave ("περίπου 500-600") widens the same way.
- **A lowest price, set by code:** when the user gave none, 80% of the top price for a home to live in or to rent, 50% for an investment, rounded to €5,000 (€50 for a monthly rent). It keeps out wrecks and ads with no real price, it's shown on the card, and the user can change it. The user's own minimum always wins. "Around 200" therefore searches €180k to €220k.
- **Why code and not the model:** the rules are arithmetic, so they live in one tested function (`search_card`). The model writes down what it heard, so a card can't drift by 10% each turn, and the eval checks the model on what it heard.
- **"Δωμάτια" means bedrooms,** written on the card ("3 υπνοδωμάτια") so the user can correct it, with no question. Listing words like δυάρι keep counting the living room.
- **"Διαμέρισμα" is apartment only.** When an apartment search is thin, code adds "add a maisonette" and "add a loft" to the easing options, with their counts, and the assistant asks first.
- **Also in v5:** "σε όροφο" rules out the ground floors; a stated range sets both prices; code refuses a confirmed card with no top price (gb_2 had none) and a preference of the wrong kind (a year needs a number, a balcony a yes or no; mike_3 had "renovated_year: true").
- **Ranking:** a ρετιρέ with no floor number used to count as the highest floor. Following D51 its height is now unknown.
- **Eval:** "around" is scored as its own field; switching a card to "around" without the user's yes counts as loosening a limit. Three dev chats changed by these rules: el_01 and en_02 no longer need the ceiling question, el_09 no longer needs rooms or bedrooms.
- **Harness:** the simulated user now confirms what it has already said ("για επένδυση" in mike_5 couldn't confirm investor mode before).
- **Not run yet,** at your request. The clean cards need your answers first (below, in chat).

## D54. The details settled on 22 October

- **Rentals aren't supported yet.** The assistant says so once and offers to look at buying; code refuses to confirm a rental card. Five chats became checks of that instead of scored cards: el_03 and en_03 in the 40, gb_2, gb_4 and mike_1 in the clean test. Rentals are on the expansions list.
- **To live in or as an investment?** The lowest price depends on it (80% or 50%), so when a purchase doesn't say, the assistant asks once. "Investment" as the answer is the user's own choice of investor mode. With no answer, it's a home to live in. In the 40, every purchase that doesn't say who it's for or that it's to rent out (34) now expects the question; gb_3, whose card says investment though the chat doesn't, gets the fact "investment, to rent it out" so the simulated user can answer.
- **Floors:** no basement also rules out the semi-basement, and no ground floor the raised ground (el_02 and en_07 updated in the 40).
- **"Renovated" with no year** means renovated in the last 10 years, so 2016 or later; code fills the year in.
- **No question about the year built or the costs unless the user brings them up.** Those ticks are off the clean cards.
- **The clean cards, rewritten to these rules** in one table (`FIXES` in `interview_clean_test.py`), each change with its reason in `changes.json`; the cards as written are kept beside them.
- **mike_4: 400k, reached only by asking.** "A loan of up to 350k" isn't the price, so the assistant should ask whether savings come on top. The chat gets the fact "plus about 50k of my own" so the simulated user can answer, and the prompt gets a general rule: a loan isn't the price, ask about savings, never work out what a bank would lend. That rule came from looking at a clean chat, so mike_4 is no longer fully blind.
- **Not run yet.**

## D55. Interview v5, run on both sets

- **The 40 chats** ($1.40, 3.5 cents a chat): fields **100%**, **0 invented hard limits**, preferences 16 of 17, behaviours **100%**: all 34 purpose questions, both "rentals aren't supported yet", the trade-offs, the advice, every reply in the user's language; no limit loosened without a yes; easing suggested with code's numbers in all 3 thin chats; narrowing asked in 3 of 4 wide chats.
- **The clean 10** ($1.06, 11 cents a chat): fields **82.9%** (as written 43.5% with v4), **0 invented hard limits**, behaviours 97.1%, rentals 3 of 3.
- **What the 6 clean field misses are:**
  - 3 investment chats ended as "buy". In mike_2 and mike_5 the user says investment outright; the assistant asked two or three times to confirm investor mode, and the simulated user kept saying "no preference" though it's told to confirm what it already said. In gb_3 the assistant asked "to live in or as an investment?" twice while GB's script answered other things, so the fact never came up.
  - 3 in mike_3: "ιδανικά … 30 to 50 m² with 1 bedroom" became nice-to-haves under the agreed rule that "ideally" softens; the card has them as limits. The assistant asked "essential or just ideal?", and the simulated user had no fact to answer from.
- **Real bugs found:** "renovated after 2015" became 2016, because the 10-year default overrode the user's own year (el_17); and in mike_3 the assistant said "Athens isn't covered yet", though our three areas are in Athens.
- **Two measurement fixes, rescored for free:** rental chats no longer score questions a rental doesn't get; "wide" now means the card's own check, not a probe of the whole snapshot (el_02, en_18).
- **Weights:** 2 of 6 checked weights agree on the clean set ("I like big balconies" and "βεβαιώσου αν έχει μπαλκόνι" are a must on the cards, a plain wish to the model). Weights are judgement; they're reported, not scored.
- **Still development scores** for the 40; the clean 10 are partly shaped now (D54), so they're the closest thing to a fresh test we have.

## D56. Your four calls for v6 (built, not run)

- **Investor mode is confirmed on the card,** as the spec says: when the user says investment, the card shows "investor mode" and confirming the card switches it on. No separate question that can go unanswered (mike_2, mike_5).
- **The user's own renovation year wins** over the 10-year default ("after 2015" is 2015, el_17).
- **Egaleo, Peristeri and Chaidari are in Athens:** "Athens" on its own gets "which of the three, or any?", not "Athens isn't covered" (mike_3).
- **"Ιδανικά" before a list:** a size or a bedroom count stays a limit, widened by code, 10% either side for size and one bedroom either side; anything else is a wish. "Ideally 30 to 50 m² with 1 bedroom" searches 27 to 55 m² and 0 to 2 bedrooms. That needs a maximum bedroom limit, now in the search's own filter (`max_bedrooms`), which "up to 2 bedrooms" also uses.
- **"Ιδανικά" before a price means "around"** (you confirmed): a price can't be a wish, because a card needs a top price (D53). mike_3's "idanika ... mexri 200000" searches €180k to €220k.
- **Eval:** "ideally" is scored as its own field, like "around"; adding it to a card without a yes counts as loosening; a confirmed card with investor mode counts as confirming it.

## D57. Interview v6, run on both sets

- **The 40 chats** ($1.66, 4.2 cents a chat): fields **100%**, **0 invented hard limits**, preferences **17 of 17** (el_17's "after 2015" now stays 2015), behaviours **100%**, narrowing in 3 of 3 wide chats, easing with code's numbers in 3 of 3 thin chats, no limit loosened without a yes.
- **The clean 10** ($1.08, 11 cents a chat): fields **92.1%** (v5 82.9%, v4 43.5% as written), 1 invented hard limit, preferences 12 of 13, behaviours **100%**, rentals 3 of 3. All three investment chats now end in investor mode, confirmed on the card.
- **What's left on the clean 10:**
  - **mike_3, a real miss:** the assistant caught "idanika" before the price (around, so €180k to €220k) but not before the size and bedrooms, so they stayed exact. It then found 2 listings and suggested raising the size to 55 m², the margin the rule would have given.
  - **mike_2, a judgement call:** "one bedroom but studios are fine" became "up to 1 bedroom", which takes studios in; the card says apartment or studio with no bedroom limit. Both say roughly the same, but the eval counts the first as an invented limit.
  - **mike_4, a judgement call:** "high floors" became floor 4 and up; the card says 3.
  - **Weights:** 3 of 6 checked weights agree; reported, not scored.
- **Two measurement fixes, rescored for free:** "which of our three areas?" counts as asking for the areas (mike_3); a change counts as confirmed on the first card shown after it, with a question in between allowed (en_19 asked first whether €220k is the bank's figure, the D54 loan rule).
- **Where to stop:** the dev set is at 100% and the clean set's remaining misses are one real slip and two judgement calls. Another round would be tuning to 10 chats we've now read closely. The next honest test is new chats nobody has seen.

## D58. Two last cards, and the go for v1

- **mike_2:** "one bedroom but studios are fine" is "up to 1 bedroom", as the assistant read it. **mike_4:** "high floors" start at floor 4. With these, prompt v6 on the clean 10 scores **97.3%** of fields (target 95%), **0 invented hard limits**, preferences 13 of 13, behaviours 100%. The one real miss left is mike_3's "idanika" before the size and bedrooms.
- **v1 features, approved:** the extraction and the interview's tools on the MCP server, a small web API, and the React app from D20 (chat, criteria card, table view).

## D59. v1: the server's tools, a small web API and the app

- **Your rules live in one place:** `core/card_rules.py`. The interview, the MCP server's search and the web API all call the same function, so "around 200k" means €180k to €220k everywhere, and the evals test that one function.
- **The MCP server, v1:** `search_listings` takes the card as the user said it (with "around" and "ideally") and returns the limits it applied; `check_supply` counts what each limit costs; `extract_listing` runs the measured extraction (Haiku 5.5, prompt v3, the on-foot rule, merged with the page's own fields, the page winning); `criteria_interview` is the interview prompt for clients that run their own model, such as the Claude desktop app.
- **A web API on the standard library** (`api/server.py`): no new Python dependency. It listens on 127.0.0.1 only, keeps chats in memory, and calls the same interview, rules and search code the evals measure. It refuses rentals.
- **The app (D20): React, Vite and TypeScript** in `app/`, five pinned packages (react and react-dom 18.3.1, vite 5.4.11 with its React plugin 4.3.4, typescript 5.6.3) plus their types. Three parts: the chat; the criteria card, split into "never broken" and "nice to have", editable, showing what the search will really run on ("searched as €180,000 to €220,000") and nothing searched until you press "Confirm and search"; and a sortable results table with price changes and first-seen dates (the listing summary gained both).
- **Checked end to end:** a real chat on synthetic listings ("Ψάχνω διάρι ... γύρω στις 200 χιλιάδες, με μπαλκόνι") gave the right card, 1 bedroom from "δυάρι" despite the typo, €180k to €220k, balcony as a wish, and the search returned 5 homes, none breaking a limit. The page fits a phone's width.
- **Search safety, rebuilt:** with the server adding a lowest price, each case's expected list is now computed on the limits the search runs on, and the independent checker also checks the new bedroom maximum. 0 breaks, recall 1.00, precision 1.00.
- **Open, your call:** the 80% lowest price hides 46% to 78% of the homes within budget on the real listings. I recommend 50% for everyone as a junk filter and letting ranking do the narrowing.

## D60. The lowest price is half the top price

- **Your call:** the lowest price is 50% of the top for everyone, to keep out wrecks and ads with no real price. Ranking, not a hard floor, does the narrowing.
- **Measured on your real listings:** the 80% floor hid 46% to 78% of the homes within budget; 50% hides 3% to 23% ("up to €200k in Egaleo": 88 homes, 68 shown, against 19 before).
- **One number in code** (`LOWEST_SHARE` in `core/card_rules.py`). The search safety lists were rebuilt on it: 0 breaks, recall and precision 1.00, and the Greek-floors case (ss05) has listings to test again.
- **Prompt v7** is v6 without the percentages: the assistant quotes the range code returns, so the number can change again without touching the prompt. Not run yet; the app uses it.
- **The purpose question stays** (D62), though the lowest price no longer depends on it.

## D61. The product's flow: no confirm step, a bar above the deck

- **Your call:** while chatting, the chat takes the full width. When the assistant has what it needs, the swipe deck comes straight up; there's no card to confirm inside the chat. The card lives on as a one-line bar above the deck ("Egaleo · €180–220k · 2+ bedrooms · balcony"). Changes happen by chat ("make it 220k") and rerun the search.
- **What this changes in the spec:** "nothing is searched until they confirm" goes. It was there because a wrong hard limit hides homes silently. Two things keep that check: the assistant's last message says in one sentence what it will search, and the bar always shows the hard limits (area, price range, bedrooms, floors ruled out); nice-to-haves can shorten to "+2 more". Investor mode shows on the bar too. The repo's `docs/spec.md` is updated; your original in the Project is unchanged.
- **When:** with v2, the swipe deck. The v1 app keeps its side-by-side card and table, which is the quickest way to test the interview and the search.
- **For the evals:** the assistant's "confirm" becomes "ready to search", and the simulated user's fixed "yes" becomes "no objection", so the scores keep their meaning.

## D62. The purpose question stays, for investor mode

- **Your call:** keep asking "to live in or as an investment?" when a purchase doesn't say. Investor mode will grow its own tools, such as ROI calculations, so knowing who's investing early matters even though the lowest price is now the same for everyone (D60).
- **On the expansions list:** investor mode with ROI and more, calculated in code.

## D63. When a search finds fewer than 5, code offers ways to widen it

- **Your test:** "an apartment in Egaleo, around €190k, ideally 80 m²" found 1 home, and nothing offered to widen it. You expected the assistant to ask about widening the size and the price past the 10%.
- **Why it happened, three reasons:** the assistant checked supply only just before showing a card; the app's search button had no widening step at all; and the server ran on the 60 synthetic listings, where that search finds 1. On your real listings it finds 10, so no widening is needed there.
- **What changed:**
  1. **Code's options** (`eased` in `agent/interview.py`): each one now carries the exact limits it would set, the lowest price can be eased too, and there's a new "together" option, every number one step wider at once, for when no single change reaches 5. On the synthetic example: size 65 to 88 m² gives 5; price €155,000 to €230,000 with size 65 to 97 m² gives 7.
  2. **Prompt v7:** the assistant calls check_supply as soon as it knows the area and the top price, not only before the card. If fewer than 5 pass, it offers the smallest change that reaches 5 (one limit if one is enough, otherwise "together"), gives its numbers and asks.
  3. **The app:** when a search finds fewer than 5, the search route returns the options and the app shows up to four as buttons with their counts. A click is the user's yes, so D50 still holds: nothing widens without one. The card then holds exactly the numbers that were counted, with "around" and "ideally" switched off for what changed, so the rerun finds the number on the button.
- **Why code picks the steps:** the counts are calculations, so code does them; the model only chooses which option to suggest and how to say it.
- **A gap left for v2:** the assistant doesn't hear about a button click (or a hand edit to the card), so a later chat message can bring the old numbers back. v2 routes every change through the chat (D61), which closes it.
- **Not measured yet:** prompt v7 needs its eval run (about $2.70). The eval already reads the numbers inside each option, so a count the assistant quotes is checked against code.

## D64. Choices for v2, the swipe deck

- **Photos (your call):** on your real listings, the card's main photo loads from the portal only when that card is on screen, the same as opening the listing yourself. Nothing is downloaded or stored. Synthetic listings in the public repo get placeholder pictures. This is the one place v2 touches a live site.
- **Export (your call):** a CSV download that opens straight in Google Sheets. It needs no new dependency and no Google sign-in. Sending straight to Google Sheets can come later, or Claude can do it in the desktop demo.
- **Reject reasons (your call):** the spec's six: too dark, too small, bad floor, needs work, too expensive, wrong area.
- **"Why this one" reasons come from code, not the model:** code picks the card's two strongest matches to your preferences and words them from a template ("Balcony, as you asked"). They can only point to real fields, which is what the explanation eval checks, and they cost nothing.
- **Swipes stay local:** saved in `data/private/`, never pushed. The record holds the listing, like or reject, any reasons and the deck position, as in spec section 6.
- **Still open:** endless deck or 20 a day, and whether to have a super like. Explained to you; my suggestion is endless and no super like, to revisit after a week of use.
- **Done when (spec):** the explanation eval passes and your like rate is recorded, from about 100 swipes on real listings over a few days. That rate is the baseline the learned ranking in v3 has to beat.

## D65. Prompt v7 passes; the easing check learns the "nothing reaches 5" case

- **Results:** 40 chats: fields 100%, 0 invented hard limits, 0 unasked loosenings, behaviours 100%, 17 of 17 preferences with the weights agreeing. Clean 10: fields 97.3%, behaviours 100%, the same single miss as v6 (an "ideally" the card didn't carry). Together $3.02, so about $15.40 spent of the $100.
- **The early supply check works:** the assistant now sees a wide search in 13 chats instead of 3, and asked a narrowing question in all 13 without adding questions overall (2.1 a chat, as in v6). Tool calls went from 111 to 132, which is the extra early check.
- **One grader fix, no prompt change:** en_10 asks for 4 bedrooms over 130 m² under €160,000 in Egaleo. Nothing passes, and no widening reaches 5 (together gives 2). The assistant said exactly that, with code's counts, and kept the card as given. The grader only counted a suggestion that asks to ease a limit, so it marked this a miss. Now, when no option reaches 5, explaining with the counts is what passes, and the summary counts such chats separately ("nothing_reaches_5"). The v7 results were rescored, with no calls; v6 is unaffected (all its thin chats had a fix).
- **Why it matters in an interview:** a grader can be wrong the same way a model can, and a miss has to be read before it's believed. This is the third grader slip the chats have caught (D48, D52), and each one was fixed in code with a test.

## D66. The v2 plan: a check-in after every 10 swipes, found by code, worded by the assistant

- **Your call:** chat one to three messages, swipe, and after a few swipes get a question or a suggestion from the assistant based on what you swiped, so the next swipes fit better. Your example: someone keeps liking homes built from 2015 on, so the assistant offers a limit on the year built. The spec had this after 15 to 20 swipes; it now comes every 10.
- **Why 10, not 5:** after 5 swipes nearly every field splits by chance, and the user gets a wrong question. At 10, with at least 3 likes and 3 rejects that state the field, a clean split means something. The number is one constant in code.
- **Code finds the pattern** (`learning/patterns.py`): it compares likes with rejects on year built, renovated, floor, size, price, €/m², energy class, metro walk, balcony, lift, parking and storage, plus the reject reasons. A pattern counts only when nearly all likes sit on one side of a line and most rejects on the other, with enough of each. Code keeps the strongest one, with its evidence as counts ("0 of 6 likes built before 2015, 7 of 8 rejects were") and the exact change it would make. The model never sees the swipes, only this.
- **Limit or ranking, decided by the count:** code counts what the change would leave as a hard limit. 5 or more (the THIN line from D50), and it's offered as a limit; fewer, and the same thing is offered as a strong preference, which ranks those homes first without hiding the rest.
- **The assistant words it and asks** (prompt v8): the suggestion goes into the chat as a message from code, the assistant puts it to the user in their language with the counts, and the user answers in the chat: yes, no, or a different number. Nothing changes without a yes (D50). A declined suggestion isn't repeated.
- **In the deck:** every 10 cards, a card from the assistant appears in the deck itself, with the question and a reply box. Every change still goes through the chat, which also closes the D63 gap (a button or a hand edit the assistant never heard about).
- **A new hard limit, min_year_built:** "built from 2015 on" can't be a limit without it. It's filtered in code like the others, unknown years fail closed, and the search safety checker learns it. The interview still records a year the user mentions as a preference ("not too old" is a wish); the limit comes from a check-in the user accepted, or from the user asking for it as a limit.
- **Explore cards, 1 in 5:** kept from the spec. Once the deck shows only homes built from 2015 on, it can never learn the user would have liked a renovated 2005 one.
- **Daily cap, later:** endless now, a cap per user per day in the final version (your call). One constant in code, off while testing, counted from the swipe log.
- **Testing costs nothing:** pattern finding is code, so it runs on the frozen snapshot with made-up swipe histories of known taste, and must stay quiet on random swipes. The assistant's wording is checked as its trade-offs are: it must quote code's numbers.

## D67. What the suggestion eval changed in the pattern finder

- **Why an eval before tuning:** the first run of the pattern finder on 30 made-up swipe histories gave 70.6% precision. Two "false alarms" and three "wrong changes" were real findings about the rules; five "misses" were histories with nothing to read (0 or 1 likes), so their labels were wrong, not the code.
- **Four changes, all in code, all one constant or one line:**
  1. Most rejects on the other side now means 70%, not 60%. At 60%, three chance likes under a price line plus 6 of 9 rejects above it read as a pattern on a random history.
  2. Low floors rejected with no reason given need four rejects before they count; with "bad floor" said, three are enough. Three silent rejects on low floors turned up in random swipes.
  3. A pattern's strength counts every swipe, not only those that state the field. A line through 14 swipes now outranks one through the 10 that happened to state the metro walk, which had put "under 10 minutes from the metro" ahead of "100 m² or more" for someone liking big homes.
  4. On a tie, a field that can be a hard limit comes before one that can only rank, because it ends up on the bar where the user sees it.
- **Labels fixed too:** a history whose taste leaves fewer than 3 likes or 3 rejects is labelled "nothing to read", and "high floors" accepts either "floor from 2" or "no low floors", since both say the same thing.
- **After:** precision 94.4%, recall 94.4%, no false alarms, every evidence count recounted correct. The one miss left is a history where 11 of 11 likes have a balcony and 3 of 3 rejects don't, which the swipes support exactly as well as the floor pattern the taste was written with.
- **A limit of the synthetic set:** year built is known for every synthetic listing but for only 47 of your 484 real ones, so on your data the year pattern will rarely have three known values on each side, and a year limit would hide the 437 homes that don't state one. The finder stays quiet rather than guessing; more detail pages (D24) would feed it.

## D68. Every new or refreshed dataset reads the listing pages, not only the result cards

- **Your call:** the listing-page reader was built and measured for a reason, so it's the default whenever the data is built, refreshed or expanded. My miss: I treated the 100 listing pages as an eval set and kept the product's snapshot on result cards only, which is why it knows the year for 47 of 484 homes.
- **The pipeline from now on, for Spitogatos:**
  1. Result pages find the listings (about 30 cards a page).
  2. Each listing page is opened in your Chrome, slowly, and its table, ticked and crossed-out features and description are saved, scrubbed of contact details (D24, D29).
  3. Code reads the table and the ticks (`adapters/spitogatos_details.py`); Haiku reads the description (prompt extraction_v3); they're merged with the rules the extraction eval measured, the table winning on a conflict (D33 to D43).
  4. Code checks every record against the same models as before, so a phone number or an impossible value is refused, not stored.
- **What it was measured at:** Haiku plus code, 99.3% on table fields and 94.8% on text fields against answer key v4 (D43); Pagrati clean test 100% and 88.2% (D45).
- **spiti24 stays on result cards** until its pages get the same treatment: a reader, a labelled set and an eval. Its listings are mostly copies of Spitogatos ones (D18).
- **The evals still run on the frozen 20 October snapshot**; a new dataset is for the product.
- **First use, 23 October (your ask: run the product on the pages we already read):** `adapters/page_snapshot.py` turned the 100 listing pages of 20 October into `data/private/snapshot_pages.jsonl`. Every Haiku reading was already cached from the extraction eval, so it cost nothing. Known for these 100 homes: year built 92 (35 from the cards alone), floor and energy class 100, parking and storage 96, balcony 88, renovation year 31, metro on foot 22. Photo links only 13, because the pages were saved without their gallery. The independent checker found 0 broken limits on decks in all three areas.
- **What 100 homes means for testing:** about 33 per area, so a deck runs out fast (Egaleo up to €200k: 16 homes; Peristeri up to €180k: 5). The "typical €/m²" on the cards also comes from those 33, so it's a rough figure.

## D69. Kypseli and Pagrati join, and the covered areas follow the data

- **Your call:** the next dataset covers Egaleo, Peristeri, Chaidari, Pagrati and Kypseli, up to 1000 Spitogatos listings, collected by Claude Code on your Mac with your Chrome, so the data goes straight to your machine.
- **Why the areas can't just be added to a fixed list:** two interview chats (el_06, en_06) test that Kypseli and Pagrati are not covered, and the evals run on the frozen three-area snapshot. So the covered areas are now whatever the loaded dataset holds at least 10 homes for sale in (`adapters/snapshot.py`, `data_areas`). The evals still see three areas and score as before; the app on the new dataset sees five. Requests to the model are byte for byte the same for three areas, so the interview cache still holds.
- **The prompt says where the areas are:** prompt v8's area sentence now comes from code. For three areas it reads exactly as before; for five it says the first three are western suburbs and Pagrati and Kypseli are central Athens. v8 hasn't been run yet, so nothing measured changes.
- **The recipe is written down** (`docs/collecting.md`): the rules, the two file formats, the selectors that worked on 22 October, a checkpoint after 5 pages, and the build command, so the Mac session follows a fixed method instead of improvising, and every refresh is the same.
- **The build command now takes raw files** (`adapters/page_snapshot.py --cards --pages`): it reads the cards itself, uses a page's own crossed-out lists and photo link, and keeps a listing whose page failed as a card alone, counted. It rebuilds the 100 pages byte for byte, and builds the 10 Pagrati pages with no model calls.

## D70. Every value from the listing page; result pages only find the listings

- **Your call:** take everything from the listing page and move on. The area can't be wrong, because it's the area that was searched: on 20 October, 270 of 270 listings found by an area's search were in that area by their own card.
- **What the page gives now:** type and size from its title, bedrooms and bathrooms from its room badges, the neighbourhood from the line under the title, the date the ad was published from the table ("Δημοσίευση αγγελίας"), and everything else as before (D68). The collection script saves those parts since the 23 October run.
- **The cards stay as a free check:** the result page is visited anyway to find the links, so its cards are saved, and `--check-cards` reports field by field how often the page reading agrees with the card. They're never used as data. A listing whose page failed is left out rather than kept as a card.
- **Bedrooms by badge order:** if a badge shows only a number, the first is bedrooms and the second bathrooms, the order on the page. The check against the cards is what proves or breaks that assumption; it's the first thing to read on the 50-listing test.
- **Older pages** (the 100 of 20 October, the 10 Pagrati ones) lack the title and badges, so they still take those from their card. They rebuild byte for byte.
- **The test, 24 October (your ask: 50 listings):** 50 pages, 10 per area, read on their own and compared with their cards: 50 of 50 agree on area, neighbourhood, type, size, bedrooms, bathrooms and price. Because the check is free, it then ran on all 916 pages that carry the new fields: 0 disagreements on any field (bedrooms stated on 884, bathrooms on 890, both sources silent on the rest). Badge order never had to be guessed: every badge says "υ/δ" or "μπ".
- **The location line** reads "Λιούμη, Αιγάλεω (Αθήνα - Δυτικά Προάστια)"; the neighbourhood is the part before the comma, once the bracket is dropped.
- **The 84 early Egaleo pages** were saved before the new fields were added. Your call: no card data for them either, so they're fetched again (84 requests, about 8 minutes, same pace and rules) with `PM.only()` in the collection script. The build keeps one record per listing, preferring the copy with its title and badges, so the refetch simply replaces the old copy and the dataset is page-only throughout.
- **Two fixes found on the way:** the build now splits files on newlines only, because `splitlines()` also breaks on the U+2028 characters some descriptions hold (the run's first build failed on it); and the Mac session's card parser fix (a card without the generated sentence kept losing its floor) and its chat-scroll fix are committed.

## D71. Skip, back, "Can't judge" and "Other…" on the deck

- **Your calls:** an "Other…" tile with a text box after a reject; a "Can't judge" option for a listing that doesn't let you decide (your example: photos that are a floor plan and a filler image); and two icons between Reject and Like, back and skip.
- **A skip is no verdict.** It goes in the swipe log but counts in no like rate, triggers no check-in and teaches no pattern, because the user didn't decide against the home. A skipped home comes back at the end of the deck, marked "You skipped this one earlier". Check-ins now count likes and rejects only.
- **"Can't judge" is a skip with a reason:** "Photos don't show it", "Too little information" or "Other…". Recorded as a reject, a bad listing would have taught the ranking that you dislike its size, area or price. Kept apart, it's listing-quality data for the expansion noted earlier (reject reasons as facts about a listing).
- **"Other…" opens one short line** (up to 300 characters), saved with the reason "other" and scrubbed of contact details like every other text. Code can't learn from prose, so for now the notes are counted; later Haiku can sort them into existing reasons or new themes, which is how missing tiles get found.
- **Back takes back the last decision:** it's removed from the log as if it never happened, and its card returns to the front with its reasons. While the assistant's check-in question is waiting, back is off: answer the question first. Keyboard: ← reject, → like, ↓ skip, Backspace back.
- **The swipe record** gains "skip" as a decision, the can't-judge reasons and an optional note. Older logs read as before.

## D72. A check-in can't get lost or block for good

- **What you saw:** "the chat doesn't interrupt me no matter how many swipes". Replaying your 30 swipes of 23 October through the pattern finder, it should have asked after 20 (5 rejects on a ground floor, 4 marked needs work).
- **The likely cause:** a check-in waits for its answer, and while it waits no new one is made. The app didn't keep the waiting question across a reload, so a check-in shown once and lost on a reload blocked every later one until the next chat message.
- **The fix:** the server returns a waiting check-in with the state, so a reload shows it again; and a question left unanswered for 10 more likes or rejects is taken as a no, so it can never block for good. The check-in ladder (D75) also means every 10 swipes say something.

## D73. Three search additions: condition, price per m² and stairs

- **Your calls (24 October):** condition in the chat search, a price per m² limit, and a limit for no stairs above the 1st floor without a lift. Planned for v3 and built first.
- **Condition is a wish by default:** "no renovation projects" or "δεν θέλω μαστορέματα" sets move_in_ready (renovated, new build or good, against needs work or unfinished) as a strong wish. In your 1,000 listings 286 don't state a condition, and a hard limit would hide them too. Only when the user insists does it become a hard limit (exclude_conditions), and the assistant says how many unstated homes drop out. A renovation year still goes to renovated_year and "new build" to year_built: both rules are measured, and year built is known for far more homes.
- **Price per m² is a hard limit** (max_price_per_m2). Code computes it from price and size, so only homes missing one of them are unknown. It isn't a top price: the assistant still asks for the budget.
- **Stairs are one limit** (max_floor_without_lift): the most floors the user would climb. A home higher up stays only with a lift; an unstated floor, an unstated lift on a high floor, or a ρετιρέ with no number fail closed. "A ground floor or a lift" is 0, which finally expresses interview chat el_14, so its label changed from a lift wish plus an open question to the limit. The clean test's gb_3 ("μέχρι 2000 ανά τετραγωνικό") now expects the price per m² limit.
- **Checked like every limit:** filtered in code, written a second time in the independent checker, three new search safety cases (23 in all, 0 breaks), unit tests for each edge, eight new interview chats (`evals/datasets/interview_chats_v3.jsonl`), and easing options for each.
- **Prompt v8, still unrun,** carries the rules, so one eval run measures everything.

## D74. Two market lines on every card: price per m² against similar homes, and time on the market

- **Your call (brainstorm, 24 October):** you liked "€1,615/m², 20% under the typical €2,028 in Kypseli" and picked two more facts of that kind for v3: the price per m² against homes like this one, and how long it has been on the market.
- **"Similar" is the most specific group with enough homes behind it.** First the same area, bedroom band (studio or 1, 2, 3 or more) and age band (before 1980, 1980 to 2004, 2005 on), if at least 8 homes share them; else the neighbourhood, if it has at least 10; else the whole area, if it has at least 5; else no line. The line names the group and code keeps how many homes it rests on, so a figure from 8 homes is never dressed up as one from 200. Medians, not means, so one penthouse doesn't move everyone's typical price. Under 5% either way reads "about the typical".
- **Time on the market comes from the date the ad says it went up** ("Δημοσίευση αγγελίας" on the listing page), now its own field, `published`. `first_seen` goes back to meaning the day we first saw the listing. No date, no line: nothing is guessed. A price cut is added to the same line ("On the market for 6 months, price cut from €155,000"), since the two together are what a buyer reads as room to negotiate.
- **These moved out of the "why this one" reasons**, which now say only how the home meets the card. Market facts are a separate list under them, with their own icons.
- **Checked like the reasons:** the explanation eval recomputes every group, median and day count from the listing summaries with its own code. 50 cards, 194 reasons and market lines (94 of them market lines), 100% backed.
- **Area stats for everyone else:** `/api/areas` and the MCP tool `area_stats` give each area's homes for sale, typical €/m², median days on the market and the neighbourhoods with at least 10 homes. The assistant quotes them; it never estimates a typical price itself.
- **Synthetic data:** the public listings gained published dates from a separate random generator, so no other field changed (checked: 60 rows, 0 other changes; search safety still 23 of 23 with 0 breaks).

## D75. The check-in ladder, and New search starts from scratch

- **Your call (brainstorm):** check-ins felt dry and silent. Every 10 likes or rejects now says something, from the first rung that applies:
  1. **A pattern** code found (D66): the assistant words it with the counts, as before.
  2. **A reason you tapped,** even once: "You turned down one home for needing work. Show homes that are ready to move in first?" Your own tap is evidence enough to ask, because nothing changes without your yes. The question is fixed text in Greek or English, in the language of your last chat message, so it costs nothing. "Yes" goes through the chat as your words, so the assistant makes the change like any other (D61); "No, just that one" is a tap and isn't asked again. Reasons with a question: needs work, bad value (a €/m² wish at the search's median), too expensive, too small, the floor (a limit on that floor) and the area (leave it out).
  3. **A pulse:** "How are these homes so far?" Spot on / Mixed / Not for me. Mixed answers with how the homes split, counted by code, and puts the cursor in the chat; Not for me asks what's off. The answers are counted in the swipe stats.
- **Why fixed text for rungs 2 and 3:** a model call would add a wait and a few cents to say a sentence code can write, and code can't put words in your mouth: the only change it offers is the one your tap points to.
- **New search scraps the history (your call):** the swipe log moves to `data/private/swipes/archive/` with a timestamp, so nothing is lost, and the like rate, the check-in count and the learned ranking (D76) start from zero. The old swipes are still there for the learning eval.
- **Tested** with a fake model through the real API: a tapped reason gives the reason question, the next ten give the pulse, "Mixed" returns the counted line, and a new search archives the log.

## D76. The learned ranking: a small logistic regression on your own likes and rejects

- **What it reads:** 22 features per home, in plain words: price against your top price, price per m² against similar homes (D74), size, bedrooms, a second bathroom, low, high and top floors, building age, a renovation in the last 10 years, energy class, balcony, parking, lift, storage, the metro within 10 minutes, ready to move in, 6 months or more on the market, and the interview's own score for the home. An unstated yes/no counts as halfway; an unstated floor, year or energy class has its own "not stated" flag, so nothing is guessed.
- **What it learns from:** likes and rejects in this search. Skips and "Can't judge" teach nothing (D71). A reject with a tapped reason counts double, because you said why (spec section 10). New search starts it from zero (D75); the archived swipes only feed the eval.
- **The blend (spec section 10):** nothing is learned until there are 3 likes and 3 rejects, since one side alone teaches nothing. Then the swipes' share of the order rises with every verdict, to all of it at 30. The hard limits are untouched: the model only reorders homes that already passed.
- **Why the interview's score is one of its features:** the eval found the first version, without it, overruling good interviews. A buyer whose chat already said "at least 70 m²" lost up to 0.24 AUC at 30 swipes, because 30 swipes over 20 features isn't enough to relearn what the chat said. Two fixes were measured: hand over later (at 100), which removed the dip but still threw the chat away in the end; or give the model the chat's score as a feature, so the swipes learn how much your stated wishes count. The second kept the spec's 30 and beat the rules for every buyer it could learn by 160 swipes.
- **Why plain Python, not a library:** about 200 swipes and 22 features is tiny (a fit takes 0.3 seconds), the weights can be read out and explained, and numpy would be a new dependency. The server refits only when the swipes or the card change.
- **What you see:** under the deck, "Order: 40% from your 12 likes and rejects · counting for: a balcony · against: a low floor". A leaning shows only from 10 verdicts and with a clear weight, so a handful of swipes isn't presented as your taste. The MCP tool `next_cards` uses the same blend.
- **The eval (spec section 12):** until there are 200 real swipes, eight simulated buyers stand in, each with a hidden taste written in the eval's own code that the interview only partly caught (one likes space, one value, one high floors, one homes ready to move in, and so on). Each swipes the deck as it is before learning, with noise. The ranking learns from their first swipes and then orders the homes still waiting after 160, which it has never seen: the deck's real job. Five runs each. Target, set before the first run: a mean AUC lift of 0.05 over the rules, with precision at 10 no lower.
- **Results, frozen 20 October snapshot:** AUC 0.634 with the rules, 0.742 learned (+0.108; +0.072 after only 30 swipes); precision at 10 up 0.110; 7 of 8 buyers better. The eighth likes two neighbourhoods, which the model has no feature for: it's there on purpose to show what it can't learn. On the richer 23 October dataset (also frozen, read-only): 0.650 to 0.756, precision at 10 up 0.170.
- **Read these as development scores.** The protocol changed once (the first scored the last 40 swipes, and for buyers the rules already served well those 40 held no likes at all, so there was nothing to measure), and the interview feature and the bathroom feature came after seeing results. The buyers are mine, so this shows the machinery learns, not that it fits real taste. The real test is your swipes: `uv run python -m evals.harness.learning_eval --real me`, once there are about 200.

## D77. The prompt v8 eval: what it found, two relabels, and prompt v9

- **Results:** the 40 chats 99.4% of fields (1 invented hard limit), preferences 16 of 16 with 1 extra, behaviours 100%, $1.98. The 8 new chats for D73: 100%, nothing invented, $0.38. The clean 10 as labelled: 90.2%, 3 invented, $1.21.
- **Two of the clean test's three "inventions" were the stairs limit doing its job.** gb_1 said "αν είναι σε όροφο, να έχει ασανσέρ" (0 floors without a lift) and your mike_5 said "αν είναι πάνω από 1ο όροφο βεβαιώσου ότι έχει ασανσέρ" (1 floor), which is the very limit you asked for. Their labels were written before the field existed, as lift wishes. D73 relabelled el_14 and gb_3 the same way before the run; I missed these two. Relabelled: 95.1%, 1 invented. Relabelling after seeing the output is the weak spot here, so both scores are kept and you can reverse it.
- **The one real slip, twice:** a bare bedroom count became a maximum as well. "Δυάρι" (el_02) and "1 υπνοδωμάτιο" (mike_3) gave max_bedrooms 1, which would hide every larger home. Cause: v8 added max_bedrooms to the prompt's list of hard limits (v7's list had left it out by mistake), and the model started using it.
- **The extra preference:** el_17 said "ανακαινισμένο μετά το 2015, δεν θέλω να κάνω μαστορέματα" and got the year and move_in_ready both. The year already says it, so the second wish double counts renovation.
- **Left as they are:** gb_3 got its homes without the purpose answer. v8 asked twice, the user didn't answer, and since D61 there's no confirmation turn where the simulated user would have said "investment"; the prompt says an unanswered purpose means a home to live in, and the user can say it any time. gb_2 is a rental (never searched): the simulated user repeated "περίπου 500-600" and the card took "around", which the eval's rule counts as an unasked loosening although the word was the user's.
- **Prompt v9** adds two sentences: a bedroom count on its own is a minimum (a maximum only for "up to", "μέχρι", "το πολύ" or "a studio is fine too"), and a renovation year means no move_in_ready on top. It hasn't run: the app stays on v8 until v9 is measured, about $3.60 for the three sets, your go.

## D78. Duplicates: one card per home, merged only on strong evidence

- **The rule from the spec (section 11):** a false merge hides a real option, which is worse than a duplicate, so the finder is built for precision.
- **How a pair is judged** (`dedupe/finder.py`), always within one area:
  - **must agree:** size within 2 m², price within 10%, and bedrooms, floor and type the same wherever both listings state them;
  - **must not disagree:** building or renovation years more than 2 apart, or a different number of bathrooms;
  - **same:** a shared photo hash; or descriptions at least 60% alike (the share of 3-word runs they share); or 30% alike with the same neighbourhood, floor and building year; or a **copy**: the same price to the euro and size to the m² in the same neighbourhood, when no third listing matches that way (a third could mean twin flats in one new build);
  - **borderline:** nothing contradicts and there's some evidence. Kept apart for now; the spec gives these to the model, and the labels will show whether that's needed;
  - **different:** the rest.
- **Why the copy rule:** in the frozen 20 October snapshot, Spitogatos and spiti24 (one group) carry the same ads, and the spiti24 side usually has no description, so wording can't find them. 171 groups of two, 342 of its 484 listings. In your 23 October dataset (Spitogatos only), 35 groups: different agencies listing the same flat, with the same size, price, floor, year and neighbourhood in different words. I read 8 of them and all looked like one home; one had renovation years 2024 and 2017, which became the renovation veto.
- **On the deck:** one card per home: the cheapest version that passes the hard limits, at the best place any version had. The card says "Listed twice, €223,000 to €226,000; this is the cheapest" with links to the other versions, so even a wrong merge leaves the other listing one tap away. A like, reject or skip on any version covers the home. A version over your limits is never the card, though its price shows in the range. The MCP tool `find_duplicates` gives the groups with their evidence.
- **Synthetic check (development):** with photo hashes, 12 of 12 known groups and nothing merged wrongly. Without photos, still nothing wrong, but 4 of 12 missed: those are reworded copies that only a photo gives away. The real listings have no photo hashes yet: making them means fetching each first photo once, which touches the live site, so it waits for your go. Only the hash would be kept (spec section 3).
- **The spec's eval, 60 labelled pairs, needs you and GB:** `data/private/labels/duplicates/duplicate_pairs.html` (with the descriptions, for you) and `duplicate_pairs_links.html` (facts and links only, for GB, like D28). 24 pairs the finder merges, 18 borderline and 18 close ones it keeps apart, shuffled, and the page doesn't say which is which. Then `uv run python -m evals.harness.duplicates_eval --labels mike.jsonl gb.jsonl`. Targets 0.95 precision, 0.85 recall.

## D79. What the user says outright becomes a hard limit, where listings reliably say it

- **What you found testing (24 October):** a crash on a "move in ready" wish, and a user who wants the assistant to hold what they said: "renovated since 2020" or parking should be limits, with the search widened only when fewer than 5 homes are left.
- **The crash was mine:** the card's "why this one" line looked for a field called move_in_ready, which is worked out from the condition instead (714 of your 1,000 homes state one). It has its own wording now, and so does a price per m² wish; the explanation eval adds both and checks them independently (50 cards, 192 reasons and market lines, 100% backed).
- **Option B, your call (brainstorm, 25 October):** a wish said outright becomes a hard limit only for fields the listings reliably state. On the 23 October dataset: floor 99%, bathrooms 98%, lift 97%, year built 94%, storage 93%, parking 91%. Balcony (76%) and a recent renovation (66%) join them because a silent listing is almost always a "no": 758 of the 759 that mention a balcony have one, and 279 of the 345 silent on renovation give no condition, no renovation year and an older build. Move in ready (71%, the silent ones genuinely mixed) and metro minutes (19%) stay wishes. Anything said with "ideally", "if possible" or "αν γίνεται" stays a wish.
- **How it works:** the assistant writes every wish with `firm` (said outright, or softened); code (`core/card_rules.harden`) turns firm wishes on those fields into hard limits: `must_have` (parking, lift, balcony, storage), `min_bathrooms`, `min_year_built`, `min_renovated_year` and a floor band. The model never writes those limits itself, so the rule lives in one tested place, and the reply format stays inside the structured output limits. A firm wish never loosens a stricter limit already on the card.
- **"Ανακαινισμένο" means the last five years now (was ten, D54),** and a home built in that time passes too. A year the user gives wins. A home that says "renovated" with no year can't be promised, so it fails closed and is counted.
- **The guard:** check_supply returns `hidden_unknown` (homes left out only because the listing doesn't say, per field), and the assistant says it when a limit hides 10 or more. For a firm move-in-ready or metro wish it returns `if_made_limit`, and the assistant offers the must once with those counts (tag make_limit); a yes sets `exclude_conditions` or the new `max_metro_walk_min`.
- **Widening:** under 5 homes, the existing step (D50, D63) now also offers a must-have back as a wish, a renovation year five years earlier, one bathroom fewer, a floor lower or higher, five more minutes to the metro. Turning `firm` off counts as loosening a limit, so it needs the user's yes like any other.
- **Checked like every limit:** filtered in code, written again in the independent checker, six new search safety cases (29 in all, 0 breaks), including one where firm wishes go through the MCP server and an "ideally" one doesn't. The bar shows the new limits; the wishes list shows only what's still a wish.
- **Also fixed:** New search's confirmation said the swipes and shortlist stay; since D75 they're archived and start again from zero, and it says so.

## D80. The interview eval moves to the frozen 23 October dataset

- **Why (your call):** the 20 October snapshot hardly states parking (17 of 484), a lift or a balcony (0), so with D79 every chat would look short of homes. The 23 October file (1,000 listings, five areas) is frozen and read-only, so it can be a fixed test set; the build you're about to make on your Mac keeps changing and isn't here.
- **What changed with it:** the eval now covers what the dataset holds (D69), so Pagrati and Kypseli are covered areas. Two chats that tested an uncovered area used them; they now use Nea Smyrni and Koukaki. Two said "any of the three areas" and now say "your areas".
- **A fair baseline first:** v8 as it stood, on the new file, scored against the labels as they were: 40 chats 100% of fields with 0 invented hard limits, but 2 unasked loosenings (el_03); the clean 10 97.5%; the 8 D73 chats 97.5% with 2 asking misses. $3.85. Rescored on the D79 labels, v8 gets 96.9%, 81.2% and 97.5%: the gap is the firm wishes it leaves as wishes, which is what v10 is for.

## D81. Prompt v10: results, one eval fix, and v11 waiting

- **Prompt v10** is v9 (D77's two fixes, never run on its own) plus D79: every wish carries `firm`, "ανακαινισμένο" means the last five years, the must offers for move in ready and metro, and easing a must-have by turning firm off.
- **Results on the frozen 23 October file:** the 40 chats 100% of fields, 0 invented hard limits, behaviours 100% (55 of 55 questions and offers), 0 unasked loosenings; the 8 D73 chats 97.5% (v3_07's bedroom question and v3_05's stairs question, both missed by v8 too); the clean 10 89.6%. The app now runs v10.
- **One eval fix after the first run:** the simulated user answered the must offers itself and said yes four times, from facts that never said so, which set the limits. Like a suggestion to ease a limit (D50), an offer now gets a fixed "no preference", so the card stays as the user said it. The rerun paid only for the turns after the offer ($0.29). The yes path is covered by the unit tests.
- **Two label fixes, made after seeing results, so flagged:** en_10 no longer requires an offer, since nothing passes its search and narrowing an empty search makes no sense; v3_03's budget fact was reworded because the simulated user misread it as having no top price.
- **The clean test's four misses:**
  - gb_3: the purpose question went unanswered, as in D77.
  - mike_3: "idanika" before the bedroom count was caught for size only, as since v7.
  - mike_4, your call: "I like high floors and big balconies" is labelled as two musts (said outright, no "ideally"); v10 read them as wishes, and called the balcony's size uncheckable. Must or wish?
  - mike_5, a regression I caused: my new example for a must with a condition, "a balcony if it's above the 1st floor", pulled "a lift and a balcony if it's above the 1st floor" away from the stairs limit (D77), so the lift became a wish.
- **Prompt v11, written, not run:** the example is now "parking, but only if it's a house", with a line saying a lift wanted above some floor is the stairs limit; and no must offer when fewer than 5 homes pass. About $4.50 to run the three sets; your go.
- **Spent:** v8 baseline $3.85, v10 $4.42 plus $0.29, so $8.56 against the estimate of about $7. About $29.20 in total.

## D82. Prompt v11: a fuller vocabulary, a hidden quote behind every wish, and a blind stress set

- **Your calls (brainstorm, 25 October):** put the work of telling a must from a wish on Sonnet, with a fuller vocabulary like "ideally" (A), and make it show its work for every wish in a hidden field (B); extended thinking (C) only if those still miss. Musts hold until under 5 homes, and then the assistant offers to widen and asks: nothing loosens on its own. And make the eval chats more creative, written blind, to find gaps.
- **A, the vocabulary:** firm is said plainly, including likes and polite wants with nothing softening them ("I like high floors", "μου αρέσει", "θα ήθελα"); soft is anything that makes it optional ("ideally", "I'd prefer", "θα προτιμούσα", "θα ήταν καλό", "δεν είναι απαραίτητο"); "don't mind" and needs that are only implied ("I have two cars") write nothing until asked. A softener covers only what it's attached to. The prompt asks Sonnet to judge the meaning, not match a list.
- **B, the hidden quote:** every wish carries `said`, the user's own words behind it. Sonnet has to find them before it may write the wish. It's never shown: the bar and the deck are unchanged. The eval checks each quote against what the user actually wrote, ignoring accents and case: a wish with no words behind it would be an invented wish.
- **Also in v11:** the D81 stairs fix (a lift wanted above a floor is the stairs limit, not a condition) and no must offer when fewer than 5 homes pass.
- **The stress set** (`evals/datasets/interview_chats_stress.jsonl`): 30 chats written by a separate agent that never saw the prompt or the other chats, aimed at softeners, likes, negations, conditions, implied needs, changes of mind, Greeklish and slang, vague words and numbers in words. I checked its labels against the rules and changed one (a rental's monthly rent may sit in the price field, as elsewhere). It's held out: it ran once, and nothing is tuned on it. You spot-check 10 labels.
- **Results, frozen 23 October file:** the 40 chats 100% of fields, 0 invented, behaviours 99.2%; the clean 10 95.8% (from 89.6%: the stairs fix worked), 0 invented; the 8 D73 chats 97.5%; the stress set 95.7%, 1 invented hard limit, behaviours 94.6%. Every wish's quote was found in the user's words: 75 of 75.
- **What the stress set found:** firm against soft held up; the one invented limit is "κάπως ψηλό όροφο" ("a high-ish floor"), which v11 made a must and the label calls soft. The bigger pattern is the bedroom question: five chats ended without a bedroom count, because the question lost out to a widening, a purpose or a costs question, or the simulated user didn't answer it (v3_07 has shown this since v8). It's dialogue order, not translation, so C (extended thinking) isn't the fix: a rule that the bedroom question comes before optional ones is, in the next prompt, tuned on the dev chats.
- **Simulated-user noise, not prompt faults:** in mike_4 v11 made both musts, said so, and the simulated user objected "I never said they're must-haves", so it made them wishes (it followed the user, rightly); st_20 raised the price after the user's own scripted turn asked for it.
- **The app runs v11.** Spent $7.30 on these runs (estimate about $6.50); about $36.50 in total.

## D83. Duplicates: the first real labels, and what they say

- **Your labels:** all 60 pairs: 45 the same home, 8 different, 7 can't tell (each one because a listing is gone). I found your export in Downloads; there was no second labeller's file, so there's no agreement figure.
- **Result:** precision 1.0 (all 22 merges right), recall 0.49 (22 of 45 real duplicates found). Precision passes the 0.95 target; recall fails the 0.85.
- **Why it misses:** both of the finder's safety guards cost real duplicates. A copy needed no third listing with the same price and size, but the third was the same home too (one flat listed three or four times across agencies and both portals). And it needed the same neighbourhood name, which spiti24 and Spitogatos write differently. 14 of the 15 borderline pairs were the same home.
- **What would fix it, measured on the same labels:** an exact price and size in the same area as enough on its own: 41 of 41 merges right, recall 0.91. That's fitted to these 53 pairs, so it's a development score; a fresh batch of about 30 labelled pairs would be the clean check. Merging every borderline pair instead gives 36 of 37 (0.97) and recall 0.80.
- **Not changed yet:** your call.

## D84. Duplicates: an exact copy is enough, and groups never chain

- **Your call (25 October):** use the exact price and size rule; no more labelling.
- **The rule:** two listings in the same area with the same price to the euro and the same size to the m², and nothing contradicting (bedrooms, floor, type, years, bathrooms), are the same home. The neighbourhood name no longer has to match, and a third or fourth match no longer blocks the merge.
- **One thing the change exposed, fixed before shipping:** grouping by chains (a like b, b like c, so all three together) let an exact copy pull a different flat of the same new build into a group: 82 and 80 m² at €260,000, with the same developer's wording, which you labelled different. A group now only grows when the newcomer is "same" with every listing already in it, strongest evidence first (a shared photo, then an exact copy, then wording). It also split a 600 m² building listed nine times with 8, 10 and 12 bedrooms into its consistent parts.
- **Result on your labels:** precision 1.0 (40 of 40 merges right), recall 0.89 (40 of 45): both targets met. That's a development score, since the rule came from the same labels, and it's the number to quote with that caveat.
- **On the data:** the frozen 20 October snapshot folds 216 of its 484 listings into 199 homes (mostly spiti24 copies of Spitogatos ads); your 23 October dataset (Spitogatos only) folds 53 of 1,000. The synthetic check is unchanged: 12 of 12 with photo hashes, nothing merged wrongly without.

## D85. Your stress-set spot-check

- **Eight of ten labels stood.** Three comments:
  - **st_13, "no renovation projects, full stop":** only renovated homes and new builds, plus a move-in-ready wish on top. The limit already leaves only those two in the 23 October data ("good condition" never occurs), so the label gains the wish. v11 doesn't add it, so the rescore now counts one missed wish; the next prompt adds that rule.
  - **st_15, parking a must only if it's a house:** this wants an "if" rule, which doesn't exist yet, so the label stays a strong wish plus a note, which is what v11 did. Your idea, a separate search for houses with parking as a must, is open.
  - **st_23, "tria dwmatia":** 3 bedrooms, as labelled; τριάρι would be 2.
- **Rescored for free:** fields 95.7% and the 41 of 41 quotes are unchanged; wishes 25 of 28.

## D86. Prompt v12: your stress-set feedback

- **Parking a must only for houses (st_15):** a new kind of limit, `must_have_if_type`, for example {"detached_house": ["parking"]}. Sonnet marks the wish with `only_for_types`; code makes it a must for those types only, so apartments in the same search aren't touched and a house that doesn't say whether it has parking is left out. It works for parking, lift, balcony and storage; anything else tied to a type stays a wish. Filtered in code, written again in the independent checker, a new search safety case (30 in all, 0 breaks), a widening option to drop it, and "parking for a house" on the bar. One build snag: as a list of types the reply grammar became too large for structured output, so Sonnet writes the types as one comma-separated string and code reads it.
- **"No renovation projects, full stop" (st_13):** the condition limit plus a move-in-ready wish. v3_02 says the same thing, so its label gained the wish too.
- **The bedroom question comes first:** before searching, the user has answered about bedrooms if they gave neither a size nor a count ("no preference" counts); it comes before optional questions and before a widening, since the answer changes the count; and it's asked once more if the next message skips it.
- **Results, frozen 23 October file:** the 40 chats 100% of fields, 0 invented, behaviours 99.2%; the clean 10 97.9% (from 95.8%); the 8 D73 chats 100% of fields and behaviours (v3_07's bedroom question, missed since v8, is now asked); the stress set 95.7% of fields, behaviours 97.3% (from 94.6%), 1 invented ("κάπως ψηλό όροφο" again). Every wish's quote found in the user's words: 77 of 77.
- **A new miss to fix next:** "a high floor" came out as floor 3 in mike_4 and st_06. Your rule (D58) is 4, and it isn't written in the prompt.
- **The stress set is no longer fully held out:** st_13 and st_15 shaped v12. The other 28 still are.
- **The app runs v12.** Spent $9.05 on this round (estimate $7.30; replies got longer, about 9 cents a chat in the dev set, from 6), about $45.50 in total.


## D87. The palette: graphite with a lime signal

- **Context:** the first design system (25 October) used a honey accent on warm stone. You rejected it on sight ("very much like pornhub") and asked for several directions, including neon green, to choose from.
- **How we chose:** three rounds on a Design canvas, each option shown as the same screen (wordmark, limits bar, a home card with its market line, Reject and Like, the assistant's bubble, the learning line) in light and dark, so only the colour varied. Round one: neon lime, olive, Aegean blue, plum, graphite with a green signal, teal. You kept Aegean blue and graphite. Round two grew from those: graphite with a blue signal, graphite with a lime signal, blue on stone, and blue limits with green verdicts. You chose graphite with a lime signal. Round three varied one thing at a time: a yellower or greener lime, lime reaching the limits bar and the mark, one hue with Reject in ink, a charcoal dark mode. You chose the reach variant (H-c).
- **The palette:** neutrals are graphite, a hair warm: surface #f4f4f2 / #151515, raised #ffffff / #1e1e1d, ink #1b1b19 / #ebebe7, muted #5b5b57 / #a4a4a0. The signal is lime #c8f542, the same hex in both themes, as a fill only: Like and Send, and the lifted tile of the mark on a dark ground. At text size the signal is lime-deep, #3f6d00 on light and #d4ff5c on dark: the limit chips on the bar (on lime-soft, #ecf8c4 / #27301a), the active tab's border, the market-line marks, the learning line's leanings, links, the focus ring, and the lifted tile on a light ground. Reject stays brick (#b0432f / #e58a78), so it differs from Like in lightness as well as hue, and it is always also the word.
- **Why this and not the others, in plain words:** the brief says the content is the design. Graphite chrome has no colour of its own, so the price, the m² and the words are what the eye lands on, and lime appears only where Tispi commits (the limits) or you decide (Like). Neon on a dark ground is the current AI-startup default and fails as text on light; using it only as a fill behind dark text, with a deep green for text, keeps the neon you wanted without either problem, and makes light and dark the same product rather than two. Blue was the safe trust colour and the one every bank and portal uses.
- **Changes that followed:** the assistant's bubbles are now neutral (raised with a hairline), so the signal is not spent on talk; the limits bar is a neutral strip with each limit a lime chip; the mark is two-tone (four ink tiles and the lifted tile in the signal), in three files for light, dark and print; `chip` is a new type style (13px, 600) for limits and reason chips. Every text colour was checked at 4.5:1 or better on its ground in both themes; the figures are in each token's note.
- **Where it lives:** the Tispi design system artifact (version 2), `docs/brand-brief.md`, and this entry. The React app still runs the old teal until the UI build.
- **Say:** "The chrome is graphite so the numbers are the colour; lime marks only a limit or a verdict; and neon lives as a fill, never as text, so it reads the same in light and dark."

## D88. The deck's two icons, from Mike's sketch

- **Context:** the deck had two text glyphs for the actions that are not words, ↶ for back and ↷ for skip. Mike sketched what he wanted instead (25 October).
- **The icons:** *previous* is a circular arrow that turns back on itself, open at the left with the arrowhead at the top of the gap; *skip* is a filled play triangle against a bar, "to the end of this one". Both drawn at 20px on a 24px box with 2px round strokes, one ink via `currentColor`, so they take the button's colour in both themes. They are the whole icon set; Reject and Like stay words.
- **Geometry:** my first hand-drawn arc read wrong at 20px (Mike: "looks weird"), so the shapes are Lucide's `rotate-ccw` and `skip-forward` (ISC licence, which allows this with the licence kept), with the triangle filled to match the sketch. A proven icon beats a bespoke one that nobody can read.
- **Where they sit:** on the outside, previous left of Reject and skip right of Like (Mike's call, 25 October, over the system's first draft which had them in the middle). The two verdicts sit together, and the two rarer actions are at the edges where a thumb has to mean it. On a phone the two word buttons share the width between the icons, which keep 44px.
- **Where it lives:** `assets/Icons` in the design system (version 4), the Button and SwipeActions guidelines, and the screens canvas. The React app follows in the UI build.
- **The screens canvas** now shows every screen in Greek and English side by side (a Greek desktop, English phone screens), so the two languages can be judged against each other: same layout, different lengths. Greek runs about 15% longer, which the chips and buttons must absorb.
- **Say:** "Two icons in the whole product, both drawn from the owner's sketch; everything else is a word."

## D89. The limits bar on a phone: one row, the rest folds

- **Context (Mike, 25 October):** on the phone screens the limits wrapped to a second row, and the chat button at the bottom was pushed off the screen.
- **The rule:** on a phone the bar is one row and never wraps. The "Limits" label is dropped, the chips use a compact form ("€90–220k", "90–220 χιλ. €"), and every chip that would not fit the row goes behind the fold-out button together with the wishes, which is labelled with the count of what it holds ("+3 ▾"). The fold-out lists every limit in full. On desktop the bar is unchanged.
- **Why this way:** the promise (D61) is that every hard limit is always on screen or one tap away, never silently gone. Hiding by width, with the count on the button, keeps that honest: nothing is dropped by rule, and the number tells the user how much is folded. A horizontal scroll was the alternative; it hides the overflow without saying so, and on a phone a scrolled bar reads as decoration.
- **In the build:** code measures the chips against the row width and moves whole chips behind the button; the count is hidden chips plus wishes. The design system's limits-bar guideline (version 5) carries the rule.
- **Say:** "One row on the phone. What doesn't fit is one tap away, and the button says how much."

## D90. The phone shell: a searches drawer, a title that is the search, and three floating views

- **Context (Mike, 25 October):** on the phone, lay the app out like a chat app's conversation screen: a drawer icon on the left of the header, the search's areas and price right-aligned as the title, a left drawer with past searches, and three floating view buttons at the bottom.
- **The header:** one icon button on the left opens the drawer; on the right, right-aligned, the areas on one line and the price range under it, in place of the logo. The two biggest limits are therefore always in view as the title, and the limits bar below carries only the rest (bedrooms, musts, the fold-out with the wishes), which fits one row (D89). The logo moves to the top of the drawer.
- **The drawer:** slides in from the left to 90% of the width over a dimmed screen. Top: the lockup. Then "Searches", each past search as a row: its areas and price as the title, under it the date, the homes count, the verdicts and the shortlist count; the current one on `lime-soft`. Bottom: "New search" (primary) above "Options" (quiet). A search's title is its limits, never a name the user has to invent.
- **Three floating views:** a pill bar floating at the bottom with Chat, Homes and Shortlist (with its count). Chat shows the thread with the composer above the bar; Homes is the deck, and the app also lands there by itself once the limits are validated and the first homes are in; Shortlist lists the kept homes with price, facts, the reason kept, the portal link and Remove. The active view sits on `lime-soft` in `lime-deep`. The bar replaces the old "Change anything by chat" button; the counts ("13 left · 8 swiped") move under the swipe actions.
- **Desktop followed the next day's hour (D91):** the same logic, with the drawer as a sidebar.
- **Open:** the drawer icon. Mike's attachment did not arrive, so the mockups use a plain panel icon (Lucide `panel-left`) as a placeholder until his arrives.
- **Say:** "On the phone the search is the title, the past searches are a drawer, and the three things you can look at are one tap away at the bottom."

## D91. The desktop takes the same shell

- **Context (Mike, 25 October):** "transfer the mobile UI to the desktop with the same Claude UI logic".
- **The layout at 1440:** a 272px sidebar on the left with the lockup and a collapse button at the top, the searches list (the current one on `lime-soft`), and "New search" above "Options" at the bottom; then the main area, with a header whose title is the search (areas on one line, the price range under it) and the status on the right, and under it the two panes as before: the chat on the left, Homes and Shortlist as tabs on the right above the limits bar and the deck. Chat is not a view on desktop because it is always visible; the three phone views become "the chat pane" plus the two tabs.
- **One rule across devices:** the title holds the areas and the price; the bar holds every other limit and the wishes fold-out; past searches are titled by their limits. The desktop bar keeps its "Limits" label and wraps if it must, since it has the room; only the phone's is one row (D89).
- **Why a sidebar and not a drawer on desktop:** the width is there, and a list that is always visible is how people keep several searches going (a buyer compares two or three areas over weeks). The collapse button exists for a narrow window; collapsed, it behaves like the phone's drawer.
- **Say:** "Same shell on both: the search is the title, the searches are on the left, the promise is above the homes."
