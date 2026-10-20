"""The frozen snapshot adapter: the default for demos and every eval.

It reads a JSON Lines file of listings and never touches a live site, so eval
results can be repeated exactly. By default it serves the synthetic listings
in data/synthetic/. Point PM_SNAPSHOT at a private file (data/private/...) to
use real listings on your own machine.

Every line is validated through the Listing model when loaded, so a snapshot
with a phone number or an unknown field fails at start-up, not in front of a user.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from core.models import Listing

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SNAPSHOT = REPO_ROOT / "data" / "synthetic" / "listings.jsonl"


class SnapshotError(ValueError):
    pass


class SnapshotAdapter:
    name = "snapshot"

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path or os.environ.get("PM_SNAPSHOT") or DEFAULT_SNAPSHOT)
        self._listings: dict[str, Listing] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            raise SnapshotError(f"snapshot not found: {self.path}")
        with self.path.open(encoding="utf-8") as fh:
            for number, line in enumerate(fh, start=1):
                if not line.strip():
                    continue
                try:
                    listing = Listing.model_validate(json.loads(line))
                except Exception as exc:  # noqa: BLE001 - re-raised with the line number
                    raise SnapshotError(f"{self.path.name} line {number}: {exc}") from exc
                if listing.listing_id in self._listings:
                    raise SnapshotError(f"{self.path.name} line {number}: duplicate id {listing.listing_id}")
                self._listings[listing.listing_id] = listing

    @property
    def is_synthetic(self) -> bool:
        return all(listing.synthetic for listing in self._listings.values())

    def listings(self) -> list[Listing]:
        return list(self._listings.values())

    def get(self, listing_id: str) -> Listing | None:
        return self._listings.get(listing_id)
