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
