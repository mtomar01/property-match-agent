"""The web API behind the app: chat, deck, swipes, check-ins and the shortlist, over plain HTTP (D59, D61, D66).

Standard library only, so it adds no dependency. It listens on 127.0.0.1, so
only this machine can reach it. Every route calls the same code the evals
measure: the interview (agent/interview.py, Sonnet 5.5), Mike's price and size
rules (core/card_rules.py), the hard-limit search (core/filters.py), the deck
and the pattern finder (learning/). It also serves the built React app.

One user per server (personal scale): the chat and the card are saved in
data/private/state/, the swipes in data/private/swipes/, both ignored by git.

    uv run python -m api.server                       # synthetic listings, http://127.0.0.1:8765
    PM_SNAPSHOT=data/private/snapshot.jsonl uv run python -m api.server   # your private listings

Routes:
    GET  /api/state                      -> the chat so far, the card, the swipe counts
    POST /api/chat     {"text": "..."}  -> the reply, the card as said and as searched, whether the deck is ready
    POST /api/deck     {"limit": 10}    -> the next cards, each with its two reasons
    POST /api/swipe    {"listing_id", "decision", "reasons", "deck_position", "explore_card", "note"}
                                         -> the counts, and a check-in from the assistant when code found a pattern
                                            (decision like, reject or skip; a skip with reasons is "can't judge", D71)
    POST /api/undo                       -> takes back the last decision and returns its card
    GET  /api/shortlist                  -> the liked homes, newest first
    GET  /api/export.csv                 -> the liked homes as a spreadsheet
    POST /api/reset                      -> a new search (the swipes stay)
    POST /api/search   {"card": {...}, "limit": 20}            -> the v1 table: listings that pass the card's limits
    GET  /api/listing?id=spitogatos:SYN0001                     -> one listing, its description marked untrusted
"""

from __future__ import annotations

import csv
import io
import json
import mimetypes
import os
import threading
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from adapters.snapshot import SnapshotAdapter, data_areas
from agent import interview, llm
from core import greek
from core.card_rules import search_card
from core.models import Criteria, HardLimits, set_covered_areas
from core.search import MAX_LIMIT, search
from core.reasons import typical_price_per_m2
from learning import deck, patterns
from learning.swipes import SwipeStore

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "app" / "dist"
PRIVATE = ROOT / "data" / "private"
CACHE = PRIVATE / "cache" / "app"
STATE = PRIVATE / "state"
SWIPES = PRIVATE / "swipes"
HOST, PORT = "127.0.0.1", 8765
MAX_BODY = 64_000  # bytes; a chat message or a card is far smaller
DECK_LIMIT = 10
USER = os.environ.get("PM_USER", "me")
EXPORT_COLUMNS = ("price_eur", "size_m2", "price_per_m2", "floor", "year_built", "renovated_year", "energy_class", "area",
                  "sub_area", "url", "first_seen", "previous_price_eur")  # the shortlist columns from spec section 4


class App:
    """What the routes share: the listings, the model client, this user's chat and swipes."""

    def __init__(self, adapter: SnapshotAdapter | None = None, client=None, cache_dir: Path | None = CACHE,
                 user_id: str = USER, state_dir: Path = STATE, swipes_dir: Path = SWIPES):
        self.adapter = adapter or SnapshotAdapter()
        self.areas = set_covered_areas(data_areas(self.adapter.listings()))  # what this dataset covers (D69)
        self._client = client
        self.cache_dir = cache_dir
        self.user_id = user_id
        self.state_path = state_dir / f"{user_id}.json"
        self.swipes = SwipeStore(user_id, swipes_dir)
        self.lock = threading.Lock()
        self.state = self._load()

    @property
    def client(self):
        if self._client is None:
            self._client = llm.client()
        return self._client

    # -- state --------------------------------------------------------------

    def _load(self) -> dict:
        blank = {"history": [], "card": None, "last": None, "declined": [], "pending": None, "checkin_at": 0}
        if self.state_path.exists():
            return {**blank, **json.loads(self.state_path.read_text(encoding="utf-8"))}
        return blank

    def _save(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(self.state, ensure_ascii=False), encoding="utf-8")

    def snapshot(self) -> dict:
        """What the app needs after a reload: the chat as shown, the card and the counts."""
        shown = []
        for message in self.state["history"]:
            if message["role"] == "user" and isinstance(message["content"], str) and not message["content"].startswith("<swipe_stats>"):
                shown.append({"role": "user", "text": message["content"]})
            elif message["role"] == "assistant":
                text = "".join(b["text"] for b in message["content"] if b["type"] == "text")
                try:
                    shown.append({"role": "assistant", "text": json.loads(text)["reply"]})
                except (json.JSONDecodeError, KeyError):
                    pass
        last = self.state["last"] or {}
        return {"messages": shown, "card": self.state["card"], "action": last.get("action"),
                "asking_about": last.get("asking_about", []), "unsupported": last.get("unsupported", []),
                "searched_as": search_card(self.state["card"])["hard_limits"] if self.state["card"] else None,
                "swipes": self.swipes.stats(), "data": self.data_label(), "checkin_every": patterns.CHECKIN_EVERY,
                "areas": list(self.areas)}

    def data_label(self) -> str:
        return "synthetic listings" if self.adapter.is_synthetic else "private personal-use snapshot"

    def reset(self) -> dict:
        with self.lock:
            self.state = {"history": [], "card": None, "last": None, "declined": [], "pending": None,
                          "checkin_at": len(self.swipes.verdicts())}
            self._save()
        return self.snapshot()

    # -- chat ---------------------------------------------------------------

    def _assistant(self, content: str) -> dict:
        """One turn of the interview on this user's history, saved. Returns the parsed answer and the card."""
        history = list(self.state["history"])
        history.append({"role": "user", "content": content})
        cache = self.cache_dir / interview.PROMPT_VERSION if self.cache_dir else None
        out = interview.reply(self.client, history, self.adapter.listings(), date.today().isoformat(), cache_dir=cache)
        if out["error"] or not out["output"]:
            raise RuntimeError(out["error"] or "the assistant gave no answer")
        history.extend(out["added"])
        answer, card = out["output"], out["output"]["criteria"]
        last = {"reply": answer["reply"], "action": answer["action"], "asking_about": answer["asking_about"],
                "unsupported": answer.get("unsupported", []), "repairs": out["repairs"]}
        self.state.update(history=history, card=card, last=last)
        supply = out["tool_calls"][-1]["result"] if out["tool_calls"] else None
        return {**last, "card": card, "searched_as": search_card(card)["hard_limits"], "supply": supply,
                "deck_ready": answer["action"] == "confirm" and card.get("intent") != "rent"}

    def chat(self, text: str) -> dict:
        text = (text or "").strip()
        if not text:
            raise ValueError("write a message first")
        with self.lock:
            pending = self.state["pending"]
            result = self._assistant(text)
            if pending:  # the user answered a check-in: a suggestion the card didn't take isn't offered again (D66)
                if not patterns.taken(result["card"], pending["patch"]):
                    self.state["declined"] = sorted({*self.state["declined"], pending["key"]})
                self.state["pending"] = None
            self._save()
        return {**result, "swipes": self.swipes.stats()}

    # -- deck and swipes ------------------------------------------------------

    def criteria(self) -> Criteria:
        if not self.state["card"]:
            raise ValueError("tell the assistant what you're looking for first")
        if self.state["card"].get("intent") == "rent":
            raise ValueError("rentals aren't supported yet")
        return interview.card(self.state["card"])

    def deck(self, limit: int = DECK_LIMIT) -> dict:
        criteria = self.criteria()
        everything = self.swipes.load()
        built = deck.build(self.adapter.listings(), criteria, self.swipes.swiped_ids(), start_position=len(everything),
                           limit=max(1, min(int(limit), MAX_LIMIT)), seed=len(self.swipes.verdicts()) // deck.EXPLORE_EVERY,
                           skipped_ids=self.swipes.skipped_ids())
        if built["total_matches"] < interview.THIN:  # thin: code's ways to widen, for the user to ask the assistant (D63)
            built["if_eased"] = interview.eased(criteria, self.adapter.listings())
        return {**built, "searched_as": search_card(self.state["card"])["hard_limits"], "swipes": self.swipes.stats(),
                "data": self.data_label(), "checkin_every": patterns.CHECKIN_EVERY,
                "since_checkin": len(self.swipes.verdicts()) - self.state["checkin_at"], "can_undo": bool(everything)}

    def shortlist(self) -> dict:
        """The liked homes, newest like first, for the table; the CSV has the same columns."""
        homes = []
        for listing_id in reversed(self.swipes.liked_ids()):
            listing = self.adapter.get(listing_id)
            if listing is not None:
                homes.append(listing.summary())
        return {"homes": homes, "swipes": self.swipes.stats()}

    def swipe(self, listing_id: str, decision: str, reasons: list[str] | None = None, deck_position: int = 0,
              explore_card: bool = False, note: str | None = None) -> dict:
        if self.adapter.get(listing_id) is None:
            raise KeyError(listing_id)
        with self.lock:
            self.swipes.record(listing_id, decision, reasons or [], int(deck_position), bool(explore_card), note=note)
            checkin = self._checkin() if decision != "skip" else None  # a skip is no verdict (D71)
            self._save()
        return {"swipes": self.swipes.stats(), "checkin": checkin,
                "since_checkin": len(self.swipes.verdicts()) - self.state["checkin_at"], "can_undo": True}

    def undo(self) -> dict:
        """The back button (D71): the last decision is taken back and its card returns to the front of the deck."""
        with self.lock:
            if self.state["pending"]:
                raise ValueError("answer the assistant's question first, then go back")
            last = self.swipes.undo()
            if last is None:
                raise ValueError("there's nothing to go back to")
            self.state["checkin_at"] = min(self.state["checkin_at"], len(self.swipes.verdicts()))
            self._save()
        listing = self.adapter.get(last.listing_id)
        back = None
        if listing is not None:
            back = deck.card(listing, self.criteria(), typical_price_per_m2(self.adapter.listings()), last.deck_position,
                             last.explore_card, skipped=False)
        return {"card": back, "undone": last.decision, "swipes": self.swipes.stats(),
                "since_checkin": len(self.swipes.verdicts()) - self.state["checkin_at"], "can_undo": bool(self.swipes.load())}

    def _checkin(self) -> dict | None:
        """Every 10 likes or rejects, code looks for a pattern; when it finds one, the assistant puts it to the user (D66)."""
        count = len(self.swipes.verdicts())
        if self.state["pending"] or count - self.state["checkin_at"] < patterns.CHECKIN_EVERY:
            return None
        criteria = self.criteria()
        found = patterns.observe(self.swipes.verdicts(), self.adapter.listings(), criteria, set(self.state["declined"]))
        if not found:
            return None
        top = found[0]
        total = len(deck.ranked_matches(self.adapter.listings(), criteria))
        note = {k: top[k] for k in ("feature", "kind", "line", "patch")}
        note["evidence"] = top["evidence"]["text"]
        note["homes_now"] = total
        if "would_leave" in top:
            note["homes_if_limit"] = top["would_leave"]
        message = ("<swipe_stats>\n"
                   f"After {count} swipes, this is the clearest pattern in the user's likes against their rejects:\n"
                   f"{json.dumps(note, ensure_ascii=False)}\n"
                   "Put this one suggestion to the user with its counts and ask whether to make the change. "
                   "Don't change the card until they answer.\n</swipe_stats>")
        result = self._assistant(message)
        self.state["pending"] = {"key": top["key"], "patch": top["patch"]}
        self.state["checkin_at"] = count
        return {**result, "suggestion": top}

    def export_csv(self) -> str:
        out = io.StringIO()
        writer = csv.DictWriter(out, fieldnames=["listing_id", *EXPORT_COLUMNS], extrasaction="ignore")
        writer.writeheader()
        for listing_id in self.swipes.liked_ids():
            listing = self.adapter.get(listing_id)
            if listing is not None:
                writer.writerow(listing.summary())
        return out.getvalue()

    # -- v1 routes ----------------------------------------------------------

    def search(self, card: dict, limit: int = 20) -> dict:
        if card.get("intent") == "rent":
            raise ValueError("rentals aren't supported yet")
        applied = search_card(card)
        limits = {k: v for k, v in applied["hard_limits"].items() if v not in (None, [])}
        preferences = [{k: v for k, v in p.items() if v is not None} for p in card.get("preferences") or []]
        criteria = Criteria(user_id="app", intent=card.get("intent") or "buy", areas=card.get("areas") or [],
                            hard_limits=HardLimits(**limits), preferences=preferences, confirmed_by_user=True)
        result = search(self.adapter, criteria, limit=max(1, min(int(limit), MAX_LIMIT)))
        result["searched_as"] = limits
        if result["total_matches"] < interview.THIN:  # thin: code's ways to widen, each counted (D50, D63)
            result["if_eased"] = interview.eased(criteria, self.adapter.listings())
        result["data"] = self.data_label()
        return result

    def listing(self, listing_id: str) -> dict:
        listing = self.adapter.get(listing_id)
        if listing is None:
            raise KeyError(listing_id)
        record = listing.model_dump(by_alias=True, mode="json", exclude={"description", "photo_hashes"})
        record["energy_class_greek"] = greek.energy_class_greek(listing.energy_class.value)
        record["description_untrusted"] = listing.description
        return record


def handler_for(app: App) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "PropertyMatch/2"
        app_areas = app.areas

        def log_message(self, format, *args):  # noqa: A002 - the base class's name
            pass  # quiet; errors still come back as JSON

        def _send(self, status: int, body: bytes, kind: str, extra: dict | None = None) -> None:
            self.send_response(status)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            for name, value in (extra or {}).items():
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status: int, payload: dict) -> None:
            self._send(status, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

        def _body(self) -> dict:
            size = int(self.headers.get("Content-Length") or 0)
            if size > MAX_BODY:
                raise ValueError("the request is too large")
            return json.loads(self.rfile.read(size) or b"{}")

        def do_POST(self):  # noqa: N802 - the base class's name
            route = urlparse(self.path).path
            try:
                body = self._body()
                if route == "/api/chat":
                    return self._json(200, app.chat(body.get("text", "")))
                if route == "/api/deck":
                    return self._json(200, app.deck(body.get("limit", DECK_LIMIT)))
                if route == "/api/swipe":
                    return self._json(200, app.swipe(body.get("listing_id", ""), body.get("decision", ""), body.get("reasons"),
                                                     body.get("deck_position", 0), body.get("explore_card", False),
                                                     body.get("note")))
                if route == "/api/undo":
                    return self._json(200, app.undo())
                if route == "/api/reset":
                    return self._json(200, app.reset())
                if route == "/api/search":
                    return self._json(200, app.search(body.get("card") or {}, body.get("limit", 20)))
                return self._json(404, {"error": "no such route"})
            except KeyError as err:
                return self._json(404, {"error": f"no such listing: {err}"})
            except (ValueError, TypeError) as err:
                return self._json(400, {"error": str(err)})
            except Exception as err:  # noqa: BLE001 - the app shows the reason instead of hanging
                return self._json(500, {"error": f"{type(err).__name__}: {err}"})

        def do_GET(self):  # noqa: N802 - the base class's name
            url = urlparse(self.path)
            if url.path == "/api/state":
                return self._json(200, app.snapshot())
            if url.path == "/api/shortlist":
                return self._json(200, app.shortlist())
            if url.path == "/api/export.csv":
                body = app.export_csv().encode("utf-8-sig")  # the BOM makes Excel and Sheets read the Greek
                return self._send(200, body, "text/csv; charset=utf-8",
                                  {"Content-Disposition": 'attachment; filename="shortlist.csv"'})
            if url.path == "/api/listing":
                try:
                    return self._json(200, app.listing(parse_qs(url.query).get("id", [""])[0]))
                except KeyError:
                    return self._json(404, {"error": "no such listing"})
            return self._static(url.path)

        def _static(self, path: str) -> None:
            target = (DIST / path.lstrip("/")).resolve()
            if path in ("", "/") or not target.is_file():
                target = DIST / "index.html"
            if DIST.resolve() not in target.resolve().parents and target != DIST / "index.html":
                return self._json(404, {"error": "not found"})
            if not target.exists():
                return self._json(404, {"error": "build the app first: cd app && npm run build"})
            kind = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            self._send(200, target.read_bytes(), kind)

    return Handler


def serve(app: App | None = None, host: str = HOST, port: int = PORT) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), handler_for(app or App()))


if __name__ == "__main__":
    snapshot = os.environ.get("PM_SNAPSHOT")
    server = serve(App(SnapshotAdapter(snapshot) if snapshot else None))
    print(f"Property Match on http://{HOST}:{PORT} ({'private snapshot' if snapshot else 'synthetic listings'}, user {USER}, "
          f"areas {', '.join(server.RequestHandlerClass.app_areas)})")
    server.serve_forever()
