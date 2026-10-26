# Eval datasets

Everything in this folder is public, so it holds invented data only. Labels for real listings live in `data/private/labels/`, which git ignores.

| File | What it is | Used by |
|---|---|---|
| `search_safety.jsonl` | 20 criteria sets with their expected matches on the synthetic snapshot | Search safety eval (v0.1, live) |
| `interview_chats.jsonl` | 40 scripted interview chats, 20 Greek and 20 English | Interview eval (v1) |
| `interview_chats_v4.jsonl` | 4 chats on the order of the homes (D98): two strict orders asked for, one wish that is not an order, one order set and then dropped | Interview eval, `--chats` |
| `templates/` | Empty templates for extraction labels, chats and duplicate pairs | Labelling |

Extraction labels for the 100 real listings are made with the offline labelling tool (`evals/harness/build_label_tool.py`, rules in `docs/labelling-guide.md`) and stay in `data/private/labels/`. `evals/harness/labels.py` defines and checks the label format.

## Interview chats: how they will be scored

Each chat has the user's turns in order, `user_facts` for a simulated user who answers only from those facts, and `expected_criteria`, the card a perfect interview ends with.

- **Exact:** `intent`, `areas` and every `hard_limits` field. A wrong or invented hard limit is the costly mistake, so `must_not_invent` lists the ones to watch.
- **By feature and bound:** each preference must name the right feature and bound. Weights are only checked as strong (0.7 or more) or weak (below 0.4), because exact weights are a matter of judgement.
- **Behaviours:** `must_ask` lists what the agent has to ask before searching, such as a budget ceiling when the user says "around 200". `must_say` lists what the reply has to contain, such as `reply_in:el`, `area_not_covered:Κυψέλη` or `tradeoff_with_numbers`. These are judged per chat.
- **Not scored:** the wording of `open_questions`. They're there to show a reader what a good card looks like.

Two chats (`el_14`, `en_14`) mark schema gaps: "ground floor or lift" and "new build only" can't be hard limits yet. They test that the agent records them honestly as strong preferences instead of inventing a field.

Regenerate the JSONL from its readable source with `uv run python -m evals.harness.build_interview_chats evals/datasets/interview_chats.jsonl`.
