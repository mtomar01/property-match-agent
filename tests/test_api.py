"""The app's web API, served for real on a free local port, with a fake model (no paid calls)."""

import json
import threading
import urllib.error
import urllib.request
from types import SimpleNamespace

import pytest

from agent import interview
from api.server import App, serve


def card(**limits):
    hard = {n: None for n in interview.HARD_FIELDS}
    hard.update(property_types=[], exclude_floors=[])
    hard.update(limits)
    return {"intent": "buy", "areas": ["Egaleo"], "hard_limits": hard, "budget_around": False, "ideally": [],
            "preferences": [], "open_questions": []}


class FakeModel:
    def __init__(self):
        self.messages, self.seen = self, []

    def create(self, **body):
        self.seen.append(body["messages"])
        out = {"reasoning": "", "reply": "Αγορά στο Αιγάλεω, έως 200.000 €. Σωστά;", "action": "confirm", "asking_about": [],
               "not_covered_areas": [], "declined_advice": [], "unsupported": [], "criteria": card(max_price_eur=200000)}
        usage = SimpleNamespace(input_tokens=1, output_tokens=1, cache_creation_input_tokens=0, cache_read_input_tokens=0)
        return SimpleNamespace(stop_reason="end_turn", usage=usage, content=[SimpleNamespace(type="text", text=json.dumps(out))])


@pytest.fixture()
def api():
    model = FakeModel()
    server = serve(App(client=model, cache_dir=None), port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"

    def ask(path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(base + path, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as err:
            return err.code, json.loads(err.read())

    yield ask, model
    server.shutdown()


def test_chat_keeps_the_conversation_and_shows_the_card_as_searched(api):
    ask, model = api
    status, first = ask("/api/chat", {"session": None, "text": "Αιγάλεω μέχρι 200 χιλιάδες"})
    assert status == 200 and first["action"] == "confirm"
    assert first["searched_as"]["min_price_eur"] == 100000  # code's lowest price, shown to the user
    status, second = ask("/api/chat", {"session": first["session"], "text": "Ναι"})
    assert second["session"] == first["session"] and len(model.seen[-1]) == 3  # user, assistant, user


def test_search_never_breaks_a_limit_and_refuses_rentals(api):
    ask, _ = api
    status, out = ask("/api/search", {"card": card(max_price_eur=200000)})
    assert status == 200 and out["searched_as"]["max_price_eur"] == 200000
    assert all(100000 <= r["price_eur"] <= 200000 and r["area"] == "Egaleo" for r in out["results"])
    status, out = ask("/api/search", {"card": dict(card(max_price_eur=900), intent="rent")})
    assert status == 400 and "rentals" in out["error"]


def test_a_listing_marks_its_description_untrusted(api):
    ask, _ = api
    status, out = ask("/api/listing?id=spitogatos:SYN0001")
    assert status == 200 and "description_untrusted" in out
    assert ask("/api/listing?id=nope")[0] == 404


def test_an_empty_message_is_refused(api):
    ask, _ = api
    status, out = ask("/api/chat", {"text": "  "})
    assert status == 400 and "message" in out["error"]
