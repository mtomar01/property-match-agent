"""The interface every source adapter implements (spec section 8).

One adapter per source, all behind the same two methods. If a portal changes
its layout, only its adapter breaks, and the rest of the system (search,
ranking, evals) doesn't notice.
"""

from __future__ import annotations

from typing import Iterable, Protocol

from core.models import Listing


class Adapter(Protocol):
    name: str

    def listings(self) -> Iterable[Listing]:
        """Every listing this adapter can see right now."""

    def get(self, listing_id: str) -> Listing | None:
        """One listing by id, or None if this adapter doesn't have it."""
