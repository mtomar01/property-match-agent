"""Spitogatos feature lists: ticked (yes) and crossed out (no), from the revisit (D34).

On a Spitogatos listing page every feature in the four lists (interior,
exterior, construction, suitable for) carries an icon: a tick for yes and a
cross for no (D29: the advertiser crossed it out, so the home doesn't have it).
The 20 October collection kept only the ticked ones. The revisit reads the
crossed-out ones too.

To move the lists from the browser to here without retyping Greek, the page
script returns numbers from FEATURE_NAMES below, and only a name that isn't in
the list comes back as text. The page computes a fingerprint of the list it was
given, so a script and a decoder that disagree on the list can't be mixed up.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

SECTIONS = {"in": "Εσωτερικό", "ex": "Εξωτερικά χαρακτηριστικά", "co": "Κατασκευή", "su": "Κατάλληλο για"}

FEATURE_NAMES = (
    "Ασανσέρ", "Αποθήκη", "Parking", "Βεράντα", "Κήπος", "Ιδιωτικός Κήπος", "Κοινόχρηστος κήπος",
    "Γωνιακό", "Διαμπερές", "Οροφοδιαμέρισμα", "Ρετιρέ", "Ανακαινισμένο", "Νεόδμητο", "Χρήζει ανακαίνισης",
    "Ημιτελές", "Διατηρητέο", "Νεοκλασικό", "Υπόσκαφο", "Εσωτερική σκάλα", "Επιπλωμένο", "Τζάκι",
    "Ενδοδαπέδια θέρμανση", "Νυχτερινό ρεύμα", "Σοφίτα", "Δορυφορική κεραία", "Συναγερμός",
    "Υποδοχή με θυρωρό", "Εγκαταστάσεις φόρτισης ηλεκτρικού αυτοκινήτου", "Κλιματισμός",
    "Ηλιακός θερμοσίφωνας", "Playroom", "Πόρτα ασφαλείας", "Διπλός υαλοπίνακας", "Σίτες", "Φωτεινό",
    "Βαμμένο", "Πολυτελές", "Εντοιχισμένο BBQ", "Πρόσβαση για ΑμεΑ", "Πισίνα", "Θέα", "Τέντες",
    "Προσόψεως", "Οικιστική ζώνη", "Εξοχικό", "Επαγγελματική χρήση", "Ιατρείο", "Tουριστική ενοικίαση",
    "Επενδυτικό", "Φοιτητικό", "Μονός υαλοπίνακας", "Τριπλός υαλοπίνακας", "Μπαλκόνι",
)


def fingerprint(names: tuple[str, ...] = FEATURE_NAMES) -> str:
    return hashlib.sha256("|".join(names).encode("utf-8")).hexdigest()[:12]


def page_script(names: tuple[str, ...] = FEATURE_NAMES) -> str:
    """The script run on each listing page. It reads feature names and icons only, nothing else."""
    return """
const V = %s;
const FP = [...new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(V.join('|'))))].map(b => b.toString(16).padStart(2, '0')).join('').slice(0, 12);
const want = %s;
const t0 = Date.now();
while (Date.now() - t0 < 10000 && !document.querySelector('ul.property__features')) await new Promise(r => setTimeout(r, 400));
const out = {p: location.pathname.split('/').pop(), t: document.querySelector('h1.property__title')?.textContent.trim() || null, fp: FP, n: {}, y: {}, x: 0};
for (const h of document.querySelectorAll('h3.property__subheading')) {
  const key = want[h.textContent.trim()]; const list = h.nextElementSibling;
  if (!key || !list) continue;
  for (const li of list.querySelectorAll('li')) {
    const icon = (li.querySelector('use')?.getAttribute('href') || '').split('#')[1];
    const base = li.textContent.trim().replace(/\\s+/g, ' ').replace(/\\s*\\(.*\\)$/, '');
    const i = V.indexOf(base);
    if (icon === 'i-negative') (out.n[key] ||= []).push(i >= 0 ? i : base);
    else if (icon === 'i-correct') { if (i >= 0) (out.y[key] ||= []).push(i); }
    else out.x++;
  }
}
JSON.stringify(out)
""".strip() % (json.dumps(list(names), ensure_ascii=False), json.dumps({v: k for k, v in SECTIONS.items()}, ensure_ascii=False))


def decode(row: dict, seen: str, names: tuple[str, ...] = FEATURE_NAMES) -> dict:
    """One page's result as feature names per section, refusing a row made with another list."""
    if row.get("fp") != fingerprint(names):
        raise ValueError(f"listing {row.get('p')}: feature list fingerprint {row.get('fp')} doesn't match")

    def names_of(codes: dict) -> dict[str, list[str]]:
        return {SECTIONS[k]: [names[c] if isinstance(c, int) else str(c) for c in v] for k, v in codes.items()}

    return {"source_id": str(row["p"]), "seen": seen, "title": row.get("t"),
            "crossed": names_of(row.get("n", {})), "ticked": names_of(row.get("y", {})),
            "unmarked": row.get("x", 0), "gone": not row.get("n") and not row.get("y")}


REVISIT = Path(__file__).resolve().parents[1] / "data" / "private" / "revisit" / "features_2026-10-22.jsonl"


def attach(records: list[dict], revisit: dict[str, dict]) -> list[dict]:
    """Copies of the 20 October records, with the revisit's crossed-out lists where there is one.

    The ticked lists stay as collected on 20 October, the copy the labels were
    made against; only the crossed-out lists are new.
    """
    out = []
    for record in records:
        row = revisit.get(str(record["source_id"]))
        out.append(dict(record, crossed=row["crossed"], revisit_seen=row["seen"]) if row else dict(record))
    return out


def load(path: Path = REVISIT) -> dict[str, dict]:
    """Revisit rows by source id."""
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return {row["source_id"]: row for row in rows}
