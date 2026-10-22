# Prompt changelog

Every prompt change gets a line here with the eval result that justified it (spec, section 9).

| Prompt | Date | Change | Eval result |
|---|---|---|---|
| extraction_v1 | 22 October 2026 | First version: the description only, every rule from the labelling guide and Mike's reading notes (D31), the glossary from `core/greek.py`, evidence quotes first, structured output (D33). | Key v1: text fields 69.4%, 72 invented (code alone 73.1%, 43). |
| extraction_v2 | 22 October 2026 | Dropped the "good" condition, which the guide doesn't have (17 inventions); a lift that goes down to the basement ("έως -1") is a lift (3 errors). | Key v1: text fields 72.2%, 58 invented. |
| extraction_v3 | 22 October 2026 | Metro: a kilometres field (code converts), all 66 Athens metro stations and the line names in the glossary, minutes by car or bus aren't on foot, only the metro's distance when a sentence gives several. Invented examples only, none from the 100 listings (D40). | Key v3: text fields 91.9% (v2 91.7%), metro 87% (v2 85%). Kilometres fixed; minutes with no "on foot" now skipped, see D40. |
| interview_v1 | 22 October 2026 | First version: fewest questions, hard limits only when stated as limits, the Greek room count, the hard cases from spec section 9, the check_supply tool for trade-offs, tags for what each reply asks (D46). No examples from the 40 chats. | 40 chats: fields 88.8%, 0 invented hard limits, behaviours 98.8%. A stated bedroom count became a preference in 17 chats. |
| interview_v2 | 22 October 2026 | A number given for price, size or bedrooms is a hard limit unless softened; intent from the price; floor_level takes numbers only, "top floor" goes in an open question; clearer budget tags (D47). | See D47. |
