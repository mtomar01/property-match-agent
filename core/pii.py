"""Find and remove contact details from listing text before anything is stored.

Spec section 3: never store agent or owner names, phone numbers or emails.
Phones and emails have a recognisable shape, so code removes them. Personal
names don't, so they are handled by policy instead (descriptions stay in the
private snapshot only, and the model never copies names into fields).

The phone rule is deliberately broad: any run of 9 or more digits, allowing
spaces, dots and dashes between them, or digits right after "τηλ"/"tel".
Prices (at most 7 digits, such as 1.050.000), sizes and years never reach 9,
so they survive. A false positive costs a bit of text; a miss stores a phone.
"""

from __future__ import annotations

import re

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")

# 9+ digits, optionally separated by single spaces, dots, dashes or slashes,
# optionally starting with +30 or 0030.
PHONE = re.compile(r"(?:\+|00)?(?:\d[\s./-]?){8,}\d")

# "Τηλ: 2105...", "τηλ επικοινωνίας 69...", "tel. 210 ..." even when short or truncated.
PHONE_LABEL = re.compile(r"(?i)(?<!\w)(τηλ\w*|tel\w*|phone|κιν\.?)\s*[:.]?\s*(?:[^\W\d]+\s*){0,2}[:.]?\s*(?:\+|00)?\d[\d\s./-]{4,}")

PHONE_REPLACEMENT = "[phone removed]"
EMAIL_REPLACEMENT = "[email removed]"


def _digits(text: str) -> int:
    return sum(ch.isdigit() for ch in text)


def find_pii(text: str | None) -> list[str]:
    """Return the contact details found in the text (empty list if none)."""
    if not text:
        return []
    found = [m.group(0) for m in EMAIL.finditer(text)]
    found += [m.group(0) for m in PHONE.finditer(text) if _digits(m.group(0)) >= 9]
    found += [m.group(0) for m in PHONE_LABEL.finditer(text)]
    return found


def scrub(text: str | None) -> str | None:
    """Replace phones and emails with placeholders. Safe to run more than once."""
    if text is None:
        return None
    text = EMAIL.sub(EMAIL_REPLACEMENT, text)
    text = PHONE_LABEL.sub(lambda m: m.group(1) + " " + PHONE_REPLACEMENT, text)
    text = PHONE.sub(lambda m: PHONE_REPLACEMENT if _digits(m.group(0)) >= 9 else m.group(0), text)
    return text
