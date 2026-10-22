# Prompt changelog

Every prompt change gets a line here with the eval result that justified it (spec, section 9).

| Prompt | Date | Change | Eval result |
|---|---|---|---|
| extraction_v1 | 22 October 2026 | First version: the description only, every rule from the labelling guide and Mike's reading notes (D31), the glossary from `core/greek.py`, evidence quotes first, structured output (D33). | Key v1: text fields 69.4%, 72 invented (code alone 73.1%, 43). |
| extraction_v2 | 22 October 2026 | Dropped the "good" condition, which the guide doesn't have (17 inventions); a lift that goes down to the basement ("έως -1") is a lift (3 errors). | Key v1: text fields 72.2%, 58 invented. |
| extraction_v3 | 22 October 2026 | Metro: a kilometres field (code converts), all 66 Athens metro stations and the line names in the glossary, minutes by car or bus aren't on foot, only the metro's distance when a sentence gives several. Invented examples only, none from the 100 listings (D40). | Key v3: text fields 91.9% (v2 91.7%), metro 87% (v2 85%). Kilometres fixed; minutes with no "on foot" now skipped, see D40. |
