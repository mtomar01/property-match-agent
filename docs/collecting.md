# Collecting a dataset from Spitogatos

How a new, refreshed or expanded product dataset is built (D68). It runs on Mike's Mac, in his own Chrome, through Claude Code with the Claude in Chrome extension (`claude --chrome`). Everything collected stays in `data/private/`, which git ignores. The evals stay on the frozen 20 October snapshot; the learning eval also runs on a frozen, read-only copy of the 23 October dataset (D76), because the older snapshot lacks most of the fields the learned ranking reads.

## Rules

- **Personal use, polite pace.** One tab, one request at a time, 4 to 7 seconds apart (random), never in parallel. No logging in.
- **Read robots.txt and the terms first** (`https://www.spitogatos.gr/robots.txt`). Spitogatos allowed this on 20 October (D13): it disallows map search, annual reports, the account area and named bad bots, none of them Claude. If that has changed, or the result or listing pages are disallowed, stop and ask Mike.
- **Stop and ask** on a 403 or 429, a captcha, an "access denied" page, or three failed pages in a row. Don't retry harder.
- **No contact details, ever.** Phone numbers and emails are replaced with `[removed]` in the browser before anything is saved, then scrubbed again in Python, and the Listing model refuses anything left (D5). Agent and owner names aren't collected.
- **Don't pass page text through the chat.** A thousand pages are far too much text for a conversation. A script in the tab collects them and saves files; the chat only sees counts and problems.
- **Spitogatos only.** spiti24 waits until its listing pages have a reader and an eval (D68).

## Scope (23 October run)

Homes for sale in Egaleo, Peristeri, Chaidari, Pagrati and Kypseli, up to 200 listings per area: about 7 result pages of 30 cards each, plus each listing's page. Area slugs for file names: `aigaleo`, `peristeri`, `chaidari`, `pagkrati`, `kypseli`.

Find each area's results URL through the site's own search (homes for sale, the area), note the URL and how it pages, and write both in the run log.

## Step 1: result pages, for the links

The result pages are only how the listings are found (D70). The area of every listing is the area searched: on 20 October that matched the card's own area for 270 of 270 listings. The script still saves each card as below, because it costs no extra request and the build uses the cards as a check, never as data.

One record per card, one JSON object per line, in `cards_<slug>_<YYYY-MM-DD>.jsonl`:

```json
{"source": "spitogatos", "source_id": "1000000001", "url": "https://www.spitogatos.gr/aggelia/1000000001",
 "area_query": "aigaleo", "card_text": "12\nItem 1 of 12\nΔιαμέρισμα, 86τ.μ.\nΔιαμέρισμα, 86τ.μ.\nΛιούμη (Αιγάλεω)\n\n...\n€185.000",
 "photo_url": null, "seen": "2026-10-23"}
```

- `card_text` is the card's `innerText`, unchanged except for the scrub. The parser (`adapters/spitogatos_cards.py`) expects the layout above: an optional photo count, the title ("Διαμέρισμα, 86τ.μ."), the sub-area line ("Λιούμη (Αιγάλεω)" or "Κυψέλη (Αθήνα - Κέντρο)"), the generated sentence, the badges and the price, with an old price after it when there was a drop. See `tests/test_spitogatos_cards.py` for a full made-up example.
- `photo_url` is the card image's `https://` address if the image has loaded, else null. Never the image itself.
- Skip promoted mini cards that show only a price and a size. A listing seen twice keeps its first card.

## Step 2: listing pages, for every value

One record per listing, in `pages_<slug>_<YYYY-MM-DD>.jsonl`. Everything in the dataset comes from here: type and size from the title, bedrooms and bathrooms from the room badges, the neighbourhood from the line under the title, the rest from the table, the features and the description.

```json
{"source_id": "1000000001", "url": "https://www.spitogatos.gr/aggelia/1000000001", "seen": "2026-10-23",
 "area_query": "aigaleo", "title": "Διαμέρισμα, 86τ.μ.", "location": "Λιούμη (Αιγάλεω)", "rooms": "2 υ/δ\n1 μπ",
 "photo_url": "https://...jpg",
 "sections": {"Περιγραφή": "full description", "Χαρακτηριστικά": "Τιμή\n€185.000\nΕμβαδόν\n86τ.μ.\nΌροφος\n2ος\n...\nΈτος κατασκευής\n1978",
              "Εσωτερικό": "Ασανσέρ\nΑποθήκη", "Εξωτερικά χαρακτηριστικά": "Βεράντα\nΓωνιακό", "Κατασκευή": "Ανακαινισμένο", "Κατάλληλο για": "Επενδυτικό"},
 "crossed": {"Εσωτερικό": ["Τζάκι"], "Εξωτερικά χαρακτηριστικά": ["Parking", "Κήπος"]}}
```

- **Selectors that worked on 22 October** (check they still do on the first page): the title `h1.property__title`; each section starts at an `h3.property__subheading` whose text is one of the six names above; the four feature lists are `ul.property__features`, and each `li` carries an icon whose `use` `href` ends in `#i-correct` (ticked) or `#i-negative` (crossed out). `adapters/spitogatos_features.page_script()` is the script used then for the feature lists.
- `sections`: the text under each of the six headings as `innerText` lines. In the four feature lists keep only the ticked items; the crossed-out ones go in `crossed`, each name without a trailing bracket. "Χαρακτηριστικά" is the details table as alternating name and value lines. "Περιγραφή" is the whole description: expand a "read more" first if the text is cut.
- `photo_url`: the first gallery photo's `https://` address, or null.
- `title`, `location`, `rooms`: the text of `h1.property__title`, of `.property__address`, and of the bedroom and bathroom badges in `ul.property__info` (one per line, bedroom first). `area_query` is the slug that was searched. `adapters/spitogatos_collect.js` saves all four.
- **Fetch or open:** first try `fetch()` of a listing URL from a Spitogatos tab and parse it with `DOMParser`. If the six sections are in the fetched HTML, use that for every page (same load as a visit, without images). If they only appear after the page's JavaScript runs, open each page in the tab instead. Either way, one at a time, 4 to 7 seconds apart.

## Moving the files

The script keeps its results in the tab and saves them with a Blob download, one file per area and kind (`cards_...` and `pages_...`), into `~/Downloads`. Chrome asks once whether spitogatos.gr may download several files: allow it. Then move them into `data/private/collect/`.

## Checkpoint before the full run

After the first results page and the first 5 listing pages of the first area, build from just those files and look at the summary:

```bash
uv run python -m adapters.page_snapshot --pages 'data/private/collect/pages_aigaleo_*.jsonl' \
  --check-cards 'data/private/collect/cards_aigaleo_*.jsonl' --out /tmp/pm_check.jsonl
```

Go on only if `refused` is empty, year built, floor, energy class and bedrooms are known on most of the 5, and `check_against_cards` shows the page and the card agreeing on area, type, size, bedrooms and price.

## Step 3: build the dataset

```bash
uv run python -m adapters.page_snapshot --pages 'data/private/collect/pages_*.jsonl' \
  --check-cards 'data/private/collect/cards_*.jsonl' --out data/private/snapshot_<YYYY-MM-DD>.jsonl
```

Code reads each page's table and features, Haiku 5.5 reads each description (prompt extraction_v3, about a tenth of a cent each, cached), and the two are merged with the rule the extraction eval measured. It needs the Anthropic key in `~/.config/property-match/anthropic.env`. A listing whose page failed isn't in the dataset; it shows in `refused` or in the run's failures.

A page saved twice (a refetch with `PM.only()`) keeps one record: the copy with its title and badges, then the newest (D70).

## Rentals (D102)

The same method, the same five areas, the rental results instead of the sale results. The script reads the kind from the path: `/enoikiaseis-katoikies/<area>` is a rental run, and every card and page it saves carries `listing_type: "rent"`, which the build keeps. The files are named `cards_rent_<slug>_<date>.jsonl` and `pages_rent_<slug>_<date>.jsonl`, so they never collide with the sale files of the same day. A rental's price line ends "/ μήνα"; the card test and the page reader accept it, and the price is the month's rent (`price_per_m2` is then €/m² a month). The hard-limit filter already matches the listing type to the intent, so a sale search never sees a rental and the other way round.

**The pilot first:** two rentals from each area, ten in all, read by hand before the full run.

```js
PM.area({slug: 'aigaleo', path: '/enoikiaseis-katoikies/aigaleo', seen: '<YYYY-MM-DD>'})
PM.run({resultPages: 1, listings: 2, pages: 2})
await PM.wait(45)
PM.save()
```

Then the other four areas the same way (the site spells Kypseli `kipseli`; check each rental results URL through the site's own search first, as for sales, and note it in the run log). Build the ten into their own file, never into the sale snapshot:

```bash
uv run python -m adapters.page_snapshot --pages 'data/private/collect/pages_rent_*.jsonl' \
  --check-cards 'data/private/collect/cards_rent_*.jsonl' --out data/private/snapshot_rent_pilot_<YYYY-MM-DD>.jsonl
```

Check on each of the ten: the price is the month's rent and `monthly` is in the extras, the size, floor, bedrooms and area read right, and the page agrees with its card. Also note what a rental page says that a sale page does not (furnished, available from, deposit, pets, bills included, minimum term) and in which section, so the fields can be decided before the 1,000. Go on to the full run (7 result pages, 200 listings per area, as for sales) only on Mike's go after the ten are read.

## Step 4: run the app on it

```bash
PM_SNAPSHOT=data/private/snapshot_<YYYY-MM-DD>.jsonl uv run python -m api.server
```

The app covers every area the dataset has at least 10 homes for sale in (D69), so the header shows all five.

## Run log

Write `data/private/collect/run_<YYYY-MM-DD>.md`: when robots.txt and the terms were read and what they said, the results URLs, start and end times, pages collected per area, anything skipped and why, and the build summary. Commit the collection script itself (it holds no data) so the next refresh reuses it; never commit anything under `data/private/`.
