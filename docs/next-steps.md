# Next steps

Updated 24 October 2026, after the v3 build (D72 to D78).

## Where we are

- **v3 built:** waiting check-ins survive a reload (D72); condition, a price per m² limit and a stairs limit (D73); market lines and area stats (D74); the check-in ladder and a fresh start on New search (D75); the learned ranking (D76); one card per home for duplicates (D78). Prompt v8's eval is in (D77) and prompt v9 is written but not run.
- **Data:** your product dataset is the 1,000 listings of 23 October (five areas, 200 each), private and on your Mac. The evals stay on the frozen 20 October snapshot (484 listings), plus the 23 October file as a second frozen set for the learning eval.
- **Tests:** the whole suite passes; the app builds and works at phone width.
- **Spent:** about $20.60 of the $100 in total ($3.56 on the v8 run).

## Next steps

1. **Prompt v9 eval run** (about $3.60, your go). Two sentences fix v8's one slip, a bare bedroom count that also became a maximum (D77). The app stays on v8 until v9 is measured.
2. **On your Mac:** pull, rebuild the app, and rebuild the dataset page-only, so each listing gets its published date and the cards show time on the market (the 84 early Egaleo pages read from cards are refetched first, if not done yet). Then run the server on it. The prompt for Claude Code on your Mac is in the chat.
3. **Check the two relabels** in the clean test (gb_1 and your mike_5, D77): both said "a lift if it's above the ground or 1st floor", which is the stairs limit. Say if you'd rather keep them as lift wishes.
4. **Swipe:** about 100 swipes gives the baseline like rate (v2's finishing line); at about 200, `uv run python -m evals.harness.learning_eval --real me` measures the learned ranking on your own taste, the spec's real test.
5. **Label 60 duplicate pairs, you and GB** (D78): `uv run python -m evals.harness.build_duplicate_labels`, then `--links-only` for GB. Targets 0.95 precision, 0.85 recall.
6. **Photo hashes for duplicates** (your call, a live-site step): reworded copies need them.

## Interview eval (22 October, D46, D47)

- 40 chats: scripted user turns, a simulated user (Haiku) for gaps, scored in code. Sonnet 5.5 with one tool, check_supply, so trade-offs use code's numbers.
- Prompt v1: fields 88.8%, 0 invented hard limits; stated bedroom counts became preferences. Prompt v2: fields 98.8%, 1 invented hard limit, behaviours 98.8%, 2.3 cents a chat.
- Prompt v3 with the narrowing question: fields 97.5%, 2 invented hard limits, both from the simulated user (D49).
- Prompt v4, suggest easing one limit and ask (D50): fields 100%, 0 invented hard limits, 0 unasked loosenings, behaviours 100%.
- Clean test, 10 new chats (D52): 43.5% as labelled; see the decision list.
- Prompt v5 (D55): 40 chats 100% fields and behaviours; clean 10: 82.9% fields, 0 invented hard limits.
- Prompt v6 (D57): 40 chats 100%; clean 10 at 92.1% fields, behaviours 100%.
- Prompt v7 (D63, D65): 40 chats 100%, 13 of 13 narrowing questions when wide; clean 10 at 97.3% fields, behaviours 100%.
- Spent about $15.40 of the $100 in total.
- Prompt v8 (D77, 24 October): 40 chats 99.4%, 1 invented (a bare bedroom count became a maximum); 8 new chats 100%; clean 10 90.2% as labelled, 95.1% with two lift wishes relabelled to the stairs limit. $3.56.

## Pagrati clean test, scored (22 October, D45)

- As labelled: Haiku v3 + code 100% table fields, 88.2% text fields; code alone 91.2%. All four of Haiku's disagreements were facts the labels left blank.
- You confirmed the four, so Pagrati key v2: Haiku v3 + code 100% on both; code alone 91.2%. Headline stays 88.2%.

## Pagrati clean test (22 October, D44)

- 10 listings, chosen at random from the first results page, saved with their crossed-out lists. Pagrati is now an area.
- Two blind labelling pages of 5 (round 6), pre-filled only with what code reads from the table, ticks and crosses.

## Answer key v4 (22 October, D43)

- GB took the proposed value on 20 of 21 disputed values. Haiku v3 + code: 99.3% table fields, 94.8% text fields; code alone 99.1% and 93.1%; Sonnet ties at eleven times the cost.
- Spent about $1.17 of the $100.

## Prompt v3 (22 October, D40)

- Kilometres field, all 66 Athens metro stations in the glossary, rules for vehicles and several distances; minutes count only on foot, enforced in code (D41). Text fields 92.1%, metro 88%. $1.09 spent in total.

## Answer key v3 and the model comparison (22 October, D39)

- 24 crossed-out blanks filled by rule, each marked. Haiku + code: 98.9% table fields, 91.7% text fields. Sonnet ties at eleven times the cost, so Haiku stays.
- Spent $1.01 of the $100.

## Crossed-out lists for all 100 (22 October, D38)

- Haiku v2 + code: 98.9% on table fields, 87.1% on text-only fields (targets 98% and 85%). Code alone 85.7%.
- Check 5: every difference was a crossed-out lift, parking or storage; the system now agrees with Checks 4 and 5 on 418 of 420 fields.

## Check 4 (22 October, D37)

- You agreed with the system on 103 of 105 fields, GB on 102. All balconies and 4 of 5 parking answers right; the misses were crossed-out lift, parking and storage on a listing not revisited.

## Answer key v2 (22 October, D35)

- Every round combined: a value one labeller found beats a blank another left; a clash goes to the newer label. 70 of 100 listings have two or three labels.
- Haiku v2 + code with crossed-out lists: 89.9% on text fields on the revisited 50 (target 85%), 82.1% on all 100, with metro within a minute (D36).
- Round 2 agreement: 89.3% and 90.0%, parking 34 of 87 disagreements; round 3: 95.7% and 92.4%.

## The crossed-out revisit (22 October, D34)

- 50 pages, feature lists only. Code reads a crossed-out lift, storage or parking as "no".
- On those 50: misses fall from 48 to 8 (code) and from 44 to 5 (Haiku). Text fields: code 78.6%, Haiku 75.6%.
- The lists give 26 "no"s the key left blank; round 3 checks them.

## First model run (22 October, D33)

- Haiku 5.5 reads the description only; code reads the table and merges. Prompt v2 on key v1: table fields 98.2%, text fields 72.2% (code alone 73.1%).
- Of 171 disagreements with the key, about 20 look like real model mistakes; the rest are crossed-out "no"s (73), values the key left blank (57), the key predating your notes (14) and raised ground (7).
- Spent $0.155 of the $100.

## v1 features, after the evals

The extraction prompt (Haiku 5.5) with the glossary, `extract_listing` on the server, the conflict rule from D25 in code, the interview prompt (Sonnet 5.5), the criteria card, the table view (React, D20).

## Possible expansions

In `docs/expansions.md`: xe.gr, more areas, rentals, investor versus live-in buyer, and listing fields such as rented, lift reaches the floor and delivery date (D51).

## Open items

1. **Anthropic API key.** Working, stored outside the repo, $100 credit with a $100 monthly limit. Delete it and make a new one when the project's done, since it was pasted in chat.
2. **Tab suspender.** You can turn it back on. If I collect more pages later, please whitelist spitogatos.gr instead.

Decided this session: spiti24 added (D18), agency names kept (D19), React for the front end (D20), plus D21 to D62.

## For the desktop app demo

Follow `docs/connect-claude-desktop.md` once the repo is on your machine.
