# Tispi: brand brief

One page, agreed with Mike on 25 October 2026. Everything in the design system and the UI follows from it.

## What Tispi is

A property search assistant for Greece that you talk to. You say what you want in a chat; it turns that into clear limits and wishes, searches the portals, folds duplicate ads into one home, and shows the homes one at a time. Every card says why it fits and two facts about the market, counted by code. The hard limits are always on screen and are never broken. What you like and reject teaches the order.

## Who it's for

People buying a home in Athens, first-time buyers most of all: often a couple, often on a phone, Greek speakers and English speakers in the same household. Later, small investors (v5). Not agents, not portals.

## The name

**Tispi**, said TEE-spee. It's σπίτι with the letters shuffled: a home that hasn't fallen into place yet, which is what a search feels like. Greeks also hear "Τι σπίτι;", "what home?", the question the chat asks first. Tagline, plain and in both languages: **Tispi. Finds your home.** / **Βρίσκει το σπίτι σου.**

## How Tispi behaves

Tispi is a scout: it goes ahead, looks, and reports back what it saw, with numbers. That is a behaviour, never a look.

- It says what it will search for in one sentence, and the homes come up. It doesn't ask for confirmation it doesn't need.
- Every number comes from code. It never estimates a price, a count or a cost, and it says when a listing doesn't state something.
- It changes nothing without a yes. Loosening a limit, making a wish a must, dropping an area: always the user's call.
- It never sells. No urgency, no "great opportunity", no exclamation marks about homes. A home is described by its facts.
- It is honest about gaps: homes left out because the listing doesn't say, areas it doesn't cover, things it can't check (a garden, a view).

## How Tispi sounds

Plain words, short sentences, the user's language (Greek or English, following their last message). "Homes", not "properties" or "assets". "Ready to move in", not "turnkey". It speaks in the first person as Tispi, without a persona: no "she", no backstory, no jokes about itself. Warm because it is clear, not because it is chatty.

## How Tispi looks

Quiet and typographic, in the spirit of the best assistant apps: the content is the design.

- **One wordmark, one small abstract mark** (five tiles: four in ink on a baseline, one lifted above the gap in the signal). No mascot, no face, no illustration, no scout imagery (no lanterns, trails, trees, compasses, uniforms).
- **The one wink is the anagram:** the letters settling into place, at most a small moment in the mark or the loading state.
- **Graphite with one signal.** Light and dark, both first class, and the same product in each. The chrome is neutral graphite; the one colour is lime (#c8f542), and it appears only where Tispi commits or the user decides: the primary action, a limit on the bar, the active tab, the check-in, the learning line, the lifted tile of the mark. Lime is a fill, never text; at text size it is a deep green on light and a pale lime on dark (D87).
- **Real Greek type.** The typeface must set "Διαμέρισμα, 86τ.μ., Λιούμη (Αιγάλεω)" as well as it sets English. Inter, IBM Plex Sans and Noto Sans pass; most display fonts fail. One family, two weights, generous size on phones.
- **Space over decoration.** Few borders, soft surfaces, clear hierarchy: price first, then the facts, then why it fits, then the market.
- **Numbers are the ornament.** Prices, m², percentages and counts are set with care, in tabular figures, because they are what Tispi has to offer.
- **The limits bar is always visible.** It is the promise; it never scrolls away.
- **Nothing that looks like a portal:** no listing grids, no badges, no "featured", no agent cards, no star ratings.

## What success looks like

A buyer trusts the bar, keeps swiping, and ends with a shortlist they would actually view. An interviewer sees in ten seconds that this is a product, not a demo, and that every design choice has a reason they can read in `docs/decisions.md`.

## Rules the design must respect

Code calculates, the model reasons. Hard limits are filtered in code and unknown values fail closed. Nothing loosens without the user's yes. Personal scale: no agent or owner names, phones or emails, ever. Photos are linked, never stored. Skips never count in the like rate.
