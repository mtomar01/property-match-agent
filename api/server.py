"""The web API behind the app (v1, D59): chat, search and one listing, over plain HTTP.

Standard library only, so it adds no dependency. It listens on 127.0.0.1, so
only this machine can reach it. Every route calls the same code the evals
measure: the interview (agent/interview.py, Sonnet 5.5), Mike's price and size
rules (core/card_rules.py) and the hard-limit search (core/search.py). It also
serves the built React app from app/dist.

    uv run python -m api.server                       # synthetic listings, http://127.0.0.1:8765
    PM_SNAPSHOT=data/private/snapshot.jsonl uv run python -m api.server   # your private listings

Routes:
    POST /api/chat     {"session": id or null, "text": "..."}  -> the reply, the card as said and as searched
    POST /api/search   {"card": {...}, "limit": 20}            -> listings that pass the card's limits
    GET  /api/listing?id=spitogatos:SYN0001                     -> one listing, its description marked untrusted
"""

from __future__ import annotations

import json
import mimetypes
import os
import threading
import uuid
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from adapters.snapshot import SnapshotAdapter
from agent import interview, llm
from core import greek
from core.card_rules import search_card
from core.models import Criteria, HardLimits
from core.search import MAX_LIMIT, search

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "app" / "dist"
CACHE = ROOT / "data" / "private" / "cache" / "app"
HOST, PORT = "127.0.0.1", 8765
MAX_BODY = 64_000  # bytes; a chat message or a card is far smaller


class App:
    """What the routes share: the listings, the model client and the open chats (in memory, this machine only)."""

    def __init__(self, adapter: SnapshotAdapter | None = None, client=None, cache_dir: Path | None = CACHE):
        self.adapter = adapter or SnapshotAdapter()
        self._client = client
        self.cache_dir = cache_dir
        self.sessions: dict[str, list[dict]] = {}
        self.lock = threading.Lock()

    @property
    def client(self):
        if self._client is None:
            self._client = llm.client()
        return self._client

    def chat(self, session: str | None, text: str) -> dict:
        text = (text or "").strip()
        if not text:
            raise ValueError("write a message first")
        with self.lock:
            session = session if session in self.sessions else uuid.uuid4().hex
            history = list(self.sessions.get(session, []))
        history.append({"role": "user", "content": text})
        cache = self.cache_dir / interview.PROMPT_VERSION if self.cache_dir else None
        out = interview.reply(self.client, history, self.adapter.listings(), date.today().isoformat(), cache_dir=cache)
        if out["error"] or not out["output"]:
            raise RuntimeError(out["error"] or "the assistant gave no answer")
        history.extend(out["added"])
        with self.lock:
            self.sessions[session] = history
        answer, card = out["output"], out["output"]["criteria"]
        supply = out["tool_calls"][-1]["result"] if out["tool_calls"] else None
        return {
            "session": session, "reply": answer["reply"], "action": answer["action"],
            "asking_about": answer["asking_about"], "unsupported": answer.get("unsupported", []),
            "card": card, "searched_as": search_card(card)["hard_limits"], "supply": supply,
            "repairs": out["repairs"],
        }

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
        result["data"] = "synthetic listings" if self.adapter.is_synthetic else "private personal-use snapshot"
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
        server_version = "PropertyMatch/1"

        def log_message(self, format, *args):  # noqa: A002 - the base class's name
            pass  # quiet; errors still come back as JSON

        def _send(self, status: int, body: bytes, kind: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
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
                    return self._json(200, app.chat(body.get("session"), body.get("text", "")))
                if route == "/api/search":
                    return self._json(200, app.search(body.get("card") or {}, body.get("limit", 20)))
                return self._json(404, {"error": "no such route"})
            except (ValueError, KeyError, TypeError) as err:
                return self._json(400, {"error": str(err)})
            except Exception as err:  # noqa: BLE001 - the app shows the reason instead of hanging
                return self._json(500, {"error": f"{type(err).__name__}: {err}"})

        def do_GET(self):  # noqa: N802 - the base class's name
            url = urlparse(self.path)
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
    print(f"Property Match on http://{HOST}:{PORT} ({'private snapshot' if snapshot else 'synthetic listings'})")
    server.serve_forever()
